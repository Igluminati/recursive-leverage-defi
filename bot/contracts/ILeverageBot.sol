// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

interface IERC4626 {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256 assets);
    function previewRedeem(uint256 shares) external view returns (uint256 assets);
}

// Morpho market configuration
struct MarketParams {
    address loanToken;
    address collateralToken;
    address oracle;  // price feed
    address irm;     // Interest Rate Model
    uint256 lltv;    // Liquidation Loan-To-Value - 91.5% for yoUSD
}

// Position layout for Morpho.position(marketId, user)
struct Position {
    uint256 supplyShares;
    uint128 borrowShares;
    uint128 collateral;
}

interface IMorpho {
    function flashLoan(address token, uint256 assets, bytes calldata data) external;
    function supplyCollateral(MarketParams calldata marketParams, uint256 assets, address onBehalf, bytes calldata data) external;
    function borrow(MarketParams calldata marketParams, uint256 assets, uint256 shares, address onBehalf, address receiver) external returns (uint256 assetsBorrowed, uint256 sharesBorrowed);
    function repay(MarketParams calldata marketParams, uint256 assets, uint256 shares, address onBehalf, bytes calldata data) external returns (uint256 assetsRepaid, uint256 sharesRepaid);
    function withdrawCollateral(MarketParams calldata marketParams, uint256 assets, address onBehalf, address receiver) external;
    function position(bytes32 marketId, address user) external view returns (Position memory);
    function market(bytes32 marketId) external view returns (
        uint128 totalSupplyAssets,
        uint128 totalSupplyShares,
        uint128 totalBorrowAssets,
        uint128 totalBorrowShares,
        uint128 lastUpdate,
        uint128 fee
    );
}

// Morpho calls this on our contract during the flashloan
interface IMorphoFlashLoanCallback {
    function onMorphoFlashLoan(uint256 assets, bytes calldata data) external;
}