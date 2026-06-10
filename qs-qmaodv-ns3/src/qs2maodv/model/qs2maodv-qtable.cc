/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * QS-QMAODV Q-table — implementation.
 * See qs2maodv-qtable.h for full design discussion.
 */

#include "qs2maodv-qtable.h"
#include "ns3/log.h"
#include "ns3/simulator.h"
#include <algorithm>
#include <cmath>
#include <numeric>

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("Qs2maodvQTable");

namespace qs2maodv
{

// ============================================================
// Constructor
// ============================================================
QsQTable::QsQTable(uint32_t maxPaths)
    : m_maxPaths(maxPaths),
      m_alpha(0.30),
      m_gamma(0.90),
      m_epsilon(0.30),
      m_epsilonMin(0.10),
      m_epsilonMax(0.50),
      m_thetaH(0.70),
      m_thetaL(0.30),
      m_deltaQ(0.15),
      m_deltaDecay(0.02),
      m_w1(0.45),
      m_w2(0.45),
      m_w3(0.10),
      m_beta(0.50)
{
    m_uniform = CreateObject<UniformRandomVariable>();
}

// ============================================================
// Capacity
// ============================================================
void QsQTable::SetMaxPaths(uint32_t mp)
{
    NS_ASSERT_MSG(mp >= 1, "MaxPaths must be >= 1");
    m_maxPaths = mp;
}

uint32_t QsQTable::GetMaxPaths() const { return m_maxPaths; }

// ============================================================
// RL hyper-parameters
// ============================================================
void QsQTable::SetLearningParameters(double alpha, double gamma, double epsilon)
{
    NS_ASSERT_MSG(alpha >= 0.0 && alpha <= 1.0, "alpha in [0,1]");
    NS_ASSERT_MSG(gamma >= 0.0 && gamma <= 1.0, "gamma in [0,1]");
    NS_ASSERT_MSG(epsilon >= 0.0 && epsilon <= 1.0, "epsilon in [0,1]");
    m_alpha   = alpha;
    m_gamma   = gamma;
    m_epsilon = epsilon;
}

void QsQTable::SetRewardWeights(double w1, double w2, double w3)
{
    m_w1 = w1;
    m_w2 = w2;
    m_w3 = w3;
}

// ============================================================
// Queue-triggered epsilon (blueprint §3.3)
// ============================================================
void QsQTable::UpdateEpsilon(double qt)
{
    if (qt > m_thetaH)
    {
        // High queue → congested → explore more
        m_epsilon = std::min(m_epsilonMax, m_epsilon + m_deltaQ);
        NS_LOG_DEBUG("QS-ε BUMP qt=" << qt << " ε=" << m_epsilon);
    }
    else if (qt < m_thetaL)
    {
        // Low queue → stable → exploit more
        m_epsilon = std::max(m_epsilonMin, m_epsilon - m_deltaDecay);
        NS_LOG_DEBUG("QS-ε DECAY qt=" << qt << " ε=" << m_epsilon);
    }
    // else: unchanged
}

// ============================================================
// State construction (blueprint §3.2)
// ============================================================
/* static */
QsStateKey QsQTable::BuildState(Ipv4Address dst, double qt, double Et)
{
    // Clamp to [0,1]
    qt = std::max(0.0, std::min(1.0, qt));
    Et = std::max(0.0, std::min(1.0, Et));

    int qBucket = std::min(4, static_cast<int>(qt / 0.20));
    int eBucket = std::min(4, static_cast<int>(Et / 0.20));

    return QsStateKey(dst, qBucket, eBucket);
}

// ============================================================
// Private helpers
// ============================================================
std::vector<QsRecord>::iterator QsQTable::FindWorst(std::vector<QsRecord>& vec)
{
    if (vec.empty()) return vec.end();
    auto worst = vec.begin();
    for (auto it = vec.begin() + 1; it != vec.end(); ++it)
    {
        if (it->rt.GetHop() > worst->rt.GetHop()) worst = it;
    }
    return worst;
}

double QsQTable::ApproxNextHopQueue(uint32_t hcA, uint32_t hcMax) const
{
    // Proxy: nodes farther from source tend to have higher queue occupancy
    // f_avail ≈ 1 - (HC_a / HC_max)
    if (hcMax == 0) return 0.0;
    double ratio = static_cast<double>(hcA) / static_cast<double>(hcMax);
    return std::max(0.0, std::min(1.0, ratio));
}

void QsQTable::ReinitQValues(Ipv4Address dst)
{
    // Re-normalise Q-values using 1/HC across ALL state buckets for this dst
    // Only seed entries that have not been updated by experience (txCount == 0)
    double sumInv = 0.0;
    for (const auto& key : m_dstToKeys[dst])
    {
        auto it = m_records.find(key);
        if (it == m_records.end()) continue;
        for (const auto& r : it->second)
        {
            uint32_t hc = std::max<uint32_t>(1, r.rt.GetHop());
            sumInv += 1.0 / static_cast<double>(hc);
        }
    }
    if (sumInv <= 0.0) return;

    for (const auto& key : m_dstToKeys[dst])
    {
        auto it = m_records.find(key);
        if (it == m_records.end()) continue;
        for (auto& r : it->second)
        {
            if (r.txCount > 0) continue;  // preserve learned Q
            uint32_t hc = std::max<uint32_t>(1, r.rt.GetHop());
            r.qValue = (1.0 / hc) / sumInv;
        }
    }
}

// ============================================================
// Route management
// ============================================================
bool QsQTable::AddRoute(const RoutingTableEntry& rt, const QsStateKey& state)
{
    Ipv4Address dst = rt.GetDestination();
    Ipv4Address nh  = rt.GetNextHop();
    auto& vec = m_records[state];

    // Dedup: refresh if (state, nextHop) already present
    for (auto& existing : vec)
    {
        if (existing.rt.GetNextHop() == nh)
        {
            existing.rt = rt;
            NS_LOG_DEBUG("QS AddRoute refresh: " << dst << " via " << nh);
            return false;
        }
    }

    // Register key for this dst
    auto& keys = m_dstToKeys[dst];
    if (std::find(keys.begin(), keys.end(), state) == keys.end())
        keys.push_back(state);

    if (vec.size() < m_maxPaths)
    {
        vec.push_back(QsRecord(rt, 0.0));
        NS_LOG_DEBUG("QS AddRoute: " << dst << " via " << nh
                     << " HC=" << (uint32_t)rt.GetHop()
                     << " qBkt=" << state.qBucket << " eBkt=" << state.eBucket);
        ReinitQValues(dst);
        return true;
    }

    // At capacity: evict worst if rt is strictly better
    auto worst = FindWorst(vec);
    if (worst != vec.end() && rt.GetHop() < worst->rt.GetHop())
    {
        NS_LOG_DEBUG("QS Evict: " << dst << " via " << worst->rt.GetNextHop()
                     << " for HC=" << (uint32_t)rt.GetHop());
        *worst = QsRecord(rt, 0.0);
        ReinitQValues(dst);
        return true;
    }
    return false;
}

bool QsQTable::EnsureRecord(const RoutingTableEntry& rt, const QsStateKey& state)
{
    Ipv4Address dst = rt.GetDestination();
    Ipv4Address nh  = rt.GetNextHop();
    auto& vec = m_records[state];

    for (auto& existing : vec)
    {
        if (existing.rt.GetNextHop() == nh)
        {
            existing.rt = rt;  // refresh metadata, keep learned Q
            return false;
        }
    }

    // Register key
    auto& keys = m_dstToKeys[dst];
    if (std::find(keys.begin(), keys.end(), state) == keys.end())
        keys.push_back(state);

    // Bypass capacity for primary route
    vec.push_back(QsRecord(rt, 0.0));
    ReinitQValues(dst);
    NS_LOG_DEBUG("QS EnsureRecord: " << dst << " via " << nh);
    return true;
}

void QsQTable::UpdateQValueOrCreate(const RoutingTableEntry& rt,
                                     const QsStateKey& state,
                                     double ackSuccess, double delaySec, double Et)
{
    EnsureRecord(rt, state);
    UpdateQValue(state, rt.GetNextHop(), ackSuccess, delaySec, Et);
}

// ============================================================
// GetRoutes — returns all valid routes for dst across all states
// ============================================================
uint32_t QsQTable::GetRoutes(Ipv4Address dst,
                              std::vector<RoutingTableEntry>& routes,
                              const RoutingTable* mainTable) const
{
    auto kit = m_dstToKeys.find(dst);
    if (kit == m_dstToKeys.end()) return 0;

    uint32_t added = 0;
    for (const auto& key : kit->second)
    {
        auto it = m_records.find(key);
        if (it == m_records.end()) continue;
        for (const auto& r : it->second)
        {
            if (r.rt.GetFlag() != VALID || r.rt.GetLifeTime() <= Time(0)) continue;
            if (mainTable != nullptr)
            {
                RoutingTableEntry nbr;
                if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(r.rt.GetNextHop(), nbr) ||
                    nbr.GetFlag() != VALID)
                    continue;
            }
            // Dedup by next-hop
            bool dup = false;
            for (const auto& already : routes)
                if (already.GetNextHop() == r.rt.GetNextHop()) { dup = true; break; }
            if (!dup) { routes.push_back(r.rt); ++added; }
        }
    }
    return added;
}

