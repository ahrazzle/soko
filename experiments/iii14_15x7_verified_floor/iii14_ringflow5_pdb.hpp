#pragma once
#include "iii14_15x7_core.hpp"
// ============================================================================
// PDB 1: RingFlow5_15PDB under Exact Crush Semantics
struct RingFlow5_15PDB {
 static constexpr int NB = 60;
 struct Tup5 { uint8_t km, k0, k1, k2, k3; };
 int tp_id[10][10][10][10][10], tp10_id[10][10], NR = 0;
 vector<Tup5> tp_list;
 int max_adj[N], da_id[N][3], NDA = 0;
 vector<pair<int, int>> da_list;
 vector<uint8_t> dist;
 struct Cap8 { uint8_t m01, m10, m12, m21, m23, m32, m34, m43; bool operator==(const Cap8&) const = default; };
 int cap_id_of[NB][4][2];
 vector<vector<vector<uint16_t>>> back_tp;
 inline uint32_t encode(int rt, int da, int bi, int ah) const {
  return ((((uint32_t)rt * NDA + da) * NB + bi) * 2) + ah;
 }
 void build() {
  auto t0 = chrono::steady_clock::now();
  memset(tp_id, -1, sizeof(tp_id)); tp_list.clear();
  for (int km = 0; km <= 9; ++km)
   for (int k0 = 0; k0 <= km; ++k0)
   for (int k1 = 0; k0 + k1 <= km; ++k1)
   for (int k2 = 0; k0 + k1 + k2 <= km; ++k2)
   for (int k3 = 0; k0 + k1 + k2 + k3 <= km; ++k3) {
    tp_id[km][k0][k1][k2][k3] = (int)tp_list.size();
    tp_list.push_back({(uint8_t)km, (uint8_t)k0, (uint8_t)k1, (uint8_t)k2, (uint8_t)k3});
   }
  for (int k0 = 0; k0 <= 9; ++k0)
   for (int k1 = 0; k1 <= 9; ++k1) {
    tp10_id[k0][k1] = (int)tp_list.size();
    tp_list.push_back({10, (uint8_t)k0, (uint8_t)k1, 0, 0});
   }
  NR = (int)tp_list.size();
  memset(da_id, -1, sizeof(da_id)); da_list.clear();
  for (int i = 0; i < N; ++i) {
   max_adj[i] = popcnt128(ORIGIN_MASK & ORTHO[i]);
   for (int a = 0; a <= max_adj[i]; ++a) { da_id[i][a] = (int)da_list.size(); da_list.push_back({i, a}); }
  }
  NDA = (int)da_list.size();
  vector<Cap8> ucaps;
  for (int bi = 0; bi < NB; ++bi) {
   int bx = bi % W, by = bi / W;
   for (int d = 0; d < 4; ++d) {
    int nbx = bx + DX[d], nby = by + DY[d];
    int nbi = (nbx >= 0 && nbx < W && nby >= 0 && nby < H) ? (nby * W + nbx) : -1;
    for (int ao = 0; ao < 2; ++ao) {
     Cap8 sc{};
     if (nbi >= 0) {
      for (int c = 0; c < N; ++c) {
       if (c == bi || !tst(AURA[bi], c) || (ao == 0 && IS_PD[c])) continue;
       int tx = (c % W) + DX[d], ty = (c / W) + DY[d];
       if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
       int tc = ty * W + tx;
       if (tc == nbi || (ao == 0 && IS_PD[tc])) continue;
       int rs = D5_RING[c], rd = D5_RING[tc];
       if (rs == 0 && rd == 1) sc.m01++; else if (rs == 1 && rd == 0) sc.m10++;
       else if (rs == 1 && rd == 2) sc.m12++; else if (rs == 2 && rd == 1) sc.m21++;
       else if (rs == 2 && rd == 3) sc.m23++; else if (rs == 3 && rd == 2) sc.m32++;
       else if (rs == 3 && rd == 4) sc.m34++; else if (rs == 4 && rd == 3) sc.m43++;
      }
     }
     int cid = -1;
     for (int u = 0; u < (int)ucaps.size(); ++u) if (ucaps[u] == sc) { cid = u; break; }
     if (cid < 0) { cid = (int)ucaps.size(); ucaps.push_back(sc); }
     cap_id_of[bi][d][ao] = cid;
    }
   }
  }
  back_tp.assign(NR, vector<vector<uint16_t>>(ucaps.size()));
  for (int cid = 0; cid < (int)ucaps.size(); ++cid) {
   auto sc = ucaps[cid];
   for (int prt = 0; prt < NR; ++prt) {
    auto [pkm, k0, k1, k2, k3] = tp_list[prt];
    if (pkm <= 9) {
     int k4 = pkm - k0 - k1 - k2 - k3;
     for (int x01 = 0; x01 <= min<int>(sc.m01, k0); ++x01)
     for (int x10 = 0; x10 <= min<int>(sc.m10, k1); ++x10)
     for (int x12 = 0; x10 + x12 <= k1 && x12 <= sc.m12; ++x12)
     for (int x21 = 0; x21 <= min<int>(sc.m21, k2); ++x21)
     for (int x23 = 0; x21 + x23 <= k2 && x23 <= sc.m23; ++x23)
     for (int x32 = 0; x32 <= min<int>(sc.m32, k3); ++x32)
     for (int x34 = 0; x32 + x34 <= k3 && x34 <= sc.m34; ++x34)
     for (int x43 = 0; x43 <= min<int>(sc.m43, k4); ++x43) {
      int n0 = k0 - x01 + x10, n1 = k1 - x10 - x12 + x01 + x21;
      int n2 = k2 - x21 - x23 + x12 + x32, n3 = k3 - x32 - x34 + x23 + x43;
      if (n0 <= 9) {
       int nrt = tp_id[pkm][n0][n1][n2][n3];
       if (nrt >= 0) back_tp[nrt][cid].push_back((uint16_t)prt);
      }
     }
    } else {
     for (int x01 = 0; x01 <= min<int>(sc.m01, k0); ++x01)
     for (int x10 = 0; x10 <= (k1 < 9 ? min<int>(sc.m10, k1) : (int)sc.m10); ++x10) {
      int n0 = k0 - x01 + x10;
      if (n0 < 0 || n0 > 9) continue;
      if (k1 < 9) {
       for (int x12 = 0; x10 + x12 <= k1 && x12 <= sc.m12; ++x12)
       for (int x21 = 0; x21 <= sc.m21; ++x21) {
        int n1 = min(9, (int)k1 - x10 - x12 + x01 + x21);
        back_tp[tp10_id[n0][n1]][cid].push_back((uint16_t)prt);
       }
      } else {
       int lo1 = max(0, 9 - x10 - (int)sc.m12 + x01);
       for (int n1 = min(9, lo1); n1 <= 9; ++n1)
        back_tp[tp10_id[n0][n1]][cid].push_back((uint16_t)prt);
      }
     }
    }
   }
   for (int nrt = 0; nrt < NR; ++nrt) {
    auto& v = back_tp[nrt][cid];
    sort(v.begin(), v.end()); v.erase(unique(v.begin(), v.end()), v.end());
   }
  }
  const uint32_t TOTAL = (uint32_t)NR * NDA * NB * 2;
  dist.assign(TOTAL, 255);
  auto ao_of = [&](int rt, int bi, int di) -> int {
   return ((int)tp_list[rt].k0 + (IS_SW[bi] ? 1 : 0) + (IS_SW[di] ? 1 : 0) == 9) ? 1 : 0;
  };
  auto valid_u = [&](int rt, int di, int adj, int bi) -> bool {
   if (bi >= NB || bi == di || adj < 0 || adj > max_adj[di]) return false;
   int h_sw = (IS_SW[bi] ? 1 : 0) + (IS_SW[di] ? 1 : 0);
   if ((int)tp_list[rt].k0 + h_sw > 9) return false;
   int ao = ((int)tp_list[rt].k0 + h_sw == 9) ? 1 : 0;
   if (ao == 0 && (IS_PD[bi] || IS_PD[di])) return false;
   return true;
  };
  vector<vector<uint16_t>> pre_crush(NR);
  for (int nrt = 0; nrt < NR; ++nrt) {
   auto [nkm, n0, n1, n2, n3] = tp_list[nrt];
   pre_crush[nrt].push_back((uint16_t)nrt);
   if (nkm <= 9) {
    int n4 = nkm - n0 - n1 - n2 - n3;
    for (int c2 = 0; c2 <= 3; ++c2)
    for (int c3 = 0; c3 <= 3; ++c3)
    for (int c4 = 0; c4 <= 6; ++c4) {
     int tot = c2 + c3 + c4;
     if (tot == 0) continue;
     if (nkm + tot <= 9) {
      int ert = tp_id[nkm + tot][n0][n1][n2 + c2][n3 + c3];
      if (ert >= 0) pre_crush[nrt].push_back((uint16_t)ert);
     } else {
      pre_crush[nrt].push_back((uint16_t)tp10_id[n0][n1]);
     }
    }
   } else {
    pre_crush[nrt].push_back((uint16_t)tp10_id[n0][n1]);
   }
   auto& v = pre_crush[nrt];
   sort(v.begin(), v.end()); v.erase(unique(v.begin(), v.end()), v.end());
  }
  vector<vector<vector<uint16_t>>> back_tp_crush1(NR, vector<vector<uint16_t>>(ucaps.size()));
  for (int nrt = 0; nrt < NR; ++nrt)
   for (int cid = 0; cid < (int)ucaps.size(); ++cid) {
    auto& dst = back_tp_crush1[nrt][cid];
    for (uint16_t ert : pre_crush[nrt])
     for (uint16_t prt : back_tp[ert][cid])
      if (tp_list[prt].k0 >= 7) dst.push_back(prt);
    sort(dst.begin(), dst.end()); dst.erase(unique(dst.begin(), dst.end()), dst.end());
   }
  vector<uint32_t> q; q.reserve(TOTAL / 2);
  for (int rt = 0; rt < NR; ++rt) {
   for (int gi = 0; gi < 2; ++gi) {
    int bg = GOALS[gi], dg = GOALS[1 - gi];
    for (int adj = 0; adj <= max_adj[dg]; ++adj)
     for (int ah = 0; ah < 2; ++ah)
      if (valid_u(rt, dg, adj, bg)) {
       uint32_t w = encode(rt, da_id[dg][adj], bg, ah);
       if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
      }
   }
  }
  for (size_t qi = 0; qi < q.size(); ++qi) {
   uint32_t v = q[qi]; uint8_t nd = dist[v] + 1; uint32_t tmp = v;
   int nah = tmp & 1; tmp >>= 1;
   int nbi = tmp % NB; tmp /= NB; int nda = tmp % NDA; tmp /= NDA; int nrt = (int)tmp;
   auto [ndi, nadj] = da_list[nda];
   int nao = ao_of(nrt, nbi, ndi);
   auto push_pred = [&](int rt, int di, int adj, int bi, int ah) {
    if (rt < 0 || !valid_u(rt, di, adj, bi)) return;
    uint32_t u = encode(rt, da_id[di][adj], bi, ah);
    if (dist[u] == 255) { dist[u] = nd; q.push_back(u); }
   };
   push_pred(nrt, ndi, nadj, nbi, 1 - nah);
   if (nah == 1) {
    int ndx = ndi % W, ndy = ndi / W;
    for (int d = 0; d < 4; ++d) {
     int px = ndx - DX[d], py = ndy - DY[d];
     if (px < 0 || px >= W || py < 0 || py >= H) continue;
     int pdi = py * W + px;
     for (int padj = 0; padj <= max_adj[pdi]; ++padj) {
      if (ao_of(nrt, nbi, pdi) == 0 && !IS_PD[ndi]) push_pred(nrt, pdi, padj, nbi, 1);
      if (nao == 1) {
       if (ao_of(nrt, nbi, pdi) == 1) push_pred(nrt, pdi, padj, nbi, 1);
      } else {
       for (uint16_t ert : pre_crush[nrt])
        if (ao_of(ert, nbi, pdi) == 1) push_pred(ert, pdi, padj, nbi, 1);
      }
     }
    }
    auto [nkm, n0, n1, n2, n3] = tp_list[nrt];
    for (int d = 0; d < 4; ++d) {
     int tx = ndx + DX[d], ty = ndy + DY[d];
     if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
     int ti = ty * W + tx;
     if (ti == nbi || (IS_PD[ti] && nao == 0)) continue;
     int bk = D5_RING[ti];
     if (!IS_ORIG[ti]) {
      bool ok = (nkm >= 1);
      if (bk == 0 && n0 == 0) ok = false;
      if (bk == 1 && n1 == 0) ok = false;
      if (bk == 2 && nkm <= 9 && n2 == 0) ok = false;
      if (bk == 3 && nkm <= 9 && n3 == 0) ok = false;
      if (bk == 4 && nkm <= 9 && (nkm - n0 - n1 - n2 - n3) == 0) ok = false;
      if (ok) push_pred(nrt, ndi, nadj, nbi, 1);
     } else {
      if (nadj + 1 <= max_adj[ndi]) {
       if (nkm >= 1 && nkm <= 9) {
        int p2 = (int)n2 - (bk == 2), p3 = (int)n3 - (bk == 3);
        if (p2 >= 0 && p3 >= 0 && n0 + n1 + p2 + p3 <= nkm - 1)
         push_pred(tp_id[nkm - 1][n0][n1][p2][p3], ndi, nadj + 1, nbi, 1);
       } else if (nkm == 10) {
        push_pred(nrt, ndi, nadj + 1, nbi, 1);
        for (int p2 = 0; n0 + n1 + p2 <= 9; ++p2)
         for (int p3 = 0; n0 + n1 + p2 + p3 <= 9; ++p3)
          push_pred(tp_id[9][n0][n1][p2][p3], ndi, nadj + 1, nbi, 1);
       }
      }
      if (nadj >= 1) {
       if (nkm <= 8) {
        int p2 = (int)n2 + (bk == 2), p3 = (int)n3 + (bk == 3);
        if (n0 + n1 + p2 + p3 <= nkm + 1)
         push_pred(tp_id[nkm + 1][n0][n1][p2][p3], ndi, nadj - 1, nbi, 1);
       } else if (nkm == 9) {
        push_pred(tp10_id[n0][n1], ndi, nadj - 1, nbi, 1);
       } else {
        push_pred(nrt, ndi, nadj - 1, nbi, 1);
       }
      }
     }
    }
   } else {
    auto emit_bard_back = [&](int bi, int nbi_raw, int ndi_raw, int d) {
     bool b_pd = IS_PD[bi] || IS_PD[nbi_raw];
     int ndx = ndi_raw % W, ndy = ndi_raw / W;
     int pdx = ndx - DX[d], pdy = ndy - DY[d];
     int pdi_p = (pdx >= 0 && pdx < W && pdy >= 0 && pdy < H && tst(AURA[bi], pdy * W + pdx)) ? (pdy * W + pdx) : -1;
     if (!b_pd) {
      const auto& prts0 = back_tp[nrt][cap_id_of[bi][d][0]];
      for (uint16_t prt : prts0) {
       if (ao_of(prt, bi, ndi_raw) == 0) push_pred(prt, ndi_raw, nadj, bi, 0);
       if (pdi_p >= 0 && !IS_PD[pdi_p] && !IS_PD[ndi_raw])
        for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
         if (ao_of(prt, bi, pdi_p) == 0) push_pred(prt, pdi_p, padj, bi, 0);
      }
     }
     if (nao == 1) {
      const auto& prts1 = back_tp[nrt][cap_id_of[bi][d][1]];
      for (uint16_t prt : prts1) {
       if (ao_of(prt, bi, ndi_raw) == 1) push_pred(prt, ndi_raw, nadj, bi, 0);
       if (pdi_p >= 0)
        for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
         if (ao_of(prt, bi, pdi_p) == 1) push_pred(prt, pdi_p, padj, bi, 0);
      }
     } else {
      for (uint16_t prt : back_tp_crush1[nrt][cap_id_of[bi][d][1]]) {
       if (ao_of(prt, bi, ndi_raw) == 1) push_pred(prt, ndi_raw, nadj, bi, 0);
       if (pdi_p >= 0)
        for (int padj = 0; padj <= max_adj[pdi_p]; ++padj)
         if (ao_of(prt, bi, pdi_p) == 1) push_pred(prt, pdi_p, padj, bi, 0);
      }
     }
    };
    int nbx = nbi % W, nby = nbi / W;
    for (int d = 0; d < 4; ++d) {
     int bx = nbx - DX[d], by = nby - DY[d];
     if (bx >= 0 && bx < W && by >= 0 && by <= 3) emit_bard_back(by * W + bx, nbi, ndi, d);
    }
    if (nby == 2) emit_bard_back(3 * W + nbx, 4 * W + nbx, mirror_y_cell(ndi), 1);
   }
  }
  cout << "Built Exact-Crush RingFlow5_15PDB: NR=" << NR << " reachable=" << q.size() << "/" << TOTAL
   << " (" << fixed << setprecision(1) << (TOTAL / 1048576.0) << " MiB) in "
   << setprecision(2) << chrono::duration<double>(chrono::steady_clock::now() - t0).count() << "s\n";
 }
 inline int lookup(const CState& s_in) const {
  CState s = (s_in.by <= 3) ? s_in : mirror_y_state(s_in);
  u128 act = s.crates | (s.walls & ~ORIGIN_MASK);
  int km = min(10, popcnt128(act));
  int k0 = popcnt128(act & D5_MASK[0]);
  int k1 = min(9, popcnt128(act & D5_MASK[1]));
  int rt = (km <= 9) ? tp_id[km][k0][k1][popcnt128(act & D5_MASK[2])][popcnt128(act & D5_MASK[3])] : tp10_id[k0][k1];
  int di = s.dy * W + s.dx, bi = s.by * W + s.bx;
  int adj = popcnt128(s.walls & ORIGIN_MASK & ORTHO[di]);
  uint8_t d = dist[encode(rt, da_id[di][adj], bi, s.ah)];
  return d == 255 ? 999 : (int)d;
 }
};
