#!/usr/bin/env bash
# qs2_run_E2.sh — Family E2: Battery depletion REDESIGN
# initialEnergy {1,2,5,10,20} J — node cạn pin trong 200s
#
# SAFE DESIGN: mỗi run ghi thẳng vào CSV chính qua flock
#   - Temp file chỉ sống ~7s (duration 1 NS-3 run)
#   - VM crash: mất tối đa 3 runs đang chạy, còn lại an toàn
#   - Resume: tự động bỏ qua runs đã có trong CSV
#
# Upload: cp qs2_run_E2.sh ~/qs2_run_E2.sh
# Chạy:   bash ~/qs2_run_E2.sh

NS3=~/ns-allinone-3.40-qs2maodv/ns-3.40
OUT=~/QS-QMAODV-results/v5/family_E2.csv
LOCK="${OUT}.lock"
SIM=200
MAX_JOBS=3   # song song 3 jobs

mkdir -p "$(dirname "$OUT")"

echo "=== Family E2: Battery depletion redesign — $(date '+%H:%M') ==="
echo "    energies : 1 2 5 10 20 J"
echo "    protocols: AODV PMAODV QMAODV QS2MAODV"
echo "    seeds    : 1–30 | simTime=${SIM}s | nodes=20 | pi=0.25s | speed=5m/s"
echo "    parallel : ${MAX_JOBS} jobs | flock append → $OUT"
if [[ -f "$OUT" ]]; then
    existing=$(( $(wc -l < "$OUT") - 1 ))
    echo "    RESUME   : tìm thấy CSV có ${existing} rows — bỏ qua runs đã xong"
fi
echo ""

# ── Kiểm tra run đã xong chưa (Protocol,Seed,InitEnergy_J) ──────────────────
# CSV columns: Protocol(1) Seed(2) ... InitEnergy_J(6) PktInterval_s(7) [awk 1-based]
is_done() {
    local proto=$1 seed=$2 energy=$3
    [[ -f "$OUT" ]] || return 1
    awk -F',' -v p="$proto" -v s="$seed" -v e="$energy" \
        'NR>1 && $1==p && $2==s && $6==e { found=1; exit }
         END { exit !found }' "$OUT" 2>/dev/null
}

# ── Hàm chạy 1 NS-3 run và append thẳng vào CSV ────────────────────────────
run_one() {
    local proto=$1 seed=$2 energy=$3
    local tmpout="/tmp/qs2_E2_${proto}_e${energy}_s${seed}.csv"

    "$NS3/ns3" run scratch/compare-sim -- \
        --protocol="$proto" --seed="$seed" --csvFile="$tmpout" \
        --numNodes=20 --simTime=$SIM \
        --pktInterval=0.25 --initialEnergy="$energy" \
        --meanVelMin=5 --meanVelMax=5 2>/dev/null

    # Append với exclusive lock
    if [[ -s "$tmpout" ]]; then
        (
            flock -x 9
            if [[ ! -s "$OUT" ]]; then
                cat "$tmpout" >> "$OUT"         # lần đầu: giữ header
            else
                tail -n +2 "$tmpout" >> "$OUT"  # tiếp theo: bỏ header
            fi
        ) 9>"$LOCK"
    fi
    rm -f "$tmpout"
}
export -f run_one
export NS3 OUT LOCK SIM

# ── Đếm tổng runs cần chạy ───────────────────────────────────────────────────
total=0; skip=0
for e in 1 2 5 10 20; do
    for p in AODV PMAODV QMAODV QS2MAODV; do
        for s in $(seq 1 30); do
            if is_done "$p" "$s" "$e"; then
                (( skip++ ))
            else
                (( total++ ))
            fi
        done
    done
done
echo "    Cần chạy: ${total} runs | Bỏ qua (đã xong): ${skip} runs"
echo ""

# ── Chạy parallel 3 jobs ─────────────────────────────────────────────────────
done_count=0
for e in 1 2 5 10 20; do
    for p in AODV PMAODV QMAODV QS2MAODV; do
        for s in $(seq 1 30); do

            # Bỏ qua nếu đã xong
            if is_done "$p" "$s" "$e"; then
                continue
            fi

            # Throttle: chờ khi đủ MAX_JOBS đang chạy
            while (( $(jobs -rp | wc -l) >= MAX_JOBS )); do
                sleep 0.3
            done

            run_one "$p" "$s" "$e" &
            (( done_count++ ))

            if (( done_count % 30 == 0 )); then
                rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
                echo "  [$(date '+%H:%M')] ${done_count}/${total} launched | CSV: ${rows} rows | energy=${e}J proto=${p}"
            fi
        done
    done
    echo "  [$(date '+%H:%M')] energy=${e}J — tất cả seeds đã launch"
done

wait
echo ""

# ── Tổng kết ─────────────────────────────────────────────────────────────────
final_rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
expected=600
echo "=== Family E2 COMPLETE — $(date '+%H:%M') ==="
echo "    Output : $OUT"
echo "    Rows   : ${final_rows} / ${expected} expected"
(( final_rows < expected )) && \
    echo "    WARNING: thiếu $(( expected - final_rows )) rows!"
rm -f "$LOCK"
