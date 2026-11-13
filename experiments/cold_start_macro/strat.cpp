// Stratified uniform-cost macro search ("cold start": no reference route is read).
// States are expanded in order of exact key cost g. Each state maps to an order-free
// progress cell; at most K states are expanded per cell. Generic for Part III rooms.
#include "macro.hpp"
#include <map>
#include <thread>
#include <atomic>
#include <mutex>

struct Node { uint32_t parent; uint16_t g; string keys; };
static LevelMeta M; static int K = 8; static int NOV = 1; static int FREEDOM = 0; static int RELALL = 0; static int GMAX = 400; static double TLIM = 600; static int MAXN = 30000000;
static vector<int> interior_wall0;

struct Rel : RelevanceFn {
  bool operator()(const LevelMeta& M, const DynState& s, int h, int c) const override {
    if (RELALL || M.flr[c] == 1) return true;
    int x = c % M.w, y = c / M.w;
    for (int d = 0; d < 4; d++) { int nx = x + DX[d], ny = y + DY[d]; if (nx < 0 || ny < 0 || nx >= M.w || ny >= M.h) continue;
      uint8_t o = s.obj[ny * M.w + nx]; if (is_hero(o) && !is_act(o)) return true; }
    for (int i = 0; i < M.n; i++) if (s.obj[i] == 11) { // inactive Bard: cells inside its aura
      if (abs(i % M.w - x) <= 2 && abs(i / M.w - y) <= 2) return true; }
    return false;
  }
};

static inline bool safe_cell(const DynState& s, int c) {
  int x = c % M.w, y = c / M.w;
  for (int d = 0; d < 4; d++) { int nx = x + DX[d], ny = y + DY[d]; if (nx < 0 || ny < 0 || nx >= M.w || ny >= M.h) continue;
    if (s.obj[ny * M.w + nx] == 15) return false; }
  return true;
}

// progress cell: on-goal mask, can-walk-to-goal mask, goblins alive, walls removed, crates count, active hero
static uint64_t cell_of(const DynState& s) {
  int ong = 0, reach = 0, gob = 0, walls = 0, crates = 0, act = 0; uint64_t area = 0;
  for (int i = 0; i < M.n; i++) { uint8_t o = s.obj[i];
    if (o == 15) gob++; else if (o == 13) walls++; else if (o == 14) crates++;
    if (is_act(o)) act = o;
    if (is_hero(o) && M.flr[i] == 1) ong |= 1 << ((o - 1) % 6); }
  for (int i = 0; i < M.n; i++) { uint8_t o = s.obj[i]; if (!is_hero(o)) continue;
    int h = (o - 1) % 6; if (ong >> h & 1) { reach |= 1 << h; continue; }
    static thread_local vector<char> seen; seen.assign(M.n, 0); vector<int> q{i}; seen[i] = 1; bool ok = false;
    for (size_t qi = 0; qi < q.size() && !ok; qi++) { int c = q[qi]; int x = c % M.w, y = c / M.w;
      for (int d = 0; d < 4; d++) { int nx = x + DX[d], ny = y + DY[d]; if (nx < 0 || ny < 0 || nx >= M.w || ny >= M.h) continue;
        int ni = ny * M.w + nx; if (seen[ni] || s.obj[ni]) continue; if (!safe_cell(s, ni)) continue;
        seen[ni] = 1; if (M.flr[ni] == 1) { ok = true; break; } q.push_back(ni); } }
    if (ok) reach |= 1 << h;
    if (FREEDOM) { // walkable-area bucket per hero: 0..3 for <8, <16, <32, >=32 cells
      // finish the flood fill (the loop above may stop early at the first exit)
      for (size_t qi = 0; qi < q.size(); qi++) { int c = q[qi]; int x = c % M.w, y = c / M.w;
        for (int d = 0; d < 4; d++) { int nx = x + DX[d], ny = y + DY[d]; if (nx < 0 || ny < 0 || nx >= M.w || ny >= M.h) continue;
          int ni = ny * M.w + nx; if (seen[ni] || s.obj[ni]) continue; if (!safe_cell(s, ni)) continue; seen[ni] = 1; q.push_back(ni); } }
      int a = (int)q.size(); int b = a < 8 ? 0 : a < 16 ? 1 : a < 32 ? 2 : 3; area |= (uint64_t)b << (2 * h); } }
  int wr = 0; for (int c : interior_wall0) if (s.obj[c] != 13) wr++;
  return (uint64_t)ong | (uint64_t)reach << 6 | (uint64_t)gob << 12 | (uint64_t)min(wr, 31) << 16 | (uint64_t)min(crates, 63) << 21 | (uint64_t)act << 27 | area << 32;
}

struct H128 { uint64_t a, b; bool operator==(const H128& o) const { return a == o.a && b == o.b; } };
struct HH { size_t operator()(const H128& h) const { return h.a ^ (h.b * 0x9e3779b97f4a7c15ULL); } };
static H128 hash_state(const DynState& s) {
  uint64_t a = 1469598103934665603ULL, b = 0x84222325cbf29ce4ULL;
  for (int i = 0; i < M.n; i++) { a = (a ^ s.obj[i]) * 1099511628211ULL; b = (b ^ (s.obj[i] + 0x9e)) * 0x100000001b3ULL; b ^= b >> 29; }
  a ^= s.y_op | (s.p_op << 8);
  return {a, b};
}

