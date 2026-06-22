#!/usr/bin/env python3
"""
qs2_patch_decay_params.py
==========================
Adds SilenceThreshold (default 15 s) and DecayFactor (default 0.92)
as configurable NS-3 attributes to the qs2maodv routing protocol,
then exposes them as command-line arguments in compare-sim.cc.

Patches (with .bak backup):
  1. qs2maodv-routing-protocol.h   → add 2 member variables
  2. qs2maodv-routing-protocol.cc  → add 2 AddAttribute entries in GetTypeId()
                                      replace hardcoded 15.0 / 0.92 on line 1909
  3. compare-sim.cc                → add variables, AddValue calls, .Set() calls

Usage:
  python3 qs2_patch_decay_params.py
  cd ~/ns-allinone-3.40-qs2maodv/ns-3.40
  ./ns3 build
"""

import os, re, shutil, sys

BASE     = os.path.expanduser("~/ns-allinone-3.40-qs2maodv/ns-3.40")
H_FILE   = f"{BASE}/src/qs2maodv/model/qs2maodv-routing-protocol.h"
CC_FILE  = f"{BASE}/src/qs2maodv/model/qs2maodv-routing-protocol.cc"
SIM_FILE = f"{BASE}/scratch/compare-sim.cc"

TICK = "✓"; CROSS = "✗"

def backup(path):
    bak = path + ".bak_decay"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"  backup → {bak}")

def read(path):
    with open(path, 'r') as f:
        return f.read()

def write(path, content):
    with open(path, 'w') as f:
        f.write(content)

def check_already_patched(content, marker):
    return marker in content

# ═══════════════════════════════════════════════════════════════════════════════
# 1. routing-protocol.h
#    Add two member variables right after the m_enableDecay line
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Patch 1: routing-protocol.h ──────────────────────────────────────────")
backup(H_FILE)
h = read(H_FILE)

if check_already_patched(h, "m_silenceThreshold"):
    print(f"  {TICK} Already patched — skipping")
else:
    # Match the full m_enableDecay line (handles varying whitespace / comments)
    m = re.search(r'[^\n]*m_enableDecay[^\n]*\n', h)
    if not m:
        print(f"  {CROSS} Could not find 'm_enableDecay' line — check header path")
        sys.exit(1)

    new_members = (
        "  double   m_silenceThreshold{{15.0}}; ///< ACK-silence threshold (s) for Q-value decay\n"
        "  double   m_decayFactor{{0.92}};      ///< Q-value decay multiplier (applied every decay pass)\n"
    )
    # {{ }} escapes are for format-string safety; actual content has single braces
    new_members = new_members.replace("{{", "{").replace("}}", "}")

    h = h[:m.end()] + new_members + h[m.end():]
    write(H_FILE, h)
    print(f"  {TICK} Added m_silenceThreshold and m_decayFactor member variables")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. routing-protocol.cc
#    2a. Insert two AddAttribute blocks before the "AdaptiveW3" attribute
#        (which immediately follows EnableDecay in GetTypeId)
#    2b. Replace the hardcoded DecayStaleRoutes call (line 1909)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Patch 2: routing-protocol.cc ─────────────────────────────────────────")
backup(CC_FILE)
cc = read(CC_FILE)

# ── 2a. AddAttribute entries ──────────────────────────────────────────────────
if check_already_patched(cc, '"SilenceThreshold"'):
    print(f"  {TICK} AddAttribute already patched — skipping 2a")
else:
    # Find the AdaptiveW3 AddAttribute line (immediately after EnableDecay block)
    pat_adaptive = re.compile(r'([ \t]*\.AddAttribute\s*\(\s*"AdaptiveW3")', re.MULTILINE)
    m_adaptive = pat_adaptive.search(cc)
    if not m_adaptive:
        print(f"  {CROSS} Could not find 'AdaptiveW3' AddAttribute — check routing-protocol.cc")
        sys.exit(1)

    # Detect indentation from the AdaptiveW3 line
    indent = re.match(r'([ \t]*)', m_adaptive.group(0)).group(1)

    new_attrs = (
        f'{indent}.AddAttribute ("SilenceThreshold",\n'
        f'{indent}               "ACK-silence threshold (seconds) before Q-value decay is applied.",\n'
        f'{indent}               DoubleValue (15.0),\n'
        f'{indent}               MakeDoubleAccessor (&RoutingProtocol::m_silenceThreshold),\n'
        f'{indent}               MakeDoubleChecker<double> (1.0, 120.0))\n'
        f'{indent}.AddAttribute ("DecayFactor",\n'
        f'{indent}               "Q-value decay multiplier applied to stale Q-table entries (0-1).",\n'
        f'{indent}               DoubleValue (0.92),\n'
        f'{indent}               MakeDoubleAccessor (&RoutingProtocol::m_decayFactor),\n'
        f'{indent}               MakeDoubleChecker<double> (0.01, 1.0))\n'
    )

    insert_pos = m_adaptive.start()
    cc = cc[:insert_pos] + new_attrs + cc[insert_pos:]
    print(f"  {TICK} Inserted SilenceThreshold + DecayFactor AddAttribute blocks")

