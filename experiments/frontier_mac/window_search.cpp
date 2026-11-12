#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <queue>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
using namespace std;

static constexpr int MAX_C = 512;
static const int DX[4] = {0, 0, -1, 1}, DY[4] = {-1, 1, 0, 0};
static const char DCH[5] = {'U', 'D', 'L', 'R', 'A'};
inline int d_idx(char c) { return c=='U'?0:c=='D'?1:c=='L'?2:c=='R'?3:c=='A'?4:-1; }

struct LevelMeta {
  int part = 3, w = 0, h = 0, n = 0, max_h = 6;
  uint8_t flr[MAX_C] = {}, near_g[MAX_C] = {};
  vector<int> goals, y_sw, p_sw, y_dr, p_dr;
  bool has_bard = false;
};

struct DynState {
  uint8_t obj[MAX_C];
  uint64_t notes[8];
  uint8_t y_op = 0, p_op = 0;
  inline bool has_n(int i) const { return (notes[i >> 6] >> (i & 63)) & 1ULL; }
  inline void set_n(int i) { notes[i >> 6] |= (1ULL << (i & 63)); }
  inline void clr_n() { memset(notes, 0, sizeof(notes)); }
  bool eq(const DynState& o, int n, bool cn) const {
    return y_op == o.y_op && p_op == o.p_op && !memcmp(obj, o.obj, n) && (!cn || !memcmp(notes, o.notes, sizeof(notes)));
  }
  uint64_t hash64(int n, bool cn) const {
    uint64_t h = 1469598103934665603ULL;
    const uint64_t* p = reinterpret_cast<const uint64_t*>(obj);
    for (int i = 0; i < (n >> 3); ++i) { h ^= p[i] + 0x9e3779b97f4a7c15ULL; h *= 1099511628211ULL; }
    for (int i = (n >> 3) << 3; i < n; ++i) { h ^= obj[i]; h *= 1099511628211ULL; }
    h = (h ^ (((uint64_t)y_op << 8) | p_op)) * 1099511628211ULL;
    if (cn) for (int i = 0; i < ((n + 63) >> 6); ++i) if (notes[i]) h = (h ^ (notes[i] + i)) * 1099511628211ULL;
    return h ^ (h >> 31);
  }
};

inline bool is_act(uint8_t v) { return v >= 1 && v <= 6; }
inline bool is_inact(uint8_t v) { return v >= 7 && v <= 12; }
inline bool is_hero(uint8_t v) { return v >= 1 && v <= 12; }
inline bool is_heal(uint8_t v) { return v == 4 || v == 10; }
inline bool is_mon(int p, uint8_t v) { return p == 1 ? false : (p == 2 ? (v >= 15 && v <= 17) : v == 15); }
inline bool is_mov(int p, uint8_t v) { return v == 14 || is_inact(v) || is_mon(p, v); }
inline bool is_stat(uint8_t v) { return v == 13 || v >= 18; }
inline bool is_vuln(int p, uint8_t v) { return is_hero(v) || is_mon(p, v); }
inline bool is_wgh(int p, uint8_t v) { return v == 14 || (p == 3 && v == 13) || is_hero(v) || is_mon(p, v); }

void comp_notes(const LevelMeta& M, DynState& s) {
  s.clr_n();
  if (!M.has_bard) return;
  int bi = -1;
  for (int i = 0; i < M.n; ++i) if (s.obj[i] == 5) { bi = i; break; }
  if (bi < 0) return;
  int bx = bi % M.w, by = bi / M.w;
  for (int y = max(0, by - 2); y <= min(M.h - 1, by + 2); ++y)
    for (int x = max(0, bx - 2); x <= min(M.w - 1, bx + 2); ++x)
      if ((x != bx || y != by) && is_mov(M.part, s.obj[y * M.w + x])) s.set_n(y * M.w + x);
}

