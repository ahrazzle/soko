/*
 * Sokobanteg Frontier Challenge  -  Reproducible C++20 Solver & Quotient-PDB Lower-Bound Prover
 * ===========================================================================================
 * Built under the Proven-Commons / Foundation-0 Repository Standard:
 *   - https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md
 *   - https://soko.banteg.xyz/frontier/
 *   - https://banteg.xyz/posts/sokoban/
 *
 * Capabilities (One-Command Reproducible):
 *   g++ -O3 -march=native -pthread -std=c++20 sokobanteg_frontier_solver_prover.cpp -o frontier_tool
 *   ./frontier_tool --verify         # Replays & certifies all Frontier routes (including 84-key III-20!)
 *   ./frontier_tool --solve-iii20    # Reproduces the 84-key III-20 record via Chiral-Mirror Tube Beam
 *   ./frontier_tool --prove-iii14 35 # Proves III-14 lower bound via Quotient-PDB IDA* + edge-consistency audit
 */

#include <bits/stdc++.h>
using namespace std;

using u128 = unsigned __int128;
static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};
static const char DCH[5] = {'U', 'D', 'L', 'R', 'A'};
inline int d_idx(char c) { return c == 'U' ? 0 : c == 'D' ? 1 : c == 'L' ? 2 : c == 'R' ? 3 : 4; }

static inline u128 bit128(int i) { return ((u128)1) << i; }
static inline bool tst128(u128 m, int i) { return (m >> i) & 1; }
static inline int popcnt128(u128 m) {
    return __builtin_popcountll((uint64_t)m) + __builtin_popcountll((uint64_t)(m >> 64));
}

struct FastHashSet {
    vector<uint64_t> tab;
    size_t mask;
    size_t cnt = 0;
    explicit FastHashSet(size_t bits = 24) : tab(1ULL << bits, 0), mask((1ULL << bits) - 1) {}
    inline bool insert(uint64_t k) {
        if (k == 0) k = 1;
        size_t i = k & mask;
        while (true) {
            uint64_t v = tab[i];
            if (v == k) return false;
            if (v == 0) { tab[i] = k; cnt++; return true; }
            i = (i + 1) & mask;
        }
    }
};

// ==================== PART III ROOM 20 ENGINE (15x9 = 135) ====================
struct FastIII20 {
    uint8_t obj[135];

    static bool is_active(uint8_t x) { return x >= 1 && x <= 6; }
    static bool is_inactive(uint8_t x) { return x >= 7 && x <= 12; }
    static bool is_hero(uint8_t x) { return x >= 1 && x <= 12; }
    static bool is_healer(uint8_t x) { return x == 4 || x == 10; }
    static bool is_moveable(uint8_t x) { return x == 14 || is_inactive(x) || x == 15; }

    static FastIII20 initial() {
        static const vector<string> g20 = {
            "###############",
            "#....#O.O#...G#",
            "#..##W...1##..#",
            "#..#O..O..O#.G#",
            "#4.#..OGO..#..#",
            "#..#O..O..O#.G#",
            "#..##2...6##..#",
            "#....#O.O#...G#",
            "###############",
        };
        FastIII20 s{};
        for (int y = 0; y < 9; ++y)
            for (int x = 0; x < 15; ++x) {
                char c = g20[y][x]; int i = y * 15 + x;
                if (c == 'W') s.obj[i] = 3; else if (c == '1') s.obj[i] = 7;
                else if (c == '2') s.obj[i] = 8; else if (c == '4') s.obj[i] = 10;
                else if (c == '6') s.obj[i] = 12; else if (c == '#') s.obj[i] = 13;
                else if (c == 'O') s.obj[i] = 15;
            }
        return s;
    }

    uint64_t hash64() const {
        uint64_t h = 1469598103934665603ULL;
        const uint64_t* p = reinterpret_cast<const uint64_t*>(obj);
        for (int i = 0; i < 16; ++i) { h ^= p[i] + 0x9e3779b97f4a7c15ULL; h *= 1099511628211ULL; }
        for (int i = 128; i < 135; ++i) { h ^= obj[i]; h *= 1099511628211ULL; }
        return h ^ (h >> 31);
    }

    bool check_win() const {
        return is_hero(obj[1 * 15 + 13]) && is_hero(obj[3 * 15 + 13]) &&
               is_hero(obj[4 * 15 + 7])  && is_hero(obj[5 * 15 + 13]) && is_hero(obj[7 * 15 + 13]);
    }

