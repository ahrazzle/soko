/*
 * soko_engine.cpp - Hardened Zero-Allocation C++20 PuzzleScript Solver, Chiral-Mirror Optimizer & Exact-TT Quotient-PDB Prover
 * ============================================================================================================================
 * v0.2.0 Soundness & Performance Upgrades (Seat `fdn0-eval` Audit Fixes):
 *   - F-02 Fix: `verify` mode computes a 64-bit FNV-1a rolling per-frame trajectory digest (`traj_fnv64`) across every
 *     step t = 0..L covering (obj[0..n-1], notes_mask, y_open_eff, p_open_eff), matching Python `PuzzleScriptOracle`
 *     and `FlatBitmaskOracle` bit-for-bit.
 *   - F-04 Fix (Collision-Free Exact-State TT): `prove_lb` stores full `DynState` records in a bounded linear-probing
 *     transposition table and requires `s.eq(slot.state, ...)` before pruning — eliminating 48-bit hash-collision unsoundness.
 *   - F-04 Fix (Automatic Quotient-PDB + Switch-Deficit Heuristic): `prove_lb` automatically constructs a general
 *     backward-BFS Quotient Pattern Database for Bard+Druid+PurpleSwitch rooms (including both 14x7 and 15x7 III-14)
 *     and checks `h(s) <= 1 + h(s')` on every expanded edge (failing closed with structured JSON instead of silent pruning).
 *   - Collision-safe bucket chaining in `exact_window_shortcut`.
 */

#include <bits/stdc++.h>
using namespace std;

static constexpr int MAX_CELLS = 512;
static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};
static const char DCH[5] = {'U', 'D', 'L', 'R', 'A'};
inline int d_idx(char c) { return c=='U'?0:c=='D'?1:c=='L'?2:c=='R'?3:c=='A'?4:-1; }

struct LevelMeta {
    int part = 3;
    int w = 0, h = 0, n = 0;
    uint8_t floor_grid[MAX_CELLS] = {};
    uint8_t near_goal[MAX_CELLS] = {};
    uint8_t init_wall[MAX_CELLS] = {};
    vector<int> goals, y_switches, p_switches, y_doors_init, p_doors_init;
    int max_heroes = 6;
    bool has_bard = false;
};

struct DynState {
    uint8_t obj[MAX_CELLS];
    uint64_t notes[8]; // 512-bit Note mask for Part 3 Bard
    uint8_t y_open = 0;
    uint8_t p_open = 0;

    inline bool has_note(int i) const { return (notes[i >> 6] >> (i & 63)) & 1ULL; }
    inline void set_note(int i) { notes[i >> 6] |= (1ULL << (i & 63)); }
    inline void clr_notes() { memset(notes, 0, sizeof(notes)); }

    bool eq(const DynState& o, int n, bool check_notes) const {
        if (y_open != o.y_open || p_open != o.p_open) return false;
        if (memcmp(obj, o.obj, n) != 0) return false;
        if (check_notes && memcmp(notes, o.notes, sizeof(notes)) != 0) return false;
        return true;
    }

    // Each 8-byte word is absorbed with a multiply followed by an xorshift.
    // A multiply alone (the earlier FNV-style loop) only carries bits upward,
    // so states that differed only in the high bytes of a word collided:
    // 0.2-0.8% of distinct states shared a full 64-bit hash, against about
    // 1e-6 expected from the birthday bound. Exact-state tables still compare
    // full states; the hash-only sets in the beam modes now lose almost none.
    static inline uint64_t absorb(uint64_t h, uint64_t w) {
        h ^= w; h *= 0xbf58476d1ce4e5b9ULL; return h ^ (h >> 31);
    }
    uint64_t hash64(int n, bool check_notes) const {
        uint64_t h = 1469598103934665603ULL;
        int i = 0;
        for (; i + 8 <= n; i += 8) { uint64_t w; memcpy(&w, obj + i, 8); h = absorb(h, w); }
        if (i < n) { uint64_t w = 0; memcpy(&w, obj + i, n - i); h = absorb(h, w ^ ((uint64_t)(n - i) << 56)); }
        h = absorb(h, ((uint64_t)y_open << 8) | p_open | 0x10000ULL);
        if (check_notes) {
            int nw = (n + 63) >> 6;
            for (int k = 0; k < nw; ++k) if (notes[k]) h = absorb(h ^ ((uint64_t)k << 58), notes[k]);
        }
        h ^= h >> 33; h *= 0x94d049bb133111ebULL; return h ^ (h >> 29);
    }
};

static inline uint64_t fold_traj_fnv64(const LevelMeta& M, const DynState& s, uint64_t acc) {
    static constexpr uint64_t FNV_PRIME = 1099511628211ULL;
    uint64_t h = acc;
    for (int i = 0; i < M.n; ++i) {
        uint64_t nbit = (M.part == 3 && s.has_note(i)) ? 1ULL : 0ULL;
        uint64_t bval = (uint64_t)(s.obj[i] & 0x1F) | (nbit << 5);
        h = (h ^ bval) * FNV_PRIME;
    }
    uint64_t y_eff = (!M.y_doors_init.empty() && s.y_open) ? 1ULL : 0ULL;
    uint64_t p_eff = (!M.p_doors_init.empty() && s.p_open) ? 1ULL : 0ULL;
    uint64_t dflags = y_eff | (p_eff << 1);
    h = (h ^ dflags) * FNV_PRIME;
    h = (h ^ 0xFFULL) * FNV_PRIME;
    return h;
}

static inline bool is_active(uint8_t v) { return v >= 1 && v <= 6; }
static inline bool is_inactive(uint8_t v) { return v >= 7 && v <= 12; }
static inline bool is_hero(uint8_t v) { return v >= 1 && v <= 12; }
static inline bool is_healer(uint8_t v) { return v == 4 || v == 10; }
static inline bool is_monster(int part, uint8_t v) {
    if (part == 1) return false;
    return part == 2 ? (v >= 15 && v <= 17) : (v == 15);
}
static inline bool is_moveable(int part, uint8_t v) { return v == 14 || is_inactive(v) || is_monster(part, v); }
static inline bool is_static_obj(uint8_t v) { return v == 13 || v == 18 || v == 19 || v == 20; }
static inline bool is_vulnerable(int part, uint8_t v) { return is_hero(v) || is_monster(part, v); }
static inline bool is_weighing(int part, uint8_t v) {
    return (part == 3) ? (v == 14 || v == 13 || is_hero(v) || is_monster(part, v))
                       : (v == 14 || is_hero(v) || is_monster(part, v));
}

void compute_notes(const LevelMeta& M, DynState& s) {
    s.clr_notes();
    if (!M.has_bard) return;
    int bi = -1;
    for (int i = 0; i < M.n; ++i) if (s.obj[i] == 5) { bi = i; break; }
    if (bi < 0) return;
    int bx = bi % M.w, by = bi / M.w;
    for (int ny = max(0, by - 2); ny <= min(M.h - 1, by + 2); ++ny)
        for (int nx = max(0, bx - 2); nx <= min(M.w - 1, bx + 2); ++nx) {
            if (nx == bx && ny == by) continue;
            int ni = ny * M.w + nx;
            if (is_moveable(M.part, s.obj[ni])) s.set_note(ni);
        }
}

bool run_late(const LevelMeta& M, DynState& s) {
    if (M.has_bard) compute_notes(M, s);

    uint8_t dying[MAX_CELLS] = {};
    if (M.part == 2) {
        for (int y = 0; y < M.h; ++y)
            for (int x = 0; x < M.w; ++x) {
                uint8_t o = s.obj[y * M.w + x];
                if (o == 17) {
                    for (int nx = x + 1; nx < M.w; ++nx) {
                        uint8_t no = s.obj[y * M.w + nx];
                        if (!no) continue;
                        if (is_vulnerable(M.part, no)) dying[y * M.w + nx] = 1;
                        break;
                    }
                } else if (o == 16) {
                    for (int nx = x - 1; nx >= 0; --nx) {
                        uint8_t no = s.obj[y * M.w + nx];
                        if (!no) continue;
                        if (is_vulnerable(M.part, no)) dying[y * M.w + nx] = 1;
                        break;
                    }
                }
            }
    }
    if (M.part >= 2) {
        for (int y = 0; y < M.h; ++y)
            for (int x = 0; x < M.w; ++x)
                if (s.obj[y * M.w + x] == 15)
                    for (int d = 0; d < 4; ++d) {
                        int nx = x + DX[d], ny = y + DY[d];
                        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && is_vulnerable(M.part, s.obj[ny * M.w + nx]))
                            dying[ny * M.w + nx] = 1;
                    }
        for (int i = 0; i < M.n; ++i)
            if (is_healer(s.obj[i])) {
                dying[i] = 0;
                int x = i % M.w, y = i / M.w;
                for (int d = 0; d < 4; ++d) {
                    int nx = x + DX[d], ny = y + DY[d];
                    if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h) {
                        int ni = ny * M.w + nx;
                        if (dying[ni] && is_hero(s.obj[ni])) dying[ni] = 0;
                    }
                }
            }
        for (int i = 0; i < M.n; ++i) {
            if (dying[i]) {
                if (is_monster(M.part, s.obj[i])) s.obj[i] = 0;
                else if (is_hero(s.obj[i])) return true;
            }
        }
    }
    if (!M.y_switches.empty()) {
        bool any_w = false, any_u = false;
        for (int idx : M.y_switches) { if (is_weighing(M.part, s.obj[idx])) any_w = true; else any_u = true; }
        if (any_w && !any_u && !M.y_doors_init.empty() && !s.y_open) {
            s.y_open = 1;
            for (int idx : M.y_doors_init) if (s.obj[idx] == 18) s.obj[idx] = 0;
        } else if (any_u && s.y_open) {
            s.y_open = 0;
            for (int idx : M.y_doors_init) { if (is_hero(s.obj[idx])) return true; s.obj[idx] = 18; }
        }
    }
    if (!M.p_switches.empty()) {
        bool any_w = false, any_u = false;
        for (int idx : M.p_switches) { if (is_weighing(M.part, s.obj[idx])) any_w = true; else any_u = true; }
        if (any_w && !any_u && !M.p_doors_init.empty() && !s.p_open) {
            s.p_open = 1;
            for (int idx : M.p_doors_init) if (s.obj[idx] == 19) s.obj[idx] = 0;
        } else if (any_u && s.p_open) {
            s.p_open = 0;
            for (int idx : M.p_doors_init) { if (is_hero(s.obj[idx])) return true; s.obj[idx] = 19; }
        }
    }
    // The monster gate opens after the door phase: a closing colored door may
    // crush the last monster on this same turn (original rule order).
    if (M.part >= 2) {
        bool any_monster = false;
        for (int i = 0; i < M.n && !any_monster; ++i) any_monster = is_monster(M.part, s.obj[i]);
        if (!any_monster) for (int i = 0; i < M.n; ++i) if (s.obj[i] == 20) s.obj[i] = 0;
    }
    if (M.has_bard) {
        for (int i = 0; i < M.n; ++i) if (s.has_note(i) && !is_moveable(M.part, s.obj[i])) s.notes[i >> 6] &= ~(1ULL << (i & 63));
    }
    return false;
}

inline bool check_win(const LevelMeta& M, const DynState& s) {
    for (int g : M.goals) if (!is_hero(s.obj[g])) return false;
    int hc = 0;
    for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) hc++;
    return hc == (int)M.goals.size();
}