bool run_late(const LevelMeta& M, DynState& s) {
  if (M.has_bard) comp_notes(M, s);
  uint8_t dy[MAX_C] = {};
  if (M.part == 2) {
    for (int y = 0; y < M.h; ++y)
      for (int x = 0; x < M.w; ++x) {
        uint8_t o = s.obj[y * M.w + x];
        if (o == 17) for (int nx = x + 1; nx < M.w; ++nx) { uint8_t u = s.obj[y * M.w + nx]; if (u) { if (is_vuln(2, u)) dy[y * M.w + nx] = 1; break; } }
        if (o == 16) for (int nx = x - 1; nx >= 0; --nx) { uint8_t u = s.obj[y * M.w + nx]; if (u) { if (is_vuln(2, u)) dy[y * M.w + nx] = 1; break; } }
      }
  }
  if (M.part >= 2) {
    for (int y = 0; y < M.h; ++y)
      for (int x = 0; x < M.w; ++x)
        if (s.obj[y * M.w + x] == 15)
          for (int d = 0; d < 4; ++d) {
            int nx = x + DX[d], ny = y + DY[d];
            if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && is_vuln(M.part, s.obj[ny * M.w + nx])) dy[ny * M.w + nx] = 1;
          }
    for (int i = 0; i < M.n; ++i) if (is_heal(s.obj[i])) {
      dy[i] = 0; int x = i % M.w, y = i / M.w;
      for (int d = 0; d < 4; ++d) {
        int nx = x + DX[d], ny = y + DY[d];
        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && is_hero(s.obj[ny * M.w + nx])) dy[ny * M.w + nx] = 0;
      }
    }
    int ml = 0;
    for (int i = 0; i < M.n; ++i) {
      if (dy[i]) { if (is_mon(M.part, s.obj[i])) s.obj[i] = 0; else if (is_hero(s.obj[i])) return true; }
      if (is_mon(M.part, s.obj[i])) ml++;
    }
    if (!ml) for (int i = 0; i < M.n; ++i) if (s.obj[i] == 20) s.obj[i] = 0;
  }
  auto chk_sw = [&](const vector<int>& sw, const vector<int>& dr, uint8_t& op, uint8_t dcode) {
    if (sw.empty()) return false;
    bool aw = false, au = false;
    for (int i : sw) { if (is_wgh(M.part, s.obj[i])) aw = true; else au = true; }
    if (aw && !au && !op) { op = 1; for (int i : dr) if (s.obj[i] == dcode) s.obj[i] = 0; }
    else if (au && op) { op = 0; for (int i : dr) { if (is_hero(s.obj[i])) return true; s.obj[i] = dcode; } }
    return false;
  };
  if (chk_sw(M.y_sw, M.y_dr, s.y_op, 18) || chk_sw(M.p_sw, M.p_dr, s.p_op, 19)) return true;
  if (M.has_bard) for (int i = 0; i < M.n; ++i) if (s.has_n(i) && !is_mov(M.part, s.obj[i])) s.notes[i >> 6] &= ~(1ULL << (i & 63));
  return false;
}

inline bool check_win(const LevelMeta& M, const DynState& s) {
  for (int g : M.goals) if (!is_hero(s.obj[g])) return false;
  int hc = 0;
  for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) hc++;
  return hc == (int)M.goals.size();
}

