// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// lets us call approve etc. on any token without importing their full contract code
interface IERC20 {
    function approve(address spender, uint256 amount) external returns (bool);

    function transfer(address to, uint256 amount) external returns (bool);

    function transferFrom(address from, address to, uint256 amount) external returns (bool);

    function balanceOf(address account) external view returns (uint256);
}

// ERC4626 vault interface - deposit USDC directly into YO vault, receive yoUSD back
interface IERC4626 {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
}

// morpho MarketParams
struct MarketParams {
    address loanToken;
    address collateralToken;
    address oracle;  // price feed
    address irm; // Interest Rate Model - how much interest borrowers pay
    uint256 lltv; // Liquidation Loan-To-Value - 91.5% for yoUSD
}

// morpho core interface
interface IMorpho {
    function flashLoan(address token, uint256 assets, bytes calldata data) external;

    function supplyCollateral(MarketParams calldata marketParams, uint256 assets, address onBehalf, bytes calldata data) external;

    function borrow(MarketParams calldata marketParams, uint256 assets, uint256 shares, address onBehalf, address receiver) external returns (uint256 assetsBorrowed, uint256 sharesBorrowed);
}

// morpho will call this on our contract
interface IMorphoFlashLoanCallback {
    function onMorphoFlashLoan(uint256 assets, bytes calldata data) external;
}

/*
LeverageBot - yoUSD/USDC
Atomic, one-transaction leverage loop using a Morpho flashloan on Base.

execute() flow:
1. Owner approves 10 USDC and calls execute()
2. Contract pulls 10 USDC from owner
3. Requests 90 USDC flashloan from Morpho
4. Morpho calls back onMorphoFlashLoan() — contract holds 100 USDC total
5. Deposit 100 USDC into YO vault, receive 93 yoUSD (no swap, no slippage)
6. Supply yoUSD as collateral on Morpho (yoUSD/USDC market)
7. Borrow 90 USDC from Morpho against yoUSD collateral
8. Repay 90 USDC flashloan, tx completes

Result: 100 USDC worth of yoUSD sitting as collateral in Morpho,
        funded with only 10 USDC of your own capital so 10x leverage
*/
contract LeverageBot is IMorphoFlashLoanCallback {
    // Base mainnet addresses
    address public constant MORPHO = 0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb;
    address public constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;

    // yoUSD - YO Protocol ERC4626 vault on Base
    // deposit USDC -> receive yoUSD
    address public constant YO_USD = 0x0000000f2eB9f69274678c76222B35eEc7588a65;

    // yoUSD/USDC Morpho market params
    address public constant MARKET_ORACLE = 0x77f59C5C09e7ABEF6991B456170930324FE36222;
    address public constant MARKET_IRM = 0x46415998764C29aB2a25CbeA6254146D50D22687;
    uint256 public constant MARKET_LLTV = 915000000000000000; // 91.5


    // 90% borrow ratio, safely below 91.5% LLTV
    uint256 public constant OWN_CAPITAL = 10_000_000; // 10 USDC (6 decimals)
    uint256 public constant FLASHLOAN_AMOUNT = 90_000_000; // 90 USDC (6 decimals)

    address public immutable owner;

    event LeverageExecuted(
        uint256 ownCapital,
        uint256 flashloanAmount,
        uint256 yoUsdDeposited,
        uint256 usdcBorrowed
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "LeverageBot: not owner");
        _;
    }

    modifier onlyMorpho() {
        require(msg.sender == MORPHO, "LeverageBot: caller not Morpho");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /*
    Starts the leverage loop.
    Before calling: approve this contract to spend 10 USDC
    */
    function execute() external onlyOwner {
        // pull 10 USDC from owner into this contract
        IERC20(USDC).transferFrom(msg.sender, address(this), OWN_CAPITAL);

        // encode params to pass through the flashloan callback
        bytes memory data = abi.encode(OWN_CAPITAL, FLASHLOAN_AMOUNT);

        // request flashloan - Morpho calls onMorphoFlashLoan() before returning
        IMorpho(MORPHO).flashLoan(USDC, FLASHLOAN_AMOUNT, data);
    }

    // FLASHLOAN CALLBACK
    function onMorphoFlashLoan(
        uint256 flashloanAmount,
        bytes calldata data
    ) external override onlyMorpho {
        (uint256 ownCapital,) = abi.decode(data, (uint256, uint256));

        uint256 totalUsdc = ownCapital + flashloanAmount; // 100 USDC

        // deposit 100 USDC into YO vault, receive yoUSD
        // no swap, no slippage, no whitelist, direct ERC4626 deposit
        IERC20(USDC).approve(YO_USD, totalUsdc);

        uint256 yoUsdReceived = IERC4626(YO_USD).deposit(
            totalUsdc, // amount of USDC to deposit
            address(this)// yoUSD sent to this contract
        );

        // supply all yoUSD as collateral on Morpho
        MarketParams memory marketParams = _getMarketParams();
        IERC20(YO_USD).approve(MORPHO, yoUsdReceived);

        IMorpho(MORPHO).supplyCollateral(
            marketParams,
            yoUsdReceived,
            address(this), // collateral credited to this contract
            ""
        );

        // borrow 90 USDC from Morpho against yoUSD collateral
        IMorpho(MORPHO).borrow(
            marketParams,
            flashloanAmount, // assets to borrow
            0,               // shares (0 = use assets amount above)
            address(this),   // onBehalf = our contract takes the debt
            address(this)    // receiver = our contract gets the USDC
        );

        // approve Morpho to pull back the flashloan
        // Morpho transfers flashloanAmount from us automatically after callback returns
        IERC20(USDC).approve(MORPHO, flashloanAmount);

        emit LeverageExecuted(ownCapital, flashloanAmount, yoUsdReceived, flashloanAmount);
    }

    function _getMarketParams() private pure returns (MarketParams memory) {
        return MarketParams({
            loanToken: USDC,
            collateralToken: YO_USD,
            oracle: MARKET_ORACLE,
            irm: MARKET_IRM,
            lltv: MARKET_LLTV
        });
    }

    // pull any stuck tokens out of the contract
    function rescueToken(address token, uint256 amount) external onlyOwner {
        IERC20(token).transfer(owner, amount);
    }

    function usdcBalance() external view returns (uint256) {
        return IERC20(USDC).balanceOf(address(this));
    }

    function yoUsdBalance() external view returns (uint256) {
        return IERC20(YO_USD).balanceOf(address(this));
    }
}