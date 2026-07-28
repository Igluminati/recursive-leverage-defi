"""
Color palette + helper functions matching the chart style used in
arXiv:2506.01462v4 (figures/*.pdf). Colors sampled directly from the
rendered PDFs, not guessed.

Pair with paper_style.mplstyle:
    import matplotlib.pyplot as plt
    plt.style.use("paper_style.mplstyle")
"""

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

# Categorical series palette (5-way, used across nearly every figure).
# Order matters: linestyles below are aligned to this order.
SERIES_COLORS = {
    "Arbitrum": "#66B8EC",
    "Base":     "#DC5244",
    "Optimism": "#B7B7B7",
    "Unichain": "#DD5491",
    "ZKsync":   "#6EBC6B",
}
SERIES_LINESTYLES = {
    "Arbitrum": "-",
    "Base":     "--",
    "Optimism": "-.",
    "Unichain": "-",
    "ZKsync":   ":",
}

# Separate 3-way palette used only for stacked fee-component charts
# (fees_all_chains.pdf: Priority Fee / Base Fee / L1 Fee).
FEE_COMPONENT_COLORS = {
    "Priority Fee": "#EA3323",
    "Base Fee":     "#377E22",
    "L1 Fee":       "#0000F5",
}


# ── Protocol colors (Morpho vs Aave) ──────────────────────────────────
MORPHO_COLOR = "#6A4C93"   # purple
AAVE_COLOR   = "#2E9E8F"   # teal

# ── Whale / retailer segment colors ──────────────────────────────────
WHALE_COLOR          = "#D4793A"   # warm orange
WHALE_COLOR_LIGHT    = "#F2C29C"   # light orange (stacked segments)
RETAILER_COLOR       = "#7BAFD4"   # soft blue
RETAILER_COLOR_LIGHT = "#A6C1E0"   # light blue (stacked segments)

# ── Token colors (consistent across all charts) ──────────────────────
TOKEN_COLORS = {
    "sUSDS":     "#66B8EC",   # blue
    "sUSDe":     "#DC5244",   # red
    "syrupUSDC": "#6EBC6B",   # green
}

# ── Flashloan usage colors ────────────────────────────────────────────
FLASHLOAN_YES_COLOR = "#DD5491"   # pink
FLASHLOAN_NO_COLOR  = "#B7B7B7"   # neutral gray

# ── Risk band colors (health-factor charts) ──────────────────────────
RISK_BAND_COLORS = {
    "critical (<1.05)":     "#B22222",   # dark red
    "high_risk (1.05-1.2)": "#DD8452",   # orange
    "moderate (1.2-1.5)":   "#F2C14E",   # yellow
    "safe (>1.5)":          "#66B8EC",   # blue
}

# ── Metric comparison colors (positions vs collateral charts) ─────────
POSITIONS_COLOR  = "#B7B7B7"   # gray
COLLATERAL_COLOR = "#DC5244"   # red

# ── APY profitability colors (yield vs borrow cost) ──────────────────
NATIVE_APY_COLOR    = "#377E22"   # green (matches Base Fee green)
BORROW_COST_COLOR   = "#B22222"   # dark red
SPREAD_POS_COLOR    = "#377E22"   # green for positive spread
SPREAD_NEG_COLOR    = "#B22222"   # red for negative spread

# ── Allocation archetype colors (3-way horizontal bar) ────────────────
ALLOCATION_COLORS = {
    "spot_hold":       "#66B8EC",   # matches Arbitrum blue from the cycle
    "mix_allocation":  "#DD5491",   # matches Unichain pink from the cycle
    "fully_allocated": "#6EBC6B",   # matches ZKsync green from the cycle
}
ALLOCATION_LABELS = {
    "spot_hold":       "Spot hold / Other protocols",
    "mix_allocation":  "Mix allocation",
    "fully_allocated": "Fully allocated to Aave/Morpho",
}

# ── Protocol-group colors (for the 4-way split chart) ────────────────
PROTOCOL_GROUP_COLORS = {
    "Aave only":                     AAVE_COLOR,
    "Both":                          "#B7B7B7",   # neutral gray
    "Morpho only":                   MORPHO_COLOR,
    "Spot held / (other protocols)": "#66B8EC",
}


def annotate_bars(ax, fmt="{:.1f}", inside_frac=0.85, fontsize=8):
    """
    Label each bar with its value, matching the paper's convention:
    white bold text near the top INSIDE the bar if the bar is tall enough
    to fit it, otherwise black text just ABOVE the bar.
    """
    ymin, ymax = ax.get_ylim()
    span = ymax - ymin
    for bar in ax.patches:
        h = bar.get_height()
        x = bar.get_x() + bar.get_width() / 2
        if h >= inside_frac * 0.3 * span:  # "tall enough" heuristic
            ax.text(
                x, h * 0.92, fmt.format(h),
                ha="center", va="top", color="white", fontweight="bold",
                fontsize=fontsize,
                path_effects=[pe.withStroke(linewidth=0)],
            )
        else:
            ax.text(
                x, h + span * 0.01, fmt.format(h),
                ha="center", va="bottom", color="black", fontsize=fontsize,
            )


def plot_median_iqr_band(ax, x, median, q1, q3, series, reverted_median=None):
    """
    Reproduce the "median line + shaded IQR band (+ optional dotted
    reverted-median overlay)" style used in priority_fee_vs_index_*.pdf.
    """
    color = SERIES_COLORS[series]
    ax.fill_between(x, q1, q3, color=color, alpha=0.25, linewidth=0)
    ax.plot(x, median, color=color, linestyle="-", linewidth=2.2,
             label="Median (Successful)")
    if reverted_median is not None:
        ax.plot(x, reverted_median, color=color, linestyle=":",
                 linewidth=1.6, label="Median (Reverted)")


def facet_axes(fig_width_ratio_per_panel=2.2, n_panels=5, height=3.0,
               sharey=True):
    """Small-multiples layout used throughout: one panel per chain."""
    fig, axes = plt.subplots(
        1, n_panels,
        figsize=(fig_width_ratio_per_panel * n_panels, height),
        sharey=sharey,
    )
    for ax, name in zip(axes, SERIES_COLORS):
        ax.set_title(name)
    return fig, axes