int step_state(const LevelMeta& M, DynState& s, int mv, bool prune = true) {
  int ai = -1;
  for (int i = 0; i < M.n; ++i) if (is_act(s.obj[i])) { ai = i; break; }
  if (ai < 0) return -1;
  int ax = ai % M.w, ay = ai / M.w; uint8_t ah = s.obj[ai];
  DynState snap = s;
  if (mv == 4) {
    if (M.has_bard) s.clr_n();
    bool sw = false;
    for (int off = 1; off < M.max_h; ++off) {
      uint8_t th = ((ah - 1 + off) % M.max_h) + 1, ti = th + 6; int f = -1;
      for (int x = 0; x < M.w && f < 0; ++x) for (int y = 0; y < M.h; ++y) if (s.obj[y * M.w + x] == ti) { f = y * M.w + x; break; }
      if (f >= 0) { s.obj[ai] = ah + 6; s.obj[f] = th; sw = true; break; }
    }
    if (!sw) return prune ? -1 : (M.part <= 2 ? (check_win(M, s) ? 1 : 0) : (run_late(M, s) ? -1 : (check_win(M, s) ? 1 : 0)));
    if (run_late(M, s) || (prune && s.eq(snap, M.n, M.has_bard))) return -1;
    return check_win(M, s) ? 1 : 0;
  }
  int dx = DX[mv], dy = DY[mv], nx = ax + dx, ny = ay + dy; bool moved = false;
  if (ah == 1) {
    if (M.has_bard) s.clr_n();
    if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h) {
      int cx = nx, cy = ny;
      while (cx >= 0 && cx < M.w && cy >= 0 && cy < M.h && is_mov(M.part, s.obj[cy * M.w + cx])) { cx += dx; cy += dy; }
      if (cx >= 0 && cx < M.w && cy >= 0 && cy < M.h && !s.obj[cy * M.w + cx]) {
        while (cx != ax || cy != ay) { s.obj[cy * M.w + cx] = s.obj[(cy - dy) * M.w + (cx - dx)]; cx -= dx; cy -= dy; }
        s.obj[ai] = 0; moved = true;
      }
    }
  } else if (ah == 2) {
    if (M.has_bard) s.clr_n();
    if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && !s.obj[ny * M.w + nx]) {
      int bx = ax - dx, by = ay - dy; s.obj[ny * M.w + nx] = 2;
      if (bx >= 0 && bx < M.w && by >= 0 && by < M.h && is_mov(M.part, s.obj[by * M.w + bx])) { s.obj[ai] = s.obj[by * M.w + bx]; s.obj[by * M.w + bx] = 0; }
      else s.obj[ai] = 0;
      moved = true;
    }
  } else if (ah == 3) {
    if (M.has_bard) s.clr_n();
    int wx = ax, wy = ay;
    while (true) {
      int tx = wx + dx, ty = wy + dy;
      if (tx < 0 || tx >= M.w || ty < 0 || ty >= M.h) {
        if (M.part == 3 && nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && !s.obj[ny * M.w + nx]) { s.obj[ny * M.w + nx] = 3; s.obj[ai] = 0; moved = true; }
        break;
      }
      uint8_t to = s.obj[ty * M.w + tx];
      if (!to) { wx = tx; wy = ty; }
      else if (is_stat(to)) { if (!s.obj[ny * M.w + nx]) { s.obj[ny * M.w + nx] = 3; s.obj[ai] = 0; moved = true; } break; }
      else if (is_mov(M.part, to)) { s.obj[ty * M.w + tx] = 3; s.obj[ai] = to; moved = true; break; }
      else break;
    }
  } else if (ah == 4) {
    if (M.has_bard) s.clr_n();
    if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && !s.obj[ny * M.w + nx]) { s.obj[ny * M.w + nx] = 4; s.obj[ai] = 0; moved = true; }
  } else if (ah == 6) {
    if (M.has_bard) s.clr_n();
    if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h) {
      int ni = ny * M.w + nx; uint8_t to = s.obj[ni];
      if (!to) { s.obj[ni] = 6; s.obj[ai] = 0; moved = true; }
      else if (to == 14 || to == 15) { s.obj[ni] = 13; moved = true; }
      else if (to == 13) { s.obj[ni] = 14; moved = true; }
      else if (is_heal(to)) { if (prune) return -1; moved = true; }
      else if (is_hero(to)) {
        bool ah_adj = false;
        for (int d = 0; d < 4; ++d) { int hx = nx + DX[d], hy = ny + DY[d]; if (hx >= 0 && hx < M.w && hy >= 0 && hy < M.h && is_heal(s.obj[hy * M.w + hx])) ah_adj = true; }
        if (!ah_adj) s.obj[ni] = 13; else if (prune) return -1;
        moved = true;
      }
    }
  } else if (ah == 5) {
    int bp = ai, chm[25], nc = 0; bool bmv = false;
    for (int yy = max(0, ay - 2); yy <= min(M.h - 1, ay + 2); ++yy)
      for (int xx = max(0, ax - 2); xx <= min(M.w - 1, ax + 2); ++xx)
        if (s.has_n(yy * M.w + xx)) chm[nc++] = yy * M.w + xx;
    uint8_t st[25]; memset(st, 1, nc); bool chg = true;
    while (chg) {
      chg = false;
      for (int ci = 0; ci < nc; ++ci) if (st[ci]) {
        int p = chm[ci], tx = (p % M.w) + dx, ty = (p / M.w) + dy;
        if (tx >= 0 && tx < M.w && ty >= 0 && ty < M.h && !s.obj[ty * M.w + tx]) { s.obj[ty * M.w + tx] = s.obj[p]; s.obj[p] = 0; st[ci] = 0; chg = true; }
      }
      if (!bmv) {
        int tx = (bp % M.w) + dx, ty = (bp / M.w) + dy;
        if (tx >= 0 && tx < M.w && ty >= 0 && ty < M.h && !s.obj[ty * M.w + tx]) { s.obj[ty * M.w + tx] = 5; s.obj[bp] = 0; bp = ty * M.w + tx; bmv = true; chg = true; }
      }
    }
    if (!bmv) { s = snap; return prune ? -1 : (check_win(M, s) ? 1 : 0); }
    s.clr_n(); moved = true;
  }
  if (!moved) { if (M.part <= 2) { s = snap; return prune ? -1 : (check_win(M, s) ? 1 : 0); } if (prune) return -1; }
  if (run_late(M, s) || (prune && s.eq(snap, M.n, M.has_bard))) return -1;
  return check_win(M, s) ? 1 : 0;
}

