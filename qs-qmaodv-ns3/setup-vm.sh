#!/bin/bash
# =============================================================
# setup-vm.sh — Tạo môi trường NS-3 RIÊNG cho QS-QMAODV
#
# HOÀN TOÀN ĐỘC LẬP — không đụng đến ns-allinone-3.40 gốc
#
# Cách dùng:
#   cd ~/qs-qmaodv-ns3
#   bash setup-vm.sh
#
# Kết quả:
#   ~/ns-allinone-3.40-qs2maodv/  ← bản NS-3 riêng
# =============================================================

set -e

# ============================================================
# Config — chỉnh nếu cần
# ============================================================
NS3_ORIG="${HOME}/ns-allinone-3.40"
NS3_NEW="${HOME}/ns-allinone-3.40-qs2maodv"
NS3_ORIG_INNER="${NS3_ORIG}/ns-3.40"
NS3_NEW_INNER="${NS3_NEW}/ns-3.40"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# ============================================================
CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${CYAN}[QS-QMAODV]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "========================================================="
echo "  QS-QMAODV — NS-3 Environment Setup"
echo "  Repo   : ${REPO_DIR}"
echo "  Origin : ${NS3_ORIG}"
echo "  New    : ${NS3_NEW}"
echo "========================================================="
echo ""

# ============================================================
# BƯỚC 0: Kiểm tra
# ============================================================
log "Bước 0: Kiểm tra điều kiện..."

[ -d "${NS3_ORIG_INNER}" ] || err "NS-3 gốc không tồn tại: ${NS3_ORIG_INNER}"
[ -d "${NS3_ORIG_INNER}/src/qmaodv" ] || err "qmaodv không tìm thấy trong ${NS3_ORIG_INNER}/src/"

AVAIL_KB=$(df -k "${HOME}" | tail -1 | awk '{print $4}')
NEED_KB=200000  # ~200MB
if [ "${AVAIL_KB}" -lt "${NEED_KB}" ]; then
    err "Không đủ dung lượng (cần ~200MB, còn ${AVAIL_KB}KB)"
fi

ok "Điều kiện đáp ứng (còn ${AVAIL_KB}KB trống)"

# ============================================================
# BƯỚC 1: Copy NS-3 gốc → NS-3 riêng
# ============================================================
if [ -d "${NS3_NEW}" ]; then
    log "Bước 1: ${NS3_NEW} đã tồn tại — xóa và copy lại sạch..."
    rm -rf "${NS3_NEW}"
fi
log "Bước 1: Copy NS-3 gốc → bản riêng (~vài phút)..."
cp -r "${NS3_ORIG}" "${NS3_NEW}"
ok "Copy xong: ${NS3_NEW}"

# Xóa cmake cache ngay sau khi copy — TRƯỚC KHI làm bất cứ điều gì khác
# (bản gốc đã có cache của qsaqmaodv, qmaodv... gây conflict)
log "Xóa cmake cache từ bản gốc..."
rm -rf "${NS3_NEW_INNER}/cmake-cache/"
rm -rf "${NS3_NEW_INNER}/build/"
rm -f  "${NS3_NEW_INNER}/.lock-ns3_linux_build"
ok "Cache sạch"

# ============================================================
# BƯỚC 2: Tạo module qs2maodv — copy support files từ qmaodv
# ============================================================
log "Bước 2: Tạo module qs2maodv..."

QMAODV_SRC="${NS3_ORIG_INNER}/src/qmaodv"
QS_DST="${NS3_NEW_INNER}/src/qs2maodv"

mkdir -p "${QS_DST}/model"
mkdir -p "${QS_DST}/helper"
mkdir -p "${QS_DST}/test"

SUPPORT_FILES=(
    "model/qmaodv-dpd.h"
    "model/qmaodv-dpd.cc"
    "model/qmaodv-id-cache.h"
    "model/qmaodv-id-cache.cc"
    "model/qmaodv-neighbor.h"
    "model/qmaodv-neighbor.cc"
    "model/qmaodv-packet.h"
    "model/qmaodv-packet.cc"
    "model/qmaodv-rqueue.h"
    "model/qmaodv-rqueue.cc"
    "model/qmaodv-rtable.h"
    "model/qmaodv-rtable.cc"
    "helper/qmaodv-helper.h"
    "helper/qmaodv-helper.cc"
)

