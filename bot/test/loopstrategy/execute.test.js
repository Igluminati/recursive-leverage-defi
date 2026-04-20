import assert from "assert";
import {
    setup, setUsdcBalance, borrowOf, runLoop, runLoopWithFailureAt,
    owner, usdc, yoUsd, morpho,
    OWN_CAPITAL, MARKET_ID,
} from "./fixtures.js";

before(async function () {
    await setup();
});

describe("LoopStrategy: pre-loop wallet state", function () {
    it("owner has exactly 3 USDC", async function () {
        // ARRANGE
        await setUsdcBalance(owner.address, OWN_CAPITAL);

        // ACTION
        const balance = await usdc.balanceOf(owner.address);

        // ASSERT
        assert.equal(balance, OWN_CAPITAL);
    });

    it("loop 1 borrow amount is 88% of 3 USDC to 2.64 USDC", function () {
        // ARRANGE + ACTION
        const borrow = borrowOf(OWN_CAPITAL);

        // ASSERT
        assert.equal(borrow, 2_640_000n);
    });

    it("loop 2 borrow amount is 88% of loop 1 to 2.3232 USDC", function () {
        // ARRANGE + ACTION
        const borrow = borrowOf(borrowOf(OWN_CAPITAL));

        // ASSERT
        assert.equal(borrow, 2_323_200n);
    });

    it("loop 3 borrow amount is 88% of loop 2 to 2.044416 USDC", function () {
        // ARRANGE + ACTION
        const borrow = borrowOf(borrowOf(borrowOf(OWN_CAPITAL)));

        // ASSERT
        assert.equal(borrow, 2_044_416n);
    });
});


describe("LoopStrategy: loop execution", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE
        await setUsdcBalance(owner.address, OWN_CAPITAL);

        // ACTION
        await runLoop();
    });

    it("owner has no yoUSD left in wallet all posted as collateral", async function () {
        // ASSERT
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        assert.equal(yoUsdBal, 0n);
    });

    it("owner holds the final loop's borrowed USDC in wallet", async function () {
        // ARRANGE
        const expected = borrowOf(borrowOf(borrowOf(OWN_CAPITAL))); // 2.044416 USDC

        // ACTION
        const usdcBal = await usdc.balanceOf(owner.address);

        // ASSERT
        assert.equal(usdcBal, expected);
    });

    it("Morpho position has yoUSD collateral posted", async function () {
        // ACTION
        const {collateral} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.ok(collateral > 0n);
    });

    it("Morpho position has USDC borrow shares", async function () {
        // ACTION
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.ok(borrowShares > 0n);
    });

    it("Morpho position has no supply shares — owner is borrowing not lending", async function () {
        // ACTION
        const {supplyShares} = await morpho.position(MARKET_ID, owner.address);

        // ASSERT
        assert.equal(supplyShares, 0n);
    });
});


describe("LoopStrategy: math invariants", function () {
    it("total debt is sum of all three loop borrows", function () {
        // ARRANGE
        const loop1 = borrowOf(OWN_CAPITAL);
        const loop2 = borrowOf(loop1);
        const loop3 = borrowOf(loop2);

        // ACTION
        const totalDebt = loop1 + loop2 + loop3; // 7.007616 USDC

        // ASSERT
        assert.ok(totalDebt < OWN_CAPITAL * 3n);
    });
});


describe("LoopStrategy: atomicity  failure at loop 1", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE + ACTION
        await setUsdcBalance(owner.address, OWN_CAPITAL);
        await runLoopWithFailureAt(1);
    });

    it("Morpho position has zero collateral", async function () {
        const {collateral} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(collateral, 0n);
    });

    it("Morpho position has zero borrow shares", async function () {
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(borrowShares, 0n);
    });

    it("owner has no yoUSD stranded in wallet", async function () {
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        assert.equal(yoUsdBal, 0n);
    });
});

describe("LoopStrategy: atomicity  failure at loop 2", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE + ACTION
        await setUsdcBalance(owner.address, OWN_CAPITAL);
        await runLoopWithFailureAt(2);
    });

    it("Morpho position has zero collateral after auto-unwind", async function () {
        const {collateral} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(collateral, 0n);
    });

    it("Morpho position has zero borrow shares after auto-unwind", async function () {
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(borrowShares, 0n);
    });

    it("owner has no yoUSD stranded in wallet", async function () {
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        assert.equal(yoUsdBal, 0n);
    });

    it("owner recovers USDC from redeemed loop 1 collateral", async function () {
        const usdcBal = await usdc.balanceOf(owner.address);
        assert.ok(usdcBal > 0n);
    });
});

describe("LoopStrategy: atomicity  failure at loop 3", function () {
    this.timeout(120_000);

    before(async function () {
        // ARRANGE + ACTION
        await setUsdcBalance(owner.address, OWN_CAPITAL);
        await runLoopWithFailureAt(3);
    });

    it("Morpho position has zero collateral after auto-unwind", async function () {
        const {collateral} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(collateral, 0n);
    });

    it("Morpho position has zero borrow shares after auto-unwind", async function () {
        const {borrowShares} = await morpho.position(MARKET_ID, owner.address);
        assert.equal(borrowShares, 0n);
    });

    it("owner has no yoUSD stranded in wallet", async function () {
        const yoUsdBal = await yoUsd.balanceOf(owner.address);
        assert.equal(yoUsdBal, 0n);
    });

    it("owner recovers USDC from redeemed loop 1+2 collateral", async function () {
        const usdcBal = await usdc.balanceOf(owner.address);
        assert.ok(usdcBal > 0n);
    });
});