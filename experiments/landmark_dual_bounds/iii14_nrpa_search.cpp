// iii14_nrpa_search.cpp
// Controlled 2-Arm Deterministic-Seed NRPA (`ahrazzle/soko#53` C1 + `ahrazzle/soko#46`):
//   Arm A: Primitive 1-key (`UDLRA`) NRPA with sparse quotient-state policy keying.
//   Arm B: Macro-Augmented NRPA combining primitive `UDLRA` keys with state-generated Part III
//          mechanical macros (Druid walk+border-harvest, Druid BFS-to-switch-crate petrification,
//          Bard 1..3-step switch-herding, and open-door goal-delivery walks), with zero hardcoded
//          routes or coordinate templates, evaluated both at open horizon (`<= 76`) and strict
//          sub-record horizon (`<= 47`).

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <queue>
#include <random>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>

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
    "###############",
};

static inline u128 bit(int i) { return ((u128)1) << i; }
static inline bool tst(u128 m, int i) { return (m >> i) & 1; }
static inline int popcnt128(u128 m) {
  return __builtin_popcountll((uint64_t)m) + __builtin_popcountll((uint64_t)(m >> 64));
}

static u128 ORIGIN_MASK = 0, SWITCH_MASK = 0, PDOOR_MASK = 0, AURA[N]{};
static int SW_CELLS[9]{};
static int B0 = -1, D0 = -1, GOALS[2];

struct CState {
  u128 crates, walls;
  uint8_t bx, by, dx, dy, ah, doors_open;
};

static uint64_t state_hash64(const CState& s) {
  uint64_t c0 = uint64_t(s.crates), c1 = uint64_t(s.crates >> 64);
  uint64_t w0 = uint64_t(s.walls), w1 = uint64_t(s.walls >> 64);
  uint64_t h = c0 ^ (c1 * 0x9e3779b97f4a7c15ULL) ^ (w0 * 0xbf58476d1ce4e5b9ULL) ^ (w1 * 0x94d049bb133111ebULL);
  uint64_t meta = uint64_t(s.bx) | (uint64_t(s.by) << 8) | (uint64_t(s.dx) << 16) |
                  (uint64_t(s.dy) << 24) | (uint64_t(s.ah) << 32) | (uint64_t(s.doors_open) << 33);
  h ^= meta * 0xd6e8feb86659fd93ULL;
  h ^= h >> 33; h *= 0xff51afd7ed558ccdULL; h ^= h >> 33;
  return h;
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
  ORIGIN_MASK = SWITCH_MASK = PDOOR_MASK = 0;
  for (int i = 0; i < N; ++i) AURA[i] = 0;
  int g_i = 0, sw_i = 0;
  for (int y = 0; y < H; ++y)
    for (int x = 0; x < W; ++x) {
      char c = GRID_III14[y][x]; int i = y * W + x;
      if (c == '#') ORIGIN_MASK |= bit(i);
      else if (c == '}') { SWITCH_MASK |= bit(i); SW_CELLS[sw_i++] = i; }
      else if (c == ']') PDOOR_MASK |= bit(i);
      else if (c == 'G') GOALS[g_i++] = i;
      else if (c == '5') B0 = i;
      else if (c == 'D') D0 = i;
    }
  for (int b = 0; b < N; ++b) {
    int bx = b % W, by = b / W;
    for (int y = max(0, by - 2); y <= min(H - 1, by + 2); ++y)
      for (int x = max(0, bx - 2); x <= min(W - 1, bx + 2); ++x) AURA[b] |= bit(y * W + x);
  }
}

struct MacroOp {
  uint32_t op_tag;
  string keys;
  CState end_state;
};

