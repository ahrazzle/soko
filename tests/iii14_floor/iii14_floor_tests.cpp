// Regression tests for the 15x7 III-14 floor prover and its heuristic (eval_h).
//   iii14_floor_tests all        run every PDB-based test below (builds the five tables once)
//   iii14_floor_tests route      read routes on stdin, print step_concrete's state after each key (no tables;
//                                used by the oracle parity test in tests/test_iii14_floor_regression.py)
// Tests: edges (a), exact (b), reflection (c), v14 (d). All counts and seeds are fixed.
// Exit status is the number of failed tests. Each test prints one "[PASS]" or "[FAIL]" line.
#include "harness.hpp"
#include <atomic>
#include <mutex>

static const string R48 = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
// The 48-key witness from the closed PR #41 (reported there as a 48-key route). It differs from R48.
static const string W41 = "LLULULUULRRURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";

static int failures = 0;
static double secs_since(chrono::steady_clock::time_point t0) { return chrono::duration<double>(chrono::steady_clock::now() - t0).count(); }
static void verdict(const string& name, bool ok, const string& detail, chrono::steady_clock::time_point t0) {
  cout << (ok ? "[PASS] " : "[FAIL] ") << name << ": " << detail << " (" << fixed << setprecision(1) << secs_since(t0) << "s)\n";
  if (!ok) failures++;
}
static const int NT = 10;

template <class F> void parallel_for(size_t n, F f) {  // f(i, thread)
  vector<thread> th;
  for (int t = 0; t < NT; ++t) th.emplace_back([&, t]() { for (size_t i = t; i < n; i += NT) f(i, t); });
  for (auto& x : th) x.join();
}

// Seeded walk off an R48 prefix: prefix length 0..48, then random legal moves that do not win.
static vector<CState> walk_states(uint64_t seed, int len, string* path = nullptr) {
  mt19937_64 rng(seed);
  int pre = (int)(rng() % 49);
  CState s = replay(R48.substr(0, pre));
  vector<CState> out{s};
  for (int k = 0; k < len; ++k) {
    int ok[5], n = 0; CState nx[5];
    for (int mv = 0; mv < 5; ++mv) if (step_concrete(s, mv, nx[mv]) && !is_win(nx[mv])) ok[n++] = mv;
    if (!n) break;
    int mv = ok[rng() % n]; s = nx[mv]; out.push_back(s);
  }
  if (path) *path = "R48[:" + to_string(pre) + "] + seeded walk " + to_string(seed);
  return out;
}

// Random states that satisfy the game's invariants but need not be reachable from s0: crates plus walls
// come only from origin walls, doors_open matches the weighed switches, nothing sits on a closed door cell,
// and heroes stand on free cells. Returns false if the draw is rejected.
static bool fuzz_state(mt19937_64& rng, CState& out) {
  vector<int> origin, interior;
  for (int i = 0; i < N; ++i) (IS_ORIG[i] ? origin : interior).push_back(i);
  CState s{}; s.walls = ORIGIN_MASK; s.crates = 0;
  int m = rng() % 30;
  vector<int> miss; for (int j = 0; j < m; ++j) { int c = origin[rng() % origin.size()]; if (tst(s.walls, c)) { s.walls &= ~bit(c); miss.push_back(c); } }
  int nobj = miss.empty() ? 0 : (int)(rng() % (miss.size() + 1));
  bool fill_sw = (rng() % 3 == 0);
  int placed = 0;
  bool fill_all = fill_sw && (rng() & 1);
  if (fill_all) nobj = max(nobj, min((int)miss.size(), 9));
  if (fill_sw) for (int c = 0; c < N && placed < nobj; ++c) if (IS_SW[c] && (fill_all || rng() % 10 < 8)) { if (rng() % 4) s.crates |= bit(c); else s.walls |= bit(c); placed++; }
  for (int tries = 0; placed < nobj && tries < 400; ++tries) {
    int c; int mode = rng() % 4;
    if (mode == 0 && !miss.empty()) c = miss[rng() % miss.size()];
    else if (mode == 1) { int x = 2 + rng() % 7, y = 1 + rng() % 5; c = y * W + x; }
    else c = interior[rng() % interior.size()];
    if (tst(s.crates | s.walls, c)) continue;
    if (IS_ORIG[c] || rng() % 4) s.crates |= bit(c); else s.walls |= bit(c);
    placed++;
  }
  auto free_cell = [&](int avoid) { for (;;) { int c = (rng() % 3 == 0) ? (rng() % N) : ((1 + rng() % 5) * W + 1 + rng() % 13);
    if (c != avoid && !tst(s.crates | s.walls, c)) return c; } };
  int b = free_cell(-1), d = free_cell(b);
  if (rng() % 3 == 0) { int x = 2 + rng() % 7, y = 1 + rng() % 5; int c = y * W + x; if (c != b && !tst(s.crates | s.walls, c)) d = c; }
  if (fill_all && rng() % 2) { for (int r = 0; r < 2; ++r) { int x = 7 + rng() % 7, y = 1 + rng() % 5; int c = y * W + x; if (!tst(s.crates | s.walls, c) && c != (r ? b : d)) { if (r) d = c; else b = c; } } }
  s.bx = b % W; s.by = b / W; s.dx = d % W; s.dy = d / W; s.ah = rng() & 1;
  u128 weighing = s.crates | s.walls | bit(b) | bit(d);
  s.doors_open = ((weighing & SWITCH_MASK) == SWITCH_MASK);
  if (!s.doors_open) {
    if (IS_PD[b] || IS_PD[d]) return false;
    s.crates &= ~PDOOR_MASK; s.walls &= ~PDOOR_MASK;
  }
  out = s; return true;
}