pair<LevelMeta, DynState> parse_lv(int part, int w, int h, const vector<string>& rows) {
  LevelMeta M; M.part = part; M.w = w; M.h = h; M.n = w * h; M.max_h = part == 1 ? 3 : (part == 2 ? 4 : 6);
  DynState s{};
  for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) {
    char c = rows[y][x]; int i = y * w + x;
    if (c == 'G') { M.flr[i] = 1; M.goals.push_back(i); }
    else if (c == '{') { M.flr[i] = 2; M.y_sw.push_back(i); }
    else if (c == '}') { M.flr[i] = 3; M.p_sw.push_back(i); }
    else if (c == '#') s.obj[i] = 13; else if (c == '*') s.obj[i] = 14;
    else if (c == 'O') s.obj[i] = 15; else if (c == 'L') s.obj[i] = 16; else if (c == 'R') s.obj[i] = 17;
    else if (c == '[') { s.obj[i] = 18; M.y_dr.push_back(i); }
    else if (c == ']') { s.obj[i] = 19; M.p_dr.push_back(i); }
    else if (c == 'M') s.obj[i] = 20;
    else if (c == 'F') s.obj[i] = 1; else if (c == 'T') s.obj[i] = 2; else if (c == 'W') s.obj[i] = 3;
    else if (c == 'P') s.obj[i] = 4; else if (c == 'B') { s.obj[i] = 5; M.has_bard = true; }
    else if (c == 'D') s.obj[i] = 6;
    else if (c >= '1' && c <= '6') { s.obj[i] = (uint8_t)(6 + c - '0'); if (c == '5') M.has_bard = true; }
  }
  for (int i = 0; i < M.n; ++i) for (int g : M.goals) if (abs((i % w) - (g % w)) + abs((i / w) - (g / w)) <= 3) M.near_g[i] = 1;
  if (part == 3) run_late(M, s);
  return {M, s};
}

