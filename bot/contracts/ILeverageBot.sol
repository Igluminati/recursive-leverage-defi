// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

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

// Morpho market configuration
struct MarketParams {
    address loanToken;
    address collateralToken;
    address oracle;  // price feed
    address irm;     // Interest Rate Model
    uint256 lltv;    // Liquidation Loan-To-Value - 91.5% for yoUSD
}

interface IMorpho {
    function flashLoan(address token, uint256 assets, bytes calldata data) external;
    function supplyCollateral(MarketParams calldata marketParams, uint256 assets, address onBehalf, bytes calldata data) external;
    function borrow(MarketParams calldata marketParams, uint256 assets, uint256 shares, address onBehalf, address receiver) external returns (uint256 assetsBorrowed, uint256 sharesBorrowed);
}

// Morpho calls this on our contract during the flashloan
interface IMorphoFlashLoanCallback {
    function onMorphoFlashLoan(uint256 assets, bytes calldata data) external;
}