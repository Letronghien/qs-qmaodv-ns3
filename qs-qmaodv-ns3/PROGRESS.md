# QS-QMAODV — Ghi chú tiến độ

## Tóm tắt dự án
Implement giao thức **QS-QMAODV** (Queue-State-Aware Q-Learning Multipath AODV) trên NS-3.40.
Module tên: `qs2maodv` (đổi từ `qsqmaodv` để tránh conflict với `qsaqmaodv` đang có).
NS-3 riêng: `~/ns-allinone-3.40-qs2maodv/` — hoàn toàn độc lập.

---

## Đã làm

### 1. Thiết kế & code
- `qs2maodv-qtable.h / .cc` — Q-table với **3D state** (dst, queue_bucket, energy_bucket)
- `qs2maodv-routing-protocol.h / .cc` — Routing protocol với 3 cơ chế QS:
  - [QS-1] State space 3D
  - [QS-2] Queue-triggered epsilon (θ_H=0.70, θ_L=0.30)
  - [QS-3] Hybrid selection: score = Q(s,a) × (1-q_a)^β
- `qs2maodv-helper.h / .cc` — NS-3 helper
- `CMakeLists.txt` — Build config
- `scratch/qs2maodv-sim.cc` — Simulation script (50 nodes, CBR, energy)
- `setup-vm.sh` — Script cài tự động
- Support files tự động generate từ qmaodv (dpd, id-cache, neighbor, packet, rqueue, rtable)

### 2. Môi trường
- NS-3 riêng: `~/ns-allinone-3.40-qs2maodv/ns-3.40/`
- Build thành công: `./ns3 build qs2maodv` ✅
- Simulation chạy được (không crash) ✅
- Repo GitHub: `https://github.com/Letronghien/qs-qmaodv-ns3`

### 3. Các lỗi đã fix
| # | Lỗi | Fix |
|---|-----|-----|
| 1 | CMakeCache conflict với qsaqmaodv | Đổi tên module → `qs2maodv` |
| 2 | CMakeCache path cũ sau copy NS-3 | Xóa cache sau copy trong setup-vm.sh |
| 3 | `GetQueueOccupancy() const` error | Bỏ `const` qualifier |
| 4 | `!m_qtable.CountFor() >= maxPaths` | Đổi thành `< m_maxPaths` |
| 5 | WiFi PHY crash (IsStateIdle) | Fix RandomWaypointMobilityModel PositionAllocator |
| 6 | Port 654 trùng AODV/QMAODV | Đổi port → 655 |
| 7 | Broadcast dest `10.1.1.255` không đến được | Đổi → `255.255.255.255` |
| 8 | Broadcast socket bind `10.1.1.255` | Đổi → `GetAny()` (0.0.0.0) |
| 9 | `limited broadcast - no route` | Thêm route cho `255.255.255.255` |

---

## Vấn đề hiện tại 🔴

**PDR = 0% — Packets không được nhận bởi node đích**

### Debug đã làm:
- ✅ Socket được tạo đúng trong `NotifyInterfaceUp`
- ✅ UDP packets được gửi đến `255.255.255.255:655`
- ✅ IP layer gửi thành công (`Send case 1b: passed in with route`)
- ❌ Node nhận **không có `Ipv4L3Protocol::Receive`** — packets không đến IP layer
- ❌ `RecvQs2maodv` không bao giờ được gọi

### Root cause nghi ngờ:
Packets bị drop ở **WiFi/MAC layer** — chưa xác nhận. Cần check:
```
NS_LOG="YansWifiPhy=level_warn:WifiMac=level_warn"
```

---

## Tiếp theo cần làm

### Bước 1 — Xác định WiFi drop
```bash
NS_LOG="YansWifiPhy=level_warn|prefix_time:WifiMac=level_warn|prefix_time" \
./ns3 run "scratch/qs2maodv-sim --warmUp=2 --simTime=6 --nNodes=2 --nFlows=1 --seed=1" \
2>&1 | head -30
```

### Bước 2 — Nếu WiFi OK, check AdhocWifiMac
Có thể cần `Ipv4RawSocket` thay vì `UdpSocket` cho broadcast trong ad-hoc.
Hoặc cần set `SetPromiscReceiveCallback`.

### Bước 3 — So sánh trực tiếp với QMAODV
Tạo test script dùng QMAODV để verify WiFi hoạt động, sau đó so sánh từng bước.

### Bước 4 — Khi routing hoạt động
- Test PDR > 0 với nNodes=4, nFlows=2
- Test full scenario: 50 nodes, 10 flows, 200s
- Thu thập metrics: PDR, throughput, delay, energy
- So sánh với AODV/QMAODV/QSAQMAODV

### Bước 5 — Cleanup
- Cập nhật `setup-vm.sh` với cmake flags đúng (hiện tại cần chạy cmake manually)
- Viết README đầy đủ với kết quả simulation

---

## Lệnh thường dùng trên VM

```bash
# Build
cd ~/ns-allinone-3.40-qs2maodv/ns-3.40
./ns3 build qs2maodv

# Chạy simulation ngắn (debug)
./ns3 run "scratch/qs2maodv-sim --warmUp=2 --simTime=10 --nNodes=4 --nFlows=2 --seed=1"

# Chạy full scenario
./ns3 run "scratch/qs2maodv-sim --nNodes=50 --nFlows=10 --simTime=150 --seed=1"

# Debug routing
NS_LOG="Qs2maodvRoutingProtocol=level_all|prefix_time" \
./ns3 run "scratch/qs2maodv-sim --warmUp=2 --simTime=10 --nNodes=4 --nFlows=1 --seed=1" \
2>&1 | grep -E "RecvRequest|RecvReply|RouteOutput" | head -30

# Update code từ repo
cd ~/qs-qmaodv-ns3 && git fetch origin && git reset --hard origin/master
cp qs-qmaodv-ns3/src/qs2maodv/model/qs2maodv-routing-protocol.cc \
   ~/ns-allinone-3.40-qs2maodv/ns-3.40/src/qs2maodv/model/
```

---

## Cấu trúc file quan trọng

```
~/ns-allinone-3.40-qs2maodv/ns-3.40/src/qs2maodv/
├── model/
│   ├── qs2maodv-routing-protocol.cc  ← HAND-WRITTEN (QS logic)
│   ├── qs2maodv-routing-protocol.h   ← HAND-WRITTEN
│   ├── qs2maodv-qtable.cc            ← HAND-WRITTEN (3D state)
│   ├── qs2maodv-qtable.h             ← HAND-WRITTEN
│   ├── qs2maodv-dpd.cc/h             ← generated từ qmaodv
│   ├── qs2maodv-id-cache.cc/h        ← generated
│   ├── qs2maodv-neighbor.cc/h        ← generated
│   ├── qs2maodv-packet.cc/h          ← generated
│   ├── qs2maodv-rqueue.cc/h          ← generated
│   └── qs2maodv-rtable.cc/h          ← generated
└── helper/
    ├── qs2maodv-helper.cc            ← HAND-WRITTEN
    └── qs2maodv-helper.h             ← HAND-WRITTEN
```