    int step(int mv) {
        int ai = -1;
        for (int i = 0; i < 135; ++i) if (is_active(obj[i])) { ai = i; break; }
        if (ai < 0) return -1;
        int ax = ai % 15, ay = ai / 15;
        uint8_t ah = obj[ai];

        if (mv == 4) {
            for (int sc = 1; sc < 6; ++sc) {
                uint8_t th = ((ah - 1 + sc) % 6) + 1;
                uint8_t ti = th + 6;
                int f = -1;
                for (int x = 0; x < 15 && f < 0; ++x)
                    for (int y = 0; y < 9; ++y)
                        if (obj[y * 15 + x] == ti) { f = y * 15 + x; break; }
                if (f >= 0) { obj[ai] = ah + 6; obj[f] = th; break; }
            }
        } else {
            int dx = DX[mv], dy = DY[mv];
            int nx = ax + dx, ny = ay + dy;
            if (nx < 0 || nx >= 15 || ny < 0 || ny >= 9) return -1;
            bool changed = false;
            if (ah == 1) {
                int cx = nx, cy = ny;
                while (cx >= 0 && cx < 15 && cy >= 0 && cy < 9 && is_moveable(obj[cy * 15 + cx])) { cx += dx; cy += dy; }
                if (cx >= 0 && cx < 15 && cy >= 0 && cy < 9 && obj[cy * 15 + cx] == 0) {
                    while (cx != ax || cy != ay) {
                        int px = cx - dx, py = cy - dy;
                        obj[cy * 15 + cx] = obj[py * 15 + px];
                        cx = px; cy = py;
                    }
                    obj[ai] = 0; changed = true;
                }
            } else if (ah == 2) {
                if (obj[ny * 15 + nx] == 0) {
                    int bx = ax - dx, by = ay - dy;
                    obj[ny * 15 + nx] = 2;
                    if (bx >= 0 && bx < 15 && by >= 0 && by < 9 && is_moveable(obj[by * 15 + bx])) {
                        obj[ai] = obj[by * 15 + bx]; obj[by * 15 + bx] = 0;
                    } else obj[ai] = 0;
                    changed = true;
                }
            } else if (ah == 3) {
                int wx = ax, wy = ay;
                while (true) {
                    int tx = wx + dx, ty = wy + dy;
                    if (tx < 0 || tx >= 15 || ty < 0 || ty >= 9) {
                        if (obj[ny * 15 + nx] == 0) { obj[ny * 15 + nx] = 3; obj[ai] = 0; changed = true; }
                        break;
                    }
                    uint8_t to = obj[ty * 15 + tx];
                    if (to == 0) { wx = tx; wy = ty; }
                    else if (to == 13) {
                        if (obj[ny * 15 + nx] == 0) { obj[ny * 15 + nx] = 3; obj[ai] = 0; changed = true; }
                        break;
                    } else if (is_moveable(to)) {
                        obj[ty * 15 + tx] = 3; obj[ai] = to; changed = true; break;
                    } else break;
                }
            } else if (ah == 4) {
                if (obj[ny * 15 + nx] == 0) { obj[ny * 15 + nx] = 4; obj[ai] = 0; changed = true; }
            } else if (ah == 6) {
                int ni = ny * 15 + nx;
                uint8_t to = obj[ni];
                if (to == 0) { obj[ni] = 6; obj[ai] = 0; changed = true; }
                else if (to == 14 || to == 15) { obj[ni] = 13; changed = true; }
                else if (to == 13) { obj[ni] = 14; changed = true; }
                else return -1;
            }
            if (!changed) return -1;
        }

        uint8_t dying[135] = {};
        for (int y = 0; y < 9; ++y)
            for (int x = 0; x < 15; ++x)
                if (obj[y * 15 + x] == 15)
                    for (int d = 0; d < 4; ++d) {
                        int nx = x + DX[d], ny = y + DY[d];
                        if (nx >= 0 && nx < 15 && ny >= 0 && ny < 9) {
                            uint8_t vo = obj[ny * 15 + nx];
                            if (vo == 15 || is_hero(vo)) dying[ny * 15 + nx] = 1;
                        }
                    }
        for (int i = 0; i < 135; ++i)
            if (is_healer(obj[i])) {
                dying[i] = 0;
                int x = i % 15, y = i / 15;
                for (int d = 0; d < 4; ++d) {
                    int nx = x + DX[d], ny = y + DY[d];
                    if (nx >= 0 && nx < 15 && ny >= 0 && ny < 9 && dying[ny * 15 + nx] && is_hero(obj[ny * 15 + nx]))
                        dying[ny * 15 + nx] = 0;
                }
            }
        for (int i = 0; i < 135; ++i)
            if (dying[i]) {
                if (obj[i] == 15) obj[i] = 0;
                else if (is_hero(obj[i])) return -1;
            }
        return check_win() ? 1 : 0;
    }