// ---------------------------------------------------------------------------------------------
// (a) Edge consistency: L(s) <= 1 + L(s') on every edge for the seven lookups and eval_h, L = 0 at wins.
static void test_edges() {
  auto t0 = chrono::steady_clock::now();
  const int BALL_DEPTH = 14, NWALKS = 600, WALK_LEN = 60, NFUZZ = 100000;
  uint64_t tot_states = 0, tot_edges = 0, tot_viol = 0; string first;
  auto run = [&](const string& name, size_t n, const function<CState(size_t)>& get) {
    vector<vector<Viol>> vv(NT); vector<uint64_t> ne(NT, 0), nv(NT, 0);
    parallel_for(n, [&](size_t i, int t) { nv[t] += check_edges(get(i), vv[t], 2, ne[t], name); });
    uint64_t e = 0, v = 0; for (int t = 0; t < NT; ++t) { e += ne[t]; v += nv[t]; if (first.empty() && !vv[t].empty()) {
      auto& x = vv[t][0]; first = string("lookup ") + PART_NAMES[x.part] + " h(s)=" + to_string(x.hs) + " h(s')=" + to_string(x.hn) + " move=" + "UDLRA"[x.mv] + "\n" + x.where; } }
    tot_states += n; tot_edges += e; tot_viol += v;
    verdict("edges/" + name, v == 0, to_string(n) + " states, " + to_string(e) + " edges, " + to_string(v) + " violations", t0);
    t0 = chrono::steady_clock::now();
  };
  Bfs ball = bfs(start_state(), BALL_DEPTH);
  run("ball_depth_" + to_string(BALL_DEPTH), ball.states.size(), [&](size_t i) { return ball.states[i]; });
  vector<CState> ws; for (int w = 0; w < NWALKS; ++w) { auto v = walk_states(1000 + w, WALK_LEN); ws.insert(ws.end(), v.begin(), v.end()); }
  run("walks_off_R48_prefixes", ws.size(), [&](size_t i) { return ws[i]; });
  vector<CState> fz; { mt19937_64 rng(7919); while ((int)fz.size() < NFUZZ) { CState s; if (fuzz_state(rng, s)) fz.push_back(s); } }
  run("invariant_fuzz", fz.size(), [&](size_t i) { return fz[i]; });
  if (tot_viol) cout << "first violation: " << first << "\n";
}

// ---------------------------------------------------------------------------------------------
// (b) R48 tail: exact BFS distance d*(s_t) = 48 - t for t = 34..48, and every lookup on both orientations <= d*.
static void test_exact() {
  auto t0 = chrono::steady_clock::now();
  bool ok = true; string detail;
  for (int t = 34; t <= 48; ++t) {
    CState s = replay(R48.substr(0, t));
    Bfs b = bfs(s, 48 - t);
    int want = 48 - t, hmax = 0;
    CState ms = mirror_y_state(s);
    auto a = parts(s), m = parts(ms);
    hmax = max(hmax, (int)eval_h(s)); hmax = max(hmax, (int)eval_h(ms));
    for (int j = 0; j < 7; ++j) hmax = max({hmax, a[j], m[j]});
    bool good = (b.firstwin == want) && hmax <= b.firstwin;
    if (!good) { ok = false; detail += " t=" + to_string(t) + ": bfs d*=" + to_string(b.firstwin) + " want " + to_string(want) + " max lookup " + to_string(hmax) + ";"; }
  }
  verdict("exact/R48_tail_t34_48", ok, ok ? "d*(s_t)=48-t for t=34..48 and every lookup (both orientations) <= d*" : detail, t0);
}

