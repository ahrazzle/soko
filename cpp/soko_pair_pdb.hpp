#pragma once
struct PairAtomQuotientPDB {
  bool enabled = false;
  int N = 0, K_REQ = 0, a_unborn = 0, a_spare = 0, NA = 0, npairs = 0;
  vector<int> int_idx_of, int_cell_of, atom_cell, initw_cells, pair_id_flat, sw_tx, sw_ty;
  vector<uint8_t> is_sw, is_pd, is_chamber, atom_is_sw, dist;
  vector<pair<uint16_t, uint16_t>> pairs;
  bool coord_bound_ok = false;
  int g1_cell = -1, g2_cell = -1, min_r_b = 99, min_d_b = 99, min_u_b = 99;
  inline int pid_of(int a, int b) const { return pair_id_flat[a * NA + b]; }
  inline uint32_t encode(int pid, int bi, int dz, int rd, int ah, int ao) const {
    return ((((((uint32_t)pid * N + bi) * 2 + dz) * 4 + rd) * 2 + ah) * 2) + ao;
  }
  int calc_r_dist(const LevelMeta& M, const DynState& s, int di) const {
    int dx = di % M.w, dy = di / M.w, best = 99;
    for (int ic : initw_cells) if (s.obj[ic] == 13) best = min(best, abs((ic % M.w) - dx) + abs((ic / M.w) - dy));
    return min(3, max(0, best - 1));
  }
  void try_build(const LevelMeta& M, const DynState& s0) {
    if (M.part != 3 || !M.has_bard || M.n > 112 || M.goals.size() != 2 || M.p_switches.empty() || !M.y_switches.empty()) return;
    int cnt_b = 0, cnt_d = 0, cnt_other = 0, cnt_mon = 0, init_crates = 0;
    for (int i = 0; i < M.n; ++i) {
      uint8_t v = s0.obj[i];
      if (v == 5 || v == 11) cnt_b++; else if (v == 6 || v == 12) cnt_d++;
      else if (is_hero(v)) cnt_other++; else if (is_monster(M.part, v)) cnt_mon++; else if (v == 14) init_crates++;
    }
    if (cnt_b != 1 || cnt_d != 1 || cnt_other != 0 || cnt_mon != 0 || init_crates != 0) return;
    N = M.n; K_REQ = (int)M.p_switches.size();
    if (K_REQ < 2 || K_REQ > 9) return;
    is_sw.assign(N, 0); is_pd.assign(N, 0); is_chamber.assign(N, 0);
    for (int idx : M.p_switches) is_sw[idx] = 1;
    for (int idx : M.p_doors_init) { is_pd[idx] = 1; is_chamber[idx] = 1; }
    g1_cell = M.goals[0]; g2_cell = M.goals[1];
    {
      queue<int> fq; vector<uint8_t> vis(N, 0);
      for (int g : M.goals) { vis[g] = 1; fq.push(g); }
      bool sealed = true;
      while (!fq.empty()) {
        int u = fq.front(); fq.pop(); int ux = u % M.w, uy = u / M.w;
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
    int_idx_of.assign(N, -1); int_cell_of.clear(); initw_cells.clear();
    for (int i = 0; i < N; ++i) {
      if (M.init_wall[i]) initw_cells.push_back(i);
      else { int_idx_of[i] = (int)int_cell_of.size(); int_cell_of.push_back(i); }
    }
    int n_int = (int)int_cell_of.size();
    a_unborn = N + n_int; a_spare = N + n_int + 1; NA = N + n_int + 2;
    atom_cell.assign(NA, -1); atom_is_sw.assign(NA, 0);
    for (int a = 0; a < NA; ++a) {
      atom_cell[a] = (a < N) ? a : ((a < a_unborn) ? int_cell_of[a - N] : -1);
      atom_is_sw[a] = (atom_cell[a] >= 0 && is_sw[atom_cell[a]]) || (a == a_spare);
    }
    pair_id_flat.assign(NA * NA, -1); pairs.clear();
    for (int a = 0; a < NA; ++a) for (int b = a; b < NA; ++b) {
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
    auto in_aura = [&](int cell, int bi) { return abs((cell % M.w) - (bi % M.w)) <= 2 && abs((cell / M.w) - (bi / M.w)) <= 2; };
    auto valid_u = [&](int pid, int bi) { auto [a, b] = pairs[pid]; return atom_cell[a] != bi && atom_cell[b] != bi; };
    auto can_ao1 = [&](int pid, int nbi, int ndz) {
      auto [na, nb] = pairs[pid];
      return ((!atom_is_sw[na] ? 1 : 0) + (!atom_is_sw[nb] ? 1 : 0)) <= ((is_sw[nbi] ? 1 : 0) + (ndz == 0 ? 1 : 0));
    };
    vector<uint32_t> q; q.reserve(TOTAL / 2);
    for (int pid = 0; pid < npairs; ++pid) for (int bg : {g1_cell, g2_cell})
      for (int rd = 0; rd < 4; ++rd) for (int ah = 0; ah < 2; ++ah) for (int ao = 0; ao < 2; ++ao) {
        uint32_t w = encode(pid, bg, 1, rd, ah, ao);
        if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
      }
    for (size_t qi = 0; qi < q.size(); ++qi) {
      uint32_t v = q[qi]; uint8_t nd = dist[v] + 1; uint32_t tmp = v;
      int nao = tmp & 1; tmp >>= 1; int nah = tmp & 1; tmp >>= 1;
      int nrd = tmp & 3; tmp >>= 2; int ndz = tmp & 1; tmp >>= 1;
      int nbi = tmp % N; tmp /= N; int npid = (int)tmp;
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
            int p = M.init_wall[ta] ? pid_of(a_unborn, ob) : pid_of(N + int_idx_of[ta], ob);
            int r0 = M.init_wall[ta] ? 0 : nrd;
            for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, r0, 1, ao);
          } else if (ta < a_unborn) {
            int p = pid_of(atom_cell[ta], ob);
            for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, nrd, 1, ao);
          } else if (ta == a_unborn && nrd == 0) {
            for (int icell : initw_cells) {
              int p = pid_of(icell, ob);
              for (int rprev = 0; rprev < 4; ++rprev) for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, rprev, 1, ao);
            }
          } else if (ta == a_spare) {
            for (int pa = 0; pa < NA; ++pa) { int p = pid_of(pa, ob); for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, 0, 1, ao); }
          }
        };
        trans_one(na, nb); if (nb != na) trans_one(nb, na);
        if (nrd == 0) for (int rprev = 0; rprev < 4; ++rprev) for (int ao = 0; ao < 2; ++ao) push_pred(p, nbi, ndz, rprev, 1, ao);
        for (int ao = 0; ao < 2; ++ao) { push_pred(npid, nbi, ndz, 0, 1, ao); push_pred(npid, nbi, ndz, nrd, 1, ao); }
      } else {
        int nbx = nbi % M.w, nby = nbi / M.w, rd_lo = max(0, nrd - 1), rd_hi = (nrd == 3) ? 3 : (nrd + 1);
        for (int d = 0; d < 4; ++d) {
          int bx = nbx - DX[d], by = nby - DY[d];
          if (bx < 0 || bx >= M.w || by < 0 || by >= M.h) continue;
          int bi = by * M.w + bx, cand_a[2] = {(int)na, 0}, nca = 1, cand_b[2] = {(int)nb, 0}, ncb = 1;
          if (na < N) { int px = (na % M.w) - DX[d], py = (na / M.w) - DY[d]; if (px >= 0 && px < M.w && py >= 0 && py < M.h && in_aura(py * M.w + px, bi)) cand_a[nca++] = py * M.w + px; }
          if (nb < N) { int px = (nb % M.w) - DX[d], py = (nb / M.w) - DY[d]; if (px >= 0 && px < M.w && py >= 0 && py < M.h && in_aura(py * M.w + px, bi)) cand_b[ncb++] = py * M.w + px; }
          for (int ia = 0; ia < nca; ++ia) for (int ib = 0; ib < ncb; ++ib) {
            int pid = pid_of(cand_a[ia], cand_b[ib]); if (pid < 0) continue;
            for (int rd = rd_lo; rd <= rd_hi; ++rd) for (int ao = 0; ao < 2; ++ao) { push_pred(pid, bi, ndz, rd, 0, ao); push_pred(pid, bi, 1 - ndz, rd, 0, ao); }
          }
        }
      }
    }
    sw_tx.clear(); sw_ty.clear();
    for (int idx : M.p_switches) { sw_tx.push_back(idx % M.w); sw_ty.push_back(idx / M.w); }
    sort(sw_tx.begin(), sw_tx.end()); sort(sw_ty.begin(), sw_ty.end());
    int min_sw_ch_dist = 99;
    for (int si : M.p_switches) for (int ci = 0; ci < N; ++ci) if (is_chamber[ci]) min_sw_ch_dist = min(min_sw_ch_dist, abs((si % M.w) - (ci % M.w)) + abs((si / M.w) - (ci / M.w)));
    coord_bound_ok = (K_REQ == 9 && min_sw_ch_dist >= 2 && (g1_cell / M.w) == (g2_cell / M.w));
    if (coord_bound_ok) {
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
    int bi = -1, di = -1, ah = 0, atoms[64], na = 0;
    for (int i = 0; i < N; ++i) {
      uint8_t v = s.obj[i];
      if (v == 5) { bi = i; ah = 0; } else if (v == 11) bi = i;
      else if (v == 6) { di = i; ah = 1; } else if (v == 12) di = i;
      if (v == 14 && na < 60) atoms[na++] = i;
      else if (v == 13 && !M.init_wall[i] && na < 60) atoms[na++] = N + int_idx_of[i];
    }
    if (bi < 0 || di < 0) return 999;
    int dz = is_chamber[di] ? 1 : 0, rd = calc_r_dist(M, s, di), ao = s.p_open ? 1 : 0, best = 0;
    if (na > K_REQ) {
      for (int i = 0; i < na; ++i) { uint8_t d = dist[encode(pid_of(atoms[i], a_spare), bi, dz, rd, ah, ao)]; best = max(best, d == 255 ? 999 : (int)d); }
    } else {
      while (na < K_REQ) atoms[na++] = a_unborn;
      for (int i = 0; i < K_REQ; ++i) for (int j = i + 1; j < K_REQ; ++j) {
        uint8_t d = dist[encode(pid_of(atoms[i], atoms[j]), bi, dz, rd, ah, ao)];
        best = max(best, d == 255 ? 999 : (int)d);
      }
    }
    if (best >= 999) return 999;
    if (coord_bound_ok && !(is_chamber[bi] && is_chamber[di])) {
      int bx = bi % M.w, by = bi / M.w, dx = di % M.w, dy = di / M.w, gy = g1_cell / M.w, g1x = g1_cell % M.w, g2x = g2_cell % M.w;
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
        int use_old = 9 - c, sw_keys = (c > 0) ? (ah == 0 ? 2 : 1) : ((uncov_sw > 0 && ah == 1) ? 1 : 0);
        int req_R = 0, req_L = 0, req_D = 0, req_U = 0, min_cbx = 99, max_cbx = -99, min_cby = 99, max_cby = -99;
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
          int h_mx = (abs(dbx) + abs(ddx) + abs(dbx - ddx)) >> 1, h_my = (abs(dby) + abs(ddy) + abs(dby - ddy)) >> 1;
          int b_mx = max({req_R + req_L, 2 * req_L + dbx, 2 * req_R - dbx, h_mx});
          int b_my = max({req_D + req_U, 2 * req_U + dby, 2 * req_D - dby, h_my});
          int move_sum = b_mx + b_my;
          if (c_b > 0 && min_r_b < 99 && min_d_b < 99 && min_u_b < 99) {
            move_sum = min({
              max({min_r_b + req_L, 2 * req_L + dbx, 2 * min_r_b - dbx, b_mx}) + b_my,
              b_mx + max({min_d_b + req_U, 2 * req_U + dby, 2 * min_d_b - dby, b_my}),
              b_mx + max({req_D + min_u_b, 2 * min_u_b + dby, 2 * req_D - dby, b_my})
            });
          }
          best_c = min(best_c, c + sw_keys + move_sum);
        }
      }
      best = max(best, best_c);
    }
    return best;
  }
};
struct WizardRayGoalBound {
  bool enabled = false, count_uncov_goals_ok = false;
  vector<int> wiz_dist;
  void build(const LevelMeta& M, const DynState& s0, bool has_druid, bool has_fighter) {
    if (M.goals.empty()) return;
    wiz_dist.assign(M.n, 999); queue<int> q;
    for (int g : M.goals) { wiz_dist[g] = 0; q.push(g); }
    while (!q.empty()) {
      int u = q.front(); q.pop(); int ux = u % M.w, uy = u / M.w;
      for (int d = 0; d < 4; ++d) {
        int nx = ux + DX[d], ny = uy + DY[d];
        if (nx >= 0 && nx < M.w && ny >= 0 && ny < M.h) {
          int ni = ny * M.w + nx;
          if ((has_druid || s0.obj[ni] != 13) && wiz_dist[ni] > wiz_dist[u] + 1) { wiz_dist[ni] = wiz_dist[u] + 1; q.push(ni); }
        }
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
    int best = 1, hero_cnt = 0;
    for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) { hero_cnt++; best = max(best, wiz_dist[i]); }
    if (hero_cnt < (int)M.goals.size()) return 999;
    if (count_uncov_goals_ok) { int uncov = 0; for (int g : M.goals) if (!is_hero(s.obj[g])) uncov++; best = max(best, uncov); }
    return best;
  }
};
