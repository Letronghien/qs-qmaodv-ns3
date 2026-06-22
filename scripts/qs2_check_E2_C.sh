#!/usr/bin/env bash
LOGDIR=~/QS-QMAODV-results/v5
echo "=== Progress Check — $(date '+%H:%M:%S') ==="
for fam in E2 C; do
    csv="${LOGDIR}/family_${fam}.csv"
    log="${LOGDIR}/log_${fam}.txt"
    if [[ -f "$csv" && -s "$csv" ]]; then
        rows=$(( $(wc -l < "$csv") - 1 ))
        pct=$(( rows * 100 / 600 ))
        bar=$(printf '█%.0s' $(seq 1 $(( pct / 5 )) 2>/dev/null))
        echo "  Family ${fam}: ${rows}/600 rows (${pct}%) ${bar}"
    else
        echo "  Family ${fam}: chưa có data"
    fi
    if tmux has-session -t "run${fam}" 2>/dev/null; then
        echo "             session run${fam}: RUNNING"
    else
        echo "             session run${fam}: DONE"
    fi
    if [[ -f "$log" ]]; then
        echo "             $(tail -2 "$log" | grep -v '^$' | tail -1)"
    fi
    echo ""
done
