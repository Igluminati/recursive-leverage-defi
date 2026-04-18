// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./ILeverageBot.sol";

/*
LeverageBot - yoUSD/USDC
Atomic, one-transaction leverage loop using a Morpho flashloan on Base.

execute() flow:
1. Owner approves 10 USDC and calls execute()
2. Contract pulls 10 USDC from owner
3. Requests 90 USDC flashloan from Morpho
4. Morpho calls back onMorphoFlashLoan(); contract holds 100 USDC total
5. Deposit 100 USDC into YO vault, receive 93 yoUSD (no swap, no slippage)
6. Supply yoUSD as collateral on Morpho (yoUSD/USDC market)
7. Borrow 90 USDC from Morpho against yoUSD collateral
8. Repay 90 USDC flashloan, tx completes

unwind() reverses the loop via a second Morpho flashloan: repay the debt by
shares, withdraw all yoUSD collateral, redeem yoUSD back to USDC, repay the
flashloan, and sweep any remaining USDC to the owner.
*/
contract LeverageBot is IMorphoFlashLoanCallback {
    // Base mainnet addresses
    address public constant MORPHO = 0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb;
    address public constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;

    address public constant YO_USD = 0x0000000f2eB9f69274678c76222B35eEc7588a65;

    // yoUSD/USDC Morpho market params
    address public constant MARKET_ORACLE = 0x77f59C5C09e7ABEF6991B456170930324FE36222;
    address public constant MARKET_IRM = 0x46415998764C29aB2a25CbeA6254146D50D22687;
    uint256 public constant MARKET_LLTV = 915000000000000000;
    bytes32 public constant MARKET_ID = 0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137;

    uint256 public constant OWN_CAPITAL = 10_000_000;        // 10 USDC (6dp)
    uint256 public constant FLASHLOAN_AMOUNT = 90_000_000;   // 90 USDC (6dp)

    uint256 public constant UNWIND_OVERSHOOT_BPS = 100;
    uint256 public constant BPS_DENOMINATOR = 10_000;

    uint8 private constant ACTION_LEVERAGE = 1;
    uint8 private constant ACTION_UNWIND = 2;

    address public owner;

    // Set by _onUnwind, read by unwind() once the flashloan returns.
    uint256 private _unwindUsdcReceived;

    event LeverageExecuted(
        uint256 ownCapital,
        uint256 flashloanAmount,
        uint256 yoUsdDeposited,
        uint256 usdcBorrowed
    );

    event LeverageUnwound(
        address indexed caller,
        uint256 usdcRepaid,
        uint256 yoUsdWithdrawn,
        uint256 usdcReceived,
        uint256 netToOwner
    );

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

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
    */
    function execute() external onlyOwner {
        IERC20(USDC).transferFrom(msg.sender, address(this), OWN_CAPITAL);

        bytes memory data = abi.encode(ACTION_LEVERAGE, OWN_CAPITAL, FLASHLOAN_AMOUNT);
        IMorpho(MORPHO).flashLoan(USDC, FLASHLOAN_AMOUNT, data);
    }

    // FLASHLOAN CALLBACK
    function onMorphoFlashLoan(
        uint256 flashloanAmount,
        bytes calldata data
    ) external override onlyMorpho {
        uint8 action = abi.decode(data, (uint8));

        if (action == ACTION_LEVERAGE) {
            _onLeverage(flashloanAmount, data);
        } else if (action == ACTION_UNWIND) {
            _onUnwind(flashloanAmount, data);
        } else {
            revert("LeverageBot: unknown action");
        }

        IERC20(USDC).approve(MORPHO, flashloanAmount);
    }

    // Closes the full position in one transaction and sends the owner their equity plus yield.
    function unwind() external onlyOwner {
        Position memory pos = IMorpho(MORPHO).position(MARKET_ID, address(this));
        require(pos.borrowShares > 0 || pos.collateral > 0, "LeverageBot: no position to unwind");

        uint256 owedAssets = _debtSharesToAssets(pos.borrowShares);
        uint256 flashloanAmount = (owedAssets * (BPS_DENOMINATOR + UNWIND_OVERSHOOT_BPS)) / BPS_DENOMINATOR + 1;

        uint256 usdcReceived = _runUnwindFlashloan(flashloanAmount, pos);

        uint256 netToOwner = IERC20(USDC).balanceOf(address(this));
        if (netToOwner > 0) {
            IERC20(USDC).transfer(owner, netToOwner);
        }

        emit LeverageUnwound(msg.sender, owedAssets, uint256(pos.collateral), usdcReceived, netToOwner);
    }

    // Hands control of the bot to a new owner (Gnosis Safe).
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "LeverageBot: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    // Pull any stuck tokens out of the contract.
    function rescueToken(address token, uint256 amount) external onlyOwner {
        IERC20(token).transfer(owner, amount);
    }

    function usdcBalance() external view returns (uint256) {
        return IERC20(USDC).balanceOf(address(this));
    }

    function yoUsdBalance() external view returns (uint256) {
        return IERC20(YO_USD).balanceOf(address(this));
    }

    function _onLeverage(uint256 flashloanAmount, bytes calldata data) private {
        (, uint256 ownCapital, ) = abi.decode(data, (uint8, uint256, uint256));

        uint256 totalUsdc = ownCapital + flashloanAmount;

        IERC20(USDC).approve(YO_USD, totalUsdc);
        uint256 yoUsdReceived = IERC4626(YO_USD).deposit(totalUsdc, address(this));

        MarketParams memory marketParams = _getMarketParams();
        IERC20(YO_USD).approve(MORPHO, yoUsdReceived);
        IMorpho(MORPHO).supplyCollateral(marketParams, yoUsdReceived, address(this), "");

        IMorpho(MORPHO).borrow(
            marketParams,
            flashloanAmount,
            0,
            address(this),
            address(this)
        );

        emit LeverageExecuted(ownCapital, flashloanAmount, yoUsdReceived, flashloanAmount);
    }

    function _onUnwind(uint256 flashloanAmount, bytes calldata data) private {
        (, uint256 borrowShares, uint256 collateral) = abi.decode(data, (uint8, uint256, uint256));

        MarketParams memory marketParams = _getMarketParams();

        IERC20(USDC).approve(MORPHO, flashloanAmount);
        IMorpho(MORPHO).repay(marketParams, 0, borrowShares, address(this), "");

        IMorpho(MORPHO).withdrawCollateral(marketParams, collateral, address(this), address(this));

        uint256 yoUsdHeld = IERC20(YO_USD).balanceOf(address(this));
        if (yoUsdHeld > 0) {
            _unwindUsdcReceived = IERC4626(YO_USD).redeem(yoUsdHeld, address(this), address(this));
        }
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

    function _runUnwindFlashloan(uint256 flashloanAmount, Position memory pos) private returns (uint256 usdcReceived) {
        bytes memory data = abi.encode(ACTION_UNWIND, uint256(pos.borrowShares), uint256(pos.collateral));

        _unwindUsdcReceived = 0;
        IMorpho(MORPHO).flashLoan(USDC, flashloanAmount, data);
        usdcReceived = _unwindUsdcReceived;
        _unwindUsdcReceived = 0;
    }

    // Converts borrowShares to USDC at the live market ratio, rounded up to match Morpho.
    function _debtSharesToAssets(uint128 borrowShares) private view returns (uint256) {
        (, , uint128 totalBorrowAssets, uint128 totalBorrowShares, , ) = IMorpho(MORPHO).market(MARKET_ID);
        if (totalBorrowShares == 0) return 0;
        return (uint256(borrowShares) * uint256(totalBorrowAssets) + uint256(totalBorrowShares) - 1) / uint256(totalBorrowShares);
    }
}
