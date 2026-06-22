#!/usr/bin/env bash
# qs2_run_C.sh — Family C: Combined Stress Test
#
# 5 stress levels (pktInterval unique per level → dùng để resume):
#   L1: pi=1.00s, speed= 5 m/s  (light)
#   L2: pi=0.50s, speed=15 m/s
#   L3: pi=0.25s, speed=25 m/s  (medium)
#   L4: pi=0.10s, speed=35 m/s
#   L5: pi=0.05s, speed=45 m/s  (extreme)
#
# SAFE DESIGN: flock append thẳng vào CSV, temp sống ~7s, resume tự động
#
# Upload: cp qs2_run_C.sh ~/qs2_run_C.sh
# Chạy:   bash ~/qs2_run_C.sh

NS3=~/ns-allinone-3.40-qs2maodv/ns-3.40
OUT=~/QS-QMAODV-results/v5/family_C.csv
LOCK="${OUT}.lock"
SIM=200
MAX_JOBS=3

mkdir -p "$(dirname "$OUT")"

# Stress levels — pktInterval UNIQUE cho mỗi level (dùng để nhận dạng khi resume)
declare -A SPEED=( ["1.00"]="5" ["0.50"]="15" ["0.25"]="25" ["0.10"]="35" ["0.05"]="45" )
LEVELS=("1.00" "0.50" "0.25" "0.10" "0.05")
LNAMES=("L1-light" "L2-mild" "L3-medium" "L4-heavy" "L5-extreme")

echo "=== Family C: Combined Stress Test — $(date '+%H:%M') ==="
echo "    L1(1.00s/5m/s) L2(0.50s/15) L3(0.25s/25) L4(0.10s/35) L5(0.05s/45)"
echo "    protocols: AODV PMAODV QMAODV QS2MAODV"
echo "    seeds    : 1–30 | simTime=${SIM}s | nodes=20 | energy=50J"
echo "    parallel : ${MAX_JOBS} jobs | flock append → $OUT"
if [[ -f "$OUT" ]]; then
    existing=$(( $(wc -l < "$OUT") - 1 ))
    echo "    RESUME   : tìm thấy CSV có ${existing} rows"
fi
echo ""

# ── Resume check: (Protocol, Seed, PktInterval_s) — col 1,2,7 (awk 1-based) ─
# Mỗi stress level có pktInterval KHÁC NHAU → đủ để identify unique run
is_done() {
    local proto=$1 seed=$2 pi=$3
    [[ -f "$OUT" ]] || return 1
    awk -F',' -v p="$proto" -v s="$seed" -v pi="$pi" \
        'NR>1 && $1==p && $2==s && $7==pi { found=1; exit }
         END { exit !found }' "$OUT" 2>/dev/null
}

# ── Hàm chạy 1 run ───────────────────────────────────────────────────────────
run_one() {
    local proto=$1 seed=$2 pi=$3 vel=$4
    local tmpout="/tmp/qs2_C_${proto}_pi${pi}_s${seed}.csv"

    "$NS3/ns3" run scratch/compare-sim -- \
        --protocol="$proto" --seed="$seed" --csvFile="$tmpout" \
        --numNodes=20 --simTime=$SIM \
        --pktInterval="$pi" --initialEnergy=50 \
        --meanVelMin="$vel" --meanVelMax="$vel" 2>/dev/null

    if [[ -s "$tmpout" ]]; then
        (
            flock -x 9
            if [[ ! -s "$OUT" ]]; then
                cat "$tmpout" >> "$OUT"
            else
                tail -n +2 "$tmpout" >> "$OUT"
            fi
        ) 9>"$LOCK"
    fi
    rm -f "$tmpout"
}
export -f run_one
export NS3 OUT LOCK SIM

# ── Đếm tổng ─────────────────────────────────────────────────────────────────
total=0; skip=0
for pi in "${LEVELS[@]}"; do
    for p in AODV PMAODV QMAODV QS2MAODV; do
        for s in $(seq 1 30); do
            if is_done "$p" "$s" "$pi"; then (( skip++ ))
            else (( total++ ))
            fi
        done
    done
done
echo "    Cần chạy: ${total} runs | Bỏ qua (đã xong): ${skip} runs"
echo ""

# ── Chạy ─────────────────────────────────────────────────────────────────────
done_count=0
for idx in "${!LEVELS[@]}"; do
    pi="${LEVELS[$idx]}"
    vel="${SPEED[$pi]}"
    lname="${LNAMES[$idx]}"

    for p in AODV PMAODV QMAODV QS2MAODV; do
        for s in $(seq 1 30); do

            if is_done "$p" "$s" "$pi"; then
                continue
            fi

            while (( $(jobs -rp | wc -l) >= MAX_JOBS )); do
                sleep 0.3
            done

            run_one "$p" "$s" "$pi" "$vel" &
            (( done_count++ ))

            if (( done_count % 30 == 0 )); then
                rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
                echo "  [$(date '+%H:%M')] ${done_count}/${total} launched | CSV: ${rows} rows | ${lname} proto=${p}"
            fi
        done
    done
    echo "  [$(date '+%H:%M')] ${lname} (pi=${pi}s, v=${vel}m/s) — seeds launched"
done

wait
echo ""

final_rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 ))
expected=600
echo "=== Family C COMPLETE — $(date '+%H:%M') ==="
echo "    Output : $OUT"
echo "    Rows   : ${final_rows} / ${expected} expected"
(( final_rows < expected )) && \
    echo "    WARNING: thiếu $(( expected - final_rows )) rows!"
rm -f "$LOCK"
