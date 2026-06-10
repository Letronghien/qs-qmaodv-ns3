/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * QS-QMAODV Simulation Script
 *
 * Scenario: 50 nodes, 1000×1000m, random waypoint mobility
 * Traffic: 10 CBR/UDP flows, 512B packets, 4 pkt/s
 * Duration: 200s warm-up 50s + sim 150s
 * Energy: BasicEnergySource E_0=50J, WifiRadioEnergyModel
 *
 * Metrics collected (stdout + CSV):
 *   PDR, throughput, e2e delay, routing overhead, energy consumption
 *
 * Usage:
 *   ./ns3 run "scratch/qs2maodv-sim --nNodes=50 --simTime=150 --seed=1"
 *
 * Authors: QS-QMAODV Research Group — IUH
 */

#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/basic-energy-source-helper.h"
#include "ns3/core-module.h"
#include "ns3/energy-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-radio-energy-model-helper.h"
#include "ns3/wifi-module.h"
#include "ns3/qs2maodv-helper.h"   // QS-QMAODV helper

#include <fstream>
#include <iomanip>
#include <sstream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("Qs2maodvSim");

// ============================================================
// Simulation parameters
// ============================================================
struct SimParams
{
    uint32_t nNodes      = 50;
    double   simTime     = 150.0;  // seconds (excluding warm-up)
    double   warmUp      = 50.0;   // seconds
    uint32_t nFlows      = 10;
    uint32_t pktSize     = 512;    // bytes
    double   pktRate     = 4.0;    // packets/s
    double   areaSize    = 1000.0; // meters (dùng 300.0 khi debug với nNodes<=6)
    double   maxSpeed    = 20.0;   // m/s (random waypoint)
    double   pauseTime   = 0.0;    // s
    double   initialEnergy = 50.0; // J per node
    uint32_t seed        = 1;
    uint32_t maxPaths    = 3;
    double   alpha       = 0.30;
    double   gamma       = 0.90;
    double   epsilon     = 0.30;
    std::string outputCsv = "qs2maodv-results.csv";
};

// ============================================================
// Helper: install energy model
// ============================================================
EnergySourceContainer InstallEnergy(NodeContainer& nodes, double initialEnergy)
{
    BasicEnergySourceHelper basicSourceHelper;
    basicSourceHelper.Set("BasicEnergySourceInitialEnergyJ",
                          DoubleValue(initialEnergy));
    EnergySourceContainer sources = basicSourceHelper.Install(nodes);

    WifiRadioEnergyModelHelper radioEnergyHelper;
    radioEnergyHelper.Set("TxCurrentA", DoubleValue(0.0174));
    radioEnergyHelper.Set("RxCurrentA", DoubleValue(0.0174));
    DeviceEnergyModelContainer deviceModels;
    for (uint32_t i = 0; i < nodes.GetN(); ++i)
    {
        Ptr<EnergySource> src = sources.Get(i);
        Ptr<NetDevice>    dev = nodes.Get(i)->GetDevice(0);
        deviceModels.Add(radioEnergyHelper.Install(dev, src));
    }
    return sources;
}

// ============================================================
// Helper: write CSV header
// ============================================================
void WriteCsvHeader(std::ofstream& ofs)
{
    ofs << "Protocol,Seed,nNodes,nFlows,MaxPaths,Alpha,Gamma,Epsilon,"
        << "PDR,Throughput_kbps,Delay_ms,Jitter_ms,"
        << "OverheadRatio,EnergyPerPkt_J,LiveNodes\n";
}

