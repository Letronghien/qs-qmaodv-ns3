# QS-QMAODV — Queue-State-Aware Q-Learning Multipath AODV

NS-3.40 implementation — IUH Research.

> **Hoàn toàn độc lập** — tạo bản NS-3 riêng `ns-allinone-3.40-qsqmaodv`,
> không đụng đến các dự án NS-3 hiện có.

## Cấu trúc repo

```
qs-qmaodv-ns3/
├── README.md
├── setup-vm.sh                   ← Chạy 1 lần trên VM là xong
├── scratch/
│   └── qsqmaodv-sim.cc           ← Simulation script
└── src/
    └── qsqmaodv/
        ├── CMakeLists.txt
        ├── model/
        │   ├── qsqmaodv-qtable.h / .cc          ← [QS-1] 3D state space
        │   └── qsqmaodv-routing-protocol.h / .cc ← [QS-2][QS-3] QS logic
        └── helper/
            └── qsqmaodv-helper.h / .cc
```

## Điểm khác biệt QS-QMAODV vs QMAODV

| | QMAODV | **QS-QMAODV** |
|---|---|---|
| **State** | s = destination | s = (dst, **queue_bucket**, **energy_bucket**) |
| **Epsilon** | Decay timer | **Queue-triggered**: q>0.70→ε↑, q<0.30→ε↓ |
| **Selection** | argmax Q(s,a) | **Hybrid**: Q(s,a)×(1−q_a)^β |
| **Reward** | ACK + delay | ACK + delay + **energy** |

## Cài đặt trên VM (1 lệnh duy nhất)

```bash
# 1. Clone repo
cd ~
git clone https://github.com/Letronghien/qs-qmaodv-ns3.git
cd qs-qmaodv-ns3

# 2. Chạy setup — tự động tạo NS-3 riêng và build
bash setup-vm.sh
```

Script sẽ:
1. Copy `~/ns-allinone-3.40` → `~/ns-allinone-3.40-qsqmaodv` (bản riêng)
2. Tạo support files từ qmaodv (đổi namespace → qsqmaodv)
3. Copy module QS-QMAODV vào
4. Configure + Build tự động

## Chạy simulation

```bash
cd ~/ns-allinone-3.40-qsqmaodv/ns-3.40

# Chạy mặc định (50 nodes, 10 flows)
./ns3 run scratch/qsqmaodv-sim

# Tùy chọn
./ns3 run "scratch/qsqmaodv-sim \
    --nNodes=50 \
    --nFlows=10 \
    --simTime=150 \
    --seed=1 \
    --maxPaths=3"
```

Kết quả ghi vào `qsqmaodv-results.csv`.

## Tham số blueprint

| Tham số | Giá trị |
|---|---|
| α | 0.30 |
| γ | 0.90 |
| ε_init / ε_min / ε_max | 0.30 / 0.10 / 0.50 |
| θ_H / θ_L | 0.70 / 0.30 |
| δ_q / δ_decay | 0.15 / 0.02 |
| β (hybrid) | 0.50 |
| w1/w2/w3 | 0.45/0.45/0.10 |
| MaxPaths | 3 |
| E_0 | 50 J |

## Kịch bản simulation

- 50 nodes, 1000×1000m, Random Waypoint v∈[1,20] m/s
- 10 CBR/UDP flows, 512B, 4 pkt/s
- 802.11b 11Mbps, TwoRayGround
- BasicEnergySource E_0=50J, WifiRadioEnergyModel
- Thời gian: 200s (50s warm-up + 150s đo)
