# QS-QMAODV: Queue-State-Aware Q-Learning Multipath AODV

Implementation and evaluation of QS-QMAODV routing protocol for MANETs,
built on NS-3.40.

## Repository Structure

```
src/qs2maodv/          NS-3 routing module (C++)
scratch/compare-sim.cc Simulation runner (4 protocols × 5 families)
scripts/               Run scripts, analysis, patch utilities
results/               Simulation CSV data + plots
paper/                 Paper build scripts (Python → .docx)
```

## Quick Start

```bash
# 1. Patch NS-3 source for decay parameter sweep
python3 scripts/qs2_patch_decay_params.py

# 2. Build
cd ~/ns-allinone-3.40-qs2maodv/ns-3.40 && ./ns3 build

# 3. Run all experiment families
bash scripts/qs2_launch_E2_C.sh       # Family E2 + C
# (Family N, L, S use similar runners)

# 4. Run sensitivity sweeps
bash scripts/qs2_launch_W2_W3.sh      # W2 (threshold) + W3 (decay factor)

# 5. Analyse, plot (A4 2-column format), and export Excel
python3 scripts/qs2_analyze_all.py
python3 scripts/qs2_plot_paper_final.py      # publication-quality figures
python3 scripts/qs2_export_results_excel.py  # Excel workbook

# 6. Build paper (latest = v10)
python3 paper/build_paper_v10.py
```

## Experiment Families

| Family | Varied | Values | Runs |
|--------|--------|--------|------|
| N — Node density | nNodes | 5–50 | 30 seeds × 4 protocols |
| L — Traffic load | pktInterval | 0.05–1.0 s | 30 seeds × 4 protocols |
| E2 — Energy sensitivity | InitEnergy | 1–20 J | 30 seeds × 4 protocols |
| C — Combined stress | (load, speed) | L1–L5 | 30 seeds × 4 protocols |
| S — Node speed | speed | 5–45 m/s | 30 seeds × 4 protocols |
| W — w3 sensitivity | w3 | 0.00–0.50 | 30 seeds × QS2MAODV |
| W2 — Threshold sweep | ackSilenceThreshold | 5–30 s | 30 seeds × QS2MAODV |
| W3 — Decay sweep | decayFactor | 0.85–0.99 | 30 seeds × QS2MAODV |

## Protocols

- **AODV** — baseline (NS-3 built-in)
- **PMAODV** — multipath reactive (group's prior work)
- **QMAODV** — Q-learning multipath (group's prior work)
- **QS2MAODV** — Queue-State-Aware Q-Learning Multipath AODV (proposed)

## Citation

```
Le, T.H. et al. QS-QMAODV: Queue-State-Aware Q-Learning Multipath AODV
for Adaptive Routing in Mobile Ad Hoc Networks. (Under review, Q3 journal)
```
