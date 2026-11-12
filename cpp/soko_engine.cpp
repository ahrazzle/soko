// Heroes of Sokoban replay engine and bounded exact-state breadth-first search.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <queue>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <bitset>

using Mask = std::bitset<512>;

static constexpr int EMPTY = 0;
static constexpr int ACT_F = 1, ACT_T = 2, ACT_W = 3, ACT_P = 4, ACT_B = 5, ACT_D = 6;
static constexpr int INA_1 = 7, INA_6 = 12;
static constexpr int WALL = 13, CRATE = 14, GOBLIN = 15, DRAG_L = 16, DRAG_R = 17;
static constexpr int YDOOR = 18, PDOOR = 19, MGATE = 20;

static constexpr uint64_t FNV64_OFFSET = 14695981039346656037ULL;
static constexpr uint64_t FNV64_PRIME = 1099511628211ULL;
static constexpr uint64_t MASK64 = 0xFFFFFFFFFFFFFFFFULL;

static int char_to_obj(char ch) {
    switch (ch) {
        case 'F': return ACT_F;
        case 'T': return ACT_T;
        case 'W': return ACT_W;
        case 'P': return ACT_P;
        case 'B': return ACT_B;
        case 'D': return ACT_D;
        case '1': return INA_1;
        case '2': return INA_1 + 1;
        case '3': return INA_1 + 2;
        case '4': return INA_1 + 3;
        case '5': return INA_1 + 4;
        case '6': return INA_6;
        case '#': return WALL;
        case '*': return CRATE;
        case 'O': return GOBLIN;
        case 'L': return DRAG_L;
        case 'R': return DRAG_R;
        case '[': return YDOOR;
        case ']': return PDOOR;
        case 'M': return MGATE;
        default: return -1;
    }
}

static char obj_to_char(int c) {
    static const char* tbl = "?FTWPBD123456#*OLR[]M";
    if (c >= ACT_F && c <= MGATE) return tbl[c];
    return '?';
}

struct Engine {
    int part = 1;
    int w = 0, h = 0, n = 0;
    int max_slot = 3;
    Mask goals_mask, ysw_mask, psw_mask;
    Mask ydoor_init_mask, pdoor_init_mask;
    std::vector<int> cells;
    Mask notes_mask;
    int y_open = 0, p_open = 0;
    std::vector<std::vector<int>> orth_neighbors;
    std::vector<Mask> aura5x5_mask;
    std::vector<int> col_major_indices;

    explicit Engine(int p, const std::vector<std::string>& rows) : part(p) {
        h = (int)rows.size();
        w = (int)rows[0].size();
        n = w * h;
        max_slot = (part == 1) ? 3 : (part == 2 ? 4 : 6);
        cells.assign(n, EMPTY);
        orth_neighbors.assign(n, {});
        aura5x5_mask.assign(n, 0);
        for (int idx = 0; idx < n; ++idx) {
            int cx = idx % w, cy = idx / w;
            for (auto [dx, dy] : std::vector<std::pair<int,int>>{{0,-1},{0,1},{-1,0},{1,0}}) {
                int nx = cx + dx, ny = cy + dy;
                if (nx >= 0 && nx < w && ny >= 0 && ny < h) orth_neighbors[idx].push_back(ny * w + nx);
            }
            Mask amask;
            for (int ay = std::max(0, cy - 2); ay < std::min(h, cy + 3); ++ay)
                for (int ax = std::max(0, cx - 2); ax < std::min(w, cx + 3); ++ax)
                    if (ax != cx || ay != cy) amask.set(ay * w + ax);
            aura5x5_mask[idx] = amask;
        }
        for (int x = 0; x < w; ++x)
            for (int y = 0; y < h; ++y) col_major_indices.push_back(y * w + x);

        for (int y = 0; y < h; ++y) {
            for (int x = 0; x < w; ++x) {
                char ch = rows[y][x];
                int idx = y * w + x;
                int idx_bit = idx;
                if (ch == '.') continue;
                if (ch == 'G') goals_mask.set(idx);
                else if (ch == '{') ysw_mask.set(idx);
                else if (ch == '}') psw_mask.set(idx);
                else {
                    int code = char_to_obj(ch);
                    if (code < 0) throw std::runtime_error("unknown tile");
                    cells[idx] = code;
                    if (code == YDOOR) ydoor_init_mask.set(idx);
                    else if (code == PDOOR) pdoor_init_mask.set(idx);
                }
            }
        }
        if (part == 3) apply_late_phase();
    }

