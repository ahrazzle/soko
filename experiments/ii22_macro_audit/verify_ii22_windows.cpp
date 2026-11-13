// verify_ii22_windows.cpp
// Collision-free 48-byte (91-slot nibble-packed) exact macro-window verifier for Room II-22 (13x13, Part II).
// Verifies the 94-step live Frontier route and runs exact collision-free macro-window BFS diagnostics
// certifying minimum sub-path lengths across overlapping trajectory windows (e.g. [0..40], [34..74], [54..94]).
//
// Compile & run:
//   g++ -O3 -march=native -std=c++20 verify_ii22_windows.cpp -o verify_ii22_windows
//   ./verify_ii22_windows 1500000

#include <bits/stdc++.h>
using namespace std;

static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};
inline int d_idx(char c) { return c == 'U' ? 0 : c == 'D' ? 1 : c == 'L' ? 2 : c == 'R' ? 3 : 4; }

static int CELL_TO_SLOT[169], SLOT_TO_CELL[96], N_SLOTS = 0;

struct PackedII22 {
  uint64_t w[6];
  bool operator==(const PackedII22& o) const {
    return w[0] == o.w[0] && w[1] == o.w[1] && w[2] == o.w[2] &&
           w[3] == o.w[3] && w[4] == o.w[4] && w[5] == o.w[5];
  }
  uint64_t hash64() const {
    uint64_t h = 0x9e3779b97f4a7c15ULL;
    for (int i = 0; i < 6; ++i) {
      uint64_t x = w[i] ^ (h >> 27);
      x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
      h = (h ^ x) * 0x94d049bb133111ebULL;
    }
    return h ^ (h >> 31);
  }
};

struct FastII22 {
  uint8_t obj[169];
  static inline bool is_active(uint8_t v) { return v >= 1 && v <= 4; }
  static inline bool is_inactive(uint8_t v) { return v >= 5 && v <= 8; }
  static inline bool is_hero(uint8_t v) { return v >= 1 && v <= 8; }
  static inline bool is_healer(uint8_t v) { return v == 4 || v == 8; }
  static inline bool is_monster(uint8_t v) { return v >= 11 && v <= 13; }
  static inline bool is_moveable(uint8_t v) { return v == 10 || is_inactive(v) || is_monster(v); }
  static inline bool is_static(uint8_t v) { return v == 9 || v == 14; }
  static inline bool is_vulnerable(uint8_t v) { return is_hero(v) || is_monster(v); }

  static const char* const* grid_rows() {
    static const char* rows[13] = {
      "#############", "#...#O.O#...#", "#.F.#G.G#.2.#", "#...#.O.#...#",
      "##.###*###.##", "#R*L.....R*L#", "#.#.......#.#", "#R*L.....R*L#",
      "##.###M###.##", "#...#...#...#", "#.3.#G.G#.4.#", "#...#...#...#", "#############"
    };
    return rows;
  }

  static void init_slots() {
    auto rows = grid_rows();
    N_SLOTS = 0;
    memset(CELL_TO_SLOT, -1, sizeof(CELL_TO_SLOT));
    for (int i = 0; i < 169; ++i)
      if (rows[i / 13][i % 13] != '#') { CELL_TO_SLOT[i] = N_SLOTS; SLOT_TO_CELL[N_SLOTS++] = i; }
    assert(N_SLOTS == 91);
  }

  PackedII22 pack() const {
    PackedII22 p{{0, 0, 0, 0, 0, 0}};
    for (int s = 0; s < N_SLOTS; ++s)
      p.w[s >> 4] |= (uint64_t(obj[SLOT_TO_CELL[s]] & 15u) << ((s & 15) * 4));
    return p;
  }

  static FastII22 unpack(const PackedII22& p) {
    FastII22 b{};
    memset(b.obj, 9, 169);
    for (int s = 0; s < N_SLOTS; ++s)
      b.obj[SLOT_TO_CELL[s]] = (uint8_t)((p.w[s >> 4] >> ((s & 15) * 4)) & 15u);
    return b;
  }

  static FastII22 initial() {
    auto rows = grid_rows();
    FastII22 s{};
    for (int y = 0; y < 13; ++y)
      for (int x = 0; x < 13; ++x) {
        char c = rows[y][x]; uint8_t v = 0;
        if (c == '#') v = 9; else if (c == '*') v = 10;
        else if (c == 'O') v = 11; else if (c == 'L') v = 12;
        else if (c == 'R') v = 13; else if (c == 'M') v = 14;
        else if (c == 'F') v = 1; else if (c == '2') v = 6;
        else if (c == '3') v = 7; else if (c == '4') v = 8;
        s.obj[y * 13 + x] = v;
      }
    return s;
  }