// Several simultaneously active heroes (e.g. I-22, II-12, III-22). PuzzleScript
// assigns directions to every Player at once and resolves ability rules before
// ordinary movement; this mirrors PuzzleScriptOracle._step_multiple.
// Scope: it mirrors the oracle under default flags only. The oracle's planted-bug
// mutators (BUG_09 cycle order, BUG_10 cancel exemption) have no native plumbing,
// like the rest of this engine, so do not assume flag parity with the oracle.
int multi_step_state(const LevelMeta& M, DynState& s, int mv, bool prune_noop) {
    const DynState snap = s;
    int players[MAX_CELLS], np = 0;
    uint8_t initial[MAX_CELLS];
    for (int i = 0; i < M.n; ++i) if (is_active(s.obj[i])) players[np++] = i;
    for (int k = 0; k < np; ++k) initial[k] = s.obj[players[k]];
    auto cancel = [&]() {
        s = snap;
        return prune_noop ? -1 : (check_win(M, s) ? 1 : 0);
    };
    auto finish = [&]() {
        if (M.part == 2)
            for (int k = 0; k < np; ++k) if (is_active(s.obj[players[k]])) return cancel();
        if (run_late(M, s)) return -1;
        if (prune_noop && s.eq(snap, M.n, M.has_bard)) return -1;
        return check_win(M, s) ? 1 : 0;
    };

    if (mv == 4) {
        bool pending[MAX_CELLS] = {};
        for (int k = 0; k < np; ++k) pending[k] = true;
        for (int offset = 1; offset < M.max_heroes; ++offset)
            for (int slot = 0; slot < M.max_heroes; ++slot) {
                uint8_t identity = (uint8_t)(slot + 7);
                for (int k = 0; k < np; ++k) {
                    if (!pending[k] || initial[k] + 6 != identity) continue;
                    uint8_t target = (uint8_t)(((slot + offset) % M.max_heroes) + 7);
                    int f = -1;
                    for (int x = 0; x < M.w && f < 0; ++x)
                        for (int y = 0; y < M.h; ++y)
                            if (s.obj[y * M.w + x] == target) { f = y * M.w + x; break; }
                    if (f >= 0) { s.obj[players[k]] = identity; s.obj[f] = (uint8_t)(target - 6); pending[k] = false; }
                }
            }
        return finish();
    }

    const int dx = DX[mv], dy = DY[mv];
    auto adj = [&](int i) {
        int x = i % M.w + dx, y = i / M.w + dy;
        return (x >= 0 && x < M.w && y >= 0 && y < M.h) ? y * M.w + x : -1;
    };
    bool motion[MAX_CELLS] = {};
    for (int k = 0; k < np; ++k) motion[players[k]] = true;
    for (int k = 0; k < np; ++k) {
        int src = players[k];
        if (initial[k] == 1) {
            for (int t = adj(src); t >= 0 && is_moveable(M.part, s.obj[t]); t = adj(t)) motion[t] = true;
        } else if (initial[k] == 2) {
            int x = src % M.w - dx, y = src / M.w - dy;
            if (x >= 0 && x < M.w && y >= 0 && y < M.h && is_moveable(M.part, s.obj[y * M.w + x])) motion[y * M.w + x] = true;
        }
    }
    for (int k = 0; k < np; ++k) {  // Wizard warpballs pass through active heroes.
        if (initial[k] != 3) continue;
        int src = players[k];
        motion[src] = false;
        int t = adj(src);
        while (t >= 0) {
            uint8_t o = s.obj[t];
            if (is_static_obj(o)) { motion[src] = true; break; }
            if (is_moveable(M.part, o)) { s.obj[src] = o; s.obj[t] = 3; break; }
            t = adj(t);
        }
        if (t < 0 && M.part == 3) motion[src] = true;
    }
    for (int k = 0; k < np; ++k) {  // Druid transformations precede movement.
        int src = players[k];
        if (initial[k] != 6 || s.obj[src] != 6) continue;
        int t = adj(src);
        if (t < 0 || s.obj[t] == 0) continue;
        motion[src] = false;
        uint8_t o = s.obj[t];
        if (o == 14 || o == 15 || o == 13) s.obj[t] = (o == 13) ? 14 : 13;
        else if (is_hero(o) && !is_healer(o)) {
            bool shielded = false;
            int tx = t % M.w, ty = t / M.w;
            for (int d = 0; d < 4; ++d) {
                int hx = tx + DX[d], hy = ty + DY[d];
                if (hx >= 0 && hx < M.w && hy >= 0 && hy < M.h && is_healer(s.obj[hy * M.w + hx])) shielded = true;
            }
            if (!shielded) s.obj[t] = 13;
        }
    }
    bool bard[MAX_CELLS] = {};
    bool any_bard = false;
    for (int k = 0; k < np; ++k)
        if (initial[k] == 5 && s.obj[players[k]] == 5) { bard[players[k]] = true; any_bard = true; }
    if (any_bard) {  // Bard pseudo-movement overwrites other active heroes.
        bool pending[MAX_CELLS] = {};
        for (int i = 0; i < M.n; ++i) {
            pending[i] = bard[i] || (s.has_note(i) && is_moveable(M.part, s.obj[i]));
            if (bard[i]) motion[i] = false;
        }
        for (bool progress = true; progress;) {
            progress = false;
            for (int i = 0; i < M.n; ++i) {
                if (!pending[i]) continue;
                int t = adj(i);
                if (t >= 0 && (s.obj[t] == 0 || (is_active(s.obj[t]) && s.obj[t] != 5))) {
                    s.obj[t] = s.obj[i]; s.obj[i] = 0; pending[i] = false; progress = true;
                }
            }
        }
        for (int i = 0; i < M.n; ++i) if (pending[i] && bard[i]) return cancel();
    }
    if (M.has_bard) s.clr_notes();
    for (bool progress = true; progress;) {
        progress = false;
        for (int i = 0; i < M.n; ++i) {
            if (!motion[i]) continue;
            int t = adj(i);
            if (t >= 0 && s.obj[t] == 0) { s.obj[t] = s.obj[i]; s.obj[i] = 0; motion[i] = false; progress = true; }
        }
    }
    return finish();
}

int step_state(const LevelMeta& M, DynState& s, int mv, bool prune_noop = true) {
    int active_count = 0;
    for (int i = 0; i < M.n && active_count < 2; ++i) if (is_active(s.obj[i])) ++active_count;
    if (active_count > 1) return multi_step_state(M, s, mv, prune_noop);
    int ai = -1;
    for (int i = 0; i < M.n; ++i) if (is_active(s.obj[i])) { ai = i; break; }
    if (ai < 0) return -1;
    int ax = ai % M.w, ay = ai / M.w;
    uint8_t ah = s.obj[ai];
    DynState snap = s;

    if (mv == 4) {
        if (M.has_bard) s.clr_notes();
        bool switched = false;
        for (int off = 1; off < M.max_heroes; ++off) {
            uint8_t th = ((ah - 1 + off) % M.max_heroes) + 1, ti = th + 6;
            int f = -1;
            for (int x = 0; x < M.w && f < 0; ++x)
                for (int y = 0; y < M.h; ++y)
                    if (s.obj[y * M.w + x] == ti) { f = y * M.w + x; break; }
            if (f >= 0) { s.obj[ai] = ah + 6; s.obj[f] = th; switched = true; break; }
        }
        if (!switched) {
            if (prune_noop) return -1;
            if (M.part <= 2) return check_win(M, s) ? 1 : 0;
        }
        if (run_late(M, s)) return -1;
        if (prune_noop && s.eq(snap, M.n, M.has_bard)) return -1;
        return check_win(M, s) ? 1 : 0;
    }

    int dx = DX[mv], dy = DY[mv], nx = ax + dx, ny = ay + dy;
    bool moved = false;

    if (ah == 1) {
        if (M.has_bard) s.clr_notes();
        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h) {
            int cx = nx, cy = ny;
            while (cx >= 0 && cx < M.w && cy >= 0 && cy < M.h && is_moveable(M.part, s.obj[cy * M.w + cx])) { cx += dx; cy += dy; }
            if (cx >= 0 && cx < M.w && cy >= 0 && cy < M.h && s.obj[cy * M.w + cx] == 0) {
                while (cx != ax || cy != ay) {
                    int px = cx - dx, py = cy - dy;
                    s.obj[cy * M.w + cx] = s.obj[py * M.w + px]; cx = px; cy = py;
                }
                s.obj[ai] = 0; moved = true;
            }
        }
    } else if (ah == 2) {
        if (M.has_bard) s.clr_notes();
        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && s.obj[ny * M.w + nx] == 0) {
            int bx = ax - dx, by = ay - dy;
            s.obj[ny * M.w + nx] = 2;
            if (bx >= 0 && bx < M.w && by >= 0 && by < M.h && is_moveable(M.part, s.obj[by * M.w + bx])) {
                s.obj[ai] = s.obj[by * M.w + bx]; s.obj[by * M.w + bx] = 0;
            } else s.obj[ai] = 0;
            moved = true;
        }
    } else if (ah == 3) {
        if (M.has_bard) s.clr_notes();
        int wx = ax, wy = ay;
        while (true) {
            int tx = wx + dx, ty = wy + dy;
            if (tx < 0 || tx >= M.w || ty < 0 || ty >= M.h) {
                if (M.part == 3 && nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && s.obj[ny * M.w + nx] == 0) {
                    s.obj[ny * M.w + nx] = 3; s.obj[ai] = 0; moved = true;
                }
                break;
            }
            uint8_t to = s.obj[ty * M.w + tx];
            if (to == 0) { wx = tx; wy = ty; }
            else if (is_static_obj(to)) {
                if (s.obj[ny * M.w + nx] == 0) { s.obj[ny * M.w + nx] = 3; s.obj[ai] = 0; moved = true; }
                break;
            } else if (is_moveable(M.part, to)) {
                s.obj[ty * M.w + tx] = 3; s.obj[ai] = to; moved = true; break;
            } else break;
        }
    } else if (ah == 4) {
        if (M.has_bard) s.clr_notes();
        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && s.obj[ny * M.w + nx] == 0) {
            s.obj[ny * M.w + nx] = 4; s.obj[ai] = 0; moved = true;
        }
    } else if (ah == 6) {
        if (M.has_bard) s.clr_notes();
        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h) {
            int ni = ny * M.w + nx;
            uint8_t to = s.obj[ni];
            if (to == 0) { s.obj[ni] = 6; s.obj[ai] = 0; moved = true; }
            else if (to == 14 || to == 15) { s.obj[ni] = 13; moved = true; }
            else if (to == 13) { s.obj[ni] = 14; moved = true; }
            else if (is_healer(to)) { if (prune_noop) return -1; moved = true; }
            else if (is_hero(to)) {
                bool adj_h = false;
                for (int d = 0; d < 4; ++d) {
                    int hx = nx + DX[d], hy = ny + DY[d];
                    if (hx >= 0 && hx < M.w && hy >= 0 && hy < M.h && is_healer(s.obj[hy * M.w + hx])) adj_h = true;
                }
                if (!adj_h) s.obj[ni] = 13;
                else if (prune_noop) return -1;
                moved = true;
            }
        }
    } else if (ah == 5) {
        int bpos = ai;
        bool bard_moved = false;
        int charmed[25], nc = 0;
        int bx0 = ai % M.w, by0 = ai / M.w;
        for (int yy = max(0, by0 - 2); yy <= min(M.h - 1, by0 + 2); ++yy)
            for (int xx = max(0, bx0 - 2); xx <= min(M.w - 1, bx0 + 2); ++xx) {
                int ii = yy * M.w + xx;
                if (s.has_note(ii)) charmed[nc++] = ii;
            }
        uint8_t still[25]; memset(still, 1, nc);
        bool changed = true;
        while (changed) {
            changed = false;
            for (int ci = 0; ci < nc; ++ci) {
                if (!still[ci]) continue;
                int pos = charmed[ci], tx = (pos % M.w) + dx, ty = (pos / M.w) + dy;
                if (tx >= 0 && tx < M.w && ty >= 0 && ty < M.h && s.obj[ty * M.w + tx] == 0) {
                    s.obj[ty * M.w + tx] = s.obj[pos]; s.obj[pos] = 0; still[ci] = 0; changed = true;
                }
            }
            if (!bard_moved) {
                int tx = (bpos % M.w) + dx, ty = (bpos / M.w) + dy;
                if (tx >= 0 && tx < M.w && ty >= 0 && ty < M.h && s.obj[ty * M.w + tx] == 0) {
                    s.obj[ty * M.w + tx] = 5; s.obj[bpos] = 0; bpos = ty * M.w + tx; bard_moved = true; changed = true;
                }
            }
        }
        if (!bard_moved) { s = snap; return prune_noop ? -1 : (check_win(M, s) ? 1 : 0); }
        s.clr_notes();
        moved = true;
    }

    if (!moved) {
        if (M.part <= 2) { s = snap; return prune_noop ? -1 : (check_win(M, s) ? 1 : 0); }
        if (prune_noop) return -1;
    }
    if (run_late(M, s)) return -1;
    if (prune_noop && s.eq(snap, M.n, M.has_bard)) return -1;
    return check_win(M, s) ? 1 : 0;
}

pair<LevelMeta, DynState> parse_level(int part, int w, int h, const vector<string>& rows) {
    LevelMeta M;
    M.part = part; M.w = w; M.h = h; M.n = w * h;
    M.max_heroes = (part == 1 ? 3 : (part == 2 ? 4 : 6));
    DynState s{};
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            char c = rows[y][x]; int i = y * w + x;
            if (c == 'G') { M.floor_grid[i] = 1; M.goals.push_back(i); }
            else if (c == '{') { M.floor_grid[i] = 2; M.y_switches.push_back(i); }
            else if (c == '}') { M.floor_grid[i] = 3; M.p_switches.push_back(i); }
            else if (c == '#') { s.obj[i] = 13; M.init_wall[i] = 1; }
            else if (c == '*') s.obj[i] = 14;
            else if (c == 'O') s.obj[i] = 15;
            else if (c == 'L') s.obj[i] = 16;
            else if (c == 'R') s.obj[i] = 17;
            else if (c == '[') { s.obj[i] = 18; M.y_doors_init.push_back(i); }
            else if (c == ']') { s.obj[i] = 19; M.p_doors_init.push_back(i); }
            else if (c == 'M') s.obj[i] = 20;
            else if (c == 'F') s.obj[i] = 1;
            else if (c == 'T') s.obj[i] = 2;
            else if (c == 'W') s.obj[i] = 3;
            else if (c == 'P') s.obj[i] = 4;
            else if (c == 'B') { s.obj[i] = 5; M.has_bard = true; }
            else if (c == 'D') s.obj[i] = 6;
            else if (c >= '1' && c <= '6') {
                s.obj[i] = (uint8_t)(6 + (c - '0'));
                if (c == '5') M.has_bard = true;
            }
        }
    for (int i = 0; i < M.n; ++i) {
        int x = i % w, y = i / w;
        for (int g : M.goals) {
            if (abs(x - (g % w)) + abs(y - (g / w)) <= 3) { M.near_goal[i] = 1; break; }
        }
    }
    if (part == 3) run_late(M, s);
    return {M, s};
}