// ============================================================
// Build candidates for hybrid selection
// ============================================================
std::vector<QsRecord> QsQTable::BuildCandidates(const RoutingTableEntry& primary,
                                                  const QsStateKey& state,
                                                  const RoutingTable* mainTable) const
{
    Ipv4Address dst    = primary.GetDestination();
    Ipv4Address primNh = primary.GetNextHop();

    std::vector<QsRecord> cands;

    // Look up primary's learned Q from the state's records
    double primQ    = 0.0;
    bool   primFound = false;
    auto it = m_records.find(state);
    if (it != m_records.end())
    {
        for (const auto& r : it->second)
        {
            if (r.rt.GetNextHop() == primNh) { primQ = r.qValue; primFound = true; }
            else
            {
                // Alternate
                if (r.rt.GetFlag() != VALID || r.rt.GetLifeTime() <= Time(0)) continue;
                if (mainTable != nullptr)
                {
                    RoutingTableEntry nbr;
                    if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(r.rt.GetNextHop(), nbr) ||
                        nbr.GetFlag() != VALID)
                        continue;
                }
                cands.push_back(r);
            }
        }
    }

    // Also collect alternates from OTHER state buckets for same dst
    auto kit = m_dstToKeys.find(dst);
    if (kit != m_dstToKeys.end())
    {
        for (const auto& key : kit->second)
        {
            if (key == state) continue;
            auto it2 = m_records.find(key);
            if (it2 == m_records.end()) continue;
            for (const auto& r : it2->second)
            {
                if (r.rt.GetNextHop() == primNh) continue;
                if (r.rt.GetFlag() != VALID || r.rt.GetLifeTime() <= Time(0)) continue;
                // Dedup by nextHop
                bool dup = false;
                for (const auto& c : cands)
                    if (c.rt.GetNextHop() == r.rt.GetNextHop()) { dup = true; break; }
                if (!dup) cands.push_back(r);
            }
        }
    }

    // Build primary QRecord
    uint32_t hcP = std::max<uint32_t>(1, primary.GetHop());
    double   primQValue;
    if (primFound)
    {
        primQValue = primQ;
    }
    else
    {
        double sumInv = 1.0 / hcP;
        for (const auto& c : cands)
            sumInv += 1.0 / std::max<uint32_t>(1, c.rt.GetHop());
        primQValue = (sumInv > 0.0) ? (1.0 / hcP) / sumInv : 0.5;
    }
    cands.insert(cands.begin(), QsRecord(primary, primQValue));
    return cands;
}

