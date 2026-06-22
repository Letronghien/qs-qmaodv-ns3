#!/usr/bin/env bash
# qs2_run_W3.sh — Family W3: ACK-Decay Factor Sensitivity
#
# Mục đích: sweep decay_factor ∈ {0.85,0.90,0.92,0.95,0.99} cho QS2MAODV
#           QMAODV chạy 1 lần (decay_factor ko ảnh hưởng) để làm baseline
#
# Fixed params:
#   numNodes=20, pktInterval=0.10s, initialEnergy=50J, speed=5m/s
#   ackSilenceThreshold=15s (default), w3=0.10 (default)
#
# CSV output: family_W3.csv — cột 19 = SweepParam (decay_factor value)
#
# ── Verify tên tham số với compare-sim.cc của bạn ─────────────────────────
# Nếu tên khác (vd: --qDecayFactor, --decayRate), sửa dòng dưới:
DECAY_PARAM="decayFactor"
# ──────────────────────────────────────────────────────────────────────────
#
# Upload: cp qs2_run_W3.sh ~/qs2_run_W3.sh
# Chạy:   bash ~/qs2_run_W3.sh

NS3=~/ns-allinone-3.40-qs2maodv/ns-3.40
OUT=~/QS-QMAODV-results/v5/family_W3.csv
LOCK="${OUT}.lock"
RUNDIR=~/QS-QMAODV-results/v5/runs_W3   # persistent — tồn tại qua VM reboot
SIM=200
MAX_JOBS=3

mkdir -p "$(dirname "$OUT")" "$RUNDIR"

# Decay factor values
DECAYS=(0.85 0.90 0.92 0.95 0.99)

echo "=== Family W3: ACK-Decay Factor Sensitivity — $(date '+%H:%M') ==="
echo "    QS2MAODV: decay_factor ∈ {0.85,0.90,0.92,0.95,0.99} | threshold=15s (fixed)"
echo "    QMAODV  : baseline reference (decay_factor không ảnh hưởng)"
echo "    seeds   : 1–30 | numNodes=20 | pktInterval=0.10s | speed=5m/s"
echo "    parallel: ${MAX_JOBS} jobs | flock append → $OUT"
echo "    NOTE: SweepParam (decay_factor) được thêm vào cột 19 của CSV"
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
    local proto=$1 seed=$2 decay=$3
    local runfile="$RUNDIR/W3_${proto}_d${decay}_s${seed}.csv"

    # Nếu file run đã tồn tại (VM crash trước đó) → append trực tiếp, không chạy lại
    if [[ ! -s "$runfile" ]]; then
        "$NS3/ns3" run scratch/compare-sim -- \
            --protocol="$proto" --seed="$seed" --csvFile="$runfile" \
            --numNodes=20 --simTime=$SIM \
            --pktInterval=0.10 --initialEnergy=50 \
            --meanVelMin=5 --meanVelMax=5 \
            --ackSilenceThreshold=15 \
            --${DECAY_PARAM}="$decay" 2>/dev/null
    fi

    if [[ -s "$runfile" ]]; then
        (
            flock -x 9
            if [[ ! -s "$OUT" ]]; then
                # Lần đầu: thêm header với cột SweepParam
                head -1 "$runfile" | awk -F',' '{print $0",SweepParam"}' >> "$OUT"
            fi
            # Data rows: thêm decay value vào cuối
            tail -n +2 "$runfile" | awk -F',' -v sv="$decay" '{print $0","sv}' >> "$OUT"
        ) 9>"$LOCK"
        rm -f "$runfile"   # xóa sau khi đã append thành công
    fi
}
export -f run_one
export NS3 OUT LOCK RUNDIR SIM DECAY_PARAM

# ── Đếm tổng ─────────────────────────────────────────────────────────────────
total=0; skip=0
# QS2MAODV × mỗi decay
for d in "${DECAYS[@]}"; do
    for s in $(seq 1 30); do
        if is_done "QS2MAODV" "$s" "$d"; then (( skip++ ))
        else (( total++ ))
        fi
    done
done
# QMAODV × decay=0.92 (reference placeholder)
for s in $(seq 1 30); do
    if is_done "QMAODV" "$s" "0.92"; then (( skip++ ))
    else (( total++ ))
    fi
done
echo "    Cần chạy: ${total} runs | Bỏ qua (đã xong): ${skip} runs"
echo ""

# ── Chạy QS2MAODV — sweep decay_factor ───────────────────────────────────────
done_count=0
for d in "${DECAYS[@]}"; do
    for s in $(seq 1 30); do
        is_done "QS2MAODV" "$s" "$d" && continue

        while (( $(jobs -rp | wc -l) >= MAX_JOBS )); do sleep 0.3; done

        run_one "QS2MAODV" "$s" "$d" &
        (( done_count++ ))
        if (( done_count % 30 == 0 )); then
            rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
            echo "  [$(date '+%H:%M')] ${done_count}/${total} launched | CSV: ${rows} rows | decay=${d}"
        fi
    done
    echo "  [$(date '+%H:%M')] decay=${d} — seeds launched"
done

# ── Chạy QMAODV baseline (decay=0.92 làm SweepParam placeholder) ─────────────
echo ""
echo "  [$(date '+%H:%M')] QMAODV baseline — 30 seeds..."
for s in $(seq 1 30); do
    is_done "QMAODV" "$s" "0.92" && continue

    while (( $(jobs -rp | wc -l) >= MAX_JOBS )); do sleep 0.3; done

    run_one "QMAODV" "$s" "0.92" &
    (( done_count++ ))
done

wait
echo ""

final_rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
expected=180   # 5 decay values × 30 seeds + 1 QMAODV × 30 seeds
echo "=== Family W3 COMPLETE — $(date '+%H:%M') ==="
echo "    Output : $OUT"
echo "    Rows   : ${final_rows} / ${expected} expected"
(( final_rows < expected )) && \
    echo "    WARNING: thiếu $(( expected - final_rows )) rows!"
rm -f "$LOCK"