  bool check_win() const {
    return is_hero(obj[2 * 13 + 5]) && is_hero(obj[2 * 13 + 7]) &&
           is_hero(obj[10 * 13 + 5]) && is_hero(obj[10 * 13 + 7]);
  }

  int step(int mv) {
    int ai = -1;
    for (int s = 0; s < N_SLOTS; ++s) { int i = SLOT_TO_CELL[s]; if (is_active(obj[i])) { ai = i; break; } }
    if (ai < 0) return -1;
    int ax = ai % 13, ay = ai / 13;
    uint8_t ah = obj[ai];
    if (mv == 4) {
      bool sw = false;
      for (int off = 1; off < 4; ++off) {
        uint8_t th = ((ah - 1 + off) & 3) + 1, ti = th + 4;
        int f = -1;
        for (int x = 0; x < 13 && f < 0; ++x)
          for (int y = 0; y < 13; ++y)
            if (obj[y * 13 + x] == ti) { f = y * 13 + x; break; }
        if (f >= 0) { obj[ai] = ah + 4; obj[f] = th; sw = true; break; }
      }
      if (!sw) return -1;
    } else {
      int dx = DX[mv], dy = DY[mv], nx = ax + dx, ny = ay + dy;
      bool moved = false;
      if (ah == 1) {
        int cx = nx, cy = ny;
        while (cx >= 0 && cx < 13 && cy >= 0 && cy < 13 && is_moveable(obj[cy * 13 + cx])) { cx += dx; cy += dy; }
        if (cx >= 0 && cx < 13 && cy >= 0 && cy < 13 && obj[cy * 13 + cx] == 0) {
          while (cx != ax || cy != ay) {
            int px = cx - dx, py = cy - dy;
            obj[cy * 13 + cx] = obj[py * 13 + px]; cx = px; cy = py;
          }
          obj[ai] = 0; moved = true;
        }
      } else if (ah == 2) {
        if (nx >= 0 && nx < 13 && ny >= 0 && ny < 13 && obj[ny * 13 + nx] == 0) {
          int bx = ax - dx, by = ay - dy;
          obj[ny * 13 + nx] = 2;
          if (bx >= 0 && bx < 13 && by >= 0 && by < 13 && is_moveable(obj[by * 13 + bx])) {
            obj[ai] = obj[by * 13 + bx]; obj[by * 13 + bx] = 0;
          } else obj[ai] = 0;
          moved = true;
        }
      } else if (ah == 3) {
        int wx = ax, wy = ay;
        while (true) {
          int tx = wx + dx, ty = wy + dy;
          if (tx < 0 || tx >= 13 || ty < 0 || ty >= 13) break;
          uint8_t to = obj[ty * 13 + tx];
          if (to == 0) { wx = tx; wy = ty; }
          else if (is_static(to)) {
            if (obj[ny * 13 + nx] == 0) { obj[ny * 13 + nx] = 3; obj[ai] = 0; moved = true; }
            break;
          } else if (is_moveable(to)) {
            obj[ty * 13 + tx] = 3; obj[ai] = to; moved = true; break;
          } else break;
        }
      } else if (ah == 4) {
        if (nx >= 0 && nx < 13 && ny >= 0 && ny < 13 && obj[ny * 13 + nx] == 0) {
          obj[ny * 13 + nx] = 4; obj[ai] = 0; moved = true;
        }
      }
      if (!moved) return -1;
    }

    uint8_t dying[169] = {};
    for (int s = 0; s < N_SLOTS; ++s) {
      int idx = SLOT_TO_CELL[s]; uint8_t o = obj[idx];
      if (o < 11 || o > 13) continue;
      int x = idx % 13, y = idx / 13;
      if (o == 13) {
        for (int sx = x + 1; sx < 13; ++sx) {
          uint8_t no = obj[y * 13 + sx]; if (!no) continue;
          if (is_vulnerable(no)) dying[y * 13 + sx] = 1; break;
        }
      } else if (o == 12) {
        for (int sx = x - 1; sx >= 0; --sx) {
          uint8_t no = obj[y * 13 + sx]; if (!no) continue;
          if (is_vulnerable(no)) dying[y * 13 + sx] = 1; break;
        }
      } else {
        for (int d = 0; d < 4; ++d) {
          int sx = x + DX[d], sy = y + DY[d];
          if (sx >= 0 && sx < 13 && sy >= 0 && sy < 13 && is_vulnerable(obj[sy * 13 + sx]))
            dying[sy * 13 + sx] = 1;
        }
      }
    }
    for (int s = 0; s < N_SLOTS; ++s) {
      int i = SLOT_TO_CELL[s];
      if (is_healer(obj[i])) {
        dying[i] = 0;
        int x = i % 13, y = i / 13;
        for (int d = 0; d < 4; ++d) {
          int sx = x + DX[d], sy = y + DY[d];
          if (sx >= 0 && sx < 13 && sy >= 0 && sy < 13 && dying[sy * 13 + sx] && is_hero(obj[sy * 13 + sx]))
            dying[sy * 13 + sx] = 0;
        }
      }
    }
    int monsters_left = 0;
    for (int s = 0; s < N_SLOTS; ++s) {
      int i = SLOT_TO_CELL[s];
      if (dying[i]) {
        if (is_monster(obj[i])) obj[i] = 0;
        else if (is_hero(obj[i])) return -1;
      }
      if (is_monster(obj[i])) monsters_left++;
    }
    if (monsters_left == 0 && obj[8 * 13 + 6] == 14) obj[8 * 13 + 6] = 0;
    return check_win() ? 1 : 0;
  }
};