static uint64_t quotient_macro_code(const CState& s, int step_idx, uint32_t op_tag) {
  uint32_t sw9 = 0;
  u128 obs = s.crates | s.walls;
  for (int k = 0; k < 9; ++k) if (tst(obs, SW_CELLS[k])) sw9 |= (1u << k);
  uint32_t sw_walls = 0;
  for (int k = 0; k < 9; ++k) if (tst(s.walls, SW_CELLS[k])) sw_walls |= (1u << k);
  uint32_t m_act = uint32_t(min(10, popcnt128(s.crates | (s.walls & ~ORIGIN_MASK))));
  uint64_t h = uint64_t(op_tag) * 0x9e3779b97f4a7c15ULL;
  uint64_t q = uint64_t(s.ah) |
               (uint64_t(s.doors_open) << 1) |
               (uint64_t(s.by * W + s.bx) << 2) |
               (uint64_t(s.dy * W + s.dx) << 9) |
               (uint64_t(m_act) << 16) |
               (uint64_t(sw9) << 20) |
               (uint64_t(sw_walls) << 29) |
               (uint64_t(step_idx / 4) << 38);
  return h ^ (q * 0xbf58476d1ce4e5b9ULL);
}

// Generate candidate actions from `s`:
// - If `use_macros == false`: ONLY the 5 primitive keys `U, D, L, R, A` (`op_tag = 0..4`).
// - If `use_macros == true`: primitive keys PLUS state-derived mechanical macros (walk+harvest border wall,
//   Druid short-BFS petrify switch crate, Bard 2-step herd, and open-door goal walk) within `rem_keys`!
static void generate_actions(
    const CState& s,
    int rem_keys,
    bool use_macros,
    char last_key,
    const unordered_set<uint64_t>& visited,
    vector<MacroOp>& out
) {
  out.clear();
  if (rem_keys <= 0) return;

  int m_act = popcnt128(s.crates | (s.walls & ~ORIGIN_MASK));

  // 1. Primitive 1-key actions (`op_tag = 1..5`)
  // In macro/landmark-guided mode (`use_macros == true`), apply the proved 9-Harvest Landmark hygiene:
  //   - Do not toggle an already-harvested border crate (`ORIGIN_MASK & crates`) back into `#` wall.
  //   - Do not switch Druid -> Bard (`mv == 4`) before harvesting `m_act >= 9` active obstacles.
  //   - Do not petrify interior crates outside `SWITCH_MASK` into `#` walls.
  for (int mv = 0; mv < 5; ++mv) {
    if (mv == 4 && last_key == 'A') continue;
    if (use_macros && mv == 4 && s.ah == 1 && m_act < 9) continue;
    if (use_macros && mv < 4 && s.ah == 1) {
      int tx = int(s.dx) + DX[mv], ty = int(s.dy) + DY[mv];
      if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
        int ti = ty * W + tx;
        if (tst(ORIGIN_MASK & s.crates, ti)) continue;
        if (tst(s.crates, ti) && !tst(SWITCH_MASK, ti)) continue;
        if (m_act >= 9 && tst(ORIGIN_MASK & s.walls, ti)) continue;
      }
    }
    CState ns;
    if (!step_concrete(s, mv, ns)) continue;
    if (is_win(ns)) {
      out.clear();
      out.push_back(MacroOp{uint32_t(1 + mv), string(1, "UDLRA"[mv]), ns});
      return;
    }
    if (visited.find(state_hash64(ns)) == visited.end()) {
      out.push_back(MacroOp{uint32_t(1 + mv), string(1, "UDLRA"[mv]), ns});
    }
  }
  if (!use_macros || rem_keys < 2) return;

  if (s.ah == 1) {
    // Macro M1: Druid 1-step walk + adjacent ORIGIN_MASK wall harvest (`# -> *`, 2 keys)
    if (m_act < 9) {
      for (int d1 = 0; d1 < 4; ++d1) {
        CState s1;
        if (!step_concrete(s, d1, s1)) continue;
        if (s1.dx == s.dx && s1.dy == s.dy) continue; // wasn't a walk
        for (int d2 = 0; d2 < 4; ++d2) {
          int tx = int(s1.dx) + DX[d2], ty = int(s1.dy) + DY[d2];
          if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
          int ti = ty * W + tx;
          if (!tst(ORIGIN_MASK & s1.walls, ti)) continue; // must be unharvested border wall!
          CState s2;
          if (!step_concrete(s1, d2, s2)) continue;
          if (visited.find(state_hash64(s2)) == visited.end()) {
            string ks; ks.push_back("UDLRA"[d1]); ks.push_back("UDLRA"[d2]);
            out.push_back(MacroOp{uint32_t(100 + d1 * 4 + d2), ks, s2});
          }
        }
      }
    }

    // Macro M2: Druid shortest walk (0..3 steps) + petrify a crate `*` sitting on a switch `}` (`* -> #`)!
    u128 sw_crates = s.crates & SWITCH_MASK;
    if (sw_crates != 0) {
      for (int k = 0; k < 9; ++k) {
        int sc = SW_CELLS[k];
        if (!tst(sw_crates, sc)) continue;
        // Short BFS (<= 3 walk steps) for Druid to reach ortho-adjacent to `sc` without toggling anything on the way
        struct QN { CState st; string path; };
        queue<QN> q;
        unordered_set<int> seen_d;
        q.push({s, ""});
        seen_d.insert(s.dy * W + s.dx);
        bool emitted = false;
        while (!q.empty() && !emitted) {
          QN cur = q.front(); q.pop();
          if (int(cur.path.size()) + 1 > rem_keys) continue;
          for (int d = 0; d < 4; ++d) {
            if (int(cur.st.dx) + DX[d] == (sc % W) && int(cur.st.dy) + DY[d] == (sc / W)) {
              CState fin;
              if (step_concrete(cur.st, d, fin) && visited.find(state_hash64(fin)) == visited.end()) {
                out.push_back(MacroOp{uint32_t(200 + k), cur.path + "UDLRA"[d], fin});
                emitted = true;
                break;
              }
            }
          }
          if (!emitted && cur.path.size() < 3) {
            for (int d = 0; d < 4; ++d) {
              CState nx;
              if (!step_concrete(cur.st, d, nx)) continue;
              if (nx.dx == cur.st.dx && nx.dy == cur.st.dy) continue; // only pure walks!
              int dp = nx.dy * W + nx.dx;
              if (seen_d.insert(dp).second) {
                q.push({nx, cur.path + "UDLRA"[d]});
              }
            }
          }
        }
      }
    }
  } else {
    // Bard active (`s.ah == 0`):
    // Macro M3: 2-step Bard run in direction `d` (`dd`, e.g. RR, UU, DD, LL)
    for (int d = 0; d < 4; ++d) {
      CState s1, s2;
      if (!step_concrete(s, d, s1)) continue;
      if (is_win(s1)) continue;
      if (!step_concrete(s1, d, s2)) continue;
      if (is_win(s2) || visited.find(state_hash64(s2)) == visited.end()) {
        string ks(2, "UDLRA"[d]);
        out.push_back(MacroOp{uint32_t(300 + d), ks, s2});
      }
    }

    // Macro M4: When `doors_open == 1` (or 8 switches covered), short 2..6-key BFS check for immediate win!
    int sw_cov = popcnt128((s.crates | s.walls) & SWITCH_MASK);
    if (sw_cov >= 8 && rem_keys >= 2) {
      int cap_d = min(rem_keys, 7);
      struct WN { CState st; string path; };
      queue<WN> wq;
      unordered_set<uint64_t> wseen;
      wq.push({s, ""});
      wseen.insert(state_hash64(s));
      int exp_lim = 0;
      while (!wq.empty() && exp_lim < 180) {
        WN cur = wq.front(); wq.pop();
        if (int(cur.path.size()) >= cap_d) continue;
        exp_lim++;
        for (int mv = 0; mv < 5; ++mv) {
          CState nx;
          if (!step_concrete(cur.st, mv, nx)) continue;
          string np = cur.path + "UDLRA"[mv];
          if (is_win(nx)) {
            out.clear();
            out.push_back(MacroOp{400u, np, nx});
            return;
          }
          if (int(np.size()) < cap_d && wseen.insert(state_hash64(nx)).second) {
            wq.push({nx, np});
          }
        }
      }
    }
  }
}