    bool is_hero(int c) const { return c >= ACT_F && c <= INA_6; }
    bool is_monster(int c) const {
        if (part == 1) return false;
        if (part == 2) return c == GOBLIN || c == DRAG_L || c == DRAG_R;
        return c == GOBLIN;
    }
    bool is_moveable(int c) const { return c == CRATE || (c >= INA_1 && c <= INA_6) || is_monster(c); }
    bool is_static(int c) const { return c == WALL || c == YDOOR || c == PDOOR || c == MGATE; }
    bool is_weighing(int c) const {
        if (part == 3 && c == WALL) return true;
        return c == CRATE || is_hero(c) || is_monster(c);
    }

    void recompute_notes() {
        notes_mask.reset();
        if (part != 3) return;
        int bard = -1;
        for (int i = 0; i < n; ++i)
            if (cells[i] == ACT_B) { bard = i; break; }
        if (bard < 0) return;
        const Mask& cand = aura5x5_mask[bard];
        Mask m;
        for (int i = 0; i < n; ++i)
            if (cand.test(i) && is_moveable(cells[i])) m.set(i);
        notes_mask = m;
    }

    bool apply_late_phase() {
        if (part == 3) recompute_notes();
        Mask dying_mask;
        if (part == 2) {
            for (int y = 0; y < h; ++y) {
                int base = y * w;
                for (int x = 0; x < w; ++x) {
                    int c = cells[base + x];
                    if (c == DRAG_R) {
                        for (int nx = x + 1; nx < w; ++nx) {
                            int tc = cells[base + nx];
                            if (tc == EMPTY) continue;
                            if (is_hero(tc) || is_monster(tc)) dying_mask.set(base + nx);
                            break;
                        }
                    } else if (c == DRAG_L) {
                        for (int nx = x - 1; nx >= 0; --nx) {
                            int tc = cells[base + nx];
                            if (tc == EMPTY) continue;
                            if (is_hero(tc) || is_monster(tc)) dying_mask.set(base + nx);
                            break;
                        }
                    }
                }
            }
        }
        bool hero_died = false;
        if (part >= 2) {
            for (int idx = 0; idx < n; ++idx)
                if (cells[idx] == GOBLIN)
                    for (int nb : orth_neighbors[idx]) {
                        int tc = cells[nb];
                        if (is_hero(tc) || is_monster(tc)) dying_mask.set(nb);
                    }
            if (dying_mask.any()) {
                Mask shield;
                for (int idx = 0; idx < n; ++idx) {
                    if (cells[idx] == ACT_P || cells[idx] == INA_1 + 3) {
                        shield.set(idx);
                        for (int nb : orth_neighbors[idx])
                            if (is_hero(cells[nb])) shield.set(nb);
                    }
                }
                dying_mask &= ~shield;
                for (int idx = 0; idx < n; ++idx) {
                    if (dying_mask.test(idx)) {
                        int tc = cells[idx];
                        if (is_monster(tc)) cells[idx] = EMPTY;
                        else if (is_hero(tc)) hero_died = true;
                    }
                }
            }
        }
        if (ysw_mask.any()) {
            bool all_w = true, any_w = false;
            for (int idx = 0; idx < n; ++idx)
                if (ysw_mask.test(idx)) {
                    if (is_weighing(cells[idx])) any_w = true;
                    else all_w = false;
                }
            if (any_w && all_w) {
                if (ydoor_init_mask.any()) {
                    y_open = 1;
                    for (int idx = 0; idx < n; ++idx)
                        if (ydoor_init_mask.test(idx) && cells[idx] == YDOOR) cells[idx] = EMPTY;
                }
            } else if (!all_w && y_open) {
                y_open = 0;
                for (int idx = 0; idx < n; ++idx)
                    if (ydoor_init_mask.test(idx)) {
                        if (is_hero(cells[idx])) hero_died = true;
                        cells[idx] = YDOOR;
                    }
            }
        }
        if (psw_mask.any()) {
            bool all_w = true, any_w = false;
            for (int idx = 0; idx < n; ++idx)
                if (psw_mask.test(idx)) {
                    if (is_weighing(cells[idx])) any_w = true;
                    else all_w = false;
                }
            if (any_w && all_w) {
                if (pdoor_init_mask.any()) {
                    p_open = 1;
                    for (int idx = 0; idx < n; ++idx)
                        if (pdoor_init_mask.test(idx) && cells[idx] == PDOOR) cells[idx] = EMPTY;
                }
            } else if (!all_w && p_open) {
                p_open = 0;
                for (int idx = 0; idx < n; ++idx)
                    if (pdoor_init_mask.test(idx)) {
                        if (is_hero(cells[idx])) hero_died = true;
                        cells[idx] = PDOOR;
                    }
            }
        }
        // Colored doors may crush the final monster on this same turn.
        if (part >= 2 && std::none_of(cells.begin(), cells.end(), [&](int c) { return is_monster(c); }))
            for (int& c : cells) if (c == MGATE) c = EMPTY;
        if (part == 3 && notes_mask.any()) {
            Mask clean;
            for (int idx = 0; idx < n; ++idx)
                if (notes_mask.test(idx) && is_moveable(cells[idx])) clean.set(idx);
            notes_mask = clean;
        }
        return hero_died;
    }