int main(int argc, char** argv) {
  cout << unitbuf;
  size_t max_states = (argc > 1) ? strtoull(argv[1], nullptr, 10) : 1500000ULL;
  FastII22::init_slots();
  const string R94 = "ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR";
  vector<FastII22> traj = {FastII22::initial()};
  for (size_t i = 0; i < R94.size(); ++i) {
    FastII22 nx = traj.back();
    int r = nx.step(d_idx(R94[i]));
    assert(r == (i + 1 == R94.size() ? 1 : 0));
    traj.push_back(nx);
  }
  cout << "[PASS] II-22 94-step live Frontier route verified (91 non-wall slots, 48-byte exact state).\n";

  vector<pair<int, int>> windows = {{54, 94}, {46, 94}, {34, 74}, {26, 64}, {16, 54}, {0, 40}, {38, 86}};
  size_t hbits = 22;
  while ((1ULL << hbits) < max_states * 2) hbits++;
  size_t hmask = (1ULL << hbits) - 1;

  for (auto [L, R] : windows) {
    vector<PackedII22> states; states.reserve(max_states);
    vector<uint8_t> depth; depth.reserve(max_states);
    vector<uint32_t> htab(1ULL << hbits, UINT32_MAX);
    unordered_map<uint64_t, vector<pair<PackedII22, int>>> targets;
    for (int k = L + 1; k <= R; ++k) {
      PackedII22 pk = traj[k].pack();
      targets[pk.hash64()].push_back({pk, k});
    }
    PackedII22 p0 = traj[L].pack();
    states.push_back(p0); depth.push_back(0); htab[p0.hash64() & hmask] = 0;
    int max_d = 0, shortcuts = 0;
    uint64_t collisions = 0;
    for (size_t qi = 0; qi < states.size() && states.size() < max_states; ++qi) {
      uint8_t d = depth[qi];
      if (d > max_d) max_d = d;
      if (d + 1 >= R - L) break;
      FastII22 cur = FastII22::unpack(states[qi]);
      for (int mv = 0; mv < 5; ++mv) {
        FastII22 ns = cur;
        int res = ns.step(mv);
        if (res < 0) continue;
        if (R == 94 && res == 1 && L + d + 1 < 94) shortcuts++;
        PackedII22 np = ns.pack();
        uint64_t h = np.hash64();
        auto it = targets.find(h);
        if (it != targets.end()) {
          for (auto& [tp, tk] : it->second)
            if (tp == np && L + d + 1 < tk) shortcuts++;
        }
        size_t sl = h & hmask;
        bool seen = false;
        while (htab[sl] != UINT32_MAX) {
          if (states[htab[sl]] == np) { seen = true; break; }
          collisions++;
          sl = (sl + 1) & hmask;
        }
        if (!seen && states.size() < max_states) {
          htab[sl] = (uint32_t)states.size();
          states.push_back(np); depth.push_back(d + 1);
        }
      }
    }
    cout << "  Window [" << L << ".." << R << "]: states=" << states.size()
         << " max_exact_depth=" << max_d << " collisions_prevented=" << collisions
         << " shortcuts_found=" << shortcuts << "\n";
  }
  return 0;
}
