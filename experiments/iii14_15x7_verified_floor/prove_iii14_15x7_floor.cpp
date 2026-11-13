// prove_iii14_15x7_floor.cpp
// Reproducible C++20 collision-free lower-bound prover for True 15x7 Room III-14
// (Part III SHA-256: f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0).
// Compile:
//   g++ -O3 -march=native -std=c++20 -pthread prove_iii14_15x7_floor.cpp -o prove_iii14_15x7_floor
// Run:
//   ./prove_iii14_15x7_floor 90.0

#include "iii14_15x7_core.hpp"
#include "iii14_ringflow5_pdb.hpp"
#include "iii14_harvest_pdb.hpp"
#include "iii14_rowstrip_pdb.hpp"
#include "iii14_gateway67_pdb.hpp"

struct CandEdge {
  Packed15 np;
  CState ns;
  uint8_t hs, ng;
};

int main(int argc, char** argv) {
  cout << unitbuf;
  double time_limit = (argc > 1) ? atof(argv[1]) : 90.0;
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

  CState s0{0, ORIGIN_MASK, (uint8_t)(B0 % W), (uint8_t)(B0 / W), (uint8_t)(D0 % W), (uint8_t)(D0 / W), 1, 0};

  // Negative test: verify the invalid 34-step sticky-door route is REJECTED by exact crush semantics at step 30!
  {
    const string BAD34 = "LULULUULRURRURURUALDRRUDRRUDDRURRR";
    CState cur = s0;
    int steps_ok = 0;
    for (char ch : BAD34) {
      CState nxt;
      if (!step_concrete(cur, string("UDLRA").find(ch), nxt)) break;
      cur = nxt; steps_ok++;
    }
    assert(steps_ok == 29); // 0-indexed move #29 (30th step) crushes Druid on PDOOR_MASK, matching oracle.py!
    cout << "[PASS] Sticky-door 34-step false route rejected at step 30 (hero crushed on closing purple door)!\n";
  }

  RingFlow5_15PDB pdb_rf5;
  HarvestAdj15PDB pdb_ha;
  RowStrip15PDB pdb_r2, pdb_r3;
  Gateway67_15PDB pdb_gw;
  thread tb1([&]() { pdb_rf5.build(); pdb_r2.build(2); pdb_r3.build(3); });
  thread tb2([&]() { pdb_gw.build(); pdb_ha.build(); });
  tb1.join(); tb2.join();

  auto eval_h = [&](const CState& s) -> uint8_t {
    CState ms = mirror_y_state(s);
    int h = max({pdb_rf5.lookup(s), pdb_ha.lookup(s), pdb_ha.lookup(ms),
          pdb_gw.lookup(s), pdb_r2.lookup(s), pdb_r2.lookup(ms), pdb_r3.lookup(s)});
    return (uint8_t)min(250, h);
  };

  cout << "Root bounds at s0 (True 15x7 Exact Crush): rf5=" << pdb_rf5.lookup(s0)
    << " ha=" << max(pdb_ha.lookup(s0), pdb_ha.lookup(mirror_y_state(s0)))
    << " r2=" << max(pdb_r2.lookup(s0), pdb_r2.lookup(mirror_y_state(s0)))
    << " r3=" << pdb_r3.lookup(s0)
    << " => combined h(s0) = " << (int)eval_h(s0) << "\n";

  const string R48 = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
  {
    CState cur = s0;
    cout << "r48 trace (t:g+h[rf5,ha,gw,r3]): ";
    for (int t = 0; t < (int)R48.size(); ++t) {
      int ht = eval_h(cur);
      if (t % 4 == 0) {
        CState ms = mirror_y_state(cur);
        cout << t << ":" << (t + ht) << "[" << pdb_rf5.lookup(cur) << ","
          << max(pdb_ha.lookup(cur), pdb_ha.lookup(ms)) << ","
          << pdb_gw.lookup(cur) << "," << pdb_r3.lookup(cur) << "] ";
      }
      assert(t + ht <= 48);
      CState nxt; assert(step_concrete(cur, string("UDLRA").find(R48[t]), nxt));
      if (ht > 1 + (int)eval_h(nxt)) {
        cerr << "\nr48 BELLMAN VIOLATION at t=" << t << ": ht=" << ht << " hnxt=" << (int)eval_h(nxt) << "\n";
        return 2;
      }
      cur = nxt;
    }
    assert(is_win(cur) && eval_h(cur) == 0);
    cout << "\n[PASS] r48 48-step admissibility & step-consistency audit (0 violations)!\n";
  }

  auto t_astar = chrono::steady_clock::now();
  constexpr size_t MAX_STATES = 152000000;
  constexpr size_t HASH_BITS = 28;
  vector<Packed15> states; states.reserve(MAX_STATES);
  vector<uint8_t> best_g, state_h; best_g.reserve(MAX_STATES); state_h.reserve(MAX_STATES);
    vector<uint32_t> htab(1ULL << HASH_BITS, UINT32_MAX);
  size_t hmask = (1ULL << HASH_BITS) - 1;

  vector<vector<uint32_t>> waves[60];
  for (int f = 0; f < 60; ++f) waves[f].resize(60);

  Packed15 p0 = pack_canon(s0);
  uint8_t h0 = eval_h(s0);
  states.push_back(p0); best_g.push_back(0); state_h.push_back(h0); 
  htab[p0.hash64() & hmask] = 0;
  waves[h0][0].push_back(0);

  uint64_t expanded = 0, edge_checks = 0, hash_collisions_prevented = 0, bellman_violations = 0;
  int proven_floor = h0;
  bool hit_cap = false;

  vector<CandEdge> tbuf[2];
  tbuf[0].reserve(2000000); tbuf[1].reserve(2000000);

  for (int f = h0; f <= 48 && !hit_cap; ++f) {
    proven_floor = f;
    for (int g = 0; g <= f && !hit_cap; ++g) {
      auto& wvec = waves[f][g];
      if (wvec.empty()) continue;
      vector<uint32_t> active; active.reserve(wvec.size());
      for (uint32_t uid : wvec)
        if (best_g[uid] == g && (int)g + (int)state_h[uid] == f) active.push_back(uid);
      vector<uint32_t>().swap(wvec);
      if (active.empty()) continue;

      const size_t CHUNK = 400000;
      for (size_t base = 0; base < active.size() && !hit_cap; base += CHUNK) {
        if (chrono::duration<double>(chrono::steady_clock::now() - t_astar).count() > time_limit ||
          states.size() >= MAX_STATES - 2500000) { hit_cap = true; break; }
        size_t cnt = min(CHUNK, active.size() - base), mid = cnt / 2;
        tbuf[0].clear(); tbuf[1].clear();
        atomic<bool> found_win{false};
        atomic<uint32_t> win_puid{UINT32_MAX};

        auto worker_expand = [&](int tid, size_t l, size_t r) {
          auto& out = tbuf[tid];
          for (size_t idx = l; idx < r; ++idx) {
            uint32_t uid = active[base + idx];
            uint8_t hs = state_h[uid];
            CState s = unpack15(states[uid]);
            for (int mv = 0; mv < 5; ++mv) {
              CState ns;
              if (!step_concrete(s, mv, ns)) continue;
              if (is_win(ns)) {
                uint32_t exp = UINT32_MAX;
                win_puid.compare_exchange_strong(exp, uid);
                found_win.store(true);
                return;
              }
              out.push_back(CandEdge{pack_canon(ns), ns, hs, (uint8_t)(g + 1)});
            }
          }
        };
        if (cnt >= 1024) { thread w0(worker_expand, 0, 0, mid); worker_expand(1, mid, cnt); w0.join(); }
        else worker_expand(0, 0, cnt);

        if (found_win.load()) { cout << "[EXACT OPTIMUM REACHED AT g=" << (g + 1) << "]\n"; proven_floor = g + 1; hit_cap = true; break; }

        expanded += cnt;
        size_t n0 = tbuf[0].size(), n1 = tbuf[1].size(), ntot = n0 + n1;
        edge_checks += ntot;
        vector<uint32_t> found_eid(ntot, UINT32_MAX);
        vector<uint8_t> cand_h(ntot, 0);
        uint64_t col_part[2] = {0, 0};

        auto worker_eval = [&](int tid, size_t l, size_t r) {
          uint64_t local_col = 0;
          for (size_t i = l; i < r; ++i) {
            const CandEdge& ce = (i < n0) ? tbuf[0][i] : tbuf[1][i - n0];
            size_t sl = ce.np.hash64() & hmask;
            uint32_t eid = UINT32_MAX;
            while (htab[sl] != UINT32_MAX) {
              uint32_t cand = htab[sl];
              if (states[cand] == ce.np) { eid = cand; break; }
              local_col++;
              sl = (sl + 1) & hmask;
            }
            found_eid[i] = eid;
            cand_h[i] = (eid != UINT32_MAX) ? state_h[eid] : eval_h(ce.ns);
          }
          col_part[tid] = local_col;
        };
        size_t emid = ntot / 2;
        if (ntot >= 1024) { thread e0(worker_eval, 0, 0, emid); worker_eval(1, emid, ntot); e0.join(); }
        else worker_eval(0, 0, ntot);
        hash_collisions_prevented += col_part[0] + col_part[1];

        for (size_t i = 0; i < ntot; ++i) {
          const CandEdge& ce = (i < n0) ? tbuf[0][i] : tbuf[1][i - n0];
          uint8_t hns = cand_h[i];
          if ((int)ce.hs > 1 + (int)hns) {
            bellman_violations++;
            cerr << "BELLMAN VIOLATION at g=" << g << ": hs=" << (int)ce.hs << " hns=" << (int)hns
              << " | rf5:" << pdb_rf5.lookup(ce.ns)
              << " | ha:" << max(pdb_ha.lookup(ce.ns), pdb_ha.lookup(mirror_y_state(ce.ns)))
              << " | r3:" << pdb_r3.lookup(ce.ns) << "\n";
            return 2;
          }
          int nf = (int)ce.ng + (int)hns;
          if (nf > 48) continue;
          uint32_t eid = found_eid[i];
          if (eid != UINT32_MAX) {
            if (ce.ng < best_g[eid]) { best_g[eid] = ce.ng; waves[nf][ce.ng].push_back(eid); }
          } else {
            size_t sl = ce.np.hash64() & hmask;
            while (htab[sl] != UINT32_MAX) {
              uint32_t cand = htab[sl];
              if (states[cand] == ce.np) { eid = cand; break; }
              hash_collisions_prevented++;
              sl = (sl + 1) & hmask;
            }
            if (eid != UINT32_MAX) {
              if (ce.ng < best_g[eid]) { best_g[eid] = ce.ng; waves[nf][ce.ng].push_back(eid); }
            } else {
              uint32_t nid = (uint32_t)states.size();
              states.push_back(ce.np); best_g.push_back(ce.ng); state_h.push_back(hns); 
              htab[sl] = nid; waves[nf][ce.ng].push_back(nid);
            }
          }
        }
      }
    }
    if (!hit_cap) {
      double el = chrono::duration<double>(chrono::steady_clock::now() - t_astar).count();
      cout << "  [CERTIFIED TRUE 15x7 FLOOR >= " << (f + 1) << "] expanded=" << expanded
        << " unique_canon_states=" << states.size() << " edges_checked=" << edge_checks
        << " collisions_prevented=" << hash_collisions_prevented
        << " time=" << fixed << setprecision(2) << el << "s\n";
      proven_floor = f + 1;
    }
  }
  double total_el = chrono::duration<double>(chrono::steady_clock::now() - t_astar).count();
  cout << "FINAL VERIFIED TRUE 15x7 III-14 FLOOR >= " << proven_floor
    << " | expanded=" << expanded << " | unique_canon_states=" << states.size()
    << " | edges_verified=" << edge_checks << " | bellman_violations=" << bellman_violations
    << " | hash_collisions_prevented=" << hash_collisions_prevented
    << " | time=" << fixed << setprecision(2) << total_el << "s\n";
  return 0;
}
