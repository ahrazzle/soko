// Shared test harness for the 15x7 III-14 floor prover (experiments/iii14_15x7_verified_floor).
// It includes only files inside this repository. The prover's main() holds the board setup and the
// PDB construction, so init_globals() and build_all() below repeat those few lines; the test
// program checks them against the prover's own start-state and R48 behaviour.
#pragma once
#include "../../experiments/iii14_15x7_verified_floor/iii14_15x7_core.hpp"
#include "../../experiments/iii14_15x7_verified_floor/iii14_ringflow5_pdb.hpp"
#include "../../experiments/iii14_15x7_verified_floor/iii14_harvest_pdb.hpp"
#include "../../experiments/iii14_15x7_verified_floor/iii14_rowstrip_pdb.hpp"
#include "../../experiments/iii14_15x7_verified_floor/iii14_gateway67_pdb.hpp"

// Same board setup as prove_iii14_15x7_floor.cpp (the loop at the top of main).
inline void init_globals() {
  int g_i = 0;
  for (int y = 0; y < H; ++y)
    for (int x = 0; x < W; ++x) {
      char c = GRID_III14[y][x]; int i = y * W + x;
      IS_ORIG[i] = (c == '#'); IS_SW[i] = (c == '}'); IS_PD[i] = (c == ']');
      IS_VAULT[i] = (y == 3 && x >= 9 && x <= 11);
      if (c == '#') ORIGIN_MASK |= bit(i);
      else if (c == '}') SWITCH_MASK |= bit(i);
      else if (c == ']') { PDOOR_MASK |= bit(i); CHAMBER_MASK |= bit(i); }
      else if (c == 'G') { GOALS[g_i++] = i; CHAMBER_MASK |= bit(i); }
      else if (c == '5') B0 = i;
      else if (c == 'D') D0 = i;
      if (IS_VAULT[i]) CHAMBER_MASK |= bit(i);
      int dm = max(0, max(4 - x, x - 6)) + max(0, max(2 - y, y - 4));
      D5_RING[i] = min(4, dm); D5_MASK[D5_RING[i]] |= bit(i);
      for (int d = 0; d < 4; ++d) {
        int nx = x + DX[d], ny = y + DY[d];
        if (nx >= 0 && nx < W && ny >= 0 && ny < H) ORTHO[i] |= bit(ny * W + nx);
      }
    }
  for (int b = 0; b < N; ++b) {
    int bx = b % W, by = b / W;
    for (int y = max(0, by - 2); y <= min(H - 1, by + 2); ++y)
      for (int x = max(0, bx - 2); x <= min(W - 1, bx + 2); ++x) AURA[b] |= bit(y * W + x);
  }
}

static RingFlow5_15PDB pdb_rf5;
static HarvestAdj15PDB pdb_ha;
static RowStrip15PDB pdb_r2, pdb_r3;
static Gateway67_15PDB pdb_gw;

// Same builds as the prover, run on two threads.
inline void build_all() {
  thread tb1([&]() { pdb_rf5.build(); pdb_r2.build(2); pdb_r3.build(3); });
  thread tb2([&]() { pdb_gw.build(); pdb_ha.build(); });
  tb1.join(); tb2.join();
}

// Same formula as the prover's eval_h lambda.
inline uint8_t eval_h(const CState& s) {
  CState ms = mirror_y_state(s);
  int h = max({pdb_rf5.lookup(s), pdb_ha.lookup(s), pdb_ha.lookup(ms),
        pdb_gw.lookup(s), pdb_r2.lookup(s), pdb_r2.lookup(ms), pdb_r3.lookup(s)});
  return (uint8_t)min(250, h);
}

// The seven lookups that eval_h takes the maximum of, in the prover's order.
inline array<int, 7> parts(const CState& s) {
  CState ms = mirror_y_state(s);
  return {pdb_rf5.lookup(s), pdb_ha.lookup(s), pdb_ha.lookup(ms), pdb_gw.lookup(s),
          pdb_r2.lookup(s), pdb_r2.lookup(ms), pdb_r3.lookup(s)};
}
static const char* PART_NAMES[8] = {"rf5", "ha", "ha(mirror)", "gw", "r2", "r2(mirror)", "r3", "eval_h"};

inline CState start_state() {
  return CState{0, ORIGIN_MASK, (uint8_t)(B0 % W), (uint8_t)(B0 / W), (uint8_t)(D0 % W), (uint8_t)(D0 / W), 1, 0};
}

