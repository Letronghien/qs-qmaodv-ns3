#!/usr/bin/env python3
"""
qs2_plot_paper_final.py  —  Publication-ready figures for QS-QMAODV paper
Layout: A4 two-column (column = 8.5 cm = 3.35 in), 300 DPI

Figures generated:
  fig_N.png   fig_L.png   fig_E2.png  fig_C.png   fig_S.png
  fig_W.png   fig_W2.png  fig_W3.png
  fig_overview_PDR.png    fig_overview_NRL.png
  fig_ablation.png

Chạy trên VM:
    python3 ~/qs2_plot_paper_final.py

Output: ~/QS-QMAODV-results/v5/plots/
"""

import os, sys, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from scipy import stats as scipy_stats
warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS  (A4 two-column, MDPI/IEEE style)
# ══════════════════════════════════════════════════════════════════════════════
COL1  = 3.35   # single-column width  (inches)  = 8.5 cm
COL2  = 6.89   # full-width (2 cols)  (inches)  = 17.5 cm
DPI   = 300

# Font sizes tuned for 8-9 pt after PDF scaling
plt.rcParams.update({
    'font.family':       'serif',
    'font.size':         8,
    'axes.titlesize':    8,
    'axes.labelsize':    8,
    'xtick.labelsize':   7,
    'ytick.labelsize':   7,
    'legend.fontsize':   7,
    'legend.framealpha': 0.85,
    'axes.grid':         True,
    'grid.alpha':        0.25,
    'grid.linewidth':    0.4,
    'axes.linewidth':    0.6,
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'lines.linewidth':   1.2,
    'lines.markersize':  4,
    'errorbar.capsize':  2,
    'figure.dpi':        DPI,
})

# ══════════════════════════════════════════════════════════════════════════════
# STYLE
# ══════════════════════════════════════════════════════════════════════════════
COLORS  = {
    'AODV':    '#2196F3',   # blue
    'PMAODV':  '#FF9800',   # orange
    'QMAODV':  '#4CAF50',   # green
    'QS2MAODV':'#F44336',   # red
}
MARKERS = {'AODV': 'o', 'PMAODV': 's', 'QMAODV': '^', 'QS2MAODV': 'D'}
DISPLAY = {
    'AODV':    'AODV',
    'PMAODV':  'PMAODV',
    'QMAODV':  'QMAODV',
    'QS2MAODV':'QS-QMAODV (proposed)',
}
PROTOS  = ['AODV', 'PMAODV', 'QMAODV', 'QS2MAODV']

YLABELS = {
    'PDR':             'PDR (%)',
    'Delay_ms':        'E2E Delay (ms)',
    'Throughput_kbps': 'Throughput (kbps)',
    'NRL':             'NRL',
    'EnergyPerPkt_J':  'Energy/Pkt (J)',
}
METRIC_4 = ['PDR', 'Delay_ms', 'Throughput_kbps', 'NRL']

# ══════════════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════════════
DATA_DIR = os.path.expanduser('~/QS-QMAODV-results/v5')
PLOT_DIR = os.path.join(DATA_DIR, 'plots')
os.makedirs(PLOT_DIR, exist_ok=True)