string render_ascii(const LevelMeta& M, const DynState& s) {
    static const char* HACT = "?FTWPBD";
    string out;
    for (int y = 0; y < M.h; ++y) {
        for (int x = 0; x < M.w; ++x) {
            int i = y * M.w + x; uint8_t o = s.obj[i]; char ch = '.';
            if (o >= 1 && o <= 6) ch = HACT[o];
            else if (o >= 7 && o <= 12) ch = (char)('0' + (o - 6));
            else if (o == 13) ch = '#'; else if (o == 14) ch = '*';
            else if (o == 15) ch = 'O'; else if (o == 16) ch = 'L';
            else if (o == 17) ch = 'R'; else if (o == 18) ch = '[';
            else if (o == 19) ch = ']'; else if (o == 20) ch = 'M';
            else if (M.floor_grid[i] == 1) ch = 'G';
            else if (M.floor_grid[i] == 2) ch = '{';
            else if (M.floor_grid[i] == 3) ch = '}';
            out.push_back(ch);
        }
        if (y + 1 < M.h) out.push_back('\n');
    }
    return out;
}

struct FastHashSet {
    vector<uint64_t> tab;
    size_t mask, cnt = 0;
    explicit FastHashSet(size_t bits = 24) : tab(1ULL << bits, 0), mask((1ULL << bits) - 1) {}
    inline bool insert(uint64_t k) {
        if (!k) k = 1;
        size_t i = k & mask;
        while (true) {
            uint64_t v = tab[i];
            if (v == k) return false;
            if (!v) { tab[i] = k; cnt++; return true; }
            i = (i + 1) & mask;
        }
    }
};

DynState transform_state(const LevelMeta& M, const DynState& s, int sym_mode) {
    if (sym_mode == 0) return s;
    DynState out{};
    out.y_open = s.y_open; out.p_open = s.p_open;
    for (int y = 0; y < M.h; ++y)
        for (int x = 0; x < M.w; ++x) {
            int tx = (sym_mode == 2 || sym_mode == 3) ? (M.w - 1 - x) : x;
            int ty = (sym_mode == 1 || sym_mode == 3) ? (M.h - 1 - y) : y;
            uint8_t v = s.obj[y * M.w + x];
            if (sym_mode == 2 || sym_mode == 3) {
                if (v == 16) v = 17; else if (v == 17) v = 16;
            }
            out.obj[ty * M.w + tx] = v;
        }
    return out;
}

inline int compact_bucket16(const LevelMeta& M, const DynState& s) {
    int ng = 0, ah = 0;
    for (int i = 0; i < M.n; ++i) {
        if (is_hero(s.obj[i])) {
            if (is_active(s.obj[i])) ah = s.obj[i];
            if (M.near_goal[i]) ng++;
        }
    }
    return (ng * 6 + (ah % 6)) & 15;
}

string tube_beam_refine(const LevelMeta& M, const DynState& start, const vector<DynState>& target,
                        int max_d, int beam_w, int cap_bkt, bool role_agnostic, double budget_s) {
    auto t0 = chrono::steady_clock::now();
    int N = (int)target.size() - 1;
    auto norm_v = [&](uint8_t v) -> uint8_t {
        if (role_agnostic && is_hero(v)) return 99;
        if (!role_agnostic && is_active(v)) return (uint8_t)(v + 6);
        return v;
    };
    vector<array<uint8_t, MAX_CELLS>> norm_t(N + 1);
    for (int k = 0; k <= N; ++k)
        for (int i = 0; i < M.n; ++i)
            norm_t[k][i] = norm_v(target[k].obj[i]);

    struct PRec { int prev; char mv; };
    vector<vector<PRec>> trace(max_d + 1);
    vector<DynState> cur = {start};
    trace[0].push_back({-1, 0});
    FastHashSet seen(24);
    seen.insert(start.hash64(M.n, M.has_bard));
    string best_win;

    for (int d = 1; d <= max_d; ++d) {
        if (chrono::duration<double>(chrono::steady_clock::now() - t0).count() > budget_s || seen.cnt > 13000000) break;
        vector<DynState> c_states;
        vector<PRec> c_precs;
        vector<int> c_bkt;
        vector<uint64_t> order_keys;
        c_states.reserve(cur.size() * 4);
        c_precs.reserve(cur.size() * 4);
        c_bkt.reserve(cur.size() * 4);
        order_keys.reserve(cur.size() * 4);

        int k_lo = max(0, d - 12), k_hi = min(N, d + 16);
        uint8_t nbuf[MAX_CELLS];
        for (int i = 0; i < (int)cur.size(); ++i) {
            for (int mv = 0; mv < 5; ++mv) {
                DynState ns = cur[i];
                int res = step_state(M, ns, mv, true);
                if (res < 0) continue;
                if (res == 1) {
                    string p; p.push_back(DCH[mv]);
                    int ci = i;
                    for (int cd = d - 1; cd >= 1; --cd) { p.push_back(trace[cd][ci].mv); ci = trace[cd][ci].prev; }
                    reverse(p.begin(), p.end());
                    if (best_win.empty() || p.size() < best_win.size()) {
                        best_win = p;
                        max_d = (int)p.size() - 1;
                    }
                    continue;
                }
                if (d >= max_d || !seen.insert(ns.hash64(M.n, M.has_bard))) continue;
                for (int j = 0; j < M.n; ++j) nbuf[j] = norm_v(ns.obj[j]);
                int best_sc = 999999, best_k = d;
                for (int k = k_lo; k <= k_hi; ++k) {
                    int diff = 0;
                    const uint8_t* tk = norm_t[k].data();
                    for (int j = 0; j < M.n; ++j) diff += (nbuf[j] != tk[j]);
                    int sc = diff * 6 - k * 5;
                    if (sc < best_sc) { best_sc = sc; best_k = k; }
                }
                uint32_t idx = (uint32_t)c_states.size();
                c_bkt.push_back((best_k * 16) + compact_bucket16(M, ns));
                c_states.push_back(ns);
                c_precs.push_back({i, DCH[mv]});
                order_keys.push_back(((uint64_t)(uint32_t)(best_sc + 500000) << 32) | idx);
            }
        }
        if (c_states.empty() || d >= max_d) break;
        sort(order_keys.begin(), order_keys.end());
        unordered_map<int, int> bc;
        vector<DynState> nxt;
        int keep = min((int)c_states.size(), beam_w);
        nxt.reserve(keep); trace[d].reserve(keep);
        vector<uint8_t> used(c_states.size(), 0);
        for (uint64_t ok : order_keys) {
            if ((int)nxt.size() >= keep) break;
            uint32_t idx = (uint32_t)ok;
            if (++bc[c_bkt[idx]] <= cap_bkt) { used[idx] = 1; nxt.push_back(c_states[idx]); trace[d].push_back(c_precs[idx]); }
        }
        for (uint64_t ok : order_keys) {
            if ((int)nxt.size() >= keep) break;
            uint32_t idx = (uint32_t)ok;
            if (!used[idx]) { nxt.push_back(c_states[idx]); trace[d].push_back(c_precs[idx]); }
        }
        cur.swap(nxt);
    }
    return best_win;
}

string exact_window_shortcut(const LevelMeta& M, const DynState& start, string route, int win_len) {
    bool improved = true;
    while (improved) {
        improved = false;
        vector<DynState> traj = {start};
        for (char c : route) { DynState nx = traj.back(); step_state(M, nx, d_idx(c), false); traj.push_back(nx); }
        int N = (int)route.size();
        for (int L = 0; L < N && !improved; L += max(2, win_len / 3)) {
            int R = min(N, L + win_len);
            unordered_map<uint64_t, vector<pair<int, DynState>>> goal_idx;
            for (int k = L + 2; k <= R; ++k) {
                goal_idx[traj[k].hash64(M.n, M.has_bard)].push_back({k, traj[k]});
            }
            struct Node { DynState s; int prev; char mv; int d; };
            vector<Node> q = {{traj[L], -1, 0, 0}};
            unordered_map<uint64_t, vector<int>> vis;
            vis[traj[L].hash64(M.n, M.has_bard)].push_back(0);
            int max_bfs = (R - L) - 1;
            for (size_t qi = 0; qi < q.size() && !improved; ++qi) {
                if (q[qi].d >= max_bfs || q.size() > 150000) break;
                for (int mv = 0; mv < 5; ++mv) {
                    DynState ns = q[qi].s;
                    int res = step_state(M, ns, mv, true);
                    if (res < 0) continue;
                    if (res == 1 && (L + q[qi].d + 1) < N) {
                        string mid; mid.push_back(DCH[mv]);
                        int cur = (int)qi;
                        while (cur > 0) { mid.push_back(q[cur].mv); cur = q[cur].prev; }
                        reverse(mid.begin(), mid.end());
                        route = route.substr(0, L) + mid;
                        improved = true; break;
                    }
                    uint64_t h = ns.hash64(M.n, M.has_bard);
                    auto it = goal_idx.find(h);
                    if (it != goal_idx.end()) {
                        int best_k = -1;
                        for (const auto& cand : it->second) {
                            if (ns.eq(cand.second, M.n, M.has_bard) && (q[qi].d + 1) < (cand.first - L)) {
                                best_k = max(best_k, cand.first);
                            }
                        }
                        if (best_k >= 0) {
                            string mid; mid.push_back(DCH[mv]);
                            int cur = (int)qi;
                            while (cur > 0) { mid.push_back(q[cur].mv); cur = q[cur].prev; }
                            reverse(mid.begin(), mid.end());
                            route = route.substr(0, L) + mid + route.substr(best_k);
                            improved = true; break;
                        }
                    }
                    if (q[qi].d + 1 < max_bfs) {
                        auto& bucket = vis[h];
                        bool already = false;
                        for (int vi : bucket) {
                            if (ns.eq(q[vi].s, M.n, M.has_bard)) { already = true; break; }
                        }
                        if (!already) {
                            int nqi = (int)q.size();
                            q.push_back({ns, (int)qi, DCH[mv], q[qi].d + 1});
                            bucket.push_back(nqi);
                        }
                    }
                }
            }
        }
    }
    return route;
}

// ==================== GENERAL BARD+DRUID QUOTIENT-PDB BUILDER FOR `prove_lb` ====================
struct BardDruidQuotientPDB {
    bool enabled = false;
    int N = 0;
    int K_CAP = 0;
    vector<int> max_adj_init;
    vector<vector<int>> adj_init_cells;
    vector<uint8_t> dist;

    inline int encode(int bi, int di, int ah_is_d, int k, int iadj, int dop) const {
        return (((((bi * N + di) * 2 + ah_is_d) * (K_CAP + 1) + k) * 5 + iadj) * 2) + dop;
    }

    void try_build(const LevelMeta& M, const DynState& s0) {
        if (M.part != 3 || !M.has_bard || M.n > 128 || M.goals.size() != 2 || M.p_switches.empty() || !M.y_switches.empty())
            return;
        int cnt_b = 0, cnt_d = 0, cnt_other_hero = 0, cnt_mon = 0;
        for (int i = 0; i < M.n; ++i) {
            uint8_t v = s0.obj[i];
            if (v == 5 || v == 11) cnt_b++;
            else if (v == 6 || v == 12) cnt_d++;
            else if (is_hero(v)) cnt_other_hero++;
            else if (is_monster(M.part, v)) cnt_mon++;
        }
        if (cnt_b != 1 || cnt_d != 1 || cnt_other_hero != 0 || cnt_mon != 0) return;

        N = M.n;
        K_CAP = min(9, (int)M.p_switches.size());
        max_adj_init.assign(N, 0);
        adj_init_cells.assign(N, {});
        vector<uint8_t> is_sw(N, 0), is_pd(N, 0);
        for (int idx : M.p_switches) is_sw[idx] = 1;
        for (int idx : M.p_doors_init) is_pd[idx] = 1;

        for (int i = 0; i < N; ++i) {
            int x = i % M.w, y = i / M.w;
            for (int d = 0; d < 4; ++d) {
                int nx = x + DX[d], ny = y + DY[d];
                if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h && M.init_wall[ny * M.w + nx]) {
                    adj_init_cells[i].push_back(ny * M.w + nx);
                }
            }
            max_adj_init[i] = (int)adj_init_cells[i].size();
        }