// ============================================================
// Main
// ============================================================
int main(int argc, char* argv[])
{
    SimParams p;

    CommandLine cmd(__FILE__);
    cmd.AddValue("nNodes",    "Number of nodes",              p.nNodes);
    cmd.AddValue("simTime",   "Simulation time (s)",          p.simTime);
    cmd.AddValue("warmUp",    "Warm-up time (s)",             p.warmUp);
    cmd.AddValue("nFlows",    "Number of CBR flows",          p.nFlows);
    cmd.AddValue("pktSize",   "UDP payload size (bytes)",     p.pktSize);
    cmd.AddValue("pktRate",   "Packets per second per flow",  p.pktRate);
    cmd.AddValue("areaSize",  "Simulation area side (m)",     p.areaSize);
    cmd.AddValue("maxSpeed",  "Max node speed (m/s)",         p.maxSpeed);
    cmd.AddValue("pauseTime", "Pause time for RWP (s)",       p.pauseTime);
    cmd.AddValue("energy",    "Initial energy per node (J)",  p.initialEnergy);
    cmd.AddValue("seed",      "RNG seed",                     p.seed);
    cmd.AddValue("maxPaths",  "Max multipath routes",         p.maxPaths);
    cmd.AddValue("alpha",     "Q-learning rate",              p.alpha);
    cmd.AddValue("gamma",     "Q-learning discount",          p.gamma);
    cmd.AddValue("epsilon",   "Initial epsilon",              p.epsilon);
    cmd.AddValue("output",    "Output CSV file",              p.outputCsv);
    cmd.Parse(argc, argv);

    // RNG
    SeedManager::SetSeed(p.seed);
    SeedManager::SetRun(p.seed);

    double totalTime = p.warmUp + p.simTime;

    // ---- Nodes -------------------------------------------------------
    NodeContainer nodes;
    nodes.Create(p.nNodes);

    // ---- WiFi (802.11b, ad-hoc) -------------------------------------
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",    StringValue("DsssRate11Mbps"),
                                 "ControlMode", StringValue("DsssRate1Mbps"));

    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");

    YansWifiPhyHelper phy;
    YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::FriisPropagationLossModel");
    phy.SetChannel(channel.Create());
    // [FIX v13] TxPower 7.5dBm (~150m range) too low for 1000x1000m area.
    // 20dBm gives ~250-300m range with Friis model, matching standard MANET sims.
    phy.Set("TxPowerStart", DoubleValue(20.0));
    phy.Set("TxPowerEnd",   DoubleValue(20.0));

    NetDeviceContainer devices = wifi.Install(phy, mac, nodes);

    // ---- Mobility (Random Waypoint) ---------------------------------
    MobilityHelper mobility;

    // Position allocator for initial placement AND waypoint targets
    ObjectFactory posFactory;
    posFactory.SetTypeId("ns3::RandomRectanglePositionAllocator");
    posFactory.Set("X", StringValue("ns3::UniformRandomVariable[Min=0|Max=" +
                                    std::to_string(p.areaSize) + "]"));
    posFactory.Set("Y", StringValue("ns3::UniformRandomVariable[Min=0|Max=" +
                                    std::to_string(p.areaSize) + "]"));
    Ptr<PositionAllocator> posAlloc =
        posFactory.Create()->GetObject<PositionAllocator>();

    mobility.SetPositionAllocator(posAlloc);
    mobility.SetMobilityModel("ns3::RandomWaypointMobilityModel",
                              "Speed", StringValue("ns3::UniformRandomVariable[Min=1|Max=" +
                                                   std::to_string(p.maxSpeed) + "]"),
                              "Pause", StringValue("ns3::ConstantRandomVariable[Constant=" +
                                                   std::to_string(p.pauseTime) + "]"),
                              "PositionAllocator", PointerValue(posAlloc));
    mobility.Install(nodes);

    // ---- Energy model -----------------------------------------------
    EnergySourceContainer energySources = InstallEnergy(nodes, p.initialEnergy);

    // ---- Internet stack with QS-QMAODV ------------------------------
    InternetStackHelper internet;
    Qs2maodvHelper qs2maodv;
    qs2maodv.Set("MaxPaths",  UintegerValue(p.maxPaths));
    qs2maodv.Set("Alpha",     DoubleValue(p.alpha));
    qs2maodv.Set("Gamma",     DoubleValue(p.gamma));
    qs2maodv.Set("Epsilon",   DoubleValue(p.epsilon));
    qs2maodv.Set("InitialEnergy", DoubleValue(p.initialEnergy));
    internet.SetRoutingHelper(qs2maodv);
    internet.Install(nodes);

    // ---- IP addressing ----------------------------------------------
    Ipv4AddressHelper address;
    address.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(devices);

    // ---- Applications (CBR/UDP) -------------------------------------
    uint16_t port = 9;
    double   dataRate = p.pktRate * p.pktSize * 8; // bps

    ApplicationContainer serverApps, clientApps;
    Ptr<UniformRandomVariable> rng = CreateObject<UniformRandomVariable>();
    rng->SetAttribute("Min", DoubleValue(0));
    rng->SetAttribute("Max", DoubleValue(p.nNodes - 1));

    std::set<std::pair<uint32_t, uint32_t>> usedPairs;
    uint32_t flowsInstalled = 0;
    uint32_t attempt        = 0;

    while (flowsInstalled < p.nFlows && attempt < 1000)
    {
        ++attempt;
        uint32_t src = rng->GetInteger(0, p.nNodes - 1);
        uint32_t dst = rng->GetInteger(0, p.nNodes - 1);
        if (src == dst) continue;
        if (usedPairs.count({src, dst})) continue;
        usedPairs.insert({src, dst});

        // Sink
        PacketSinkHelper sink("ns3::UdpSocketFactory",
                               InetSocketAddress(Ipv4Address::GetAny(), port + flowsInstalled));
        serverApps.Add(sink.Install(nodes.Get(dst)));

        // Source
        OnOffHelper onOff("ns3::UdpSocketFactory",
                           InetSocketAddress(interfaces.GetAddress(dst), port + flowsInstalled));
        onOff.SetConstantRate(DataRate(dataRate), p.pktSize);
        // [FIX v13] Fixed start after warmUp + small deterministic jitter per flow
        double startJitter = 1.0 + flowsInstalled * 0.5;
        onOff.SetAttribute("StartTime", TimeValue(Seconds(p.warmUp + startJitter)));
        onOff.SetAttribute("StopTime",  TimeValue(Seconds(totalTime)));
        clientApps.Add(onOff.Install(nodes.Get(src)));

        ++flowsInstalled;
    }

    NS_LOG_UNCOND("Flows installed: " << flowsInstalled);
    serverApps.Start(Seconds(0.0));
    serverApps.Stop(Seconds(totalTime));

    // ---- Flow monitor -----------------------------------------------
    FlowMonitorHelper flowMonHelper;
    Ptr<FlowMonitor> flowMonitor = flowMonHelper.InstallAll();

    // ---- Run ---------------------------------------------------------
    Simulator::Stop(Seconds(totalTime));
    NS_LOG_UNCOND("Starting QS-QMAODV simulation for " << totalTime << "s ...");
    Simulator::Run();

    // ---- Collect metrics --------------------------------------------
    flowMonitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier =
        DynamicCast<Ipv4FlowClassifier>(flowMonHelper.GetClassifier());
    FlowMonitor::FlowStatsContainer stats = flowMonitor->GetFlowStats();

    double totalTx         = 0, totalRx       = 0;
    double totalDelay      = 0, totalJitter    = 0;
    double totalThroughput = 0;
    uint32_t flowCount     = 0;

    for (auto& kv : stats)
    {
        // Skip AODV/routing control flows (port 654)
        Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(kv.first);
        // [FIX v13] Filter routing control traffic (port 655 = QS2MAODV, 654 = AODV/QMAODV)
        if (t.destinationPort == 655 || t.sourcePort == 655) continue;
        if (t.destinationPort == 654 || t.sourcePort == 654) continue;

        const FlowMonitor::FlowStats& fs = kv.second;
        totalTx += fs.txPackets;
        totalRx += fs.rxPackets;
        if (fs.rxPackets > 0)
        {
            double delay  = fs.delaySum.GetSeconds() / fs.rxPackets;
            double jitter = (fs.rxPackets > 1)
                            ? fs.jitterSum.GetSeconds() / (fs.rxPackets - 1) : 0.0;
            double tput   = fs.rxBytes * 8.0 / p.simTime / 1000.0; // kbps
            totalDelay      += delay;
            totalJitter     += jitter;
            totalThroughput += tput;
            ++flowCount;
        }
    }

    double pdr        = (totalTx > 0) ? totalRx / totalTx : 0.0;
    double avgDelay   = (flowCount > 0) ? totalDelay  / flowCount * 1000.0 : 0.0; // ms
    double avgJitter  = (flowCount > 0) ? totalJitter / flowCount * 1000.0 : 0.0; // ms
    double avgTput    = (flowCount > 0) ? totalThroughput / flowCount : 0.0; // kbps

    // Overhead: routing pkts / data pkts (rough proxy via flowmon)
    double overheadRatio = 0.0; // placeholder — detailed RREQ/RERR counters need traces

    // Energy consumed
    double totalEnergyConsumed = 0.0;
    uint32_t liveNodes = 0;
    for (uint32_t i = 0; i < nodes.GetN(); ++i)
    {
        Ptr<EnergySource> src = energySources.Get(i);
        double rem = src->GetRemainingEnergy();
        totalEnergyConsumed += (p.initialEnergy - rem);
        if (rem > 0.0) ++liveNodes;
    }
    double energyPerPkt = (totalRx > 0) ? totalEnergyConsumed / totalRx : 0.0;

    // ---- Print results ----------------------------------------------
    std::cout << "\n========== QS-QMAODV Simulation Results ==========\n";
    std::cout << std::fixed << std::setprecision(4);
    std::cout << "Nodes       : " << p.nNodes     << "\n";
    std::cout << "Flows       : " << flowsInstalled << "\n";
    std::cout << "MaxPaths    : " << p.maxPaths   << "\n";
    std::cout << "α/γ/ε       : " << p.alpha << "/" << p.gamma << "/" << p.epsilon << "\n";
    std::cout << "Seed        : " << p.seed       << "\n";
    std::cout << "---\n";
    std::cout << "PDR         : " << pdr * 100.0  << " %\n";
    std::cout << "Throughput  : " << avgTput       << " kbps (avg/flow)\n";
    std::cout << "E2E Delay   : " << avgDelay      << " ms\n";
    std::cout << "Jitter      : " << avgJitter     << " ms\n";
    std::cout << "Energy/pkt  : " << energyPerPkt  << " J\n";
    std::cout << "Live nodes  : " << liveNodes     << "/" << p.nNodes << "\n";
    std::cout << "==================================================\n\n";

    // ---- Write CSV --------------------------------------------------
    bool newFile = !std::ifstream(p.outputCsv).good();
    std::ofstream ofs(p.outputCsv, std::ios::app);
    if (newFile) WriteCsvHeader(ofs);
    ofs << std::fixed << std::setprecision(6);
    ofs << "QS-QMAODV,"
        << p.seed      << ","
        << p.nNodes    << ","
        << flowsInstalled << ","
        << p.maxPaths  << ","
        << p.alpha     << ","
        << p.gamma     << ","
        << p.epsilon   << ","
        << pdr         << ","
        << avgTput     << ","
        << avgDelay    << ","
        << avgJitter   << ","
        << overheadRatio << ","
        << energyPerPkt  << ","
        << liveNodes   << "\n";
    ofs.close();

    Simulator::Destroy();
    NS_LOG_UNCOND("Results written to " << p.outputCsv);
    return 0;
}
