#!/usr/bin/env bash
LOGDIR=~/QS-QMAODV-results/v5
echo "=== W2/W3 Progress Check — $(date '+%H:%M:%S') ==="

for fam in W2 W3; do
    csv="${LOGDIR}/family_${fam}.csv"
    log="${LOGDIR}/log_${fam}.txt"
    expected=180

    if [[ -f "$csv" && -s "$csv" ]]; then
        rows=$(( $(wc -l < "$csv") - 1 ))
        pct=$(( rows * 100 / expected ))
        filled=$(( pct / 5 ))
        bar=$(printf '█%.0s' $(seq 1 $filled 2>/dev/null))
        echo "  Family ${fam}: ${rows}/${expected} rows (${pct}%) ${bar}"
    else
        echo "  Family ${fam}: chưa có data"
    fi

    if tmux has-session -t "run${fam}" 2>/dev/null; then
        echo "             session run${fam}: RUNNING"
    else
        echo "             session run${fam}: DONE / not started"
    fi

    if [[ -f "$log" ]]; then
        last=$(grep -v '^$' "$log" | tail -1)
        [[ -n "$last" ]] && echo "             last: $last"
    fi
    echo ""
done

# Check pending run files (sẽ rỗng khi chạy bình thường)
pending_W2=$(ls ~/QS-QMAODV-results/v5/runs_W2/ 2>/dev/null | wc -l)
pending_W3=$(ls ~/QS-QMAODV-results/v5/runs_W3/ 2>/dev/null | wc -l)
[[ $pending_W2 -gt 0 ]] && echo "  [INFO] runs_W2/: ${pending_W2} pending files (normal during run)"
[[ $pending_W3 -gt 0 ]] && echo "  [INFO] runs_W3/: ${pending_W3} pending files (normal during run)"
