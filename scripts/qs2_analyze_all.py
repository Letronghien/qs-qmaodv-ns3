#!/usr/bin/env python3
"""
qs2_analyze_all.py — Tổng hợp dữ liệu + vẽ đồ thị tất cả families
Families: N (node density), L (load), E2 (energy redesign),
          C (combined stress), S (speed), W (w3 sensitivity)

Chạy trên VM:
    python3 ~/qs2_analyze_all.py

Output: ~/QS-QMAODV-results/v5/plots/
    fig_N.png / fig_L.png / fig_E2.png / fig_C.png
    fig_S.png / fig_W.png
    summary_stats.csv
    stat_tests.csv     (Mann-Whitney + Cliff's Delta)
"""

import os, sys, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats as scipy_stats
warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
DATA_DIR = os.path.expanduser('~/QS-QMAODV-results/v5')
PLOT_DIR = os.path.join(DATA_DIR, 'plots')
os.makedirs(PLOT_DIR, exist_ok=True)

COLORS  = {'AODV': '#2196F3', 'PMAODV': '#FF9800',
           'QMAODV': '#4CAF50', 'QS2MAODV': '#F44336'}
MARKERS = {'AODV': 'o', 'PMAODV': 's', 'QMAODV': '^', 'QS2MAODV': 'D'}
DISPLAY = {'AODV': 'AODV', 'PMAODV': 'PMAODV',
           'QMAODV': 'QMAODV', 'QS2MAODV': 'QS-QMAODV (proposed)'}
PROTOS  = ['AODV', 'PMAODV', 'QMAODV', 'QS2MAODV']

METRICS = {
    'PDR':             'Packet Delivery Ratio (%)',
    'Delay_ms':        'End-to-End Delay (ms)',
    'Throughput_kbps': 'Throughput (kbps)',
    'NRL':             'Normalized Routing Load',
    'EnergyPerPkt_J':  'Energy per Packet (J)',
    'EnergyConsumed_J':'Energy Consumed (J)',
}

plt.rcParams.update({
    'font.family': 'serif', 'font.size': 11,
    'axes.titlesize': 12, 'axes.labelsize': 11,
    'xtick.labelsize': 9,  'ytick.labelsize': 9,
    'legend.fontsize': 9,  'figure.dpi': 150,
    'axes.grid': True,     'grid.alpha': 0.25,
    'axes.spines.top': False, 'axes.spines.right': False,
    'lines.linewidth': 2.2,   'lines.markersize': 7,
})

# ═══════════════════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════════════════
def load_csv(name):
    path = os.path.join(DATA_DIR, f'family_{name}.csv')
    if not os.path.exists(path):
        print(f'  [SKIP] {path} không tồn tại')
        return None
    df = pd.read_csv(path)
    # Chuẩn hoá tên cột
    df.columns = [c.strip() for c in df.columns]
    # Đổi QS2MAODV → QS2MAODV (giữ nguyên để consistent)
    n = len(df)
    print(f'  Loaded {name}: {n} rows, protocols: {sorted(df["Protocol"].unique())}')
    return df


def cliffs_delta(a, b):
    """Cliff's Delta effect size (non-parametric)."""
    a, b = np.array(a), np.array(b)
    n = len(a) * len(b)
    if n == 0:
        return 0.0
    greater = np.sum(ai > bi for ai in a for bi in b)
    less    = np.sum(ai < bi for ai in a for bi in b)
    return (greater - less) / n


def mw_test(df, group_col, group_val, metric, proto_a='QS2MAODV', proto_b='QMAODV'):
    """Mann-Whitney U (one-sided: QS2MAODV > baseline) + Cliff's Delta."""
    sub = df[df[group_col] == group_val] if group_col else df
    a = sub[sub['Protocol'] == proto_a][metric].dropna().values
    b = sub[sub['Protocol'] == proto_b][metric].dropna().values
    if len(a) < 3 or len(b) < 3:
        return np.nan, np.nan, np.nan, np.nan
    u, p = scipy_stats.mannwhitneyu(a, b, alternative='greater')
    cd   = cliffs_delta(a, b)
    mag  = 'negligible' if abs(cd)<0.147 else 'small' if abs(cd)<0.330 else \
           'medium' if abs(cd)<0.474 else 'large'
    return u, p, cd, mag


