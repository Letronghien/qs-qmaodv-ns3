#!/usr/bin/env python3
"""
qs2_plot_W2_W3.py — Vẽ biểu đồ sensitivity sweep W2 + W3
  Family W2: ACK-Silence Threshold ∈ {5,10,15,20,30}s
  Family W3: Decay Factor ∈ {0.85,0.90,0.92,0.95,0.99}

CSV format:
  Cột 1–18: Protocol,Seed,PDR,Delay_ms,Throughput_kbps,NRL,...
  Cột 19   : SweepParam (threshold / decay value)

Output: ~/QS-QMAODV-results/v5/plots/fig_W2.png + fig_W3.png

Chạy trên VM:
    python3 ~/qs2_plot_W2_W3.py
"""

import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats as scipy_stats
warnings.filterwarnings('ignore')

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.expanduser('~/QS-QMAODV-results/v5')
PLOT_DIR = os.path.join(DATA_DIR, 'plots')
os.makedirs(PLOT_DIR, exist_ok=True)

COLOR_QS  = '#F44336'   # red — QS2MAODV
COLOR_QM  = '#4CAF50'   # green — QMAODV baseline

plt.rcParams.update({
    'font.family': 'serif', 'font.size': 11,
    'axes.titlesize': 12, 'axes.labelsize': 11,
    'xtick.labelsize': 10, 'ytick.labelsize': 10,
    'legend.fontsize': 9,  'figure.dpi': 150,
    'axes.grid': True,     'grid.alpha': 0.25,
    'axes.spines.top': False, 'axes.spines.right': False,
    'lines.linewidth': 2.2, 'lines.markersize': 7,
})

# ── Helper: Cliff's Delta ────────────────────────────────────────────────────
def cliffs_delta(a, b):
    a, b = np.array(a), np.array(b)
    n = len(a) * len(b)
    if n == 0: return 0.0
    greater = sum(1 for ai in a for bi in b if ai > bi)
    less    = sum(1 for ai in a for bi in b if ai < bi)
    return (greater - less) / n

def effect_label(cd):
    a = abs(cd)
    return ('large' if a >= 0.474 else 'medium' if a >= 0.330 else
            'small' if a >= 0.147 else 'negligible')

def sig_label(p):
    return '***' if p<0.001 else '**' if p<0.01 else '*' if p<0.05 else 'ns'

# ── Generic sweep plot (4 metrics) ────────────────────────────────────────────
def plot_sweep(df_qs, qm_means, qm_stds,
               sweep_vals, x_label, default_val,
               title, fname):
    """
    df_qs    : DataFrame for QS2MAODV rows (has SweepParam column)
    qm_means : dict {metric: scalar} — QMAODV baseline mean
    qm_stds  : dict {metric: scalar} — QMAODV baseline std
    sweep_vals: list of numeric x values
    default_val: draw vertical dashed line here (the paper's chosen value)
    """
    metrics = {
        'PDR':             'Packet Delivery Ratio (%)',
        'Delay_ms':        'End-to-End Delay (ms)',
        'Throughput_kbps': 'Throughput (kbps)',
        'NRL':             'Normalized Routing Load',
    }

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(title, fontsize=12, fontweight='bold', y=1.01)
    axes = axes.flatten()

    for ax, (metric, ylabel) in zip(axes, metrics.items()):
        grp = df_qs.groupby('SweepParam')[metric]
        mn  = grp.mean().reindex(sweep_vals)
        sd  = grp.std().reindex(sweep_vals)

        # QS2MAODV sweep line
        ax.plot(sweep_vals, mn.values,
                color=COLOR_QS, marker='D', label='QS-QMAODV (proposed)', zorder=4)
        ax.fill_between(sweep_vals,
                        (mn - sd).values, (mn + sd).values,
                        color=COLOR_QS, alpha=0.15, zorder=3)

        # QMAODV horizontal baseline
        if metric in qm_means:
            qm_m = qm_means[metric]
            qm_s = qm_stds.get(metric, 0)
            ax.axhline(qm_m, color=COLOR_QM, linestyle='--',
                       linewidth=1.8, alpha=0.85, label='QMAODV (baseline)', zorder=2)
            ax.fill_between(sweep_vals,
                            qm_m - qm_s, qm_m + qm_s,
                            color=COLOR_QM, alpha=0.08, zorder=1)

        # Default value vertical line
        ax.axvline(default_val, color='gray', linestyle=':', linewidth=1.5,
                   alpha=0.7, label=f'default={default_val}', zorder=5)

        ax.set_xlabel(x_label)
        ax.set_ylabel(ylabel)
        ax.set_xticks(sweep_vals)
        ax.set_xticklabels([str(v) for v in sweep_vals])

    # Shared legend
    handles = [
        mpatches.Patch(color=COLOR_QS, label='QS-QMAODV (proposed)'),
        mpatches.Patch(color=COLOR_QM, label='QMAODV (baseline)'),
        plt.Line2D([0],[0], color='gray', linestyle=':', label=f'default={default_val}'),
    ]
    fig.legend(handles=handles, loc='lower center', ncol=3,
               bbox_to_anchor=(0.5, -0.04), frameon=True)

    plt.tight_layout()
    for ext in ('png', 'pdf'):
        path = os.path.join(PLOT_DIR, f'{fname}.{ext}')
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  → {fname}.png  saved')
    return mn, sd


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY W2 — ACK-Silence Threshold
# ══════════════════════════════════════════════════════════════════════════════
print('\n── Family W2: ACK-Silence Threshold ──')
w2_path = os.path.join(DATA_DIR, 'family_W2.csv')

