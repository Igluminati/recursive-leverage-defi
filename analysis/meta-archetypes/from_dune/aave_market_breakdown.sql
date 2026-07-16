-- Aave v3 market breakdown for YBS collateral holders (sUSDe-focused).
-- NEW query — does not modify the existing Morpho market-breakdown or full-panel queries.
--
-- Goal: mirror from_dune/morpho_market_breakdown_individual.csv shape so
-- aave_holder_analysis.ipynb can run the same "which market / what for / LTV"
-- questions on Aave that morpho_market_breakdown.ipynb runs on Morpho.
--
-- Suggested Dune output CSV path after export:
--   analysis/meta-archetypes/from_dune/aave_market_breakdown_individual.csv
--
-- Expected columns:
--   wallet, token_name, loan_token_symbol, lltv,
--   collateral_balance, borrowed_amount

WITH ybs AS (
    SELECT * FROM (VALUES
        (0x9d39a5de30e57443bff2a8307a4256c8797a3497, 'sUSDe', 18)
        -- Aave collateral for sUSDS / syrupUSDC is zero in the current holder
        -- panel; keep the table ready if that changes later.
        -- ,(0xa3931d71877c0e7a3148cb7eb4463524fec27fbd, 'sUSDS', 18)
        -- ,(0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b, 'syrupUSDC', 6)
    ) AS t(token, token_name, decimals)
),

-- Optional: restrict to Aave sUSDe wallets exported by aave_holder_analysis.ipynb
-- (susde_aave_wallets.csv uploaded as a Dune dataset). Leave commented to
-- scan the full Aave pool.
-- target_wallets AS (
--     SELECT wallet FROM dune.YOUR_TEAM.dataset_susde_aave_wallets
-- ),

loan_tokens AS (
    SELECT * FROM (VALUES
        (0xdac17f958d2ee523a2206206994597c13d831ec7, 'USDT', 6),
        (0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48, 'USDC', 6),
        (0x4c9edd5852cd905f086c759e8383e09bff1e68b3, 'USDe', 18),
        (0x6c3ea9036406852006290770bedfcaba0e23a0e8, 'PYUSD', 6),
        (0x83f20f44975d03b1b09e64809b757c47f942beea, 'sDAI', 18)
    ) AS t(token, symbol, decimals)
),

-- Current aToken collateral per wallet for each YBS reserve
collateral AS (
    SELECT
        s."onBehalfOf" AS wallet,
        y.token_name,
        SUM(CAST(s.amount AS DOUBLE) / POWER(10, y.decimals)) AS supplied
    FROM aave_v3_ethereum.Pool_evt_Supply s
    JOIN ybs y ON s.reserve = y.token
    GROUP BY 1, 2
),
withdraws AS (
    SELECT
        w."user" AS wallet,
        y.token_name,
        SUM(CAST(w.amount AS DOUBLE) / POWER(10, y.decimals)) AS withdrawn
    FROM aave_v3_ethereum.Pool_evt_Withdraw w
    JOIN ybs y ON w.reserve = y.token
    GROUP BY 1, 2
),
collateral_balance AS (
    SELECT
        c.wallet,
        c.token_name,
        c.supplied - COALESCE(w.withdrawn, 0) AS collateral_balance
    FROM collateral c
    LEFT JOIN withdraws w
      ON w.wallet = c.wallet AND w.token_name = c.token_name
    WHERE c.supplied - COALESCE(w.withdrawn, 0) > 1
),

-- Outstanding variable debt per wallet × borrow reserve
borrows AS (
    SELECT
        b."onBehalfOf" AS wallet,
        l.symbol AS loan_token_symbol,
        SUM(CAST(b.amount AS DOUBLE) / POWER(10, l.decimals)) AS borrowed
    FROM aave_v3_ethereum.Pool_evt_Borrow b
    JOIN loan_tokens l ON b.reserve = l.token
    GROUP BY 1, 2
),
repays AS (
    SELECT
        r."user" AS wallet,
        l.symbol AS loan_token_symbol,
        SUM(CAST(r.amount AS DOUBLE) / POWER(10, l.decimals)) AS repaid
    FROM aave_v3_ethereum.Pool_evt_Repay r
    JOIN loan_tokens l ON r.reserve = l.token
    GROUP BY 1, 2
),
debt_balance AS (
    SELECT
        b.wallet,
        b.loan_token_symbol,
        b.borrowed - COALESCE(r.repaid, 0) AS borrowed_amount
    FROM borrows b
    LEFT JOIN repays r
      ON r.wallet = b.wallet AND r.loan_token_symbol = b.loan_token_symbol
    WHERE b.borrowed - COALESCE(r.repaid, 0) > 0
),

-- sUSDe stablecoin E-Mode liquidation threshold used in the whale panel
emode_lltv AS (
    SELECT 0.92 AS lltv
)

SELECT
    lower(to_hex(c.wallet)) AS wallet,
    c.token_name,
    COALESCE(d.loan_token_symbol, 'NONE') AS loan_token_symbol,
    e.lltv,
    c.collateral_balance,
    COALESCE(d.borrowed_amount, 0) AS borrowed_amount
FROM collateral_balance c
CROSS JOIN emode_lltv e
LEFT JOIN debt_balance d ON d.wallet = c.wallet
-- Uncomment once the Dune dataset exists:
-- WHERE c.wallet IN (SELECT wallet FROM target_wallets)
ORDER BY c.collateral_balance DESC, borrowed_amount DESC
;