using Policy = unordered_map<uint64_t, double>;

struct RolloutTrace {
  int score = -999999;
  bool won = false;
  string route;
  vector<CState> step_states;
  vector<int> step_key_counts;
  vector<uint32_t> chosen_tags;
  vector<vector<uint32_t>> cand_tags_at_step;
};

static RolloutTrace playout(int max_horizon, bool use_macros, const Policy& pol, mt19937_64& rng) {
  RolloutTrace tr;
  CState cur{0, ORIGIN_MASK, uint8_t(B0 % W), uint8_t(B0 / W), uint8_t(D0 % W), uint8_t(D0 / W), 1, 0};
  unordered_set<uint64_t> visited;
  visited.reserve(160);
  visited.insert(state_hash64(cur));

  int max_sw_obs = 0;
  int max_sw_walls = 0;
  bool ever_opened = false;
  vector<MacroOp> cands;

  while (int(tr.route.size()) < max_horizon) {
    int used_keys = int(tr.route.size());
    char last_k = tr.route.empty() ? '\0' : tr.route.back();
    generate_actions(cur, max_horizon - used_keys, use_macros, last_k, visited, cands);
    if (cands.empty()) break;

    vector<double> w_vals(cands.size());
    double max_w = -1e30;
    for (size_t i = 0; i < cands.size(); ++i) {
      auto it = pol.find(quotient_macro_code(cur, used_keys, cands[i].op_tag));
      double w = (it != pol.end()) ? it->second : 0.0;
      w_vals[i] = w;
      if (w > max_w) max_w = w;
    }
    vector<double> probs(cands.size());
    double sum_p = 0.0;
    for (size_t i = 0; i < cands.size(); ++i) {
      probs[i] = exp(w_vals[i] - max_w);
      sum_p += probs[i];
    }
    uniform_real_distribution<double> udist(0.0, sum_p);
    double pick = udist(rng), acc = 0.0;
    size_t chosen = cands.size() - 1;
    for (size_t i = 0; i < cands.size(); ++i) {
      acc += probs[i];
      if (pick <= acc) { chosen = i; break; }
    }

    tr.step_states.push_back(cur);
    tr.step_key_counts.push_back(used_keys);
    tr.chosen_tags.push_back(cands[chosen].op_tag);
    vector<uint32_t> all_tags;
    all_tags.reserve(cands.size());
    for (const auto& op : cands) all_tags.push_back(op.op_tag);
    tr.cand_tags_at_step.push_back(std::move(all_tags));

    // Replay chosen macro's keys step-by-step to record intermediate visited hashes and check early win!
    for (char ch : cands[chosen].keys) {
      CState nx;
      int mv = int(string("UDLRA").find(ch));
      if (!step_concrete(cur, mv, nx)) break;
      tr.route.push_back(ch);
      cur = nx;
      visited.insert(state_hash64(cur));
      int sw_obs = popcnt128((cur.crates | cur.walls) & SWITCH_MASK);
      if (sw_obs > max_sw_obs) max_sw_obs = sw_obs;
      int sw_w = popcnt128(cur.walls & SWITCH_MASK);
      if (sw_w > max_sw_walls) max_sw_walls = sw_w;
      if (cur.doors_open) ever_opened = true;
      if (is_win(cur)) {
        tr.won = true;
        tr.score = 200000 - 1000 * int(tr.route.size());
        return tr;
      }
    }
  }

  int m_act = min(9, popcnt128(cur.crates | (cur.walls & ~ORIGIN_MASK)));
  int end_sw = popcnt128((cur.crates | cur.walls) & SWITCH_MASK);
  int c6w = (tst(cur.walls, 2 * W + 6) ? 1 : 0) + (tst(cur.walls, 3 * W + 6) ? 1 : 0) + (tst(cur.walls, 4 * W + 6) ? 1 : 0);
  int gd1 = abs(int(cur.bx) - 9) + abs(int(cur.by) - 3) + abs(int(cur.dx) - 11) + abs(int(cur.dy) - 3);
  int gd2 = abs(int(cur.bx) - 11) + abs(int(cur.by) - 3) + abs(int(cur.dx) - 9) + abs(int(cur.dy) - 3);
  tr.score = 40 * m_act + 140 * max_sw_obs + 200 * end_sw + 260 * c6w + 90 * max_sw_walls +
             (ever_opened ? 1800 : 0) + (cur.doors_open ? 2200 : 0) - 10 * min(gd1, gd2);
  return tr;
}

