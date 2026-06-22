#!/usr/bin/env bash
# qs2_launch_E2_C.sh — Chạy Family E2 + C song song trên 2 tmux sessions
#
# Cách dùng:
#   1. Upload 3 scripts lên VM:
#        cp qs2_run_E2.sh      ~/qs2_run_E2.sh
#        cp qs2_run_C.sh       ~/qs2_run_C.sh
#        cp qs2_launch_E2_C.sh ~/qs2_launch_E2_C.sh
#   2. Khởi động:
#        bash ~/qs2_launch_E2_C.sh
#
# Monitor:
#   bash ~/qs2_check_E2_C.sh   ← xem tiến độ nhanh
#   tmux attach -t runE2        ← live view (Ctrl+B D để thoát)
#   tmux attach -t runC

set -e

LOGDIR=~/QS-QMAODV-results/v5
mkdir -p "$LOGDIR"

echo "=== QS-QMAODV Parallel Launcher — $(date '+%H:%M') ==="
echo "    E2: energy {1,2,5,10,20}J | 3 parallel jobs"
echo "    C : combined stress L1–L5  | 3 parallel jobs"
echo "    Tổng: 6 NS-3 jobs đồng thời"
echo ""

# ── Kiểm tra scripts ─────────────────────────────────────────────────────────
missing=0
for f in ~/qs2_run_E2.sh ~/qs2_run_C.sh; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Thiếu $f — upload trước!"
        missing=1
    fi
done
(( missing )) && exit 1

# ── Kill sessions cũ ─────────────────────────────────────────────────────────
for sess in runE2 runC; do
    if tmux has-session -t "$sess" 2>/dev/null; then
        echo "  [WARN] Session '$sess' tồn tại — kill và restart"
        tmux kill-session -t "$sess"
        sleep 0.5
    fi
done

# ── Start runE2 ──────────────────────────────────────────────────────────────
tmux new-session -d -s runE2 \
    "bash ~/qs2_run_E2.sh 2>&1 | tee ${LOGDIR}/log_E2.txt; \
     echo ''; echo '>>> runE2 FINISHED <<<'"
echo "  ✓ runE2 started"

# ── Start runC ───────────────────────────────────────────────────────────────
tmux new-session -d -s runC \
    "bash ~/qs2_run_C.sh 2>&1 | tee ${LOGDIR}/log_C.txt; \
     echo ''; echo '>>> runC FINISHED <<<'"
echo "  ✓ runC started"

echo ""
tmux ls
echo ""

# ── Tạo script check tiến độ ─────────────────────────────────────────────────
cat > ~/qs2_check_E2_C.sh << 'EOF'
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
EOF
chmod +x ~/qs2_check_E2_C.sh

echo "Lệnh theo dõi:"
echo "  bash ~/qs2_check_E2_C.sh   # progress"
echo "  tmux attach -t runE2        # live E2"
echo "  tmux attach -t runC         # live C"