if not os.path.exists(w2_path):
    print(f'  [SKIP] {w2_path} không tồn tại')
else:
    dfW2 = pd.read_csv(w2_path)
    dfW2.columns = [c.strip() for c in dfW2.columns]
    print(f'  Loaded W2: {len(dfW2)} rows')
    print(f'  Protocols: {sorted(dfW2["Protocol"].unique())}')
    print(f'  SweepParam values: {sorted(dfW2["SweepParam"].unique())}')

    # PDR is 0–1 fraction → multiply ×100
    if dfW2['PDR'].max() <= 1.0:
        dfW2['PDR'] = dfW2['PDR'] * 100
        print('  PDR scaled ×100')

    thresh_vals = sorted([v for v in dfW2['SweepParam'].unique()
                          if dfW2[dfW2['SweepParam']==v]['Protocol'].eq('QS2MAODV').any()])
    df_qs_W2 = dfW2[dfW2['Protocol'] == 'QS2MAODV'].copy()
    df_qm_W2 = dfW2[dfW2['Protocol'] == 'QMAODV'].copy()

    qm_means_W2 = {m: df_qm_W2[m].mean() for m in
                   ['PDR','Delay_ms','Throughput_kbps','NRL'] if m in df_qm_W2.columns}
    qm_stds_W2  = {m: df_qm_W2[m].std()  for m in qm_means_W2}

    mn_W2, sd_W2 = plot_sweep(
        df_qs_W2, qm_means_W2, qm_stds_W2,
        sweep_vals=thresh_vals,
        x_label='ACK-Silence Threshold (s)',
        default_val=15,
        title='Family W2 — ACK-Silence Threshold Sensitivity\n'
              'QS-QMAODV vs QMAODV baseline (20 nodes, 30 seeds, pktInterval=0.10s)',
        fname='fig_W2',
    )

    # Print summary table
    print('\n  W2 Summary (QS2MAODV mean PDR by threshold):')
    print(f'  {"Thresh":>8} {"PDR(%)":>8} {"Delay":>8} {"NRL":>8} {"ΔPDR":>8}')
    qm_pdr = qm_means_W2.get('PDR', np.nan)
    for t in thresh_vals:
        sub = df_qs_W2[df_qs_W2['SweepParam'] == t]
        pdr = sub['PDR'].mean(); dly = sub['Delay_ms'].mean(); nrl = sub['NRL'].mean()
        print(f'  {t:>8} {pdr:>8.2f} {dly:>8.1f} {nrl:>8.3f} {pdr-qm_pdr:>+8.2f}')

    # Mann-Whitney for default (threshold=15) vs QMAODV
    a = df_qs_W2[df_qs_W2['SweepParam']==15]['PDR'].values
    b = df_qm_W2['PDR'].values
    if len(a)>=3 and len(b)>=3:
        u, p = scipy_stats.mannwhitneyu(a, b, alternative='greater')
        cd   = cliffs_delta(a, b)
        print(f'\n  W2@threshold=15 vs QMAODV: U={u:.0f}, p={p:.4f} {sig_label(p)}, '
              f"Cliff's δ={cd:.3f} ({effect_label(cd)})")


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY W3 — Decay Factor
# ══════════════════════════════════════════════════════════════════════════════
print('\n── Family W3: Decay Factor ──')
w3_path = os.path.join(DATA_DIR, 'family_W3.csv')