def sig_label(p):
    if p < 0.001: return '***'
    if p < 0.01:  return '**'
    if p < 0.05:  return '*'
    if p < 0.10:  return '†'
    return 'ns'


def plot_family(df, x_col, x_label, x_vals, x_ticks,
                title, fname, metrics=None):
    """4-subplot figure: PDR, Delay, Throughput, NRL."""
    if metrics is None:
        metrics = list(METRICS.keys())

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(title, fontsize=13, fontweight='bold', y=1.01)
    axes = axes.flatten()

    for ax, metric in zip(axes, metrics):
        for proto in PROTOS:
            if proto not in df['Protocol'].unique():
                continue
            sub = df[df['Protocol'] == proto]
            grp = sub.groupby(x_col)[metric]
            mn  = grp.mean().reindex(x_vals)
            sd  = grp.std().reindex(x_vals)

            ax.plot(x_ticks, mn.values,
                    color=COLORS[proto], marker=MARKERS[proto],
                    label=DISPLAY[proto], zorder=3)
            ax.fill_between(x_ticks,
                            (mn - sd).values, (mn + sd).values,
                            color=COLORS[proto], alpha=0.12, zorder=2)

        ax.set_xlabel(x_label)
        ax.set_ylabel(METRICS[metric])
        ax.set_xticks(x_ticks)
        ax.set_xticklabels([str(v) for v in x_vals], rotation=30, ha='right')

    # Legend dùng axes[0]
    handles = [mpatches.Patch(color=COLORS[p], label=DISPLAY[p]) for p in PROTOS
               if p in df['Protocol'].unique()]
    fig.legend(handles=handles, loc='lower center', ncol=4,
               bbox_to_anchor=(0.5, -0.04), frameon=True)

    plt.tight_layout()
    for ext in ('png', 'pdf'):
        path = os.path.join(PLOT_DIR, f'{fname}.{ext}')
        fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  → {fname}.png saved')