// ============================================================
// Hybrid ε-greedy selection (blueprint §3.5)
// ============================================================
bool QsQTable::SelectHybrid(const RoutingTableEntry& primary,
                             const QsStateKey& state,
                             double qt_local,
                             RoutingTableEntry& out,
                             const RoutingTable* mainTable)
{
    auto cands = BuildCandidates(primary, state, mainTable);

    if (cands.empty())
    {
        out = primary;
        return false;
    }
    if (cands.size() == 1)
    {
        out = cands[0].rt;
        return true;
    }

    // Find max HC across candidates for proxy approximation
    uint32_t hcMax = 0;
    for (const auto& c : cands)
        hcMax = std::max(hcMax, static_cast<uint32_t>(c.rt.GetHop()));

    double u = m_uniform->GetValue(0.0, 1.0);

    if (u < m_epsilon)
    {
        // EXPLORE: uniform random
        uint32_t idx = static_cast<uint32_t>(
            m_uniform->GetValue(0.0, static_cast<double>(cands.size())));
        if (idx >= cands.size()) idx = static_cast<uint32_t>(cands.size()) - 1;
        out = cands[idx].rt;
        NS_LOG_DEBUG("QS EXPLORE dst=" << primary.GetDestination()
                     << " via " << out.GetNextHop()
                     << " ε=" << m_epsilon);
        return true;
    }

    // EXPLOIT: hybrid score = Q(s,a) * (1 - q_a)^β
    size_t bestIdx = 0;
    double bestScore = -std::numeric_limits<double>::infinity();
    uint32_t bestHC  = std::numeric_limits<uint32_t>::max();

    for (size_t i = 0; i < cands.size(); ++i)
    {
        double   q   = cands[i].qValue;
        uint32_t hcA = std::max<uint32_t>(1, cands[i].rt.GetHop());

        // Approximate queue of next-hop using HC proxy
        double q_a    = ApproxNextHopQueue(hcA, hcMax);
        double f_avail = std::pow(1.0 - q_a, m_beta);
        double score  = q * f_avail;

        NS_LOG_DEBUG("QS candidate via " << cands[i].rt.GetNextHop()
                     << " Q=" << q << " q_a=" << q_a
                     << " f=" << f_avail << " score=" << score);

        if (score > bestScore || (std::fabs(score - bestScore) < 1e-9 && hcA < bestHC))
        {
            bestScore = score;
            bestHC    = hcA;
            bestIdx   = i;
        }
    }

    out = cands[bestIdx].rt;
    NS_LOG_DEBUG("QS EXPLOIT dst=" << primary.GetDestination()
                 << " via " << out.GetNextHop()
                 << " score=" << bestScore << " HC=" << bestHC
                 << " qBkt=" << state.qBucket << " eBkt=" << state.eBucket);
    return true;
}

