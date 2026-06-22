#!/usr/bin/env bash
# qs2_run_W2.sh — Family W2: ACK-Silence Threshold Sensitivity
#
# Mục đích: sweep silence_threshold ∈ {5,10,15,20,30}s cho QS2MAODV
#           QMAODV chạy 1 lần (threshold ko ảnh hưởng) để làm baseline
#
# Fixed params:
#   numNodes=20, pktInterval=0.10s, initialEnergy=50J, speed=5m/s
#   decayFactor=0.92 (default), w3=0.10 (default)
#
# CSV output: family_W2.csv — cột 19 = SweepParam (threshold value)
#
# ── Verify tên tham số với compare-sim.cc của bạn ─────────────────────────
# Nếu tên khác (vd: --silenceThreshold, --ackThreshold), sửa dòng dưới:
ACK_PARAM="ackSilenceThreshold"
# ──────────────────────────────────────────────────────────────────────────
#
# Upload: cp qs2_run_W2.sh ~/qs2_run_W2.sh
# Chạy:   bash ~/qs2_run_W2.sh

NS3=~/ns-allinone-3.40-qs2maodv/ns-3.40
OUT=~/QS-QMAODV-results/v5/family_W2.csv
LOCK="${OUT}.lock"
RUNDIR=~/QS-QMAODV-results/v5/runs_W2   # persistent — tồn tại qua VM reboot
SIM=200
MAX_JOBS=4

mkdir -p "$(dirname "$OUT")" "$RUNDIR"

# Threshold values (giây)
THRESHOLDS=(5 10 15 20 30)

echo "=== Family W2: ACK-Silence Threshold Sensitivity — $(date '+%H:%M') ==="
echo "    QS2MAODV: threshold ∈ {5,10,15,20,30}s | decayFactor=0.92 (fixed)"
echo "    QMAODV  : baseline reference (threshold không ảnh hưởng)"
echo "    seeds   : 1–30 | numNodes=20 | pktInterval=0.10s | speed=5m/s"
echo "    parallel: ${MAX_JOBS} jobs | flock append → $OUT"
echo "    NOTE: SweepParam (threshold) được thêm vào cột 19 của CSV"
if [[ -f "$OUT" ]]; then
    existing=$(( $(wc -l < "$OUT") - 1 ))
    echo "    RESUME  : tìm thấy CSV có ${existing} rows"
fi
echo ""

# ── Resume check: (Protocol, Seed, SweepParam=col19) ─────────────────────────
is_done() {
    local proto=$1 seed=$2 sweep_val=$3
    [[ -f "$OUT" ]] || return 1
    awk -F',' -v p="$proto" -v s="$seed" -v sv="$sweep_val" \
        'NR>1 && $1==p && $2==s && $19==sv { found=1; exit }
         END { exit !found }' "$OUT" 2>/dev/null
}

# ── Chạy 1 run, inject SweepParam vào cột 19 khi append ──────────────────────
run_one() {
    local proto=$1 seed=$2 threshold=$3
    local runfile="$RUNDIR/W2_${proto}_t${threshold}_s${seed}.csv"

    # Nếu file run đã tồn tại (VM crash trước đó) → append trực tiếp, không chạy lại
    if [[ ! -s "$runfile" ]]; then
        "$NS3/ns3" run scratch/compare-sim -- \
            --protocol="$proto" --seed="$seed" --csvFile="$runfile" \
            --numNodes=20 --simTime=$SIM \
            --pktInterval=0.10 --initialEnergy=50 \
            --meanVelMin=5 --meanVelMax=5 \
            --${ACK_PARAM}="$threshold" \
            --decayFactor=0.92 2>/dev/null
    fi

    if [[ -s "$runfile" ]]; then
        (
            flock -x 9
            if [[ ! -s "$OUT" ]]; then
                # Lần đầu: thêm header với cột SweepParam
                head -1 "$runfile" | awk -F',' '{print $0",SweepParam"}' >> "$OUT"
            fi
            # Data rows: thêm threshold value vào cuối
            tail -n +2 "$runfile" | awk -F',' -v sv="$threshold" '{print $0","sv}' >> "$OUT"
        ) 9>"$LOCK"
        rm -f "$runfile"   # xóa sau khi đã append thành công
    fi
}
export -f run_one
export NS3 OUT LOCK RUNDIR SIM ACK_PARAM

# ── Đếm tổng ─────────────────────────────────────────────────────────────────
total=0; skip=0
# QS2MAODV × mỗi threshold
for t in "${THRESHOLDS[@]}"; do
    for s in $(seq 1 30); do
        if is_done "QS2MAODV" "$s" "$t"; then (( skip++ ))
        else (( total++ ))
        fi
    done
done
# QMAODV × threshold=15 (reference, dùng giá trị default để phân biệt)
for s in $(seq 1 30); do
    if is_done "QMAODV" "$s" "15"; then (( skip++ ))
    else (( total++ ))
    fi
done
echo "    Cần chạy: ${total} runs | Bỏ qua (đã xong): ${skip} runs"
echo ""

# ── Chạy QS2MAODV — sweep threshold ──────────────────────────────────────────
done_count=0
for t in "${THRESHOLDS[@]}"; do
    for s in $(seq 1 30); do
        is_done "QS2MAODV" "$s" "$t" && continue

        while (( $(jobs -rp | wc -l) >= MAX_JOBS )); do sleep 0.3; done

        run_one "QS2MAODV" "$s" "$t" &
        (( done_count++ ))
        if (( done_count % 30 == 0 )); then
            rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
            echo "  [$(date '+%H:%M')] ${done_count}/${total} launched | CSV: ${rows} rows | threshold=${t}s"
        fi
    done
    echo "  [$(date '+%H:%M')] threshold=${t}s — seeds launched"
done

# ── Chạy QMAODV baseline (threshold=15 làm SweepParam placeholder) ────────────
echo ""
echo "  [$(date '+%H:%M')] QMAODV baseline — 30 seeds..."
for s in $(seq 1 30); do
    is_done "QMAODV" "$s" "15" && continue

    while (( $(jobs -rp | wc -l) >= MAX_JOBS )); do sleep 0.3; done

    run_one "QMAODV" "$s" "15" &
    (( done_count++ ))
done

wait
echo ""

final_rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
expected=180   # 5 thresholds × 30 seeds + 1 QMAODV × 30 seeds
echo "=== Family W2 COMPLETE — $(date '+%H:%M') ==="
echo "    Output : $OUT"
echo "    Rows   : ${final_rows} / ${expected} expected"
(( final_rows < expected )) && \
    echo "    WARNING: thiếu $(( expected - final_rows )) rows!"
rm -f "$LOCK"
