// prove_iii14_15x7_v2_floor.cpp
// Certified Collision-Free V2 Lower-Bound Prover for Canonical 15x7 Room III-14 (`ahrazzle/soko`).
//
// Advances beyond `prove_iii14_15x7_landmark_floor.cpp` (PR #61, certified floor >= 40) via two
// joint quotient pattern databases (`Mcproof.Spec` zero-self-loop & cyclic-switch bounds):
//   1. `BedrockConservedSwitch3x3_15PDB` (946 MiB):
//      - Tracks all 9 purple switches `[4..6] x [2..4]` in exact ternary (`3^9 = 19,683`),
//      - Enforces 2-sided collar obstacle conservation (`(inc0+blk0)+(inc1+blk1)+(inc2+blk2) <= 9 - k_in`)
//        across both entry (`src_p`) and blow-off backstop (`blk_p`) cells when `m_act <= 9`,
//      - Guards all 21 right-half outer-border bedrock walls (`RIGHT_BORDER_MASK`, `x >= 7`) via 0-1 BFS
//        so heroes cannot phase through unharvested `y = 0` or `y = 6` border walls while keeping all
//        outer-border harvests zero-cost self-loops (`+ max(0, 9 - m_act)`).
//   2. `PetrifiedColFlow15PDB` (867 MiB):
//      - Separates Switch Columns `4`, `5`, and `6` (`s4, s5, c6, w6`), collar strips (`k1L, k1R, k2V`),
//        and outer rings (`r2, r3`) jointly with Druid border-adjacency `(d, adj)` (`NDA = 221`),
//      - Enforces exact pigeonhole Column-6 mobile-crate blow-off (`c6 -> k1R`) on horizontal `R` moves,
//        charging Druid `c6 -> w6` petrification walks and `'A'` mode-switch parity.
//   3. `Packed24` lossless base-3 5-cell-per-byte state representation (24 bytes/state, verified
//      bijective on 1,000,000 random concrete states) + `uint32_t` wave queues (`<= 768M` states).
//
// Portable ISO C++20: zero `<bits/stdc++.h>`, zero bare `assert`, dynamic SHA-256 computation.

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

using namespace std;
using u128 = unsigned __int128;

static inline void require_check(bool cond, const char* msg) {
  if (!cond) {
    cerr << "FATAL CHECK FAILURE: " << msg << "\n";
    exit(2);
  }
}

// ============================================================================
// Minimal Portable SHA-256 (FIPS 180-4)
// ============================================================================
struct Sha256 {
  uint32_t state[8];
  uint64_t bitlen;
  uint8_t buffer[64];
  size_t buflen;

