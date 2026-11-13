// gateway67_pdb.hpp
// Exact 2x3 Gateway Block Quotient Homomorphism on [6..7] x [2..4] (3^6 = 729 states)
// Captures simultaneous x=6 switch-column transmutation & x=7 aura-pull crush hazards!
#pragma once
#include "iii14_15x7_core.hpp"

struct Gateway67_15PDB {
  static constexpr uint32_t TOTAL = 105 * 105 * 2 * 729 * 2; // 32,148,900 (30.66 MiB)
  vector<uint8_t> dist;

  static inline uint32_t enc(int b, int d, int ah, int st, int pd) {
    return (((uint32_t(b) * 105 + d) * 2 + ah) * 729 + st) * 2 + pd;
  }
  static inline int gcell(int col, int row) { return (2 + row) * W + (6 + col); }
  static inline int gidx_of(int cell) {
    int x = cell % W, y = cell / W;
    return (x >= 6 && x <= 7 && y >= 2 && y <= 4) ? ((x - 6) * 3 + (y - 2)) : -1;
  }

  inline int lookup(const CState& s) const {
    int st = 0, p3 = 1;
    for (int col = 0; col < 2; ++col)
      for (int row = 0; row < 3; ++row) {
        int c = gcell(col, row);
        st += (tst(s.crates, c) ? 1 : (tst(s.walls, c) ? 2 : 0)) * p3;
        p3 *= 3;
      }
    uint8_t d = dist[enc(s.by * W + s.bx, s.dy * W + s.dx, s.ah, st, s.doors_open)];
    return d == 255 ? 999 : (int)d;
  }