# ── 2b. Replace hardcoded DecayStaleRoutes call ───────────────────────────────
OLD_DECAY_CALL = "m_qtable.DecayStaleRoutes(Simulator::Now(), 15.0, 0.92)"
NEW_DECAY_CALL = "m_qtable.DecayStaleRoutes(Simulator::Now(), m_silenceThreshold, m_decayFactor)"

if NEW_DECAY_CALL in cc:
    print(f"  {TICK} DecayStaleRoutes already patched — skipping 2b")
elif OLD_DECAY_CALL in cc:
    cc = cc.replace(OLD_DECAY_CALL, NEW_DECAY_CALL, 1)
    print(f"  {TICK} Replaced hardcoded 15.0/0.92 in DecayStaleRoutes call")
else:
    print(f"  {CROSS} Could not find DecayStaleRoutes call — check line 1909 manually:")
    print(f"         Old: {OLD_DECAY_CALL}")
    print(f"         New: {NEW_DECAY_CALL}")

write(CC_FILE, cc)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. compare-sim.cc
#    3a. Add two double variables near the other QS2MAODV decay vars
#    3b. Add two cmd.AddValue calls after qsW3
#    3c. Add two qs2maodv.Set() calls after EnableDecay Set
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Patch 3: compare-sim.cc ──────────────────────────────────────────────")
backup(SIM_FILE)
sim = read(SIM_FILE)

# ── 3a. Variable declarations ─────────────────────────────────────────────────
if check_already_patched(sim, "ackSilenceThreshold"):
    print(f"  {TICK} Variable declarations already patched — skipping 3a")
else:
    # Insert after "double qmDecayPeriod = 10.0;"
    m_decperiod = re.search(r'(double\s+qmDecayPeriod\s*=\s*10\.0\s*;[^\n]*\n)', sim)
    if not m_decperiod:
        print(f"  {CROSS} Could not find 'qmDecayPeriod' declaration")
        sys.exit(1)
    new_vars = (
        "  double ackSilenceThreshold = 15.0;  // W2 sweep: ACK-silence threshold (s)\n"
        "  double decayFactor         = 0.92;  // W3 sweep: Q-value decay multiplier\n"
    )
    sim = sim[:m_decperiod.end()] + new_vars + sim[m_decperiod.end():]
    print(f"  {TICK} Added ackSilenceThreshold + decayFactor variable declarations")

# ── 3b. cmd.AddValue calls ────────────────────────────────────────────────────
if check_already_patched(sim, '"ackSilenceThreshold"'):
    print(f"  {TICK} AddValue calls already patched — skipping 3b")
else:
    # Insert after the qsW3 AddValue line
    m_qsw3 = re.search(r'(cmd\.AddValue\s*\(\s*"qsW3"[^\n]*\n)', sim)
    if not m_qsw3:
        print(f"  {CROSS} Could not find 'qsW3' AddValue — check compare-sim.cc line ~115")
        sys.exit(1)
    new_addvalues = (
        '  cmd.AddValue ("ackSilenceThreshold", "QS2MAODV ACK-silence threshold (s)", ackSilenceThreshold);\n'
        '  cmd.AddValue ("decayFactor",         "QS2MAODV Q-value decay multiplier",  decayFactor);\n'
    )
    sim = sim[:m_qsw3.end()] + new_addvalues + sim[m_qsw3.end():]
    print(f"  {TICK} Added cmd.AddValue for ackSilenceThreshold + decayFactor")

# ── 3c. qs2maodv.Set() calls ──────────────────────────────────────────────────
if check_already_patched(sim, '"SilenceThreshold"'):
    print(f"  {TICK} .Set() calls already patched — skipping 3c")
else:
    # Insert after the EnableDecay .Set() line
    m_enabledecay_set = re.search(r'(qs2maodv\.Set\s*\(\s*"EnableDecay"[^\n]*\n)', sim)
    if not m_enabledecay_set:
        print(f"  {CROSS} Could not find qs2maodv.Set(\"EnableDecay\") — check compare-sim.cc line ~194")
        sys.exit(1)
    new_sets = (
        '  qs2maodv.Set ("SilenceThreshold", DoubleValue (ackSilenceThreshold));\n'
        '  qs2maodv.Set ("DecayFactor",      DoubleValue (decayFactor));\n'
    )
    sim = sim[:m_enabledecay_set.end()] + new_sets + sim[m_enabledecay_set.end():]
    print(f"  {TICK} Added qs2maodv.Set() for SilenceThreshold + DecayFactor")

write(SIM_FILE, sim)

# ═══════════════════════════════════════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════════════════════════════════════
print("""
═══════════════════════════════════════════════════════════
Patch xong! Bước tiếp theo:

  cd ~/ns-allinone-3.40-qs2maodv/ns-3.40
  ./ns3 build 2>&1 | tail -20

Nếu build OK → chạy:
  bash ~/qs2_launch_W2_W3.sh

Nếu build lỗi → xem lỗi và báo lại để fix.
Để rollback: các file .bak_decay là bản gốc.
═══════════════════════════════════════════════════════════
""")