def plot_2metric(df, x_col, x_label, x_vals, x_ticks,
                 title, fname, m1='PDR', m2='NRL'):
    """2-subplot: PDR + NRL (cho W sensitivity)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.suptitle(title, fontsize=12, fontweight='bold')

    for ax, metric in zip(axes, [m1, m2]):
        for proto in PROTOS:
            if proto not in df['Protocol'].unique():
                continue
            sub = df[df['Protocol'] == proto]
            grp = sub.groupby(x_col)[metric]
            mn  = grp.mean().reindex(x_vals)
            sd  = grp.std().reindex(x_vals)
            ax.plot(x_ticks, mn.values,
                    color=COLORS[proto], marker=MARKERS[proto],
                    label=DISPLAY[proto])
            ax.fill_between(x_ticks, (mn-sd).values, (mn+sd).values,
                            color=COLORS[proto], alpha=0.12)
        ax.set_xlabel(x_label)
        ax.set_ylabel(METRICS[metric])
        ax.set_xticks(x_ticks)
        ax.set_xticklabels([str(v) for v in x_vals], rotation=30, ha='right')

    handles = [mpatches.Patch(color=COLORS[p], label=DISPLAY[p]) for p in PROTOS
               if p in df['Protocol'].unique()]
    fig.legend(handles=handles, loc='lower center', ncol=4,
               bbox_to_anchor=(0.5, -0.08), frameon=True)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(PLOT_DIR, f'{fname}.{ext}'),
                    dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  → {fname}.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
summary_rows = []
stat_rows    = []

def add_summary(family, group_col, group_val, df):
    for proto in PROTOS:
        sub = df[(df['Protocol'] == proto)]
        if group_col:
            sub = sub[sub[group_col] == group_val]
        if len(sub) == 0:
            continue
        row = {
            'Family': family,
            group_col if group_col else 'All': group_val,
            'Protocol':  proto,
            'PDR_mean':  round(sub['PDR'].mean(), 2),
            'PDR_std':   round(sub['PDR'].std(),  2),
            'Delay_mean':round(sub['Delay_ms'].mean(), 1),
            'Delay_std': round(sub['Delay_ms'].std(),  1),
            'Tput_mean': round(sub['Throughput_kbps'].mean(), 2),
            'NRL_mean':  round(sub['NRL'].mean(), 3),
            'N_runs':    len(sub),
        }
        summary_rows.append(row)

def add_stat(family, group_col, group_val, df, metric='PDR'):
    u, p, cd, mag = mw_test(
        df[df[group_col]==group_val] if group_col else df,
        None, None, metric)
    # mean difference
    qs = df[df['Protocol']=='QS2MAODV']
    qm = df[df['Protocol']=='QMAODV']
    if group_col:
        qs = qs[qs[group_col]==group_val]
        qm = qm[qm[group_col]==group_val]
    delta = round(qs[metric].mean() - qm[metric].mean(), 3) if len(qs)>0 and len(qm)>0 else np.nan
    stat_rows.append({
        'Family':   family,
        'Condition': f'{group_col}={group_val}' if group_col else 'all',
        'Metric':   metric,
        'Delta':    delta,
        'U':        round(u, 1) if not np.isnan(u) else '',
        'p_value':  f'{p:.4f}' if not np.isnan(p) else '',
        'sig':      sig_label(p) if not np.isnan(p) else '',
        'CliffD':   round(cd, 3) if not np.isnan(cd) else '',
        'Effect':   mag if not np.isnan(cd) else '',
    })

# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY N — Node Density
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Family N: Node Density ──')
dfN = load_csv('N')
if dfN is not None:
    x_vals  = sorted(dfN['nNodes'].unique())
    x_ticks = list(range(len(x_vals)))
    x_map   = {v: i for i, v in enumerate(x_vals)}
    dfN['_x'] = dfN['nNodes'].map(x_map)
    plot_family(dfN, 'nNodes', 'Number of Nodes', x_vals,
                [str(v) for v in x_vals],
                'Family N — Node Density (30 seeds, 200s)',
                'fig_N')
    for nv in x_vals:
        add_summary('N', 'nNodes', nv, dfN)
        add_stat('N', 'nNodes', nv, dfN, 'PDR')
        add_stat('N', 'nNodes', nv, dfN, 'NRL')

# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY L — Traffic Load
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Family L: Traffic Load ──')
dfL = load_csv('L')
if dfL is not None:
    x_vals  = sorted(dfL['PktInterval_s'].unique(), reverse=True)  # high→low load
    plot_family(dfL, 'PktInterval_s',
                'Packet Interval (s)  ←heavy    light→',
                x_vals, [str(v) for v in x_vals],
                'Family L — Traffic Load (20 nodes, 30 seeds, 200s)',
                'fig_L')
    for v in x_vals:
        add_summary('L', 'PktInterval_s', v, dfL)
        add_stat('L', 'PktInterval_s', v, dfL, 'PDR')

# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY E2 — Battery Depletion Redesign
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Family E2: Battery Depletion (redesign) ──')
dfE2 = load_csv('E2')
if dfE2 is not None:
    x_vals = sorted(dfE2['InitEnergy_J'].unique())
    plot_family(dfE2, 'InitEnergy_J',
                'Initial Energy (J)',
                x_vals, [str(v) for v in x_vals],
                'Family E2 — Battery Depletion (20 nodes, energy {1–20}J, 30 seeds)',
                'fig_E2',
                metrics=['PDR', 'Delay_ms', 'NRL', 'EnergyPerPkt_J']
                if 'EnergyPerPkt_J' in dfE2.columns else None)
    for v in x_vals:
        add_summary('E2', 'InitEnergy_J', v, dfE2)
        add_stat('E2', 'InitEnergy_J', v, dfE2, 'PDR')

# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY C — Combined Stress
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Family C: Combined Stress ──')
dfC = load_csv('C')
if dfC is not None:
    # Map pktInterval → stress level label (pi unique per level)
    C_MAP = {1.00: 'L1\n(1.0s/5m/s)',  0.50: 'L2\n(0.5s/15m/s)',
             0.25: 'L3\n(0.25s/25m/s)',0.10: 'L4\n(0.1s/35m/s)',
             0.05: 'L5\n(0.05s/45m/s)'}
    dfC['StressLevel'] = dfC['PktInterval_s'].map(C_MAP)
    c_order = ['L1\n(1.0s/5m/s)', 'L2\n(0.5s/15m/s)', 'L3\n(0.25s/25m/s)',
               'L4\n(0.1s/35m/s)', 'L5\n(0.05s/45m/s)']
    x_vals_c = [1.00, 0.50, 0.25, 0.10, 0.05]
    plot_family(dfC, 'PktInterval_s',
                'Stress Level  ←light    extreme→',
                x_vals_c, c_order,
                'Family C — Combined Stress: Load + Mobility (20 nodes, 30 seeds, 200s)',
                'fig_C')
    for v in x_vals_c:
        add_summary('C', 'PktInterval_s', v, dfC)
        add_stat('C', 'PktInterval_s', v, dfC, 'PDR')

# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY S — Node Speed
# Speed NOT in CSV → reconstruct từ row order (sequential run: 120 rows/speed)
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Family S: Node Speed ──')
dfS = load_csv('S')
if dfS is not None:
    n_s = len(dfS)
    speeds = [5, 15, 25, 35, 45]
    expected_s = len(speeds) * len(PROTOS) * 30  # 600
    if n_s == expected_s:
        block = expected_s // len(speeds)   # 120
        speed_col = []
        for sp in speeds:
            speed_col.extend([sp] * block)
        dfS['Speed_ms'] = speed_col
        print(f'  Speed column reconstructed: {block} rows/speed')
    else:
        # Partial data — reconstruct best-effort
        block = n_s // len(speeds) if n_s >= len(speeds) else 1
        speed_col = []
        for i, sp in enumerate(speeds):
            end = min((i+1)*block, n_s)
            speed_col.extend([sp] * (end - i*block))
        while len(speed_col) < n_s:
            speed_col.append(45)
        dfS['Speed_ms'] = speed_col[:n_s]
        print(f'  WARN: {n_s} rows ≠ {expected_s} expected — partial reconstruction')

    x_vals = sorted(dfS['Speed_ms'].unique())
    plot_family(dfS, 'Speed_ms',
                'Node Speed (m/s)',
                x_vals, [str(v) for v in x_vals],
                'Family S — Node Mobility (20 nodes, 30 seeds, 200s)',
                'fig_S')
    for v in x_vals:
        add_summary('S', 'Speed_ms', v, dfS)
        add_stat('S', 'Speed_ms', v, dfS, 'PDR')

# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY W — w3 Sensitivity (QS2MAODV only)
# w3 NOT in CSV → reconstruct từ row order (sequential run: 30 rows/w3)
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Family W: w3 Sensitivity ──')
dfW = load_csv('W')
if dfW is not None:
    w3_vals = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    expected_w = len(w3_vals) * 30  # 270
    n_w = len(dfW)
    if n_w == expected_w:
        w3_col = []
        for w in w3_vals:
            w3_col.extend([w] * 30)
        dfW['w3'] = w3_col
        print(f'  w3 column reconstructed: 30 rows/w3')
    else:
        block_w = n_w // len(w3_vals) if n_w >= len(w3_vals) else 1
        w3_col = []
        for i, w in enumerate(w3_vals):
            end = min((i+1)*block_w, n_w)
            w3_col.extend([w] * (end - i*block_w))
        while len(w3_col) < n_w:
            w3_col.append(0.50)
        dfW['w3'] = w3_col[:n_w]
        print(f'  WARN: {n_w} rows ≠ {expected_w} — partial reconstruction')

    # W chỉ có QS2MAODV
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    fig.suptitle('Family W — w3 Sensitivity: QS-QMAODV (20 nodes, pktInterval=0.10s, 30 seeds)',
                 fontsize=11, fontweight='bold')
    for ax, metric in zip(axes, METRICS.keys()):
        grp = dfW.groupby('w3')[metric]
        mn = grp.mean()
        sd = grp.std()
        ax.plot(mn.index, mn.values, color=COLORS['QS2MAODV'],
                marker='D', linewidth=2.2, markersize=7)
        ax.fill_between(mn.index, (mn-sd).values, (mn+sd).values,
                        color=COLORS['QS2MAODV'], alpha=0.15)
        ax.axvline(0.10, color='gray', linestyle='--', alpha=0.5,
                   label='default w3=0.10')
        ax.set_xlabel('w3')
        ax.set_ylabel(METRICS[metric])
        ax.set_xticks(w3_vals)
        ax.set_xticklabels([str(w) for w in w3_vals], rotation=45, ha='right')
    axes[0].legend(fontsize=8)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(PLOT_DIR, f'fig_W.{ext}'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('  → fig_W.png saved')

    # Summary W
    for w in w3_vals:
        sub = dfW[dfW['w3'] == w]
        summary_rows.append({
            'Family': 'W', 'w3': w, 'Protocol': 'QS2MAODV',
            'PDR_mean': round(sub['PDR'].mean(), 2),
            'PDR_std':  round(sub['PDR'].std(), 2),
            'Delay_mean': round(sub['Delay_ms'].mean(), 1),
            'NRL_mean': round(sub['NRL'].mean(), 3),
            'N_runs': len(sub),
        })

# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED OVERVIEW PLOT — PDR tất cả families (QS2MAODV vs QMAODV)
# ═══════════════════════════════════════════════════════════════════════════════
print('\n── Combined Overview Plot ──')
fig, axes = plt.subplots(2, 3, figsize=(16, 9))
fig.suptitle('QS-QMAODV vs Baselines — PDR (%) Summary Across All Families',
             fontsize=13, fontweight='bold', y=1.01)
axes = axes.flatten()

configs = [
    ('N',  dfN if dfN is not None else None,  'nNodes',       'Number of Nodes'),
    ('L',  dfL if dfL is not None else None,  'PktInterval_s','Packet Interval (s)'),
    ('E2', dfE2 if dfE2 is not None else None,'InitEnergy_J', 'Initial Energy (J)'),
    ('C',  dfC if dfC is not None else None,  'PktInterval_s','Stress Level'),
    ('S',  dfS if dfS is not None else None,  'Speed_ms',     'Speed (m/s)'),
    ('W',  dfW if dfW is not None else None,  'w3',           'w3 weight'),
]

for ax, (name, df, xcol, xlabel) in zip(axes, configs):
    ax.set_title(f'Family {name}', fontweight='bold')
    ax.set_xlabel(xlabel); ax.set_ylabel('PDR (%)')
    if df is None or xcol not in df.columns:
        ax.text(0.5, 0.5, 'Data not available',
                ha='center', va='center', transform=ax.transAxes, color='gray')
        continue
    x_vals_p = sorted(df[xcol].unique())
    protos_here = PROTOS if name != 'W' else ['QS2MAODV']
    for proto in protos_here:
        if proto not in df['Protocol'].unique():
            continue
        sub = df[df['Protocol'] == proto]
        mn  = sub.groupby(xcol)['PDR'].mean().reindex(x_vals_p)
        sd  = sub.groupby(xcol)['PDR'].std().reindex(x_vals_p)
        xs  = list(range(len(x_vals_p)))
        ax.plot(xs, mn.values, color=COLORS[proto], marker=MARKERS[proto],
                label=DISPLAY[proto])
        ax.fill_between(xs, (mn-sd).values, (mn+sd).values,
                        color=COLORS[proto], alpha=0.10)
    ax.set_xticks(range(len(x_vals_p)))
    ax.set_xticklabels([str(v) for v in x_vals_p], rotation=30, ha='right')

handles = [mpatches.Patch(color=COLORS[p], label=DISPLAY[p]) for p in PROTOS]
fig.legend(handles=handles, loc='lower center', ncol=4,
           bbox_to_anchor=(0.5, -0.04), frameon=True)
plt.tight_layout()
for ext in ('png', 'pdf'):
    fig.savefig(os.path.join(PLOT_DIR, f'fig_overview_PDR.{ext}'),
                dpi=300, bbox_inches='tight')
plt.close(fig)
print('  → fig_overview_PDR.png saved')

# ═══════════════════════════════════════════════════════════════════════════════
# NRL OVERVIEW — cùng layout nhưng metric = NRL
# ═══════════════════════════════════════════════════════════════════════════════
fig2, axes2 = plt.subplots(2, 3, figsize=(16, 9))
fig2.suptitle('QS-QMAODV vs Baselines — Normalized Routing Load (NRL) Across Families',
              fontsize=13, fontweight='bold', y=1.01)
axes2 = axes2.flatten()
for ax, (name, df, xcol, xlabel) in zip(axes2, configs):
    ax.set_title(f'Family {name}', fontweight='bold')
    ax.set_xlabel(xlabel); ax.set_ylabel('NRL')
    if df is None or xcol not in df.columns:
        ax.text(0.5, 0.5, 'Data not available',
                ha='center', va='center', transform=ax.transAxes, color='gray')
        continue
    x_vals_p = sorted(df[xcol].unique())
    protos_here = PROTOS if name != 'W' else ['QS2MAODV']
    for proto in protos_here:
        if proto not in df['Protocol'].unique():
            continue
        sub = df[df['Protocol'] == proto]
        mn  = sub.groupby(xcol)['NRL'].mean().reindex(x_vals_p)
        sd  = sub.groupby(xcol)['NRL'].std().reindex(x_vals_p)
        xs  = list(range(len(x_vals_p)))
        ax.plot(xs, mn.values, color=COLORS[proto], marker=MARKERS[proto],
                label=DISPLAY[proto])
        ax.fill_between(xs, (mn-sd).values, (mn+sd).values,
                        color=COLORS[proto], alpha=0.10)
    ax.set_xticks(range(len(x_vals_p)))
    ax.set_xticklabels([str(v) for v in x_vals_p], rotation=30, ha='right')

fig2.legend(handles=handles, loc='lower center', ncol=4,
            bbox_to_anchor=(0.5, -0.04), frameon=True)
plt.tight_layout()
for ext in ('png', 'pdf'):
    fig2.savefig(os.path.join(PLOT_DIR, f'fig_overview_NRL.{ext}'),
                 dpi=300, bbox_inches='tight')
plt.close(fig2)
print('  → fig_overview_NRL.png saved')

# ═══════════════════════════════════════════════════════════════════════════════
# SAVE SUMMARY CSV + STAT CSV
# ═══════════════════════════════════════════════════════════════════════════════
if summary_rows:
    dfsum = pd.DataFrame(summary_rows)
    sout  = os.path.join(DATA_DIR, 'summary_stats.csv')
    dfsum.to_csv(sout, index=False)
    print(f'\n  → summary_stats.csv saved ({len(dfsum)} rows)')

if stat_rows:
    dfstat = pd.DataFrame(stat_rows)
    stout  = os.path.join(DATA_DIR, 'stat_tests.csv')
    dfstat.to_csv(stout, index=False)
    print(f'  → stat_tests.csv saved ({len(dfstat)} rows)')

# ═══════════════════════════════════════════════════════════════════════════════
# PRINT TỔNG HỢP NHANH
# ═══════════════════════════════════════════════════════════════════════════════
print('\n' + '='*70)
print('TỔNG HỢP: QS2MAODV vs QMAODV (mean across all conditions per family)')
print('='*70)
print(f'{"Family":<8} {"ΔPDR":>8} {"ΔDelay":>10} {"ΔNRL":>10} {"best p":>10}')
print('-'*70)

all_dfs = [('N', dfN, 'nNodes'), ('L', dfL, 'PktInterval_s'),
           ('E2', dfE2, 'InitEnergy_J'), ('C', dfC, 'PktInterval_s'),
           ('S', dfS if dfS is not None and 'Speed_ms' in (dfS.columns if dfS is not None else []) else None, 'Speed_ms')]

for fname, df, xcol in all_dfs:
    if df is None:
        print(f'{fname:<8} {"N/A":>8}')
        continue
    qs = df[df['Protocol'] == 'QS2MAODV']
    qm = df[df['Protocol'] == 'QMAODV']
    dp = qs['PDR'].mean() - qm['PDR'].mean()
    dd = qs['Delay_ms'].mean() - qm['Delay_ms'].mean()
    dn = qs['NRL'].mean() - qm['NRL'].mean()
    # best p-value across conditions
    best_p = 1.0
    for v in df[xcol].unique():
        _, p, _, _ = mw_test(df, xcol, v, 'PDR')
        if not np.isnan(p) and p < best_p:
            best_p = p
    print(f'{fname:<8} {dp:>+8.2f}% {dd:>+9.1f}ms {dn:>+9.3f} '
          f'{best_p:>9.4f} {sig_label(best_p)}')

print('='*70)
print(f'\nPlots saved → {PLOT_DIR}')
print('Files: fig_N, fig_L, fig_E2, fig_C, fig_S, fig_W,')
print('       fig_overview_PDR, fig_overview_NRL')
print('CSVs : summary_stats.csv, stat_tests.csv')