  template <typename EmitFn>
  static void enum_all_edges(EmitFn&& on_edge) {
    auto emit_late = [&](uint32_t u, int nb, int nd, int nah, const int ns[6]) {
      if (nb == nd) return;
      for (int k = 0; k < 6; ++k) {
        int c = gcell(k / 3, k % 3);
        if (ns[k] != 0 && (nb == c || nd == c)) return;
      }
      int nst = 0, p3 = 1;
      for (int k = 0; k < 6; ++k) { nst += ns[k] * p3; p3 *= 3; }
      bool c6_all3 = true;
      for (int r = 0; r < 3; ++r) {
        int c = gcell(0, r);
        if (ns[r] == 0 && nb != c && nd != c) { c6_all3 = false; break; }
      }
      bool hpd = IS_PD[nb] || IS_PD[nd];
      if (c6_all3) {
        on_edge(u, enc(nb, nd, nah, nst, 1));
        if (!hpd) on_edge(u, enc(nb, nd, nah, nst, 0));
      } else {
        if (!hpd) on_edge(u, enc(nb, nd, nah, nst, 0));
      }
    };

    for (int b = 0; b < N; ++b) {
      int bx = b % W, by = b / W;
      for (int d = 0; d < N; ++d) {
        if (b == d) continue;
        int dx = d % W, dy = d / W;
        for (int st = 0; st < 729; ++st) {
          int sa[6], tmp = st;
          bool bad = false;
          for (int k = 0; k < 6; ++k) {
            sa[k] = tmp % 3; tmp /= 3;
            int c = gcell(k / 3, k % 3);
            if (sa[k] != 0 && (b == c || d == c)) bad = true;
          }
          if (bad) continue;
          bool c6_pre = true;
          for (int r = 0; r < 3; ++r) {
            int c = gcell(0, r);
            if (sa[r] == 0 && b != c && d != c) { c6_pre = false; break; }
          }
          for (int pd = 0; pd < 2; ++pd) {
            if (pd == 0 && (IS_PD[b] || IS_PD[d])) continue;
            if (pd == 1 && !c6_pre) continue;
            for (int ah = 0; ah < 2; ++ah) {
              uint32_t u = enc(b, d, ah, st, pd);
              emit_late(u, b, d, 1 - ah, sa);
              if (ah == 1) {
                for (int mv = 0; mv < 4; ++mv) {
                  int tx = dx + DX[mv], ty = dy + DY[mv];
                  if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                  int tc = ty * W + tx;
                  if (tc == b || (pd == 0 && IS_PD[tc])) continue;
                  int gi = gidx_of(tc);
                  if (gi >= 0) {
                    int ns[6]; memcpy(ns, sa, sizeof(sa));
                    if (sa[gi] == 0) emit_late(u, b, tc, 1, ns);
                    else { ns[gi] = 3 - sa[gi]; emit_late(u, b, d, 1, ns); }
                  } else {
                    emit_late(u, b, tc, 1, sa);
                    emit_late(u, b, d, 1, sa);
                  }
                }
              } else {
                for (int mv = 0; mv < 4; ++mv) {
                  int nbx = bx + DX[mv], nby = by + DY[mv];
                  if (nbx < 0 || nbx >= W || nby < 0 || nby >= H) continue;
                  int nbc = nby * W + nbx;
                  if (pd == 0 && IS_PD[nbc]) continue;
                  int dc[2] = {d, -1}, ndc_cnt = 1;
                  if (tst(AURA[b], d)) {
                    int ndx = dx + DX[mv], ndy = dy + DY[mv];
                    if (ndx >= 0 && ndx < W && ndy >= 0 && ndy < H && !(pd == 0 && IS_PD[ndy * W + ndx]))
                      dc[ndc_cnt++] = ndy * W + ndx;
                  }
                  if (DY[mv] == 0) {
                    int dir = DX[mv]; // -1 (L) or +1 (R)
                    int src_x = (dir == 1) ? 5 : 8;
                    int dst_col = (dir == 1) ? 0 : 1;
                    int exit_col = (dir == 1) ? 1 : 0;
                    int in_allow = 0, out_crate = 0;
                    for (int r = 0; r < 3; ++r) {
                      int sc = (2 + r) * W + src_x;
                      if (!(src_x == 8 && pd == 0) && tst(AURA[b], sc) && b != sc && d != sc)
                        in_allow |= (1 << r);
                      int ec = gcell(exit_col, r);
                      if (sa[exit_col * 3 + r] == 1 && tst(AURA[b], ec))
                        out_crate |= (1 << r);
                    }
                    for (int di_i = 0; di_i < ndc_cnt; ++di_i) {
                      int ndc = dc[di_i];
                      if (ndc == nbc) continue;
                      // Note: when dir == +1 and pd == 0, (8, 2..4) are closed purple doors -> ALL blocked!
                      for (int bm = 0; bm < 8; ++bm) {
                        if (dir == 1 && pd == 0 && bm != out_crate) continue;
                        if ((bm & ~out_crate) != 0) continue;
                        for (int im = 0; im < 8; ++im) {
                          if ((im & ~in_allow) != 0) continue;
                          int cs[6]; memcpy(cs, sa, sizeof(sa));
                          bool ch[6];
                          for (int k = 0; k < 6; ++k)
                            ch[k] = (cs[k] == 1) && tst(AURA[b], gcell(k / 3, k % 3));
                          bool in_p[3] = {(bool)(im & 1), (bool)(im & 2), (bool)(im & 4)};
                          int cb = b, cd = d;
                          bool bd = false, dd = (ndc == d), chg = true;
                          while (chg) {
                            chg = false;
                            for (int k = 0; k < 6; ++k) if (ch[k]) {
                              int col = k / 3, r = k % 3, ncol = col + dir;
                              int tc = (2 + r) * W + (6 + ncol);
                              if (ncol >= 0 && ncol < 2) {
                                int nk = ncol * 3 + r;
                                if (cs[nk] == 0 && cb != tc && cd != tc) {
                                  cs[nk] = 1; cs[k] = 0; ch[k] = false; chg = true;
                                }
                              } else {
                                if (!((bm >> r) & 1) && cb != tc && cd != tc) {
                                  cs[k] = 0; ch[k] = false; chg = true;
                                }
                              }
                            }
                            for (int r = 0; r < 3; ++r) if (in_p[r]) {
                              int nk = dst_col * 3 + r, tc = gcell(dst_col, r);
                              if (cs[nk] == 0 && cb != tc && cd != tc) {
                                cs[nk] = 1; in_p[r] = false; chg = true;
                              }
                            }
                            if (!dd) {
                              int gi = gidx_of(ndc);
                              if ((gi < 0 || cs[gi] == 0) && cb != ndc) { cd = ndc; dd = true; chg = true; }
                            }
                            if (!bd) {
                              int gi = gidx_of(nbc);
                              if ((gi < 0 || cs[gi] == 0) && cd != nbc) { cb = nbc; bd = true; chg = true; }
                            }
                          }
                          if (bd && dd) emit_late(u, cb, cd, 0, cs);
                        }
                      }
                    }
                  } else {
                    int dir = DY[mv]; // -1 (U) or +1 (D)
                    int src_y = (dir == 1) ? 1 : 5;
                    int dst_r = (dir == 1) ? 0 : 2;
                    int exit_r = (dir == 1) ? 2 : 0;
                    int in_allow = 0, out_crate = 0;
                    for (int col = 0; col < 2; ++col) {
                      int sc = src_y * W + (6 + col);
                      if (tst(AURA[b], sc) && b != sc && d != sc) in_allow |= (1 << col);
                      int ec = gcell(col, exit_r);
                      if (sa[col * 3 + exit_r] == 1 && tst(AURA[b], ec)) out_crate |= (1 << col);
                    }
                    for (int di_i = 0; di_i < ndc_cnt; ++di_i) {
                      int ndc = dc[di_i];
                      if (ndc == nbc) continue;
                      for (int bm = 0; bm < 4; ++bm) {
                        if ((bm & ~out_crate) != 0) continue;
                        for (int im = 0; im < 4; ++im) {
                          if ((im & ~in_allow) != 0) continue;
                          int cs[6]; memcpy(cs, sa, sizeof(sa));
                          bool ch[6];
                          for (int k = 0; k < 6; ++k)
                            ch[k] = (cs[k] == 1) && tst(AURA[b], gcell(k / 3, k % 3));
                          bool in_p[2] = {(bool)(im & 1), (bool)(im & 2)};
                          int cb = b, cd = d;
                          bool bd = false, dd = (ndc == d), chg = true;
                          while (chg) {
                            chg = false;
                            for (int k = 0; k < 6; ++k) if (ch[k]) {
                              int col = k / 3, r = k % 3, nr = r + dir;
                              int tc = (2 + nr) * W + (6 + col);
                              if (nr >= 0 && nr < 3) {
                                int nk = col * 3 + nr;
                                if (cs[nk] == 0 && cb != tc && cd != tc) {
                                  cs[nk] = 1; cs[k] = 0; ch[k] = false; chg = true;
                                }
                              } else {
                                if (!((bm >> col) & 1) && cb != tc && cd != tc) {
                                  cs[k] = 0; ch[k] = false; chg = true;
                                }
                              }
                            }
                            for (int col = 0; col < 2; ++col) if (in_p[col]) {
                              int nk = col * 3 + dst_r, tc = gcell(col, dst_r);
                              if (cs[nk] == 0 && cb != tc && cd != tc) {
                                cs[nk] = 1; in_p[col] = false; chg = true;
                              }
                            }
                            if (!dd) {
                              int gi = gidx_of(ndc);
                              if ((gi < 0 || cs[gi] == 0) && cb != ndc) { cd = ndc; dd = true; chg = true; }
                            }
                            if (!bd) {
                              int gi = gidx_of(nbc);
                              if ((gi < 0 || cs[gi] == 0) && cd != nbc) { cb = nbc; bd = true; chg = true; }
                            }
                          }
                          if (bd && dd) emit_late(u, cb, cd, 0, cs);
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  void build() {
    auto t0 = chrono::steady_clock::now();
    vector<uint32_t> deg(TOTAL + 1, 0);
    uint64_t nedges = 0;
    enum_all_edges([&](uint32_t, uint32_t v) { deg[v]++; nedges++; });
    for (uint32_t i = 1; i <= TOTAL; ++i) deg[i] += deg[i - 1];
    vector<uint32_t> inv(nedges), cur = deg;
    enum_all_edges([&](uint32_t u, uint32_t v) { inv[--cur[v]] = u; });

    dist.assign(TOTAL, 255);
    vector<uint32_t> q; q.reserve(TOTAL / 2);
    for (int gi = 0; gi < 2; ++gi) {
      int bg = GOALS[gi], dg = GOALS[1 - gi];
      for (int ah = 0; ah < 2; ++ah)
        for (int st = 0; st < 729; ++st) {
          int sa[6], tmp = st;
          for (int k = 0; k < 6; ++k) { sa[k] = tmp % 3; tmp /= 3; }
          bool c6 = (sa[0] != 0 && sa[1] != 0 && sa[2] != 0);
          for (int pd = 0; pd <= (c6 ? 1 : 0); ++pd) {
            uint32_t w = enc(bg, dg, ah, st, pd);
            if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
          }
        }
    }
    for (size_t qi = 0; qi < q.size(); ++qi) {
      uint32_t v = q[qi]; uint8_t nd = dist[v] + 1;
      for (uint32_t ei = cur[v]; ei < deg[v]; ++ei) {
        uint32_t u = inv[ei];
        if (dist[u] == 255) { dist[u] = nd; q.push_back(u); }
      }
    }
    double dt = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
    cout << "Built Exact-Crush Gateway67_15PDB: edges=" << nedges << " reachable=" << q.size() << "/" << TOTAL
      << " (" << fixed << setprecision(1) << (TOTAL / 1048576.0) << " MiB) in " << setprecision(2) << dt << "s\n";
  }
};