        const int TOTAL = N * N * 2 * (K_CAP + 1) * 5 * 2;
        vector<uint32_t> head(TOTAL, 0xFFFFFFFFu), to_e, nxt_e;
        to_e.reserve(18000000);
        nxt_e.reserve(18000000);
        auto add_rev = [&](int u, int v) {
            uint32_t e = (uint32_t)to_e.size();
            to_e.push_back((uint32_t)u);
            nxt_e.push_back(head[v]);
            head[v] = e;
        };

        const int req_sw = (int)M.p_switches.size();
        auto finish_edge = [&](int u, int nbi, int ndi, int nah, int nk, int niadj, int dop) {
            if (nbi == ndi || niadj < 0 || niadj > max_adj_init[ndi]) return;
            // In general Part III grids, initial walls on switches or created objects + heroes can weigh switches.
            // Relax soundly: if nk + hero_on_sw >= min(K_CAP, req_sw), allow opening p_doors!
            int hero_sw = (is_sw[nbi] ? 1 : 0) + (is_sw[ndi] ? 1 : 0);
            if (!M.p_doors_init.empty() && (nk + hero_sw >= min(K_CAP, req_sw))) {
                add_rev(u, encode(nbi, ndi, nah, nk, niadj, 1));
            }
            if (dop == 0) {
                add_rev(u, encode(nbi, ndi, nah, nk, niadj, 0));
            } else {
                add_rev(u, encode(nbi, ndi, nah, nk, niadj, 1));
                if (!is_pd[nbi] && !is_pd[ndi]) {
                    for (int nk2 = 0; nk2 <= nk; ++nk2) add_rev(u, encode(nbi, ndi, nah, nk2, niadj, 0));
                }
            }
        };

        for (int bi = 0; bi < N; ++bi) {
            int bx = bi % M.w, by = bi / M.w;
            for (int di = 0; di < N; ++di) {
                if (bi == di) continue;
                int dx = di % M.w, dy = di / M.w;
                for (int ah = 0; ah < 2; ++ah)
                    for (int k = 0; k <= K_CAP; ++k)
                        for (int iadj = 0; iadj <= max_adj_init[di]; ++iadj)
                            for (int dop = 0; dop < 2; ++dop) {
                                int u = encode(bi, di, ah, k, iadj, dop);
                                // Action switch
                                finish_edge(u, bi, di, 1 - ah, k, iadj, dop);
                                if (ah == 1) {
                                    // Druid step
                                    for (int d = 0; d < 4; ++d) {
                                        int nx = dx + DX[d], ny = dy + DY[d];
                                        if (nx < 0 || nx >= M.w || ny < 0 || ny >= M.h) continue;
                                        int ni = ny * M.w + nx;
                                        if (ni == bi || (!dop && is_pd[ni])) continue;
                                        for (int nia = 0; nia <= max_adj_init[ni]; ++nia)
                                            finish_edge(u, bi, ni, 1, k, nia, dop);
                                    }
                                    // Transmute non-init wall <-> crate
                                    finish_edge(u, bi, di, 1, k, iadj, dop);
                                    // Transmute intact init_wall -> crate
                                    if (iadj >= 1) finish_edge(u, bi, di, 1, min(K_CAP, k + 1), iadj - 1, dop);
                                    // Transmute crate on init_wall cell -> init_wall
                                    if (iadj < max_adj_init[di]) {
                                        if (k > 0) finish_edge(u, bi, di, 1, k - 1, iadj + 1, dop);
                                        if (k == K_CAP) finish_edge(u, bi, di, 1, K_CAP, iadj + 1, dop);
                                    }
                                } else {
                                    // Bard step
                                    bool can_c = (abs(dx - bx) <= 2 && abs(dy - by) <= 2);
                                    for (int d = 0; d < 4; ++d) {
                                        int nbx = bx + DX[d], nby = by + DY[d];
                                        if (nbx < 0 || nbx >= M.w || nby < 0 || nby >= M.h) continue;
                                        int nbi = nby * M.w + nbx;
                                        if (!dop && is_pd[nbi]) continue;
                                        if (nbi != di) finish_edge(u, nbi, di, 0, k, iadj, dop);
                                        if (can_c) {
                                            int ndx = dx + DX[d], ndy = dy + DY[d];
                                            if (ndx >= 0 && ndx < M.w && ndy >= 0 && ndy < M.h) {
                                                int ndi = ndy * M.w + ndx;
                                                if (dop || !is_pd[ndi])
                                                    for (int nia = 0; nia <= max_adj_init[ndi]; ++nia)
                                                        finish_edge(u, nbi, ndi, 0, k, nia, dop);
                                            }
                                        }
                                    }
                                }
                            }
            }
        }

        dist.assign(TOTAL, 255);
        vector<int> q;
        q.reserve(TOTAL);
        int g1 = M.goals[0], g2 = M.goals[1];
        for (int ah = 0; ah < 2; ++ah)
            for (int k = 0; k <= K_CAP; ++k)
                for (int dop = 0; dop < 2; ++dop)
                    for (auto [bg, dg] : {pair{g1, g2}, pair{g2, g1}})
                        for (int ia = 0; ia <= max_adj_init[dg]; ++ia) {
                            int w = encode(bg, dg, ah, k, ia, dop);
                            if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
                        }
        for (size_t qi = 0; qi < q.size(); ++qi) {
            int v = q[qi];
            uint8_t nd = dist[v] + 1;
            for (uint32_t e = head[v]; e != 0xFFFFFFFFu; e = nxt_e[e]) {
                uint32_t u = to_e[e];
                if (dist[u] == 255) { dist[u] = nd; q.push_back((int)u); }
            }
        }
        enabled = true;
    }

    inline int lookup(const LevelMeta& M, const DynState& s) const {
        if (!enabled) return 0;
        int bi = -1, di = -1, ah_is_d = 0, k_cr = 0;
        for (int i = 0; i < N; ++i) {
            uint8_t v = s.obj[i];
            if (v == 5) { bi = i; ah_is_d = 0; }
            else if (v == 11) bi = i;
            else if (v == 6) { di = i; ah_is_d = 1; }
            else if (v == 12) di = i;
            if (v == 14 || (v == 13 && !M.init_wall[i])) k_cr++;
        }
        if (bi < 0 || di < 0) return 999; // One hero was petrified -> win unreachable!
        k_cr = min(K_CAP, k_cr);
        int iadj = 0;
        for (int nb : adj_init_cells[di]) if (s.obj[nb] == 13) iadj++;
        uint8_t d = dist[encode(bi, di, ah_is_d, k_cr, iadj, s.p_open ? 1 : 0)];
        return (d == 255) ? 999 : (int)d;
    }
};

// ==================== GENERAL PAIR-ATOM QUOTIENT HOMOMORPHISM PDB (`PairAtomQuotientPDB`, v0.3.0) ====================
// Explicit 2-atom quotient homomorphism for 2-hero Bard+Druid+PurpleSwitch rooms (N <= 128, e.g. 14x7 & 15x7 III-14):
// Models unordered pairs of typed created weighing atoms `{crate@cell, interior_wall@cell, UNBORN, SPARE}`,
// conservatively simulating both rigid co-translation AND blocked/moving charmed crate pairs (e.g. step 25 of III-14),
// Druid transmutations (`# <-> *`), border re-petrification, and 10th-atom `SPARE` creation.
struct PairAtomQuotientPDB {
    bool enabled = false;
    int N = 0, K_REQ = 0;
    int a_unborn = 0, a_spare = 0, NA = 0;
    vector<int> int_idx_of, int_cell_of, atom_cell, initw_cells;
    vector<uint8_t> is_sw, is_pd, is_chamber, atom_is_sw;
    vector<int> pair_id_flat;
    vector<pair<uint16_t, uint16_t>> pairs;
    int npairs = 0;
    vector<uint8_t> dist;

    // Also include the 9-switch coordinate push lower bound when all switches form a grid and doors are closed:
    bool coord_bound_ok = false;
    vector<int> sw_tx, sw_ty;
    int g1_cell = -1, g2_cell = -1;
    int min_r_b = 99, min_d_b = 99, min_u_b = 99;

    inline int pid_of(int a, int b) const { return pair_id_flat[a * NA + b]; }

    inline uint32_t encode(int pid, int bi, int dz, int rd, int ah, int ao) const {
        return ((((((uint32_t)pid * N + bi) * 2 + dz) * 4 + rd) * 2 + ah) * 2) + ao;
    }

    int calc_r_dist(const LevelMeta& M, const DynState& s, int di) const {
        int dx = di % M.w, dy = di / M.w, best = 99;
        for (int ic : initw_cells) {
            if (s.obj[ic] == 13) {
                int d = abs((ic % M.w) - dx) + abs((ic / M.w) - dy);
                if (d < best) best = d;
            }
        }
        return min(3, max(0, best - 1));
    }

