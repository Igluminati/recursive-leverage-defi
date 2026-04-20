import assert from "assert";
import {
    setup, setUsdcBalance, runLoop, runUnwind, runUnwindStep1Only, runUnwindStep2Only,
    owner, usdc, yoUsd, morpho,
    OWN_CAPITAL, REPAY_FUND, MARKET_ID,
} from "./fixtures.js";

before(async function () {
    await setup();
});


describe("LoopStrategy: unwind pre-unwind state", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE
        await setUsdcBalance(owner.address, OWN_CAPITAL);

        // ACTION
        await runLoop();
    });

    it("Morpho position has collateral before unwind", async function () {
        // ACTION
        const {collateral} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.ok(collateral > 0n);
    });

    it("Morpho position has borrow shares before unwind", async function () {
        // ACTION
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.ok(borrowShares > 0n);
    });

    it("owner has USDC in wallet from final loop borrow", async function () {
        // ACTION
        const usdcBal = await usdc.balanceOf(owner.address);

        // ASSERT
        assert.ok(usdcBal > 0n);
    });
});

describe("LoopStrategy: unwind full execution", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE
        await setUsdcBalance(owner.address, REPAY_FUND);

        // ACTION
        await runUnwind();
    });

    it("Morpho position has zero collateral after unwind", async function () {
        // ACTION
        const {collateral} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.equal(collateral, 0n);
    });

    it("Morpho position has zero borrow shares after unwind", async function () {
        // ACTION
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.equal(borrowShares, 0n);
    });

    it("owner has no yoUSD left in wallet after redeem", async function () {
        // ACTION
        const yoUsdBal = await yoUsd.balanceOf(owner.address);

        // ASSERT
        assert.equal(yoUsdBal, 0n);
    });

    it("owner receives USDC back after redeeming yoUSD", async function () {
        // ACTION
        const usdcBal = await usdc.balanceOf(owner.address);

        // ASSERT
        assert.ok(usdcBal > 0n);
    });
});


describe("LoopStrategy: Unwind: guard  no open position", function () {
    it("position is fully zeroed  re-run would exit early", async function () {
        // ACTION
        const {supplyShares, borrowShares, collateral} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.equal(borrowShares, 0n);
        assert.equal(collateral, 0n);
        assert.equal(supplyShares, 0n);
    });
});


describe("LoopStrategy: unwind atomicity crash after step 1 debt repaid, collateral still in Morpho", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE  build fresh position, then only run step 1
        await setUsdcBalance(owner.address, OWN_CAPITAL);
        await runLoop();
        await setUsdcBalance(owner.address, REPAY_FUND);

        // ACTION
        await runUnwindStep1Only();
    });

    it("borrow shares are zero  debt was repaid before crash", async function () {
        // ASSERT
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(borrowShares, 0n);
    });

    it("collateral is still in Morpho  step 2 not yet run", async function () {
        // ASSERT
        const {collateral} = await morpho.position(MARKET_ID, owner.address);
        assert.ok(collateral > 0n);
    });

    it("re-run completes the unwind from step 2 onward", async function () {
        // ACTION step 1 skipped (borrowShares=0), steps 2+3 execute
        await runUnwind();

        // ASSERT
        const {collateral, borrowShares} = await morpho.position(MARKET_ID, owner.address);
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        assert.equal(collateral, 0n);
        assert.equal(borrowShares, 0n);
        assert.equal(yoUsdBal, 0n);
    });
});

describe("LoopStrategy: unwind: atomicity crash after step 2 collateral withdrawn, yoUSD in wallet", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE — build fresh position, then only run steps 1+2
        await setUsdcBalance(owner.address, OWN_CAPITAL);
        await runLoop();
        await setUsdcBalance(owner.address, REPAY_FUND);

        // ACTION
        await runUnwindStep2Only();
    });

    it("borrow shares are zero  debt was repaid", async function () {
        // ASSERT
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(borrowShares, 0n);
    });

    it("collateral is zero  withdrawal completed before crash", async function () {
        // ASSERT
        const {collateral} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(collateral, 0n);
    });

    it("yoUSD is sitting in wallet  step 3 not yet run", async function () {
        // ASSERT — re-run will pick up here
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        assert.ok(yoUsdBal > 0n);
    });

    it("re-run completes the unwind from step 3 onward", async function () {
        // ACTION — steps 1+2 skipped, only redemption executes
        await runUnwind();

        // ASSERT
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        const usdcBal = await usdc.balanceOf(owner.address);
        assert.equal(yoUsdBal, 0n);
        assert.ok(usdcBal > 0n);
    });
});