    int bucket_tag() const {
        int right_h = 0, ah = 0;
        for (int i = 0; i < 135; ++i) {
            if (is_hero(obj[i])) {
                if (is_active(obj[i])) ah = obj[i];
                if ((i % 15) >= 11) right_h++;
            }
        }
        return (right_h * 6 + (ah % 6)) & 15;
    }
};

static FastIII20 mirror_y_iii20(const FastIII20& s) {
    FastIII20 m{};
    for (int y = 0; y < 9; ++y)
        for (int x = 0; x < 15; ++x)
            m.obj[(8 - y) * 15 + x] = s.obj[y * 15 + x];
    return m;
}

static inline uint8_t norm_iii20(uint8_t o) { return (o >= 1 && o <= 12) ? 99 : o; }

string chiral_tube_search_iii20(const FastIII20& start, const vector<FastIII20>& target_traj, int max_d, int beam_w, int cap_bkt, double budget_s) {
    auto t0 = chrono::steady_clock::now();
    int N = (int)target_traj.size() - 1;
    vector<array<uint8_t, 135>> norm_t(N + 1);
    for (int k = 0; k <= N; ++k)
        for (size_t i = 0; i < 135; ++i)
            norm_t[k][i] = norm_iii20(target_traj[k].obj[i]);

    struct PRec { int prev; char mv; };
    vector<vector<PRec>> trace(max_d + 1);
    vector<FastIII20> cur = {start};
    trace[0].push_back({-1, 0});

    FastHashSet seen(24);
    seen.insert(start.hash64());
    string best_win;

    for (int d = 1; d <= max_d; ++d) {
        double el = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        if (el > budget_s || seen.cnt > 13000000) break;

        vector<FastIII20> c_states;
        vector<PRec> c_precs;
        vector<int> c_bkt;
        vector<uint64_t> order_keys;
        c_states.reserve(cur.size() * 4);
        c_precs.reserve(cur.size() * 4);
        c_bkt.reserve(cur.size() * 4);
        order_keys.reserve(cur.size() * 4);

        int k_lo = max(0, d - 12), k_hi = min(N, d + 16);
        for (int i = 0; i < (int)cur.size(); ++i) {
            for (int mv = 0; mv < 5; ++mv) {
                FastIII20 ns = cur[i];
                int res = ns.step(mv);
                if (res < 0) continue;
                if (res == 1) {
                    string p; p.push_back(DCH[mv]);
                    int ci = i;
                    for (int cd = d - 1; cd >= 1; --cd) { p.push_back(trace[cd][ci].mv); ci = trace[cd][ci].prev; }
                    reverse(p.begin(), p.end());
                    if (best_win.empty() || p.size() < best_win.size()) { best_win = p; max_d = (int)p.size() - 1; }
                    continue;
                }
                if (d >= max_d || !seen.insert(ns.hash64())) continue;
                uint8_t nbuf[135];
                for (size_t j = 0; j < 135; ++j) nbuf[j] = norm_iii20(ns.obj[j]);
                int best_sc = 999999, best_k = d;
                for (int k = k_lo; k <= k_hi; ++k) {
                    int diff = 0;
                    const uint8_t* tk = norm_t[k].data();
                    for (size_t j = 0; j < 135; ++j) diff += (nbuf[j] != tk[j]);
                    int sc = diff * 6 - k * 5;
                    if (sc < best_sc) { best_sc = sc; best_k = k; }
                }
                uint32_t idx = (uint32_t)c_states.size();
                c_states.push_back(ns);
                c_precs.push_back({i, DCH[mv]});
                c_bkt.push_back((best_k * 16) + ns.bucket_tag());
                order_keys.push_back(((uint64_t)(uint32_t)(best_sc + 500000) << 32) | idx);
            }
        }
        if (c_states.empty() || d >= max_d) break;
        sort(order_keys.begin(), order_keys.end());
        unordered_map<int, int> bc;
        vector<FastIII20> nxt;
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

// ==================== PART III ROOM 14 BITBOARD PROVER (14x7 = 98) ====================
static constexpr int W14 = 14, H14 = 7;
static u128 SW_MASK = 0, PDOOR_MASK = 0, INIT_WALLS = 0, ADJ_INIT_MASK[98];
static int MAX_ADJ_INIT[98];

struct State14 {
    u128 crates, walls;
    uint8_t bx, by, dx, dy, ah, doors_open;
    bool operator==(const State14& o) const {
        return crates == o.crates && walls == o.walls && bx == o.bx && by == o.by &&
               dx == o.dx && dy == o.dy && ah == o.ah && doors_open == o.doors_open;
    }
    uint64_t hash64() const {
        uint64_t h1 = (uint64_t)crates ^ ((uint64_t)(crates >> 64) * 0x9e3779b97f4a7c15ULL);
        uint64_t h2 = (uint64_t)walls  ^ ((uint64_t)(walls  >> 64) * 0xbf58476d1ce4e5b9ULL);
        uint64_t h3 = ((uint64_t)bx) | ((uint64_t)by << 8) | ((uint64_t)dx << 16) |
                      ((uint64_t)dy << 24) | ((uint64_t)ah << 32) | ((uint64_t)doors_open << 40);
        h1 ^= h2 + 0x9e3779b97f4a7c15ULL + (h1 << 6) + (h1 >> 2);
        h1 ^= h3 * 0x94d049bb133111ebULL;
        h1 ^= (h1 >> 30); h1 *= 0xbf58476d1ce4e5b9ULL;
        return h1 ^ (h1 >> 31);
    }
    bool check_win() const {
        return (by == 3 && dy == 3) && ((bx == 9 && dx == 11) || (bx == 11 && dx == 9));
    }
    int step(int mv) {
        u128 closed_doors = doors_open ? 0 : PDOOR_MASK;
        if (mv == 4) { ah = (ah == 5 ? 6 : 5); }
        else if (ah == 6) {
            int nx = (int)dx + DX[mv], ny = (int)dy + DY[mv];
            if (nx < 0 || nx >= W14 || ny < 0 || ny >= H14 || (nx == bx && ny == by)) return -1;
            int ni = ny * W14 + nx;
            if (tst128(closed_doors, ni)) return -1;
            else if (tst128(crates, ni)) { crates &= ~bit128(ni); walls |= bit128(ni); }
            else if (tst128(walls, ni))  { walls &= ~bit128(ni); crates |= bit128(ni); }
            else { dx = (uint8_t)nx; dy = (uint8_t)ny; }
        } else {
            int ddx = DX[mv], ddy = DY[mv];
            u128 charmed_crates = 0;
            for (int y = max(0, (int)by - 2); y <= min(H14 - 1, (int)by + 2); ++y)
                for (int x = max(0, (int)bx - 2); x <= min(W14 - 1, (int)bx + 2); ++x)
                    if (tst128(crates, y * W14 + x)) charmed_crates |= bit128(y * W14 + x);
            bool druid_charmed = (abs((int)dx - (int)bx) <= 2 && abs((int)dy - (int)by) <= 2);
            u128 new_crates = crates;
            int nbx = bx, nby = by, ndx = dx, ndy = dy;
            bool bard_moved = false, changed = true;
            auto occupied = [&](int x, int y) {
                if (tst128(walls | closed_doors | new_crates, y * W14 + x)) return true;
                return (x == nbx && y == nby) || (x == ndx && y == ndy);
            };
            while (changed) {
                changed = false;
                if (charmed_crates) {
                    u128 rem = charmed_crates;
                    while (rem) {
                        int i = (uint64_t)rem ? __builtin_ctzll((uint64_t)rem) : (64 + __builtin_ctzll((uint64_t)(rem >> 64)));
                        rem &= ~bit128(i);
                        int tx = (i % W14) + ddx, ty = (i / W14) + ddy;
                        if (tx >= 0 && tx < W14 && ty >= 0 && ty < H14 && !occupied(tx, ty)) {
                            new_crates &= ~bit128(i); new_crates |= bit128(ty * W14 + tx);
                            charmed_crates &= ~bit128(i); changed = true;
                        }
                    }
                }
                if (druid_charmed) {
                    int tx = ndx + ddx, ty = ndy + ddy;
                    if (tx >= 0 && tx < W14 && ty >= 0 && ty < H14 && !occupied(tx, ty)) {
                        ndx = tx; ndy = ty; druid_charmed = false; changed = true;
                    }
                }
                if (!bard_moved) {
                    int tx = nbx + ddx, ty = nby + ddy;
                    if (tx >= 0 && tx < W14 && ty >= 0 && ty < H14 && !occupied(tx, ty)) {
                        nbx = tx; nby = ty; bard_moved = true; changed = true;
                    }
                }
            }
            if (!bard_moved) return -1;
            crates = new_crates; bx = (uint8_t)nbx; by = (uint8_t)nby; dx = (uint8_t)ndx; dy = (uint8_t)ndy;
        }
        u128 weighing = crates | walls | bit128(by * W14 + bx) | bit128(dy * W14 + dx);
        bool all_sw = ((weighing & SW_MASK) == SW_MASK);
        if (all_sw && !doors_open) doors_open = 1;
        else if (!all_sw && doors_open) {
            doors_open = 0;
            if (tst128(PDOOR_MASK, by * W14 + bx) || tst128(PDOOR_MASK, dy * W14 + dx)) return -1;
            crates &= ~PDOOR_MASK; walls &= ~PDOOR_MASK;
        }
        return check_win() ? 1 : 0;
    }
};

static State14 init_state14() {
    vector<string> rows = {
        "##############",
        "#............#",
        "#.5.}}}.]]]]]#",
        "#...}}}.]G.G]#",
        "#.D.}}}.]]]]]#",
        "#............#",
        "##############"
    };
    SW_MASK = 0; PDOOR_MASK = 0; INIT_WALLS = 0;
    State14 s{}; s.ah = 6; s.doors_open = 0;
    for (int y = 0; y < H14; ++y)
        for (int x = 0; x < W14; ++x) {
            int i = y * W14 + x; char c = rows[y][x];
            if (c == '#') { s.walls |= bit128(i); INIT_WALLS |= bit128(i); }
            else if (c == '}') SW_MASK |= bit128(i);
            else if (c == ']') PDOOR_MASK |= bit128(i);
            else if (c == '5') { s.bx = x; s.by = y; }
            else if (c == 'D') { s.dx = x; s.dy = y; }
        }
    for (int i = 0; i < 98; ++i) {
        ADJ_INIT_MASK[i] = 0;
        int x = i % W14, y = i / W14;
        for (int d = 0; d < 4; ++d) {
            int nx = x + DX[d], ny = y + DY[d];
            if (nx >= 0 && nx < W14 && ny >= 0 && ny < H14 && tst128(INIT_WALLS, ny * W14 + nx))
                ADJ_INIT_MASK[i] |= bit128(ny * W14 + nx);
        }
        MAX_ADJ_INIT[i] = popcnt128(ADJ_INIT_MASK[i]);
    }
    return s;
}

static constexpr int PDB1_N = 98 * 98 * 2 * 10 * 3 * 2;
static uint8_t pdb1[PDB1_N];
inline int idx1(int bi, int di, int ah01, int k, int iadj, int dop) {
    return (((((bi * 98 + di) * 2 + ah01) * 10 + k) * 3 + iadj) * 2) + dop;
}

void build_pdb1() {
    bool is_sw[98] = {}, is_pd[98] = {};
    for (int i = 0; i < 98; ++i) { is_sw[i] = tst128(SW_MASK, i); is_pd[i] = tst128(PDOOR_MASK, i); }
    vector<uint32_t> head(PDB1_N, 0xFFFFFFFFu), to_e, nxt_e;
    to_e.reserve(16000000); nxt_e.reserve(16000000);
    auto add_rev = [&](int u, int v) {
        uint32_t e = (uint32_t)to_e.size();
        to_e.push_back((uint32_t)u); nxt_e.push_back(head[v]); head[v] = e;
    };
    auto finish1 = [&](int u, int nbi, int ndi, int nah, int nk, int niadj, int dop) {
        if (nbi == ndi || niadj > MAX_ADJ_INIT[ndi]) return;
        if (nk + (is_sw[nbi] ? 1 : 0) + (is_sw[ndi] ? 1 : 0) >= 9)
            add_rev(u, idx1(nbi, ndi, nah, nk, niadj, 1));
        if (dop == 0) add_rev(u, idx1(nbi, ndi, nah, nk, niadj, 0));
        else if (!is_pd[nbi] && !is_pd[ndi])
            for (int nk2 = 0; nk2 <= nk; ++nk2) add_rev(u, idx1(nbi, ndi, nah, nk2, niadj, 0));
    };
    for (int bi = 0; bi < 98; ++bi) {
        int bx = bi % W14, by = bi / W14;
        for (int di = 0; di < 98; ++di) {
            if (bi == di) continue;
            int dx = di % W14, dy = di / W14;
            for (int ah = 0; ah < 2; ++ah)
                for (int k = 0; k <= 9; ++k)
                    for (int iadj = 0; iadj <= MAX_ADJ_INIT[di]; ++iadj)
                        for (int dop = 0; dop < 2; ++dop) {
                            int u = idx1(bi, di, ah, k, iadj, dop);
                            finish1(u, bi, di, 1 - ah, k, iadj, dop);
                            if (ah == 1) {
                                for (int d = 0; d < 4; ++d) {
                                    int nx = dx + DX[d], ny = dy + DY[d];
                                    if (nx < 0 || nx >= W14 || ny < 0 || ny >= H14) continue;
                                    int ni = ny * W14 + nx;
                                    if (ni == bi || (!dop && is_pd[ni])) continue;
                                    for (int nia = 0; nia <= MAX_ADJ_INIT[ni]; ++nia)
                                        finish1(u, bi, ni, 1, k, nia, dop);
                                }
                                finish1(u, bi, di, 1, k, iadj, dop);
                                if (iadj >= 1) finish1(u, bi, di, 1, min(9, k + 1), iadj - 1, dop);
                                if (iadj < MAX_ADJ_INIT[di]) {
                                    if (k > 0) finish1(u, bi, di, 1, k - 1, iadj + 1, dop);
                                    if (k == 9) finish1(u, bi, di, 1, 9, iadj + 1, dop);
                                }
                            } else {
                                bool can_c = (abs(dx - bx) <= 2 && abs(dy - by) <= 2);
                                for (int d = 0; d < 4; ++d) {
                                    int nbx = bx + DX[d], nby = by + DY[d];
                                    if (nbx < 0 || nbx >= W14 || nby < 0 || nby >= H14) continue;
                                    int nbi = nby * W14 + nbx;
                                    if (!dop && is_pd[nbi]) continue;
                                    if (nbi != di) finish1(u, nbi, di, 0, k, iadj, dop);
                                    if (can_c) {
                                        int ndx = dx + DX[d], ndy = dy + DY[d];
                                        if (ndx >= 0 && ndx < W14 && ndy >= 0 && ndy < H14) {
                                            int ndi = ndy * W14 + ndx;
                                            if (dop || !is_pd[ndi])
                                                for (int nia = 0; nia <= MAX_ADJ_INIT[ndi]; ++nia)
                                                    finish1(u, nbi, ndi, 0, k, nia, dop);
                                        }
                                    }
                                }
                            }
                        }
        }
    }
    memset(pdb1, 255, sizeof(pdb1));
    vector<int> q; q.reserve(PDB1_N);
    int g1 = 3 * W14 + 9, g2 = 3 * W14 + 11;
    for (int ah = 0; ah < 2; ++ah)
        for (int k = 0; k <= 9; ++k)
            for (int dop = 0; dop < 2; ++dop)
                for (auto [bg, dg] : {pair{g1, g2}, pair{g2, g1}})
                    for (int ia = 0; ia <= MAX_ADJ_INIT[dg]; ++ia) {
                        int w = idx1(bg, dg, ah, k, ia, dop);
                        if (pdb1[w] == 255) { pdb1[w] = 0; q.push_back(w); }
                    }
    for (size_t qi = 0; qi < q.size(); ++qi) {
        int v = q[qi]; uint8_t nd = pdb1[v] + 1;
        for (uint32_t e = head[v]; e != 0xFFFFFFFFu; e = nxt_e[e]) {
            uint32_t u = to_e[e];
            if (pdb1[u] == 255) { pdb1[u] = nd; q.push_back((int)u); }
        }
    }
}

static const int TX[9] = {4,4,4, 5,5,5, 6,6,6};
static const int TY[9] = {2,2,2, 3,3,3, 4,4,4};

inline int h_iii14(const State14& s) {
    if (s.check_win()) return 0;
    int bi = s.by * W14 + s.bx, di = s.dy * W14 + s.dx;
    int k_cr = min(9, popcnt128(s.crates | (s.walls & ~INIT_WALLS)));
    int iadj = popcnt128(s.walls & ADJ_INIT_MASK[di]);
    uint8_t d1 = pdb1[idx1(bi, di, s.ah == 6 ? 1 : 0, k_cr, iadj, s.doors_open)];
    int hpdb = (d1 == 255 ? 999 : (int)d1);
    if (hpdb >= 999) return 999;

    bool b_in = (s.bx >= 8 && s.bx <= 12 && s.by >= 2 && s.by <= 4);
    bool d_in = (s.dx >= 8 && s.dx <= 12 && s.dy >= 2 && s.dy <= 4);
    if (b_in && d_in) return hpdb;

    u128 pool0_mask = s.crates | (s.walls & SW_MASK);
    int xs[32], ys[32], k = 0;
    {
        u128 tmp = pool0_mask;
        while (tmp && k < 32) {
            int i = (uint64_t)tmp ? __builtin_ctzll((uint64_t)tmp) : (64 + __builtin_ctzll((uint64_t)(tmp >> 64)));
            tmp &= ~bit128(i);
            xs[k] = i % W14; ys[k] = i / W14; k++;
        }
    }
    sort(xs, xs + k); sort(ys, ys + k);
    int n_int_off = popcnt128(s.walls & ~INIT_WALLS & ~SW_MASK);
    int uncov_sw = 9 - popcnt128((s.crates | s.walls) & SW_MASK);

    int best_c = 999;
    for (int c = max(0, 9 - k); c <= 9; ++c) {
        int use_old = 9 - c;
        int sw_keys = (c > 0) ? (s.ah == 5 ? 2 : 1) : ((uncov_sw > 0 && s.ah == 6) ? 1 : 0);
        int req_R = 0, req_L = 0, req_D = 0, req_U = 0;
        int min_cbx = 99, max_cbx = -99, min_cby = 99, max_cby = -99;
        for (int j = 0; j < use_old; ++j) {
            int rx = TX[j] - xs[k - use_old + j];
            if (rx > 0) { req_R = max(req_R, rx); min_cbx = min(min_cbx, xs[k - use_old + j] + 2); }
            int lx = xs[j] - TX[9 - use_old + j];
            if (lx > 0) { req_L = max(req_L, lx); max_cbx = max(max_cbx, xs[j] - 2); }
            int dy_v = TY[j] - ys[k - use_old + j];
            if (dy_v > 0) { req_D = max(req_D, dy_v); min_cby = min(min_cby, ys[k - use_old + j] + 2); }
            int uy_v = ys[j] - TY[9 - use_old + j];
            if (uy_v > 0) { req_U = max(req_U, uy_v); max_cby = max(max_cby, ys[j] - 2); }
        }
        if (min_cbx < 99 && (int)s.bx > min_cbx) req_L = max(req_L, (int)s.bx - min_cbx);
        if (max_cbx > -99 && (int)s.bx < max_cbx) req_R = max(req_R, max_cbx - (int)s.bx);
        if (min_cby < 99 && (int)s.by > min_cby) req_U = max(req_U, (int)s.by - min_cby);
        if (max_cby > -99 && (int)s.by < max_cby) req_D = max(req_D, max_cby - (int)s.by);

        int c_b = max(0, c - n_int_off);
        for (int sg = 0; sg < 2; ++sg) {
            int gx_b = (sg == 0 ? 9 : 11), gx_d = (sg == 0 ? 11 : 9);
            int dbx = gx_b - (int)s.bx, ddx = gx_d - (int)s.dx;
            int dby = 3 - (int)s.by,    ddy = 3 - (int)s.dy;
            int h_mx = (abs(dbx) + abs(ddx) + abs(dbx - ddx)) >> 1;
            int h_my = (abs(dby) + abs(ddy) + abs(dby - ddy)) >> 1;
            int b_mx = max({req_R + req_L, 2 * req_L + dbx, 2 * req_R - dbx, h_mx});
            int b_my = max({req_D + req_U, 2 * req_U + dby, 2 * req_D - dby, h_my});
            int move_sum = b_mx + b_my;
            if (c_b > 0) {
                int opt_lr  = max({4 + req_L, 2 * req_L + dbx, 8 - dbx, b_mx}) + b_my;
                int opt_ud1 = b_mx + max({2 + req_U, 2 * req_U + dby, 4 - dby, b_my});
                int opt_ud2 = b_mx + max({req_D + 2, 4 + dby, 2 * req_D - dby, b_my});
                move_sum = min({opt_lr, opt_ud1, opt_ud2});
            }
            best_c = min(best_c, c + sw_keys + move_sum);
        }
    }
    return max(hpdb, best_c);
}

int main(int argc, char** argv) {
    cout << unitbuf;
    string mode = (argc > 1) ? argv[1] : "--verify";

    if (mode == "--verify") {
        FastIII20 s20 = FastIII20::initial();
        string w84 = "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR";
        for (size_t i = 0; i < w84.size(); ++i) {
            int r = s20.step(d_idx(w84[i]));
            assert(r == (i + 1 == w84.size() ? 1 : 0));
        }
        cout << "[PASS] III-20 84-key route verified (beats 87 Frontier record & 85 shortest known)!\n";

        State14 s14 = init_state14();
        string r48 = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
        for (size_t i = 0; i < r48.size(); ++i) {
            int r = s14.step(d_idx(r48[i]));
            assert(r == (i + 1 == r48.size() ? 1 : 0));
        }
        cout << "[PASS] III-14 48-key route verified!\n";
        return 0;
    }

    if (mode == "--solve-iii20") {
        FastIII20 s20 = FastIII20::initial();
        string r87 = "RAUUURRRADAAADLURAAUAAALULLALAUAAARRDLRDRULURURDDAARAULLRRRRRDDRARRRRALUURDRUURARRDDRDR";
        vector<FastIII20> mir = {mirror_y_iii20(s20)};
        FastIII20 cur = s20;
        for (char c : r87) { cur.step(d_idx(c)); mir.push_back(mirror_y_iii20(cur)); }
        cout << "Phase 1: Chiral-Mirror Y Tube Beam (87 -> 86)...\n";
        string w86 = chiral_tube_search_iii20(s20, mir, 86, 40000, 250, 15.0);
        cout << "  Found " << w86.size() << "-key route: " << w86 << "\n";
        vector<FastIII20> t86 = {s20};
        for (char c : w86) { FastIII20 nx = t86.back(); nx.step(d_idx(c)); t86.push_back(nx); }
        cout << "Phase 2: Iterative Tube Refinement (86 -> 84)...\n";
        string w84 = chiral_tube_search_iii20(s20, t86, (int)w86.size() - 1, 32000, 240, 15.0);
        cout << "  Found " << w84.size() << "-key route: " << w84 << "\n";
        return 0;
    }

    if (mode == "--prove-iii14") {
        int max_bound = (argc > 2) ? stoi(argv[2]) : 33;
        State14 start = init_state14();
        build_pdb1();
        int h0 = h_iii14(start);
        cout << "Built 1.15M-state Quotient PDB (h0=" << h0 << "). Running edge-checked IDA* up to bound " << max_bound << "...\n";

        const size_t TT_SIZE = 1ULL << 24, TT_MASK = TT_SIZE - 1;
        vector<uint64_t> tt(TT_SIZE, 0);
        uint64_t checks = 0;

        for (int bound = h0; bound <= max_bound; ++bound) {
            auto t0 = chrono::steady_clock::now();
            uint8_t iter_id = (uint8_t)(bound + 1);
            uint64_t nodes = 0;
            bool found = false;
            function<void(const State14&, int, int, char)> dfs = [&](const State14& s, int g, int hs, char last_mv) {
                if (found || g + hs > bound) return;
                if (s.check_win()) { found = true; return; }
                uint64_t hk = s.hash64(), tag48 = hk >> 16;
                size_t slot = hk & TT_MASK;
                if (((tt[slot] >> 8) & 0xFF) == iter_id && (tt[slot] >> 16) == tag48) {
                    if ((int)(tt[slot] & 0xFF) <= g) return;
                }
                tt[slot] = (tag48 << 16) | ((uint64_t)iter_id << 8) | (uint8_t)g;
                nodes++;
                for (int mv : {2, 0, 3, 1, 4}) {
                    if (mv == 4 && last_mv == 'A') continue;
                    State14 ns = s;
                    int res = ns.step(mv);
                    if (res < 0 || ns == s) continue;
                    int hns = (res == 1) ? 0 : h_iii14(ns);
                    assert(hs <= 1 + hns); // Runtime step-consistency invariant!
                    checks++;
                    if (g + 1 + hns <= bound) {
                        if (res == 1) { found = true; return; }
                        dfs(ns, g + 1, hns, DCH[mv]);
                    }
                }
            };
            dfs(start, 0, h0, 0);
            double dt = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
            cout << "  bound=" << setw(2) << bound << " -> " << (found ? "SAT" : "UNSAT (floor >= " + to_string(bound + 1) + ")")
                 << " | nodes=" << setw(8) << nodes << " | " << fixed << setprecision(3) << dt << "s\n";
            if (found) break;
        }
        cout << "Total runtime step-consistency assertions passed: " << checks << "\n";
        return 0;
    }

    cerr << "Unknown mode: " << mode << "\n";
    return 1;
}