if not os.path.exists(w3_path):
    print(f'  [SKIP] {w3_path} không tồn tại')
else:
    dfW3 = pd.read_csv(w3_path)
    dfW3.columns = [c.strip() for c in dfW3.columns]
    print(f'  Loaded W3: {len(dfW3)} rows')
    print(f'  Protocols: {sorted(dfW3["Protocol"].unique())}')
    print(f'  SweepParam values: {sorted(dfW3["SweepParam"].unique())}')

    if dfW3['PDR'].max() <= 1.0:
        dfW3['PDR'] = dfW3['PDR'] * 100
        print('  PDR scaled ×100')

    decay_vals = sorted([v for v in dfW3['SweepParam'].unique()
                         if dfW3[dfW3['SweepParam']==v]['Protocol'].eq('QS2MAODV').any()])
    df_qs_W3 = dfW3[dfW3['Protocol'] == 'QS2MAODV'].copy()
    df_qm_W3 = dfW3[dfW3['Protocol'] == 'QMAODV'].copy()

    qm_means_W3 = {m: df_qm_W3[m].mean() for m in
                   ['PDR','Delay_ms','Throughput_kbps','NRL'] if m in df_qm_W3.columns}
    qm_stds_W3  = {m: df_qm_W3[m].std()  for m in qm_means_W3}

    mn_W3, sd_W3 = plot_sweep(
        df_qs_W3, qm_means_W3, qm_stds_W3,
        sweep_vals=decay_vals,
        x_label='Decay Factor',
        default_val=0.92,
        title='Family W3 — ACK-Decay Factor Sensitivity\n'
              'QS-QMAODV vs QMAODV baseline (20 nodes, 30 seeds, threshold=15s)',
        fname='fig_W3',
    )

    # Print summary table
    print('\n  W3 Summary (QS2MAODV mean PDR by decay factor):')
    print(f'  {"Decay":>8} {"PDR(%)":>8} {"Delay":>8} {"NRL":>8} {"ΔPDR":>8}')
    qm_pdr_w3 = qm_means_W3.get('PDR', np.nan)
    for d in decay_vals:
        sub = df_qs_W3[df_qs_W3['SweepParam'] == d]
        pdr = sub['PDR'].mean(); dly = sub['Delay_ms'].mean(); nrl = sub['NRL'].mean()
        print(f'  {d:>8} {pdr:>8.2f} {dly:>8.1f} {nrl:>8.3f} {pdr-qm_pdr_w3:>+8.2f}')

    # Mann-Whitney for default (decay=0.92) vs QMAODV
    a = df_qs_W3[df_qs_W3['SweepParam']==0.92]['PDR'].values
    b = df_qm_W3['PDR'].values
    if len(a)>=3 and len(b)>=3:
        u, p = scipy_stats.mannwhitneyu(a, b, alternative='greater')
        cd   = cliffs_delta(a, b)
        print(f'\n  W3@decay=0.92 vs QMAODV: U={u:.0f}, p={p:.4f} {sig_label(p)}, '
              f"Cliff's δ={cd:.3f} ({effect_label(cd)})")


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED W SENSITIVITY OVERVIEW (W + W2 + W3 cùng 1 figure)
# ══════════════════════════════════════════════════════════════════════════════
print('\n── Combined W Sensitivity Overview ──')

fig, axes = plt.subplots(3, 2, figsize=(13, 11))
fig.suptitle('QS-QMAODV Sensitivity Analysis — w3, Threshold, Decay Factor',
             fontsize=13, fontweight='bold', y=1.01)

row_configs = []

