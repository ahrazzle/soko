// prove_iii14_15x7_landmark_floor.cpp
// Globally 1-step-consistent Quotient + Switch-Harvest Landmark Prover for canonical 15x7 Room III-14
// (Part III SHA-256: f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0,
//  board_sha256_lf:  300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c).
//
// Portable standard C++20 (compiles cleanly under both Apple clang++ and GCC g++ without <bits/stdc++.h>,
// zero bare assert, deterministic checks active under -O3 -DNDEBUG).
//
// Modes:
//   ./prove_iii14_15x7_landmark_floor --self-test [--walk-edges 2000000] [--max-states 2000000] [--json-out out.json]
//   ./prove_iii14_15x7_landmark_floor --walk-edges 52000000 --max-states 665600000 --time-limit 180 --json-out out.json

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <random>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

using namespace std;
using u128 = unsigned __int128;

static void require_check(bool cond, const char* msg) {
  if (!cond) {
    cerr << "[FATAL CHECK FAILURE] " << msg << "\n";
    exit(2);
  }
}

static constexpr int W = 15, H = 7, N = 105;
static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};

static const char* GRID_III14[7] = {
    "###############",
    "#.............#",
    "#.5.}}}.]]]]].#",
    "#...}}}.]G.G].#",
    "#.D.}}}.]]]]].#",
    "#.............#",
    "###############",
};

static const string R48_ROUTE = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
static const string W41_ROUTE = "LLULULUULRRURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";

// Minimal standalone SHA-256 so board_sha256_lf is computed dynamically with zero hardcoded literals!
struct Sha256 {
  static inline uint32_t rotr(uint32_t x, uint32_t n) { return (x >> n) | (x << (32 - n)); }
  static string hex(const string& data) {
    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    uint32_t h[8] = {
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    };
    vector<uint8_t> msg(data.begin(), data.end());
    uint64_t bit_len = uint64_t(msg.size()) * 8ULL;
    msg.push_back(0x80);
    while ((msg.size() % 64) != 56) msg.push_back(0x00);
    for (int i = 7; i >= 0; --i) msg.push_back(uint8_t((bit_len >> (i * 8)) & 0xFF));
    for (size_t off = 0; off < msg.size(); off += 64) {
      uint32_t w[64];
      for (int i = 0; i < 16; ++i)
        w[i] = (uint32_t(msg[off + 4 * i]) << 24) | (uint32_t(msg[off + 4 * i + 1]) << 16) |
               (uint32_t(msg[off + 4 * i + 2]) << 8) | uint32_t(msg[off + 4 * i + 3]);
      for (int i = 16; i < 64; ++i) {
        uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
      }
      uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
      for (int i = 0; i < 64; ++i) {
        uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t t1 = hh + S1 + ch + K[i] + w[i];
        uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = S0 + maj;
        hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
      }
      h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }
    char out[65];
    for (int i = 0; i < 8; ++i) snprintf(out + i * 8, 9, "%08x", h[i]);
    out[64] = '\0';
    return string(out);
  }
};

static inline u128 bit(int i) { return ((u128)1) << i; }
static inline bool tst(u128 m, int i) { return (m >> i) & 1; }
static inline int popcnt128(u128 m) {
  return __builtin_popcountll((uint64_t)m) + __builtin_popcountll((uint64_t)(m >> 64));
}

static u128 ORIGIN_MASK = 0, SWITCH_MASK = 0, PDOOR_MASK = 0, VAULT_IN_MASK = 0, AURA[N]{}, ORTHO[N]{};
static u128 D5_MASK[5]{};
static int D5_RING[N]{}, O5_BKT[N]{};
static bool IS_ORIG[N], IS_SW[N], IS_PD[N];
static int B0 = -1, D0 = -1, GOALS[2];

inline int mirror_y_cell(int i) { return (6 - (i / W)) * W + (i % W); }
inline u128 mirror_y_mask(u128 m) {
  constexpr u128 RM = (u128(1) << 15) - 1;
  u128 r0 = (m >> 0) & RM, r1 = (m >> 15) & RM, r2 = (m >> 30) & RM, r3 = (m >> 45) & RM;
  u128 r4 = (m >> 60) & RM, r5 = (m >> 75) & RM, r6 = (m >> 90) & RM;
  return (r6 << 0) | (r5 << 15) | (r4 << 30) | (r3 << 45) | (r2 << 60) | (r1 << 75) | (r0 << 90);
}

struct CState {
  u128 crates, walls;
  uint8_t bx, by, dx, dy, ah, doors_open;
};

inline CState mirror_y_state(const CState& s) {
  return CState{
      mirror_y_mask(s.crates), mirror_y_mask(s.walls),
      s.bx, uint8_t(6 - s.by), s.dx, uint8_t(6 - s.dy), s.ah, s.doors_open
  };
}

struct __attribute__((packed)) Packed15 {
  uint64_t c_lo, w_lo;
  uint32_t c_mid, w_mid;
  uint16_t c_hi, w_hi;
  uint8_t b_and_do, d_and_ah;
  bool operator==(const Packed15& o) const {
    return c_lo == o.c_lo && w_lo == o.w_lo && c_mid == o.c_mid && w_mid == o.w_mid &&
           c_hi == o.c_hi && w_hi == o.w_hi && b_and_do == o.b_and_do && d_and_ah == o.d_and_ah;
  }
  bool operator<(const Packed15& o) const { return memcmp(this, &o, sizeof(Packed15)) < 0; }
  uint64_t hash64() const {
    uint64_t h1 = c_lo ^ (((uint64_t)c_mid | ((uint64_t)c_hi << 32)) * 0x9e3779b97f4a7c15ULL);
    uint64_t h2 = w_lo ^ (((uint64_t)w_mid | ((uint64_t)w_hi << 32)) * 0xbf58476d1ce4e5b9ULL);
    uint64_t h3 = ((uint64_t)b_and_do) | ((uint64_t)d_and_ah << 8);
    uint64_t h = (h1 ^ (h2 * 0x94d049bb133111ebULL)) + (h3 * 0xd6e8feb86659fd93ULL);
    h ^= h >> 33; h *= 0xff51afd7ed558ccdULL; h ^= h >> 33;
    return h;
  }
};
static_assert(sizeof(Packed15) == 30);

inline Packed15 pack_raw(const CState& s) {
  return Packed15{
      (uint64_t)s.crates, (uint64_t)s.walls,
      (uint32_t)(s.crates >> 64), (uint32_t)(s.walls >> 64),
      (uint16_t)(s.crates >> 96), (uint16_t)(s.walls >> 96),
      uint8_t((s.by * W + s.bx) | (s.doors_open << 7)),
      uint8_t((s.dy * W + s.dx) | (s.ah << 7))
  };
}
inline Packed15 pack_canon(const CState& s) {
  Packed15 p1 = pack_raw(s), p2 = pack_raw(mirror_y_state(s));
  return (p2 < p1) ? p2 : p1;
}
inline CState unpack15(const Packed15& p) {
  CState s{};
  s.crates = (u128)p.c_lo | ((u128)p.c_mid << 64) | ((u128)p.c_hi << 96);
  s.walls = (u128)p.w_lo | ((u128)p.w_mid << 64) | ((u128)p.w_hi << 96);
  uint8_t bp = p.b_and_do & 127; s.bx = bp % W; s.by = bp / W; s.doors_open = (p.b_and_do >> 7) & 1;
  uint8_t dp = p.d_and_ah & 127; s.dx = dp % W; s.dy = dp / W; s.ah = (p.d_and_ah >> 7) & 1;
  return s;
}

inline bool step_concrete(const CState& s, int mv, CState& ns) {
  ns = s;
  u128 closed = ns.doors_open ? 0 : PDOOR_MASK;
  if (mv == 4) {
    ns.ah = 1 - ns.ah;
  } else if (ns.ah == 1) {
    int nx = int(ns.dx) + DX[mv], ny = int(ns.dy) + DY[mv];
    if (nx < 0 || nx >= W || ny < 0 || ny >= H || (nx == ns.bx && ny == ns.by)) return false;
    int ni = ny * W + nx;
    if (tst(closed, ni)) return false;
    if (tst(ns.crates, ni)) { ns.crates &= ~bit(ni); ns.walls |= bit(ni); }
    else if (tst(ns.walls, ni)) { ns.crates |= bit(ni); ns.walls &= ~bit(ni); }
    else { ns.dx = uint8_t(nx); ns.dy = uint8_t(ny); }
  } else {
    int bi = ns.by * W + ns.bx;
    u128 m = ns.crates;
    int c_pos[42]; bool c_ch[42]; int nc = 0;
    while (m) {
      int c = (uint64_t)m ? __builtin_ctzll((uint64_t)m) : (64 + __builtin_ctzll((uint64_t)(m >> 64)));
      m &= ~bit(c); c_pos[nc] = c; c_ch[nc] = tst(AURA[bi], c); nc++;
    }
    bool d_ch = tst(AURA[bi], ns.dy * W + ns.dx), b_mv = false, chg = true;
    while (chg) {
      chg = false;
      for (int k = 0; k < nc; ++k) {
        if (!c_ch[k]) continue;
        int tx = (c_pos[k] % W) + DX[mv], ty = (c_pos[k] / W) + DY[mv];
        if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
        int ti = ty * W + tx;
        if (!tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.bx && ty == ns.by) && !(tx == ns.dx && ty == ns.dy)) {
          ns.crates &= ~bit(c_pos[k]); ns.crates |= bit(ti);
          c_pos[k] = ti; c_ch[k] = false; chg = true;
        }
      }
      if (d_ch) {
        int tx = int(ns.dx) + DX[mv], ty = int(ns.dy) + DY[mv];
        if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
          int ti = ty * W + tx;
          if (!tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.bx && ty == ns.by)) {
            ns.dx = uint8_t(tx); ns.dy = uint8_t(ty); d_ch = false; chg = true;
          }
        }
      }
      if (!b_mv) {
        int tx = int(ns.bx) + DX[mv], ty = int(ns.by) + DY[mv];
        if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
          int ti = ty * W + tx;
          if (!tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.dx && ty == ns.dy)) {
            ns.bx = uint8_t(tx); ns.by = uint8_t(ty); b_mv = true; chg = true;
          }
        }
      }
    }
    if (!b_mv) return false;
  }
  u128 weighing = ns.crates | ns.walls | bit(ns.by * W + ns.bx) | bit(ns.dy * W + ns.dx);
  bool all_sw = ((weighing & SWITCH_MASK) == SWITCH_MASK);
  if (all_sw) {
    ns.doors_open = 1;
  } else if (ns.doors_open) {
    ns.doors_open = 0;
    if (tst(PDOOR_MASK, ns.by * W + ns.bx) || tst(PDOOR_MASK, ns.dy * W + ns.dx)) return false;
    ns.crates &= ~PDOOR_MASK;
    ns.walls &= ~PDOOR_MASK;
  }
  return true;
}

inline bool is_win(const CState& s) {
  int bp = s.by * W + s.bx, dp = s.dy * W + s.dx;
  return (bp == GOALS[0] && dp == GOALS[1]) || (bp == GOALS[1] && dp == GOALS[0]);
}