    bool is_winning() const {
        Mask hero_mask;
        for (int idx = 0; idx < n; ++idx)
            if (is_hero(cells[idx])) hero_mask.set(idx);
        return hero_mask == goals_mask;
    }

    std::string render_ascii() const {
        std::string out;
        for (int y = 0; y < h; ++y) {
            if (y) out += '\n';
            for (int x = 0; x < w; ++x) {
                int idx = y * w + x;
                int c = cells[idx];
                if (c != EMPTY) out += obj_to_char(c);
                else if (goals_mask.test(idx)) out += 'G';
                else if (ysw_mask.test(idx)) out += '{';
                else if (psw_mask.test(idx)) out += '}';
                else out += '.';
            }
        }
        return out;
    }

    uint64_t fold_digest(uint64_t acc) const {
        int y_eff = (ydoor_init_mask.any() && y_open) ? 1 : 0;
        int p_eff = (pdoor_init_mask.any() && p_open) ? 1 : 0;
        uint64_t h = acc;
        for (int idx = 0; idx < n; ++idx) {
            int code = cells[idx];
            int nbit = notes_mask.test(idx) ? 1 : 0;
            int bval = (code & 0x1F) | (nbit << 5);
            h = ((h ^ (uint64_t)bval) * FNV64_PRIME) & MASK64;
        }
        int door_flags = (y_eff & 1) | ((p_eff & 1) << 1);
        h = ((h ^ (uint64_t)door_flags) * FNV64_PRIME) & MASK64;
        h = ((h ^ 0xFFULL) * FNV64_PRIME) & MASK64;
        return h;
    }