// ============================================================
// Q-value update (blueprint §3.6) — Bellman with 3-term reward
// ============================================================
void QsQTable::UpdateQValue(const QsStateKey& state,
                             Ipv4Address nextHop,
                             double ackSuccess,
                             double delaySec,
                             double Et)
{
    if (delaySec < 0.0) delaySec = 0.0;
    Et = std::max(0.0, std::min(1.0, Et));

    // r = w1*ACK + w2*1/(delay+1) + w3*E_t
    double reward = m_w1 * ackSuccess
                  + m_w2 * (1.0 / (delaySec + 1.0))
                  + m_w3 * Et;

    auto it = m_records.find(state);
    if (it == m_records.end()) return;

    // max_a' Q(s', a')  — use max Q across all records in this state
    double maxFuture = 0.0;
    QsRecord* target = nullptr;
    for (auto& r : it->second)
    {
        if (r.qValue > maxFuture) maxFuture = r.qValue;
        if (r.rt.GetNextHop() == nextHop) target = &r;
    }
    if (target == nullptr) return;

    double oldQ = target->qValue;
    // Q ← (1-α)*Q + α*(r + γ*max_a' Q)
    target->qValue = (1.0 - m_alpha) * oldQ
                   + m_alpha * (reward + m_gamma * maxFuture);
    target->txCount  += 1;
    if (ackSuccess > 0.5) target->ackCount += 1;
    target->lastUpd = Simulator::Now();

    NS_LOG_DEBUG("QS Q-update dst=" << state.dst
                 << " nh=" << nextHop
                 << " r=" << reward
                 << " Q: " << oldQ << " → " << target->qValue
                 << " [qBkt=" << state.qBucket
                 << " eBkt=" << state.eBucket << "]");
}