def savefig(fig, name):
    for ext in ('png', 'pdf'):
        p = os.path.join(PLOT_DIR, f'{name}.{ext}')
        fig.savefig(p, dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    print(f'  → {name}.png  ({name}.pdf)')


def load_csv(name):
    path = os.path.join(DATA_DIR, f'family_{name}.csv')
    if not os.path.exists(path):
        print(f'  [SKIP] {path} not found')
        return None
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    # Scale PDR 0-1 → 0-100
    if 'PDR' in df.columns and df['PDR'].max() <= 1.01:
        df['PDR'] = df['PDR'] * 100.0
    print(f'  Loaded {name}: {len(df)} rows | '
          f'protocols: {sorted(df["Protocol"].unique())}')
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CORE PLOT FUNCTION — 4-subplot 2×2 (full width)
# ══════════════════════════════════════════════════════════════════════════════
def plot_family4(df, x_col, x_label, x_vals, x_tick_labels,
                 suptitle, fname, metrics=None, default_x=None):
    """
    4-subplot figure (2×2) at COL2 width.
    x_vals       : actual data values for groupby
    x_tick_labels: strings shown on x-axis
    default_x    : draw vertical dashed line at this x position (index)
    """
    if metrics is None:
        metrics = [m for m in METRIC_4 if m in df.columns]

    n_metrics = len(metrics)
    ncols = 2
    nrows = (n_metrics + 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(COL2, nrows * 1.80),
                             constrained_layout=True)
    axes = np.array(axes).flatten()

    x_pos = list(range(len(x_vals)))  # integer positions for x-axis

    for ax, metric in zip(axes, metrics):
        for proto in PROTOS:
            if proto not in df['Protocol'].unique():
                continue
            sub = df[df['Protocol'] == proto]
            grp = sub.groupby(x_col)[metric]
            mn  = grp.mean().reindex(x_vals)
            sd  = grp.std().reindex(x_vals)

            ax.plot(x_pos, mn.values,
                    color=COLORS[proto], marker=MARKERS[proto],
                    label=DISPLAY[proto], clip_on=False)
            ax.fill_between(x_pos,
                            (mn - sd).values, (mn + sd).values,
                            color=COLORS[proto], alpha=0.10)

        if default_x is not None and 0 <= default_x < len(x_pos):
            ax.axvline(default_x, color='#777', lw=0.7,
                       ls='--', alpha=0.6, zorder=0)

        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_tick_labels, rotation=30, ha='right',
                           fontsize=6)
        ax.set_xlabel(x_label, labelpad=2)
        ax.set_ylabel(YLABELS.get(metric, metric), labelpad=2)
        ax.yaxis.set_major_formatter(
            ticker.FuncFormatter(lambda v, _: f'{v:.1f}'))

    # Hide any extra axes
    for ax in axes[n_metrics:]:
        ax.set_visible(False)

    # Shared legend at top
    handles = [mpatches.Patch(color=COLORS[p], label=DISPLAY[p])
               for p in PROTOS if p in df['Protocol'].unique()]
    fig.legend(handles=handles, loc='upper center',
               ncol=min(4, len(handles)),
               bbox_to_anchor=(0.5, 1.04),
               frameon=True, fontsize=7,
               handlelength=1.2, handletextpad=0.4, columnspacing=0.8)

    savefig(fig, fname)