    std::pair<bool, bool> multi_step(char key) {
        auto before = cells;
        auto old_notes = notes_mask;
        int old_y = y_open, old_p = p_open;
        std::vector<int> players;
        for (int i = 0; i < n; ++i) if (cells[i] >= ACT_F && cells[i] <= ACT_D) players.push_back(i);
        auto cancel = [&]() {
            cells = before; notes_mask = old_notes; y_open = old_y; p_open = old_p;
            return std::make_pair(true, is_winning());
        };
        if (key == 'A') {
            Mask pending;
            for (int i : players) pending.set(i);
            for (int distance = 1; distance < max_slot; ++distance) {
                for (int code = 1; code <= max_slot; ++code) {
                    for (int src : players) {
                        if (!pending.test(src) || before[src] != code) continue;
                        int target = (code - 1 + distance) % max_slot + 1;
                        int dst = -1;
                        for (int at : col_major_indices) if (cells[at] == target + 6) { dst = at; break; }
                        if (dst >= 0) { cells[src] = code + 6; cells[dst] = target; pending.reset(src); }
                    }
                }
            }
            if (part == 2) for (int src : players) if (cells[src] >= ACT_F && cells[src] <= ACT_D) return cancel();
            bool died = apply_late_phase();
            return {!died, is_winning()};
        }
        int dx = key == 'R' ? 1 : key == 'L' ? -1 : 0;
        int dy = key == 'D' ? 1 : key == 'U' ? -1 : 0;
        std::vector<int> adjacent(n, -1);
        for (int i = 0; i < n; ++i) {
            int x = i % w + dx, y = i / w + dy;
            if (x >= 0 && x < w && y >= 0 && y < h) adjacent[i] = y * w + x;
        }
        Mask moving;
        for (int i : players) moving.set(i);
        for (int src : players) {
            if (before[src] == ACT_F) {
                int at = adjacent[src];
                while (at >= 0 && is_moveable(cells[at])) { moving.set(at); at = adjacent[at]; }
            }
            if (before[src] == ACT_T) {
                int x = src % w - dx, y = src / w - dy;
                if (x >= 0 && x < w && y >= 0 && y < h && is_moveable(cells[y * w + x])) moving.set(y * w + x);
            }
        }
        for (int src : players) {
            if (before[src] != ACT_W) continue;
            moving.reset(src);
            int at = adjacent[src];
            while (at >= 0) {
                if (is_static(cells[at])) { moving.set(src); break; }
                if (is_moveable(cells[at])) { cells[src] = cells[at]; cells[at] = ACT_W; break; }
                at = adjacent[at];
            }
            if (at < 0 && part == 3) moving.set(src);
        }
        for (int src : players) {
            if (before[src] != ACT_D || cells[src] != ACT_D) continue;
            int at = adjacent[src];
            if (at < 0 || cells[at] == EMPTY) continue;
            moving.reset(src);
            int obj = cells[at];
            if (obj == CRATE || obj == GOBLIN || obj == WALL) {
                cells[at] = obj == WALL ? CRATE : WALL;
            } else if (is_hero(obj) && obj != ACT_P && obj != INA_1 + 3) {
                bool shielded = false;
                for (int nb : orth_neighbors[at]) if (cells[nb] == ACT_P || cells[nb] == INA_1 + 3) shielded = true;
                if (!shielded) cells[at] = WALL;
            }
        }
        Mask bards;
        for (int src : players) if (before[src] == ACT_B && cells[src] == ACT_B) bards.set(src);
        if (bards.any()) {
            Mask pending = bards;
            for (int i = 0; i < n; ++i) if (notes_mask.test(i) && is_moveable(cells[i])) pending.set(i);
            moving &= ~bards;
            bool progress = true;
            while (progress) {
                progress = false;
                for (int at = 0; at < n; ++at) {
                    if (pending.test(at) && adjacent[at] >= 0 && cells[adjacent[at]] <= ACT_D && cells[adjacent[at]] != ACT_B) {
                        cells[adjacent[at]] = cells[at]; cells[at] = EMPTY;
                        pending.reset(at); progress = true;
                    }
                }
            }
            if ((pending & bards).any()) return cancel();
        }
        notes_mask.reset();
        bool progress = true;
        while (progress) {
            progress = false;
            for (int at = 0; at < n; ++at) {
                if (moving.test(at) && adjacent[at] >= 0 && cells[adjacent[at]] == EMPTY) {
                    cells[adjacent[at]] = cells[at]; cells[at] = EMPTY;
                    moving.reset(at); progress = true;
                }
            }
        }
        if (part == 2) for (int src : players) if (cells[src] >= ACT_F && cells[src] <= ACT_D) return cancel();
        bool died = apply_late_phase();
        return {!died, is_winning()};
    }