    void try_build(const LevelMeta& M, const DynState& s0) {
        if (M.part != 3 || !M.has_bard || M.n > 112 || M.goals.size() != 2 || M.p_switches.empty() || !M.y_switches.empty())
            return;
        int cnt_b = 0, cnt_d = 0, cnt_other = 0, cnt_mon = 0, init_crates = 0;
        for (int i = 0; i < M.n; ++i) {
            uint8_t v = s0.obj[i];
            if (v == 5 || v == 11) cnt_b++;
            else if (v == 6 || v == 12) cnt_d++;
            else if (is_hero(v)) cnt_other++;
            else if (is_monster(M.part, v)) cnt_mon++;
            else if (v == 14) init_crates++;
        }
        if (cnt_b != 1 || cnt_d != 1 || cnt_other != 0 || cnt_mon != 0 || init_crates != 0) return;

        N = M.n;
        K_REQ = (int)M.p_switches.size();
        if (K_REQ < 2 || K_REQ > 9) return;

        is_sw.assign(N, 0); is_pd.assign(N, 0); is_chamber.assign(N, 0);
        for (int idx : M.p_switches) is_sw[idx] = 1;
        for (int idx : M.p_doors_init) { is_pd[idx] = 1; is_chamber[idx] = 1; }
        g1_cell = M.goals[0]; g2_cell = M.goals[1];

        // Identify sealed goal chamber via flood-fill from goals not crossing p_doors_init or init_wall:
        {
            queue<int> fq;
            vector<uint8_t> vis(N, 0);
            for (int g : M.goals) { vis[g] = 1; fq.push(g); }
            bool sealed = true;
            while (!fq.empty()) {
                int u = fq.front(); fq.pop();
                int ux = u % M.w, uy = u / M.w;
                for (int d = 0; d < 4; ++d) {
                    int nx = ux + DX[d], ny = uy + DY[d];
                    if (nx < 0 || nx >= M.w || ny < 0 || ny >= M.h) continue;
                    int ni = ny * M.w + nx;
                    if (is_pd[ni]) continue;
                    if (M.init_wall[ni] || is_sw[ni]) { sealed = false; break; }
                    if (!vis[ni]) { vis[ni] = 1; fq.push(ni); }
                }
            }
            if (!sealed) return;
            for (int i = 0; i < N; ++i) if (vis[i]) is_chamber[i] = 1;
        }

        int_idx_of.assign(N, -1);
        int_cell_of.clear();
        initw_cells.clear();
        for (int i = 0; i < N; ++i) {
            if (M.init_wall[i]) initw_cells.push_back(i);
            else { int_idx_of[i] = (int)int_cell_of.size(); int_cell_of.push_back(i); }
        }
        int n_int = (int)int_cell_of.size();
        a_unborn = N + n_int;
        a_spare  = N + n_int + 1;
        NA       = N + n_int + 2;

        atom_cell.assign(NA, -1);
        atom_is_sw.assign(NA, 0);
        for (int a = 0; a < NA; ++a) {
            if (a < N) atom_cell[a] = a;
            else if (a < a_unborn) atom_cell[a] = int_cell_of[a - N];
            else atom_cell[a] = -1;
            atom_is_sw[a] = (atom_cell[a] >= 0 && is_sw[atom_cell[a]]) || (a == a_spare);
        }

        pair_id_flat.assign(NA * NA, -1);
        pairs.clear();
        for (int a = 0; a < NA; ++a)
            for (int b = a; b < NA; ++b) {
                if (a < a_unborn && b < a_unborn && atom_cell[a] == atom_cell[b]) continue;
                int id = (int)pairs.size();
                pair_id_flat[a * NA + b] = pair_id_flat[b * NA + a] = id;
                pairs.push_back({(uint16_t)a, (uint16_t)b});
            }
        npairs = (int)pairs.size();
        const uint64_t TOTAL64 = (uint64_t)npairs * N * 2 * 4 * 2 * 2;
        if (TOTAL64 > 65000000ULL) return;
        const uint32_t TOTAL = (uint32_t)TOTAL64;
        dist.assign(TOTAL, 255);

        auto in_aura = [&](int cell, int bi) {
            return abs((cell % M.w) - (bi % M.w)) <= 2 && abs((cell / M.w) - (bi / M.w)) <= 2;
        };
        auto valid_u = [&](int pid, int bi) {
            auto [a, b] = pairs[pid];
            return atom_cell[a] != bi && atom_cell[b] != bi;
        };
        auto can_ao1 = [&](int pid, int nbi, int ndz) {
            auto [na, nb] = pairs[pid];
            int off_sw = (!atom_is_sw[na] ? 1 : 0) + (!atom_is_sw[nb] ? 1 : 0);
            int h_sw = (is_sw[nbi] ? 1 : 0) + (ndz == 0 ? 1 : 0);
            return off_sw <= h_sw;
        };

        vector<uint32_t> q;
        q.reserve(TOTAL / 2);
        for (int pid = 0; pid < npairs; ++pid)
            for (int bg : {g1_cell, g2_cell})
                for (int rd = 0; rd < 4; ++rd)
                    for (int ah = 0; ah < 2; ++ah)
                        for (int ao = 0; ao < 2; ++ao) {
                            uint32_t w = encode(pid, bg, 1, rd, ah, ao);
                            if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
                        }

        for (size_t qi = 0; qi < q.size(); ++qi) {
            uint32_t v = q[qi]; uint8_t nd = dist[v] + 1; uint32_t tmp = v;
            int nao = tmp & 1; tmp >>= 1; int nah = tmp & 1; tmp >>= 1;
            int nrd = tmp & 3; tmp >>= 2; int ndz = tmp & 1; tmp >>= 1;
            int nbi = tmp % N; tmp /= N;  int npid = (int)tmp;

            if (!valid_u(npid, nbi) || (nao == 1 && !can_ao1(npid, nbi, ndz))) continue;
            auto push_pred = [&](int pid, int bi, int dz, int rd, int ah, int ao) {
                if (pid < 0 || !valid_u(pid, bi)) return;
                uint32_t u = encode(pid, bi, dz, rd, ah, ao);
                if (dist[u] == 255) { dist[u] = nd; q.push_back(u); }
            };

            for (int ao = 0; ao < 2; ++ao) push_pred(npid, nbi, ndz, nrd, 1 - nah, ao);
            auto [na, nb] = pairs[npid];

            if (nah == 1) {
                int rd_lo = max(0, nrd - 1), rd_hi = (nrd == 3) ? 3 : (nrd + 1);
                for (int rd = rd_lo; rd <= rd_hi; ++rd) {
                    for (int ao = 0; ao < 2; ++ao) push_pred(npid, nbi, ndz, rd, 1, ao);
                    if (ndz == 1) push_pred(npid, nbi, 0, rd, 1, 1);
                    else for (int ao = 0; ao < 2; ++ao) push_pred(npid, nbi, 1, rd, 1, ao);
                }
                auto trans_one = [&](int ta, int ob) {
                    if (ta < N) {
                        if (M.init_wall[ta]) {
                            int p = pid_of(a_unborn, ob);
                            for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, 0, 1, ao);
                        } else {
                            int p = pid_of(N + int_idx_of[ta], ob);
                            for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, nrd, 1, ao);
                        }
                    } else if (ta < a_unborn) {
                        int p = pid_of(atom_cell[ta], ob);
                        for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, nrd, 1, ao);
                    } else if (ta == a_unborn && nrd == 0) {
                        for (int icell : initw_cells) {
                            int p = pid_of(icell, ob);
                            for (int rprev = 0; rprev < 4; ++rprev)
                                for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, rprev, 1, ao);
                        }
                    } else if (ta == a_spare) {
                        for (int pa = 0; pa < NA; ++pa) {
                            int p = pid_of(pa, ob);
                            for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, 0, 1, ao);
                        }
                    }
                };
                trans_one(na, nb);
                if (nb != na) trans_one(nb, na);
                if (nrd == 0)
                    for (int rprev = 0; rprev < 4; ++rprev)
                        for (int ao = 0; ao < 2; ++ao) push_pred(npid, nbi, ndz, rprev, 1, ao);
                for (int ao = 0; ao < 2; ++ao) {
                    push_pred(npid, nbi, ndz, 0, 1, ao);
                    push_pred(npid, nbi, ndz, nrd, 1, ao);
                }
            } else {
                int nbx = nbi % M.w, nby = nbi / M.w;
                int rd_lo = max(0, nrd - 1), rd_hi = (nrd == 3) ? 3 : (nrd + 1);
                for (int d = 0; d < 4; ++d) {
                    int bx = nbx - DX[d], by = nby - DY[d];
                    if (bx < 0 || bx >= M.w || by < 0 || by >= M.h) continue;
                    int bi = by * M.w + bx;
                    int cand_a[2] = {(int)na, 0}, nca = 1, cand_b[2] = {(int)nb, 0}, ncb = 1;
                    if (na < N) {
                        int px = (na % M.w) - DX[d], py = (na / M.w) - DY[d];
                        if (px >= 0 && px < M.w && py >= 0 && py < M.h && in_aura(py * M.w + px, bi))
                            cand_a[nca++] = py * M.w + px;
                    }
                    if (nb < N) {
                        int px = (nb % M.w) - DX[d], py = (nb / M.w) - DY[d];
                        if (px >= 0 && px < M.w && py >= 0 && py < M.h && in_aura(py * M.w + px, bi))
                            cand_b[ncb++] = py * M.w + px;
                    }
                    for (int ia = 0; ia < nca; ++ia)
                    for (int ib = 0; ib < ncb; ++ib) {
                        int pid = pid_of(cand_a[ia], cand_b[ib]);
                        if (pid < 0) continue;
                        for (int rd = rd_lo; rd <= rd_hi; ++rd)
                            for (int ao = 0; ao < 2; ++ao) {
                                push_pred(pid, bi, ndz, rd, 0, ao);
                                push_pred(pid, bi, 1 - ndz, rd, 0, ao);
                            }
                    }
                }
            }
        }

        // Precompute sorted switch X/Y targets for coordinate bound when K_REQ == 9:
        sw_tx.clear(); sw_ty.clear();
        for (int idx : M.p_switches) { sw_tx.push_back(idx % M.w); sw_ty.push_back(idx / M.w); }
        sort(sw_tx.begin(), sw_tx.end());
        sort(sw_ty.begin(), sw_ty.end());
        // Check if chamber has min distance >= 2 from all switches (so 9 non-hero objects are strictly required!):
        int min_sw_ch_dist = 99;
        for (int si : M.p_switches)
            for (int ci = 0; ci < N; ++ci)
                if (is_chamber[ci])
                    min_sw_ch_dist = min(min_sw_ch_dist, abs((si % M.w) - (ci % M.w)) + abs((si / M.w) - (ci / M.w)));
        coord_bound_ok = (K_REQ == 9 && min_sw_ch_dist >= 2 && (g1_cell / M.w) == (g2_cell / M.w));
        if (coord_bound_ok) {
            min_r_b = 99; min_d_b = 99; min_u_b = 99;
            for (int ic : initw_cells) {
                int wx = ic % M.w, wy = ic / M.w;
                if (wx < sw_tx[0]) min_r_b = min(min_r_b, sw_tx[0] - wx);
                if (wy < sw_ty[0]) min_d_b = min(min_d_b, sw_ty[0] - wy);
                if (wy > sw_ty[8]) min_u_b = min(min_u_b, wy - sw_ty[8]);
            }
        }
        enabled = true;
    }

    inline int lookup(const LevelMeta& M, const DynState& s) const {
        if (!enabled) return 0;
        int bi = -1, di = -1, ah = 0;
        int atoms[64], na = 0;
        for (int i = 0; i < N; ++i) {
            uint8_t v = s.obj[i];
            if (v == 5) { bi = i; ah = 0; }
            else if (v == 11) bi = i;
            else if (v == 6) { di = i; ah = 1; }
            else if (v == 12) di = i;
            if (v == 14 && na < 60) atoms[na++] = i;
            else if (v == 13 && !M.init_wall[i] && na < 60) atoms[na++] = N + int_idx_of[i];
        }
        if (bi < 0 || di < 0) return 999;
        int dz = is_chamber[di] ? 1 : 0;
        int rd = calc_r_dist(M, s, di);
        int ao = s.p_open ? 1 : 0;

        int best = 0;
        if (na > K_REQ) {
            for (int i = 0; i < na; ++i) {
                uint8_t d = dist[encode(pid_of(atoms[i], a_spare), bi, dz, rd, ah, ao)];
                best = max(best, d == 255 ? 999 : (int)d);
            }
        } else {
            int tot = K_REQ;
            while (na < tot) atoms[na++] = a_unborn;
            for (int i = 0; i < tot; ++i)
                for (int j = i + 1; j < tot; ++j) {
                    uint8_t d = dist[encode(pid_of(atoms[i], atoms[j]), bi, dz, rd, ah, ao)];
                    int val = (d == 255 ? 999 : (int)d);
                    if (val > best) best = val;
                }
        }
        if (best >= 999) return 999;

        // Coordinate push lower bound when sealed chamber hasn't been entered by both heroes:
        if (coord_bound_ok && !(is_chamber[bi] && is_chamber[di])) {
            int bx = bi % M.w, by = bi / M.w, dx = di % M.w, dy = di / M.w;
            int gy = g1_cell / M.w, g1x = g1_cell % M.w, g2x = g2_cell % M.w;
            int xs[64], ys[64], k = 0, n_int_off = 0, uncov_sw = 0;
            for (int i = 0; i < N; ++i) {
                uint8_t v = s.obj[i];
                if (v == 14 || (v == 13 && is_sw[i])) { xs[k] = i % M.w; ys[k] = i / M.w; k++; }
                else if (v == 13 && !M.init_wall[i] && !is_sw[i]) n_int_off++;
                if (is_sw[i] && v != 14 && v != 13) uncov_sw++;
            }
            sort(xs, xs + k); sort(ys, ys + k);
            int best_c = 999;
            for (int c = max(0, 9 - k); c <= 9; ++c) {
                int use_old = 9 - c;
                int sw_keys = (c > 0) ? (ah == 0 ? 2 : 1) : ((uncov_sw > 0 && ah == 1) ? 1 : 0);
                int req_R = 0, req_L = 0, req_D = 0, req_U = 0;
                int min_cbx = 99, max_cbx = -99, min_cby = 99, max_cby = -99;
                for (int j = 0; j < use_old; ++j) {
                    int rx = sw_tx[j] - xs[k - use_old + j]; if (rx > 0) { req_R = max(req_R, rx); min_cbx = min(min_cbx, xs[k - use_old + j] + 2); }
                    int lx = xs[j] - sw_tx[9 - use_old + j]; if (lx > 0) { req_L = max(req_L, lx); max_cbx = max(max_cbx, xs[j] - 2); }
                    int dv = sw_ty[j] - ys[k - use_old + j]; if (dv > 0) { req_D = max(req_D, dv); min_cby = min(min_cby, ys[k - use_old + j] + 2); }
                    int uv = ys[j] - sw_ty[9 - use_old + j]; if (uv > 0) { req_U = max(req_U, uv); max_cby = max(max_cby, ys[j] - 2); }
                }
                if (min_cbx < 99 && bx > min_cbx) req_L = max(req_L, bx - min_cbx);
                if (max_cbx > -99 && bx < max_cbx) req_R = max(req_R, max_cbx - bx);
                if (min_cby < 99 && by > min_cby) req_U = max(req_U, by - min_cby);
                if (max_cby > -99 && by < max_cby) req_D = max(req_D, max_cby - by);

                int c_b = max(0, c - n_int_off);
                for (int sg = 0; sg < 2; ++sg) {
                    int gx_b = (sg == 0 ? g1x : g2x), gx_d = (sg == 0 ? g2x : g1x);
                    int dbx = gx_b - bx, ddx = gx_d - dx, dby = gy - by, ddy = gy - dy;
                    int h_mx = (abs(dbx) + abs(ddx) + abs(dbx - ddx)) >> 1;
                    int h_my = (abs(dby) + abs(ddy) + abs(dby - ddy)) >> 1;
                    int b_mx = max({req_R + req_L, 2 * req_L + dbx, 2 * req_R - dbx, h_mx});
                    int b_my = max({req_D + req_U, 2 * req_U + dby, 2 * req_D - dby, h_my});
                    int move_sum = b_mx + b_my;
                    if (c_b > 0) {
                        int cand = move_sum;
                        if (min_r_b < 99 && min_d_b < 99 && min_u_b < 99) {
                            int opt_lr  = max({min_r_b + req_L, 2 * req_L + dbx, 2 * min_r_b - dbx, b_mx}) + b_my;
                            int opt_ud1 = b_mx + max({min_d_b + req_U, 2 * req_U + dby, 2 * min_d_b - dby, b_my});
                            int opt_ud2 = b_mx + max({req_D + min_u_b, 2 * min_u_b + dby, 2 * req_D - dby, b_my});
                            cand = min({opt_lr, opt_ud1, opt_ud2});
                        }
                        move_sum = cand;
                    }
                    best_c = min(best_c, c + sw_keys + move_sum);
                }
            }
            best = max(best, best_c);
        }
        return best;
    }
};

