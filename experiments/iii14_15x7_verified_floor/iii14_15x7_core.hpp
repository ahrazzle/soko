#pragma once
// prove_iii14_15x7_exact_ps.cpp
// Exact Part III PuzzleScript Semantics (with Purple Door Crush & Crushed-Obstacle Erasure)
// Collision-Free 15x7 Quotient-Homomorphism + Vertical-Automorphism Prover for Room III-14.
#include <bits/stdc++.h>
#include <thread>
using namespace std;

using u128 = unsigned __int128;
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
    "###############"
};

static inline u128 bit(int i) { return ((u128)1) << i; }
static inline bool tst(u128 m, int i) { return (m >> i) & 1; }
static inline int popcnt128(u128 m) {
    return __builtin_popcountll((uint64_t)m) + __builtin_popcountll((uint64_t)(m >> 64));
}

static u128 ORIGIN_MASK = 0, SWITCH_MASK = 0, PDOOR_MASK = 0, CHAMBER_MASK = 0, AURA[N]{}, ORTHO[N]{};
static u128 D5_MASK[5]{}, QUAD_MASK[4]{};
static int D5_RING[N]{}, QUAD_OF[N]{};
static bool IS_ORIG[N], IS_SW[N], IS_PD[N], IS_VAULT[N];
static int B0 = -1, D0 = -1, GOALS[2];

inline int mirror_y_cell(int i) { return (6 - (i / W)) * W + (i % W); }
inline u128 mirror_y_mask(u128 m) {
    constexpr u128 RM = (u128(1) << 15) - 1;
    u128 r0 = (m >>  0) & RM, r1 = (m >> 15) & RM, r2 = (m >> 30) & RM, r3 = (m >> 45) & RM;
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
        s.bx, (uint8_t)(6 - s.by), s.dx, (uint8_t)(6 - s.dy), s.ah, s.doors_open
    };
}

// 35-byte exact collision-free canonical state (doors_open packed into b_pos bit 7 since N=105 < 128!)
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
    return Packed15{(uint64_t)s.crates, (uint64_t)s.walls, (uint32_t)(s.crates >> 64), (uint32_t)(s.walls >> 64),
                    (uint16_t)(s.crates >> 96), (uint16_t)(s.walls >> 96),
                    (uint8_t)((s.by * W + s.bx) | (s.doors_open << 7)), (uint8_t)((s.dy * W + s.dx) | (s.ah << 7))};
}
inline Packed15 pack_canon(const CState& s) { Packed15 p1 = pack_raw(s), p2 = pack_raw(mirror_y_state(s)); return (p2 < p1) ? p2 : p1; }
inline CState unpack15(const Packed15& p) {
    CState s{};
    s.crates = (u128)p.c_lo | ((u128)p.c_mid << 64) | ((u128)p.c_hi << 96);
    s.walls  = (u128)p.w_lo | ((u128)p.w_mid << 64) | ((u128)p.w_hi << 96);
    uint8_t bp = p.b_and_do & 127; s.bx = bp % W; s.by = bp / W; s.doors_open = (p.b_and_do >> 7) & 1;
    uint8_t dp = p.d_and_ah & 127; s.dx = dp % W; s.dy = dp / W; s.ah = (p.d_and_ah >> 7) & 1;
    return s;
}
// Exact Part III PuzzleScript step for Room III-14 (matches soko_mcp/oracle.py bit-for-bit!)
inline bool step_concrete(const CState& s, int mv, CState& ns) {
    ns = s;
    u128 closed = ns.doors_open ? 0 : PDOOR_MASK;
    if (mv == 4) {
        ns.ah = 1 - ns.ah;
    } else if (ns.ah == 1) {
        int nx = (int)ns.dx + DX[mv], ny = (int)ns.dy + DY[mv];
        // Note: if Druid steps onto unshielded Bard, Bard turns into '#' leaving <2 heroes (irrecoverable loss)
        if (nx < 0 || nx >= W || ny < 0 || ny >= H || (nx == ns.bx && ny == ns.by)) return false;
        int ni = ny * W + nx;
        if (tst(closed, ni)) return false;
        if (tst(ns.crates, ni)) { ns.crates &= ~bit(ni); ns.walls |= bit(ni); }
        else if (tst(ns.walls, ni)) { ns.crates |= bit(ni); ns.walls &= ~bit(ni); }
        else { ns.dx = nx; ns.dy = ny; }
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
                int tx = (int)ns.dx + DX[mv], ty = (int)ns.dy + DY[mv];
                if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
                    int ti = ty * W + tx;
                    if (!tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.bx && ty == ns.by)) {
                        ns.dx = tx; ns.dy = ty; d_ch = false; chg = true;
                    }
                }
            }
            if (!b_mv) {
                int tx = (int)ns.bx + DX[mv], ty = (int)ns.by + DY[mv];
                if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
                    int ti = ty * W + tx;
                    if (!tst(ns.walls | closed | ns.crates, ti) && !(tx == ns.dx && ty == ns.dy)) {
                        ns.bx = tx; ns.by = ty; b_mv = true; chg = true;
                    }
                }
            }
        }
        // In Part III, if Bard fails to move, action cancels to pre-move state (self-loop, never optimal in shortest path)
        if (!b_mv) return false;
    }
    // Late phase: Purple switches & crushing purple doors (oracle.py lines 302-320)
    u128 weighing = ns.crates | ns.walls | bit(ns.by * W + ns.bx) | bit(ns.dy * W + ns.dx);
    bool all_sw = ((weighing & SWITCH_MASK) == SWITCH_MASK);
    if (all_sw) {
        ns.doors_open = 1;
    } else if (ns.doors_open) {
        ns.doors_open = 0;
        if (tst(PDOOR_MASK, ns.by * W + ns.bx) || tst(PDOOR_MASK, ns.dy * W + ns.dx)) return false; // Hero crushed!
        ns.crates &= ~PDOOR_MASK;
        ns.walls  &= ~PDOOR_MASK;
    }
    return true;
}

inline bool is_win(const CState& s) {
    int bp = s.by * W + s.bx, dp = s.dy * W + s.dx;
    return (bp == GOALS[0] && dp == GOALS[1]) || (bp == GOALS[1] && dp == GOALS[0]);
}