// ---------------------------------------------------------------------------------------------
// (c) Reflection: step_concrete commutes with the top-bottom mirror, and rf5's row-3 Bard entries are symmetric.
static void test_reflection() {
  auto t0 = chrono::steady_clock::now();
  vector<CState> sts;
  for (int w = 0; w < 300; ++w) { auto v = walk_states(5000 + w, 60); sts.insert(sts.end(), v.begin(), v.end()); }
  { mt19937_64 rng(31337); size_t base = sts.size(); while (sts.size() < base + 20000) { CState s; if (fuzz_state(rng, s)) sts.push_back(s); } }
  atomic<uint64_t> checks{0}, bad{0}; string first; mutex mu;
  parallel_for(sts.size(), [&](size_t i, int) {
    const CState& s = sts[i]; CState ms = mirror_y_state(s);
    for (int mv = 0; mv < 5; ++mv) {
      CState r1, r2; bool o1 = step_concrete(s, mv, r1), o2 = step_concrete(ms, mirror_mv(mv), r2);
      checks++;
      if (o1 != o2 || (o1 && !state_eq(mirror_y_state(r1), r2))) { bad++; lock_guard<mutex> g(mu); if (first.empty()) first = show(s) + "key " + "UDLRA"[mv]; }
    }
  });
  verdict("reflection/step_commutes_with_mirror", bad == 0, to_string(sts.size()) + " seeded states, " + to_string(checks.load()) + " (state, key) pairs, " + to_string(bad.load()) + " mismatches" + (bad ? "\n" + first : ""), t0);

  t0 = chrono::steady_clock::now();
  auto& P = pdb_rf5; uint64_t rc = 0, mism = 0;
  for (int rt = 0; rt < P.NR; ++rt)
    for (int di = 0; di < N; ++di)
      for (int adj = 0; adj <= P.max_adj[di]; ++adj)
        for (int bx = 0; bx < W; ++bx)
          for (int ah = 0; ah < 2; ++ah) {
            int bi = 3 * W + bx, mdi = mirror_y_cell(di);
            if (P.da_id[mdi][adj] < 0) { mism++; continue; }
            uint8_t a = P.dist[P.encode(rt, P.da_id[di][adj], bi, ah)], b = P.dist[P.encode(rt, P.da_id[mdi][adj], bi, ah)];
            rc++; if (a != b) mism++;
          }
  verdict("reflection/rf5_row3_bard_symmetric", mism == 0, to_string(rc) + " entries compared, " + to_string(mism) + " mismatches", t0);
}