string render_ascii(const LevelMeta& M, const DynState& s) {
  static const char* HA = "?FTWPBD"; string out;
  for (int y = 0; y < M.h; ++y) {
    for (int x = 0; x < M.w; ++x) {
      int i = y * M.w + x; uint8_t o = s.obj[i]; char ch = '.';
      if (o >= 1 && o <= 6) ch = HA[o]; else if (o >= 7 && o <= 12) ch = (char)('0' + o - 6);
      else if (o == 13) ch = '#'; else if (o == 14) ch = '*'; else if (o == 15) ch = 'O';
      else if (o == 16) ch = 'L'; else if (o == 17) ch = 'R'; else if (o == 18) ch = '[';
      else if (o == 19) ch = ']'; else if (o == 20) ch = 'M';
      else if (M.flr[i] == 1) ch = 'G'; else if (M.flr[i] == 2) ch = '{'; else if (M.flr[i] == 3) ch = '}';
      out.push_back(ch);
    }
    if (y + 1 < M.h) out.push_back('\\'); // escaped in JSON output directly below
  }
  return out;
}

struct FastHashSet {
  vector<uint64_t> tab; size_t mask, cnt = 0;
  explicit FastHashSet(size_t b = 24) : tab(1ULL << b, 0), mask((1ULL << b) - 1) {}
  inline bool insert(uint64_t k) {
    if (!k) k = 1;
    for (size_t i = k & mask;; i = (i + 1) & mask) {
      if (tab[i] == k) return false;
      if (!tab[i]) { tab[i] = k; cnt++; return true; }
    }
  }
};

DynState xform(const LevelMeta& M, const DynState& s, int sm) {
  if (!sm) return s;
  DynState o{}; o.y_op = s.y_op; o.p_op = s.p_op;
  for (int y = 0; y < M.h; ++y) for (int x = 0; x < M.w; ++x) {
    int tx = (sm >= 2) ? (M.w - 1 - x) : x, ty = (sm == 1 || sm == 3) ? (M.h - 1 - y) : y;
    uint8_t v = s.obj[y * M.w + x];
    if (sm >= 2) { if (v == 16) v = 17; else if (v == 17) v = 16; }
    o.obj[ty * M.w + tx] = v;
  }
  return o;
}

inline int bkt16(const LevelMeta& M, const DynState& s) {
  int ng = 0, ah = 0;
  for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) { if (is_act(s.obj[i])) ah = s.obj[i]; if (M.near_g[i]) ng++; }
  return (ng * 6 + (ah % 6)) & 15;
}

struct PRec { int prev; char mv; };

void select_beam(int keep, int cap, const vector<uint64_t>& ord, const vector<int>& cb,
                 const vector<DynState>& cs, const vector<PRec>& cp, vector<DynState>& nxt, vector<PRec>& tr) {
  unordered_map<int, int> bc; vector<uint8_t> used(cs.size(), 0);
  nxt.reserve(keep); tr.reserve(keep);
  for (uint64_t ok : ord) {
    if ((int)nxt.size() >= keep) break;
    uint32_t i = (uint32_t)ok;
    if (++bc[cb[i]] <= cap) { used[i] = 1; nxt.push_back(cs[i]); tr.push_back(cp[i]); }
  }
  for (uint64_t ok : ord) {
    if ((int)nxt.size() >= keep) break;
    uint32_t i = (uint32_t)ok;
    if (!used[i]) { nxt.push_back(cs[i]); tr.push_back(cp[i]); }
  }
}