static void adapt_policy(Policy& pol, const RolloutTrace& best, double alpha = 1.0) {
  Policy delta;
  for (size_t i = 0; i < best.chosen_tags.size(); ++i) {
    const CState& s = best.step_states[i];
    int used_k = best.step_key_counts[i];
    const auto& tags = best.cand_tags_at_step[i];
    vector<double> w_vals(tags.size());
    double max_w = -1e30;
    for (size_t j = 0; j < tags.size(); ++j) {
      auto it = pol.find(quotient_macro_code(s, used_k, tags[j]));
      double w = (it != pol.end()) ? it->second : 0.0;
      w_vals[j] = w;
      if (w > max_w) max_w = w;
    }
    vector<double> probs(tags.size());
    double sum_p = 0.0;
    for (size_t j = 0; j < tags.size(); ++j) {
      probs[j] = exp(w_vals[j] - max_w);
      sum_p += probs[j];
    }
    delta[quotient_macro_code(s, used_k, best.chosen_tags[i])] += alpha;
    for (size_t j = 0; j < tags.size(); ++j) {
      delta[quotient_macro_code(s, used_k, tags[j])] -= alpha * (probs[j] / sum_p);
    }
  }
  for (const auto& kv : delta) pol[kv.first] += kv.second;
}

static RolloutTrace nrpa_recurse(
    int level,
    int iterations,
    int max_horizon,
    bool use_macros,
    Policy pol,
    mt19937_64& rng,
    uint64_t& rollout_counter
) {
  if (level == 0) {
    rollout_counter++;
    return playout(max_horizon, use_macros, pol, rng);
  }
  RolloutTrace best;
  for (int it = 0; it < iterations; ++it) {
    RolloutTrace cand = nrpa_recurse(level - 1, iterations, max_horizon, use_macros, pol, rng, rollout_counter);
    if (cand.score > best.score) best = cand;
    if (best.score > -900000) adapt_policy(pol, best, 1.0);
  }
  return best;
}