for f in "${SUPPORT_FILES[@]}"; do
    src_file="${QMAODV_SRC}/${f}"
    dst_rel="${f//qmaodv-/qs2maodv-}"
    dst_file="${QS_DST}/${dst_rel}"

    if [ ! -f "${src_file}" ]; then
        echo "  SKIP (not found): ${src_file}"
        continue
    fi

    echo "  Generating: ${dst_rel}"
    sed \
        -e 's/QMAODV_PORT/QS2MAODV_PORT/g' \
        -e 's/QMAODVTYPE_/QS2MAODVTYPE_/g' \
        -e 's/namespace qmaodv/namespace qs2maodv/g' \
        -e 's/ns3::qmaodv::/ns3::qs2maodv::/g' \
        -e 's/"ns3::qmaodv::/"ns3::qs2maodv::/g' \
        -e 's/RecvQmaodv/RecvQs2maodv/g' \
        -e 's/QmaodvRoutingProtocol/Qs2maodvRoutingProtocol/g' \
        -e 's/class QmaodvHelper/class Qs2maodvHelper/g' \
        -e 's/QmaodvHelper/Qs2maodvHelper/g' \
        -e 's/QMAODV_H\b/QS2MAODV_H/g' \
        -e 's/_QMAODV_/_QS2MAODV_/g' \
        -e 's/Qmaodv\b/Qs2maodv/g' \
        -e 's/qmaodv-/qs2maodv-/g' \
        -e 's/SetGroupName("Qmaodv")/SetGroupName("QsQmaodv")/g' \
        -e 's/SetGroupName("qmaodv")/SetGroupName("qs2maodv")/g' \
        -e 's/NS_LOG_COMPONENT_DEFINE("Qmaodv/NS_LOG_COMPONENT_DEFINE("Qs2maodv/g' \
        "${src_file}" > "${dst_file}"
done

ok "Support files generated"

# ============================================================
# BƯỚC 3: Copy hand-written QS files từ repo
# ============================================================
log "Bước 3: Copy hand-written QS files từ repo..."

for f in \
    "src/qs2maodv/model/qs2maodv-qtable.h" \
    "src/qs2maodv/model/qs2maodv-qtable.cc" \
    "src/qs2maodv/model/qs2maodv-routing-protocol.h" \
    "src/qs2maodv/model/qs2maodv-routing-protocol.cc" \
    "src/qs2maodv/helper/qs2maodv-helper.h" \
    "src/qs2maodv/helper/qs2maodv-helper.cc" \
    "src/qs2maodv/CMakeLists.txt"
do
    src="${REPO_DIR}/${f}"
    # strip leading src/qs2maodv/
    rel="${f#src/qs2maodv/}"
    dst="${QS_DST}/${rel}"
    if [ -f "${src}" ]; then
        echo "  COPY ${rel}"
        cp "${src}" "${dst}"
    else
        echo "  MISSING: ${src}"
    fi
done

ok "Hand-written files copied"

# ============================================================
# BƯỚC 4: Copy scratch simulation script
# ============================================================
log "Bước 4: Copy scratch simulation script..."
cp "${REPO_DIR}/scratch/qs2maodv-sim.cc" \
   "${NS3_NEW_INNER}/scratch/qs2maodv-sim.cc"
ok "scratch/qs2maodv-sim.cc copied"

# ============================================================
# BƯỚC 5: Configure & Build
# ============================================================
log "Bước 5: Configure NS-3..."
cd "${NS3_NEW_INNER}"
./ns3 configure --enable-examples --enable-tests 2>&1 | \
    grep -E "(qs2maodv|Enabled modules|error)" | head -30

echo ""
log "Bước 6: Build module qs2maodv..."
./ns3 build qs2maodv 2>&1

echo ""
log "Bước 7: Build simulation script..."
./ns3 build scratch/qs2maodv-sim 2>&1

echo ""
echo "========================================================="
echo -e "  ${GREEN}HOÀN TẤT!${NC}"
echo ""
echo "  NS-3 riêng cho QS-QMAODV:"
echo "    ${NS3_NEW_INNER}"
echo ""
echo "  Chạy simulation:"
echo "    cd ${NS3_NEW_INNER}"
echo "    ./ns3 run scratch/qs2maodv-sim"
echo ""
echo "  Tùy chọn:"
echo "    ./ns3 run \"scratch/qs2maodv-sim --nNodes=50 --nFlows=10 --seed=1\""
echo "========================================================="
