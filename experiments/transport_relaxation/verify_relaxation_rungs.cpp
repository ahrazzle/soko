// verify_relaxation_rungs.cpp
// Standalone C++20 Prover & Empirical Verifier for Room III-14 Transport-Relaxation Rungs:
//   1. Exhaustive 250,000-state BFS check of the Unblocked-Crate Non-Stuttering Law (0 violations / 255,924 stutters)
//   2. Hall vs Intact-Border 9-Flow separation on r30, r33, and r48
#include <bits/stdc++.h>
using namespace std;
using u128 = unsigned __int128;
static constexpr int W = 15, H = 7, N = 105;
static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};
static const char DCH[5] = {'U', 'D', 'L', 'R', 'A'};
static const char* GRID[7] = {
"###############",
"#.............#",
"#.5.}}}.]]]]].#",
"#...}}}.]G.G].#",
"#.D.}}}.]]]]].#",
"#.............#",
"###############"
};
static inline u128 bit(int i) { return ((u128)1) << i; }
static inline bool tst(u128 m, int i) { return (m >> i) & 1; }
struct Dinic {
struct Edge { int to, rev, cap; };
int V;
vector<vector<Edge>> adj;
vector<int> level, ptr;
explicit Dinic(int v) : V(v), adj(v), level(v), ptr(v) {}
void add_edge(int u, int v, int cap) {
 adj[u].push_back({v, (int)adj[v].size(), cap});
 adj[v].push_back({u, (int)adj[u].size() - 1, 0});
}
bool bfs(int s, int t) {
 fill(level.begin(), level.end(), -1);
 queue<int> q; level[s] = 0; q.push(s);
 while (!q.empty()) {
 int u = q.front(); q.pop();
 for (const auto& e : adj[u])
  if (e.cap > 0 && level[e.to] < 0) { level[e.to] = level[u] + 1; q.push(e.to); }
 }
 return level[t] >= 0;
}
int dfs(int u, int t, int pushed) {
 if (pushed == 0 || u == t) return pushed;
 for (int& cid = ptr[u]; cid < (int)adj[u].size(); ++cid) {
 auto& e = adj[u][cid];
 if (level[u] + 1 != level[e.to] || e.cap == 0) continue;
 int tr = dfs(e.to, t, min(pushed, e.cap));
 if (tr == 0) continue;
 e.cap -= tr; adj[e.to][e.rev].cap += tr;
 return tr;
 }
 return 0;
}
int max_flow(int s, int t, int limit = 9) {
 int flow = 0;
 while (flow < limit && bfs(s, t)) {
 fill(ptr.begin(), ptr.end(), 0);
 while (flow < limit) {
  int tr = dfs(s, t, limit - flow);
  if (!tr) break;
  flow += tr;
 }
 }
 return flow;
}
};
struct HeroSchedule { vector<int> bp, dp, ahp, acts; };
int check_9flow(u128 origin_mask, u128 switch_mask, const u128 AURA[N], const HeroSchedule& s, int lm, bool intact_border) {
int total_v = 2 + N + (lm + 1) * N * 2;
Dinic din(total_v);
auto orig_v = [&](int c) { return 2 + c; };
auto in_v = [&](int t, int c) { return 2 + N + (t * N + c) * 2; };
auto out_v = [&](int t, int c) { return 2 + N + (t * N + c) * 2 + 1; };
vector<int> fh(N, 999999);
for (int t = 0; t < lm; ++t) {
 int a = s.acts[t];
 if (a < 4 && s.ahp[t] == 1 && s.dp[t + 1] == s.dp[t]) {
 int tx = (s.dp[t] % W) + DX[a], ty = (s.dp[t] / W) + DY[a];
 if (tx >= 0 && tx < W && ty >= 0 && ty < H && tst(origin_mask, ty * W + tx))
  fh[ty * W + tx] = min(fh[ty * W + tx], t + 1);
 }
}
for (int c = 0; c < N; ++c) if (tst(origin_mask, c) && fh[c] <= lm) din.add_edge(0, orig_v(c), 1);
for (int t = 1; t <= lm; ++t)
 for (int c = 0; c < N; ++c) {
 if (c == s.bp[t] || c == s.dp[t] || (intact_border && tst(origin_mask, c) && t < fh[c])) continue;
 din.add_edge(in_v(t, c), out_v(t, c), 1);
 if (t == lm && tst(switch_mask, c)) din.add_edge(out_v(t, c), 1, 1);
 }
for (int t = 0; t < lm; ++t) {
 int a = s.acts[t];
 if (a < 4 && s.ahp[t] == 1 && s.dp[t + 1] == s.dp[t]) {
 int tx = (s.dp[t] % W) + DX[a], ty = (s.dp[t] / W) + DY[a];
 if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
  int tg = ty * W + tx;
  if (tst(origin_mask, tg)) din.add_edge(orig_v(tg), in_v(t + 1, tg), 1);
 }
 }
 if (t == 0) continue;
 bool bs = (a < 4 && s.ahp[t] == 0 && s.bp[t + 1] != s.bp[t]);
 u128 au = bs ? AURA[s.bp[t]] : 0;
 for (int c = 0; c < N; ++c) {
 din.add_edge(out_v(t, c), in_v(t + 1, c), 1);
 if (bs && tst(au, c)) {
  int nx = (c % W) + DX[a], ny = (c / W) + DY[a];
  if (nx >= 0 && nx < W && ny >= 0 && ny < H) din.add_edge(out_v(t, c), in_v(t + 1, ny * W + nx), 1);
 }
 }
}
return din.max_flow(0, 1, 9);
}
struct CState {
u128 crates, walls, open_pd;
uint8_t bx, by, dx, dy, ah;
bool operator==(const CState& o) const {
 return crates == o.crates && walls == o.walls && open_pd == o.open_pd &&
 bx == o.bx && by == o.by && dx == o.dx && dy == o.dy && ah == o.ah;
}
};
struct CHash {
size_t operator()(const CState& s) const {
 uint64_t h1 = (uint64_t)s.crates ^ ((uint64_t)(s.crates >> 64) * 0x9e3779b97f4a7c15ULL);
 uint64_t h2 = (uint64_t)s.walls  ^ ((uint64_t)(s.walls  >> 64) * 0xbf58476d1ce4e5b9ULL);
 uint64_t h3 = ((uint64_t)s.bx) | ((uint64_t)s.by << 8) | ((uint64_t)s.dx << 16) | ((uint64_t)s.dy << 24) | ((uint64_t)s.ah << 32);
 return (size_t)(h1 ^ (h2 * 0x94d049bb133111ebULL) ^ h3);
}
};
int main() {
u128 origin_mask = 0, switch_mask = 0, pdoor_mask = 0, AURA[N]{}, VALID_PRE_SHIFT[4]{};
vector<int> origins, switches, goals;
int b0 = -1, d0 = -1;
for (int y = 0; y < H; ++y)
 for (int x = 0; x < W; ++x) {
 char c = GRID[y][x]; int i = y * W + x;
 if (c == '#') { origins.push_back(i); origin_mask |= bit(i); }
 else if (c == '}') { switches.push_back(i); switch_mask |= bit(i); }
 else if (c == ']') pdoor_mask |= bit(i);
 else if (c == 'G') goals.push_back(i);
 else if (c == '5') b0 = i;
 else if (c == 'D') d0 = i;
 }
for (int b = 0; b < N; ++b) {
 int bx = b % W, by = b / W;
 for (int y = max(0, by - 2); y <= min(H - 1, by + 2); ++y)
 for (int x = max(0, bx - 2); x <= min(W - 1, bx + 2); ++x)
  AURA[b] |= bit(y * W + x);
}
for (int i = 0; i < N; ++i)
 for (int dir = 0; dir < 4; ++dir) {
 int nx = (i % W) + DX[dir], ny = (i / W) + DY[dir];
 if (nx >= 0 && nx < W && ny >= 0 && ny < H) VALID_PRE_SHIFT[dir] |= bit(i);
 }
auto shift_board = [&](u128 m, int dir) -> u128 {
 m &= VALID_PRE_SHIFT[dir];
 if (dir == 0) return m >> W;
 if (dir == 1) return m << W;
 return (dir == 2) ? (m >> 1) : (m << 1);
};
CState s0{0, origin_mask, 0, (uint8_t)(b0 % W), (uint8_t)(b0 / W), (uint8_t)(d0 % W), (uint8_t)(d0 / W), 1};
auto step_c = [&](const CState& s, int mv, CState& ns, vector<pair<int, int>>& crate_moves) -> bool {
 ns = s; crate_moves.clear();
 u128 closed = pdoor_mask & ~ns.open_pd;
 if (mv == 4) ns.ah = 1 - ns.ah;
 else if (ns.ah == 1) {
 int nx = (int)ns.dx + DX[mv], ny = (int)ns.dy + DY[mv];
 if (nx < 0 || nx >= W || ny < 0 || ny >= H || (nx == ns.bx && ny == ns.by)) return false;
 int ni = ny * W + nx;
 if (tst(closed, ni)) return false;
 if (tst(ns.crates, ni)) { ns.crates &= ~bit(ni); ns.walls |= bit(ni); }
 else if (tst(ns.walls, ni)) { ns.crates |= bit(ni); ns.walls &= ~bit(ni); }
 else { ns.dx = nx; ns.dy = ny; }
 } else {
 int bi = ns.by * W + ns.bx;
 vector<pair<int, int>> c_id;
 u128 m = ns.crates;
 while (m) {
  int c = (uint64_t)m ? __builtin_ctzll((uint64_t)m) : (64 + __builtin_ctzll((uint64_t)(m >> 64)));
  m &= ~bit(c); c_id.push_back({c, c});
 }
 vector<bool> charmed(c_id.size(), false);
 for (size_t k = 0; k < c_id.size(); ++k) charmed[k] = tst(AURA[bi], c_id[k].second);
 bool d_ch = tst(AURA[bi], ns.dy * W + ns.dx), b_mv = false, chg = true;
 while (chg) {
  chg = false;
  for (size_t k = 0; k < c_id.size(); ++k) {
  if (!charmed[k]) continue;
  int c = c_id[k].second, tx = (c % W) + DX[mv], ty = (c / W) + DY[mv], ti = ty * W + tx;
  if (tx >= 0 && tx < W && ty >= 0 && ty < H && !tst(ns.walls | closed | ns.crates, ti) &&
   !(tx == ns.bx && ty == ns.by) && !(tx == ns.dx && ty == ns.dy)) {
   ns.crates &= ~bit(c); ns.crates |= bit(ti); c_id[k].second = ti; charmed[k] = false; chg = true;
  }
  }
  if (d_ch) {
  int tx = (int)ns.dx + DX[mv], ty = (int)ns.dy + DY[mv], ti = ty * W + tx;
  if (tx >= 0 && tx < W && ty >= 0 && ty < H && !tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.bx && ty == ns.by)) {
   ns.dx = tx; ns.dy = ty; d_ch = false; chg = true;
  }
  }
  if (!b_mv) {
  int tx = (int)ns.bx + DX[mv], ty = (int)ns.by + DY[mv], ti = ty * W + tx;
  if (tx >= 0 && tx < W && ty >= 0 && ty < H && !tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.dx && ty == ns.dy)) {
   ns.bx = tx; ns.by = ty; b_mv = true; chg = true;
  }
  }
 }
 if (!b_mv) return false;
 crate_moves = c_id;
 }
 u128 weighing = ns.crates | ns.walls | bit(ns.by * W + ns.bx) | bit(ns.dy * W + ns.dx);
 if ((weighing & switch_mask) == switch_mask) ns.open_pd = pdoor_mask;
 else ns.open_pd &= weighing;
 return true;
};
const string R48 = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
vector<CState> frontier = {s0};
unordered_set<CState, CHash> vis = {s0};
HeroSchedule r48_sched{{b0}, {d0}, {1}, {}};
{
 CState cur = s0, nxt; vector<pair<int, int>> cm;
 for (char ch : R48) {
 int mv = string("UDLRA").find(ch);
 bool ok = step_c(cur, mv, nxt, cm);
 assert(ok);
 r48_sched.acts.push_back(mv);
 r48_sched.bp.push_back(nxt.by * W + nxt.bx);
 r48_sched.dp.push_back(nxt.dy * W + nxt.dx);
 r48_sched.ahp.push_back(nxt.ah);
 if (vis.insert(nxt).second) frontier.push_back(nxt);
 cur = nxt;
 }
}
uint64_t transitions = 0, stutters = 0, violations = 0;
for (size_t qi = 0; qi < frontier.size() && frontier.size() < 250000; ++qi) {
 CState s = frontier[qi], ns; vector<pair<int, int>> cm;
 u128 closed_before = pdoor_mask & ~s.open_pd;
 for (int mv = 0; mv < 5; ++mv) {
 if (!step_c(s, mv, ns, cm)) continue;
 transitions++;
 if (mv < 4 && s.ah == 0 && (ns.bx != s.bx || ns.by != s.by)) {
  int bi = s.by * W + s.bx;
  u128 occ_after = ns.walls | ns.crates | bit(ns.by * W + ns.bx) | bit(ns.dy * W + ns.dx);
  for (auto [c0, c1] : cm) {
  if (tst(AURA[bi], c0) && c1 == c0) {
   stutters++;
   int tx = (c0 % W) + DX[mv], ty = (c0 / W) + DY[mv];
   bool oob = (tx < 0 || tx >= W || ty < 0 || ty >= H);
   int ti = oob ? -1 : (ty * W + tx);
   if (!(oob || tst(closed_before, ti) || tst(occ_after, ti))) violations++;
  }
  }
 }
 if (frontier.size() < 250000 && vis.insert(ns).second) frontier.push_back(ns);
 }
}
cout << "[1. Non-Stuttering Theorem] states=" << frontier.size()
 << " transitions=" << transitions << " stutters=" << stutters
 << " violations=" << violations << "\n";