    std::pair<bool, bool> step(char key) {
        static const int DX[4] = {0, 0, -1, 1};
        static const int DY[4] = {-1, 1, 0, 0};
        int dix = -1;
        if (key == 'U') dix = 0;
        else if (key == 'D') dix = 1;
        else if (key == 'L') dix = 2;
        else if (key == 'R') dix = 3;
        else if (key == 'A') dix = 4;
        else return {false, false};

        int active_count = 0;
        for (int c : cells) if (c >= ACT_F && c <= ACT_D) ++active_count;
        if (active_count > 1) return multi_step(key);
        int act_idx = -1, act_code = EMPTY;
        for (int i = 0; i < n; ++i)
            if (cells[i] >= ACT_F && cells[i] <= ACT_D) { act_idx = i; act_code = cells[i]; break; }
        if (act_idx < 0) return {false, false};

        auto snap_cells = cells;
        auto snap_notes = notes_mask;
        int snap_yo = y_open, snap_po = p_open;

        if (dix == 4) {
            notes_mask.reset();
            bool switched = false;
            for (int off = 1; off < max_slot; ++off) {
                int target_act = ((act_code - 1 + off) % max_slot) + 1;
                int target_ina = target_act + 6;
                int found = -1;
                for (int scan_i : col_major_indices)
                    if (cells[scan_i] == target_ina) { found = scan_i; break; }
                if (found >= 0) {
                    cells[act_idx] = act_code + 6;
                    cells[found] = target_act;
                    switched = true;
                    break;
                }
            }
            if (!switched && part <= 2) return {true, is_winning()};
            bool died = apply_late_phase();
            return {!died, is_winning()};
        }

        int dx = DX[dix], dy = DY[dix];
        int ax = act_idx % w, ay = act_idx / w;
        int nx = ax + dx, ny = ay + dy;
        bool in_bounds = nx >= 0 && nx < w && ny >= 0 && ny < h;
        int nidx = in_bounds ? ny * w + nx : -1;
        bool moved = false;

        if (act_code == ACT_F) {
            notes_mask.reset();
            if (in_bounds) {
                int cx = nx, cy = ny;
                while (cx >= 0 && cx < w && cy >= 0 && cy < h && is_moveable(cells[cy * w + cx])) {
                    cx += dx; cy += dy;
                }
                if (cx >= 0 && cx < w && cy >= 0 && cy < h && cells[cy * w + cx] == EMPTY) {
                    while (cx != ax || cy != ay) {
                        int px = cx - dx, py = cy - dy;
                        cells[cy * w + cx] = cells[py * w + px];
                        cx = px; cy = py;
                    }
                    cells[act_idx] = EMPTY;
                    moved = true;
                }
            }
        } else if (act_code == ACT_T) {
            notes_mask.reset();
            if (in_bounds && cells[nidx] == EMPTY) {
                int bx = ax - dx, by = ay - dy;
                cells[nidx] = ACT_T;
                if (bx >= 0 && bx < w && by >= 0 && by < h && is_moveable(cells[by * w + bx])) {
                    cells[act_idx] = cells[by * w + bx];
                    cells[by * w + bx] = EMPTY;
                } else cells[act_idx] = EMPTY;
                moved = true;
            }
        } else if (act_code == ACT_W) {
            notes_mask.reset();
            int rx = ax, ry = ay;
            while (true) {
                int tx = rx + dx, ty = ry + dy;
                if (!(tx >= 0 && tx < w && ty >= 0 && ty < h)) {
                    if (part == 3 && in_bounds && cells[nidx] == EMPTY) {
                        cells[nidx] = ACT_W; cells[act_idx] = EMPTY; moved = true;
                    }
                    break;
                }
                int ti = ty * w + tx;
                int tc = cells[ti];
                if (tc == EMPTY) { rx = tx; ry = ty; }
                else if (is_static(tc)) {
                    if (in_bounds && cells[nidx] == EMPTY) {
                        cells[nidx] = ACT_W; cells[act_idx] = EMPTY; moved = true;
                    }
                    break;
                } else if (is_moveable(tc)) {
                    cells[ti] = ACT_W; cells[act_idx] = tc; moved = true; break;
                } else break;
            }
        } else if (act_code == ACT_P) {
            notes_mask.reset();
            if (in_bounds && cells[nidx] == EMPTY) {
                cells[nidx] = ACT_P; cells[act_idx] = EMPTY; moved = true;
            }
        } else if (act_code == ACT_D) {
            notes_mask.reset();
            if (in_bounds) {
                int tc = cells[nidx];
                if (tc == EMPTY) { cells[nidx] = ACT_D; cells[act_idx] = EMPTY; moved = true; }
                else if (tc == CRATE || tc == GOBLIN) { cells[nidx] = WALL; moved = true; }
                else if (tc == WALL) { cells[nidx] = CRATE; moved = true; }
                else if (tc == ACT_P || tc == INA_1 + 3) moved = true;
                else if (is_hero(tc)) {
                    bool shielded = false;
                    for (int nb : orth_neighbors[nidx])
                        if (cells[nb] == ACT_P || cells[nb] == INA_1 + 3) { shielded = true; break; }
                    if (!shielded) cells[nidx] = WALL;
                    moved = true;
                }
            }
        } else if (act_code == ACT_B) {
            int b_idx = act_idx;
            bool bard_stepped = false;
            std::vector<int> pending;
            for (int i = 0; i < n; ++i) if (notes_mask.test(i)) pending.push_back(i);
            std::vector<bool> still(pending.size(), true);
            bool progressed = true;
            while (progressed) {
                progressed = false;
                for (size_t ki = 0; ki < pending.size(); ++ki) {
                    if (!still[ki]) continue;
                    int p_idx = pending[ki];
                    int px = (p_idx % w) + dx, py = (p_idx / w) + dy;
                    if (px >= 0 && px < w && py >= 0 && py < h) {
                        int t_idx = py * w + px;
                        if (cells[t_idx] == EMPTY) {
                            cells[t_idx] = cells[p_idx];
                            cells[p_idx] = EMPTY;
                            still[ki] = false;
                            progressed = true;
                        }
                    }
                }
                if (!bard_stepped) {
                    int bx2 = (b_idx % w) + dx, by2 = (b_idx / w) + dy;
                    if (bx2 >= 0 && bx2 < w && by2 >= 0 && by2 < h) {
                        int bt = by2 * w + bx2;
                        if (cells[bt] == EMPTY) {
                            cells[bt] = ACT_B; cells[b_idx] = EMPTY;
                            b_idx = bt; bard_stepped = true; progressed = true;
                        }
                    }
                }
            }
            if (!bard_stepped) {
                cells = snap_cells; notes_mask = snap_notes; y_open = snap_yo; p_open = snap_po;
                return {true, is_winning()};
            }
            notes_mask.reset();
            moved = true;
        }

        if (part <= 2 && !moved) {
            cells = snap_cells; notes_mask = snap_notes; y_open = snap_yo; p_open = snap_po;
            return {true, is_winning()};
        }
        bool died = apply_late_phase();
        return {!died, is_winning()};
    }
};