// ============================================================
// Lifecycle
// ============================================================
void QsQTable::DeleteRoutes(Ipv4Address dst)
{
    auto kit = m_dstToKeys.find(dst);
    if (kit == m_dstToKeys.end()) return;
    for (const auto& key : kit->second)
        m_records.erase(key);
    m_dstToKeys.erase(kit);
}

void QsQTable::DeleteRoute(Ipv4Address dst, Ipv4Address nextHop)
{
    auto kit = m_dstToKeys.find(dst);
    if (kit == m_dstToKeys.end()) return;
    for (const auto& key : kit->second)
    {
        auto it = m_records.find(key);
        if (it == m_records.end()) continue;
        auto& vec = it->second;
        vec.erase(std::remove_if(vec.begin(), vec.end(),
                  [&](const QsRecord& r){ return r.rt.GetNextHop() == nextHop; }),
                  vec.end());
        if (vec.empty()) m_records.erase(it);
    }
}

void QsQTable::RemoveNextHopGlobally(Ipv4Address nextHop)
{
    for (auto it = m_records.begin(); it != m_records.end(); )
    {
        auto& vec = it->second;
        vec.erase(std::remove_if(vec.begin(), vec.end(),
                  [&](const QsRecord& r){ return r.rt.GetNextHop() == nextHop; }),
                  vec.end());
        if (vec.empty()) it = m_records.erase(it); else ++it;
    }
}

uint32_t QsQTable::Size() const
{
    return std::accumulate(m_records.begin(), m_records.end(), uint32_t{0},
        [](uint32_t a, const auto& kv){ return a + static_cast<uint32_t>(kv.second.size()); });
}

uint32_t QsQTable::CountFor(Ipv4Address dst) const
{
    auto kit = m_dstToKeys.find(dst);
    if (kit == m_dstToKeys.end()) return 0;
    uint32_t count = 0;
    for (const auto& key : kit->second)
    {
        auto it = m_records.find(key);
        if (it != m_records.end()) count += static_cast<uint32_t>(it->second.size());
    }
    return count;
}

void QsQTable::Clear()
{
    m_records.clear();
    m_dstToKeys.clear();
}

double QsQTable::GetQValue(const QsStateKey& state, Ipv4Address nextHop) const
{
    auto it = m_records.find(state);
    if (it == m_records.end()) return 0.0;
    for (const auto& r : it->second)
        if (r.rt.GetNextHop() == nextHop) return r.qValue;
    return 0.0;
}

void QsQTable::Print(std::ostream& os) const
{
    os << "QsQTable (" << Size() << " entries, MaxPaths=" << m_maxPaths
       << ", α=" << m_alpha << " γ=" << m_gamma << " ε=" << m_epsilon
       << " β=" << m_beta
       << " w1=" << m_w1 << " w2=" << m_w2 << " w3=" << m_w3 << "):\n";
    for (const auto& kv : m_records)
    {
        os << "  [dst=" << kv.first.dst
           << " qBkt=" << kv.first.qBucket
           << " eBkt=" << kv.first.eBucket << "]:\n";
        for (const auto& r : kv.second)
        {
            os << "    via " << r.rt.GetNextHop()
               << " HC=" << (uint32_t)r.rt.GetHop()
               << " Q=" << r.qValue
               << " tx=" << r.txCount << " ack=" << r.ackCount << "\n";
        }
    }
}

} // namespace qs2maodv
} // namespace ns3