assert(violations == 0);
auto eval_route = [&](const string& label, const string& route, int lm) {
 struct P { int b, d, ah; HeroSchedule s; unordered_set<int> hv; };
 vector<P> cur = {{b0, d0, 1, {{b0}, {d0}, {1}, {}}, {}}};
 for (char ch : route) {
 int mv = string("UDLRA").find(ch);
 vector<P> nxt;
 for (const auto& p : cur) {
  if ((p.b == goals[0] && p.d == goals[1]) || (p.b == goals[1] && p.d == goals[0])) continue;
  if (mv == 4) {
  auto q = p; q.ah = 1 - q.ah; q.s.acts.push_back(4);
  q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
  } else if (p.ah == 1) {
  int nx = (p.d % W) + DX[mv], ny = (p.d / W) + DY[mv], nc = ny * W + nx;
  if (tst(origin_mask, nc) && !p.hv.count(nc)) {
   auto q = p; q.hv.insert(nc); q.s.acts.push_back(mv);
   q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
  } else if (nx >= 0 && nx < W && ny >= 0 && ny < H && (!tst(origin_mask, nc) || p.hv.count(nc)) && nc != p.b) {
   auto q = p; q.d = nc; q.s.acts.push_back(mv);
   q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
  }
  } else {
  int nbx = (p.b % W) + DX[mv], nby = (p.b / W) + DY[mv], nbc = nby * W + nbx;
  if (nbx >= 0 && nbx < W && nby >= 0 && nby < H && (!tst(origin_mask, nbc) || p.hv.count(nbc))) {
   if (nbc != p.d) {
   auto q = p; q.b = nbc; q.s.acts.push_back(mv);
   q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
   }
   if (tst(AURA[p.b], p.d)) {
   int ndx = (p.d % W) + DX[mv], ndy = (p.d / W) + DY[mv], ndc = ndy * W + ndx;
   if (ndx >= 0 && ndx < W && ndy >= 0 && ndy < H && (!tst(origin_mask, ndc) || p.hv.count(ndc)) && nbc != ndc) {
    auto q = p; q.b = nbc; q.d = ndc; q.s.acts.push_back(mv);
    q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
   }
   }
  }
  }
 }
 cur.swap(nxt);
 }
 int best_hall = 0, best_f_hero = 0, best_f_intact = 0;
 for (const auto& p : cur) {
 if (!((p.b == goals[0] && p.d == goals[1]) || (p.b == goals[1] && p.d == goals[0]))) continue;
 vector<u128> R(40, 0);
 for (int t = 0; t < lm; ++t) {
  int a = p.s.acts[t];
  if (a < 4 && p.s.ahp[t] == 1 && p.s.dp[t + 1] == p.s.dp[t]) {
  int tg = ((p.s.dp[t] / W) + DY[a]) * W + ((p.s.dp[t] % W) + DX[a]);
  for (int o = 0; o < 40; ++o) if (origins[o] == tg) R[o] |= bit(tg);
  } else if (a < 4 && p.s.ahp[t] == 0 && p.s.bp[t + 1] != p.s.bp[t]) {
  for (int o = 0; o < 40; ++o) if (R[o]) R[o] |= shift_board(R[o] & AURA[p.s.bp[t]], a);
  }
 }
 int match_o[40]; fill(match_o, match_o + 40, -1); int m = 0;
 for (int q = 0; q < 9; ++q) {
  bool vis_o[40]{};
  function<bool(int)> dfs = [&](int qq) -> bool {
  int sc = switches[qq];
  for (int o = 0; o < 40; ++o) {
   if (vis_o[o] || !tst(R[o], sc)) continue;
   vis_o[o] = true;
   if (match_o[o] < 0 || dfs(match_o[o])) { match_o[o] = qq; return true; }
  }
  return false;
  };
  if (dfs(q)) m++;
 }
 best_hall = max(best_hall, m);
 best_f_hero = max(best_f_hero, check_9flow(origin_mask, switch_mask, AURA, p.s, lm, false));
 best_f_intact = max(best_f_intact, check_9flow(origin_mask, switch_mask, AURA, p.s, lm, true));
 }
 cout << label << " (H=" << route.size() << ", t_L=" << lm << "): Hall=" << best_hall
 << "/9 | HeroFlow=" << best_f_hero << "/9 | IntactFlow=" << best_f_intact << "/9\n";
};
eval_route("[2. Hall Witness r30]", "LLULULULURURURURUARRRRDDRDRUUR", 29);
eval_route("[3. Disjoint-9-Flow Witness r33]", "LLULULULRURURURURUAUDRRDUDDRRRRUR", 32);
int r48_flow = check_9flow(origin_mask, switch_mask, AURA, r48_sched, 47, true);
cout << "[4. Concrete Incumbent r48] (H=48, t_L=47): IntactFlow=" << r48_flow << "/9\n";
assert(r48_flow == 9);
return 0;
}