string tube_beam(const LevelMeta& M, const DynState& s0, const vector<DynState>& tgt, int max_d, int bw, int cap, double bsec) {
  auto t0 = chrono::steady_clock::now(); int N = (int)tgt.size() - 1;
  auto nv = [&](uint8_t v) -> uint8_t { return is_hero(v) ? 99 : v; };
  vector<array<uint8_t, MAX_C>> nt(N + 1);
  for (int k = 0; k <= N; ++k) for (int i = 0; i < M.n; ++i) nt[k][i] = nv(tgt[k].obj[i]);
  vector<vector<PRec>> tr(max_d + 1); vector<DynState> cur = {s0}; tr[0].push_back({-1, 0});
  FastHashSet seen(24); seen.insert(s0.hash64(M.n, M.has_bard)); string best;
  for (int d = 1; d <= max_d; ++d) {
    if (chrono::duration<double>(chrono::steady_clock::now() - t0).count() > bsec || seen.cnt > 13000000) break;
    vector<DynState> cs; vector<PRec> cp; vector<int> cb; vector<uint64_t> ord;
    int klo = max(0, d - 12), khi = min(N, d + 16); uint8_t nb[MAX_C];
    for (int i = 0; i < (int)cur.size(); ++i) for (int mv = 0; mv < 5; ++mv) {
      DynState ns = cur[i]; int r = step_state(M, ns, mv, true);
      if (r < 0) continue;
      if (r == 1) {
        string p(1, DCH[mv]); for (int cd = d - 1, ci = i; cd >= 1; --cd) { p.push_back(tr[cd][ci].mv); ci = tr[cd][ci].prev; }
        reverse(p.begin(), p.end());
        if (best.empty() || p.size() < best.size()) { best = p; max_d = (int)p.size() - 1; }
        continue;
      }
      if (d >= max_d || !seen.insert(ns.hash64(M.n, M.has_bard))) continue;
      for (int j = 0; j < M.n; ++j) nb[j] = nv(ns.obj[j]);
      int bsc = 999999, bk = d;
      for (int k = klo; k <= khi; ++k) {
        int df = 0; const uint8_t* tk = nt[k].data();
        for (int j = 0; j < M.n; ++j) df += (nb[j] != tk[j]);
        int sc = df * 6 - k * 5; if (sc < bsc) { bsc = sc; bk = k; }
      }
      uint32_t idx = (uint32_t)cs.size(); cs.push_back(ns); cp.push_back({i, DCH[mv]});
      cb.push_back((bk * 16) + bkt16(M, ns)); ord.push_back(((uint64_t)(uint32_t)(bsc + 500000) << 32) | idx);
    }
    if (cs.empty() || d >= max_d) break;
    sort(ord.begin(), ord.end());
    vector<DynState> nxt; select_beam(min((int)cs.size(), bw), cap, ord, cb, cs, cp, nxt, tr[d]); cur.swap(nxt);
  }
  return best;
}

string win_shortcut(const LevelMeta& M, const DynState& s0, string rt, int wl) {
  for (bool imp = true; imp;) {
    imp = false; vector<DynState> tj = {s0};
    for (char c : rt) { DynState nx = tj.back(); step_state(M, nx, d_idx(c), false); tj.push_back(nx); }
    int N = (int)rt.size();
    for (int L = 0; L < N && !imp; L += max(2, wl / 3)) {
      int R = min(N, L + wl); unordered_map<uint64_t, pair<int, DynState>> gi;
      for (int k = L + 2; k <= R; ++k) gi[tj[k].hash64(M.n, M.has_bard)] = {k, tj[k]};
      struct Nd { DynState s; int p; char m; int d; };
      vector<Nd> q = {{tj[L], -1, 0, 0}}; unordered_set<uint64_t> vis = {tj[L].hash64(M.n, M.has_bard)};
      int mb = (R - L) - 1;
      for (size_t qi = 0; qi < q.size() && !imp; ++qi) {
        if (q[qi].d >= mb || q.size() > 150000) break;
        for (int mv = 0; mv < 5; ++mv) {
          DynState ns = q[qi].s; int r = step_state(M, ns, mv, true);
          if (r < 0) continue;
          auto rec = [&](int suf_k) {
            string m(1, DCH[mv]); for (int c = (int)qi; c > 0; c = q[c].p) m.push_back(q[c].m);
            reverse(m.begin(), m.end()); return rt.substr(0, L) + m + rt.substr(suf_k);
          };
          if (r == 1 && L + q[qi].d + 1 < N) { rt = rec(N); imp = true; break; }
          uint64_t h = ns.hash64(M.n, M.has_bard); auto it = gi.find(h);
          if (it != gi.end() && ns.eq(it->second.second, M.n, M.has_bard) && q[qi].d + 1 < it->second.first - L) {
            rt = rec(it->second.first); imp = true; break;
          }
          if (q[qi].d + 1 < mb && vis.insert(h).second) q.push_back({ns, (int)qi, DCH[mv], q[qi].d + 1});
        }
      }
    }
  }
  return rt;
}


