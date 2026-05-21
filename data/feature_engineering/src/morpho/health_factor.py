"""
Morpho Blue health factor for W-1, W-4, W-5.

TODO (Dawid): implement similar to aave/health_factor.py
- Read position(market_id, user) at EOD blocks
- Compute HF = (collateral * oracle_price * LLTV) / debt
- Merge into daily_features.csv
"""