# ══════════════════════════════════════════════════════════════════════════════
# SWEEP PLOT — W / W2 / W3  (single column, 4 subplots 2×2)
# ══════════════════════════════════════════════════════════════════════════════
def plot_sweep(df, x_col, x_label, x_vals, suptitle, fname,
               baseline_proto='QMAODV', default_val=None, metrics=None):
    """
    Single-protocol sweep (QS2MAODV) + optional QMAODV horizontal baseline.
    Single column width (COL1).
    """
    if metrics is None:
        metrics = [m for m in METRIC_4 if m in df.columns]

    ncols = 2
    nrows = (len(metrics) + 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(COL2, nrows * 1.80),
                             constrained_layout=True)
    axes = np.array(axes).flatten()

    # Sort x_vals numerically
    x_sorted = sorted(x_vals)
    x_pos    = list(range(len(x_sorted)))

    for ax, metric in zip(axes, metrics):
        # QS2MAODV sweep line
        sub_qs = df[df['Protocol'] == 'QS2MAODV'] if 'Protocol' in df.columns else df
        grp_qs = sub_qs.groupby(x_col)[metric]
        mn_qs  = grp_qs.mean().reindex(x_sorted)
        sd_qs  = grp_qs.std().reindex(x_sorted)

        ax.plot(x_pos, mn_qs.values,
                color=COLORS['QS2MAODV'], marker='D',
                label='QS-QMAODV', zorder=3)
        ax.fill_between(x_pos,
                        (mn_qs - sd_qs).values, (mn_qs + sd_qs).values,
                        color=COLORS['QS2MAODV'], alpha=0.12)

        # QMAODV horizontal baseline
        if baseline_proto and baseline_proto in df.get('Protocol', pd.Series()).unique():
            sub_qm = df[df['Protocol'] == baseline_proto]
            base   = sub_qm[metric].mean()
            ax.axhline(base, color=COLORS['QMAODV'], lw=0.9,
                       ls='--', alpha=0.75, label='QMAODV baseline')

        # Default parameter vertical line
        if default_val is not None and default_val in x_sorted:
            def_pos = x_sorted.index(default_val)
            ax.axvline(def_pos, color='#555', lw=0.7,
                       ls=':', alpha=0.7, label=f'default={default_val}')

        ax.set_xticks(x_pos)
        ax.set_xticklabels([str(v) for v in x_sorted], rotation=30,
                           ha='right', fontsize=6)
        ax.set_xlabel(x_label, labelpad=2)
        ax.set_ylabel(YLABELS.get(metric, metric), labelpad=2)

    for ax in axes[len(metrics):]:
        ax.set_visible(False)

    # Legend
    # Build from first populated axes
    legend_ax = axes[0]
    h, l = legend_ax.get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=3,
               bbox_to_anchor=(0.5, 1.04), frameon=True,
               fontsize=7, handlelength=1.2,
               handletextpad=0.4, columnspacing=0.8)

    savefig(fig, fname)


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW BAR CHART  (Fig 9, 10) — full width
# ══════════════════════════════════════════════════════════════════════════════
def plot_overview(summary_data, metric, ylabel, fname):
    """
    Bar chart: mean ± std for each protocol across 5 families.
    summary_data: dict { 'N': df_N, 'L': df_L, ... }
    """
    families   = ['N', 'L', 'E2', 'C', 'S']
    fam_labels = ['N\n(density)', 'L\n(load)', 'E2\n(energy)',
                  'C\n(stress)', 'S\n(speed)']

    n_fam = len(families)
    n_pro = len(PROTOS)
    bar_w = 0.18
    x     = np.arange(n_fam)

    fig, ax = plt.subplots(1, 1, figsize=(COL2, 2.2),
                           constrained_layout=True)

    for i, proto in enumerate(PROTOS):
        means, errs = [], []
        for fam in families:
            df = summary_data.get(fam)
            if df is None or proto not in df['Protocol'].unique():
                means.append(0); errs.append(0); continue
            vals = df[df['Protocol'] == proto][metric]
            means.append(vals.mean())
            errs.append(vals.std())

        offset = (i - n_pro / 2 + 0.5) * bar_w
        ax.bar(x + offset, means, bar_w,
               color=COLORS[proto], label=DISPLAY[proto],
               yerr=errs, error_kw={'elinewidth': 0.6, 'capsize': 2},
               alpha=0.88, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(fam_labels)
    ax.set_ylabel(ylabel, labelpad=2)
    ax.legend(loc='lower right', ncol=2, fontsize=6,
              handlelength=1.0, handletextpad=0.3)
    ax.grid(axis='y', alpha=0.25, linewidth=0.4)
    ax.set_axisbelow(True)

    savefig(fig, fname)


# ══════════════════════════════════════════════════════════════════════════════
# ABLATION PLOT  (Fig 11) — single column
# ══════════════════════════════════════════════════════════════════════════════
def plot_ablation(fname='fig_ablation'):
    """
    Ablation V1–V5 bar chart. Hardcoded from paper Table 8.
    Adjust values here if your CSV differs.
    """
    variants = ['V1\n(base)', 'V2\n(+queue)', 'V3\n(+decay)',
                'V4\n(+adap.w)', 'V5\n(+trend ε)']
    data = {
        'PDR (%)':           [30.16, 32.30, 36.37, 36.60, 37.03],
        'E2E Delay (ms)':    [224.1, 215.5, 184.1, 178.2, 173.8],
        'Throughput (kbps)': [128.4, 137.6, 155.1, 156.1, 157.9],
        'NRL':               [82.1,  126.4, 92.0,  88.2,  84.6],
    }

    metrics = list(data.keys())
    x       = np.arange(len(variants))
    bar_col = ['#9E9E9E', '#2196F3', '#F44336', '#FF9800', '#4CAF50']

    fig, axes = plt.subplots(2, 2, figsize=(COL2, 3.6),
                             constrained_layout=True)
    axes = axes.flatten()

    for ax, metric in zip(axes, metrics):
        vals = data[metric]
        bars = ax.bar(x, vals, width=0.55, color=bar_col,
                      zorder=3, alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels(variants, fontsize=6)
        ax.set_ylabel(metric, labelpad=2)
        ax.set_xlim(-0.5, len(variants) - 0.5)
        ax.grid(axis='y', alpha=0.25, linewidth=0.4)
        ax.set_axisbelow(True)
        # Annotate bars
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    f'{v:.1f}', ha='center', va='bottom', fontsize=5.5)

    savefig(fig, fname)
    print('  (Ablation uses hardcoded values — edit data{} if your CSV differs)')


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
summary_dfs = {}

# ── Fig 1: Family N ───────────────────────────────────────────────────────────
print('\n── Fig 1: Family N (Node Density) ──')
dfN = load_csv('N')
if dfN is not None:
    x_vals = sorted(dfN['nNodes'].unique())
    plot_family4(dfN, 'nNodes', 'Number of Nodes',
                 x_vals, [str(v) for v in x_vals],
                 'Family N — Node Density', 'fig_N')
    summary_dfs['N'] = dfN

# ── Fig 2: Family L ───────────────────────────────────────────────────────────
print('\n── Fig 2: Family L (Traffic Load) ──')
dfL = load_csv('L')
if dfL is not None:
    xcol_L = 'PktInterval_s' if 'PktInterval_s' in dfL.columns else 'pktInterval'
    x_vals = sorted(dfL[xcol_L].unique(), reverse=True)  # heavy → light
    labs_L = [str(v) for v in x_vals]
    plot_family4(dfL, xcol_L,
                 'Packet Interval (s)  ←heavy    light→',
                 x_vals, labs_L,
                 'Family L — Traffic Load', 'fig_L')
    summary_dfs['L'] = dfL

# ── Fig 3: Family E2 ──────────────────────────────────────────────────────────
print('\n── Fig 3: Family E2 (Energy) ──')
dfE2 = load_csv('E2')
if dfE2 is not None:
    xcol_E = 'InitEnergy_J' if 'InitEnergy_J' in dfE2.columns else 'InitEnergy'
    x_vals = sorted(dfE2[xcol_E].unique())
    met_e  = ['PDR', 'Delay_ms', 'NRL',
               'EnergyPerPkt_J' if 'EnergyPerPkt_J' in dfE2.columns else 'Throughput_kbps']
    met_e  = [m for m in met_e if m in dfE2.columns]
    plot_family4(dfE2, xcol_E,
                 'Initial Energy (J)',
                 x_vals, [str(v) for v in x_vals],
                 'Family E2 — Energy Sensitivity', 'fig_E2',
                 metrics=met_e)
    summary_dfs['E2'] = dfE2

# ── Fig 4: Family C ───────────────────────────────────────────────────────────
print('\n── Fig 4: Family C (Combined Stress) ──')
dfC = load_csv('C')
if dfC is not None:
    xcol_C = 'PktInterval_s' if 'PktInterval_s' in dfC.columns else 'pktInterval'
    C_ORDER  = [1.00, 0.50, 0.25, 0.10, 0.05]
    C_LABELS = ['L1\n1.0s/5m/s', 'L2\n0.5s/15m/s',
                'L3\n0.25s/25m/s', 'L4\n0.1s/35m/s', 'L5\n0.05s/45m/s']
    x_avail = sorted(dfC[xcol_C].unique(), reverse=True)
    c_pairs  = [(v, l) for v, l in zip(C_ORDER, C_LABELS) if v in x_avail]
    plot_family4(dfC, xcol_C,
                 'Stress Level  ←light    extreme→',
                 [p[0] for p in c_pairs], [p[1] for p in c_pairs],
                 'Family C — Combined Stress', 'fig_C')
    summary_dfs['C'] = dfC

# ── Fig 5: Family S ───────────────────────────────────────────────────────────
print('\n── Fig 5: Family S (Speed) ──')
dfS = load_csv('S')
if dfS is not None:
    speeds = [5, 15, 25, 35, 45]
    if 'Speed_ms' not in dfS.columns and 'speed' not in dfS.columns:
        n_s = len(dfS)
        expected = len(speeds) * len(PROTOS) * 30
        block = n_s // len(speeds) if n_s >= len(speeds) else 1
        speed_col = []
        for i, sp in enumerate(speeds):
            cnt = block if i < len(speeds) - 1 else (n_s - i * block)
            speed_col.extend([sp] * max(1, cnt))
        dfS['Speed_ms'] = speed_col[:n_s]
        print(f'  Speed column reconstructed ({block} rows/speed)')
    xcol_S = 'Speed_ms' if 'Speed_ms' in dfS.columns else 'speed'
    x_vals = sorted(dfS[xcol_S].unique())
    plot_family4(dfS, xcol_S, 'Node Speed (m/s)',
                 x_vals, [str(v) for v in x_vals],
                 'Family S — Node Mobility', 'fig_S')
    summary_dfs['S'] = dfS

# ── Fig 6: Family W (w3 sensitivity) ─────────────────────────────────────────
print('\n── Fig 6: Family W (w3 Sensitivity) ──')
dfW = load_csv('W')
if dfW is not None:
    w3_vals = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    if 'w3' not in dfW.columns:
        n_w = len(dfW)
        block_w = n_w // len(w3_vals) if n_w >= len(w3_vals) else 1
        w3_col = []
        for i, w in enumerate(w3_vals):
            cnt = block_w if i < len(w3_vals)-1 else (n_w - i*block_w)
            w3_col.extend([w] * max(1, cnt))
        dfW['w3'] = w3_col[:n_w]
    plot_sweep(dfW, 'w3', 'w₃ weight',
               dfW['w3'].unique() if 'w3' in dfW.columns else w3_vals,
               'Family W — w₃ Sensitivity', 'fig_W',
               baseline_proto=None, default_val=0.10)

# ── Fig 7: Family W2 (ACK-silence threshold) ─────────────────────────────────
print('\n── Fig 7: Family W2 (Threshold Sweep) ──')
dfW2 = load_csv('W2')
if dfW2 is not None:
    # SweepParam column holds threshold values
    sp_col = 'SweepParam' if 'SweepParam' in dfW2.columns else dfW2.columns[-1]
    thresholds = sorted(dfW2[sp_col].unique())
    dfW2['_sp'] = dfW2[sp_col]
    plot_sweep(dfW2, '_sp',
               'ACK-Silence Threshold (s)',
               thresholds,
               'Family W2 — ACK-Silence Threshold Sensitivity', 'fig_W2',
               baseline_proto='QMAODV', default_val=15)

# ── Fig 8: Family W3 (decay factor) ──────────────────────────────────────────
print('\n── Fig 8: Family W3 (Decay Factor Sweep) ──')
dfW3 = load_csv('W3')
if dfW3 is not None:
    sp_col = 'SweepParam' if 'SweepParam' in dfW3.columns else dfW3.columns[-1]
    decays = sorted(dfW3[sp_col].unique())
    dfW3['_sp'] = dfW3[sp_col]
    plot_sweep(dfW3, '_sp',
               'Decay Factor',
               decays,
               'Family W3 — ACK-Decay Factor Sensitivity', 'fig_W3',
               baseline_proto='QMAODV', default_val=0.92)

# ── Fig 9: Overview PDR ───────────────────────────────────────────────────────
print('\n── Fig 9: Overview PDR ──')
if summary_dfs:
    plot_overview(summary_dfs, 'PDR', 'PDR (%)', 'fig_overview_PDR')

# ── Fig 10: Overview NRL ─────────────────────────────────────────────────────
print('\n── Fig 10: Overview NRL ──')
if summary_dfs:
    plot_overview(summary_dfs, 'NRL', 'Normalized Routing Load', 'fig_overview_NRL')

# ── Fig 11: Ablation ─────────────────────────────────────────────────────────
print('\n── Fig 11: Ablation V1–V5 ──')
plot_ablation('fig_ablation')

print(f'\n✓ All figures saved to {PLOT_DIR}')
print('  Files: fig_N, fig_L, fig_E2, fig_C, fig_S,')
print('         fig_W, fig_W2, fig_W3,')
print('         fig_overview_PDR, fig_overview_NRL,')
print('         fig_ablation  (each as .png + .pdf)')