static std::string state_key(const Engine& e) {
    std::string k;
    k.reserve(e.n + 16);
    for (int c : e.cells) k.push_back((char)c);
    k.push_back((char)e.y_open);
    k.push_back((char)e.p_open);
    for (int i = 0; i < (e.n + 7) / 8; ++i) {
        unsigned char byte = 0;
        for (int b = 0; b < 8; ++b) {
            int idx = i * 8 + b;
            if (idx < e.n && e.notes_mask.test(idx)) byte |= (unsigned char)(1u << b);
        }
        k.push_back((char)byte);
    }
    return k;
}

static std::string json_escape(const std::string& s) {
    std::string o;
    for (char c : s) {
        if (c == '\\') o += "\\\\";
        else if (c == '"') o += "\\\"";
        else if (c == '\n') o += "\\n";
        else o += c;
    }
    return o;
}

// Search keeps only dynamic-state bytes and parent links. Static room geometry
// is reconstructed from the root, rather than copied into every queued node.
static void restore_state(Engine& e, const std::string& key) {
    size_t pos = 0;
    for (int& c : e.cells) c = (unsigned char)key[pos++];
    e.y_open = (unsigned char)key[pos++];
    e.p_open = (unsigned char)key[pos++];
    e.notes_mask.reset();
    for (int i = 0; i < (e.n + 7) / 8; ++i) {
        unsigned char byte = (unsigned char)key[pos++];
        for (int b = 0; b < 8 && i * 8 + b < e.n; ++b)
            if (byte & (1u << b)) e.notes_mask.set(i * 8 + b);
    }
}