static void init_topology() {
  ORIGIN_MASK = SWITCH_MASK = PDOOR_MASK = VAULT_IN_MASK = 0;
  for (int k = 0; k < 5; ++k) D5_MASK[k] = 0;
  for (int i = 0; i < N; ++i) { AURA[i] = 0; ORTHO[i] = 0; }
  int g_i = 0;
  for (int y = 0; y < H; ++y)
    for (int x = 0; x < W; ++x) {
      char c = GRID_III14[y][x]; int i = y * W + x;
      IS_ORIG[i] = (c == '#'); IS_SW[i] = (c == '}'); IS_PD[i] = (c == ']');
      if (y == 3 && x >= 9 && x <= 11) VAULT_IN_MASK |= bit(i);
      if (c == '#') ORIGIN_MASK |= bit(i);
      else if (c == '}') SWITCH_MASK |= bit(i);
      else if (c == ']') PDOOR_MASK |= bit(i);
      else if (c == 'G') GOALS[g_i++] = i;
      else if (c == '5') B0 = i;
      else if (c == 'D') D0 = i;
      int dx = max(0, max(4 - x, x - 6));
      int dy = max(0, max(2 - y, y - 4));
      D5_RING[i] = min(4, dx + dy);
      D5_MASK[D5_RING[i]] |= bit(i);
      if (dx == 0 && dy == 0) O5_BKT[i] = 0;
      else if (dx == 1 && dy == 0) O5_BKT[i] = 1;
      else if (dx == 0 && dy == 1) O5_BKT[i] = 2;
      else if (dx + dy == 2) O5_BKT[i] = 3;
      else O5_BKT[i] = 4;
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

static inline CState start_state() {
  return CState{0, ORIGIN_MASK, uint8_t(B0 % W), uint8_t(B0 / W), uint8_t(D0 % W), uint8_t(D0 / W), 1, 0};
}

// ============================================================================
// QuotientAuditStats: records exhaustive forward-edge quotient verification
// ============================================================================
struct QuotientAuditStats {
  uint64_t vertices = 0;
  uint64_t reachable = 0;
  uint64_t goals = 0;
  uint64_t forward_edges_checked = 0;
  uint64_t goal_violations = 0;
  uint64_t step_violations = 0;
};

// ============================================================================
// PDB 1: Switch3x3_15PDB (All 9 switches [4..6]x[2..4] in ternary 3^9 = 19,683)
// + Zero-Self-Loop 9-Harvest Deficit Composition (`need9`)
// ============================================================================
struct Switch3x3_15PDB {
  static constexpr int NB = 60;
  static constexpr int NS9 = 19683;
  static constexpr uint32_t TOTAL = uint32_t(NB) * N * 2 * NS9;

  vector<uint8_t> dist;
  int pow3[10];
  uint16_t mirror_st9[NS9];
  uint8_t sw_zero_mask_lo[NS9], sw_zero_mask_hi[NS9];
  uint8_t h_aura5[N][3]{}, v_aura5[N][3]{};

  struct LineMap { uint32_t fwd_mask[27]; };
  vector<LineMap> u_lmaps;
  vector<array<vector<uint8_t>, 27>> back_lmaps;
  uint16_t lmap_id[2][32][8][8][3];

  static inline int scell(int col, int row) { return (2 + row) * W + (4 + col); }
  static inline int sidx_of(int cell) {
    int x = cell % W, y = cell / W;
    return (x >= 4 && x <= 6 && y >= 2 && y <= 4) ? ((x - 4) * 3 + (y - 2)) : -1;
  }
  static inline uint32_t enc(int b, int d, int ah, int st9) {
    return (((uint32_t(b) * N + d) * 2 + ah) * NS9) + st9;
  }
  inline uint32_t canon_enc(int b, int d, int ah, int st9) const {
    if (b < NB) return enc(b, d, ah, st9);
    return enc(mirror_y_cell(b), mirror_y_cell(d), ah, mirror_st9[st9]);
  }
  inline bool all_sw_fn(int st9, int b, int d) const {
    uint16_t zm = uint16_t(sw_zero_mask_lo[st9]) | (uint16_t(sw_zero_mask_hi[st9]) << 8);
    if (zm == 0) return true;
    int bi = sidx_of(b), di = sidx_of(d);
    if (bi >= 0) zm &= ~(1u << bi);
    if (di >= 0) zm &= ~(1u << di);
    return zm == 0;
  }
  inline bool valid_state_any_b(int b, int d, int st9) const {
    if (b < 0 || b >= N || d < 0 || d >= N || b == d) return false;
    int bi = sidx_of(b), di = sidx_of(d);
    if (bi >= 0 && ((st9 / pow3[bi]) % 3) != 0) return false;
    if (di >= 0 && ((st9 / pow3[di]) % 3) != 0) return false;
    bool ao = all_sw_fn(st9, b, d);
    if (!ao && (IS_PD[b] || IS_PD[d])) return false;
    return true;
  }
  inline bool valid_state(int b, int d, int st9) const {
    return b >= 0 && b < NB && valid_state_any_b(b, d, st9);
  }
  static inline int h_pos7(int cell, int row_y) {
    if (cell / W != row_y) return 7;
    int x = cell % W;
    return (x >= 2 && x <= 8) ? (x - 2) : 7;
  }
  static inline int v_pos7(int cell, int col_x) {
    if (cell % W != col_x) return 7;
    int y = cell / W;
    return (y >= 0 && y <= 6) ? y : 7;
  }

  void init_line_tables() {
    pow3[0] = 1;
    for (int i = 1; i <= 9; ++i) pow3[i] = pow3[i - 1] * 3;
    for (int st = 0; st < NS9; ++st) {
      int a[9], tmp = st; uint16_t zm = 0;
      for (int k = 0; k < 9; ++k) { a[k] = tmp % 3; tmp /= 3; if (a[k] == 0) zm |= (1u << k); }
      sw_zero_mask_lo[st] = uint8_t(zm & 0xFF);
      sw_zero_mask_hi[st] = uint8_t((zm >> 8) & 1);
      int mst = 0;
      for (int col = 0; col < 3; ++col)
        for (int row = 0; row < 3; ++row)
          mst += a[col * 3 + (2 - row)] * pow3[col * 3 + row];
      mirror_st9[st] = uint16_t(mst);
    }
    for (int b = 0; b < N; ++b) {
      for (int r = 0; r < 3; ++r) {
        int y = 2 + r; uint8_t m = 0;
        for (int j = 0; j < 5; ++j) if (tst(AURA[b], y * W + (3 + j))) m |= (1u << j);
        h_aura5[b][r] = m;
      }
      for (int c = 0; c < 3; ++c) {
        int x = 4 + c; uint8_t m = 0;
        for (int j = 0; j < 5; ++j) if (tst(AURA[b], (1 + j) * W + x)) m |= (1u << j);
        v_aura5[b][c] = m;
      }
    }
    u_lmaps.clear();
    for (int di = 0; di < 2; ++di) {
      int dir = (di == 0) ? 1 : -1;
      int src_p = (dir == 1) ? 1 : 5;
      int blk_p = (dir == 1) ? 5 : 1;
      for (int aura5 = 0; aura5 < 32; ++aura5) {
        auto in_aura_p = [&](int p) -> bool { return (p >= 1 && p <= 5) ? ((aura5 >> (p - 1)) & 1) : false; };
        for (int bp = 0; bp < 8; ++bp) {
          int nbp = (bp < 7) ? (bp + dir) : 7;
          for (int dp = 0; dp < 8; ++dp) {
            int tdp = (dp < 7) ? (dp + dir) : 7;
            for (int dm = 0; dm < 3; ++dm) {
              LineMap lm{};
              for (int pre = 0; pre < 27; ++pre) {
                int sa[3] = {pre % 3, (pre / 3) % 3, (pre / 9) % 3};
                if (bp >= 2 && bp <= 4 && sa[bp - 2] != 0) continue;
                if (dp >= 2 && dp <= 4 && sa[dp - 2] != 0) continue;
                if (bp < 7 && bp == dp) continue;
                if (nbp >= 2 && nbp <= 4 && sa[nbp - 2] == 2) continue;
                int max_inc = (in_aura_p(src_p) && bp != src_p && dp != src_p) ? 1 : 0;
                for (int inc = 0; inc <= max_inc; ++inc) {
                  for (int blk = 0; blk <= 1; ++blk) {
                    if (blk == 1 && (bp == blk_p || dp == blk_p || nbp == blk_p)) continue;
                    if (blk == 1 && dm == 2 && tdp == blk_p) continue;
                    int cs[3] = {sa[0], sa[1], sa[2]};
                    bool ch[3] = {cs[0] == 1 && in_aura_p(2), cs[1] == 1 && in_aura_p(3), cs[2] == 1 && in_aura_p(4)};
                    bool in_pend = (inc == 1);
                    int cb = bp, cd = dp;
                    bool b_done = (bp == 7);
                    bool d_tries = (dm == 2) || (dm == 1 && tdp >= 2 && tdp <= 4);
                    bool d_moved = false, chg = true;
                    while (chg) {
                      chg = false;
                      for (int j = 0; j < 3; ++j) if (ch[j]) {
                        int tp = 2 + j + dir;
                        if (tp >= 2 && tp <= 4) {
                          int nj = tp - 2;
                          if (cs[nj] == 0 && cb != tp && cd != tp) { cs[nj] = 1; cs[j] = 0; ch[j] = false; chg = true; }
                        } else {
                          if (blk == 0 && cb != tp && cd != tp) { cs[j] = 0; ch[j] = false; chg = true; }
                        }
                      }
                      if (in_pend) {
                        int tp = src_p + dir, nj = tp - 2;
                        if (cs[nj] == 0 && cb != tp && cd != tp) { cs[nj] = 1; in_pend = false; chg = true; }
                      }
                      if (d_tries && !d_moved) {
                        if (tdp >= 2 && tdp <= 4) {
                          if (cs[tdp - 2] == 0 && cb != tdp) { cd = tdp; d_moved = true; chg = true; }
                        } else if (tdp >= 7 || cb != tdp) {
                          cd = tdp; d_moved = true; chg = true;
                        }
                      }
                      if (!b_done) {
                        if (nbp >= 2 && nbp <= 4) {
                          if (cs[nbp - 2] == 0 && cd != nbp) { cb = nbp; b_done = true; chg = true; }
                        } else if (nbp >= 7 || cd != nbp) {
                          cb = nbp; b_done = true; chg = true;
                        }
                      }
                    }
                    if (!b_done || (dm == 1 && d_moved) || (dm == 2 && !d_moved)) continue;
                    lm.fwd_mask[pre] |= (1u << (cs[0] + 3 * cs[1] + 9 * cs[2]));
                  }
                }
              }
              int found = -1;
              for (int id = 0; id < int(u_lmaps.size()); ++id)
                if (memcmp(u_lmaps[id].fwd_mask, lm.fwd_mask, sizeof(lm.fwd_mask)) == 0) { found = id; break; }
              if (found < 0) { found = int(u_lmaps.size()); u_lmaps.push_back(lm); }
              lmap_id[di][aura5][bp][dp][dm] = uint16_t(found);
            }
          }
        }
      }
    }
    back_lmaps.resize(u_lmaps.size());
    for (size_t id = 0; id < u_lmaps.size(); ++id)
      for (int pre = 0; pre < 27; ++pre) {
        uint32_t m = u_lmaps[id].fwd_mask[pre];
        while (m) { int post = __builtin_ctz(m); m &= m - 1; back_lmaps[id][post].push_back(uint8_t(pre)); }
      }
  }

  size_t reachable_count = 0;

  void build(int num_threads = 10) {
    init_line_tables();
    dist.assign(TOTAL, 255);
    vector<uint32_t> frontier;
    for (int gi = 0; gi < 2; ++gi) {
      int bg = GOALS[gi], dg = GOALS[1 - gi];
      for (int ah = 0; ah < 2; ++ah)
        for (int st9 = 0; st9 < NS9; ++st9)
          if (valid_state(bg, dg, st9)) {
            uint32_t w = enc(bg, dg, ah, st9);
            if (dist[w] == 255) { dist[w] = 0; frontier.push_back(w); }
          }
    }
    reachable_count = frontier.size();
    uint8_t cur_d = 0;
    while (!frontier.empty()) {
      uint8_t nd = cur_d + 1;
      vector<vector<uint32_t>> local_next(num_threads);
      vector<thread> workers;
      size_t fsz = frontier.size();
      auto try_push = [&](uint32_t u, vector<uint32_t>& out) {
        uint8_t exp = 255;
        if (dist[u] == 255 && __atomic_compare_exchange_n(&dist[u], &exp, nd, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED))
          out.push_back(u);
      };
      for (int tid = 0; tid < num_threads; ++tid) {
        workers.emplace_back([&, tid]() {
          auto& out = local_next[tid];
          size_t lo = (fsz * tid) / num_threads, hi = (fsz * (tid + 1)) / num_threads;
          for (size_t qi = lo; qi < hi; ++qi) {
            uint32_t v = frontier[qi];
            int nst9 = v % NS9; uint32_t tmp = v / NS9;
            int nah = tmp & 1; tmp >>= 1;
            int nd_cell = tmp % N, nb_cell = tmp / N;
            bool nao = all_sw_fn(nst9, nb_cell, nd_cell);
            bool nh_pd = IS_PD[nb_cell] || IS_PD[nd_cell];
            try_push(enc(nb_cell, nd_cell, 1 - nah, nst9), out);
            for (int pc = 0; pc < 2; ++pc) {
              int tnb = (pc == 0) ? nb_cell : mirror_y_cell(nb_cell);
              int tnd = (pc == 0) ? nd_cell : mirror_y_cell(nd_cell);
              int tnst = (pc == 0) ? nst9 : int(mirror_st9[nst9]);
              if (nah == 1) {
                if (tnb >= NB) continue;
                int b = tnb, ndx = tnd % W, ndy = tnd / W;
                for (int mv = 0; mv < 4; ++mv) {
                  int px = ndx - DX[mv], py = ndy - DY[mv];
                  if (px < 0 || px >= W || py < 0 || py >= H) continue;
                  int pd_c = py * W + px;
                  if (pd_c == b || !valid_state(b, pd_c, tnst)) continue;
                  bool pre_ao = all_sw_fn(tnst, b, pd_c);
                  if ((!pre_ao && IS_PD[tnd]) || (pre_ao && !nao && nh_pd)) continue;
                  try_push(enc(b, pd_c, 1, tnst), out);
                }
                for (int mv = 0; mv < 4; ++mv) {
                  int tx = ndx + DX[mv], ty = ndy + DY[mv];
                  if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                  int tc = ty * W + tx;
                  if (tc == b) continue;
                  int ki = sidx_of(tc);
                  int pst = tnst;
                  if (ki >= 0) {
                    int pv = (tnst / pow3[ki]) % 3;
                    if (pv == 0) continue;
                    pst = tnst + (3 - 2 * pv) * pow3[ki];
                  }
                  if (!valid_state(b, tnd, pst)) continue;
                  bool pre_ao = all_sw_fn(pst, b, tnd);
                  if ((!pre_ao && IS_PD[tc]) || (pre_ao && !nao && nh_pd)) continue;
                  try_push(enc(b, tnd, 1, pst), out);
                }
              } else {
                int nbx = tnb % W, nby = tnb / W, ndx = tnd % W, ndy = tnd / W;
                for (int mv = 0; mv < 4; ++mv) {
                  int bx = nbx - DX[mv], by = nby - DY[mv];
                  if (bx < 0 || bx >= W || by < 0 || by >= H) continue;
                  int b = by * W + bx;
                  if (b >= NB) continue;
                  int d_cands[3], dm_cands[3], n_dc = 0;
                  if (tnd != b) {
                    if (!tst(AURA[b], tnd)) { d_cands[n_dc] = tnd; dm_cands[n_dc] = 0; n_dc++; }
                    else {
                      int tdx = ndx + DX[mv], tdy = ndy + DY[mv];
                      d_cands[n_dc] = tnd; dm_cands[n_dc] = (tdx < 0 || tdx >= W || tdy < 0 || tdy >= H) ? 0 : 1; n_dc++;
                    }
                  }
                  {
                    int pdx = ndx - DX[mv], pdy = ndy - DY[mv];
                    if (pdx >= 0 && pdx < W && pdy >= 0 && pdy < H) {
                      int pd_c = pdy * W + pdx;
                      if (pd_c != b && tst(AURA[b], pd_c)) { d_cands[n_dc] = pd_c; dm_cands[n_dc] = 2; n_dc++; }
                    }
                  }
                  if (DY[mv] == 0) {
                    int di = (DX[mv] == 1) ? 0 : 1;
                    int post_r[3] = {
                        ((tnst / 1) % 3) + 3 * ((tnst / 27) % 3) + 9 * ((tnst / 729) % 3),
                        ((tnst / 3) % 3) + 3 * ((tnst / 81) % 3) + 9 * ((tnst / 2187) % 3),
                        ((tnst / 9) % 3) + 3 * ((tnst / 243) % 3) + 9 * ((tnst / 6561) % 3),
                    };
                    for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                      int d = d_cands[dc_i], dm = dm_cands[dc_i];
                      const auto& v0 = back_lmaps[lmap_id[di][h_aura5[b][0]][h_pos7(b, 2)][h_pos7(d, 2)][(d / W == 2) ? dm : 0]][post_r[0]];
                      if (v0.empty()) continue;
                      const auto& v1 = back_lmaps[lmap_id[di][h_aura5[b][1]][h_pos7(b, 3)][h_pos7(d, 3)][(d / W == 3) ? dm : 0]][post_r[1]];
                      if (v1.empty()) continue;
                      const auto& v2 = back_lmaps[lmap_id[di][h_aura5[b][2]][h_pos7(b, 4)][h_pos7(d, 4)][(d / W == 4) ? dm : 0]][post_r[2]];
                      if (v2.empty()) continue;
                      for (uint8_t pr0 : v0) {
                        int base0 = (pr0 % 3) + ((pr0 / 3) % 3) * 27 + (pr0 / 9) * 729;
                        for (uint8_t pr1 : v1) {
                          int base01 = base0 + (pr1 % 3) * 3 + ((pr1 / 3) % 3) * 81 + (pr1 / 9) * 2187;
                          for (uint8_t pr2 : v2) {
                            int pst = base01 + (pr2 % 3) * 9 + ((pr2 / 3) % 3) * 243 + (pr2 / 9) * 6561;
                            if (!valid_state(b, d, pst)) continue;
                            bool pre_ao = all_sw_fn(pst, b, d);
                            if ((!pre_ao && (IS_PD[tnb] || (dm == 2 && IS_PD[tnd]))) || (pre_ao && !nao && nh_pd)) continue;
                            try_push(enc(b, d, 0, pst), out);
                          }
                        }
                      }
                    }
                  } else {
                    int di = (DY[mv] == 1) ? 0 : 1;
                    int post_c[3] = {tnst % 27, (tnst / 27) % 27, (tnst / 729) % 27};
                    for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                      int d = d_cands[dc_i], dm = dm_cands[dc_i];
                      const auto& v0 = back_lmaps[lmap_id[di][v_aura5[b][0]][v_pos7(b, 4)][v_pos7(d, 4)][(d % W == 4) ? dm : 0]][post_c[0]];
                      if (v0.empty()) continue;
                      const auto& v1 = back_lmaps[lmap_id[di][v_aura5[b][1]][v_pos7(b, 5)][v_pos7(d, 5)][(d % W == 5) ? dm : 0]][post_c[1]];
                      if (v1.empty()) continue;
                      const auto& v2 = back_lmaps[lmap_id[di][v_aura5[b][2]][v_pos7(b, 6)][v_pos7(d, 6)][(d % W == 6) ? dm : 0]][post_c[2]];
                      if (v2.empty()) continue;
                      for (uint8_t pc0 : v0)
                        for (uint8_t pc1 : v1) {
                          int base01 = int(pc0) + 27 * int(pc1);
                          for (uint8_t pc2 : v2) {
                            int pst = base01 + 729 * int(pc2);
                            if (!valid_state(b, d, pst)) continue;
                            bool pre_ao = all_sw_fn(pst, b, d);
                            if ((!pre_ao && (IS_PD[tnb] || (dm == 2 && IS_PD[tnd]))) || (pre_ao && !nao && nh_pd)) continue;
                            try_push(enc(b, d, 0, pst), out);
                          }
                        }
                    }
                  }
                }
              }
            }
          }
        });
      }
      for (auto& th : workers) th.join();
      frontier.clear();
      size_t nxt_sz = 0; for (auto& ln : local_next) nxt_sz += ln.size();
      frontier.reserve(nxt_sz);
      for (auto& ln : local_next) frontier.insert(frontier.end(), ln.begin(), ln.end());
      reachable_count += frontier.size();
      cur_d++;
    }
  }

  // Independent 100% Exhaustive Forward Quotient-Graph Edge Verifier (`dist[u] <= 1 + dist[v]` and `dist[goal] == 0`)
  QuotientAuditStats audit_all_forward_edges(int num_threads = 10) const {
    QuotientAuditStats out{};
    out.vertices = TOTAL;
    out.reachable = reachable_count;

    for (int gi = 0; gi < 2; ++gi) {
      int bg = GOALS[gi], dg = GOALS[1 - gi];
      for (int ah = 0; ah < 2; ++ah)
        for (int st9 = 0; st9 < NS9; ++st9)
          if (valid_state(bg, dg, st9)) {
            out.goals++;
            if (dist[enc(bg, dg, ah, st9)] != 0) out.goal_violations++;
          }
    }

    vector<uint64_t> t_edges(num_threads, 0), t_viols(num_threads, 0);
    vector<thread> workers;
    for (int tid = 0; tid < num_threads; ++tid) {
      workers.emplace_back([&, tid]() {
        uint64_t loc_e = 0, loc_v = 0;
        for (int b = tid; b < NB; b += num_threads) {
          int bx = b % W, by = b / W;
          for (int d = 0; d < N; ++d) {
            if (b == d) continue;
            int dx = d % W, dy = d / W;
            for (int st9 = 0; st9 < NS9; ++st9) {
              if (!valid_state(b, d, st9)) continue;
              bool pre_ao = all_sw_fn(st9, b, d);

              auto check_edge = [&](int du, int tnb, int tnd, int nah, int tnst) {
                if (!valid_state_any_b(tnb, tnd, tnst)) return;
                bool nao = all_sw_fn(tnst, tnb, tnd);
                if (pre_ao && !nao && (IS_PD[tnb] || IS_PD[tnd])) return;
                uint32_t v = canon_enc(tnb, tnd, nah, tnst);
                int dv = (dist[v] == 255) ? 999 : int(dist[v]);
                loc_e++;
                if (du > 1 + dv) loc_v++;
              };

              // ah == 1 (Druid) + 'A'
              {
                uint32_t u1 = enc(b, d, 1, st9);
                int du1 = (dist[u1] == 255) ? 999 : int(dist[u1]);
                check_edge(du1, b, d, 0, st9);
                for (int mv = 0; mv < 4; ++mv) {
                  int tx = dx + DX[mv], ty = dy + DY[mv];
                  if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                  int tc = ty * W + tx;
                  if (tc == b || (!pre_ao && IS_PD[tc])) continue;
                  int ki = sidx_of(tc);
                  if (ki >= 0) {
                    int val = (st9 / pow3[ki]) % 3;
                    if (val == 0) check_edge(du1, b, tc, 1, st9);
                    else check_edge(du1, b, d, 1, st9 + (3 - 2 * val) * pow3[ki]);
                  } else {
                    check_edge(du1, b, tc, 1, st9);
                    check_edge(du1, b, d, 1, st9);
                  }
                }
              }

              // ah == 0 (Bard) + 'A'
              {
                uint32_t u0 = enc(b, d, 0, st9);
                int du0 = (dist[u0] == 255) ? 999 : int(dist[u0]);
                check_edge(du0, b, d, 1, st9);
                int pre_r[3] = {
                    ((st9 / 1) % 3) + 3 * ((st9 / 27) % 3) + 9 * ((st9 / 729) % 3),
                    ((st9 / 3) % 3) + 3 * ((st9 / 81) % 3) + 9 * ((st9 / 2187) % 3),
                    ((st9 / 9) % 3) + 3 * ((st9 / 243) % 3) + 9 * ((st9 / 6561) % 3),
                };
                int pre_c[3] = {st9 % 27, (st9 / 27) % 27, (st9 / 729) % 27};

                for (int mv = 0; mv < 4; ++mv) {
                  int nbx = bx + DX[mv], nby = by + DY[mv];
                  if (nbx < 0 || nbx >= W || nby < 0 || nby >= H) continue;
                  int nbc = nby * W + nbx;
                  if (!pre_ao && IS_PD[nbc]) continue;

                  int nd_cands[2], dm_cands[2], n_dc = 0;
                  if (!tst(AURA[b], d)) {
                    if (d != nbc) { nd_cands[n_dc] = d; dm_cands[n_dc] = 0; n_dc++; }
                  } else {
                    int tdx = dx + DX[mv], tdy = dy + DY[mv];
                    if (tdx < 0 || tdx >= W || tdy < 0 || tdy >= H) {
                      if (d != nbc) { nd_cands[n_dc] = d; dm_cands[n_dc] = 0; n_dc++; }
                    } else {
                      int tdc = tdy * W + tdx;
                      if (d != nbc) { nd_cands[n_dc] = d; dm_cands[n_dc] = 1; n_dc++; }
                      if (tdc != nbc && !(IS_PD[tdc] && !pre_ao)) {
                        nd_cands[n_dc] = tdc; dm_cands[n_dc] = 2; n_dc++;
                      }
                    }
                  }

                  if (DY[mv] == 0) {
                    int di = (DX[mv] == 1) ? 0 : 1;
                    for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                      int ndc = nd_cands[dc_i], dm = dm_cands[dc_i];
                      uint32_t m0 = u_lmaps[lmap_id[di][h_aura5[b][0]][h_pos7(b, 2)][h_pos7(d, 2)][(dy == 2) ? dm : 0]].fwd_mask[pre_r[0]];
                      if (!m0) continue;
                      uint32_t m1 = u_lmaps[lmap_id[di][h_aura5[b][1]][h_pos7(b, 3)][h_pos7(d, 3)][(dy == 3) ? dm : 0]].fwd_mask[pre_r[1]];
                      if (!m1) continue;
                      uint32_t m2 = u_lmaps[lmap_id[di][h_aura5[b][2]][h_pos7(b, 4)][h_pos7(d, 4)][(dy == 4) ? dm : 0]].fwd_mask[pre_r[2]];
                      if (!m2) continue;
                      for (uint32_t x0 = m0; x0; x0 &= x0 - 1) {
                        int nr0 = __builtin_ctz(x0);
                        int b0 = (nr0 % 3) + ((nr0 / 3) % 3) * 27 + (nr0 / 9) * 729;
                        for (uint32_t x1 = m1; x1; x1 &= x1 - 1) {
                          int nr1 = __builtin_ctz(x1);
                          int b01 = b0 + (nr1 % 3) * 3 + ((nr1 / 3) % 3) * 81 + (nr1 / 9) * 2187;
                          for (uint32_t x2 = m2; x2; x2 &= x2 - 1) {
                            int nr2 = __builtin_ctz(x2);
                            int nst = b01 + (nr2 % 3) * 9 + ((nr2 / 3) % 3) * 243 + (nr2 / 9) * 6561;
                            check_edge(du0, nbc, ndc, 0, nst);
                          }
                        }
                      }
                    }
                  } else {
                    int di = (DY[mv] == 1) ? 0 : 1;
                    for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                      int ndc = nd_cands[dc_i], dm = dm_cands[dc_i];
                      uint32_t m0 = u_lmaps[lmap_id[di][v_aura5[b][0]][v_pos7(b, 4)][v_pos7(d, 4)][(dx == 4) ? dm : 0]].fwd_mask[pre_c[0]];
                      if (!m0) continue;
                      uint32_t m1 = u_lmaps[lmap_id[di][v_aura5[b][1]][v_pos7(b, 5)][v_pos7(d, 5)][(dx == 5) ? dm : 0]].fwd_mask[pre_c[1]];
                      if (!m1) continue;
                      uint32_t m2 = u_lmaps[lmap_id[di][v_aura5[b][2]][v_pos7(b, 6)][v_pos7(d, 6)][(dx == 6) ? dm : 0]].fwd_mask[pre_c[2]];
                      if (!m2) continue;
                      for (uint32_t x0 = m0; x0; x0 &= x0 - 1) {
                        int nc0 = __builtin_ctz(x0);
                        for (uint32_t x1 = m1; x1; x1 &= x1 - 1) {
                          int b01 = nc0 + 27 * __builtin_ctz(x1);
                          for (uint32_t x2 = m2; x2; x2 &= x2 - 1) {
                            int nst = b01 + 729 * __builtin_ctz(x2);
                            check_edge(du0, nbc, ndc, 0, nst);
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        t_edges[tid] = loc_e;
        t_viols[tid] = loc_v;
      });
    }
    for (auto& th : workers) th.join();
    for (int t = 0; t < num_threads; ++t) {
      out.forward_edges_checked += t_edges[t];
      out.step_violations += t_viols[t];
    }
    return out;
  }

  inline int lookup_plus_harvest(const CState& s_in) const {
    CState s = (s_in.by <= 3) ? s_in : mirror_y_state(s_in);
    int st9 = 0, k = 0;
    for (int col = 0; col < 3; ++col)
      for (int row = 0; row < 3; ++row) {
        int c = scell(col, row);
        st9 += (tst(s.crates, c) ? 1 : (tst(s.walls, c) ? 2 : 0)) * pow3[k++];
      }
    int bi = s.by * W + s.bx, di = s.dy * W + s.dx;
    uint8_t d = dist[enc(bi, di, s.ah, st9)];
    if (d == 255) return 999;
    if (tst(VAULT_IN_MASK, bi) && tst(VAULT_IN_MASK, di)) return int(d);
    int m_act = popcnt128(s.crates | (s.walls & ~ORIGIN_MASK));
    return int(d) + max(0, 9 - m_act);
  }
};

// ============================================================================
// PDB 2: HarvestAdj15PDB + 100% Exhaustive Forward Quotient-Graph Edge Audit
// ============================================================================
struct HarvestAdj15PDB {
  static constexpr int NW = 9, NBL = 18;
  int wall_cells[NW], wall_bit_of[N], max_adj[N], da_id[N][3], NDA = 0;
  vector<pair<int, int>> da_list;
  u128 tracked_mask = 0, other_mask = 0;
  uint32_t bl_prev[NBL][4]{}, bl_next[NBL][4]{};
  vector<uint8_t> dist;
  size_t reachable_count = 0;

  static int b_loc_of(int bx, int by) {
    if (by == 3 && (bx == 9 || bx == 11)) return 17;
    if (by == 3 && bx == 10) return 16;
    if (bx >= 8 && bx <= 12 && by >= 2 && by <= 4) return 15;
    return bx;
  }
  static int bx_min_of(int bl) { return bl <= 14 ? bl : (bl == 15 ? 8 : (bl == 16 ? 10 : 9)); }
  static int bx_max_of(int bl) { return bl <= 14 ? bl : (bl == 15 ? 12 : (bl == 16 ? 10 : 11)); }
  inline uint32_t encode(int wm, int kr, int da, int bl, int ah, int ao) const {
    return ((((((uint32_t)wm * 10 + kr) * NDA + da) * NBL + bl) * 2 + ah) * 2) + ao;
  }
  static int max_k_fn(int wm, int kr) { return (kr == 9) ? 40 : (__builtin_popcount((unsigned)wm) + kr); }
  static bool can_open_fn(int wm, int kr, int di, int bl) {
    return max_k_fn(wm, kr) + ((bl >= 4 && bl <= 6) ? 1 : 0) + (IS_SW[di] ? 1 : 0) >= 9;
  }
  inline bool valid_st(int wm, int kr, int di, int adj, int bl, int ao) const {
    if (adj < 0 || adj > max_adj[di] || max_adj[di] - adj > kr) return false;
    int wb = wall_bit_of[di];
    if (wb >= 0 && !((wm >> wb) & 1)) return false;
    if (tst(other_mask, di) && kr == 0) return false;
    if (bl == 0 && (wm & 0x0F) == 0 && kr == 0) return false;
    if (bl == 14 && kr == 0) return false;
    if (ao == 0 && (IS_PD[di] || bl == 15)) return false;
    if (ao == 1 && !can_open_fn(wm, kr, di, bl)) return false;
    return true;
  }

  void build() {
    vector<pair<int, int>> coords = {{0,2},{0,3},{0,4},{0,5},{1,6},{2,6},{3,6},{4,6},{5,6}};
    memset(wall_bit_of, -1, sizeof(wall_bit_of)); tracked_mask = 0;
    for (int b = 0; b < NW; ++b) {
      int idx = coords[b].second * W + coords[b].first;
      wall_cells[b] = idx; wall_bit_of[idx] = b; tracked_mask |= bit(idx);
    }
    other_mask = ORIGIN_MASK & ~tracked_mask;
    memset(da_id, -1, sizeof(da_id)); da_list.clear();
    for (int i = 0; i < N; ++i) {
      max_adj[i] = popcnt128(other_mask & ORTHO[i]);
      for (int a = 0; a <= max_adj[i]; ++a) { da_id[i][a] = int(da_list.size()); da_list.push_back({i, a}); }
    }
    NDA = int(da_list.size());
    const uint32_t TOTAL = (1u << NW) * 10 * NDA * NBL * 2 * 2;
    dist.assign(TOTAL, 255);
    memset(bl_prev, 0, sizeof(bl_prev));
    memset(bl_next, 0, sizeof(bl_next));
    for (int y = 0; y < H; ++y)
      for (int x = 0; x < W; ++x) {
        int l0 = b_loc_of(x, y);
        for (int d = 0; d < 4; ++d) {
          int nx = x + DX[d], ny = y + DY[d];
          if (nx >= 0 && nx < W && ny >= 0 && ny < H) {
            int l1 = b_loc_of(nx, ny);
            bl_prev[l1][d] |= (1u << l0);
            bl_next[l0][d] |= (1u << l1);
          }
        }
      }
    vector<uint32_t> q; q.reserve(TOTAL / 2);
    for (int wm = 0; wm < (1 << NW); ++wm)
      for (int kr = 0; kr <= 9; ++kr)
        for (int dg : {GOALS[0], GOALS[1]})
          for (int adj = 0; adj <= max_adj[dg]; ++adj)
            for (int ah = 0; ah < 2; ++ah)
              for (int ao = 0; ao < 2; ++ao)
                if (valid_st(wm, kr, dg, adj, 17, ao)) {
                  uint32_t w = encode(wm, kr, da_id[dg][adj], 17, ah, ao);
                  if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
                }
    for (size_t qi = 0; qi < q.size(); ++qi) {
      uint32_t v = q[qi]; uint8_t nd = dist[v] + 1; uint32_t tmp = v;
      int nao = tmp & 1; tmp >>= 1; int nah = tmp & 1; tmp >>= 1;
      int nbl = tmp % NBL; tmp /= NBL; int nda = tmp % NDA; tmp /= NDA;
      int nkr = tmp % 10; tmp /= 10; int nwm = int(tmp);
      auto [ndi, nadj] = da_list[nda];
      auto push_pred = [&](int wm, int kr, int di, int adj, int bl, int ah, int ao) {
        if (!valid_st(wm, kr, di, adj, bl, ao)) return;
        uint32_t u = encode(wm, kr, da_id[di][adj], bl, ah, ao);
        if (dist[u] == 255) { dist[u] = nd; q.push_back(u); }
      };
      push_pred(nwm, nkr, ndi, nadj, nbl, 1 - nah, nao);
      if (nah == 1) {
        int ndx = ndi % W, ndy = ndi / W;
        for (int d = 0; d < 4; ++d) {
          int px = ndx - DX[d], py = ndy - DY[d];
          if (px >= 0 && px < W && py >= 0 && py < H) {
            int pdi = py * W + px;
            for (int padj = 0; padj <= max_adj[pdi]; ++padj)
              for (int ao = 0; ao <= 1; ++ao)
                if (!(IS_PD[ndi] && ao == 0)) push_pred(nwm, nkr, pdi, padj, nbl, 1, ao);
          }
          int tx = ndx + DX[d], ty = ndy + DY[d];
          if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
          int ti = ty * W + tx, wb = wall_bit_of[ti];
          int ao = nao;
          if (IS_PD[ti] && ao == 0) continue;
          if (!IS_ORIG[ti]) { if (max_k_fn(nwm, nkr) > 0) push_pred(nwm, nkr, ndi, nadj, nbl, 1, ao); }
          else if (wb >= 0) push_pred(nwm ^ (1 << wb), nkr, ndi, nadj, nbl, 1, ao);
          else if (tst(other_mask, ti)) {
            if (nadj + 1 <= max_adj[ndi]) {
              if (nkr > 0) push_pred(nwm, nkr - 1, ndi, nadj + 1, nbl, 1, ao);
              if (nkr == 9) push_pred(nwm, 9, ndi, nadj + 1, nbl, 1, ao);
            }
            if (nadj >= 1) {
              if (nkr < 9) push_pred(nwm, nkr + 1, ndi, nadj - 1, nbl, 1, ao);
              if (nkr == 9) push_pred(nwm, 9, ndi, nadj - 1, nbl, 1, ao);
            }
          }
        }
      } else {
        int ndx = ndi % W, ndy = ndi / W;
        for (int d = 0; d < 4; ++d) {
          uint32_t pmask = bl_prev[nbl][d];
          for (int bl = 0; bl < NBL; ++bl) if ((pmask >> bl) & 1) {
            bool b_pd = (bl <= 14 && nbl == 15) || (bl == 15);
            for (int ao = 0; ao <= 1; ++ao) if (!(b_pd && ao == 0)) push_pred(nwm, nkr, ndi, nadj, bl, 0, ao);
            int px = ndx - DX[d], py = ndy - DY[d];
            if (px >= 0 && px < W && py >= 0 && py < H && px >= bx_min_of(bl) - 2 && px <= bx_max_of(bl) + 2) {
              int pdi = py * W + px; bool d_pd = IS_PD[pdi] || IS_PD[ndi];
              for (int padj = 0; padj <= max_adj[pdi]; ++padj)
                for (int ao = 0; ao <= 1; ++ao)
                  if (!((b_pd || d_pd) && ao == 0)) push_pred(nwm, nkr, pdi, padj, bl, 0, ao);
            }
          }
        }
      }
    }
    reachable_count = q.size();
  }

  QuotientAuditStats audit_all_forward_edges(int num_threads = 10) const {
    QuotientAuditStats out{};
    out.vertices = uint64_t(1u << NW) * 10 * NDA * NBL * 2 * 2;
    out.reachable = reachable_count;
    for (int wm = 0; wm < (1 << NW); ++wm)
      for (int kr = 0; kr <= 9; ++kr)
        for (int dg : {GOALS[0], GOALS[1]})
          for (int adj = 0; adj <= max_adj[dg]; ++adj)
            for (int ah = 0; ah < 2; ++ah)
              for (int ao = 0; ao < 2; ++ao)
                if (valid_st(wm, kr, dg, adj, 17, ao)) {
                  out.goals++;
                  if (dist[encode(wm, kr, da_id[dg][adj], 17, ah, ao)] != 0) out.goal_violations++;
                }

    vector<uint64_t> t_edges(num_threads, 0), t_viols(num_threads, 0);
    vector<thread> workers;
    for (int tid = 0; tid < num_threads; ++tid) {
      workers.emplace_back([&, tid]() {
        uint64_t loc_e = 0, loc_v = 0;
        for (int wm = tid; wm < (1 << NW); wm += num_threads) {
          for (int kr = 0; kr <= 9; ++kr) {
            for (int da = 0; da < NDA; ++da) {
              auto [di, adj] = da_list[da];
              int dx = di % W, dy = di / W;
              for (int bl = 0; bl < NBL; ++bl) {
                for (int ao = 0; ao <= 1; ++ao) {
                  if (!valid_st(wm, kr, di, adj, bl, ao)) continue;
                  auto check_to = [&](int du, int nwm, int nkr, int ndi, int nadj, int nbl, int nah, int nao) {
                    if (!valid_st(nwm, nkr, ndi, nadj, nbl, nao)) return;
                    uint32_t v = encode(nwm, nkr, da_id[ndi][nadj], nbl, nah, nao);
                    int dv = (dist[v] == 255) ? 999 : int(dist[v]);
                    loc_e++;
                    if (du > 1 + dv) loc_v++;
                  };
                  // ah == 1 + 'A'
                  {
                    int du1 = (dist[encode(wm, kr, da, bl, 1, ao)] == 255) ? 999 : int(dist[encode(wm, kr, da, bl, 1, ao)]);
                    check_to(du1, wm, kr, di, adj, bl, 0, ao);
                    for (int mv = 0; mv < 4; ++mv) {
                      int tx = dx + DX[mv], ty = dy + DY[mv];
                      if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                      int ti = ty * W + tx;
                      if (ao == 0 && IS_PD[ti]) continue;
                      // Walk di -> ti
                      for (int nadj = 0; nadj <= max_adj[ti]; ++nadj)
                        for (int nao = 0; nao <= 1; ++nao)
                          check_to(du1, wm, kr, ti, nadj, bl, 1, nao);
                      // Toggle ti
                      int wb = wall_bit_of[ti];
                      if (!IS_ORIG[ti]) {
                        if (max_k_fn(wm, kr) > 0) check_to(du1, wm, kr, di, adj, bl, 1, ao);
                      } else if (wb >= 0) {
                        check_to(du1, wm ^ (1 << wb), kr, di, adj, bl, 1, ao);
                      } else if (tst(other_mask, ti)) {
                        if (adj >= 1) check_to(du1, wm, min(9, kr + 1), di, adj - 1, bl, 1, ao);
                        if (adj + 1 <= max_adj[di]) {
                          if (kr < 9 && kr >= 1) check_to(du1, wm, kr - 1, di, adj + 1, bl, 1, ao);
                          if (kr == 9) {
                            check_to(du1, wm, 8, di, adj + 1, bl, 1, ao);
                            check_to(du1, wm, 9, di, adj + 1, bl, 1, ao);
                          }
                        }
                      }
                    }
                  }
                  // ah == 0 + 'A'
                  {
                    int du0 = (dist[encode(wm, kr, da, bl, 0, ao)] == 255) ? 999 : int(dist[encode(wm, kr, da, bl, 0, ao)]);
                    check_to(du0, wm, kr, di, adj, bl, 1, ao);
                    for (int mv = 0; mv < 4; ++mv) {
                      uint32_t nmask = bl_next[bl][mv];
                      for (int nbl = 0; nbl < NBL; ++nbl) if ((nmask >> nbl) & 1) {
                        bool b_pd = (bl <= 14 && nbl == 15) || (bl == 15);
                        if (ao == 0 && b_pd) continue;
                        for (int nao = 0; nao <= 1; ++nao) check_to(du0, wm, kr, di, adj, nbl, 0, nao);
                        if (dx >= bx_min_of(bl) - 2 && dx <= bx_max_of(bl) + 2) {
                          int ndx = dx + DX[mv], ndy = dy + DY[mv];
                          if (ndx >= 0 && ndx < W && ndy >= 0 && ndy < H) {
                            int ndi = ndy * W + ndx;
                            if (!(ao == 0 && (IS_PD[di] || IS_PD[ndi]))) {
                              for (int nadj = 0; nadj <= max_adj[ndi]; ++nadj)
                                for (int nao = 0; nao <= 1; ++nao)
                                  check_to(du0, wm, kr, ndi, nadj, nbl, 0, nao);
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        t_edges[tid] = loc_e;
        t_viols[tid] = loc_v;
      });
    }
    for (auto& th : workers) th.join();
    for (int t = 0; t < num_threads; ++t) {
      out.forward_edges_checked += t_edges[t];
      out.step_violations += t_viols[t];
    }
    return out;
  }

  inline int lookup(const CState& s) const {
    u128 miss = ORIGIN_MASK & ~s.walls;
    int wm = 0; for (int b = 0; b < NW; ++b) if (tst(miss, wall_cells[b])) wm |= (1 << b);
    int kr = min(9, popcnt128(miss & other_mask)), di = s.dy * W + s.dx;
    int adj = popcnt128(s.walls & other_mask & ORTHO[di]);
    uint8_t d = dist[encode(wm, kr, da_id[di][adj], b_loc_of(s.bx, s.by), s.ah, s.doors_open)];
    return d == 255 ? 999 : int(d);
  }
};

// ============================================================================
// PDB 3 & 4: RingFlow5_15PDB & OrthoFlow5_15PDB + Exhaustive Forward Edge Audit
// ============================================================================
struct OrthoFlow5_15PDB {
  bool use_ortho = true; // true = OrthoFlow5 (O5_BKT), false = RingFlow5 (D5_RING)
  static constexpr int NB = 60;
  struct Tup5 { uint8_t km, k0, k1, k2, k3; };
  int tp_id[10][10][10][10][10], tp10_id[10][10], NR = 0;
  vector<Tup5> tp_list;
  int max_adj[N], da_id[N][3], NDA = 0;
  vector<pair<int, int>> da_list;
  vector<uint8_t> dist;
  size_t reachable_count = 0;

  struct CapGen {
    uint8_t mode; // 0: horiz/ring, 1: vert
    uint8_t m[5][5];
    bool operator==(const CapGen& o) const { return mode == o.mode && memcmp(m, o.m, sizeof(m)) == 0; }
  };
  int cap_id_of[NB][4][2];
  vector<vector<vector<uint16_t>>> back_tp, fwd_tp;
  vector<vector<uint16_t>> pre_crush, post_crush;

  inline int bkt_of(int i) const { return use_ortho ? O5_BKT[i] : D5_RING[i]; }
  inline uint32_t encode(int rt, int da, int bi, int ah) const {
    return ((((uint32_t)rt * NDA + da) * NB + bi) * 2) + ah;
  }
  inline int ao_of(int rt, int bi, int di) const {
    return (int(tp_list[rt].k0) + (IS_SW[bi] ? 1 : 0) + (IS_SW[di] ? 1 : 0) == 9) ? 1 : 0;
  }
  inline bool valid_u(int rt, int di, int adj, int bi) const {
    if (bi < 0 || bi >= NB || bi == di || adj < 0 || adj > max_adj[di]) return false;
    int h_sw = (IS_SW[bi] ? 1 : 0) + (IS_SW[di] ? 1 : 0);
    if (int(tp_list[rt].k0) + h_sw > 9) return false;
    int ao = (int(tp_list[rt].k0) + h_sw == 9) ? 1 : 0;
    if (ao == 0 && (IS_PD[bi] || IS_PD[di])) return false;
    return true;
  }

  void build(bool ortho_mode) {
    use_ortho = ortho_mode;
    memset(tp_id, -1, sizeof(tp_id)); tp_list.clear();
    for (int km = 0; km <= 9; ++km)
      for (int k0 = 0; k0 <= km; ++k0)
        for (int k1 = 0; k0 + k1 <= km; ++k1)
          for (int k2 = 0; k0 + k1 + k2 <= km; ++k2)
            for (int k3 = 0; k0 + k1 + k2 + k3 <= km; ++k3) {
              tp_id[km][k0][k1][k2][k3] = int(tp_list.size());
              tp_list.push_back({uint8_t(km), uint8_t(k0), uint8_t(k1), uint8_t(k2), uint8_t(k3)});
            }
    for (int k0 = 0; k0 <= 9; ++k0)
      for (int k1 = 0; k1 <= 9; ++k1) {
        tp10_id[k0][k1] = int(tp_list.size());
        tp_list.push_back({10, uint8_t(k0), uint8_t(k1), 0, 0});
      }
    NR = int(tp_list.size());
    memset(da_id, -1, sizeof(da_id)); da_list.clear();
    for (int i = 0; i < N; ++i) {
      max_adj[i] = popcnt128(ORIGIN_MASK & ORTHO[i]);
      for (int a = 0; a <= max_adj[i]; ++a) { da_id[i][a] = int(da_list.size()); da_list.push_back({i, a}); }
    }
    NDA = int(da_list.size());

    vector<CapGen> ucaps;
    for (int bi = 0; bi < NB; ++bi) {
      int bx = bi % W, by = bi / W;
      for (int d = 0; d < 4; ++d) {
        int nbx = bx + DX[d], nby = by + DY[d];
        int nbi = (nbx >= 0 && nbx < W && nby >= 0 && nby < H) ? (nby * W + nbx) : -1;
        uint8_t mode = (use_ortho && DY[d] != 0) ? 1 : 0;
        for (int ao = 0; ao < 2; ++ao) {
          CapGen sc{}; sc.mode = mode;
          if (nbi >= 0) {
            for (int c = 0; c < N; ++c) {
              if (c == bi || !tst(AURA[bi], c) || (ao == 0 && IS_PD[c])) continue;
              int tx = (c % W) + DX[d], ty = (c / W) + DY[d];
              if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
              int tc = ty * W + tx;
              if (tc == nbi || (ao == 0 && IS_PD[tc])) continue;
              int rs = bkt_of(c), rd = bkt_of(tc);
              if (rs != rd) sc.m[rs][rd]++;
            }
          }
          int cid = -1;
          for (int u = 0; u < int(ucaps.size()); ++u) if (ucaps[u] == sc) { cid = u; break; }
          if (cid < 0) { cid = int(ucaps.size()); ucaps.push_back(sc); }
          cap_id_of[bi][d][ao] = cid;
        }
      }
    }

    fwd_tp.assign(NR, vector<vector<uint16_t>>(ucaps.size()));
    back_tp.assign(NR, vector<vector<uint16_t>>(ucaps.size()));
    for (int cid = 0; cid < int(ucaps.size()); ++cid) {
      const auto& sc = ucaps[cid];
      for (int prt = 0; prt < NR; ++prt) {
        auto [pkm, k0, k1, k2, k3] = tp_list[prt];
        if (!use_ortho) {
          if (pkm <= 9) {
            int k4 = pkm - k0 - k1 - k2 - k3;
            for (int x01 = 0; x01 <= min<int>(sc.m[0][1], k0); ++x01)
            for (int x10 = 0; x10 <= min<int>(sc.m[1][0], k1); ++x10)
            for (int x12 = 0; x10 + x12 <= k1 && x12 <= sc.m[1][2]; ++x12)
            for (int x21 = 0; x21 <= min<int>(sc.m[2][1], k2); ++x21)
            for (int x23 = 0; x21 + x23 <= k2 && x23 <= sc.m[2][3]; ++x23)
            for (int x32 = 0; x32 <= min<int>(sc.m[3][2], k3); ++x32)
            for (int x34 = 0; x32 + x34 <= k3 && x34 <= sc.m[3][4]; ++x34)
            for (int x43 = 0; x43 <= min<int>(sc.m[4][3], k4); ++x43) {
              int n0 = k0 - x01 + x10, n1 = k1 - x10 - x12 + x01 + x21;
              int n2 = k2 - x21 - x23 + x12 + x32, n3 = k3 - x32 - x34 + x23 + x43;
              if (n0 <= 9) {
                int nrt = tp_id[pkm][n0][n1][n2][n3];
                if (nrt >= 0) fwd_tp[prt][cid].push_back(uint16_t(nrt));
              }
            }
          } else {
            for (int x01 = 0; x01 <= min<int>(sc.m[0][1], k0); ++x01)
            for (int x10 = 0; x10 <= (k1 < 9 ? min<int>(sc.m[1][0], k1) : int(sc.m[1][0])); ++x10) {
              int n0 = k0 - x01 + x10;
              if (n0 < 0 || n0 > 9) continue;
              if (k1 < 9) {
                for (int x12 = 0; x10 + x12 <= k1 && x12 <= sc.m[1][2]; ++x12)
                for (int x21 = 0; x21 <= sc.m[2][1]; ++x21) {
                  int n1 = min(9, int(k1) - x10 - x12 + x01 + x21);
                  fwd_tp[prt][cid].push_back(uint16_t(tp10_id[n0][n1]));
                }
              } else {
                int lo1 = max(0, 9 - x10 - int(sc.m[1][2]) + x01);
                for (int n1 = min(9, lo1); n1 <= 9; ++n1)
                  fwd_tp[prt][cid].push_back(uint16_t(tp10_id[n0][n1]));
              }
            }
          }
        } else {
          int ba = (sc.mode == 0) ? 1 : 2, bb = 3 - ba;
          if (pkm <= 9) {
            int ka = (sc.mode == 0) ? k1 : k2, kb = (sc.mode == 0) ? k2 : k1;
            int k4 = pkm - k0 - k1 - k2 - k3;
            for (int x0a = 0; x0a <= min<int>(sc.m[0][ba], k0); ++x0a)
            for (int xa0 = 0; xa0 <= min<int>(sc.m[ba][0], ka); ++xa0)
            for (int xa3 = 0; xa0 + xa3 <= ka && xa3 <= sc.m[ba][3]; ++xa3)
            for (int xb3 = 0; xb3 <= min<int>(sc.m[bb][3], kb); ++xb3)
            for (int x3a = 0; x3a <= min<int>(sc.m[3][ba], k3); ++x3a)
            for (int x3b = 0; x3a + x3b <= k3 && x3b <= sc.m[3][bb]; ++x3b)
            for (int x34 = 0; x3a + x3b + x34 <= k3 && x34 <= sc.m[3][4]; ++x34)
            for (int x43 = 0; x43 <= min<int>(sc.m[4][3], k4); ++x43) {
              int n0 = k0 - x0a + xa0;
              int na = ka - xa0 - xa3 + x0a + x3a;
              int nb_v = kb - xb3 + x3b;
              int n3 = k3 - x3a - x3b - x34 + xa3 + xb3 + x43;
              int n1 = (sc.mode == 0) ? na : nb_v, n2 = (sc.mode == 0) ? nb_v : na;
              if (n0 <= 9) {
                int nrt = tp_id[pkm][n0][n1][n2][n3];
                if (nrt >= 0) fwd_tp[prt][cid].push_back(uint16_t(nrt));
              }
            }
          } else {
            int k12 = k1;
            int cap_12_3 = sc.m[ba][3] + sc.m[bb][3];
            int cap_3_12 = sc.m[3][ba] + sc.m[3][bb];
            for (int x0a = 0; x0a <= min<int>(sc.m[0][ba], k0); ++x0a)
            for (int xa0 = 0; xa0 <= (k12 < 9 ? min<int>(sc.m[ba][0], k12) : int(sc.m[ba][0])); ++xa0) {
              int n0 = k0 - x0a + xa0;
              if (n0 < 0 || n0 > 9) continue;
              if (k12 < 9) {
                for (int x12_3 = 0; xa0 + x12_3 <= k12 && x12_3 <= cap_12_3; ++x12_3)
                for (int x3_12 = 0; x3_12 <= cap_3_12; ++x3_12) {
                  int n12 = min(9, int(k12) - xa0 - x12_3 + x0a + x3_12);
                  fwd_tp[prt][cid].push_back(uint16_t(tp10_id[n0][n12]));
                }
              } else {
                int lo12 = max(0, 9 - xa0 - cap_12_3 + x0a);
                for (int n12 = min(9, lo12); n12 <= 9; ++n12)
                  fwd_tp[prt][cid].push_back(uint16_t(tp10_id[n0][n12]));
              }
            }
          }
        }
        auto& fv = fwd_tp[prt][cid];
        sort(fv.begin(), fv.end()); fv.erase(unique(fv.begin(), fv.end()), fv.end());
        for (uint16_t nrt : fv) back_tp[nrt][cid].push_back(uint16_t(prt));
      }
    }

    // Build exact post_crush (ert -> nrt when purple doors close) and transpose to pre_crush
    post_crush.assign(NR, {});
    pre_crush.assign(NR, {});
    int pd_cnt[5]{};
    for (int i = 0; i < N; ++i) if (IS_PD[i]) pd_cnt[bkt_of(i)]++;
    for (int nrt = 0; nrt < NR; ++nrt) {
      auto [nkm, n0, n1, n2, n3] = tp_list[nrt];
      pre_crush[nrt].push_back(uint16_t(nrt));
      if (nkm <= 9) {
        for (int c2 = 0; c2 <= pd_cnt[2]; ++c2)
        for (int c3 = 0; c3 <= pd_cnt[3]; ++c3)
        for (int c4 = 0; c4 <= pd_cnt[4]; ++c4) {
          int tot = c2 + c3 + c4;
          if (tot == 0) continue;
          if (nkm + tot <= 9) {
            int ert = tp_id[nkm + tot][n0][n1][n2 + c2][n3 + c3];
            if (ert >= 0) pre_crush[nrt].push_back(uint16_t(ert));
          } else {
            int k1_10 = use_ortho ? min(9, int(n1) + int(n2)) : int(n1);
            pre_crush[nrt].push_back(uint16_t(tp10_id[n0][k1_10]));
          }
        }
      } else {
        pre_crush[nrt].push_back(uint16_t(tp10_id[n0][n1]));
      }
      auto& v = pre_crush[nrt];
      sort(v.begin(), v.end()); v.erase(unique(v.begin(), v.end()), v.end());
      for (uint16_t ert : v) post_crush[ert].push_back(uint16_t(nrt));
    }

    vector<vector<vector<uint16_t>>> back_tp_crush1(NR, vector<vector<uint16_t>>(ucaps.size()));
    for (int nrt = 0; nrt < NR; ++nrt)
      for (int cid = 0; cid < int(ucaps.size()); ++cid) {
        auto& dst = back_tp_crush1[nrt][cid];
        for (uint16_t ert : pre_crush[nrt])
          for (uint16_t prt : back_tp[ert][cid])
            if (tp_list[prt].k0 >= 7) dst.push_back(prt);
        sort(dst.begin(), dst.end()); dst.erase(unique(dst.begin(), dst.end()), dst.end());
      }

    const uint32_t TOTAL = uint32_t(NR) * NDA * NB * 2;
    dist.assign(TOTAL, 255);
    vector<uint32_t> q; q.reserve(TOTAL / 2);
    for (int rt = 0; rt < NR; ++rt)
      for (int gi = 0; gi < 2; ++gi) {
        int bg = GOALS[gi], dg = GOALS[1 - gi];
        for (int adj = 0; adj <= max_adj[dg]; ++adj)
          for (int ah = 0; ah < 2; ++ah)
            if (valid_u(rt, dg, adj, bg)) {
              uint32_t w = encode(rt, da_id[dg][adj], bg, ah);
              if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
            }
      }
    for (size_t qi = 0; qi < q.size(); ++qi) {
      uint32_t v = q[qi]; uint8_t nd = dist[v] + 1; uint32_t tmp = v;
      int nah = tmp & 1; tmp >>= 1;
      int nbi = tmp % NB; tmp /= NB; int nda = tmp % NDA; tmp /= NDA; int nrt = int(tmp);
      auto [ndi, nadj] = da_list[nda];
      int nao = ao_of(nrt, nbi, ndi);
      auto push_pred = [&](int rt, int di, int adj, int bi, int ah) {
        if (rt < 0 || !valid_u(rt, di, adj, bi)) return;
        uint32_t u = encode(rt, da_id[di][adj], bi, ah);
        if (dist[u] == 255) { dist[u] = nd; q.push_back(u); }
      };
      push_pred(nrt, ndi, nadj, nbi, 1 - nah);
      if (nah == 1) {
        int ndx = ndi % W, ndy = ndi / W;
        for (int d = 0; d < 4; ++d) {
          int px = ndx - DX[d], py = ndy - DY[d];
          if (px < 0 || px >= W || py < 0 || py >= H) continue;
          int pdi = py * W + px;
          for (int padj = 0; padj <= max_adj[pdi]; ++padj) {
            if (ao_of(nrt, nbi, pdi) == 0 && !IS_PD[ndi]) push_pred(nrt, pdi, padj, nbi, 1);
            if (nao == 1) {
              if (ao_of(nrt, nbi, pdi) == 1) push_pred(nrt, pdi, padj, nbi, 1);
            } else {
              for (uint16_t ert : pre_crush[nrt])
                if (ao_of(ert, nbi, pdi) == 1) push_pred(ert, pdi, padj, nbi, 1);
            }
          }
        }
        auto [nkm, n0, n1, n2, n3] = tp_list[nrt];
        for (int d = 0; d < 4; ++d) {
          int tx = ndx + DX[d], ty = ndy + DY[d];
          if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
          int ti = ty * W + tx;
          if (ti == nbi || (IS_PD[ti] && nao == 0)) continue;
          int bk = bkt_of(ti);
          if (!IS_ORIG[ti]) {
            bool ok = (nkm >= 1);
            if (bk == 0 && n0 == 0) ok = false;
            if (!use_ortho) {
              if (bk == 1 && n1 == 0) ok = false;
              if (bk == 2 && nkm <= 9 && n2 == 0) ok = false;
              if (bk == 3 && nkm <= 9 && n3 == 0) ok = false;
              if (bk == 4 && nkm <= 9 && (nkm - n0 - n1 - n2 - n3) == 0) ok = false;
            } else {
              if (nkm <= 9) {
                if (bk == 1 && n1 == 0) ok = false;
                if (bk == 2 && n2 == 0) ok = false;
                if (bk == 3 && n3 == 0) ok = false;
                if (bk == 4 && (nkm - n0 - n1 - n2 - n3) == 0) ok = false;
              } else {
                if ((bk == 1 || bk == 2) && n1 == 0) ok = false;
              }
            }
            if (ok) push_pred(nrt, ndi, nadj, nbi, 1);
          } else {
            if (nadj + 1 <= max_adj[ndi]) {
              if (nkm >= 1 && nkm <= 9) {
                int p2 = int(n2) - (!use_ortho && bk == 2 ? 1 : 0);
                int p3 = int(n3) - (bk == 3 ? 1 : 0);
                if (p2 >= 0 && p3 >= 0 && n0 + n1 + p2 + p3 <= nkm - 1)
                  push_pred(tp_id[nkm - 1][n0][n1][p2][p3], ndi, nadj + 1, nbi, 1);
              } else if (nkm == 10) {
                push_pred(nrt, ndi, nadj + 1, nbi, 1);
                if (!use_ortho) {
                  for (int p2 = 0; n0 + n1 + p2 <= 9; ++p2)
                    for (int p3 = 0; n0 + n1 + p2 + p3 <= 9; ++p3)
                      push_pred(tp_id[9][n0][n1][p2][p3], ndi, nadj + 1, nbi, 1);
                } else {
                  if (n1 < 9) {
                    for (int p1 = 0; p1 <= n1; ++p1) {
                      int p2 = n1 - p1;
                      for (int p3 = 0; n0 + p1 + p2 + p3 <= 9; ++p3)
                        push_pred(tp_id[9][n0][p1][p2][p3], ndi, nadj + 1, nbi, 1);
                    }
                  } else {
                    for (int q1 = 0; n0 + q1 <= 9; ++q1)
                      for (int q2 = 0; n0 + q1 + q2 <= 9; ++q2)
                        if (q1 + q2 >= 9)
                          push_pred(tp_id[9][n0][q1][q2][0], ndi, nadj + 1, nbi, 1);
                  }
                }
              }
            }
            if (nadj >= 1) {
              if (nkm <= 8) {
                int p2 = int(n2) + (!use_ortho && bk == 2 ? 1 : 0);
                int p3 = int(n3) + (bk == 3 ? 1 : 0);
                if (n0 + n1 + p2 + p3 <= nkm + 1)
                  push_pred(tp_id[nkm + 1][n0][n1][p2][p3], ndi, nadj - 1, nbi, 1);
              } else if (nkm == 9) {
                int k1_10 = use_ortho ? min(9, int(n1) + int(n2)) : int(n1);
                push_pred(tp10_id[n0][k1_10], ndi, nadj - 1, nbi, 1);
              } else {
                push_pred(nrt, ndi, nadj - 1, nbi, 1);
              }
            }
          }
        }
      } else {
        auto emit_bard_back = [&](int bi, int nbi_raw, int ndi_raw, int d) {
          bool b_pd = IS_PD[bi] || IS_PD[nbi_raw];
          int ndx = ndi_raw % W, ndy = ndi_raw / W;
          int pdx = ndx - DX[d], pdy = ndy - DY[d];
          int pdi_p = (pdx >= 0 && pdx < W && pdy >= 0 && pdy < H && tst(AURA[bi], pdy * W + pdx)) ? (pdy * W + pdx) : -1;
          if (!b_pd) {
            const auto& prts0 = back_tp[nrt][cap_id_of[bi][d][0]];
            for (uint16_t prt : prts0) {
              if (ao_of(prt, bi, ndi_raw) == 0) push_pred(prt, ndi_raw, nadj, bi, 0);
              if (pdi_p >= 0 && !IS_PD[pdi_p] && !IS_PD[ndi_raw])
                for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
                  if (ao_of(prt, bi, pdi_p) == 0) push_pred(prt, pdi_p, padj, bi, 0);
            }
          }
          if (nao == 1) {
            const auto& prts1 = back_tp[nrt][cap_id_of[bi][d][1]];
            for (uint16_t prt : prts1) {
              if (ao_of(prt, bi, ndi_raw) == 1) push_pred(prt, ndi_raw, nadj, bi, 0);
              if (pdi_p >= 0)
                for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
                  if (ao_of(prt, bi, pdi_p) == 1) push_pred(prt, pdi_p, padj, bi, 0);
            }
          } else {
            for (uint16_t prt : back_tp_crush1[nrt][cap_id_of[bi][d][1]]) {
              if (ao_of(prt, bi, ndi_raw) == 1) push_pred(prt, ndi_raw, nadj, bi, 0);
              if (pdi_p >= 0)
                for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
                  if (ao_of(prt, bi, pdi_p) == 1) push_pred(prt, pdi_p, padj, bi, 0);
            }
          }
        };
        int nbx = nbi % W, nby = nbi / W;
        for (int d = 0; d < 4; ++d) {
          int bx = nbx - DX[d], by = nby - DY[d];
          if (bx >= 0 && bx < W && by >= 0 && by <= 3) emit_bard_back(by * W + bx, nbi, ndi, d);
        }
        if (nby == 2) emit_bard_back(3 * W + nbx, 4 * W + nbx, mirror_y_cell(ndi), 1);
      }
    }
    reachable_count = q.size();
  }

  QuotientAuditStats audit_all_forward_edges(int num_threads = 10) const {
    QuotientAuditStats out{};
    out.vertices = uint64_t(NR) * NDA * NB * 2;
    out.reachable = reachable_count;
    for (int rt = 0; rt < NR; ++rt)
      for (int gi = 0; gi < 2; ++gi) {
        int bg = GOALS[gi], dg = GOALS[1 - gi];
        for (int adj = 0; adj <= max_adj[dg]; ++adj)
          for (int ah = 0; ah < 2; ++ah)
            if (valid_u(rt, dg, adj, bg)) {
              out.goals++;
              if (dist[encode(rt, da_id[dg][adj], bg, ah)] != 0) out.goal_violations++;
            }
      }

    vector<uint64_t> t_edges(num_threads, 0), t_viols(num_threads, 0);
    vector<thread> workers;
    for (int tid = 0; tid < num_threads; ++tid) {
      workers.emplace_back([&, tid]() {
        uint64_t loc_e = 0, loc_v = 0;
        for (int rt = tid; rt < NR; rt += num_threads) {
          auto [km, k0, k1, k2, k3] = tp_list[rt];
          for (int da = 0; da < NDA; ++da) {
            auto [di, adj] = da_list[da];
            int dx = di % W, dy = di / W;
            for (int bi = 0; bi < NB; ++bi) {
              if (!valid_u(rt, di, adj, bi)) continue;
              int bx = bi % W, by = bi / W;
              int pre_ao = ao_of(rt, bi, di);
              auto check_to = [&](int du, int nrt, int ndi, int nadj, int nbi_raw, int nah) {
                int nbi = nbi_raw, c_ndi = ndi;
                if (nbi >= NB) { nbi = mirror_y_cell(nbi); c_ndi = mirror_y_cell(c_ndi); }
                if (nrt < 0 || !valid_u(nrt, c_ndi, nadj, nbi)) return;
                uint32_t v = encode(nrt, da_id[c_ndi][nadj], nbi, nah);
                int dv = (dist[v] == 255) ? 999 : int(dist[v]);
                loc_e++;
                if (du > 1 + dv) loc_v++;
              };

              // ah == 1 + 'A'
              {
                int du1 = (dist[encode(rt, da, bi, 1)] == 255) ? 999 : int(dist[encode(rt, da, bi, 1)]);
                check_to(du1, rt, di, adj, bi, 0);
                for (int d = 0; d < 4; ++d) {
                  int tx = dx + DX[d], ty = dy + DY[d];
                  if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                  int ti = ty * W + tx;
                  if (ti == bi || (pre_ao == 0 && IS_PD[ti])) continue;
                  // Walk di -> ti
                  if (pre_ao == 0) {
                    if (!IS_PD[ti])
                      for (int nadj = 0; nadj <= max_adj[ti]; ++nadj) check_to(du1, rt, ti, nadj, bi, 1);
                  } else {
                    if (ao_of(rt, bi, ti) == 1) {
                      for (int nadj = 0; nadj <= max_adj[ti]; ++nadj) check_to(du1, rt, ti, nadj, bi, 1);
                    } else if (!IS_PD[bi] && !IS_PD[ti]) {
                      for (uint16_t nrt : post_crush[rt])
                        if (ao_of(nrt, bi, ti) == 0)
                          for (int nadj = 0; nadj <= max_adj[ti]; ++nadj) check_to(du1, nrt, ti, nadj, bi, 1);
                    }
                  }
                  // Toggle ti (leaves weighing & ao identical!)
                  int bk = bkt_of(ti);
                  if (!IS_ORIG[ti]) {
                    bool ok = (km >= 1);
                    if (bk == 0 && k0 == 0) ok = false;
                    if (!use_ortho) {
                      if (bk == 1 && k1 == 0) ok = false;
                      if (bk == 2 && km <= 9 && k2 == 0) ok = false;
                      if (bk == 3 && km <= 9 && k3 == 0) ok = false;
                      if (bk == 4 && km <= 9 && (km - k0 - k1 - k2 - k3) == 0) ok = false;
                    } else {
                      if (km <= 9) {
                        if (bk == 1 && k1 == 0) ok = false;
                        if (bk == 2 && k2 == 0) ok = false;
                        if (bk == 3 && k3 == 0) ok = false;
                        if (bk == 4 && (km - k0 - k1 - k2 - k3) == 0) ok = false;
                      } else {
                        if ((bk == 1 || bk == 2) && k1 == 0) ok = false;
                      }
                    }
                    if (ok) check_to(du1, rt, di, adj, bi, 1);
                  } else {
                    // Harvest border wall (adj -> adj - 1, km -> km + 1)
                    if (adj >= 1) {
                      if (km <= 8) {
                        int n2 = int(k2) + (!use_ortho && bk == 2 ? 1 : 0);
                        int n3 = int(k3) + (bk == 3 ? 1 : 0);
                        check_to(du1, tp_id[km + 1][k0][k1][n2][n3], di, adj - 1, bi, 1);
                      } else if (km == 9) {
                        int k1_10 = use_ortho ? min(9, int(k1) + int(k2)) : int(k1);
                        check_to(du1, tp10_id[k0][k1_10], di, adj - 1, bi, 1);
                      } else {
                        check_to(du1, rt, di, adj - 1, bi, 1);
                      }
                    }
                    // Un-harvest border crate (adj -> adj + 1, km -> km - 1)
                    if (adj + 1 <= max_adj[di]) {
                      if (km >= 1 && km <= 9) {
                        int n2 = int(k2) - (!use_ortho && bk == 2 ? 1 : 0);
                        int n3 = int(k3) - (bk == 3 ? 1 : 0);
                        if (n2 >= 0 && n3 >= 0)
                          check_to(du1, tp_id[km - 1][k0][k1][n2][n3], di, adj + 1, bi, 1);
                      } else if (km == 10) {
                        check_to(du1, rt, di, adj + 1, bi, 1);
                        if (!use_ortho) {
                          for (int n2 = 0; k0 + k1 + n2 <= 9; ++n2)
                            for (int n3 = 0; k0 + k1 + n2 + n3 <= 9; ++n3)
                              check_to(du1, tp_id[9][k0][k1][n2][n3], di, adj + 1, bi, 1);
                        } else {
                          if (k1 < 9) {
                            for (int n1 = 0; n1 <= k1; ++n1)
                              for (int n3 = 0; k0 + k1 + n3 <= 9; ++n3)
                                check_to(du1, tp_id[9][k0][n1][k1 - n1][n3], di, adj + 1, bi, 1);
                          } else {
                            for (int n1 = 0; k0 + n1 <= 9; ++n1)
                              for (int n2 = 0; k0 + n1 + n2 <= 9; ++n2)
                                if (n1 + n2 >= 9)
                                  check_to(du1, tp_id[9][k0][n1][n2][0], di, adj + 1, bi, 1);
                          }
                        }
                      }
                    }
                  }
                }
              }

              // ah == 0 + 'A'
              {
                int du0 = (dist[encode(rt, da, bi, 0)] == 255) ? 999 : int(dist[encode(rt, da, bi, 0)]);
                check_to(du0, rt, di, adj, bi, 1);
                for (int d = 0; d < 4; ++d) {
                  int nbx = bx + DX[d], nby = by + DY[d];
                  if (nbx < 0 || nbx >= W || nby < 0 || nby >= H) continue;
                  int nbi_raw = nby * W + nbx;
                  if (pre_ao == 0 && (IS_PD[bi] || IS_PD[nbi_raw])) continue;
                  int cid = cap_id_of[bi][d][pre_ao];
                  int ndi_cands[2] = {di, -1}, n_nd = 1;
                  if (tst(AURA[bi], di)) {
                    int ndx = dx + DX[d], ndy = dy + DY[d];
                    if (ndx >= 0 && ndx < W && ndy >= 0 && ndy < H && !(pre_ao == 0 && IS_PD[ndy * W + ndx]))
                      ndi_cands[n_nd++] = ndy * W + ndx;
                  }
                  for (uint16_t ert : fwd_tp[rt][cid]) {
                    for (int ni_k = 0; ni_k < n_nd; ++ni_k) {
                      int ndi = ndi_cands[ni_k];
                      if (ndi == nbi_raw) continue;
                      int nadj_lo = (ndi == di) ? adj : 0;
                      int nadj_hi = (ndi == di) ? adj : max_adj[ndi];
                      int c_nbi = (nbi_raw < NB) ? nbi_raw : mirror_y_cell(nbi_raw);
                      int c_ndi = (nbi_raw < NB) ? ndi : mirror_y_cell(ndi);
                      if (pre_ao == 0) {
                        for (int nadj = nadj_lo; nadj <= nadj_hi; ++nadj)
                          if (ao_of(ert, c_nbi, c_ndi) == 0 || ao_of(ert, c_nbi, c_ndi) == 1)
                            check_to(du0, ert, ndi, nadj, nbi_raw, 0);
                      } else {
                        if (ao_of(ert, c_nbi, c_ndi) == 1) {
                          for (int nadj = nadj_lo; nadj <= nadj_hi; ++nadj)
                            check_to(du0, ert, ndi, nadj, nbi_raw, 0);
                        } else if (!IS_PD[nbi_raw] && !IS_PD[ndi]) {
                          for (uint16_t nrt : post_crush[ert])
                            if (ao_of(nrt, c_nbi, c_ndi) == 0)
                              for (int nadj = nadj_lo; nadj <= nadj_hi; ++nadj)
                                check_to(du0, nrt, ndi, nadj, nbi_raw, 0);
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        t_edges[tid] = loc_e;
        t_viols[tid] = loc_v;
      });
    }
    for (auto& th : workers) th.join();
    for (int t = 0; t < num_threads; ++t) {
      out.forward_edges_checked += t_edges[t];
      out.step_violations += t_viols[t];
    }
    return out;
  }

  inline int lookup(const CState& s_in) const {
    CState s = (s_in.by <= 3) ? s_in : mirror_y_state(s_in);
    u128 act = s.crates | (s.walls & ~ORIGIN_MASK);
    int km = min(10, popcnt128(act));
    int c0 = 0, c1 = 0, c2 = 0, c3 = 0;
    if (!use_ortho) {
      c0 = popcnt128(act & D5_MASK[0]);
      c1 = min(9, popcnt128(act & D5_MASK[1]));
      if (km <= 9) { c2 = popcnt128(act & D5_MASK[2]); c3 = popcnt128(act & D5_MASK[3]); }
    } else {
      u128 m = act;
      while (m) {
        int idx = (uint64_t)m ? __builtin_ctzll((uint64_t)m) : (64 + __builtin_ctzll((uint64_t)(m >> 64)));
        m &= ~bit(idx);
        int b = O5_BKT[idx];
        if (b == 0) c0++; else if (b == 1) c1++; else if (b == 2) c2++; else if (b == 3) c3++;
      }
    }
    int rt = (km <= 9) ? tp_id[km][c0][c1][c2][c3] : tp10_id[c0][use_ortho ? min(9, c1 + c2) : c1];
    int di = s.dy * W + s.dx, bi = s.by * W + s.bx;
    int adj = popcnt128(s.walls & ORIGIN_MASK & ORTHO[di]);
    uint8_t d = dist[encode(rt, da_id[di][adj], bi, s.ah)];
    return d == 255 ? 999 : int(d);
  }
};

// Construct exact soko#38 counterexample state in CState!
static CState make_soko38_state() {
  const char* rows[7] = {
      "#####.#########",
      "#.............#",
      "**#*}}}.]]]]].#",
      "D#*5*}}.]G.G].#",
      "...**}*#]]]]].#",
      "..............#",
      "#......########",
  };
  CState s{}; s.crates = 0; s.walls = 0; s.ah = 1; s.doors_open = 0;
  for (int y = 0; y < 7; ++y)
    for (int x = 0; x < 15; ++x) {
      char c = rows[y][x]; int i = y * W + x;
      if (c == '*') s.crates |= bit(i);
      else if (c == '#') s.walls |= bit(i);
      else if (c == '5') { s.bx = uint8_t(x); s.by = uint8_t(y); }
      else if (c == 'D') { s.dx = uint8_t(x); s.dy = uint8_t(y); }
    }
  return s;
}

struct CandEdge {
  Packed15 np;
  CState ns;
  uint8_t hs, ng;
};

struct LayerRecord {
  int f_completed;
  int certified_floor;
  uint64_t cumulative_expanded;
  uint64_t cumulative_unique_canon_states;
  uint64_t cumulative_edges_checked;
  uint64_t cumulative_hash_collisions_prevented;
  double elapsed_s;
};

int main(int argc, char** argv) {
  cout << unitbuf;
  bool self_test_only = false;
  uint64_t target_walk_edges = 52000000ULL;
  size_t max_total_states = 665600000ULL; // 256 * 2.6M (~21.3 GiB)
  double time_limit = 180.0;
  string json_out_path = "";
  string source_path = "";

  for (int i = 1; i < argc; ++i) {
    string arg = argv[i];
    if (arg == "--self-test") {
      self_test_only = true;
      target_walk_edges = 2000000ULL;
      max_total_states = 4096000ULL;
      time_limit = 15.0;
    } else if (arg == "--walk-edges" && i + 1 < argc) {
      target_walk_edges = stoull(argv[++i]);
    } else if (arg == "--max-states" && i + 1 < argc) {
      max_total_states = stoull(argv[++i]);
    } else if (arg == "--time-limit" && i + 1 < argc) {
      time_limit = stod(argv[++i]);
    } else if (arg == "--json-out" && i + 1 < argc) {
      json_out_path = argv[++i];
    } else if (arg == "--source-path" && i + 1 < argc) {
      source_path = argv[++i];
    }
  }

  auto t_program_start = chrono::steady_clock::now();
  init_topology();

  // Compute canonical board_sha256_lf dynamically from GRID_III14 (zero hardcoded SHA literals!)
  string board_lf;
  for (int y = 0; y < H; ++y) {
    if (y > 0) board_lf += "\n";
    board_lf += GRID_III14[y];
  }
  string board_sha256_lf = Sha256::hex(board_lf);

  string prover_source_sha256 = "";
  if (!source_path.empty()) {
    ifstream f(source_path, ios::binary);
    if (f) {
      ostringstream ss; ss << f.rdbuf();
      prover_source_sha256 = Sha256::hex(ss.str());
    }
  }

  cout << "[INIT] Canonical 15x7 Room III-14 board_sha256_lf = " << board_sha256_lf << "\n";

  // Build all 4 verified Quotient PDBs
  auto t_build = chrono::steady_clock::now();
  Switch3x3_15PDB pdb_sw9;
  pdb_sw9.build(10);
  HarvestAdj15PDB pdb_ha;
  OrthoFlow5_15PDB pdb_rf5, pdb_o5;
  {
    thread t1([&]() { pdb_rf5.build(false); });
    thread t2([&]() { pdb_o5.build(true); });
    thread t3([&]() { pdb_ha.build(); });
    t1.join(); t2.join(); t3.join();
  }
  double build_s = chrono::duration<double>(chrono::steady_clock::now() - t_build).count();
  cout << "[BUILD] Built Switch3x3 + OrthoFlow5 + RingFlow5 + HarvestAdj in "
       << fixed << setprecision(2) << build_s << "s\n";

  auto eval_h = [&](const CState& s) -> uint8_t {
    CState ms = mirror_y_state(s);
    int h = max({
        pdb_sw9.lookup_plus_harvest(s),
        pdb_o5.lookup(s),
        pdb_rf5.lookup(s),
        pdb_ha.lookup(s),
        pdb_ha.lookup(ms),
    });
    return uint8_t(min(250, h));
  };

  // ==========================================================================
  // STAGE 1: 100% Exhaustive Forward Quotient-Graph Edge Verification
  // ==========================================================================
  auto t_qaudit = chrono::steady_clock::now();
  QuotientAuditStats q_sw9 = pdb_sw9.audit_all_forward_edges(10);
  QuotientAuditStats q_ha = pdb_ha.audit_all_forward_edges(10);
  QuotientAuditStats q_rf5 = pdb_rf5.audit_all_forward_edges(10);
  QuotientAuditStats q_o5 = pdb_o5.audit_all_forward_edges(10);
  double qaudit_s = chrono::duration<double>(chrono::steady_clock::now() - t_qaudit).count();

  cout << "[QUOTIENT AUDIT] sw9: edges=" << q_sw9.forward_edges_checked << " viol=" << (q_sw9.goal_violations + q_sw9.step_violations)
       << " | ha: edges=" << q_ha.forward_edges_checked << " viol=" << (q_ha.goal_violations + q_ha.step_violations)
       << " | rf5: edges=" << q_rf5.forward_edges_checked << " viol=" << (q_rf5.goal_violations + q_rf5.step_violations)
       << " | o5: edges=" << q_o5.forward_edges_checked << " viol=" << (q_o5.goal_violations + q_o5.step_violations)
       << " (" << fixed << setprecision(2) << qaudit_s << "s)\n";

  require_check(q_sw9.goal_violations == 0 && q_sw9.step_violations == 0, "Switch3x3 quotient edge audit failed");
  require_check(q_ha.goal_violations == 0 && q_ha.step_violations == 0, "HarvestAdj quotient edge audit failed");
  require_check(q_rf5.goal_violations == 0 && q_rf5.step_violations == 0, "RingFlow5 quotient edge audit failed");
  require_check(q_o5.goal_violations == 0 && q_o5.step_violations == 0, "OrthoFlow5 quotient edge audit failed");

  // ==========================================================================
  // STAGE 2: Non-Tautological `must_fail` Controls Executing Real Verifiers
  // ==========================================================================
  bool mf_sticky34_rejected = false;
  {
    const string BAD34 = "LULULUULRURRURURUALDRRUDRRUDDRURRR";
    CState cur = start_state();
    int steps_ok = 0;
    for (char ch : BAD34) {
      CState nxt;
      if (!step_concrete(cur, int(string("UDLRA").find(ch)), nxt)) break;
      cur = nxt; steps_ok++;
    }
    mf_sticky34_rejected = (steps_ok == 29);
  }
  require_check(mf_sticky34_rejected, "must_fail control 1 (sticky-door 34 route) failed to reject at step 30");

  bool mf_quotient_drop_caught = false;
  {
    // Temporarily corrupt one reachable HarvestAdj entry by +2 and confirm `audit_all_forward_edges` catches it!
    uint32_t s0_idx = pdb_ha.encode(0, 0, pdb_ha.da_id[D0][pdb_ha.max_adj[D0]], HarvestAdj15PDB::b_loc_of(B0 % W, B0 / W), 1, 0);
    uint8_t saved = pdb_ha.dist[s0_idx];
    pdb_ha.dist[s0_idx] = uint8_t(saved + 2);
    QuotientAuditStats bad_q = pdb_ha.audit_all_forward_edges(10);
    pdb_ha.dist[s0_idx] = saved;
    mf_quotient_drop_caught = (bad_q.step_violations > 0);
  }
  require_check(mf_quotient_drop_caught, "must_fail control 2 (planted +2 quotient inconsistency) was not caught");

  // Check exact soko#38 counterexample state (`D` at (0,3) pressing 'R' -> (1,3) '#' -> '*')
  CState s38_before = make_soko38_state();
  CState s38_after{};
  require_check(step_concrete(s38_before, 3, s38_after), "soko#38 action 'R' must be legal");
  int h_s38_before = int(eval_h(s38_before));
  int h_s38_after = int(eval_h(s38_after));
  require_check(h_s38_before - h_s38_after <= 1, "soko#38 state violated 1-step consistency under eval_h");

  // Concrete edge checker lambda (used on real eval_h AND on planted-bug eval_fn for must_fail control 3!)
  auto check_concrete_edge_fn = [&](const CState& st, const function<int(const CState&)>& hfn, uint64_t& e_cnt) -> uint64_t {
    uint64_t v = 0;
    int hs = hfn(st);
    if (is_win(st) && hs != 0) v++;
    for (int mv = 0; mv < 5; ++mv) {
      CState nx;
      if (step_concrete(st, mv, nx)) {
        e_cnt++;
        if (hs > 1 + hfn(nx)) v++;
      }
    }
    return v;
  };

  bool mf_soko38_drop2_caught = false;
  {
    Packed15 pk38 = pack_canon(s38_before);
    uint64_t dummy_e = 0;
    uint64_t bad_v = check_concrete_edge_fn(
        s38_before,
        [&](const CState& x) -> int { return (pack_canon(x) == pk38) ? (h_s38_after + 2) : int(eval_h(x)); },
        dummy_e
    );
    mf_soko38_drop2_caught = (bad_v > 0);
  }
  require_check(mf_soko38_drop2_caught, "must_fail control 3 (planted soko#38 2-step drop) was not caught");

  // R48 & W41 admissibility + exact tail check + must_fail control 4 (planted +1 tail overestimate)
  bool mf_overestimate_caught = false;
  for (const string& witness : {R48_ROUTE, W41_ROUTE}) {
    CState cur = start_state();
    for (size_t t = 0; t < witness.size(); ++t) {
      int ht = int(eval_h(cur));
      require_check(int(t) + ht <= int(witness.size()), "Admissibility violated on 48-key witness");
      CState nxt;
      require_check(step_concrete(cur, int(string("UDLRA").find(witness[t])), nxt), "Witness step failed");
      require_check(ht <= 1 + int(eval_h(nxt)), "Step consistency violated on 48-key witness");
      if (witness == R48_ROUTE && t == 42) {
        int exact_rem = int(witness.size() - t);
        int planted_h = exact_rem + 1;
        mf_overestimate_caught = (planted_h > exact_rem);
      }
      cur = nxt;
    }
    require_check(is_win(cur) && eval_h(cur) == 0, "Witness did not end in h==0 win");
  }
  // Make must_fail_4 exercise a real exact-BFS oracle distance comparator on R48[40]!
  {
    CState s40 = start_state();
    for (int t = 0; t < 40; ++t) { CState nx; step_concrete(s40, int(string("UDLRA").find(R48_ROUTE[t])), nx); s40 = nx; }
    // Compute exact BFS distance d*(s40)
    vector<CState> q{s40};
    vector<int> qd{0};
    vector<Packed15> seen{pack_canon(s40)};
    int dstar40 = -1;
    for (size_t qi = 0; qi < q.size() && dstar40 < 0; ++qi) {
      if (qd[qi] >= 9) break;
      for (int mv = 0; mv < 5; ++mv) {
        CState nx;
        if (!step_concrete(q[qi], mv, nx)) continue;
        if (is_win(nx)) { dstar40 = qd[qi] + 1; break; }
        Packed15 pk = pack_canon(nx);
        if (find(seen.begin(), seen.end(), pk) == seen.end()) {
          seen.push_back(pk); q.push_back(nx); qd.push_back(qd[qi] + 1);
        }
      }
    }
    auto verify_admissible_at = [&](int candidate_h, int exact_d) -> bool { return exact_d >= 0 && candidate_h <= exact_d; };
    require_check(dstar40 == 8 && verify_admissible_at(int(eval_h(s40)), dstar40), "Exact BFS check at R48[40] failed");
    mf_overestimate_caught = !verify_admissible_at(int(eval_h(s40)) + 1, dstar40);
  }
  require_check(mf_overestimate_caught, "must_fail control 4 (planted +1 overestimate at R48[40]) was not caught");

  // ==========================================================================
  // STAGE 3: 50,000,000+ Concrete Random-Walk + soko#38 Edge Consistency Audit
  // ==========================================================================
  auto t_walk = chrono::steady_clock::now();
  uint64_t concrete_walk_edges = 0, concrete_walk_viols = 0;
  {
    // Include soko#38 state explicitly first
    concrete_walk_viols += check_concrete_edge_fn(s38_before, [&](const CState& x) { return int(eval_h(x)); }, concrete_walk_edges);
    concrete_walk_viols += check_concrete_edge_fn(s38_after, [&](const CState& x) { return int(eval_h(x)); }, concrete_walk_edges);

    const int NT = 10;
    uint64_t per_thread_target = (target_walk_edges + NT - 1) / NT;
    vector<uint64_t> te(NT, 0), tv(NT, 0);
    vector<thread> workers;
    for (int tid = 0; tid < NT; ++tid) {
      workers.emplace_back([&, tid]() {
        mt19937_64 rng(20261119ULL + uint64_t(tid) * 1337ULL);
        uint64_t loc_e = 0, loc_v = 0;
        while (loc_e < per_thread_target) {
          CState s = start_state();
          int mode = int(rng() % 4);
          if (mode == 1) {
            int pre = int(rng() % 49);
            for (int k = 0; k < pre; ++k) {
              CState nx; step_concrete(s, int(string("UDLRA").find(R48_ROUTE[k])), nx); s = nx;
            }
          } else if (mode == 2) {
            s = s38_before;
          }
          for (int step = 0; step < 300 && loc_e < per_thread_target; ++step) {
            int hs = int(eval_h(s));
            if (is_win(s) && hs != 0) loc_v++;
            CState nx[5]; int ok[5], nok = 0;
            for (int mv = 0; mv < 5; ++mv) {
              if (step_concrete(s, mv, nx[mv])) {
                loc_e++;
                int hn = int(eval_h(nx[mv]));
                if (hs > 1 + hn) loc_v++;
                if (!is_win(nx[mv])) ok[nok++] = mv;
              }
            }
            if (!nok) break;
            s = nx[ok[rng() % nok]];
          }
        }
        te[tid] = loc_e;
        tv[tid] = loc_v;
      });
    }
    for (auto& th : workers) th.join();
    for (int t = 0; t < NT; ++t) { concrete_walk_edges += te[t]; concrete_walk_viols += tv[t]; }
  }
  double walk_s = chrono::duration<double>(chrono::steady_clock::now() - t_walk).count();
  cout << "[CONCRETE WALK AUDIT] edges_checked=" << concrete_walk_edges
       << " violations=" << concrete_walk_viols << " (" << fixed << setprecision(2) << walk_s << "s)\n";
  require_check(concrete_walk_viols == 0, "Concrete random-walk edge audit found consistency violation!");

  // ==========================================================================
  // STAGE 4: 10-Thread 256-Shard Collision-Free Layered A* Search
  // ==========================================================================
  CState s0 = start_state();
  uint8_t h0 = eval_h(s0);
  cout << "[ROOT] h(s0)=" << int(h0)
       << " [sw9+need9=" << pdb_sw9.lookup_plus_harvest(s0)
       << ", o5=" << pdb_o5.lookup(s0)
       << ", rf5=" << pdb_rf5.lookup(s0)
       << ", ha=" << max(pdb_ha.lookup(s0), pdb_ha.lookup(mirror_y_state(s0)))
       << "] | soko#38 h: " << h_s38_before << " -> " << h_s38_after << "\n";

  constexpr int NSHARDS = 256;
  constexpr int NT = 10;
  size_t max_per_shard = max<size_t>(16384, max_total_states / NSHARDS);
  size_t shard_hbits = 16;
  while ((1ULL << shard_hbits) < max_per_shard * 2) shard_hbits++;
  size_t shard_hmask = (1ULL << shard_hbits) - 1;

  struct Shard {
    vector<Packed15> states;
    vector<uint8_t> best_g, state_h;
    vector<uint32_t> htab;
    uint64_t collisions = 0;
    void init(size_t hbits, size_t res_cap) {
      states.reserve(min<size_t>(res_cap, 500000));
      best_g.reserve(min<size_t>(res_cap, 500000));
      state_h.reserve(min<size_t>(res_cap, 500000));
      htab.assign(1ULL << hbits, UINT32_MAX);
    }
  };
  vector<Shard> shards(NSHARDS);
  {
    vector<thread> th;
    for (int t = 0; t < NT; ++t) th.emplace_back([&, t]() {
      for (int sh = t; sh < NSHARDS; sh += NT) shards[sh].init(shard_hbits, max_per_shard);
    });
    for (auto& x : th) x.join();
  }

  vector<vector<uint64_t>> waves[60];
  for (int f = 0; f < 60; ++f) waves[f].resize(60);

  Packed15 p0 = pack_canon(s0);
  uint64_t h64_0 = p0.hash64();
  int sh0 = int(h64_0 >> 56);
  shards[sh0].states.push_back(p0);
  shards[sh0].best_g.push_back(0);
  shards[sh0].state_h.push_back(h0);
  shards[sh0].htab[h64_0 & shard_hmask] = 0;
  waves[h0][0].push_back((uint64_t(sh0) << 32) | 0ULL);

  auto t_astar = chrono::steady_clock::now();
  uint64_t expanded = 0, astar_edge_checks = 0, astar_bellman_viols = 0;
  int proven_floor = int(h0);
  bool hit_cap = false;
  bool exact_opt = false;
  string stop_reason = "completed_all_layers";
  vector<LayerRecord> layer_ledger;
  vector<array<vector<CandEdge>, NSHARDS>> t_sh_buf(NT);

  for (int f = h0; f <= 48 && !hit_cap; ++f) {
    proven_floor = f;
    for (int g = 0; g <= f && !hit_cap; ++g) {
      auto& wvec = waves[f][g];
      if (wvec.empty()) continue;
      vector<uint64_t> active;
      active.reserve(wvec.size());
      for (uint64_t gid : wvec) {
        int sh = int(gid >> 32); uint32_t lid = uint32_t(gid);
        if (shards[sh].best_g[lid] == g && int(g) + int(shards[sh].state_h[lid]) == f)
          active.push_back(gid);
      }
      vector<uint64_t>().swap(wvec);
      if (active.empty()) continue;

      const size_t CHUNK = 1000000;
      for (size_t base = 0; base < active.size() && !hit_cap; base += CHUNK) {
        if (chrono::duration<double>(chrono::steady_clock::now() - t_astar).count() > time_limit) {
          hit_cap = true; stop_reason = "time_limit_during_layer_" + to_string(f); break;
        }
        size_t cnt = min(CHUNK, active.size() - base);
        atomic<bool> found_win{false};
        vector<uint64_t> t_edges(NT, 0);
        {
          vector<thread> th;
          for (int tid = 0; tid < NT; ++tid) {
            th.emplace_back([&, tid]() {
              for (int sh = 0; sh < NSHARDS; ++sh) t_sh_buf[tid][sh].clear();
              size_t lo = (cnt * tid) / NT, hi = (cnt * (tid + 1)) / NT;
              uint64_t loc_e = 0;
              for (size_t idx = lo; idx < hi; ++idx) {
                uint64_t gid = active[base + idx];
                int sh = int(gid >> 32); uint32_t lid = uint32_t(gid);
                uint8_t hs = shards[sh].state_h[lid];
                CState s = unpack15(shards[sh].states[lid]);
                for (int mv = 0; mv < 5; ++mv) {
                  CState ns;
                  if (!step_concrete(s, mv, ns)) continue;
                  if (is_win(ns)) { found_win.store(true); return; }
                  Packed15 np = pack_canon(ns);
                  int nsh = int(np.hash64() >> 56);
                  t_sh_buf[tid][nsh].push_back(CandEdge{np, ns, hs, uint8_t(g + 1)});
                  loc_e++;
                }
              }
              t_edges[tid] = loc_e;
            });
          }
          for (auto& x : th) x.join();
        }
        if (found_win.load()) {
          cout << "  [EXACT OPTIMUM REACHED AT g=" << (g + 1) << "]\n";
          proven_floor = g + 1; exact_opt = true; hit_cap = true; stop_reason = "exact_optimum_reached"; break;
        }
        expanded += cnt;
        for (int t = 0; t < NT; ++t) astar_edge_checks += t_edges[t];

        atomic<uint64_t> loc_viols{0};
        atomic<bool> shard_full{false};
        vector<array<vector<uint64_t>, 60>> t_new_waves(NT);
        {
          vector<thread> th;
          for (int tid = 0; tid < NT; ++tid) {
            th.emplace_back([&, tid]() {
              for (int sh = tid; sh < NSHARDS; sh += NT) {
                auto& S = shards[sh];
                for (int src_t = 0; src_t < NT; ++src_t) {
                  for (const CandEdge& ce : t_sh_buf[src_t][sh]) {
                    size_t sl = ce.np.hash64() & shard_hmask;
                    uint32_t eid = UINT32_MAX;
                    while (S.htab[sl] != UINT32_MAX) {
                      uint32_t cand = S.htab[sl];
                      if (S.states[cand] == ce.np) { eid = cand; break; }
                      S.collisions++;
                      sl = (sl + 1) & shard_hmask;
                    }
                    uint8_t hns = (eid != UINT32_MAX) ? S.state_h[eid] : eval_h(ce.ns);
                    if (int(ce.hs) > 1 + int(hns)) { loc_viols++; return; }
                    int nf = int(ce.ng) + int(hns);
                    if (nf > 48) continue;
                    if (eid != UINT32_MAX) {
                      if (ce.ng < S.best_g[eid]) {
                        S.best_g[eid] = ce.ng;
                        t_new_waves[tid][nf].push_back((uint64_t(sh) << 32) | eid);
                      }
                    } else {
                      if (S.states.size() >= max_per_shard) { shard_full.store(true); return; }
                      uint32_t nid = uint32_t(S.states.size());
                      S.states.push_back(ce.np);
                      S.best_g.push_back(ce.ng);
                      S.state_h.push_back(hns);
                      S.htab[sl] = nid;
                      t_new_waves[tid][nf].push_back((uint64_t(sh) << 32) | nid);
                    }
                  }
                }
              }
            });
          }
          for (auto& x : th) x.join();
        }
        astar_bellman_viols += loc_viols.load();
        require_check(astar_bellman_viols == 0, "Bellman 1-step violation detected during layered A*!");
        if (shard_full.load()) {
          hit_cap = true; stop_reason = "state_cap_during_layer_" + to_string(f); break;
        }
        for (int tid = 0; tid < NT; ++tid)
          for (int nf = f; nf <= 48; ++nf)
            if (!t_new_waves[tid][nf].empty())
              waves[nf][g + 1].insert(waves[nf][g + 1].end(), t_new_waves[tid][nf].begin(), t_new_waves[tid][nf].end());
      }
    }
    if (!hit_cap) {
      uint64_t tot_st = 0, tot_col = 0;
      for (int sh = 0; sh < NSHARDS; ++sh) { tot_st += shards[sh].states.size(); tot_col += shards[sh].collisions; }
      double el = chrono::duration<double>(chrono::steady_clock::now() - t_astar).count();
      proven_floor = f + 1;
      layer_ledger.push_back(LayerRecord{f, proven_floor, expanded, tot_st, astar_edge_checks, tot_col, el});
      cout << "  [CERTIFIED 15x7 FLOOR >= " << proven_floor << "] f=" << f
           << " expanded=" << expanded << " unique_canon_states=" << tot_st
           << " edges_checked=" << astar_edge_checks << " collisions_prevented=" << tot_col
           << " time=" << fixed << setprecision(2) << el << "s\n";
    }
  }

  uint64_t final_unique_states = 0, final_collisions = 0;
  for (int sh = 0; sh < NSHARDS; ++sh) {
    final_unique_states += shards[sh].states.size();
    final_collisions += shards[sh].collisions;
  }
  double astar_s = chrono::duration<double>(chrono::steady_clock::now() - t_astar).count();
  double total_s = chrono::duration<double>(chrono::steady_clock::now() - t_program_start).count();

  string status_str = exact_opt ? "VERIFIED" : "LOWER_BOUND_UNWITNESSED";
  cout << "[SUMMARY] status=" << status_str
       << " certified_15x7_floor=" << proven_floor
       << " stop_reason=" << stop_reason
       << " expanded=" << expanded
       << " unique_canon_states=" << final_unique_states
       << " astar_edges=" << astar_edge_checks
       << " bellman_violations=" << astar_bellman_viols
       << " total_time=" << fixed << setprecision(2) << total_s << "s\n";

  if (!json_out_path.empty()) {
    ofstream jf(json_out_path);
    require_check(bool(jf), "Failed to open --json-out path for writing");
    uint64_t total_q_edges = q_sw9.forward_edges_checked + q_ha.forward_edges_checked +
                             q_rf5.forward_edges_checked + q_o5.forward_edges_checked;
    jf << "{\n"
       << "  \"epistemic_status\": \"" << status_str << "\",\n"
       << "  \"room_id\": \"III-14-15x7\",\n"
       << "  \"board_sha256_lf\": \"" << board_sha256_lf << "\",\n"
       << "  \"prover_source_sha256\": \"" << prover_source_sha256 << "\",\n"
       << "  \"self_test_mode\": " << (self_test_only ? "true" : "false") << ",\n"
       << "  \"exact_optimum_reached\": " << (exact_opt ? "true" : "false") << ",\n"
       << "  \"certified_15x7_floor\": " << proven_floor << ",\n"
       << "  \"root_h_s0\": " << int(h0) << ",\n"
       << "  \"soko38_counterexample_check\": {\n"
       << "    \"h_before\": " << h_s38_before << ",\n"
       << "    \"h_after\": " << h_s38_after << ",\n"
       << "    \"step_drop\": " << (h_s38_before - h_s38_after) << ",\n"
       << "    \"consistent\": " << ((h_s38_before - h_s38_after <= 1) ? "true" : "false") << "\n"
       << "  },\n"
       << "  \"exhaustive_quotient_edge_audit\": {\n"
       << "    \"epistemic_status\": \"VERIFIED\",\n"
       << "    \"total_forward_quotient_edges_checked\": " << total_q_edges << ",\n"
       << "    \"total_violations\": 0,\n"
       << "    \"switch3x3_pdb\": {\"vertices\": " << q_sw9.vertices << ", \"reachable\": " << q_sw9.reachable
       << ", \"forward_edges\": " << q_sw9.forward_edges_checked << ", \"violations\": 0},\n"
       << "    \"harvest_adj_pdb\": {\"vertices\": " << q_ha.vertices << ", \"reachable\": " << q_ha.reachable
       << ", \"forward_edges\": " << q_ha.forward_edges_checked << ", \"violations\": 0},\n"
       << "    \"ringflow5_pdb\": {\"vertices\": " << q_rf5.vertices << ", \"reachable\": " << q_rf5.reachable
       << ", \"forward_edges\": " << q_rf5.forward_edges_checked << ", \"violations\": 0},\n"
       << "    \"orthoflow5_pdb\": {\"vertices\": " << q_o5.vertices << ", \"reachable\": " << q_o5.reachable
       << ", \"forward_edges\": " << q_o5.forward_edges_checked << ", \"violations\": 0}\n"
       << "  },\n"
       << "  \"concrete_random_walk_audit\": {\n"
       << "    \"edges_checked\": " << concrete_walk_edges << ",\n"
       << "    \"violations\": " << concrete_walk_viols << "\n"
       << "  },\n"
       << "  \"must_fail_controls\": {\n"
       << "    \"sticky_door_34_rejected_at_step_30\": " << (mf_sticky34_rejected ? "true" : "false") << ",\n"
       << "    \"planted_quotient_drop2_caught\": " << (mf_quotient_drop_caught ? "true" : "false") << ",\n"
       << "    \"planted_soko38_drop2_caught\": " << (mf_soko38_drop2_caught ? "true" : "false") << ",\n"
       << "    \"planted_tail_overestimate_caught\": " << (mf_overestimate_caught ? "true" : "false") << "\n"
       << "  },\n"
       << "  \"astar_summary\": {\n"
       << "    \"stop_reason\": \"" << stop_reason << "\",\n"
       << "    \"expanded_states\": " << expanded << ",\n"
       << "    \"unique_canonical_states\": " << final_unique_states << ",\n"
       << "    \"concrete_edges_checked\": " << astar_edge_checks << ",\n"
       << "    \"hash_collisions_prevented\": " << final_collisions << ",\n"
       << "    \"bellman_violations\": " << astar_bellman_viols << ",\n"
       << "    \"build_time_s\": " << fixed << setprecision(3) << build_s << ",\n"
       << "    \"quotient_audit_time_s\": " << qaudit_s << ",\n"
       << "    \"walk_audit_time_s\": " << walk_s << ",\n"
       << "    \"astar_time_s\": " << astar_s << ",\n"
       << "    \"total_time_s\": " << total_s << "\n"
       << "  },\n"
       << "  \"completed_f_layers\": [\n";
    for (size_t i = 0; i < layer_ledger.size(); ++i) {
      const auto& lr = layer_ledger[i];
      jf << "    {\"f\": " << lr.f_completed
         << ", \"certified_floor\": " << lr.certified_floor
         << ", \"expanded\": " << lr.cumulative_expanded
         << ", \"unique_canon_states\": " << lr.cumulative_unique_canon_states
         << ", \"edges_checked\": " << lr.cumulative_edges_checked
         << ", \"collisions_prevented\": " << lr.cumulative_hash_collisions_prevented
         << ", \"elapsed_s\": " << fixed << setprecision(3) << lr.elapsed_s << "}"
         << (i + 1 < layer_ledger.size() ? "," : "") << "\n";
    }
    jf << "  ]\n}\n";
  }
  return 0;
}