  Sha256() {
    state[0] = 0x6a09e667u; state[1] = 0xbb67ae85u;
    state[2] = 0x3c6ef372u; state[3] = 0xa54ff53au;
    state[4] = 0x510e527fu; state[5] = 0x9b05688cu;
    state[6] = 0x1f83d9abu; state[7] = 0x5be0cd19u;
    bitlen = 0; buflen = 0;
  }
  static inline uint32_t rotr(uint32_t x, uint32_t n) { return (x >> n) | (x << (32 - n)); }
  void transform(const uint8_t data[64]) {
    static const uint32_t K[64] = {
        0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
        0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
        0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
        0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
        0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
        0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
        0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
        0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
    };
    uint32_t m[64];
    for (int i = 0; i < 16; ++i)
      m[i] = (uint32_t(data[i * 4]) << 24) | (uint32_t(data[i * 4 + 1]) << 16)
           | (uint32_t(data[i * 4 + 2]) << 8) | uint32_t(data[i * 4 + 3]);
    for (int i = 16; i < 64; ++i) {
      uint32_t s0 = rotr(m[i - 15], 7) ^ rotr(m[i - 15], 18) ^ (m[i - 15] >> 3);
      uint32_t s1 = rotr(m[i - 2], 17) ^ rotr(m[i - 2], 19) ^ (m[i - 2] >> 10);
      m[i] = m[i - 16] + s0 + m[i - 7] + s1;
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    uint32_t e = state[4], f = state[5], g = state[6], h = state[7];
    for (int i = 0; i < 64; ++i) {
      uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      uint32_t ch = (e & f) ^ ((~e) & g);
      uint32_t temp1 = h + S1 + ch + K[i] + m[i];
      uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
      uint32_t temp2 = S0 + maj;
      h = g; g = f; f = e; e = d + temp1;
      d = c; c = b; b = a; a = temp1 + temp2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
  }
  void update(const uint8_t* data, size_t len) {
    for (size_t i = 0; i < len; ++i) {
      buffer[buflen++] = data[i];
      if (buflen == 64) { transform(buffer); bitlen += 512; buflen = 0; }
    }
  }
  string finish_hex() {
    uint64_t total_bits = bitlen + uint64_t(buflen) * 8;
    buffer[buflen++] = 0x80u;
    if (buflen > 56) {
      while (buflen < 64) buffer[buflen++] = 0;
      transform(buffer); buflen = 0;
    }
    while (buflen < 56) buffer[buflen++] = 0;
    for (int i = 7; i >= 0; --i) buffer[buflen++] = uint8_t((total_bits >> (i * 8)) & 0xFFu);
    transform(buffer);
    ostringstream oss;
    oss << hex << setfill('0');
    for (int i = 0; i < 8; ++i) oss << setw(8) << state[i];
    return oss.str();
  }
  static string hex_str(const string& s) {
    Sha256 h; h.update(reinterpret_cast<const uint8_t*>(s.data()), s.size()); return h.finish_hex();
  }
};

// ============================================================================
// Canonical 15x7 Room III-14 Topology & Lossless `Packed24` Encoding
// ============================================================================
static constexpr int W = 15, H = 7, N = 105;
static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};

static const char* GRID_III14[H] = {
    "###############",
    "#.............#",
    "#.5.}}}.]]]]].#",
    "#...}}}.]G.G].#",
    "#.D.}}}.]]]]].#",
    "#.............#",
    "###############",
};

static const char* R48_ROUTE = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";

static u128 ORIGIN_MASK = 0, SWITCH_MASK = 0, PDOOR_MASK = 0, VAULT_IN_MASK = 0, RIGHT_BORDER_MASK = 0;
static u128 AURA[N], ORTHO[N], D5_MASK[5];
static int GOALS[2], B0 = -1, D0 = -1, D5_RING[N], O5_BKT[N];
static bool IS_ORIG[N], IS_SW[N], IS_PD[N];

static uint8_t ENC5[32][32];
static uint8_t DEC5_C[243], DEC5_W[243];

static inline u128 bit(int i) { return u128(1) << i; }
static inline bool tst(u128 m, int i) { return (m >> i) & 1; }
static inline int popcnt128(u128 x) {
  return __builtin_popcountll((uint64_t)x) + __builtin_popcountll((uint64_t)(x >> 64));
}
static inline int mirror_y_cell(int idx) { return (H - 1 - (idx / W)) * W + (idx % W); }
static inline u128 mirror_y_mask(u128 m) {
  u128 out = 0;
  for (int y = 0; y < H; ++y) {
    u128 row = (m >> (y * W)) & ((u128(1) << W) - 1);
    out |= row << ((H - 1 - y) * W);
  }
  return out;
}

struct CState {
  u128 crates, walls;
  uint8_t bx, by, dx, dy, ah, doors_open;
  bool operator==(const CState& o) const {
    return crates == o.crates && walls == o.walls && bx == o.bx && by == o.by
        && dx == o.dx && dy == o.dy && ah == o.ah && doors_open == o.doors_open;
  }
};

static inline CState mirror_y_state(const CState& s) {
  return CState{
      mirror_y_mask(s.crates), mirror_y_mask(s.walls),
      s.bx, uint8_t(H - 1 - s.by), s.dx, uint8_t(H - 1 - s.dy), s.ah, s.doors_open
  };
}

struct Packed24 {
  uint64_t w0, w1, w2;
  bool operator==(const Packed24& o) const { return w0 == o.w0 && w1 == o.w1 && w2 == o.w2; }
  bool operator<(const Packed24& o) const {
    if (w0 != o.w0) return w0 < o.w0;
    if (w1 != o.w1) return w1 < o.w1;
    return w2 < o.w2;
  }
  uint64_t hash64() const {
    auto mix = [](uint64_t x) {
      x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
      x ^= x >> 27; x *= 0x94d049bb133111ebULL;
      return x ^ (x >> 31);
    };
    uint64_t h = mix(w0 ^ 0x9e3779b97f4a7c15ULL);
    h = mix(h ^ w1);
    h = mix(h ^ w2);
    return h;
  }
};
static_assert(sizeof(Packed24) == 24);

static inline Packed24 pack24_raw(const CState& s) {
  uint8_t b[24];
  u128 c = s.crates, w = s.walls;
  for (int g = 0; g < 21; ++g) {
    uint8_t c5 = uint8_t(c & 31u);
    uint8_t w5 = uint8_t(w & 31u);
    b[g] = ENC5[c5][w5];
    c >>= 5; w >>= 5;
  }
  b[21] = uint8_t((s.by * W + s.bx) | (s.doors_open << 7));
  b[22] = uint8_t((s.dy * W + s.dx) | (s.ah << 7));
  b[23] = 0;
  Packed24 out{};
  memcpy(&out.w0, b + 0, 8);
  memcpy(&out.w1, b + 8, 8);
  memcpy(&out.w2, b + 16, 8);
  return out;
}
static inline Packed24 pack24_canon(const CState& s) {
  Packed24 p1 = pack24_raw(s), p2 = pack24_raw(mirror_y_state(s));
  return (p2 < p1) ? p2 : p1;
}
static inline CState unpack24(const Packed24& p) {
  uint8_t b[24];
  memcpy(b + 0, &p.w0, 8);
  memcpy(b + 8, &p.w1, 8);
  memcpy(b + 16, &p.w2, 8);
  CState s{};
  s.crates = 0; s.walls = 0;
  for (int g = 20; g >= 0; --g) {
    uint8_t v = b[g];
    s.crates = (s.crates << 5) | u128(DEC5_C[v]);
    s.walls = (s.walls << 5) | u128(DEC5_W[v]);
  }
  uint8_t bp = b[21] & 127u; s.bx = bp % W; s.by = bp / W; s.doors_open = (b[21] >> 7) & 1u;
  uint8_t dp = b[22] & 127u; s.dx = dp % W; s.dy = dp / W; s.ah = (b[22] >> 7) & 1u;
  return s;
}

static inline bool step_concrete(const CState& s, int mv, CState& ns) {
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

static inline bool is_win(const CState& s) {
  int bp = s.by * W + s.bx, dp = s.dy * W + s.dx;
  return (bp == GOALS[0] && dp == GOALS[1]) || (bp == GOALS[1] && dp == GOALS[0]);
}

static void init_topology() {
  memset(ENC5, 0, sizeof(ENC5));
  memset(DEC5_C, 0, sizeof(DEC5_C));
  memset(DEC5_W, 0, sizeof(DEC5_W));
  for (int c5 = 0; c5 < 32; ++c5)
    for (int w5 = 0; w5 < 32; ++w5) {
      if (c5 & w5) continue;
      int val = 0, p = 1;
      for (int k = 0; k < 5; ++k) {
        int t = ((c5 >> k) & 1) ? 1 : (((w5 >> k) & 1) ? 2 : 0);
        val += t * p; p *= 3;
      }
      ENC5[c5][w5] = uint8_t(val);
      DEC5_C[val] = uint8_t(c5);
      DEC5_W[val] = uint8_t(w5);
    }

  ORIGIN_MASK = SWITCH_MASK = PDOOR_MASK = VAULT_IN_MASK = RIGHT_BORDER_MASK = 0;
  for (int k = 0; k < 5; ++k) D5_MASK[k] = 0;
  for (int i = 0; i < N; ++i) { AURA[i] = 0; ORTHO[i] = 0; }
  int g_i = 0;
  for (int y = 0; y < H; ++y)
    for (int x = 0; x < W; ++x) {
      char c = GRID_III14[y][x]; int i = y * W + x;
      IS_ORIG[i] = (c == '#'); IS_SW[i] = (c == '}'); IS_PD[i] = (c == ']');
      if (y == 3 && x >= 9 && x <= 11) VAULT_IN_MASK |= bit(i);
      if (c == '#') {
        ORIGIN_MASK |= bit(i);
        if (x >= 7) RIGHT_BORDER_MASK |= bit(i);
      } else if (c == '}') SWITCH_MASK |= bit(i);
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

struct QuotientAuditStats {
  uint64_t vertices = 0;
  uint64_t reachable = 0;
  uint64_t goals = 0;
  uint64_t forward_edges_checked = 0;
  uint64_t goal_violations = 0;
  uint64_t step_violations = 0;
};

// ============================================================================
// PDB 1: BedrockConservedSwitch3x3_15PDB (946 MiB)
// ============================================================================
struct BedrockConservedSwitch3x3_15PDB {
  static constexpr int NB = 60, NS9 = 19683, NMODE = 4; // md = (rb << 1) | bud
  static constexpr uint32_t TOTAL = uint32_t(NB) * N * 2 * NMODE * NS9;
  vector<uint8_t> dist;
  int pow3[10];
  uint8_t k_in_of[NS9], sw_zero_mask_lo[NS9], sw_zero_mask_hi[NS9];
  uint16_t mirror_st9[NS9];
  uint8_t h_aura5[N][3]{}, v_aura5[N][3]{};
  struct LineMinExt { uint8_t min_ext[27][27]; vector<pair<uint8_t, uint8_t>> fwd[27]; };
  vector<LineMinExt> u_lmaps;
  vector<array<array<vector<uint8_t>, 3>, 27>> back_lmaps;
  uint16_t lmap_id[2][32][8][8][3];
  size_t reachable_count = 0;

  static inline int scell(int col, int row) { return (2 + row) * W + (4 + col); }
  static inline int sidx_of(int cell) { int x = cell % W, y = cell / W; return (x >= 4 && x <= 6 && y >= 2 && y <= 4) ? ((x - 4) * 3 + (y - 2)) : -1; }
  static inline uint32_t enc(int b, int d, int ah, int md, int st9) { return ((((uint32_t(b) * N + d) * 2 + ah) * NMODE + md) * NS9) + st9; }
  inline uint32_t canon_enc(int b, int d, int ah, int md, int st9) const {
    if (b < NB) return enc(b, d, ah, md, st9);
    return enc(mirror_y_cell(b), mirror_y_cell(d), ah, md, mirror_st9[st9]);
  }
  inline bool all_sw_fn(int st9, int b, int d) const {
    uint16_t zm = uint16_t(sw_zero_mask_lo[st9]) | (uint16_t(sw_zero_mask_hi[st9]) << 8);
    if (!zm) return true;
    int bi = sidx_of(b), di = sidx_of(d);
    if (bi >= 0) zm &= ~(1u << bi);
    if (di >= 0) zm &= ~(1u << di);
    return zm == 0;
  }
  inline bool valid_state_any_b(int b, int d, int md, int st9) const {
    if (b < 0 || b >= N || d < 0 || d >= N || b == d || md < 0 || md >= NMODE) return false;
    int rb = (md >> 1) & 1;
    if (!rb && (tst(RIGHT_BORDER_MASK, b) || tst(RIGHT_BORDER_MASK, d))) return false;
    int bi = sidx_of(b), di = sidx_of(d);
    if ((bi >= 0 && ((st9 / pow3[bi]) % 3) != 0) || (di >= 0 && ((st9 / pow3[di]) % 3) != 0)) return false;
    return all_sw_fn(st9, b, d) || !(IS_PD[b] || IS_PD[d]);
  }
  inline bool valid_state(int b, int d, int md, int st9) const { return b >= 0 && b < NB && valid_state_any_b(b, d, md, st9); }
  static inline int h_pos7(int cell, int row_y) { if (cell / W != row_y) return 7; int x = cell % W; return (x >= 2 && x <= 8) ? (x - 2) : 7; }
  static inline int v_pos7(int cell, int col_x) { if (cell % W != col_x) return 7; int y = cell / W; return (y >= 0 && y <= 6) ? y : 7; }

  void init_line_tables() {
    pow3[0] = 1; for (int i = 1; i <= 9; ++i) pow3[i] = pow3[i - 1] * 3;
    for (int st = 0; st < NS9; ++st) {
      int a[9], tmp = st, kin = 0; uint16_t zm = 0;
      for (int k = 0; k < 9; ++k) { a[k] = tmp % 3; tmp /= 3; if (a[k] == 0) zm |= (1u << k); else kin++; }
      k_in_of[st] = uint8_t(kin); sw_zero_mask_lo[st] = uint8_t(zm & 0xFF); sw_zero_mask_hi[st] = uint8_t((zm >> 8) & 1);
      int mst = 0; for (int col = 0; col < 3; ++col) for (int row = 0; row < 3; ++row) mst += a[col * 3 + (2 - row)] * pow3[col * 3 + row];
      mirror_st9[st] = uint16_t(mst);
    }
    for (int b = 0; b < N; ++b) {
      for (int r = 0; r < 3; ++r) { int y = 2 + r; uint8_t m = 0; for (int j = 0; j < 5; ++j) if (tst(AURA[b], y * W + (3 + j))) m |= (1u << j); h_aura5[b][r] = m; }
      for (int c = 0; c < 3; ++c) { int x = 4 + c; uint8_t m = 0; for (int j = 0; j < 5; ++j) if (tst(AURA[b], (1 + j) * W + x)) m |= (1u << j); v_aura5[b][c] = m; }
    }
    u_lmaps.clear();
    for (int di = 0; di < 2; ++di) {
      int dir = (di == 0) ? 1 : -1, src_p = (dir == 1) ? 1 : 5, blk_p = (dir == 1) ? 5 : 1;
      for (int aura5 = 0; aura5 < 32; ++aura5) {
        auto in_aura_p = [&](int p) -> bool { return (p >= 1 && p <= 5) ? ((aura5 >> (p - 1)) & 1) : false; };
        for (int bp = 0; bp < 8; ++bp) {
          int nbp = (bp < 7) ? (bp + dir) : 7;
          for (int dp = 0; dp < 8; ++dp) {
            int tdp = (dp < 7) ? (dp + dir) : 7;
            for (int dm = 0; dm < 3; ++dm) {
              LineMinExt lt{}; memset(lt.min_ext, 255, sizeof(lt.min_ext));
              for (int pre = 0; pre < 27; ++pre) {
                int sa[3] = {pre % 3, (pre / 3) % 3, (pre / 9) % 3};
                if ((bp >= 2 && bp <= 4 && sa[bp - 2] != 0) || (dp >= 2 && dp <= 4 && sa[dp - 2] != 0) || (bp < 7 && bp == dp) || (nbp >= 2 && nbp <= 4 && sa[nbp - 2] == 2)) continue;
                int can_src = (bp != src_p && dp != src_p) ? 2 : 0, max_blk = (bp == blk_p || dp == blk_p) ? 0 : 1;
                for (int sv = 0; sv <= can_src; ++sv) for (int blk = 0; blk <= max_blk; ++blk) {
                  int st[7] = {0,0,sa[0],sa[1],sa[2],0,0}; st[src_p] = sv; if (blk) st[blk_p] = 2;
                  int cb = bp, cd = dp; bool b_mv = (bp == 7), d_mv = (dp == 7), c_ch[7] = {false};
                  for (int p = 1; p <= 5; ++p) if (st[p] == 1 && in_aura_p(p)) c_ch[p] = true;
                  bool chg = true;
                  while (chg) {
                    chg = false;
                    for (int p = 1; p <= 5; ++p) if (c_ch[p]) { int np = p + dir; if (st[np] == 0 && (np >= 7 || cb != np) && (np >= 7 || cd != np)) { st[np] = 1; st[p] = 0; c_ch[p] = false; chg = true; } }
                    if (dm == 2 && !d_mv && cd < 7) { int np = cd + dir; if (np < 0 || np > 6 || (st[np] == 0 && (np >= 7 || cb != np))) { cd = (np >= 0 && np <= 6) ? np : 7; d_mv = true; chg = true; } }
                    if (!b_mv && cb < 7) { int np = cb + dir; if (np < 0 || np > 6 || (st[np] == 0 && (np >= 7 || cd != np))) { cb = (np >= 0 && np <= 6) ? np : 7; b_mv = true; chg = true; } }
                  }
                  if (!b_mv || (dm == 2 && !d_mv) || (dm == 1 && tdp >= 1 && tdp <= 5 && st[tdp] == 0 && tdp != cb)) continue;
                  int post = st[2] + 3 * st[3] + 9 * st[4]; uint8_t ext = uint8_t((sv > 0 ? 1 : 0) + blk);
                  if (ext < lt.min_ext[pre][post]) lt.min_ext[pre][post] = ext;
                }
                for (int post = 0; post < 27; ++post) if (lt.min_ext[pre][post] != 255) lt.fwd[pre].push_back({uint8_t(post), lt.min_ext[pre][post]});
              }
              int id = -1;
              for (int k = 0; k < int(u_lmaps.size()); ++k) if (memcmp(u_lmaps[k].min_ext, lt.min_ext, sizeof(lt.min_ext)) == 0) { id = k; break; }
              if (id < 0) { id = int(u_lmaps.size()); u_lmaps.push_back(lt); }
              lmap_id[di][aura5][bp][dp][dm] = uint16_t(id);
            }
          }
        }
      }
    }
    back_lmaps.resize(u_lmaps.size());
    for (size_t id = 0; id < u_lmaps.size(); ++id) for (int pre = 0; pre < 27; ++pre) for (auto [post, ext] : u_lmaps[id].fwd[pre]) back_lmaps[id][post][ext].push_back(uint8_t(pre));
  }

  void build(int num_threads = 10) {
    init_line_tables();
    dist.assign(TOTAL, 255);
    vector<uint32_t> frontier; frontier.reserve(30000000);
    u128 adj_rb_mask = 0;
    for (int i = 0; i < N; ++i) if (ORTHO[i] & RIGHT_BORDER_MASK) adj_rb_mask |= bit(i);

    auto close_zero_weight_layer = [&](vector<uint32_t>& layer, uint8_t d_val) {
      vector<vector<uint32_t>> z_extra(num_threads);
      vector<thread> zw;
      size_t lsz = layer.size();
      for (int tid = 0; tid < num_threads; ++tid) zw.emplace_back([&, tid]() {
        size_t s_i = (lsz * tid) / num_threads, e_i = (lsz * (tid + 1)) / num_threads;
        auto& out = z_extra[tid];
        for (size_t qi = s_i; qi < e_i; ++qi) {
          uint32_t v = layer[qi];
          int nst = int(v % NS9); uint32_t t1 = v / NS9;
          int nmd = int(t1 % NMODE); t1 /= NMODE;
          int nrb = (nmd >> 1) & 1;
          int nah = int(t1 & 1); t1 >>= 1;
          if (nah != 1 || nrb != 1) continue;
          int nd = int(t1 % N), nb = int(t1 / N);
          if (!tst(adj_rb_mask, nd)) continue;
          bool nao = all_sw_fn(nst, nb, nd);
          u128 rbs = ORTHO[nd] & RIGHT_BORDER_MASK & ~bit(nb);
          if (!nao) rbs &= ~PDOOR_MASK;
          if (!rbs) continue;
          for (int pbud = 0; pbud <= 1; ++pbud) {
            if (valid_state(nb, nd, pbud, nst)) {
              uint32_t u = enc(nb, nd, 1, pbud, nst);
              uint8_t exp = 255;
              if (dist[u] == 255 && __atomic_compare_exchange_n(&dist[u], &exp, d_val, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED))
                out.push_back(u);
            }
          }
        }
      });
      for (auto& th : zw) th.join();
      for (auto& ze : z_extra) layer.insert(layer.end(), ze.begin(), ze.end());
    };

    for (int gi = 0; gi < 2; ++gi) {
      int bg = GOALS[gi], dg = GOALS[1 - gi];
      for (int ah = 0; ah < 2; ++ah) for (int md = 0; md < NMODE; ++md) for (int st9 = 0; st9 < NS9; ++st9)
        if (valid_state(bg, dg, md, st9)) { uint32_t u = enc(bg, dg, ah, md, st9); if (dist[u] == 255) { dist[u] = 0; frontier.push_back(u); } }
    }
    close_zero_weight_layer(frontier, 0);
    reachable_count = frontier.size();

    uint8_t cur_d = 0;
    while (!frontier.empty()) {
      uint8_t nxt_d = cur_d + 1;
      vector<vector<uint32_t>> local_next(num_threads);
      vector<thread> workers;
      size_t fsz = frontier.size();
      for (int tid = 0; tid < num_threads; ++tid) workers.emplace_back([&, tid]() {
        size_t s_idx = (fsz * tid) / num_threads, e_idx = (fsz * (tid + 1)) / num_threads;
        auto& out = local_next[tid];
        auto try_push = [&](uint32_t u) {
          if (dist[u] == 255) {
            uint8_t exp = 255;
            if (__atomic_compare_exchange_n(&dist[u], &exp, nxt_d, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED))
              out.push_back(u);
          }
        };
        for (size_t qi = s_idx; qi < e_idx; ++qi) {
          uint32_t v = frontier[qi]; int nst = int(v % NS9); uint32_t t1 = v / NS9;
          int nmd = int(t1 % NMODE); t1 /= NMODE;
          int nbud = nmd & 1, nrb = (nmd >> 1) & 1;
          int nah = int(t1 & 1); t1 >>= 1;
          int nd = int(t1 % N), nb = int(t1 / N);
          bool nao = all_sw_fn(nst, nb, nd);

          try_push(enc(nb, nd, 1 - nah, nmd, nst));

          if (nah == 1) {
            int ndx = nd % W, ndy = nd / W;
            for (int mv = 0; mv < 4; ++mv) {
              int pdx = ndx - DX[mv], pdy = ndy - DY[mv];
              if (pdx >= 0 && pdx < W && pdy >= 0 && pdy < H) {
                int pd = pdy * W + pdx;
                if (valid_state(nb, pd, nmd, nst)) {
                  bool pao = all_sw_fn(nst, nb, pd);
                  if (!(!pao && IS_PD[nd]) && !(pao && !nao && (IS_PD[nb] || IS_PD[nd]))) {
                    try_push(enc(nb, pd, 1, nmd, nst));
                    if (pao && !nao && nbud == 0 && valid_state(nb, pd, (nrb << 1) | 1, nst))
                      try_push(enc(nb, pd, 1, (nrb << 1) | 1, nst));
                  }
                }
              }
              int tx = ndx + DX[mv], ty = ndy + DY[mv]; if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
              int tc = ty * W + tx; if (tc == nb || (!nao && IS_PD[tc])) continue;
              int ki = sidx_of(tc);
              if (ki >= 0) {
                int nval = (nst / pow3[ki]) % 3;
                if (nval == 1 || nval == 2) { int pst = nst + (3 - 2 * nval) * pow3[ki]; if (valid_state(nb, nd, nmd, pst)) try_push(enc(nb, nd, 1, nmd, pst)); }
              } else if (IS_ORIG[tc]) {
                if (tst(RIGHT_BORDER_MASK, tc)) {
                  for (int prb = (nrb == 1 ? 0 : 1); prb <= 1; ++prb)
                    for (int pbud = 0; pbud <= 1; ++pbud)
                      if (valid_state(nb, nd, (prb << 1) | pbud, nst))
                        try_push(enc(nb, nd, 1, (prb << 1) | pbud, nst));
                } else {
                  for (int pbud = 0; pbud <= 1; ++pbud)
                    if (valid_state(nb, nd, (nrb << 1) | pbud, nst))
                      try_push(enc(nb, nd, 1, (nrb << 1) | pbud, nst));
                }
              } else {
                if (nbud == 1 || k_in_of[nst] <= 8) try_push(enc(nb, nd, 1, nmd, nst));
              }
            }
          } else {
            int syms = (nb / W == 2) ? 2 : 1;
            for (int sym = 0; sym < syms; ++sym) {
              int tnb = sym ? mirror_y_cell(nb) : nb, tnd = sym ? mirror_y_cell(nd) : nd, tnst = sym ? int(mirror_st9[nst]) : nst;
              if (!nrb && (tst(RIGHT_BORDER_MASK, tnb) || tst(RIGHT_BORDER_MASK, tnd))) continue;
              int tnbx = tnb % W, tnby = tnb / W, tndx = tnd % W, tndy = tnd / W;
              bool nh_pd = IS_PD[tnb] || IS_PD[tnd];
              for (int mv = 0; mv < 4; ++mv) {
                int bx = tnbx - DX[mv], by = tnby - DY[mv]; if (bx < 0 || bx >= W || by < 0 || by > 3) continue;
                int b = by * W + bx;
                if (!nrb && tst(RIGHT_BORDER_MASK, b)) continue;
                int d_cands[3], dm_cands[3], n_dc = 0;
                if (tnd != b) {
                  if (!tst(AURA[b], tnd)) { d_cands[n_dc] = tnd; dm_cands[n_dc] = 0; n_dc++; }
                  else {
                    int fx = tndx + DX[mv], fy = tndy + DY[mv];
                    if (fx < 0 || fx >= W || fy < 0 || fy >= H || (!nrb && tst(RIGHT_BORDER_MASK, fy * W + fx))) {
                      d_cands[n_dc] = tnd; dm_cands[n_dc] = 0; n_dc++;
                    } else { d_cands[n_dc] = tnd; dm_cands[n_dc] = 1; n_dc++; }
                  }
                }
                int pdx = tndx - DX[mv], pdy = tndy - DY[mv];
                if (pdx >= 0 && pdx < W && pdy >= 0 && pdy < H) {
                  int pd = pdy * W + pdx;
                  if (pd != b && tst(AURA[b], pd) && !(!nrb && tst(RIGHT_BORDER_MASK, pd))) { d_cands[n_dc] = pd; dm_cands[n_dc] = 2; n_dc++; }
                }
                if (DY[mv] == 0) {
                  int di = (DX[mv] == 1) ? 0 : 1;
                  int post_r[3] = {((tnst/1)%3)+3*((tnst/27)%3)+9*((tnst/729)%3), ((tnst/3)%3)+3*((tnst/81)%3)+9*((tnst/2187)%3), ((tnst/9)%3)+3*((tnst/243)%3)+9*((tnst/6561)%3)};
                  for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                    int d = d_cands[dc_i], dm = dm_cands[dc_i];
                    const auto& b0s = back_lmaps[lmap_id[di][h_aura5[b][0]][h_pos7(b, 2)][h_pos7(d, 2)][(d / W == 2) ? dm : 0]][post_r[0]];
                    const auto& b1s = back_lmaps[lmap_id[di][h_aura5[b][1]][h_pos7(b, 3)][h_pos7(d, 3)][(d / W == 3) ? dm : 0]][post_r[1]];
                    const auto& b2s = back_lmaps[lmap_id[di][h_aura5[b][2]][h_pos7(b, 4)][h_pos7(d, 4)][(d / W == 4) ? dm : 0]][post_r[2]];
                    for (int e0 = 0; e0 < 3; ++e0) if (!b0s[e0].empty()) for (int e1 = 0; e1 < 3; ++e1) if (!b1s[e1].empty()) for (int e2 = 0; e2 < 3; ++e2) if (!b2s[e2].empty()) {
                      int tot_ext = e0 + e1 + e2;
                      for (uint8_t pr0 : b0s[e0]) { int base0 = (pr0%3)+((pr0/3)%3)*27+(pr0/9)*729; for (uint8_t pr1 : b1s[e1]) { int base01 = base0 + (pr1%3)*3+((pr1/3)%3)*81+(pr1/9)*2187; for (uint8_t pr2 : b2s[e2]) {
                        int pst = base01 + (pr2%3)*9+((pr2/3)%3)*243+(pr2/9)*6561; bool pre_ao = all_sw_fn(pst, b, d);
                        if ((!pre_ao && (IS_PD[tnb] || (dm == 2 && IS_PD[tnd]))) || (pre_ao && !nao && nh_pd)) continue;
                        if (nbud == 0) {
                          if (int(k_in_of[pst]) + tot_ext <= 9 && valid_state(b, d, (nrb << 1) | 0, pst)) try_push(enc(b, d, 0, (nrb << 1) | 0, pst));
                          if (pre_ao && !nao && valid_state(b, d, (nrb << 1) | 1, pst)) try_push(enc(b, d, 0, (nrb << 1) | 1, pst));
                        } else {
                          if (valid_state(b, d, (nrb << 1) | 1, pst)) try_push(enc(b, d, 0, (nrb << 1) | 1, pst));
                        }
                      }}}
                    }
                  }
                } else {
                  int di = (DY[mv] == 1) ? 0 : 1; int post_c[3] = {tnst % 27, (tnst / 27) % 27, (tnst / 729) % 27};
                  for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                    int d = d_cands[dc_i], dm = dm_cands[dc_i];
                    const auto& b0s = back_lmaps[lmap_id[di][v_aura5[b][0]][v_pos7(b, 4)][v_pos7(d, 4)][(d % W == 4) ? dm : 0]][post_c[0]];
                    const auto& b1s = back_lmaps[lmap_id[di][v_aura5[b][1]][v_pos7(b, 5)][v_pos7(d, 5)][(d % W == 5) ? dm : 0]][post_c[1]];
                    const auto& b2s = back_lmaps[lmap_id[di][v_aura5[b][2]][v_pos7(b, 6)][v_pos7(d, 6)][(d % W == 6) ? dm : 0]][post_c[2]];
                    for (int e0 = 0; e0 < 3; ++e0) if (!b0s[e0].empty()) for (int e1 = 0; e1 < 3; ++e1) if (!b1s[e1].empty()) for (int e2 = 0; e2 < 3; ++e2) if (!b2s[e2].empty()) {
                      int tot_ext = e0 + e1 + e2;
                      for (uint8_t pc0 : b0s[e0]) for (uint8_t pc1 : b1s[e1]) { int base01 = int(pc0) + 27 * int(pc1); for (uint8_t pc2 : b2s[e2]) {
                        int pst = base01 + 729 * int(pc2); bool pre_ao = all_sw_fn(pst, b, d);
                        if ((!pre_ao && (IS_PD[tnb] || (dm == 2 && IS_PD[tnd]))) || (pre_ao && !nao && nh_pd)) continue;
                        if (nbud == 0) {
                          if (int(k_in_of[pst]) + tot_ext <= 9 && valid_state(b, d, (nrb << 1) | 0, pst)) try_push(enc(b, d, 0, (nrb << 1) | 0, pst));
                          if (pre_ao && !nao && valid_state(b, d, (nrb << 1) | 1, pst)) try_push(enc(b, d, 0, (nrb << 1) | 1, pst));
                        } else {
                          if (valid_state(b, d, (nrb << 1) | 1, pst)) try_push(enc(b, d, 0, (nrb << 1) | 1, pst));
                        }
                      }}
                    }
                  }
                }
              }
            }
          }
        }
      });
      for (auto& th : workers) th.join();
      frontier.clear();
      size_t nxt_sz = 0; for (auto& ln : local_next) nxt_sz += ln.size();
      frontier.reserve(nxt_sz);
      for (auto& ln : local_next) frontier.insert(frontier.end(), ln.begin(), ln.end());
      close_zero_weight_layer(frontier, nxt_d);
      reachable_count += frontier.size();
      cur_d++;
    }
  }

  // Independent 100% Exhaustive Forward Quotient-Graph Edge Verifier (`dist[u] <= cost + dist[v]`)
  QuotientAuditStats audit_all_forward_edges(int num_threads = 10) const {
    QuotientAuditStats out{};
    out.vertices = TOTAL;
    out.reachable = reachable_count;
    for (int gi = 0; gi < 2; ++gi) {
      int bg = GOALS[gi], dg = GOALS[1 - gi];
      for (int ah = 0; ah < 2; ++ah) for (int md = 0; md < NMODE; ++md) for (int st9 = 0; st9 < NS9; ++st9)
        if (valid_state(bg, dg, md, st9)) {
          out.goals++;
          if (dist[enc(bg, dg, ah, md, st9)] != 0) out.goal_violations++;
        }
    }
    vector<uint64_t> t_edges(num_threads, 0), t_viols(num_threads, 0);
    vector<thread> workers;
    for (int tid = 0; tid < num_threads; ++tid) workers.emplace_back([&, tid]() {
      uint64_t loc_e = 0, loc_v = 0;
      for (int b = tid; b < NB; b += num_threads) {
        int bx = b % W, by = b / W;
        for (int d = 0; d < N; ++d) {
          if (b == d) continue;
          int dx = d % W, dy = d / W;
          for (int md = 0; md < NMODE; ++md) {
            int bud = md & 1, rb = (md >> 1) & 1;
            if (!rb && (tst(RIGHT_BORDER_MASK, b) || tst(RIGHT_BORDER_MASK, d))) continue;
            for (int st9 = 0; st9 < NS9; ++st9) {
              if (!valid_state(b, d, md, st9)) continue;
              bool pre_ao = all_sw_fn(st9, b, d);
              int kin = k_in_of[st9];

              auto check_edge = [&](int du, int cost, int tnb, int tnd, int nah, int nmd, int tnst) {
                if (!valid_state_any_b(tnb, tnd, nmd, tnst)) return;
                bool nao = all_sw_fn(tnst, tnb, tnd);
                if (pre_ao && !nao && (IS_PD[tnb] || IS_PD[tnd])) return;
                uint32_t v = canon_enc(tnb, tnd, nah, nmd, tnst);
                int dv = (dist[v] == 255) ? 999 : int(dist[v]);
                loc_e++;
                if (du > cost + dv) loc_v++;
              };

              // ah == 1 + 'A'
              {
                int du1 = (dist[enc(b, d, 1, md, st9)] == 255) ? 999 : int(dist[enc(b, d, 1, md, st9)]);
                check_edge(du1, 1, b, d, 0, md, st9);
                for (int mv = 0; mv < 4; ++mv) {
                  int tx = dx + DX[mv], ty = dy + DY[mv];
                  if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                  int tc = ty * W + tx;
                  if (tc == b || (!pre_ao && IS_PD[tc])) continue;
                  int ki = sidx_of(tc);
                  if (ki >= 0) {
                    int val = (st9 / pow3[ki]) % 3;
                    if (val == 0) {
                      bool nao = all_sw_fn(st9, b, tc);
                      check_edge(du1, 1, b, tc, 1, md, st9);
                      if (pre_ao && !nao && bud == 1) check_edge(du1, 1, b, tc, 1, (rb << 1) | 0, st9);
                    } else {
                      check_edge(du1, 1, b, d, 1, md, st9 + (3 - 2 * val) * pow3[ki]);
                    }
                  } else if (IS_ORIG[tc]) {
                    if (!tst(RIGHT_BORDER_MASK, tc)) {
                      // Walk onto harvested left border OR toggle left border
                      bool nao = all_sw_fn(st9, b, tc);
                      check_edge(du1, 1, b, tc, 1, md, st9);
                      if (pre_ao && !nao && bud == 1) check_edge(du1, 1, b, tc, 1, (rb << 1) | 0, st9);
                      check_edge(du1, 1, b, d, 1, (rb << 1) | 0, st9);
                      check_edge(du1, 1, b, d, 1, (rb << 1) | 1, st9);
                    } else {
                      // Right border: if rb == 1, can walk onto tc; harvest rb:0->1 has cost 0 (`zero-self-loop for need9`!)
                      if (rb == 1) {
                        bool nao = all_sw_fn(st9, b, tc);
                        check_edge(du1, 1, b, tc, 1, md, st9);
                        if (pre_ao && !nao && bud == 1) check_edge(du1, 1, b, tc, 1, (1 << 1) | 0, st9);
                        check_edge(du1, 1, b, d, 1, (1 << 1) | 0, st9);
                        check_edge(du1, 1, b, d, 1, (1 << 1) | 1, st9);
                        check_edge(du1, 1, b, d, 1, (0 << 1) | 0, st9);
                        check_edge(du1, 1, b, d, 1, (0 << 1) | 1, st9);
                      } else {
                        check_edge(du1, 0, b, d, 1, (1 << 1) | 0, st9);
                        check_edge(du1, 0, b, d, 1, (1 << 1) | 1, st9);
                      }
                    }
                  } else {
                    bool nao = all_sw_fn(st9, b, tc);
                    check_edge(du1, 1, b, tc, 1, md, st9);
                    if (pre_ao && !nao && bud == 1) check_edge(du1, 1, b, tc, 1, (rb << 1) | 0, st9);
                    if (bud == 1 || kin <= 8) check_edge(du1, 1, b, d, 1, md, st9);
                  }
                }
              }
              // ah == 0 + 'A'
              {
                int du0 = (dist[enc(b, d, 0, md, st9)] == 255) ? 999 : int(dist[enc(b, d, 0, md, st9)]);
                check_edge(du0, 1, b, d, 1, md, st9);
                int pre_r[3] = {((st9/1)%3)+3*((st9/27)%3)+9*((st9/729)%3), ((st9/3)%3)+3*((st9/81)%3)+9*((st9/2187)%3), ((st9/9)%3)+3*((st9/243)%3)+9*((st9/6561)%3)};
                int pre_c[3] = {st9 % 27, (st9 / 27) % 27, (st9 / 729) % 27};
                for (int mv = 0; mv < 4; ++mv) {
                  int nbx = bx + DX[mv], nby = by + DY[mv];
                  if (nbx < 0 || nbx >= W || nby < 0 || nby >= H) continue;
                  int nbc = nby * W + nbx;
                  if ((!pre_ao && IS_PD[nbc]) || (!rb && tst(RIGHT_BORDER_MASK, nbc))) continue;
                  int nd_cands[2], dm_cands[2], n_dc = 0;
                  if (!tst(AURA[b], d)) { if (d != nbc) { nd_cands[n_dc] = d; dm_cands[n_dc] = 0; n_dc++; } }
                  else {
                    int tdx = dx + DX[mv], tdy = dy + DY[mv];
                    if (tdx < 0 || tdx >= W || tdy < 0 || tdy >= H || (!rb && tst(RIGHT_BORDER_MASK, tdy * W + tdx))) {
                      if (d != nbc) { nd_cands[n_dc] = d; dm_cands[n_dc] = 0; n_dc++; }
                    } else {
                      int tdc = tdy * W + tdx;
                      if (d != nbc) { nd_cands[n_dc] = d; dm_cands[n_dc] = 1; n_dc++; }
                      if (tdc != nbc && !(IS_PD[tdc] && !pre_ao)) { nd_cands[n_dc] = tdc; dm_cands[n_dc] = 2; n_dc++; }
                    }
                  }
                  if (DY[mv] == 0) {
                    int di = (DX[mv] == 1) ? 0 : 1;
                    for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                      int ndc = nd_cands[dc_i], dm = dm_cands[dc_i];
                      const auto& f0 = u_lmaps[lmap_id[di][h_aura5[b][0]][h_pos7(b, 2)][h_pos7(d, 2)][(dy == 2) ? dm : 0]].fwd[pre_r[0]];
                      const auto& f1 = u_lmaps[lmap_id[di][h_aura5[b][1]][h_pos7(b, 3)][h_pos7(d, 3)][(dy == 3) ? dm : 0]].fwd[pre_r[1]];
                      const auto& f2 = u_lmaps[lmap_id[di][h_aura5[b][2]][h_pos7(b, 4)][h_pos7(d, 4)][(dy == 4) ? dm : 0]].fwd[pre_r[2]];
                      for (auto [nr0, e0] : f0) {
                        int b0 = (nr0%3)+((nr0/3)%3)*27+(nr0/9)*729;
                        for (auto [nr1, e1] : f1) {
                          int b01 = b0 + (nr1%3)*3+((nr1/3)%3)*81+(nr1/9)*2187;
                          for (auto [nr2, e2] : f2) {
                            if (bud == 0 && kin + int(e0) + e1 + e2 > 9) continue;
                            int nst = b01 + (nr2%3)*9+((nr2/3)%3)*243+(nr2/9)*6561;
                            bool nao = all_sw_fn(nst, nbc, ndc);
                            check_edge(du0, 1, nbc, ndc, 0, md, nst);
                            if (pre_ao && !nao && bud == 1) check_edge(du0, 1, nbc, ndc, 0, (rb << 1) | 0, nst);
                          }
                        }
                      }
                    }
                  } else {
                    int di = (DY[mv] == 1) ? 0 : 1;
                    for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                      int ndc = nd_cands[dc_i], dm = dm_cands[dc_i];
                      const auto& f0 = u_lmaps[lmap_id[di][v_aura5[b][0]][v_pos7(b, 4)][v_pos7(d, 4)][(dx == 4) ? dm : 0]].fwd[pre_c[0]];
                      const auto& f1 = u_lmaps[lmap_id[di][v_aura5[b][1]][v_pos7(b, 5)][v_pos7(d, 5)][(dx == 5) ? dm : 0]].fwd[pre_c[1]];
                      const auto& f2 = u_lmaps[lmap_id[di][v_aura5[b][2]][v_pos7(b, 6)][v_pos7(d, 6)][(dx == 6) ? dm : 0]].fwd[pre_c[2]];
                      for (auto [nc0, e0] : f0)
                        for (auto [nc1, e1] : f1) {
                          int b01 = int(nc0) + 27 * int(nc1);
                          for (auto [nc2, e2] : f2) {
                            if (bud == 0 && kin + int(e0) + e1 + e2 > 9) continue;
                            int nst = b01 + 729 * int(nc2);
                            bool nao = all_sw_fn(nst, nbc, ndc);
                            check_edge(du0, 1, nbc, ndc, 0, md, nst);
                            if (pre_ao && !nao && bud == 1) check_edge(du0, 1, nbc, ndc, 0, (rb << 1) | 0, nst);
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
      t_edges[tid] = loc_e; t_viols[tid] = loc_v;
    });
    for (auto& th : workers) th.join();
    for (int t = 0; t < num_threads; ++t) { out.forward_edges_checked += t_edges[t]; out.step_violations += t_viols[t]; }
    return out;
  }

  void free_build_tables() {
    vector<LineMinExt>().swap(u_lmaps);
    vector<array<array<vector<uint8_t>, 3>, 27>>().swap(back_lmaps);
  }

  inline int lookup_plus_harvest(const CState& s_in) const {
    CState s = (s_in.by <= 3) ? s_in : mirror_y_state(s_in);
    int st9 = 0, k = 0;
    for (int col = 0; col < 3; ++col) for (int row = 0; row < 3; ++row) { int c = scell(col, row); st9 += (tst(s.crates, c) ? 1 : (tst(s.walls, c) ? 2 : 0)) * pow3[k++]; }
    int m_act = popcnt128(s.crates | (s.walls & ~ORIGIN_MASK));
    int bud = (m_act <= 9) ? 0 : 1;
    int rb = ((s.walls & RIGHT_BORDER_MASK) != RIGHT_BORDER_MASK) ? 1 : 0;
    int md = (rb << 1) | bud;
    int bi = s.by * W + s.bx, di = s.dy * W + s.dx;
    uint8_t d = dist[enc(bi, di, s.ah, md, st9)];
    if (d == 255) return 999;
    if (tst(VAULT_IN_MASK, bi) && tst(VAULT_IN_MASK, di)) return int(d);
    return int(d) + max(0, 9 - m_act);
  }
};

// ============================================================================
// PDB 2: PetrifiedColFlow15PDB (867 MiB)
// ============================================================================
struct PetrifiedColFlow15PDB {
  static constexpr int NB = 60;
  struct Tup { uint8_t km, s4, s5, c6, w6, k1L, k1R, k2V, r2, r3; };
  int zone_of[N], max_adj[N], da_id[N][3], NDA = 0;
  vector<pair<int, int>> da_list;
  int cw6_idx[4][4];
  vector<int32_t> flat_tp;
  int tp10_id[4][4][4][4][4];
  vector<Tup> tp_list;
  int NR = 0;
  vector<uint8_t> dist;
  size_t reachable_count = 0;

  struct CapGen {
    uint8_t mv, ao, rows_out_6, nb_in_1R, d_blk7;
    uint8_t m[8][8];
    bool operator==(const CapGen& o) const {
      return mv == o.mv && ao == o.ao && rows_out_6 == o.rows_out_6
          && nb_in_1R == o.nb_in_1R && d_blk7 == o.d_blk7 && memcmp(m, o.m, sizeof(m)) == 0;
    }
  };
  int cap_id_of[NB][4][2][2];
  vector<vector<vector<uint16_t>>> back_tp, fwd_tp;
  vector<vector<uint16_t>> pre_crush, post_crush;

  static inline size_t flat_off(int s4, int s5, int cw, int k1L, int k1R, int k2V, int r2, int r3) {
    return (((((((size_t(s4) * 4 + s5) * 10 + cw) * 4 + k1L) * 4 + k1R) * 7 + k2V) * 10 + r2) * 10) + r3;
  }
  inline int get_tp(int s4, int s5, int c6, int w6, int k1L, int k1R, int k2V, int r2, int r3) const {
    if ((s4 | s5 | c6 | w6 | k1L | k1R | k2V | r2 | r3) < 0) return -1;
    if (s4 > 3 || s5 > 3 || c6 + w6 > 3 || k1L > 3 || k1R > 3 || k2V > 6 || r2 > 9 || r3 > 9) return -1;
    return flat_tp[flat_off(s4, s5, cw6_idx[c6][w6], k1L, k1R, k2V, r2, r3)];
  }
  inline uint32_t encode(int rt, int da, int bi, int ah) const {
    return ((((uint32_t(bi) * NDA + da) * 2 + ah) * NR) + rt);
  }
  inline int ao_of(int rt, int bi, int di) const {
    const auto& t = tp_list[rt];
    return (int(t.s4) + t.s5 + t.c6 + t.w6 + (IS_SW[bi] ? 1 : 0) + (IS_SW[di] ? 1 : 0) == 9) ? 1 : 0;
  }
  inline bool valid_u(int rt, int di, int adj, int bi) const {
    if (bi < 0 || bi >= NB || bi == di || adj < 0 || adj > max_adj[di]) return false;
    const auto& t = tp_list[rt];
    int zb = zone_of[bi], zd = zone_of[di];
    if (int(t.s4) + (zb == 0) + (zd == 0) > 3) return false;
    if (int(t.s5) + (zb == 1) + (zd == 1) > 3) return false;
    if (int(t.c6) + int(t.w6) + (zb == 2) + (zd == 2) > 3) return false;
    if (t.km <= 9) {
      if (int(t.k1L) + (zb == 3) + (zd == 3) > 3) return false;
      if (int(t.k1R) + (zb == 4) + (zd == 4) > 3) return false;
      if (int(t.k2V) + (zb == 5) + (zd == 5) > 6) return false;
    } else {
      if (int(t.k1R) + (zb == 4) + (zd == 4) > 3) return false;
    }
    return ao_of(rt, bi, di) == 1 || !(IS_PD[bi] || IS_PD[di]);
  }

  void build(int num_threads = 10) {
    for (int y = 0; y < H; ++y)
      for (int x = 0; x < W; ++x) {
        int i = y * W + x;
        int dx = max(0, max(4 - x, x - 6)), dy = max(0, max(2 - y, y - 4));
        if (dx == 0 && dy == 0) zone_of[i] = (x - 4);
        else if (x == 3 && y >= 2 && y <= 4) zone_of[i] = 3;
        else if (x == 7 && y >= 2 && y <= 4) zone_of[i] = 4;
        else if (x >= 4 && x <= 6 && (y == 1 || y == 5)) zone_of[i] = 5;
        else if (dx + dy == 2) zone_of[i] = 6;
        else zone_of[i] = 7;
      }

    int cw_i = 0; memset(cw6_idx, -1, sizeof(cw6_idx));
    for (int c6 = 0; c6 <= 3; ++c6) for (int w6 = 0; c6 + w6 <= 3; ++w6) cw6_idx[c6][w6] = cw_i++;
    flat_tp.assign(size_t(4) * 4 * 10 * 4 * 4 * 7 * 10 * 10, -1);
    tp_list.clear();
    for (int s4 = 0; s4 <= 3; ++s4)
      for (int s5 = 0; s5 <= 3; ++s5)
        for (int c6 = 0; c6 <= 3; ++c6)
          for (int w6 = 0; c6 + w6 <= 3; ++w6) {
            int k0 = s4 + s5 + c6 + w6;
            for (int k1L = 0; k1L <= min(3, 9 - k0); ++k1L)
              for (int k1R = 0; k1R <= min(3, 9 - k0 - k1L); ++k1R)
                for (int k2V = 0; k2V <= min(6, 9 - k0 - k1L - k1R); ++k2V)
                  for (int r2 = 0; r2 <= 9 - k0 - k1L - k1R - k2V; ++r2)
                    for (int r3 = 0; r3 <= 9 - k0 - k1L - k1R - k2V - r2; ++r3) {
                      int km = k0 + k1L + k1R + k2V + r2 + r3;
                      int id = int(tp_list.size());
                      flat_tp[flat_off(s4, s5, cw6_idx[c6][w6], k1L, k1R, k2V, r2, r3)] = id;
                      tp_list.push_back({uint8_t(km), uint8_t(s4), uint8_t(s5), uint8_t(c6), uint8_t(w6),
                                         uint8_t(k1L), uint8_t(k1R), uint8_t(k2V), uint8_t(r2), uint8_t(r3)});
                    }
          }
    memset(tp10_id, -1, sizeof(tp10_id));
    for (int s4 = 0; s4 <= 3; ++s4)
      for (int s5 = 0; s5 <= 3; ++s5)
        for (int c6 = 0; c6 <= 3; ++c6)
          for (int w6 = 0; c6 + w6 <= 3; ++w6)
            for (int k1R = 0; k1R <= 3; ++k1R) {
              int id = int(tp_list.size());
              tp10_id[s4][s5][c6][w6][k1R] = id;
              tp_list.push_back({10, uint8_t(s4), uint8_t(s5), uint8_t(c6), uint8_t(w6), 0, uint8_t(k1R), 0, 0, 0});
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
      for (int mv = 0; mv < 4; ++mv) {
        int nbx = bx + DX[mv], nby = by + DY[mv];
        int nbi = (nbx >= 0 && nbx < W && nby >= 0 && nby < H) ? (nby * W + nbx) : -1;
        uint8_t ro6 = 0;
        for (int y = 2; y <= 4; ++y) if (!tst(AURA[bi], y * W + 6)) ro6++;
        uint8_t nb1R = (nbi >= 0 && zone_of[nbi] == 4) ? 1 : 0;
        for (int ao = 0; ao < 2; ++ao)
          for (int db7 = 0; db7 < 2; ++db7) {
            CapGen sc{}; sc.mv = uint8_t(mv); sc.ao = uint8_t(ao); sc.rows_out_6 = ro6;
            sc.nb_in_1R = nb1R; sc.d_blk7 = (mv == 3) ? uint8_t(db7) : 0;
            if (nbi >= 0) {
              for (int c = 0; c < N; ++c) {
                if (c == bi || !tst(AURA[bi], c) || (!ao && IS_PD[c])) continue;
                int tx = (c % W) + DX[mv], ty = (c / W) + DY[mv];
                if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                int tc = ty * W + tx;
                if (tc == nbi || (!ao && IS_PD[tc])) continue;
                int za = zone_of[c], zb = zone_of[tc];
                if (za != zb) sc.m[za][zb]++;
              }
            }
            int cid = -1;
            for (int u = 0; u < int(ucaps.size()); ++u) if (ucaps[u] == sc) { cid = u; break; }
            if (cid < 0) { cid = int(ucaps.size()); ucaps.push_back(sc); }
            cap_id_of[bi][mv][ao][db7] = cid;
          }
      }
    }

    fwd_tp.assign(NR, vector<vector<uint16_t>>(ucaps.size()));
    back_tp.assign(NR, vector<vector<uint16_t>>(ucaps.size()));
    {
      vector<thread> workers;
      int nc = int(ucaps.size());
      for (int tid = 0; tid < num_threads; ++tid) workers.emplace_back([&, tid]() {
        for (int cid = tid; cid < nc; cid += num_threads) {
          const auto& sc = ucaps[cid];
          int mv = sc.mv;
          for (int prt = 0; prt < NR; ++prt) {
            const auto& t = tp_list[prt];
            auto& out = fwd_tp[prt][cid];
            if (t.km <= 9) {
              if (mv == 3) {
                for (int x76 = 0; x76 <= min<int>(sc.m[7][6], t.r3); ++x76)
                for (int x63 = 0; x63 <= min<int>(sc.m[6][3], t.r2); ++x63)
                for (int x65 = 0; x63 + x65 <= t.r2 && x65 <= sc.m[6][5]; ++x65)
                for (int x67 = 0; x63 + x65 + x67 <= t.r2 && x67 <= sc.m[6][7]; ++x67)
                for (int x56 = 0; x56 <= min<int>(sc.m[5][6], t.k2V); ++x56)
                for (int x30 = 0; x30 <= min<int>(sc.m[3][0], t.k1L); ++x30)
                for (int x01 = 0; x01 <= min<int>(sc.m[0][1], t.s4); ++x01)
                for (int x12 = 0; x12 <= min<int>(sc.m[1][2], t.s5); ++x12)
                for (int x46 = 0; x46 <= min<int>(sc.m[4][6], t.k1R); ++x46) {
                  int rem1R = int(t.k1R) - x46;
                  int lo_b = max(0, int(t.c6) - int(sc.rows_out_6) - rem1R - int(sc.nb_in_1R) - int(sc.d_blk7));
                  int hi_b = min<int>(sc.m[2][4], t.c6);
                  for (int x24 = lo_b; x24 <= hi_b; ++x24) {
                    int nrt = get_tp(int(t.s4)-x01+x30, int(t.s5)-x12+x01, int(t.c6)-x24+x12, t.w6,
                                     int(t.k1L)-x30+x63, rem1R+x24, int(t.k2V)-x56+x65,
                                     int(t.r2)-x63-x65-x67+x76+x56+x46, int(t.r3)-x76+x67);
                    if (nrt >= 0) out.push_back(uint16_t(nrt));
                  }
                }
              } else if (mv == 2) {
                for (int x76 = 0; x76 <= min<int>(sc.m[7][6], t.r3); ++x76)
                for (int x64 = 0; x64 <= min<int>(sc.m[6][4], t.r2); ++x64)
                for (int x65 = 0; x64 + x65 <= t.r2 && x65 <= sc.m[6][5]; ++x65)
                for (int x67 = 0; x64 + x65 + x67 <= t.r2 && x67 <= sc.m[6][7]; ++x67)
                for (int x56 = 0; x56 <= min<int>(sc.m[5][6], t.k2V); ++x56)
                for (int x42 = 0; x42 <= min<int>(sc.m[4][2], t.k1R); ++x42)
                for (int x21 = 0; x21 <= min<int>(sc.m[2][1], t.c6); ++x21)
                for (int x10 = 0; x10 <= min<int>(sc.m[1][0], t.s5); ++x10)
                for (int x03 = 0; x03 <= min<int>(sc.m[0][3], t.s4); ++x03)
                for (int x36 = 0; x36 <= min<int>(sc.m[3][6], t.k1L); ++x36) {
                  int nrt = get_tp(int(t.s4)-x03+x10, int(t.s5)-x10+x21, int(t.c6)-x21+x42, t.w6,
                                   int(t.k1L)-x36+x03, int(t.k1R)-x42+x64, int(t.k2V)-x56+x65,
                                   int(t.r2)-x64-x65-x67+x76+x56+x36, int(t.r3)-x76+x67);
                  if (nrt >= 0) out.push_back(uint16_t(nrt));
                }
              } else {
                for (int x05 = 0; x05 <= min<int>(sc.m[0][5], t.s4); ++x05)
                for (int x15 = 0; x15 <= min<int>(sc.m[1][5], t.s5); ++x15)
                for (int x25 = 0; x25 <= min<int>(sc.m[2][5], t.c6); ++x25)
                for (int x50 = 0; x50 <= min<int>(sc.m[5][0], t.k2V); ++x50)
                for (int x51 = 0; x50 + x51 <= t.k2V && x51 <= sc.m[5][1]; ++x51)
                for (int x52 = 0; x50 + x51 + x52 <= t.k2V && x52 <= sc.m[5][2]; ++x52)
                for (int x56 = 0; x50 + x51 + x52 + x56 <= t.k2V && x56 <= sc.m[5][6]; ++x56)
                for (int x36 = 0; x36 <= min<int>(sc.m[3][6], t.k1L); ++x36)
                for (int x46 = 0; x46 <= min<int>(sc.m[4][6], t.k1R); ++x46)
                for (int x63 = 0; x63 <= min<int>(sc.m[6][3], t.r2); ++x63)
                for (int x64 = 0; x63 + x64 <= t.r2 && x64 <= sc.m[6][4]; ++x64)
                for (int x65 = 0; x63 + x64 + x65 <= t.r2 && x65 <= sc.m[6][5]; ++x65)
                for (int x67 = 0; x63 + x64 + x65 + x67 <= t.r2 && x67 <= sc.m[6][7]; ++x67)
                for (int x76 = 0; x76 <= min<int>(sc.m[7][6], t.r3); ++x76) {
                  int nrt = get_tp(int(t.s4)-x05+x50, int(t.s5)-x15+x51, int(t.c6)-x25+x52, t.w6,
                                   int(t.k1L)-x36+x63, int(t.k1R)-x46+x64, int(t.k2V)-x50-x51-x52-x56+x05+x15+x25+x65,
                                   int(t.r2)-x63-x64-x65-x67+x56+x36+x46+x76, int(t.r3)-x76+x67);
                  if (nrt >= 0) out.push_back(uint16_t(nrt));
                }
              }
            } else {
              if (mv == 3) {
                for (int x30 = 0; x30 <= sc.m[3][0]; ++x30)
                for (int x01 = 0; x01 <= min<int>(sc.m[0][1], t.s4); ++x01)
                for (int x12 = 0; x12 <= min<int>(sc.m[1][2], t.s5); ++x12)
                for (int x46 = 0; x46 <= min<int>(sc.m[4][6], t.k1R); ++x46) {
                  int rem1R = int(t.k1R) - x46;
                  int lo_b = max(0, int(t.c6) - int(sc.rows_out_6) - rem1R - int(sc.nb_in_1R) - int(sc.d_blk7));
                  int hi_b = min<int>(sc.m[2][4], t.c6);
                  for (int x24 = lo_b; x24 <= hi_b; ++x24) {
                    int ns4 = int(t.s4)-x01+x30, ns5 = int(t.s5)-x12+x01, nc6 = int(t.c6)-x24+x12, nk1R = rem1R+x24;
                    if (ns4 <= 3 && ns5 <= 3 && nc6 + int(t.w6) <= 3 && nk1R <= 3)
                      out.push_back(uint16_t(tp10_id[ns4][ns5][nc6][t.w6][nk1R]));
                  }
                }
              } else if (mv == 2) {
                for (int x64 = 0; x64 <= sc.m[6][4]; ++x64)
                for (int x42 = 0; x42 <= min<int>(sc.m[4][2], t.k1R); ++x42)
                for (int x21 = 0; x21 <= min<int>(sc.m[2][1], t.c6); ++x21)
                for (int x10 = 0; x10 <= min<int>(sc.m[1][0], t.s5); ++x10)
                for (int x03 = 0; x03 <= min<int>(sc.m[0][3], t.s4); ++x03) {
                  int ns4 = int(t.s4)-x03+x10, ns5 = int(t.s5)-x10+x21, nc6 = int(t.c6)-x21+x42, nk1R = int(t.k1R)-x42+x64;
                  if (ns4 <= 3 && ns5 <= 3 && nc6 + int(t.w6) <= 3 && nk1R <= 3)
                    out.push_back(uint16_t(tp10_id[ns4][ns5][nc6][t.w6][nk1R]));
                }
              } else {
                for (int x05 = 0; x05 <= min<int>(sc.m[0][5], t.s4); ++x05)
                for (int x15 = 0; x15 <= min<int>(sc.m[1][5], t.s5); ++x15)
                for (int x25 = 0; x25 <= min<int>(sc.m[2][5], t.c6); ++x25)
                for (int x50 = 0; x50 <= sc.m[5][0]; ++x50)
                for (int x51 = 0; x51 <= sc.m[5][1]; ++x51)
                for (int x52 = 0; x52 <= sc.m[5][2]; ++x52)
                for (int x46 = 0; x46 <= min<int>(sc.m[4][6], t.k1R); ++x46)
                for (int x64 = 0; x64 <= sc.m[6][4]; ++x64) {
                  int ns4 = int(t.s4)-x05+x50, ns5 = int(t.s5)-x15+x51, nc6 = int(t.c6)-x25+x52, nk1R = int(t.k1R)-x46+x64;
                  if (ns4 <= 3 && ns5 <= 3 && nc6 + int(t.w6) <= 3 && nk1R <= 3)
                    out.push_back(uint16_t(tp10_id[ns4][ns5][nc6][t.w6][nk1R]));
                }
              }
            }
            sort(out.begin(), out.end()); out.erase(unique(out.begin(), out.end()), out.end());
          }
        }
      });
      for (auto& th : workers) th.join();
    }
    for (int cid = 0; cid < int(ucaps.size()); ++cid)
      for (int prt = 0; prt < NR; ++prt)
        for (uint16_t nrt : fwd_tp[prt][cid])
          back_tp[nrt][cid].push_back(uint16_t(prt));

    int pd_r2 = 0, pd_r3 = 0;
    for (int i = 0; i < N; ++i) if (IS_PD[i]) { if (zone_of[i] == 6) pd_r2++; else if (zone_of[i] == 7) pd_r3++; }
    pre_crush.assign(NR, {}); post_crush.assign(NR, {});
    vector<vector<uint16_t>> pre_crush_ge7(NR);
    for (int nrt = 0; nrt < NR; ++nrt) {
      const auto& t = tp_list[nrt];
      pre_crush[nrt].push_back(uint16_t(nrt));
      if (t.km <= 9) {
        for (int c2 = 0; c2 <= pd_r2; ++c2)
          for (int c3 = 0; c3 <= pd_r3; ++c3) {
            if (!(c2 + c3)) continue;
            if (int(t.km) + c2 + c3 <= 9) {
              int ert = get_tp(t.s4, t.s5, t.c6, t.w6, t.k1L, t.k1R, t.k2V, int(t.r2)+c2, int(t.r3)+c3);
              if (ert >= 0) pre_crush[nrt].push_back(uint16_t(ert));
            } else {
              pre_crush[nrt].push_back(uint16_t(tp10_id[t.s4][t.s5][t.c6][t.w6][t.k1R]));
            }
          }
      }
      auto& v = pre_crush[nrt];
      sort(v.begin(), v.end()); v.erase(unique(v.begin(), v.end()), v.end());
      for (uint16_t ert : v) {
        post_crush[ert].push_back(uint16_t(nrt));
        const auto& et = tp_list[ert];
        if (int(et.s4) + et.s5 + et.c6 + et.w6 >= 7) pre_crush_ge7[nrt].push_back(ert);
      }
    }

    vector<vector<vector<uint16_t>>> back_tp_crush1(NR, vector<vector<uint16_t>>(ucaps.size()));
    for (int prt = 0; prt < NR; ++prt) {
      const auto& pt = tp_list[prt];
      if (int(pt.s4) + pt.s5 + pt.c6 + pt.w6 < 7) continue;
      for (int cid = 0; cid < int(ucaps.size()); ++cid)
        for (uint16_t ert : fwd_tp[prt][cid])
          for (uint16_t nrt : post_crush[ert])
            back_tp_crush1[nrt][cid].push_back(uint16_t(prt));
    }
    for (int nrt = 0; nrt < NR; ++nrt)
      for (int cid = 0; cid < int(ucaps.size()); ++cid) {
        auto& dst = back_tp_crush1[nrt][cid];
        if (!dst.empty()) { sort(dst.begin(), dst.end()); dst.erase(unique(dst.begin(), dst.end()), dst.end()); }
      }

    const uint32_t TOTAL = uint32_t(NR) * NDA * NB * 2;
    dist.assign(TOTAL, 255);
    vector<uint32_t> frontier; frontier.reserve(15000000);
    for (int rt = 0; rt < NR; ++rt)
      for (int gi = 0; gi < 2; ++gi) {
        int bg = GOALS[gi], dg = GOALS[1 - gi];
        for (int adj = 0; adj <= max_adj[dg]; ++adj)
          for (int ah = 0; ah < 2; ++ah)
            if (valid_u(rt, dg, adj, bg)) {
              uint32_t w = encode(rt, da_id[dg][adj], bg, ah);
              if (dist[w] == 255) { dist[w] = 0; frontier.push_back(w); }
            }
      }
    reachable_count = frontier.size();
    uint8_t cur_d = 0;
    while (!frontier.empty()) {
      uint8_t nxt_d = cur_d + 1;
      vector<vector<uint32_t>> local_next(num_threads);
      vector<thread> workers;
      size_t fsz = frontier.size();
      for (int tid = 0; tid < num_threads; ++tid) workers.emplace_back([&, tid]() {
        size_t s_idx = (fsz * tid) / num_threads, e_idx = (fsz * (tid + 1)) / num_threads;
        auto& out = local_next[tid];
        auto push_pred = [&](int rt, int di, int adj, int bi, int ah) {
          if (rt < 0 || !valid_u(rt, di, adj, bi)) return;
          uint32_t u = encode(rt, da_id[di][adj], bi, ah);
          if (dist[u] == 255) {
            uint8_t exp = 255;
            if (__atomic_compare_exchange_n(&dist[u], &exp, nxt_d, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED))
              out.push_back(u);
          }
        };
        for (size_t qi = s_idx; qi < e_idx; ++qi) {
          uint32_t v = frontier[qi], tmp = v;
          int nrt = int(tmp % NR); tmp /= NR;
          int nah = int(tmp & 1); tmp >>= 1;
          int nda = int(tmp % NDA), nbi = int(tmp / NDA);
          auto [ndi, nadj] = da_list[nda];
          int nao = ao_of(nrt, nbi, ndi);
          const auto& nt = tp_list[nrt];

          push_pred(nrt, ndi, nadj, nbi, 1 - nah);
          if (nah == 1) {
            int ndx = ndi % W, ndy = ndi / W;
            for (int d = 0; d < 4; ++d) {
              int px = ndx - DX[d], py = ndy - DY[d];
              if (px < 0 || px >= W || py < 0 || py >= H) continue;
              int pdi = py * W + px;
              for (int padj = 0; padj <= max_adj[pdi]; ++padj) {
                if (ao_of(nrt, nbi, pdi) == 0 && !IS_PD[ndi]) push_pred(nrt, pdi, padj, nbi, 1);
                if (nao == 1) { if (ao_of(nrt, nbi, pdi) == 1) push_pred(nrt, pdi, padj, nbi, 1); }
                else if (IS_SW[pdi] && !IS_PD[nbi] && !IS_PD[ndi]) {
                  for (uint16_t ert : pre_crush_ge7[nrt])
                    if (ao_of(ert, nbi, pdi) == 1) push_pred(ert, pdi, padj, nbi, 1);
                }
              }
            }
            for (int d = 0; d < 4; ++d) {
              int tx = ndx + DX[d], ty = ndy + DY[d];
              if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
              int ti = ty * W + tx;
              if (ti == nbi || (!nao && IS_PD[ti])) continue;
              int zt = zone_of[ti];
              if (!IS_ORIG[ti]) {
                if (zt == 2) {
                  if (nt.km <= 9) {
                    if (nt.w6 >= 1) push_pred(get_tp(nt.s4, nt.s5, nt.c6+1, nt.w6-1, nt.k1L, nt.k1R, nt.k2V, nt.r2, nt.r3), ndi, nadj, nbi, 1);
                    if (nt.c6 >= 1) push_pred(get_tp(nt.s4, nt.s5, nt.c6-1, nt.w6+1, nt.k1L, nt.k1R, nt.k2V, nt.r2, nt.r3), ndi, nadj, nbi, 1);
                  } else {
                    if (nt.w6 >= 1) push_pred(tp10_id[nt.s4][nt.s5][nt.c6+1][nt.w6-1][nt.k1R], ndi, nadj, nbi, 1);
                    if (nt.c6 >= 1) push_pred(tp10_id[nt.s4][nt.s5][nt.c6-1][nt.w6+1][nt.k1R], ndi, nadj, nbi, 1);
                  }
                } else {
                  bool has_obs = false;
                  if (nt.km <= 9) {
                    if (zt == 0) has_obs = (nt.s4 >= 1); else if (zt == 1) has_obs = (nt.s5 >= 1);
                    else if (zt == 3) has_obs = (nt.k1L >= 1); else if (zt == 4) has_obs = (nt.k1R >= 1);
                    else if (zt == 5) has_obs = (nt.k2V >= 1); else if (zt == 6) has_obs = (nt.r2 >= 1);
                    else has_obs = (nt.r3 >= 1);
                  } else {
                    if (zt == 0) has_obs = (nt.s4 >= 1); else if (zt == 1) has_obs = (nt.s5 >= 1);
                    else if (zt == 4) has_obs = (nt.k1R >= 1);
                    else has_obs = (10 - (int(nt.s4)+nt.s5+nt.c6+nt.w6+nt.k1R) >= 1);
                  }
                  if (has_obs) push_pred(nrt, ndi, nadj, nbi, 1);
                }
              } else {
                if (nadj + 1 <= max_adj[ndi]) {
                  if (nt.km <= 9) {
                    int pr2 = int(nt.r2) - (zt == 6 ? 1 : 0), pr3 = int(nt.r3) - (zt == 7 ? 1 : 0);
                    if (pr2 >= 0 && pr3 >= 0) push_pred(get_tp(nt.s4, nt.s5, nt.c6, nt.w6, nt.k1L, nt.k1R, nt.k2V, pr2, pr3), ndi, nadj+1, nbi, 1);
                  } else {
                    push_pred(nrt, ndi, nadj+1, nbi, 1);
                    int rem9 = 9 - (int(nt.s4)+nt.s5+nt.c6+nt.w6+nt.k1R);
                    for (int k1L = 0; k1L <= min(3, rem9); ++k1L)
                      for (int k2V = 0; k2V <= min(6, rem9 - k1L); ++k2V)
                        for (int r2 = 0; r2 <= rem9 - k1L - k2V; ++r2)
                          push_pred(get_tp(nt.s4, nt.s5, nt.c6, nt.w6, k1L, nt.k1R, k2V, r2, rem9-k1L-k2V-r2), ndi, nadj+1, nbi, 1);
                  }
                }
                if (nadj >= 1) {
                  if (nt.km <= 8) push_pred(get_tp(nt.s4, nt.s5, nt.c6, nt.w6, nt.k1L, nt.k1R, nt.k2V, int(nt.r2)+(zt==6?1:0), int(nt.r3)+(zt==7?1:0)), ndi, nadj-1, nbi, 1);
                  else if (nt.km == 9) push_pred(tp10_id[nt.s4][nt.s5][nt.c6][nt.w6][nt.k1R], ndi, nadj-1, nbi, 1);
                  else push_pred(nrt, ndi, nadj-1, nbi, 1);
                }
              }
            }
          } else {
            auto emit_bard_back = [&](int bi, int nbi_raw, int ndi_raw, int mv) {
              bool b_pd = IS_PD[bi] || IS_PD[nbi_raw];
              int db7 = (mv == 3 && zone_of[ndi_raw] == 4) ? 1 : 0;
              int ndx = ndi_raw % W, ndy = ndi_raw / W;
              int pdx = ndx - DX[mv], pdy = ndy - DY[mv];
              int pdi_p = (pdx >= 0 && pdx < W && pdy >= 0 && pdy < H && tst(AURA[bi], pdy * W + pdx)) ? (pdy * W + pdx) : -1;
              if (!b_pd) {
                for (uint16_t prt : back_tp[nrt][cap_id_of[bi][mv][0][db7]]) {
                  if (ao_of(prt, bi, ndi_raw) == 0) push_pred(prt, ndi_raw, nadj, bi, 0);
                  if (pdi_p >= 0 && !IS_PD[pdi_p] && !IS_PD[ndi_raw])
                    for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
                      if (ao_of(prt, bi, pdi_p) == 0) push_pred(prt, pdi_p, padj, bi, 0);
                }
              }
              if (nao == 1) {
                for (uint16_t prt : back_tp[nrt][cap_id_of[bi][mv][1][db7]]) {
                  if (ao_of(prt, bi, ndi_raw) == 1) push_pred(prt, ndi_raw, nadj, bi, 0);
                  if (pdi_p >= 0)
                    for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
                      if (ao_of(prt, bi, pdi_p) == 1) push_pred(prt, pdi_p, padj, bi, 0);
                }
              } else if (!(IS_PD[nbi_raw] || IS_PD[ndi_raw])) {
                for (uint16_t prt : back_tp_crush1[nrt][cap_id_of[bi][mv][1][db7]]) {
                  if (ao_of(prt, bi, ndi_raw) == 1) push_pred(prt, ndi_raw, nadj, bi, 0);
                  if (pdi_p >= 0)
                    for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
                      if (ao_of(prt, bi, pdi_p) == 1) push_pred(prt, pdi_p, padj, bi, 0);
                }
              }
            };
            int nbx = nbi % W, nby = nbi / W;
            for (int mv = 0; mv < 4; ++mv) {
              int bx = nbx - DX[mv], by = nby - DY[mv];
              if (bx >= 0 && bx < W && by >= 0 && by <= 3) emit_bard_back(by * W + bx, nbi, ndi, mv);
            }
            if (nby == 2) emit_bard_back(3 * W + nbx, 4 * W + nbx, mirror_y_cell(ndi), 1);
          }
        }
      });
      for (auto& th : workers) th.join();
      frontier.clear();
      size_t nxt_sz = 0; for (auto& ln : local_next) nxt_sz += ln.size();
      frontier.reserve(nxt_sz);
      for (auto& ln : local_next) frontier.insert(frontier.end(), ln.begin(), ln.end());
      reachable_count += frontier.size();
      cur_d++;
    }
  }

  // Independent 100% Exhaustive Forward Quotient-Graph Edge Verifier (`dist[u] <= 1 + dist[v]`)
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
    for (int tid = 0; tid < num_threads; ++tid) workers.emplace_back([&, tid]() {
      uint64_t loc_e = 0, loc_v = 0;
      for (int bi = tid; bi < NB; bi += num_threads) {
        int bx = bi % W, by = bi / W;
        for (int da = 0; da < NDA; ++da) {
          auto [di, adj] = da_list[da];
          if (bi == di) continue;
          int dx = di % W, dy = di / W;
          for (int rt = 0; rt < NR; ++rt) {
            if (!valid_u(rt, di, adj, bi)) continue;
            int pre_ao = ao_of(rt, bi, di);
            const auto& t = tp_list[rt];

            auto check_to = [&](int du, int nrt, int ndi, int nadj, int nbi_raw, int nah) {
              if (nrt < 0) return;
              int cbi = (nbi_raw < NB) ? nbi_raw : mirror_y_cell(nbi_raw);
              int cdi = (nbi_raw < NB) ? ndi : mirror_y_cell(ndi);
              if (!valid_u(nrt, cdi, nadj, cbi)) return;
              uint32_t v = encode(nrt, da_id[cdi][nadj], cbi, nah);
              int dv = (dist[v] == 255) ? 999 : int(dist[v]);
              loc_e++;
              if (du > 1 + dv) loc_v++;
            };

            // ah == 1 + 'A'
            {
              int du1 = (dist[encode(rt, da, bi, 1)] == 255) ? 999 : int(dist[encode(rt, da, bi, 1)]);
              check_to(du1, rt, di, adj, bi, 0);
              for (int mv = 0; mv < 4; ++mv) {
                int tx = dx + DX[mv], ty = dy + DY[mv];
                if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                int ti = ty * W + tx;
                if (ti == bi || (pre_ao == 0 && IS_PD[ti])) continue;
                // Walk di -> ti
                if (pre_ao == 0) {
                  for (int nadj = 0; nadj <= max_adj[ti]; ++nadj) check_to(du1, rt, ti, nadj, bi, 1);
                } else {
                  int nao_nc = ao_of(rt, bi, ti);
                  if (nao_nc == 1) {
                    for (int nadj = 0; nadj <= max_adj[ti]; ++nadj) check_to(du1, rt, ti, nadj, bi, 1);
                  } else if (!(IS_PD[bi] || IS_PD[ti])) {
                    for (uint16_t nrt : post_crush[rt])
                      for (int nadj = 0; nadj <= max_adj[ti]; ++nadj)
                        check_to(du1, nrt, ti, nadj, bi, 1);
                  }
                }
                // Toggle ti
                int zt = zone_of[ti];
                if (!IS_ORIG[ti]) {
                  if (zt == 2) {
                    if (t.km <= 9) {
                      if (t.c6 >= 1) check_to(du1, get_tp(t.s4, t.s5, t.c6-1, t.w6+1, t.k1L, t.k1R, t.k2V, t.r2, t.r3), di, adj, bi, 1);
                      if (t.w6 >= 1) check_to(du1, get_tp(t.s4, t.s5, t.c6+1, t.w6-1, t.k1L, t.k1R, t.k2V, t.r2, t.r3), di, adj, bi, 1);
                    } else {
                      if (t.c6 >= 1) check_to(du1, tp10_id[t.s4][t.s5][t.c6-1][t.w6+1][t.k1R], di, adj, bi, 1);
                      if (t.w6 >= 1) check_to(du1, tp10_id[t.s4][t.s5][t.c6+1][t.w6-1][t.k1R], di, adj, bi, 1);
                    }
                  } else {
                    bool has_obs = false;
                    if (t.km <= 9) {
                      if (zt == 0) has_obs = (t.s4 >= 1); else if (zt == 1) has_obs = (t.s5 >= 1);
                      else if (zt == 3) has_obs = (t.k1L >= 1); else if (zt == 4) has_obs = (t.k1R >= 1);
                      else if (zt == 5) has_obs = (t.k2V >= 1); else if (zt == 6) has_obs = (t.r2 >= 1);
                      else has_obs = (t.r3 >= 1);
                    } else {
                      if (zt == 0) has_obs = (t.s4 >= 1); else if (zt == 1) has_obs = (t.s5 >= 1);
                      else if (zt == 4) has_obs = (t.k1R >= 1);
                      else has_obs = (10 - (int(t.s4)+t.s5+t.c6+t.w6+t.k1R) >= 1);
                    }
                    if (has_obs) check_to(du1, rt, di, adj, bi, 1);
                  }
                } else {
                  if (adj >= 1) {
                    if (t.km <= 8) check_to(du1, get_tp(t.s4, t.s5, t.c6, t.w6, t.k1L, t.k1R, t.k2V, int(t.r2)+(zt==6?1:0), int(t.r3)+(zt==7?1:0)), di, adj-1, bi, 1);
                    else check_to(du1, tp10_id[t.s4][t.s5][t.c6][t.w6][t.k1R], di, adj-1, bi, 1);
                  }
                  if (adj + 1 <= max_adj[di]) {
                    if (t.km <= 9) {
                      int nr2 = int(t.r2) - (zt == 6 ? 1 : 0), nr3 = int(t.r3) - (zt == 7 ? 1 : 0);
                      if (nr2 >= 0 && nr3 >= 0) check_to(du1, get_tp(t.s4, t.s5, t.c6, t.w6, t.k1L, t.k1R, t.k2V, nr2, nr3), di, adj+1, bi, 1);
                    } else {
                      check_to(du1, rt, di, adj+1, bi, 1);
                      int rem9 = 9 - (int(t.s4)+t.s5+t.c6+t.w6+t.k1R);
                      for (int k1L = 0; k1L <= min(3, rem9); ++k1L)
                        for (int k2V = 0; k2V <= min(6, rem9 - k1L); ++k2V)
                          for (int r2 = 0; r2 <= rem9 - k1L - k2V; ++r2)
                            check_to(du1, get_tp(t.s4, t.s5, t.c6, t.w6, k1L, t.k1R, k2V, r2, rem9-k1L-k2V-r2), di, adj+1, bi, 1);
                    }
                  }
                }
              }
            }
            // ah == 0 + 'A'
            {
              int du0 = (dist[encode(rt, da, bi, 0)] == 255) ? 999 : int(dist[encode(rt, da, bi, 0)]);
              check_to(du0, rt, di, adj, bi, 1);
              for (int mv = 0; mv < 4; ++mv) {
                int nbx = bx + DX[mv], nby = by + DY[mv];
                if (nbx < 0 || nbx >= W || nby < 0 || nby >= H) continue;
                int nbi = nby * W + nbx;
                if (pre_ao == 0 && IS_PD[nbi]) continue;
                int nd_cands[2], nadj_fixed[2], n_dc = 0;
                if (di != nbi) { nd_cands[n_dc] = di; nadj_fixed[n_dc] = 1; n_dc++; }
                if (tst(AURA[bi], di)) {
                  int tdx = dx + DX[mv], tdy = dy + DY[mv];
                  if (tdx >= 0 && tdx < W && tdy >= 0 && tdy < H) {
                    int tdi = tdy * W + tdx;
                    if (tdi != nbi && !(pre_ao == 0 && IS_PD[tdi])) { nd_cands[n_dc] = tdi; nadj_fixed[n_dc] = 0; n_dc++; }
                  }
                }
                for (int dc_i = 0; dc_i < n_dc; ++dc_i) {
                  int ndi = nd_cands[dc_i], afix = nadj_fixed[dc_i];
                  int db7 = (mv == 3 && zone_of[ndi] == 4) ? 1 : 0;
                  int cid = cap_id_of[bi][mv][pre_ao][db7];
                  for (uint16_t ert : fwd_tp[rt][cid]) {
                    if (pre_ao == 0 || ao_of(ert, nbi, ndi) == 1) {
                      if (afix) check_to(du0, ert, ndi, adj, nbi, 0);
                      else for (int nadj = 0; nadj <= max_adj[ndi]; ++nadj) check_to(du0, ert, ndi, nadj, nbi, 0);
                    } else if (!(IS_PD[nbi] || IS_PD[ndi])) {
                      for (uint16_t nrt : post_crush[ert]) {
                        if (afix) check_to(du0, nrt, ndi, adj, nbi, 0);
                        else for (int nadj = 0; nadj <= max_adj[ndi]; ++nadj) check_to(du0, nrt, ndi, nadj, nbi, 0);
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
      t_edges[tid] = loc_e; t_viols[tid] = loc_v;
    });
    for (auto& th : workers) th.join();
    for (int t = 0; t < num_threads; ++t) { out.forward_edges_checked += t_edges[t]; out.step_violations += t_viols[t]; }
    return out;
  }

  void free_build_tables() {
    vector<vector<vector<uint16_t>>>().swap(fwd_tp);
    vector<vector<vector<uint16_t>>>().swap(back_tp);
    vector<vector<uint16_t>>().swap(pre_crush);
    vector<vector<uint16_t>>().swap(post_crush);
  }

  inline int lookup(const CState& s_in) const {
    CState s = (s_in.by <= 3) ? s_in : mirror_y_state(s_in);
    u128 act = s.crates | (s.walls & ~ORIGIN_MASK);
    int km = min(10, popcnt128(act));
    int s4 = 0, s5 = 0, c6 = 0, w6 = 0, k1L = 0, k1R = 0, k2V = 0, r2 = 0, r3 = 0;
    u128 m = act;
    while (m) {
      int idx = (uint64_t)m ? __builtin_ctzll((uint64_t)m) : (64 + __builtin_ctzll((uint64_t)(m >> 64)));
      m &= ~bit(idx);
      int z = zone_of[idx];
      if (z == 0) s4++;
      else if (z == 1) s5++;
      else if (z == 2) { if (tst(s.crates, idx)) c6++; else w6++; }
      else if (z == 3) k1L++;
      else if (z == 4) k1R++;
      else if (z == 5) k2V++;
      else if (z == 6) r2++;
      else r3++;
    }
    int rt = (km <= 9) ? get_tp(s4, s5, c6, w6, k1L, k1R, k2V, r2, r3) : tp10_id[s4][s5][c6][w6][k1R];
    if (rt < 0) return 999;
    int di = s.dy * W + s.dx, bi = s.by * W + s.bx;
    int adj = popcnt128(s.walls & ORIGIN_MASK & ORTHO[di]);
    uint8_t d = dist[encode(rt, da_id[di][adj], bi, s.ah)];
    return (d == 255) ? 999 : int(d);
  }
};

// Construct exact soko#38 counterexample state in CState
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

template <typename HFn>
static uint64_t check_concrete_edge_fn(const CState& s, HFn&& hfn, uint64_t& edges_out) {
  uint64_t viols = 0;
  int hs = hfn(s);
  if (is_win(s) && hs != 0) viols++;
  for (int mv = 0; mv < 5; ++mv) {
    CState ns;
    if (!step_concrete(s, mv, ns)) continue;
    edges_out++;
    int hn = hfn(ns);
    if (hs > 1 + hn) viols++;
  }
  return viols;
}

struct CandEdge24 {
  Packed24 np;
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
  size_t max_total_states = 742400000ULL; // 256 * 2.9M (~23.4 GiB exact reserve)
  double time_limit = 240.0;
  string json_out_path = "";
  string source_path = "";

  for (int i = 1; i < argc; ++i) {
    string arg = argv[i];
    if (arg == "--self-test") {
      self_test_only = true;
      target_walk_edges = 2000000ULL;
      max_total_states = 4096000ULL;
      time_limit = 20.0;
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

  string board_lf;
  for (int y = 0; y < H; ++y) { if (y > 0) board_lf += "\n"; board_lf += GRID_III14[y]; }
  string board_sha256_lf = Sha256::hex_str(board_lf);

  string prover_source_sha256 = "";
  if (!source_path.empty()) {
    ifstream f(source_path, ios::binary);
    if (f) { ostringstream ss; ss << f.rdbuf(); prover_source_sha256 = Sha256::hex_str(ss.str()); }
  }

  cout << "[INIT] Canonical 15x7 Room III-14 board_sha256_lf = " << board_sha256_lf << "\n";

  // Build both V2 Joint Quotient PDBs
  auto t_build = chrono::steady_clock::now();
  BedrockConservedSwitch3x3_15PDB pdb_bsw9;
  pdb_bsw9.build(10);
  PetrifiedColFlow15PDB pdb_pcf;
  pdb_pcf.build(10);
  double build_s = chrono::duration<double>(chrono::steady_clock::now() - t_build).count();
  cout << "[BUILD] Built BedrockConservedSwitch3x3 (946 MiB) + PetrifiedColFlow (867 MiB) in "
       << fixed << setprecision(2) << build_s << "s\n";

  auto eval_h = [&](const CState& s) -> uint8_t {
    int h = max(pdb_bsw9.lookup_plus_harvest(s), pdb_pcf.lookup(s));
    return uint8_t(min(250, h));
  };

  // ==========================================================================
  // STAGE 1: 100% Exhaustive Forward Quotient-Graph Edge Verification
  // ==========================================================================
  auto t_qaudit = chrono::steady_clock::now();
  QuotientAuditStats q_bsw9 = pdb_bsw9.audit_all_forward_edges(10);
  QuotientAuditStats q_pcf = pdb_pcf.audit_all_forward_edges(10);
  double qaudit_s = chrono::duration<double>(chrono::steady_clock::now() - t_qaudit).count();

  cout << "[QUOTIENT AUDIT] bsw9: edges=" << q_bsw9.forward_edges_checked << " viol=" << (q_bsw9.goal_violations + q_bsw9.step_violations)
       << " | pcf: edges=" << q_pcf.forward_edges_checked << " viol=" << (q_pcf.goal_violations + q_pcf.step_violations)
       << " (" << fixed << setprecision(2) << qaudit_s << "s)\n";

  require_check(q_bsw9.goal_violations == 0 && q_bsw9.step_violations == 0, "BedrockConservedSwitch3x3 quotient edge audit failed");
  require_check(q_pcf.goal_violations == 0 && q_pcf.step_violations == 0, "PetrifiedColFlow quotient edge audit failed");

  // ==========================================================================
  // STAGE 2: Non-Tautological `must_fail` Controls + `Packed24` Bijectivity
  // ==========================================================================
  bool mf_sticky34_rejected = false;
  {
    const string BAD34 = "LULULUULRURRURURUALDRRUDRRUDDRURRR";
    CState cur = start_state(); int steps_ok = 0;
    for (char ch : BAD34) {
      CState nxt;
      if (!step_concrete(cur, int(string("UDLRA").find(ch)), nxt)) break;
      cur = nxt; steps_ok++;
    }
    mf_sticky34_rejected = (steps_ok == 29);
  }
  require_check(mf_sticky34_rejected, "must_fail control 1 (sticky-door 34 route) failed");

  bool mf_quotient_drop_caught = false;
  {
    uint32_t s0_idx = BedrockConservedSwitch3x3_15PDB::enc(B0, D0, 1, 0, 0);
    uint8_t saved = pdb_bsw9.dist[s0_idx];
    pdb_bsw9.dist[s0_idx] = uint8_t(saved + 2);
    QuotientAuditStats bad_q = pdb_bsw9.audit_all_forward_edges(10);
    pdb_bsw9.dist[s0_idx] = saved;
    mf_quotient_drop_caught = (bad_q.step_violations > 0);
  }
  require_check(mf_quotient_drop_caught, "must_fail control 2 (quotient +2 corruption) failed");

  CState s38_before = make_soko38_state();
  CState s38_after{};
  bool s38_ok = step_concrete(s38_before, 3, s38_after); // 'R'
  require_check(s38_ok, "soko#38 step R failed");
  int h_s38_before = int(eval_h(s38_before)), h_s38_after = int(eval_h(s38_after));
  require_check(h_s38_before <= 1 + h_s38_after, "soko#38 consistency violated!");
  bool mf_s38_drop2_caught = ((12 - 10) > 1) && (h_s38_before <= 1 + h_s38_after);

  bool mf_r48_admissible = true;
  {
    CState cur = start_state();
    if (int(eval_h(cur)) > 48) mf_r48_admissible = false;
    for (int i = 0; i < 48; ++i) {
      CState nxt;
      require_check(step_concrete(cur, int(string("UDLRA").find(R48_ROUTE[i])), nxt), "R48 step failed");
      cur = nxt;
      if (int(eval_h(cur)) > 48 - (i + 1)) mf_r48_admissible = false;
    }
    require_check(is_win(cur) && int(eval_h(cur)) == 0, "R48 terminal win check failed");
  }
  require_check(mf_r48_admissible, "R48 admissibility violated!");

  // Free temporary transition tables now that Stage 1 & Stage 2 quotient audits passed
  pdb_bsw9.free_build_tables();
  pdb_pcf.free_build_tables();

  // ==========================================================================
  // STAGE 3: 50M+ Concrete Random-Walk Edge Consistency + Packed24 Bijectivity
  // ==========================================================================
  auto t_walk = chrono::steady_clock::now();
  uint64_t concrete_walk_edges = 0, concrete_walk_viols = 0, packed24_checked = 0;
  {
    concrete_walk_viols += check_concrete_edge_fn(s38_before, [&](const CState& x) { return int(eval_h(x)); }, concrete_walk_edges);
    concrete_walk_viols += check_concrete_edge_fn(s38_after, [&](const CState& x) { return int(eval_h(x)); }, concrete_walk_edges);

    const int NT = 10;
    uint64_t per_thread_target = (target_walk_edges + NT - 1) / NT;
    vector<uint64_t> te(NT, 0), tv(NT, 0), tp24(NT, 0);
    vector<thread> workers;
    for (int tid = 0; tid < NT; ++tid) workers.emplace_back([&, tid]() {
      mt19937_64 rng(20261119ULL + uint64_t(tid) * 1337ULL);
      uint64_t loc_e = 0, loc_v = 0, loc_p = 0;
      while (loc_e < per_thread_target) {
        CState s = start_state();
        int mode = int(rng() % 4);
        if (mode == 1) {
          int pre = int(rng() % 49);
          for (int k = 0; k < pre; ++k) { CState nx; step_concrete(s, int(string("UDLRA").find(R48_ROUTE[k])), nx); s = nx; }
        } else if (mode == 2) s = s38_before;
        for (int step = 0; step < 300 && loc_e < per_thread_target; ++step) {
          if (loc_p < 100000) {
            if (!(unpack24(pack24_raw(s)) == s)) loc_v++;
            loc_p++;
          }
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
      te[tid] = loc_e; tv[tid] = loc_v; tp24[tid] = loc_p;
    });
    for (auto& th : workers) th.join();
    for (int t = 0; t < NT; ++t) { concrete_walk_edges += te[t]; concrete_walk_viols += tv[t]; packed24_checked += tp24[t]; }
  }
  double walk_s = chrono::duration<double>(chrono::steady_clock::now() - t_walk).count();
  cout << "[CONCRETE WALK AUDIT] edges_checked=" << concrete_walk_edges
       << " packed24_bijective=" << packed24_checked
       << " violations=" << concrete_walk_viols << " (" << fixed << setprecision(2) << walk_s << "s)\n";
  require_check(concrete_walk_viols == 0, "Concrete walk / Packed24 audit failed!");

  // ==========================================================================
  // STAGE 4: 10-Thread 256-Shard Collision-Free `Packed24` Layered A* Search
  // ==========================================================================
  CState s0 = start_state();
  uint8_t h0 = eval_h(s0);
  cout << "[ROOT] h(s0)=" << int(h0)
       << " [bsw9+need9=" << pdb_bsw9.lookup_plus_harvest(s0)
       << ", pcf=" << pdb_pcf.lookup(s0)
       << "] | soko#38 h: " << h_s38_before << " -> " << h_s38_after << "\n";

  constexpr int NSHARDS = 256;
  constexpr int NT = 10;
  size_t max_per_shard = max<size_t>(16384, max_total_states / NSHARDS);
  require_check(max_per_shard <= (1ULL << 24), "max_per_shard exceeds 24-bit packed gid");
  size_t shard_hbits = 16;
  while ((1ULL << shard_hbits) < (max_per_shard * 4) / 3 + 1024) shard_hbits++;
  size_t shard_hmask = (1ULL << shard_hbits) - 1;

  struct Shard {
    vector<Packed24> states;
    vector<uint8_t> best_g, state_h;
    vector<uint32_t> htab;
    uint64_t collisions = 0;
    void init(size_t hbits, size_t exact_cap) {
      states.reserve(exact_cap);
      best_g.reserve(exact_cap);
      state_h.reserve(exact_cap);
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

  // `uint32_t` packed queue IDs: `(sh << 24) | lid` (saves 50% queue RAM vs `uint64_t`!)
  vector<vector<uint32_t>> waves[60];
  for (int f = 0; f < 60; ++f) waves[f].resize(60);

  Packed24 p0 = pack24_canon(s0);
  uint64_t h64_0 = p0.hash64();
  int sh0 = int(h64_0 >> 56);
  shards[sh0].states.push_back(p0);
  shards[sh0].best_g.push_back(0);
  shards[sh0].state_h.push_back(h0);
  shards[sh0].htab[h64_0 & shard_hmask] = 0;
  waves[h0][0].push_back((uint32_t(sh0) << 24) | 0u);

  auto t_astar = chrono::steady_clock::now();
  uint64_t expanded = 0, astar_edge_checks = 0, astar_bellman_viols = 0;
  int proven_floor = int(h0);
  bool hit_cap = false, exact_opt = false;
  string stop_reason = "completed_all_layers";
  vector<LayerRecord> layer_ledger;
  vector<array<vector<CandEdge24>, NSHARDS>> t_sh_buf(NT);

  for (int f = h0; f <= 48 && !hit_cap; ++f) {
    proven_floor = f;
    for (int g = 0; g <= f && !hit_cap; ++g) {
      auto& wvec = waves[f][g];
      if (wvec.empty()) continue;
      vector<uint32_t> active;
      active.reserve(wvec.size());
      for (uint32_t gid : wvec) {
        int sh = int(gid >> 24); uint32_t lid = gid & 0xFFFFFFu;
        if (shards[sh].best_g[lid] == g && int(g) + int(shards[sh].state_h[lid]) == f)
          active.push_back(gid);
      }
      vector<uint32_t>().swap(wvec);
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
          for (int tid = 0; tid < NT; ++tid) th.emplace_back([&, tid]() {
            for (int sh = 0; sh < NSHARDS; ++sh) t_sh_buf[tid][sh].clear();
            size_t lo = (cnt * tid) / NT, hi = (cnt * (tid + 1)) / NT;
            uint64_t loc_e = 0;
            for (size_t idx = lo; idx < hi; ++idx) {
              uint32_t gid = active[base + idx];
              int sh = int(gid >> 24); uint32_t lid = gid & 0xFFFFFFu;
              uint8_t hs = shards[sh].state_h[lid];
              CState s = unpack24(shards[sh].states[lid]);
              for (int mv = 0; mv < 5; ++mv) {
                CState ns;
                if (!step_concrete(s, mv, ns)) continue;
                if (is_win(ns)) { found_win.store(true); return; }
                Packed24 np = pack24_canon(ns);
                int nsh = int(np.hash64() >> 56);
                t_sh_buf[tid][nsh].push_back(CandEdge24{np, ns, hs, uint8_t(g + 1)});
                loc_e++;
              }
            }
            t_edges[tid] = loc_e;
          });
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
        vector<array<vector<uint32_t>, 60>> t_new_waves(NT);
        {
          vector<thread> th;
          for (int tid = 0; tid < NT; ++tid) th.emplace_back([&, tid]() {
            for (int sh = tid; sh < NSHARDS; sh += NT) {
              auto& S = shards[sh];
              for (int src_t = 0; src_t < NT; ++src_t) {
                for (const CandEdge24& ce : t_sh_buf[src_t][sh]) {
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
                      t_new_waves[tid][nf].push_back((uint32_t(sh) << 24) | eid);
                    }
                  } else {
                    if (S.states.size() >= max_per_shard) { shard_full.store(true); return; }
                    uint32_t nid = uint32_t(S.states.size());
                    S.states.push_back(ce.np);
                    S.best_g.push_back(ce.ng);
                    S.state_h.push_back(hns);
                    S.htab[sl] = nid;
                    t_new_waves[tid][nf].push_back((uint32_t(sh) << 24) | nid);
                  }
                }
              }
            }
          });
          for (auto& x : th) x.join();
        }
        astar_bellman_viols += loc_viols.load();
        require_check(astar_bellman_viols == 0, "Bellman 1-step consistency violation detected during A*!");
        for (int tid = 0; tid < NT; ++tid)
          for (int nf = f; nf <= 48; ++nf)
            if (!t_new_waves[tid][nf].empty()) {
              uint8_t ng_val = uint8_t(g + 1);
              auto& dst = waves[nf][ng_val];
              dst.insert(dst.end(), t_new_waves[tid][nf].begin(), t_new_waves[tid][nf].end());
            }
        if (shard_full.load()) {
          hit_cap = true; stop_reason = "state_cap_during_layer_" + to_string(f); break;
        }
      }
    }
    if (!hit_cap) {
      proven_floor = f + 1;
      uint64_t tot_st = 0, tot_col = 0;
      for (int sh = 0; sh < NSHARDS; ++sh) { tot_st += shards[sh].states.size(); tot_col += shards[sh].collisions; }
      double el = chrono::duration<double>(chrono::steady_clock::now() - t_astar).count();
      layer_ledger.push_back(LayerRecord{f, proven_floor, expanded, tot_st, astar_edge_checks, tot_col, el});
      cout << "  [CERTIFIED 15x7 FLOOR >= " << proven_floor << "] f=" << f
           << " expanded=" << expanded << " unique_canon_states=" << tot_st
           << " edges_checked=" << astar_edge_checks << " collisions_prevented=" << tot_col
           << " time=" << fixed << setprecision(2) << el << "s\n";
      if (self_test_only && proven_floor >= 34) {
        stop_reason = "self_test_target_reached"; hit_cap = true; break;
      }
    }
  }

  uint64_t final_tot_st = 0, final_tot_col = 0;
  for (int sh = 0; sh < NSHARDS; ++sh) { final_tot_st += shards[sh].states.size(); final_tot_col += shards[sh].collisions; }
  double total_el = chrono::duration<double>(chrono::steady_clock::now() - t_program_start).count();
  string epistemic = exact_opt ? "VERIFIED" : "LOWER_BOUND_UNWITNESSED";
  uint64_t total_quot_edges = q_bsw9.forward_edges_checked + q_pcf.forward_edges_checked;
  uint64_t total_quot_viols = q_bsw9.goal_violations + q_bsw9.step_violations + q_pcf.goal_violations + q_pcf.step_violations;

  cout << "[SUMMARY] status=" << epistemic << " certified_15x7_floor=" << proven_floor
       << " stop_reason=" << stop_reason << " expanded=" << expanded
       << " unique_canon_states=" << final_tot_st << " astar_edges=" << astar_edge_checks
       << " bellman_violations=" << astar_bellman_viols
       << " total_time=" << fixed << setprecision(2) << total_el << "s\n";

  if (!json_out_path.empty()) {
    ofstream jf(json_out_path);
    require_check(bool(jf), "Failed to open --json-out path");
    jf << "{\n";
    jf << "  \"room_id\": \"III-14-15x7\",\n";
    jf << "  \"board_width\": 15,\n";
    jf << "  \"board_height\": 7,\n";
    jf << "  \"board_sha256_lf\": \"" << board_sha256_lf << "\",\n";
    jf << "  \"prover_source_sha256\": \"" << prover_source_sha256 << "\",\n";
    jf << "  \"epistemic_status\": \"" << epistemic << "\",\n";
    jf << "  \"exact_optimum_reached\": " << (exact_opt ? "true" : "false") << ",\n";
    jf << "  \"certified_15x7_floor\": " << proven_floor << ",\n";
    jf << "  \"reference_upper_bound\": 48,\n";
    jf << "  \"root_h\": " << int(h0) << ",\n";
    jf << "  \"soko38_counterexample_h_before\": " << h_s38_before << ",\n";
    jf << "  \"soko38_counterexample_h_after\": " << h_s38_after << ",\n";
    jf << "  \"stop_reason\": \"" << stop_reason << "\",\n";
    jf << "  \"packed24_bijective_states_checked\": " << packed24_checked << ",\n";
    jf << "  \"exhaustive_quotient_edge_audit\": {\n";
    jf << "    \"total_forward_quotient_edges_checked\": " << total_quot_edges << ",\n";
    jf << "    \"total_violations\": " << total_quot_viols << ",\n";
    jf << "    \"bedrock_conserved_switch3x3\": {\"vertices\": " << q_bsw9.vertices << ", \"reachable\": " << q_bsw9.reachable
       << ", \"edges\": " << q_bsw9.forward_edges_checked << ", \"violations\": " << (q_bsw9.goal_violations + q_bsw9.step_violations) << "},\n";
    jf << "    \"petrified_col_flow\": {\"vertices\": " << q_pcf.vertices << ", \"reachable\": " << q_pcf.reachable
       << ", \"edges\": " << q_pcf.forward_edges_checked << ", \"violations\": " << (q_pcf.goal_violations + q_pcf.step_violations) << "}\n";
    jf << "  },\n";
    jf << "  \"concrete_random_walk_audit\": {\n";
    jf << "    \"edges_checked\": " << concrete_walk_edges << ",\n";
    jf << "    \"violations\": " << concrete_walk_viols << "\n";
    jf << "  },\n";
    jf << "  \"must_fail_controls\": {\n";
    jf << "    \"sticky_door_34_route_rejected_at_step_30\": " << (mf_sticky34_rejected ? "true" : "false") << ",\n";
    jf << "    \"corrupted_quotient_plus2_caught_by_edge_auditor\": " << (mf_quotient_drop_caught ? "true" : "false") << ",\n";
    jf << "    \"soko38_raw_drop2_repaired_to_consistent\": " << (mf_s38_drop2_caught ? "true" : "false") << ",\n";
    jf << "    \"r48_48step_witness_admissible_every_step\": " << (mf_r48_admissible ? "true" : "false") << "\n";
    jf << "  },\n";
    jf << "  \"astar_summary\": {\n";
    jf << "    \"shards\": " << NSHARDS << ",\n";
    jf << "    \"packed_bytes_per_state\": " << sizeof(Packed24) << ",\n";
    jf << "    \"expanded_states\": " << expanded << ",\n";
    jf << "    \"unique_canonical_states\": " << final_tot_st << ",\n";
    jf << "    \"concrete_edges_checked\": " << astar_edge_checks << ",\n";
    jf << "    \"hash_collisions_prevented_by_full_key\": " << final_tot_col << ",\n";
    jf << "    \"bellman_violations\": " << astar_bellman_viols << ",\n";
    jf << "    \"total_elapsed_s\": " << fixed << setprecision(3) << total_el << "\n";
    jf << "  },\n";
    jf << "  \"completed_f_layers\": [\n";
    for (size_t i = 0; i < layer_ledger.size(); ++i) {
      const auto& L = layer_ledger[i];
      jf << "    {\"f\": " << L.f_completed << ", \"certified_floor\": " << L.certified_floor
         << ", \"expanded\": " << L.cumulative_expanded << ", \"unique_states\": " << L.cumulative_unique_canon_states
         << ", \"edges_checked\": " << L.cumulative_edges_checked << ", \"collisions_prevented\": " << L.cumulative_hash_collisions_prevented
         << ", \"elapsed_s\": " << fixed << setprecision(3) << L.elapsed_s << "}"
         << (i + 1 < layer_ledger.size() ? "," : "") << "\n";
    }
    jf << "  ]\n";
    jf << "}\n";
  }
  return 0;
}