struct SearchResult {
    bool solved = false;
    std::string route;
    // All states at these depths have been checked for the goal. Expanding a
    // subset of the next layer never increases this value.
    int completed_depth = -1;
    int nodes = 0, transitions = 0, duplicates = 0;
    size_t states_seen = 0;
    std::string reason = "time_limit";
};

static SearchResult bounded_bfs(const Engine& root, int max_depth, int state_limit, int budget_sec) {
    SearchResult out;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(budget_sec);
    if (budget_sec <= 0) return out;
    struct Node { std::string key; size_t parent; char move; };
    std::vector<Node> nodes;
    std::unordered_set<std::string> seen;
    state_limit = std::clamp(state_limit > 0 ? state_limit : 100000, 1, 200000);
    nodes.push_back({state_key(root), 0, 0});
    seen.insert(nodes.front().key);
    out.states_seen = 1;
    if (root.is_winning()) {
        out.solved = true;
        out.reason = "solution";
        return out;
    }
    size_t begin = 0, end = 1;
    for (int depth = 0; ; ++depth) {
        // Every node in this layer was goal-tested on insertion, including
        // all duplicates. This certifies only depths already fully generated.
        out.completed_depth = depth;
        if (depth >= max_depth) { out.reason = "depth_limit"; return out; }
        for (size_t index = begin; index < end; ++index) {
            if (std::chrono::steady_clock::now() >= deadline) return out;
            Engine current = root;
            restore_state(current, nodes[index].key);
            ++out.nodes;
            for (char move : std::string("UDLRA")) {
                if (std::chrono::steady_clock::now() >= deadline) return out;
                Engine next = current;
                auto [alive, won] = next.step(move);
                ++out.transitions;
                if (!alive) continue;
                if (won) {
                    std::string path(1, move);
                    for (size_t parent = index; parent != 0; parent = nodes[parent].parent)
                        path.push_back(nodes[parent].move);
                    std::reverse(path.begin(), path.end());
                    out.route = path;
                    out.solved = true;
                    out.reason = "solution";
                    return out;
                }
                std::string key = state_key(next);
                if (seen.count(key)) { ++out.duplicates; continue; }
                if (nodes.size() >= (size_t)state_limit) {
                    out.reason = "state_limit";
                    return out;
                }
                seen.insert(key);
                nodes.push_back({std::move(key), index, move});
                out.states_seen = nodes.size();
            }
        }
        if (end == nodes.size()) {
            // No new states: the entire reachable graph has been exhausted.
            out.completed_depth = max_depth;
            out.reason = "exhausted";
            return out;
        }
        begin = end;
        end = nodes.size();
    }
}

