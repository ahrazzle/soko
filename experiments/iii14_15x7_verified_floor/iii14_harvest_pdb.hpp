#pragma once
#include "iii14_15x7_core.hpp"

struct HarvestAdj15PDB {
  static constexpr int NW = 9, NBL = 18;
  int wall_cells[NW], wall_bit_of[N], max_adj[N], da_id[N][3], NDA = 0;
  vector<pair<int, int>> da_list;
  u128 tracked_mask = 0, other_mask = 0;
  vector<uint8_t> dist;

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

  void build() {
    auto t0 = chrono::steady_clock::now();
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
      for (int a = 0; a <= max_adj[i]; ++a) { da_id[i][a] = (int)da_list.size(); da_list.push_back({i, a}); }
    }
    NDA = (int)da_list.size();
    const uint32_t TOTAL = (1u << NW) * 10 * NDA * NBL * 2 * 2;
    dist.assign(TOTAL, 255);
    uint32_t bl_prev[NBL][4] = {};
    for (int y = 0; y < H; ++y)
      for (int x = 0; x < W; ++x) {
        int l0 = b_loc_of(x, y);
        for (int d = 0; d < 4; ++d) {
          int nx = x + DX[d], ny = y + DY[d];
          if (nx >= 0 && nx < W && ny >= 0 && ny < H) bl_prev[b_loc_of(nx, ny)][d] |= (1u << l0);
        }
      }
    auto max_k = [&](int wm, int kr) { return (kr == 9) ? 40 : (__builtin_popcount((unsigned)wm) + kr); };
    auto can_open_fn = [&](int wm, int kr, int di, int bl) {
      return max_k(wm, kr) + ((bl >= 4 && bl <= 6) ? 1 : 0) + (IS_SW[di] ? 1 : 0) >= 9;
    };
    auto valid_st = [&](int wm, int kr, int di, int adj, int bl, int ao) -> bool {
      if (adj < 0 || adj > max_adj[di] || max_adj[di] - adj > kr) return false;
      int wb = wall_bit_of[di];
      if (wb >= 0 && !((wm >> wb) & 1)) return false;
      if (tst(other_mask, di) && kr == 0) return false;
      if (bl == 0 && (wm & 0x0F) == 0 && kr == 0) return false;
      if (bl == 14 && kr == 0) return false;
      if (ao == 0 && (IS_PD[di] || bl == 15)) return false;
      if (ao == 1 && !can_open_fn(wm, kr, di, bl)) return false;
      return true;
    };
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
      int nkr = tmp % 10; tmp /= 10; int nwm = (int)tmp;
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
          if (!IS_ORIG[ti]) { if (max_k(nwm, nkr) > 0) push_pred(nwm, nkr, ndi, nadj, nbl, 1, ao); }
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
    cout << "Built Exact-Crush HarvestAdj15PDB: reachable=" << q.size() << "/" << TOTAL
      << " in " << fixed << setprecision(2) << chrono::duration<double>(chrono::steady_clock::now() - t0).count() << "s\n";
  }
  inline int lookup(const CState& s) const {
    u128 miss = ORIGIN_MASK & ~s.walls;
    int wm = 0; for (int b = 0; b < NW; ++b) if (tst(miss, wall_cells[b])) wm |= (1 << b);
    int kr = min(9, popcnt128(miss & other_mask)), di = s.dy * W + s.dx;
    int adj = popcnt128(s.walls & other_mask & ORTHO[di]);
    uint8_t d = dist[encode(wm, kr, da_id[di][adj], b_loc_of(s.bx, s.by), s.ah, s.doors_open)];
    return d == 255 ? 999 : (int)d;
  }
};