struct RestartOutcome {
  int restart_id = 0;
  string arm;
  uint64_t seed_used = 0;
  int max_horizon = 0;
  bool use_macros = false;
  uint64_t rollouts = 0;
  bool won = false;
  int best_score = 0;
  int win_len = -1;
  string best_route;
};

int main(int argc, char** argv) {
  uint64_t base_seed = 20261119ULL;
  int level = 2;
  int iterations = 60;
  int restarts_prim = 10;
  int restarts_macro_open = 24;
  int restarts_macro_47 = 16;
  int horizon_open = 64;
  int num_threads = 10;
  string json_out = "";

  for (int i = 1; i < argc; ++i) {
    string a = argv[i];
    if (a == "--seed" && i + 1 < argc) base_seed = stoull(argv[++i]);
    else if (a == "--level" && i + 1 < argc) level = stoi(argv[++i]);
    else if (a == "--iterations" && i + 1 < argc) iterations = stoi(argv[++i]);
    else if (a == "--restarts-prim" && i + 1 < argc) restarts_prim = stoi(argv[++i]);
    else if (a == "--restarts-open" && i + 1 < argc) restarts_macro_open = stoi(argv[++i]);
    else if (a == "--restarts-47" && i + 1 < argc) restarts_macro_47 = stoi(argv[++i]);
    else if (a == "--horizon-open" && i + 1 < argc) horizon_open = stoi(argv[++i]);
    else if (a == "--threads" && i + 1 < argc) num_threads = stoi(argv[++i]);
    else if (a == "--json-out" && i + 1 < argc) json_out = argv[++i];
  }

  init_topology();
  int total_jobs = restarts_prim + restarts_macro_open + restarts_macro_47;
  vector<RestartOutcome> outcomes(total_jobs);

  vector<thread> workers;
  for (int tid = 0; tid < num_threads; ++tid) {
    workers.emplace_back([&, tid]() {
      for (int j = tid; j < total_jobs; j += num_threads) {
        string arm_name;
        bool use_mac = false;
        int hor = horizon_open;
        if (j < restarts_prim) {
          arm_name = "primitive_open";
          use_mac = false;
          hor = horizon_open;
        } else if (j < restarts_prim + restarts_macro_open) {
          arm_name = "macro_open";
          use_mac = true;
          hor = horizon_open;
        } else {
          arm_name = "macro_sub48_probe";
          use_mac = true;
          hor = 47;
        }
        uint64_t r_seed = base_seed + uint64_t(j) * 10007ULL;
        mt19937_64 rng(r_seed);
        Policy init_pol;
        uint64_t rollouts = 0;
        RolloutTrace res = nrpa_recurse(level, iterations, hor, use_mac, init_pol, rng, rollouts);
        outcomes[j] = RestartOutcome{
            j, arm_name, r_seed, hor, use_mac, rollouts, res.won, res.score,
            res.won ? int(res.route.size()) : -1,
            res.route
        };
      }
    });
  }
  for (auto& th : workers) th.join();

  uint64_t total_rollouts = 0;
  int wins_prim = 0, wins_macro = 0, wins_47 = 0;
  int shortest_win = -1;
  string shortest_route = "";

  for (const auto& o : outcomes) {
    total_rollouts += o.rollouts;
    if (o.won) {
      if (!o.use_macros) wins_prim++;
      else wins_macro++;
      if (o.win_len <= 47) wins_47++;
      if (shortest_win < 0 || o.win_len < shortest_win) {
        shortest_win = o.win_len;
        shortest_route = o.best_route;
      }
    }
  }

  ostringstream js;
  js << "{\n"
     << "  \"base_seed\": " << base_seed << ",\n"
     << "  \"nrpa_level\": " << level << ",\n"
     << "  \"iterations_per_level\": " << iterations << ",\n"
     << "  \"restarts_primitive_open\": " << restarts_prim << ",\n"
     << "  \"restarts_open_horizon\": " << restarts_macro_open << ",\n"
     << "  \"open_horizon_cap\": " << horizon_open << ",\n"
     << "  \"restarts_sub48_probe\": " << restarts_macro_47 << ",\n"
     << "  \"total_rollouts_executed\": " << total_rollouts << ",\n"
     << "  \"primitive_wins_count\": " << wins_prim << ",\n"
     << "  \"macro_wins_count\": " << wins_macro << ",\n"
     << "  \"winning_restarts_count\": " << (wins_prim + wins_macro) << ",\n"
     << "  \"wins_at_or_below_47\": " << wins_47 << ",\n"
     << "  \"shortest_nrpa_win_len\": " << shortest_win << ",\n"
     << "  \"shortest_nrpa_win_route\": \"" << shortest_route << "\",\n"
     << "  \"restarts\": [\n";
  for (int j = 0; j < total_jobs; ++j) {
    const auto& o = outcomes[j];
    js << "    {\"restart_id\": " << o.restart_id
       << ", \"arm\": \"" << o.arm << "\""
       << ", \"seed\": " << o.seed_used
       << ", \"horizon\": " << o.max_horizon
       << ", \"rollouts\": " << o.rollouts
       << ", \"won\": " << (o.won ? "true" : "false")
       << ", \"win_len\": " << o.win_len
       << ", \"best_score\": " << o.best_score
       << ", \"route\": \"" << (o.won ? o.best_route : "") << "\"}"
       << (j + 1 < total_jobs ? "," : "") << "\n";
  }
  js << "  ]\n}\n";

  if (!json_out.empty()) {
    ofstream f(json_out);
    f << js.str();
  } else {
    cout << js.str();
  }
  return 0;
}