# Load W if exists
w_path = os.path.join(DATA_DIR, 'family_W.csv')
if os.path.exists(w_path):
    dfW = pd.read_csv(w_path)
    dfW.columns = [c.strip() for c in dfW.columns]
    if dfW['PDR'].max() <= 1.0:
        dfW['PDR'] = dfW['PDR'] * 100
    # W has no SweepParam col — reconstruct w3
    w3_vals = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    n_w = len(dfW)
    if n_w == len(w3_vals) * 30:
        w3_col = []
        for w in w3_vals: w3_col.extend([w] * 30)
        dfW['SweepParam'] = w3_col
    else:
        block = max(1, n_w // len(w3_vals))
        w3_col = []
        for i, w in enumerate(w3_vals):
            w3_col.extend([w] * min(block, n_w - i*block))
        while len(w3_col) < n_w: w3_col.append(0.50)
        dfW['SweepParam'] = w3_col[:n_w]
    row_configs.append(('Family W — w3 Weight', dfW, w3_vals, 'w3', 0.10))
else:
    row_configs.append(None)

if os.path.exists(w2_path):
    row_configs.append(('Family W2 — ACK-Silence Threshold (s)',
                        dfW2[dfW2['Protocol']=='QS2MAODV'],
                        thresh_vals, 'Threshold (s)', 15))
else:
    row_configs.append(None)

if os.path.exists(w3_path):
    row_configs.append(('Family W3 — Decay Factor',
                        dfW3[dfW3['Protocol']=='QS2MAODV'],
                        decay_vals, 'Decay Factor', 0.92))
else:
    row_configs.append(None)

for row, cfg in enumerate(row_configs):
    ax_pdr = axes[row][0]
    ax_nrl = axes[row][1]

    if cfg is None:
        for ax in [ax_pdr, ax_nrl]:
            ax.text(0.5, 0.5, 'Data not available',
                    ha='center', va='center', transform=ax.transAxes, color='gray')
        continue

    label, df_sub, xvals, xlabel, default = cfg

    # PDR
    grp_pdr = df_sub.groupby('SweepParam')['PDR']
    mn_pdr = grp_pdr.mean().reindex(xvals)
    sd_pdr = grp_pdr.std().reindex(xvals)
    ax_pdr.plot(xvals, mn_pdr.values, color=COLOR_QS, marker='D')
    ax_pdr.fill_between(xvals, (mn_pdr-sd_pdr).values, (mn_pdr+sd_pdr).values,
                        color=COLOR_QS, alpha=0.15)
    ax_pdr.axvline(default, color='gray', linestyle=':', linewidth=1.5, alpha=0.7)
    ax_pdr.set_title(label, fontsize=10, fontweight='bold')
    ax_pdr.set_xlabel(xlabel)
    ax_pdr.set_ylabel('PDR (%)')
    ax_pdr.set_xticks(xvals)
    ax_pdr.set_xticklabels([str(v) for v in xvals], rotation=30, ha='right')

    # NRL
    grp_nrl = df_sub.groupby('SweepParam')['NRL']
    mn_nrl = grp_nrl.mean().reindex(xvals)
    sd_nrl = grp_nrl.std().reindex(xvals)
    ax_nrl.plot(xvals, mn_nrl.values, color=COLOR_QS, marker='D')
    ax_nrl.fill_between(xvals, (mn_nrl-sd_nrl).values, (mn_nrl+sd_nrl).values,
                        color=COLOR_QS, alpha=0.15)
    ax_nrl.axvline(default, color='gray', linestyle=':', linewidth=1.5, alpha=0.7)
    ax_nrl.set_title('')
    ax_nrl.set_xlabel(xlabel)
    ax_nrl.set_ylabel('Normalized Routing Load')
    ax_nrl.set_xticks(xvals)
    ax_nrl.set_xticklabels([str(v) for v in xvals], rotation=30, ha='right')

handles = [
    mpatches.Patch(color=COLOR_QS, label='QS-QMAODV (proposed)'),
    plt.Line2D([0],[0], color='gray', linestyle=':', label='Default value'),
]
fig.legend(handles=handles, loc='lower center', ncol=2,
           bbox_to_anchor=(0.5, -0.02), frameon=True)

plt.tight_layout()
for ext in ('png', 'pdf'):
    fig.savefig(os.path.join(PLOT_DIR, f'fig_sensitivity_overview.{ext}'),
                dpi=300, bbox_inches='tight')
plt.close(fig)
print('  → fig_sensitivity_overview.png saved')


print(f'\n=== XONG — Plots saved → {PLOT_DIR}')
print('    fig_W2.png')
print('    fig_W3.png')
print('    fig_sensitivity_overview.png')