int main(){
 string dummy,route; int part,w,h,budget; cin>>part>>w>>h>>budget; getline(cin,dummy);
 vector<string> rows(h); for(auto& row:rows)getline(cin,row);getline(cin,route);
 auto [M,s0]=parse_lv(part,w,h,rows); auto start=chrono::steady_clock::now();
 auto secs=[&](){return chrono::duration<double>(chrono::steady_clock::now()-start).count();};
 long windows=0,expanded=0,cap_hits=0; bool timeout=false; int lastL=-1,lastW=0;
 for(int wl:{12,16,20}){
  bool improved=true;
  while(improved && secs()<budget){
   improved=false; vector<DynState> tj={s0};
   for(char c:route){DynState nx=tj.back();step_state(M,nx,d_idx(c),false);tj.push_back(nx);}
   int N=route.size();
   for(int L=0;L<N-1&&!improved;L++){
    if(secs()>=budget){timeout=true;break;} lastL=L;lastW=wl;windows++;
    int R=min(N,L+wl);unordered_map<uint64_t,pair<int,DynState>> gi;
    for(int k=L+2;k<=R;k++)gi[tj[k].hash64(M.n,M.has_bard)]={k,tj[k]};
    struct Nd{DynState s;int p;char m;int d;};vector<Nd> q={{tj[L],-1,0,0}};
    unordered_set<uint64_t> vis={tj[L].hash64(M.n,M.has_bard)};int mb=R-L-1;
    for(size_t qi=0;qi<q.size()&&!improved;qi++){
     if(q[qi].d>=mb)break;
     if(q.size()>300000){cap_hits++;break;}
     if((qi&1023)==0 && secs()>=budget){timeout=true;break;}
     expanded++;
     for(int mv=0;mv<5;mv++){
      DynState ns=q[qi].s;int r=step_state(M,ns,mv,true);if(r<0)continue;
      int suffix=-1;
      if(r==1 && L+q[qi].d+1<N)suffix=N;
      uint64_t hash=ns.hash64(M.n,M.has_bard);auto it=gi.find(hash);
      if(suffix<0 && it!=gi.end() && ns.eq(it->second.second,M.n,M.has_bard) && q[qi].d+1<it->second.first-L)suffix=it->second.first;
      if(suffix>=0){string m(1,DCH[mv]);for(int c=qi;c>0;c=q[c].p)m.push_back(q[c].m);reverse(m.begin(),m.end());route=route.substr(0,L)+m+route.substr(suffix);improved=true;
       cout<<"{\"event\":\"candidate\",\"length\":"<<route.size()<<",\"route\":\""<<route<<"\",\"window\":"<<wl<<",\"L\":"<<L<<",\"elapsed\":"<<secs()<<"}"<<endl;break;}
      if(q[qi].d+1<mb && vis.insert(hash).second)q.push_back({ns,(int)qi,DCH[mv],q[qi].d+1});
     }
    }
    if(timeout)break;
   }
  }
  if(timeout)break;
 }
 cout<<"{\"event\":\"summary\",\"length\":"<<route.size()<<",\"route\":\""<<route<<"\",\"elapsed\":"<<secs()<<",\"windows\":"<<windows<<",\"expanded\":"<<expanded<<",\"cap_hits\":"<<cap_hits<<",\"timeout\":"<<(timeout?"true":"false")<<",\"last_window\":"<<lastW<<",\"last_L\":"<<lastL<<"}"<<endl;
}