static void print_search_metadata(const SearchResult& out) {
    std::cout << ",\"search_algorithm\":\"exact_bfs\""
              << ",\"termination_reason\":\"" << out.reason << "\""
              << ",\"completed_depth\":" << out.completed_depth
              << ",\"timed_out\":" << (out.reason == "time_limit" ? "true" : "false")
              << ",\"state_limit_reached\":" << (out.reason == "state_limit" ? "true" : "false")
              << ",\"states_seen\":" << out.states_seen
              << ",\"nodes_expanded\":" << out.nodes
              << ",\"transitions_checked\":" << out.transitions
              << ",\"duplicates_pruned\":" << out.duplicates;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::string line;
    if (!std::getline(std::cin, line)) return 1;
    std::istringstream hdr(line);
    std::string mode;
    int part, w, h, p1, p2, p3;
    if (!(hdr >> mode >> part >> w >> h >> p1 >> p2 >> p3)
        || part < 1 || part > 3 || w <= 0 || h <= 0 || w > 512 || h > 512
        || (long long)w * h > 512 || p1 < 0 || p2 < 0 || p3 < 0) {
        std::cerr << "invalid header or dimensions" << std::endl;
        return 2;
    }
    std::vector<std::string> grid;
    for (int y = 0; y < h; ++y) {
        if (!std::getline(std::cin, line)) return 1;
        if ((int)line.size() != w) return 2;
        grid.push_back(line);
    }
    std::string route = "-";
    if (!std::getline(std::cin, line)) return 1;
    if (!line.empty()) route = line;

    try {
        if (mode == "verify") {
            Engine eng(part, grid);
            uint64_t digest = eng.fold_digest(FNV64_OFFSET);
            bool alive = true, prem = false;
            int steps = 0;
            for (size_t i = 0; i < route.size(); ++i) {
                char ch = route[i];
                if (ch == '-') continue;
                auto [ok, won] = eng.step(ch);
                ++steps;
                if (!ok) { alive = false; break; }
                digest = eng.fold_digest(digest);
                if (won && i + 1 < route.size()) { prem = true; break; }
            }
            bool exact = alive && !prem && eng.is_winning();
            char hx[17];
            std::snprintf(hx, sizeof(hx), "%016llx", (unsigned long long)digest);
            std::string ascii = json_escape(eng.render_ascii());
            std::cout << "{\"alive\":" << (alive ? "true" : "false")
                      << ",\"exact_win\":" << (exact ? "true" : "false")
                      << ",\"premature_win\":" << (prem ? "true" : "false")
                      << ",\"steps_executed\":" << steps
                      << ",\"traj_fnv64\":\"" << hx << "\""
                      << ",\"final_ascii\":\"" << ascii << "\"}" << std::endl;
            return 0;
        }
        if (mode == "solve" || mode == "optimize" || mode == "prove_lb") {
            Engine eng(part, grid);
            int max_depth = mode == "optimize" ? std::max(0, (int)route.size() - 1) : p1;
            // Optimizer p1 and solver p2 are state caps (formerly beam_width).
            int state_limit = mode == "optimize" ? p1 : p2;
            auto result = bounded_bfs(eng, max_depth, state_limit, p3);
            if (mode == "solve") {
                std::cout << "{\"solved\":" << (result.solved ? "true" : "false")
                          << ",\"route\":\"" << result.route << "\""
                          << ",\"explored\":" << result.nodes;
            } else if (mode == "optimize") {
                std::cout << "{\"best_route\":\"" << (result.solved ? result.route : route)
                          << "\",\"stages\":[\"bounded_exact_bfs\"]";
            } else {
                int floor = result.solved ? (int)result.route.size() : result.completed_depth + 1;
                std::cout << "{\"epistemic_status\":\""
                          << (result.solved ? "VERIFIED" : "EXHAUSTIVE_LOWER_BOUND") << "\""
                          << ",\"proven_floor\":" << floor
                          << ",\"exact_optimum_reached\":" << (result.solved ? "true" : "false")
                          << ",\"winning_witness\":\"" << result.route << "\""
                          << ",\"exact_state_tt\":true,\"quotient_pdb_enabled\":false"
                          << ",\"exact_tt_prunes\":" << result.duplicates
                          << ",\"hash_collisions_prevented\":0,\"edge_consistency_checks\":0";
            }
            print_search_metadata(result);
            std::cout << "}" << std::endl;
            return 0;
        }

    } catch (const std::exception& ex) {
        std::cerr << ex.what() << std::endl;
        return 2;
    }
    std::cerr << "unknown mode" << std::endl;
    return 2;
}
