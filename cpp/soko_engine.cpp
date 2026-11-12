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

    uint64_t hash64(int n, bool check_notes) const {
        uint64_t h = 1469598103934665603ULL;
        int q = n >> 3;
        const uint64_t* p = reinterpret_cast<const uint64_t*>(obj);
        for (int i = 0; i < q; ++i) { h ^= p[i] + 0x9e3779b97f4a7c15ULL; h *= 1099511628211ULL; }
        for (int i = q << 3; i < n; ++i) { h ^= obj[i]; h *= 1099511628211ULL; }
        h ^= ((uint64_t)y_open << 8) | p_open;
        h *= 1099511628211ULL;
        if (check_notes) {
            int nw = (n + 63) >> 6;
            for (int i = 0; i < nw; ++i) if (notes[i]) { h ^= notes[i] + (uint64_t)i; h *= 1099511628211ULL; }
        }
        return h ^ (h >> 31);
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
        int monsters_left = 0;
        for (int i = 0; i < M.n; ++i) {
            if (dying[i]) {
                if (is_monster(M.part, s.obj[i])) s.obj[i] = 0;
                else if (is_hero(s.obj[i])) return true;
            }
            if (is_monster(M.part, s.obj[i])) monsters_left++;
        }
        if (monsters_left == 0) {
            for (int i = 0; i < M.n; ++i) if (s.obj[i] == 20) s.obj[i] = 0;
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

int step_state(const LevelMeta& M, DynState& s, int mv, bool prune_noop = true) {
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
            // Relax soundly: if nk + hero_sw >= min(K_CAP, req_sw), allow opening p_doors!
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
        double total_budget = max(4.0, (double)p3);
        string best = seed_route;
        vector<string> log_entries;

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

        string w2 = exact_window_shortcut(M, s0, best, win_len);
        if (w2.size() < best.size()) {
            log_entries.push_back("post_window_bfs:" + to_string(best.size()) + "->" + to_string(w2.size()));
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
             << ",\"stages\":[" << log_str << "]}\n";
        return 0;
    }

    if (mode == "solve") {
        int max_d = max(1, p1), beam_w = max(2000, p2);
        double budget_s = max(2.0, (double)p3);
        auto t0 = chrono::steady_clock::now();
        if (check_win(M, s0)) { cout << "{\"solved\":true,\"len\":0,\"route\":\"\",\"explored\":1}\n"; return 0; }

        struct PRec { int prev; char mv; };
        vector<vector<PRec>> trace(max_d + 1);
        vector<DynState> cur = {s0};
        trace[0].push_back({-1, 0});
        FastHashSet seen(24);
        seen.insert(s0.hash64(M.n, M.has_bard));
        string best_win;

        for (int d = 1; d <= max_d; ++d) {
            if (chrono::duration<double>(chrono::steady_clock::now() - t0).count() > budget_s || seen.cnt > 12000000) break;
            vector<DynState> c_states;
            vector<PRec> c_precs;
            vector<int> c_bkt;
            vector<uint64_t> order_keys;
            c_states.reserve(cur.size() * 4);
            c_precs.reserve(cur.size() * 4);
            c_bkt.reserve(cur.size() * 4);
            order_keys.reserve(cur.size() * 4);

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
            if (!best_win.empty() || c_states.empty()) break;
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
             << ",\"explored\":" << seen.cnt << "}\n";
        return 0;
    }

    if (mode == "prove_lb") {
        int max_bound = max(1, p1);
        double budget_s = max(2.0, (double)p3);
        auto t0 = chrono::steady_clock::now();
        bool has_druid = false, has_wizard = false;
        for (int i = 0; i < M.n; ++i) {
            if (s0.obj[i] == 6 || s0.obj[i] == 12) has_druid = true;
            if (s0.obj[i] == 3 || s0.obj[i] == 9) has_wizard = true;
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

        BardDruidQuotientPDB qpdb;
        qpdb.try_build(M, s0);

        auto h_admissible = [&](const DynState& s) -> int {
            if (check_win(M, s)) return 0;
            int best_h = 1;
            if (!has_wizard) {
                for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) best_h = max(best_h, goal_dist[i]);
            }
            if (qpdb.enabled) {
                best_h = max(best_h, qpdb.lookup(M, s));
            }
            return best_h;
        };

        // Exact-state-verified transposition table (2^18 = 262,144 full DynState slots, ~156 MB, ZERO hash-collision pruning!)
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
        bool solved = check_win(M, s0);
        bool consistency_violated = false;
        string winning_witness;
        if (solved) proven_floor = 0;

        for (int bound = proven_floor; !solved && !consistency_violated && bound <= max_bound; ++bound) {
            if (chrono::duration<double>(chrono::steady_clock::now() - t0).count() > budget_s) break;
            uint16_t iter_id = (uint16_t)(bound + 1);
            bool found = false, timed_out = false;
            int h0 = h_admissible(s0);
            if (h0 > bound) { proven_floor = h0; bound = h0 - 1; continue; }
            string path_buf;

            function<void(const DynState&, int, int, char)> dfs = [&](const DynState& s, int g, int hs, char last_mv) {
                if (found || timed_out || consistency_violated || g + hs > bound) return;
                if ((total_nodes & 8191) == 0 &&
                    chrono::duration<double>(chrono::steady_clock::now() - t0).count() > budget_s) {
                    timed_out = true; return;
                }
                uint64_t hk = s.hash64(M.n, M.has_bard);
                size_t base_slot = hk & TT_MASK;
                size_t write_slot = base_slot;
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
                    if (mv == 4 && last_mv == 'A' && M.max_heroes <= 2) continue;
                    DynState ns = s;
                    int res = step_state(M, ns, mv, true);
                    if (res < 0) continue;
                    int hns = (res == 1) ? 0 : h_admissible(ns);
                    if (hs > 1 + hns && hns < 999) {
                        consistency_violated = true;
                        return;
                    }
                    edge_checks++;
                    if (g + 1 + hns <= bound) {
                        path_buf.push_back(DCH[mv]);
                        if (res == 1) { found = true; winning_witness = path_buf; path_buf.pop_back(); return; }
                        dfs(ns, g + 1, hns, DCH[mv]);
                        path_buf.pop_back();
                        if (found || timed_out || consistency_violated) return;
                    }
                }
            };
            dfs(s0, 0, h0, 0);
            if (consistency_violated || timed_out) break;
            if (found) { solved = true; proven_floor = bound; break; }
            else proven_floor = bound + 1;
        }

        if (consistency_violated) {
            cout << "{\"proven_floor\":0,\"exact_optimum_reached\":false,\"nodes_expanded\":" << total_nodes
                 << ",\"edge_consistency_checks\":" << edge_checks
                 << ",\"epistemic_status\":\"REJECTED_STEP_INCONSISTENT\"}\n";
            return 0;
        }
        cout << "{\"proven_floor\":" << proven_floor
             << ",\"exact_optimum_reached\":" << (solved ? "true" : "false")
             << ",\"quotient_pdb_enabled\":" << (qpdb.enabled ? "true" : "false")
             << ",\"exact_state_tt\":true"
             << ",\"exact_tt_prunes\":" << exact_tt_prunes
             << ",\"hash_collisions_prevented\":" << hash_collisions_prevented
             << ",\"nodes_expanded\":" << total_nodes
             << ",\"edge_consistency_checks\":" << edge_checks
             << ",\"winning_witness\":\"" << winning_witness << "\""
             << ",\"epistemic_status\":\"VERIFIED\"}\n";
        return 0;
    }

    return 1;
}