// ==================== GENERAL WIZARD-RAY & UNCOVERED-GOAL ADMISSIBLE BOUND (`WizardRayGoalBound`, v0.3.0) ====================
// Fixes F-04b / F-10 on Wizard rooms (`III-15`, `III-20`, `II-22`):
// 1. Builds single-cell shortest path `wiz_dist[u]` allowing both orthogonal steps AND straight-line ray swaps
//    (stopping only at permanent `#` walls when `!has_druid`).
// 2. When `!has_bard` and `!has_fighter`, at most 1 uncovered goal cell can become covered by a hero on any single turn
//    (verified across Thief pull, Wizard swap, Priest walk, Druid walk/transmute, and `'A'` switch!).
struct WizardRayGoalBound {
    bool enabled = false;
    bool count_uncov_goals_ok = false;
    vector<int> wiz_dist;

    void build(const LevelMeta& M, const DynState& s0, bool has_druid, bool has_fighter) {
        if (M.goals.empty()) return;
        wiz_dist.assign(M.n, 999);
        queue<int> q;
        for (int g : M.goals) { wiz_dist[g] = 0; q.push(g); }
        while (!q.empty()) {
            int u = q.front(); q.pop();
            int ux = u % M.w, uy = u / M.w;
            // Orthogonal 1-step predecessors:
            for (int d = 0; d < 4; ++d) {
                int nx = ux + DX[d], ny = uy + DY[d];
                if (nx < 0 || nx >= M.w || ny < 0 || ny >= M.h) continue;
                int ni = ny * M.w + nx;
                if (!has_druid && s0.obj[ni] == 13) continue;
                if (wiz_dist[ni] > wiz_dist[u] + 1) { wiz_dist[ni] = wiz_dist[u] + 1; q.push(ni); }
            }
            // Straight-line Wizard ray predecessors (`ni` swaps with `u` in 1 step if unobstructed!):
            for (int d = 0; d < 4; ++d) {
                int cx = ux + DX[d], cy = uy + DY[d];
                while (cx >= 0 && cx < M.w && cy >= 0 && cy < M.h) {
                    int ci = cy * M.w + cx;
                    if (!has_druid && s0.obj[ci] == 13) break;
                    if (wiz_dist[ci] > wiz_dist[u] + 1) { wiz_dist[ci] = wiz_dist[u] + 1; q.push(ci); }
                    cx += DX[d]; cy += DY[d];
                }
            }
        }
        count_uncov_goals_ok = (!M.has_bard && !has_fighter);
        enabled = true;
    }

    inline int lookup(const LevelMeta& M, const DynState& s) const {
        if (!enabled) return 1;
        int best = 1;
        int hero_cnt = 0;
        for (int i = 0; i < M.n; ++i) {
            if (is_hero(s.obj[i])) {
                hero_cnt++;
                best = max(best, wiz_dist[i]);
            }
        }
        if (hero_cnt < (int)M.goals.size()) return 999; // A hero was petrified/killed -> unwinnable!
        if (count_uncov_goals_ok) {
            int uncov = 0;
            for (int g : M.goals) if (!is_hero(s.obj[g])) uncov++;
            best = max(best, uncov);
        }
        return best;
    }
};


string escape_json(const string& s) {
    string o;
    for (char c : s) {
        if (c == '"') o += "\\\""; else if (c == '\\') o += "\\\\";
        else if (c == '\n') o += "\\n"; else o.push_back(c);
    }
    return o;
}

