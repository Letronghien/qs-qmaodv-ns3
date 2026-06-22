#!/usr/bin/env bash
# qs2_launch_W2_W3.sh — Chạy Family W2 + W3 song song trên 2 tmux sessions
#
# Tổng: 4 jobs (runW2) + 3 jobs (runW3) = 7 NS-3 jobs đồng thời
#
# Cách dùng:
#   1. Upload 3 scripts lên VM:
#        cp qs2_run_W2.sh       ~/qs2_run_W2.sh
#        cp qs2_run_W3.sh       ~/qs2_run_W3.sh
#        cp qs2_launch_W2_W3.sh ~/qs2_launch_W2_W3.sh
#
#   2. *** QUAN TRỌNG — Verify tên tham số trước khi chạy ***
#      Kiểm tra compare-sim.cc có nhận các tham số sau không:
#        --ackSilenceThreshold   (used in W2 + W3)
#        --decayFactor           (used in W3)
#      Nếu tên khác, sửa biến ACK_PARAM trong qs2_run_W2.sh
#      và DECAY_PARAM trong qs2_run_W3.sh trước khi upload.
#
#   3. Khởi động:
#        bash ~/qs2_launch_W2_W3.sh
#
# Monitor:
#   bash ~/qs2_check_W2_W3.sh      ← xem tiến độ nhanh
#   tmux attach -t runW2           ← live view W2
#   tmux attach -t runW3           ← live view W3
#   (Ctrl+B D để detach)
#
# Tổng số runs: W2=180 + W3=180 = 360 runs
# Ước tính thời gian: ~30–45 phút (7 jobs song song, ~45s/run)

set -e

LOGDIR=~/QS-QMAODV-results/v5
mkdir -p "$LOGDIR"

echo "=== QS-QMAODV Sensitivity Launcher — $(date '+%H:%M') ==="
echo "    W2: threshold ∈ {5,10,15,20,30}s | 4 parallel jobs | 180 runs"
echo "    W3: decay    ∈ {0.85,0.90,0.92,0.95,0.99} | 3 parallel jobs | 180 runs"
echo "    Tổng: 7 NS-3 jobs đồng thời | ~360 runs | ước tính ~35–50 phút"
echo ""

# ── Kiểm tra scripts ──────────────────────────────────────────────────────────
missing=0
for f in ~/qs2_run_W2.sh ~/qs2_run_W3.sh; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Thiếu $f — upload trước!"
        missing=1
    fi
done
(( missing )) && exit 1

# ── Kill sessions cũ ─────────────────────────────────────────────────────────
for sess in runW2 runW3; do
    if tmux has-session -t "$sess" 2>/dev/null; then
        echo "  [WARN] Session '$sess' tồn tại — kill và restart"
        tmux kill-session -t "$sess"
        sleep 0.5
    fi
done

# ── Start runW2 (MAX_JOBS=4) ─────────────────────────────────────────────────
tmux new-session -d -s runW2 \
    "bash ~/qs2_run_W2.sh 2>&1 | tee ${LOGDIR}/log_W2.txt; \
     echo ''; echo '>>> runW2 FINISHED <<<'; sleep 9999"
echo "  ✓ runW2 started (4 jobs — threshold sweep)"

# ── Start runW3 (MAX_JOBS=3) ─────────────────────────────────────────────────
tmux new-session -d -s runW3 \
    "bash ~/qs2_run_W3.sh 2>&1 | tee ${LOGDIR}/log_W3.txt; \
     echo ''; echo '>>> runW3 FINISHED <<<'; sleep 9999"
echo "  ✓ runW3 started (3 jobs — decay sweep)"

echo ""
tmux ls
echo ""

# ── Tạo script check tiến độ ─────────────────────────────────────────────────
cat > ~/qs2_check_W2_W3.sh << 'CHECKEOF'
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
CHECKEOF
chmod +x ~/qs2_check_W2_W3.sh

echo "Lệnh theo dõi:"
echo "  bash ~/qs2_check_W2_W3.sh   # progress nhanh"
echo "  tmux attach -t runW2         # live W2 (Ctrl+B D thoát)"
echo "  tmux attach -t runW3         # live W3 (Ctrl+B D thoát)"
echo ""
echo "Khi xong: chạy qs2_analyze_all.py để vẽ đồ thị W2/W3"