// ---------------------------------------------------------------------------------------------
// (d) Known-answer states from the closed PR #41 (the v14 heuristic), replayed under main's rules.
// v14 reported h = 3 at the end of CE1 and CE2, with d* = 2 under its own rules (RR and LL win). This test
// replays the same key strings under main's step_concrete, computes d* by BFS, and checks eval_h <= d*.
static void report_state(const string& label, const CState& s, int d) {
  auto a = parts(s); auto m = parts(mirror_y_state(s));
  cout << "  " << label << ": d*=" << d << " eval_h=" << (int)eval_h(s) << " lookups(s)=";
  for (int j = 0; j < 7; ++j) cout << a[j] << (j < 6 ? "," : ""); cout << " lookups(mirror)=";
  for (int j = 0; j < 7; ++j) cout << m[j] << (j < 6 ? "," : ""); cout << "\n" << show(s);
}
static void test_v14() {
  auto t0 = chrono::steady_clock::now();
  {
    bool ok; int at = -1; CState e = replay(W41, &ok, &at);
    cout << "  W41 == R48: " << (W41 == R48 ? "yes" : "no") << "\n";
    verdict("v14/witness_replays_to_win_under_main", ok && is_win(e), string("48-key witness from PR #41: ") + (ok ? "all keys accepted" : "rejected at key " + to_string(at)) + ", win=" + (ok && is_win(e) ? "yes" : "no"), t0);
  }
  struct CE { const char* name; string prefix, finish; };
  CE ces[2] = {{"CE1", W41.substr(0, 38) + "DRDARURDUUL", "RR"}, {"CE2", W41.substr(0, 42) + "URURARURR", "LL"}};
  for (auto& ce : ces) {
    t0 = chrono::steady_clock::now();
    bool ok; int at = -1; CState s = replay(ce.prefix, &ok, &at);
    if (!ok) { verdict(string("v14/") + ce.name, true, "DIVERGES under main's rules: key " + to_string(at + 1) + " of " + to_string(ce.prefix.size()) + " (" + ce.prefix[at] + ") is rejected by step_concrete; no state to compare", t0); continue; }
    Bfs b = bfs(s, 14); int d = b.firstwin;
    // the key string the v14 audit used to finish
    bool okf; CState fin = replay(s, ce.finish, &okf);
    report_state(string(ce.name) + " prefix state (" + to_string(ce.prefix.size()) + " keys)", s, d);
    cout << "  " << ce.name << " finish " << ce.finish << " under main: " << (okf ? (is_win(fin) ? "wins" : "accepted, not a win") : "rejected") << "\n";
    bool good = (d >= 0) && (int)eval_h(s) <= d;
    CState ms = mirror_y_state(s); auto a = parts(s), m = parts(ms);
    for (int j = 0; j < 7; ++j) good = good && a[j] <= d && m[j] <= d;
    verdict(string("v14/") + ce.name, good, "replays under main (" + to_string(ce.prefix.size()) + " keys accepted), d*=" + (d >= 0 ? to_string(d) : string(">14")) + ", eval_h=" + to_string((int)eval_h(s)) + (good ? ", eval_h <= d*" : ", ADMISSIBILITY FAILS"), t0);
  }
}

// ---------------------------------------------------------------------------------------------
// route mode: for each route on stdin, print one line per key: "ok <crates> <walls> bx by dx dy ah doors" or "rej".
// A rejected key ends the route (step_concrete returns false for a blocked Bard move, a blocked Druid move
// and a crush alike).
static string u128hex(u128 v) { char buf[40]; snprintf(buf, sizeof buf, "%016llx%016llx", (unsigned long long)(v >> 64), (unsigned long long)v); return buf; }
static void route_mode() {
  string line;
  while (getline(cin, line)) {
    CState cur = start_state();
    cout << "start " << u128hex(cur.crates) << " " << u128hex(cur.walls) << " " << (int)cur.bx << " " << (int)cur.by << " " << (int)cur.dx << " " << (int)cur.dy << " " << (int)cur.ah << " " << (int)cur.doors_open << "\n";
    for (char ch : line) {
      CState nx; size_t mv = string("UDLRA").find(ch);
      if (mv == string::npos || !step_concrete(cur, (int)mv, nx)) { cout << "rej\n"; break; }
      cur = nx;
      cout << "ok " << u128hex(cur.crates) << " " << u128hex(cur.walls) << " " << (int)cur.bx << " " << (int)cur.by << " " << (int)cur.dx << " " << (int)cur.dy << " " << (int)cur.ah << " " << (int)cur.doors_open << "\n";
    }
    cout << "end\n";
  }
}

int main(int argc, char** argv) {
  cout << unitbuf;
  string mode = argc > 1 ? argv[1] : "all";
  init_globals();
  if (mode == "route") { route_mode(); return 0; }
  auto t0 = chrono::steady_clock::now();
  build_all();
  cout << "tables built in " << fixed << setprecision(1) << secs_since(t0) << "s\n";
  // Sanity: the setup above matches the prover (start state, the R48 route and the h at both ends).
  {
    bool ok; CState e = replay(R48, &ok);
    verdict("setup/R48_replays_to_win_and_h_is_zero_at_win", ok && is_win(e) && eval_h(e) == 0, "R48 is the prover's route; eval_h(s0)=" + to_string((int)eval_h(start_state())), chrono::steady_clock::now());
    bool bad34 = false; { bool ok2; int at; replay("LULULUULRURRURURUALDRRUDRRUDDRURRR", &ok2, &at); bad34 = !ok2 && at == 29; }
    verdict("setup/sticky_door_34_route_rejected_at_step_30", bad34, "same negative control as the prover", chrono::steady_clock::now());
  }
  test_edges(); test_exact(); test_reflection(); test_v14();
  cout << "failures=" << failures << " total_wall=" << fixed << setprecision(1) << secs_since(t0) << "s\n";
  return failures;
}