int main(int argc, char** argv) {
  for (int i = 1; i < argc; i++) { string a = argv[i];
    if (a == "--K") K = atoi(argv[++i]); else if (a == "--nov") NOV = atoi(argv[++i]); else if (a == "--freedom") FREEDOM = atoi(argv[++i]); else if (a == "--rel-all") RELALL = atoi(argv[++i]); else if (a == "--gmax") GMAX = atoi(argv[++i]);
    else if (a == "--time") TLIM = atof(argv[++i]); else if (a == "--maxn") MAXN = atoi(argv[++i]); }
  int w, h; cin >> w >> h; vector<string> rows(h); for (auto& r : rows) cin >> r;
  auto pr = parse_lv(3, w, h, rows); M = pr.first; DynState s0 = pr.second;
  for (int i = 0; i < M.n; i++) { int x = i % w, y = i / w; if (s0.obj[i] == 13 && x > 0 && y > 0 && x < w - 1 && y < h - 1) interior_wall0.push_back(i); }
  vector<Node> nodes; nodes.reserve(1 << 20);
  vector<vector<pair<uint32_t, vector<uint8_t>>>> bucket(GMAX + 1);
  unordered_map<H128, uint16_t, HH> best; unordered_map<uint64_t, int> expanded; unordered_map<uint64_t, vector<uint8_t>> atoms;
  auto pack = [&](const DynState& s) { vector<uint8_t> v(s.obj, s.obj + M.n); v.push_back(s.y_op); v.push_back(s.p_op); return v; };
  auto unpack = [&](const vector<uint8_t>& v) { DynState s{}; memcpy(s.obj, v.data(), M.n); s.y_op = v[M.n]; s.p_op = v[M.n + 1]; comp_notes(M, s); return s; };
  nodes.push_back({UINT32_MAX, 0, ""}); bucket[0].push_back({0, pack(s0)}); best[hash_state(s0)] = 0;
  Rel rel; auto t0 = chrono::steady_clock::now(); long nexp = 0, ngen = 0, cells_full_skips = 0;
  for (int g = 0; g <= GMAX; g++) {
    // expand states at cost g in order of insertion
    for (size_t bi = 0; bi < bucket[g].size(); bi++) {
      auto [id, pv] = bucket[g][bi]; DynState s = unpack(pv);
      H128 hs = hash_state(s); auto it = best.find(hs); if (it != best.end() && it->second < g) continue;
      uint64_t c = cell_of(s); int& ce = expanded[c];
      bool novel = false;
      if (NOV) { auto& bits = atoms[c]; if (bits.empty()) bits.assign((size_t)M.n * 16, 0);
        for (int i = 0; i < M.n; i++) { uint8_t o = s.obj[i]; if (!o) continue; size_t a = (size_t)i * 16 + (o > 15 ? 15 : o);
          if (!bits[a]) { bits[a] = 1; novel = true; } } }
      if (ce >= K && !novel) { cells_full_skips++; continue; } ce++;
      nexp++;
      vector<Macro> ms; gen_macros(M, s, 63, &rel, ms);
      for (auto& m : ms) {
        int ng = g + m.cost; if (ng > GMAX) continue;
        bool win = check_win(M, m.s);
        H128 hm = hash_state(m.s); auto bt = best.find(hm); if (bt != best.end() && bt->second <= ng) continue; best[hm] = ng;
        nodes.push_back({id, (uint16_t)ng, m.keys}); ngen++;
        if (win) {
          string r; for (uint32_t x = nodes.size() - 1; x != UINT32_MAX; x = nodes[x].parent) r = nodes[x].keys + r;
          printf("WIN cost=%d len=%zu expanded=%ld generated=%ld t=%.1fs\nROUTE %s\n", ng, r.size(), nexp, ngen,
            chrono::duration<double>(chrono::steady_clock::now() - t0).count(), r.c_str()); fflush(stdout);
          GMAX = min(GMAX, ng - 1); // keep searching for strictly cheaper wins
          continue;
        }
        bucket[ng].push_back({(uint32_t)nodes.size() - 1, pack(m.s)});
      }
      if ((int)nodes.size() > MAXN || chrono::duration<double>(chrono::steady_clock::now() - t0).count() > TLIM) {
        printf("STOP g=%d expanded=%ld generated=%ld cells=%zu skips=%ld\n", g, nexp, ngen, expanded.size(), cells_full_skips); return 0; }
    }
    vector<pair<uint32_t, vector<uint8_t>>>().swap(bucket[g]);
    if (g % 10 == 0) { fprintf(stderr, "g=%d exp=%ld gen=%ld cells=%zu t=%.1f\n", g, nexp, ngen, expanded.size(), chrono::duration<double>(chrono::steady_clock::now() - t0).count()); }
  }
  printf("EXHAUSTED gmax=%d expanded=%ld generated=%ld cells=%zu skips=%ld\n", GMAX, nexp, ngen, expanded.size(), cells_full_skips);
}