string hex16(uint64_t v) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%016llx", (unsigned long long)v);
    return string(buf);
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string mode;
    int part, w, h, p1, p2, p3;
    if (!(cin >> mode >> part >> w >> h >> p1 >> p2 >> p3)) return 1;
    if (w * h > MAX_CELLS) {
        cout << "{\"error\":\"grid exceeds MAX_CELLS (512)\"}\n";
        return 1;
    }
    string dummy; getline(cin, dummy);
    vector<string> rows(h);
    for (int y = 0; y < h; ++y) getline(cin, rows[y]);
    string seed_route;
    getline(cin, seed_route);
    if (seed_route == "-") seed_route.clear();

    auto [M, s0] = parse_level(part, w, h, rows);

    if (mode == "perft") {
        // Move-generator check in the style of chess perft: for each depth up to p1,
        // the number of distinct states first reached at that depth (no-op moves
        // pruned, deaths dropped) and an order-independent hash of those states
        // (sum mod 2^64 of their FNV-1a frame digests). Equal counts alone miss
        // engines that reach different states; the hash does not.
        int depth = max(0, min(p1, 64));
        unordered_map<uint64_t, vector<DynState>> seen;
        auto add = [&](const DynState& st) {
            auto& bucket = seen[st.hash64(M.n, M.has_bard)];
            for (const auto& t : bucket) if (t.eq(st, M.n, M.has_bard)) return false;
            bucket.push_back(st);
            return true;
        };
        add(s0);
        vector<DynState> layer = {s0};
        cout << "{\"layers\":[";
        for (int d = 1; d <= depth; ++d) {
            vector<DynState> next;
            uint64_t sum = 0;
            for (const auto& st : layer)
                for (int mv = 0; mv < 5; ++mv) {
                    DynState ns = st;
                    if (step_state(M, ns, mv, true) < 0) continue;
                    if (add(ns)) { next.push_back(ns); sum += fold_traj_fnv64(M, ns, 14695981039346656037ULL); }
                }
            char hex[17]; snprintf(hex, sizeof hex, "%016llx", (unsigned long long)sum);
            cout << (d > 1 ? "," : "") << "[" << next.size() << ",\"" << hex << "\"]";
            layer.swap(next);
        }
        cout << "]}\n";
        return 0;
    }

    if (mode == "verify") {
        DynState cur = s0;
        uint64_t traj_h = fold_traj_fnv64(M, cur, 14695981039346656037ULL);
        bool alive = true, premature_win = false;
        int steps_done = 0;
        for (size_t i = 0; i < seed_route.size(); ++i) {
            int mv = d_idx(seed_route[i]);
            if (mv < 0) { alive = false; break; }
            int r = step_state(M, cur, mv, false);
            steps_done++;
            if (r < 0) { alive = false; break; }
            traj_h = fold_traj_fnv64(M, cur, traj_h);
            if (r == 1 && i + 1 < seed_route.size()) { premature_win = true; break; }
        }
        bool won = alive && !premature_win && check_win(M, cur);
        cout << "{\"alive\":" << (alive ? "true" : "false")
             << ",\"exact_win\":" << (won ? "true" : "false")
             << ",\"premature_win\":" << (premature_win ? "true" : "false")
             << ",\"steps_executed\":" << steps_done
             << ",\"traj_fnv64\":\"" << hex16(traj_h) << "\""
             << ",\"final_hash\":\"" << hex << cur.hash64(M.n, M.has_bard) << dec << "\""
             << ",\"final_ascii\":\"" << escape_json(render_ascii(M, cur)) << "\"}\n";
        return 0;
    }

    if (mode == "optimize") {
        int beam_w = max(2000, p1);
        int win_len = max(8, p2);
        double total_budget = max(0.0, (double)p3);
        string best = seed_route;
        vector<string> log_entries;
        auto opt_t0 = chrono::steady_clock::now();
        if (total_budget <= 0.0) {
            cout << "{\"initial_len\":" << seed_route.size() << ",\"best_len\":" << seed_route.size()
                 << ",\"improved\":false,\"best_route\":\"" << seed_route << "\",\"stages\":[]"
                 << ",\"timed_out\":true}\n";
            return 0;
        }

        string w_opt = exact_window_shortcut(M, s0, best, win_len);
        if (w_opt.size() < best.size()) {
            log_entries.push_back("window_bfs:" + to_string(best.size()) + "->" + to_string(w_opt.size()));
            best = w_opt;
        }

        auto sym_diff = [&](int sym_mode) {
            int diff = 0;
            for (int y = 0; y < M.h; ++y)
                for (int x = 0; x < M.w; ++x) {
                    int tx = (sym_mode == 2 || sym_mode == 3) ? (M.w - 1 - x) : x;
                    int ty = (sym_mode == 1 || sym_mode == 3) ? (M.h - 1 - y) : y;
                    if (M.floor_grid[y * M.w + x] != M.floor_grid[ty * M.w + tx]) diff += 2;
                    if ((s0.obj[y * M.w + x] == 13) != (s0.obj[ty * M.w + tx] == 13)) diff += 1;
                }
            return diff;
        };

        vector<pair<int, int>> axes;
        for (int sm : {1, 2, 3}) axes.push_back({sym_diff(sm), sm});
        sort(axes.begin(), axes.end());
        double per_stage = total_budget / 2.2;

        if (axes[0].first <= M.n / 5) {
            int best_sym = axes[0].second;
            vector<DynState> mir_traj;
            DynState cur = s0;
            mir_traj.push_back(transform_state(M, cur, best_sym));
            for (char c : best) { step_state(M, cur, d_idx(c), false); mir_traj.push_back(transform_state(M, cur, best_sym)); }
            string m_hit = tube_beam_refine(M, s0, mir_traj, (int)best.size() - 1, beam_w, 240, true, per_stage);
            if (!m_hit.empty() && m_hit.size() < best.size()) {
                log_entries.push_back("chiral_sym_" + to_string(best_sym) + ":" + to_string(best.size()) + "->" + to_string(m_hit.size()));
                best = m_hit;
            }
        }

        for (int iter = 0; iter < 2; ++iter) {
            vector<DynState> ref_traj = {s0};
            for (char c : best) { DynState nx = ref_traj.back(); step_state(M, nx, d_idx(c), false); ref_traj.push_back(nx); }
            string r_hit = tube_beam_refine(M, s0, ref_traj, (int)best.size() - 1, max(32000, (beam_w * 4) / 5), 240, true, per_stage);
            if (!r_hit.empty() && r_hit.size() < best.size()) {
                log_entries.push_back("iter_tube_" + to_string(iter + 1) + ":" + to_string(best.size()) + "->" + to_string(r_hit.size()));
                best = r_hit;
            } else break;
        }

        string w2 = exact_window_shortcut(M, s0, best, max(win_len, min(20, win_len + 4)));
        if (w2.size() < best.size()) {
            log_entries.push_back("post_lns_window_bfs:" + to_string(best.size()) + "->" + to_string(w2.size()));
            best = w2;
        }

        string log_str;
        for (size_t i = 0; i < log_entries.size(); ++i) {
            if (i) log_str += ",";
            log_str += "\"" + log_entries[i] + "\"";
        }
        cout << "{\"initial_len\":" << seed_route.size()
             << ",\"best_len\":" << best.size()
             << ",\"improved\":" << (best.size() < seed_route.size() ? "true" : "false")
             << ",\"best_route\":\"" << best << "\""
             << ",\"stages\":[" << log_str << "]"
             << ",\"timed_out\":" << (chrono::duration<double>(chrono::steady_clock::now() - opt_t0).count() > total_budget ? "true" : "false")
             << "}\n";
        return 0;
    }

    if (mode == "solve") {
        int max_d = max(0, p1), beam_w = max(2000, p2);
        double budget_s = max(0.0, (double)p3);
        auto t0 = chrono::steady_clock::now();
        if (check_win(M, s0)) {
            cout << "{\"solved\":true,\"len\":0,\"route\":\"\",\"explored\":1,\"nodes_expanded\":0"
                 << ",\"completed_depth\":0,\"termination_reason\":\"solved\",\"timed_out\":false"
                 << ",\"search_algorithm\":\"bucketed_beam\"}\n";
            return 0;
        }
        uint64_t solve_nodes = 0;
        int solve_completed = 0;
        string solve_term = "depth_limit";
        bool solve_timed_out = false;

        struct PRec { int prev; char mv; };
        vector<vector<PRec>> trace(max_d + 1);
        vector<DynState> cur = {s0};
        trace[0].push_back({-1, 0});
        FastHashSet seen(24);
        seen.insert(s0.hash64(M.n, M.has_bard));
        string best_win;

        for (int d = 1; d <= max_d; ++d) {
            if (chrono::duration<double>(chrono::steady_clock::now() - t0).count() >= budget_s) {
                solve_timed_out = true; solve_term = "time_budget"; break;
            }
            if (seen.cnt > 12000000) { solve_term = "state_limit"; break; }
            vector<DynState> c_states;
            vector<PRec> c_precs;
            vector<int> c_bkt;
            vector<uint64_t> order_keys;
            c_states.reserve(cur.size() * 4);
            c_precs.reserve(cur.size() * 4);
            c_bkt.reserve(cur.size() * 4);
            order_keys.reserve(cur.size() * 4);

            for (int i = 0; i < (int)cur.size(); ++i) {
                ++solve_nodes;
                for (int mv = 0; mv < 5; ++mv) {
                    DynState ns = cur[i];
                    int res = step_state(M, ns, mv, true);
                    if (res < 0) continue;
                    if (res == 1) {
                        string p; p.push_back(DCH[mv]);
                        int ci = i;
                        for (int cd = d - 1; cd >= 1; --cd) { p.push_back(trace[cd][ci].mv); ci = trace[cd][ci].prev; }
                        reverse(p.begin(), p.end());
                        best_win = p; break;
                    }
                    if (!seen.insert(ns.hash64(M.n, M.has_bard))) continue;
                    int monsters = 0, uncov_sw = 0, hdist = 0, goals_hit = 0;
                    for (int idx : M.y_switches) if (!is_weighing(M.part, ns.obj[idx])) uncov_sw++;
                    for (int idx : M.p_switches) if (!is_weighing(M.part, ns.obj[idx])) uncov_sw++;
                    for (int j = 0; j < M.n; ++j) {
                        uint8_t v = ns.obj[j];
                        if (is_monster(M.part, v)) monsters++;
                        if (is_hero(v) && !M.goals.empty()) {
                            int x = j % M.w, y = j / M.w, bg = 999;
                            for (int gi : M.goals) bg = min(bg, abs(x - (gi % M.w)) + abs(y - (gi / M.w)));
                            hdist += bg;
                            if (bg == 0) goals_hit++;
                        }
                    }
                    int sc = monsters * 12 + uncov_sw * 8 + hdist * 2 - goals_hit * 10;
                    uint32_t idx = (uint32_t)c_states.size();
                    c_bkt.push_back(((monsters & 15) << 8) ^ ((uncov_sw & 7) << 4) ^ compact_bucket16(M, ns));
                    c_states.push_back(ns);
                    c_precs.push_back({i, DCH[mv]});
                    order_keys.push_back(((uint64_t)(uint32_t)(sc + 50000) << 32) | idx);
                }
                if (!best_win.empty()) break;
            }
            if (!best_win.empty()) { solve_term = "solved"; break; }
            if (c_states.empty()) { solve_term = "exhausted"; break; }
            solve_completed = d;
            sort(order_keys.begin(), order_keys.end());
            unordered_map<int, int> bc;
            vector<DynState> nxt;
            int keep = min((int)c_states.size(), beam_w);
            nxt.reserve(keep); trace[d].reserve(keep);
            vector<uint8_t> used(c_states.size(), 0);
            for (uint64_t ok : order_keys) {
                if ((int)nxt.size() >= keep) break;
                uint32_t idx = (uint32_t)ok;
                if (++bc[c_bkt[idx]] <= 120) { used[idx] = 1; nxt.push_back(c_states[idx]); trace[d].push_back(c_precs[idx]); }
            }
            for (uint64_t ok : order_keys) {
                if ((int)nxt.size() >= keep) break;
                uint32_t idx = (uint32_t)ok;
                if (!used[idx]) { nxt.push_back(c_states[idx]); trace[d].push_back(c_precs[idx]); }
            }
            cur.swap(nxt);
        }
        if (!best_win.empty()) best_win = exact_window_shortcut(M, s0, best_win, 14);
        cout << "{\"solved\":" << (!best_win.empty() ? "true" : "false")
             << ",\"len\":" << best_win.size()
             << ",\"route\":\"" << best_win << "\""
             << ",\"explored\":" << seen.cnt
             << ",\"nodes_expanded\":" << solve_nodes
             << ",\"completed_depth\":" << solve_completed
             << ",\"termination_reason\":\"" << solve_term << "\""
             << ",\"timed_out\":" << (solve_timed_out ? "true" : "false")
             << ",\"search_algorithm\":\"bucketed_beam\"}\n";
        return 0;
    }

    if (mode == "prove_lb") {
        // Contract: VERIFIED only with a witness; otherwise EXHAUSTIVE_LOWER_BOUND.
        // A floor never exceeds max_bound + 1 and nothing is claimed before the
        // start node has been expanded. A zero budget or state cap is honored.
        // g and h are stored in uint8_t, so the bound is clamped to 250.
        int requested_bound = max(1, p1);
        int max_bound = min(requested_bound, 250);
        double budget_s = max(0.0, (double)p3);
        size_t state_cap = p2 > 0 ? (size_t)p2 : 0;
        auto t0 = chrono::steady_clock::now();
        bool has_druid = false, has_wizard = false, has_fighter = false;
        for (int i = 0; i < M.n; ++i) {
            if (s0.obj[i] == 6 || s0.obj[i] == 12) has_druid = true;
            if (s0.obj[i] == 3 || s0.obj[i] == 9)  has_wizard = true;
            if (s0.obj[i] == 1 || s0.obj[i] == 7)  has_fighter = true;
        }
        vector<int> goal_dist(M.n, 0);
        if (!M.goals.empty()) {
            fill(goal_dist.begin(), goal_dist.end(), 999);
            queue<int> q;
            for (int g : M.goals) { goal_dist[g] = 0; q.push(g); }
            while (!q.empty()) {
                int u = q.front(); q.pop();
                int ux = u % M.w, uy = u / M.w;
                for (int d = 0; d < 4; ++d) {
                    int nx = ux + DX[d], ny = uy + DY[d];
                    if (nx < 0 || nx >= M.w || ny < 0 || ny >= M.h) continue;
                    int ni = ny * M.w + nx;
                    if (!has_druid && s0.obj[ni] == 13) continue;
                    if (goal_dist[ni] > goal_dist[u] + 1) { goal_dist[ni] = goal_dist[u] + 1; q.push(ni); }
                }
            }
        }

        PairAtomQuotientPDB ppdb;
        if (budget_s >= 6.0) ppdb.try_build(M, s0);

        BardDruidQuotientPDB qpdb;
        qpdb.try_build(M, s0);

        WizardRayGoalBound wiz_bound;
        if (has_wizard) wiz_bound.build(M, s0, has_druid, has_fighter);

        auto h_admissible = [&](const DynState& s) -> int {
            if (check_win(M, s)) return 0;
            int best_h = 1;
            int hero_cnt = 0;
            for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) hero_cnt++;
            if (hero_cnt < (int)M.goals.size()) return 999;

            if (!has_wizard) {
                for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) best_h = max(best_h, goal_dist[i]);
                if (!M.has_bard && !has_fighter) {
                    int uncov = 0;
                    for (int g : M.goals) if (!is_hero(s.obj[g])) uncov++;
                    best_h = max(best_h, uncov);
                }
            } else if (wiz_bound.enabled) {
                best_h = max(best_h, wiz_bound.lookup(M, s));
            }
            if (qpdb.enabled) best_h = max(best_h, qpdb.lookup(M, s));
            if (ppdb.enabled) best_h = max(best_h, ppdb.lookup(M, s));
            return best_h;
        };

        if (check_win(M, s0)) {
            cout << "{\"proven_floor\":0,\"exact_optimum_reached\":true"
                 << ",\"search_strategy\":\"trivial_initial_win\""
                 << ",\"quotient_pdb_enabled\":" << ((qpdb.enabled || ppdb.enabled) ? "true" : "false")
                 << ",\"pair_atom_pdb_enabled\":" << (ppdb.enabled ? "true" : "false")
                 << ",\"wizard_ray_bound_enabled\":" << (wiz_bound.enabled ? "true" : "false")
                 << ",\"exact_state_tt\":true,\"exact_tt_prunes\":0,\"hash_collisions_prevented\":0"
                 << ",\"nodes_expanded\":0,\"edge_consistency_checks\":0"
                 << ",\"completed_depth\":-1,\"termination_reason\":\"solved\",\"timed_out\":false"
                 << ",\"states_seen\":1,\"search_algorithm\":\"trivial_initial_win\""
                 << ",\"winning_witness\":\"\",\"epistemic_status\":\"VERIFIED\"}\n";
            return 0;
        }

        // Strategy A (Primary for M.n <= 256, v0.4.0): Multi-Core Exact-State Bucketed A* (covers III-14, III-20 [135], II-22 [169]!)
        if (M.n <= 256) {
            struct CompactNode {
                uint8_t raw_obj[256];
                uint64_t notes0, notes1;
                uint8_t y_open, p_open, g, h_cached, closed;
                uint32_t parent;
                char mv;
            };
            auto pack_dyn = [&](const DynState& s, uint8_t g, uint8_t h, uint32_t par, char mv) -> CompactNode {
                CompactNode c{};
                memcpy(c.raw_obj, s.obj, M.n);
                c.notes0 = s.notes[0]; c.notes1 = s.notes[1];
                c.y_open = s.y_open; c.p_open = s.p_open;
                c.g = g; c.h_cached = h; c.closed = 0; c.parent = par; c.mv = mv;
                return c;
            };
            auto unpack_dyn = [&](const CompactNode& c) -> DynState {
                DynState s{};
                memcpy(s.obj, c.raw_obj, M.n);
                s.notes[0] = c.notes0; s.notes[1] = c.notes1;
                s.y_open = c.y_open; s.p_open = c.p_open;
                return s;
            };
            auto eq_compact = [&](const DynState& s, const CompactNode& c) -> bool {
                if (s.y_open != c.y_open || s.p_open != c.p_open) return false;
                if (memcmp(s.obj, c.raw_obj, M.n) != 0) return false;
                if (M.has_bard && (s.notes[0] != c.notes0 || s.notes[1] != c.notes1)) return false;
                return true;
            };

            const size_t MAX_ASTAR_NODES = state_cap ? state_cap
                : ((budget_s >= 25.0) ? 15000000 : ((budget_s >= 10.0) ? 8000000 : 4000000));
            const size_t HBITS = (budget_s >= 25.0) ? 25 : ((budget_s >= 10.0) ? 24 : 23); // 8,388,608 hash slots
            vector<uint64_t> hkeys(1ULL << HBITS, 0);
            vector<uint32_t> hvals(1ULL << HBITS, 0xFFFFFFFFu);
            const size_t HMASK = (1ULL << HBITS) - 1;

            vector<CompactNode> pool;
            pool.reserve(min<size_t>(MAX_ASTAR_NODES, 4000000));
            vector<vector<uint32_t>> buckets(max_bound + 4);

            uint64_t edge_checks = 0, total_nodes = 0, exact_dedups = 0, hash_collisions_prevented = 0;
            int h0 = h_admissible(s0);
            int proven_floor = h0;
            bool solved = false, consistency_violated = false;
            string winning_witness;

            auto lookup_id = [&](uint64_t hk, const DynState& s) -> int64_t {
                size_t i = hk & HMASK;
                while (true) {
                    uint64_t k = hkeys[i];
                    if (k == 0) return -1;
                    if (k == hk) {
                        uint32_t id = hvals[i];
                        if (eq_compact(s, pool[id])) return (int64_t)id;
                    }
                    i = (i + 1) & HMASK;
                }
            };

            auto upsert_node = [&](uint64_t hk, const DynState& s, uint8_t g, uint8_t h, uint32_t par, char mv) {
                if ((int)g + (int)h > max_bound) return;
                size_t i = hk & HMASK;
                while (true) {
                    uint64_t k = hkeys[i];
                    if (k == 0) {
                        uint32_t id = (uint32_t)pool.size();
                        pool.push_back(pack_dyn(s, g, h, par, mv));
                        hkeys[i] = hk; hvals[i] = id;
                        buckets[g + h].push_back(id);
                        return;
                    }
                    if (k == hk) {
                        uint32_t id = hvals[i];
                        if (eq_compact(s, pool[id])) {
                            exact_dedups++;
                            if (g < pool[id].g) {
                                pool[id].g = g; pool[id].parent = par; pool[id].mv = mv; pool[id].closed = 0;
                                if ((int)g + (int)pool[id].h_cached <= max_bound)
                                    buckets[g + pool[id].h_cached].push_back(id);
                            }
                            return;
                        } else {
                            hash_collisions_prevented++;
                        }
                    }
                    i = (i + 1) & HMASK;
                }
            };

            string termination = "max_bound";
            bool timed_out = false, start_expanded = false;
            auto elapsed = [&]() { return chrono::duration<double>(chrono::steady_clock::now() - t0).count(); };
            if (h0 <= max_bound) {
                uint64_t hk0 = s0.hash64(M.n, M.has_bard); if (!hk0) hk0 = 1;
                upsert_node(hk0, s0, 0, (uint8_t)min(255, h0), 0xFFFFFFFFu, 0);
            } else if (budget_s <= 0.0 || (state_cap && state_cap <= 1)) {
                timed_out = budget_s <= 0.0;
                termination = timed_out ? "time_budget" : "state_limit";
            } else {
                // The start heuristic already exceeds the bound. Expand the start node so the
                // claim max_bound + 1 rests on checked transitions, not on h(s0) alone.
                bool any_successor = false;
                for (int mv = 0; mv < 5 && !consistency_violated; ++mv) {
                    DynState ns = s0;
                    int res = step_state(M, ns, mv, true);
                    if (res < 0) continue;
                    any_successor = true;
                    int hns = (res == 1) ? 0 : h_admissible(ns);
                    edge_checks++;
                    if (h0 > 1 + hns && hns < 999) consistency_violated = true;
                }
                total_nodes = 1;
                start_expanded = true;
                termination = any_successor ? "heuristic_exceeds_bound" : "exhausted";
                proven_floor = max_bound + 1;
            }

            const unsigned n_threads = max(1u, min(8u, thread::hardware_concurrency()));
            const size_t BATCH = 16384;
            struct CandRec { uint64_t hk; DynState ns; uint8_t g, h, won; uint32_t par; char mv; };
            atomic<bool> incons_flag{false};

            for (int f = h0; f <= max_bound && !solved && !consistency_violated; ++f) {
                size_t base = 0;
                bool stopped_early = false;
                while (base < buckets[f].size() && !solved && !consistency_violated) {
                    if (elapsed() >= budget_s) { stopped_early = true; timed_out = true; termination = "time_budget"; break; }
                    if (state_cap ? pool.size() >= MAX_ASTAR_NODES : pool.size() + BATCH * 5 > MAX_ASTAR_NODES) {
                        stopped_early = true; termination = "state_limit"; break;
                    }
                    // With an explicit state cap, expand one node at a time so the cap is exact.
                    size_t end = min(buckets[f].size(), base + (state_cap ? (size_t)1 : BATCH));
                    vector<uint32_t> active;
                    active.reserve(end - base);
                    for (size_t idx = base; idx < end; ++idx) {
                        uint32_t id = buckets[f][idx];
                        if (pool[id].closed || (int)pool[id].g + (int)pool[id].h_cached > f) continue;
                        pool[id].closed = 1;
                        active.push_back(id);
                    }
                    base = end;
                    if (active.empty()) continue;
                    total_nodes += active.size();
                    start_expanded = true;

                    unsigned nt = (active.size() >= 128) ? n_threads : 1u;
                    vector<vector<CandRec>> outs(nt);
                    vector<uint64_t> ecs(nt, 0), deds(nt, 0);
                    auto worker = [&](unsigned tid) {
                        size_t L = (active.size() * tid) / nt;
                        size_t R = (active.size() * (tid + 1)) / nt;
                        auto& out = outs[tid];
                        out.reserve((R - L) * 3);
                        for (size_t ai = L; ai < R; ++ai) {
                            uint32_t id = active[ai];
                            DynState s = unpack_dyn(pool[id]);
                            int g = pool[id].g, hs = pool[id].h_cached;
                            for (int mv = 0; mv < 5; ++mv) {
                                DynState ns = s;
                                int res = step_state(M, ns, mv, true);
                                if (res < 0) continue;
                                if (res == 1) {
                                    if (hs > 1) incons_flag = true;
                                    ecs[tid]++;
                                    out.push_back({1, ns, (uint8_t)(g + 1), 0, 1, id, DCH[mv]});
                                    continue;
                                }
                                uint64_t hk = ns.hash64(M.n, M.has_bard); if (!hk) hk = 1;
                                int64_t ex = lookup_id(hk, ns);
                                int hns;
                                if (ex >= 0) {
                                    hns = pool[ex].h_cached;
                                    if (hs > 1 + hns && hns < 255) incons_flag = true;
                                    ecs[tid]++;
                                    if (g + 1 < pool[ex].g)
                                        out.push_back({hk, ns, (uint8_t)(g + 1), (uint8_t)hns, 0, id, DCH[mv]});
                                    else deds[tid]++;
                                } else {
                                    hns = h_admissible(ns);
                                    if (hs > 1 + hns && hns < 999) incons_flag = true;
                                    ecs[tid]++;
                                    if (g + 1 + hns <= max_bound)
                                        out.push_back({hk, ns, (uint8_t)(g + 1), (uint8_t)min(255, hns), 0, id, DCH[mv]});
                                }
                            }
                        }
                    };
                    if (nt == 1) worker(0);
                    else {
                        vector<thread> ths;
                        for (unsigned tid = 0; tid < nt - 1; ++tid) ths.emplace_back(worker, tid);
                        worker(nt - 1);
                        for (auto& t : ths) t.join();
                    }
                    if (incons_flag.load()) { consistency_violated = true; break; }
                    for (unsigned tid = 0; tid < nt; ++tid) {
                        edge_checks += ecs[tid];
                        exact_dedups += deds[tid];
                        for (const auto& c : outs[tid]) {
                            if (c.won) {
                                solved = true;
                                proven_floor = c.g;
                                string wpath(1, c.mv);
                                uint32_t cur = c.par;
                                while (cur != 0xFFFFFFFFu && pool[cur].parent != 0xFFFFFFFFu) {
                                    wpath.push_back(pool[cur].mv);
                                    cur = pool[cur].parent;
                                }
                                reverse(wpath.begin(), wpath.end());
                                winning_witness = wpath;
                                break;
                            }
                            upsert_node(c.hk, c.ns, c.g, c.h, c.par, c.mv);
                        }
                        if (solved) break;
                    }
                }
                vector<uint32_t>().swap(buckets[f]);
                if (consistency_violated || stopped_early) break;
                if (!solved) {
                    proven_floor = f + 1;
                    bool open_left = false;
                    for (int g2 = f + 1; g2 <= max_bound && !open_left; ++g2) open_left = !buckets[g2].empty();
                    if (!open_left) { termination = "exhausted"; proven_floor = max_bound + 1; break; }
                }
            }
            if (solved) termination = "solved";
            // Nothing is claimed unless the start node was actually expanded.
            if (!solved && !start_expanded) proven_floor = 0;
            if (!solved) proven_floor = min(proven_floor, max_bound + 1);

            if (consistency_violated) {
                cout << "{\"proven_floor\":0,\"exact_optimum_reached\":false,\"nodes_expanded\":" << total_nodes
                     << ",\"edge_consistency_checks\":" << edge_checks
                     << ",\"epistemic_status\":\"REJECTED_STEP_INCONSISTENT\"}\n";
                return 0;
            }
            cout << "{\"proven_floor\":" << proven_floor
                 << ",\"exact_optimum_reached\":" << (solved ? "true" : "false")
                 << ",\"search_strategy\":\"multicore_exact_bucketed_astar\""
                 << ",\"quotient_pdb_enabled\":" << ((qpdb.enabled || ppdb.enabled) ? "true" : "false")
                 << ",\"pair_atom_pdb_enabled\":" << (ppdb.enabled ? "true" : "false")
                 << ",\"wizard_ray_bound_enabled\":" << (wiz_bound.enabled ? "true" : "false")
                 << ",\"exact_state_tt\":true"
                 << ",\"exact_tt_prunes\":" << exact_dedups
                 << ",\"hash_collisions_prevented\":" << hash_collisions_prevented
                 << ",\"nodes_expanded\":" << total_nodes
                 << ",\"edge_consistency_checks\":" << edge_checks
                 << ",\"completed_depth\":" << (proven_floor - 1)
                 << ",\"termination_reason\":\"" << termination << "\""
                 << ",\"timed_out\":" << (timed_out ? "true" : "false")
                 << ",\"states_seen\":" << pool.size()
                 << ",\"start_heuristic\":" << h0
                 << ",\"requested_bound\":" << requested_bound << ",\"effective_bound\":" << max_bound
                 << ",\"search_algorithm\":\"exact_state_bucketed_astar\""
                 << ",\"winning_witness\":\"" << winning_witness << "\""
                 << ",\"epistemic_status\":\"" << (solved ? "VERIFIED" : "EXHAUSTIVE_LOWER_BOUND") << "\"}\n";
            return 0;
        }

        // Strategy B (Grids 129..512 cells): Collision-free ExactTTSlot IDA*
        struct ExactTTSlot {
            uint64_t hk = 0;
            uint16_t iter_id = 0;
            uint16_t best_g = 0;
            DynState st;
        };
        const size_t TT_BITS = 18;
        const size_t TT_SIZE = 1ULL << TT_BITS;
        const size_t TT_MASK = TT_SIZE - 1;
        vector<ExactTTSlot> tt(TT_SIZE);

        uint64_t edge_checks = 0, total_nodes = 0, exact_tt_prunes = 0, hash_collisions_prevented = 0;
        int proven_floor = h_admissible(s0);
        bool solved = false, consistency_violated = false;
        string winning_witness;

        for (int bound = proven_floor; !solved && !consistency_violated && bound <= max_bound; ++bound) {
            if (chrono::duration<double>(chrono::steady_clock::now() - t0).count() > budget_s) break;
            uint16_t iter_id = (uint16_t)(bound + 1);
            bool found = false, timed_out = false;
            int h0 = h_admissible(s0);
            if (h0 > bound) { proven_floor = h0; bound = h0 - 1; continue; }
            string path_buf;

            function<void(const DynState&, int, int)> dfs = [&](const DynState& s, int g, int hs) {
                if (found || timed_out || consistency_violated || g + hs > bound) return;
                if ((total_nodes & 8191) == 0 &&
                    chrono::duration<double>(chrono::steady_clock::now() - t0).count() > budget_s) {
                    timed_out = true; return;
                }
                uint64_t hk = s.hash64(M.n, M.has_bard);
                size_t base_slot = hk & TT_MASK, write_slot = base_slot;
                bool slot_chosen = false;
                for (size_t probe = 0; probe < 4; ++probe) {
                    size_t idx = (base_slot + probe) & TT_MASK;
                    auto& ent = tt[idx];
                    if (ent.iter_id != iter_id) {
                        if (!slot_chosen) { write_slot = idx; slot_chosen = true; }
                        continue;
                    }
                    if (ent.hk == hk) {
                        if (s.eq(ent.st, M.n, M.has_bard)) {
                            if ((int)ent.best_g <= g) { exact_tt_prunes++; return; }
                            write_slot = idx; slot_chosen = true; break;
                        } else {
                            hash_collisions_prevented++;
                        }
                    }
                }
                tt[write_slot].hk = hk;
                tt[write_slot].iter_id = iter_id;
                tt[write_slot].best_g = (uint16_t)g;
                tt[write_slot].st = s;
                total_nodes++;

                for (int mv = 0; mv < 5; ++mv) {
                    DynState ns = s;
                    int res = step_state(M, ns, mv, true);
                    if (res < 0) continue;
                    int hns = (res == 1) ? 0 : h_admissible(ns);
                    if (hs > 1 + hns && hns < 999) { consistency_violated = true; return; }
                    edge_checks++;
                    if (g + 1 + hns <= bound) {
                        path_buf.push_back(DCH[mv]);
                        if (res == 1) { found = true; winning_witness = path_buf; path_buf.pop_back(); return; }
                        dfs(ns, g + 1, hns);
                        path_buf.pop_back();
                        if (found || timed_out || consistency_violated) return;
                    }
                }
            };
            dfs(s0, 0, h0);
            if (consistency_violated || timed_out) break;
            if (found) { solved = true; proven_floor = bound; break; }
            else proven_floor = bound + 1;
        }
        if (!solved && total_nodes == 0) proven_floor = 0;
        if (!solved) proven_floor = min(proven_floor, max_bound + 1);

        if (consistency_violated) {
            cout << "{\"proven_floor\":0,\"exact_optimum_reached\":false,\"nodes_expanded\":" << total_nodes
                 << ",\"edge_consistency_checks\":" << edge_checks
                 << ",\"epistemic_status\":\"REJECTED_STEP_INCONSISTENT\"}\n";
            return 0;
        }
        cout << "{\"proven_floor\":" << proven_floor
             << ",\"exact_optimum_reached\":" << (solved ? "true" : "false")
             << ",\"search_strategy\":\"exact_state_ida_star\""
             << ",\"quotient_pdb_enabled\":" << ((qpdb.enabled || ppdb.enabled) ? "true" : "false")
             << ",\"pair_atom_pdb_enabled\":" << (ppdb.enabled ? "true" : "false")
             << ",\"wizard_ray_bound_enabled\":" << (wiz_bound.enabled ? "true" : "false")
             << ",\"exact_state_tt\":true"
             << ",\"exact_tt_prunes\":" << exact_tt_prunes
             << ",\"hash_collisions_prevented\":" << hash_collisions_prevented
             << ",\"nodes_expanded\":" << total_nodes
             << ",\"edge_consistency_checks\":" << edge_checks
             << ",\"completed_depth\":" << (proven_floor - 1)
             << ",\"termination_reason\":\"" << (solved ? "solved" : (total_nodes == 0 ? "not_started" : "max_bound_or_budget")) << "\""
             << ",\"search_algorithm\":\"exact_state_ida_star\""
             << ",\"winning_witness\":\"" << winning_witness << "\""
             << ",\"epistemic_status\":\"" << (solved ? "VERIFIED" : "EXHAUSTIVE_LOWER_BOUND") << "\"}\n";
        return 0;
    }

    return 1;
}
