-- Aave v3 Ethereum variable borrow rate for 14 July 2026, for the three stablecoins
-- that sUSDe E-Mode loopers borrow (USDT, USDC, USDe).
--
-- NEW query. Does not modify the holder panel, the market-breakdown query, or any
-- existing rate query. It only pins the borrow-cost side of the APY spread to the same
-- date as the rest of aave_holder_analysis.ipynb.
--
-- Method: TIME-WEIGHTED AVERAGE of the variable borrow rate across 14 July (UTC).
-- Aave rates move intraday and spike when utilisation crosses the kink, so the last
-- rate event of the day is not representative (an end-of-day snapshot caught USDC at
-- ~13.9%, a momentary spike). Weighting each rate by how long it was actually in force
-- during the day gives the day's true average cost of borrowing.
--
-- Suggested Dune export path after running:
--   analysis/meta-archetypes/from_dune/aave_borrow_rates_2026_07_14.csv
--
-- Output columns (match the existing rate CSVs so the notebook logic is unchanged):
--   symbol, borrow_rate            -- borrow_rate is APR in percent
--
-- Note: E-Mode changes LTV / liquidation threshold, not the reserve's base borrow rate,
-- so this reserve-level rate is exactly what E-Mode loopers pay.

WITH reserves AS (
    SELECT * FROM (VALUES
        (0xdac17f958d2ee523a2206206994597c13d831ec7, 'USDT'),
        (0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48, 'USDC'),
        (0x4c9edd5852cd905f086c759e8383e09bff1e68b3, 'USDe')
    ) AS t(reserve, symbol)
),

bounds AS (
    SELECT TIMESTAMP '2026-07-14 00:00:00' AS d0,
           TIMESTAMP '2026-07-15 00:00:00' AS d1
),

-- every rate update up to end of 14 July, as APR percent, per reserve
updates AS (
    SELECT
        r.symbol,
        u.evt_block_time AS ts,
        CAST(u.variableBorrowRate AS DOUBLE) / 1e27 * 100 AS apr
    FROM aave_v3_ethereum.Pool_evt_ReserveDataUpdated u
    JOIN reserves r ON u.reserve = r.reserve
    CROSS JOIN bounds b
    WHERE u.evt_block_time < b.d1
),

-- clip each rate's active interval to the 14 July window; the last pre-day update
-- carries the rate that was in force at 00:00
segments AS (
    SELECT
        symbol,
        apr,
        GREATEST(ts, (SELECT d0 FROM bounds)) AS seg_start,
        LEAST(
            COALESCE(
                LEAD(ts) OVER (PARTITION BY symbol ORDER BY ts),
                (SELECT d1 FROM bounds)
            ),
            (SELECT d1 FROM bounds)
        ) AS seg_end
    FROM updates
)

SELECT
    symbol,
    ROUND(
        SUM(apr * date_diff('second', seg_start, seg_end))
        / NULLIF(SUM(date_diff('second', seg_start, seg_end)), 0),
        2
    ) AS borrow_rate
FROM segments
WHERE seg_end > seg_start
GROUP BY symbol
ORDER BY symbol
;