inline string show(const CState& s) {
  string out;
  for (int y = 0; y < H; ++y) {
    for (int x = 0; x < W; ++x) {
      int i = y * W + x; char c = '.';
      if (IS_SW[i]) c = '}'; if (IS_PD[i]) c = s.doors_open ? '_' : ']';
      if (i == GOALS[0] || i == GOALS[1]) c = 'G';
      if (tst(s.walls, i)) c = '#'; if (tst(s.crates, i)) c = '*';
      if (s.bx == x && s.by == y) c = 'B'; if (s.dx == x && s.dy == y) c = 'D';
      out += c;
    }
    out += '\n';
  }
  out += string("active=") + (s.ah ? "Druid" : "Bard") + " doors_open=" + to_string(s.doors_open) + "\n";
  return out;
}

inline bool state_eq(const CState& a, const CState& b) { return pack_raw(a) == pack_raw(b); }

// Replay keys with step_concrete. ok is false if any key is rejected; *at is then the index of that key.
inline CState replay(const CState& from, const string& keys, bool* ok = nullptr, int* at = nullptr) {
  CState cur = from;
  for (size_t k = 0; k < keys.size(); ++k) {
    CState nx; size_t mv = string("UDLRA").find(keys[k]);
    if (mv == string::npos || !step_concrete(cur, (int)mv, nx)) { if (ok) *ok = false; if (at) *at = (int)k; return cur; }
    cur = nx;
  }
  if (ok) *ok = true;
  return cur;
}
inline CState replay(const string& keys, bool* ok = nullptr, int* at = nullptr) { return replay(start_state(), keys, ok, at); }

// Open-addressing set of canonical Packed15 keys, with the prover's key and full-state equality.
struct CanonTable {
  vector<Packed15> keys; vector<uint32_t> slot; size_t mask;
  explicit CanonTable(int bits, size_t reserve) : slot(1ULL << bits, UINT32_MAX), mask((1ULL << bits) - 1) { keys.reserve(reserve); }
  pair<uint32_t, bool> insert(const Packed15& k) {
    size_t sl = k.hash64() & mask;
    while (slot[sl] != UINT32_MAX) { if (keys[slot[sl]] == k) return {slot[sl], false}; sl = (sl + 1) & mask; }
    uint32_t id = (uint32_t)keys.size(); keys.push_back(k); slot[sl] = id; return {id, true};
  }
};

// Layered BFS from s over the whole graph with canonical dedupe. Calls visit(state, depth) once per
// canonical state (raw representative as first reached). Win states are terminal. Returns the number of
// states; stops after depth maxd. firstwin = depth of the first win state found (-1 if none within maxd).
struct Bfs { vector<CState> states; vector<uint8_t> depth; int firstwin = -1; };
inline Bfs bfs(const CState& s, int maxd) {
  Bfs r; CanonTable tab(24, 1 << 22);
  tab.insert(pack_canon(s)); r.states.push_back(s); r.depth.push_back(0);
  if (is_win(s)) r.firstwin = 0;
  size_t lo = 0;
  for (int d = 0; d < maxd; ++d) {
    size_t hi = r.states.size();
    for (size_t i = lo; i < hi; ++i) {
      if (is_win(r.states[i])) continue;
      for (int mv = 0; mv < 5; ++mv) {
        CState ns; if (!step_concrete(r.states[i], mv, ns)) continue;
        if (tab.insert(pack_canon(ns)).second) {
          r.states.push_back(ns); r.depth.push_back(d + 1);
          if (r.firstwin < 0 && is_win(ns)) r.firstwin = d + 1;
        }
      }
    }
    lo = hi;
  }
  return r;
}

struct Viol { int part; int hs, hn; int mv; string where; };

// Per-lookup consistency on every edge out of s: L(s) <= 1 + L(s'), and L = 0 at a win s'.
// Also the same for eval_h. Counts edges. Returns the number of violations.
inline int check_edges(const CState& s, vector<Viol>& out, size_t cap, uint64_t& edges, const string& where) {
  int nv = 0;
  auto P = parts(s); int hs = eval_h(s);
  for (int mv = 0; mv < 5; ++mv) {
    CState ns; if (!step_concrete(s, mv, ns)) continue;
    edges++;
    auto Q = parts(ns); int hn = eval_h(ns);
    for (int i = 0; i < 7; ++i) {
      bool bad = P[i] > 1 + Q[i];
      if (is_win(ns) && Q[i] != 0) bad = true;
      if (bad) { nv++; if (out.size() < cap) out.push_back({i, P[i], Q[i], mv, where + "\n" + show(s)}); }
    }
    if (hs > 1 + hn || (is_win(ns) && hn != 0)) { nv++; if (out.size() < cap) out.push_back({7, hs, hn, mv, where + "\n" + show(s)}); }
  }
  return nv;
}

inline int mirror_mv(int mv) { return mv < 2 ? 1 - mv : mv; }  // U <-> D under the top-bottom mirror
