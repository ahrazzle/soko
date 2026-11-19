#pragma once
#include "iii14_15x7_core.hpp"

// ============================================================================
// PDB 3 & 4: RowStrip15PDB under Exact Crush Semantics
//   Notice line 313 of oracle.py: if row_all3 == false, all_sw is DEFINITELY false,
//   so doors_open AFTER the move MUST be 0 (and any hero on PDOOR_MASK is crushed)!
// ============================================================================
struct RowStrip15PDB {
  int Y0;
  static constexpr uint32_t TOTAL = 105 * 105 * 2 * 81 * 2;
  vector<uint8_t> dist;
  static inline uint32_t enc(int b, int d, int ah, int st, int pd) {
    return (((uint32_t(b) * 105 + d) * 2 + ah) * 81 + st) * 2 + pd;
  }
  inline int lookup(const CState& s) const {
    int st = 0, p3 = 1;
    for (int j = 0; j < 4; ++j) {
      int c = Y0 * W + (4 + j);
      st += (tst(s.crates, c) ? 1 : (tst(s.walls, c) ? 2 : 0)) * p3; p3 *= 3;
    }
    uint8_t d = dist[enc(s.by * W + s.bx, s.dy * W + s.dx, s.ah, st, s.doors_open)];
    return d == 255 ? 999 : (int)d;
  }
  void build(int y0) {
    Y0 = y0;
    vector<pair<uint32_t, uint32_t>> edges; edges.reserve(42000000);
    auto emit_late = [&](uint32_t u, int nb, int nd, int nah, const int ns[4]) {
      if (nb == nd) return;
      for (int j = 0; j < 4; ++j) if (ns[j] != 0 && (nb == Y0 * W + 4 + j || nd == Y0 * W + 4 + j)) return;
      int nst = ns[0] + 3 * ns[1] + 9 * ns[2] + 27 * ns[3];
      bool r3 = true;
      for (int j = 0; j < 3; ++j) { int c = Y0 * W + 4 + j; if (ns[j] == 0 && nb != c && nd != c) r3 = false; }
      bool hpd = tst(PDOOR_MASK, nb) || tst(PDOOR_MASK, nd);
      if (r3) {
        edges.push_back({u, enc(nb, nd, nah, nst, 1)});
        if (!hpd) edges.push_back({u, enc(nb, nd, nah, nst, 0)});
      } else {
        // Exact Crush Rule: if row_all3 is false, doors_open MUST become 0, and if hpd is true, hero is crushed!
        if (!hpd) edges.push_back({u, enc(nb, nd, nah, nst, 0)});
      }
    };
    for (int b = 0; b < N; ++b)
      for (int d = 0; d < N; ++d) if (b != d)
        for (int ah = 0; ah < 2; ++ah)
          for (int st = 0; st < 81; ++st) {
            int sa[4] = {st % 3, (st / 3) % 3, (st / 9) % 3, (st / 27) % 3};
            bool bad = false;
            for (int j = 0; j < 4; ++j) if (sa[j] && (b == Y0 * W + 4 + j || d == Y0 * W + 4 + j)) bad = true;
            if (bad) continue;
            bool r3_pre = true;
            for (int j = 0; j < 3; ++j) { int c = Y0 * W + 4 + j; if (sa[j] == 0 && b != c && d != c) r3_pre = false; }
            for (int pd = 0; pd < 2; ++pd) {
              if (pd == 0 && (tst(PDOOR_MASK, b) || tst(PDOOR_MASK, d))) continue;
              if (pd == 1 && !r3_pre) continue; // pd==1 requires row_all3!
              uint32_t u = enc(b, d, ah, st, pd);
              emit_late(u, b, d, 1 - ah, sa);
              int bx = b % W, by = b / W, dx = d % W, dy = d / W;
              if (ah == 1) {
                for (int mv = 0; mv < 4; ++mv) {
                  int tx = dx + DX[mv], ty = dy + DY[mv];
                  if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
                  int tc = ty * W + tx;
                  if (tc == b || (pd == 0 && tst(PDOOR_MASK, tc))) continue;
                  if (ty == Y0 && tx >= 4 && tx <= 7) {
                    int j = tx - 4, ns[4] = {sa[0], sa[1], sa[2], sa[3]};
                    if (sa[j] == 0) emit_late(u, b, tc, 1, ns);
                    else { ns[j] = 3 - sa[j]; emit_late(u, b, d, 1, ns); }
                  } else { emit_late(u, b, tc, 1, sa); emit_late(u, b, d, 1, sa); }
                }
              } else {
                for (int mv = 0; mv < 4; ++mv) {
                  int nbx = bx + DX[mv], nby = by + DY[mv];
                  if (nbx < 0 || nbx >= W || nby < 0 || nby >= H) continue;
                  int nbc = nby * W + nbx;
                  if (pd == 0 && tst(PDOOR_MASK, nbc)) continue;
                  vector<int> dc = {d};
                  if (tst(AURA[b], d)) {
                    int ndx = dx + DX[mv], ndy = dy + DY[mv];
                    if (ndx >= 0 && ndx < W && ndy >= 0 && ndy < H && !(pd == 0 && tst(PDOOR_MASK, ndy * W + ndx)))
                      dc.push_back(ndy * W + ndx);
                  }
                  if (DY[mv] == 0) {
                    int dir = DX[mv];
                    for (int ndc : dc) if (ndc != nbc)
                      for (int eb = 0; eb < 2; ++eb) {
                        if (dir == 1 && pd == 0 && eb == 0) continue;
                        for (int ei = 0; ei < 2; ++ei) {
                          int cs[4] = {sa[0], sa[1], sa[2], sa[3]};
                          bool ch[4]; for (int j = 0; j < 4; ++j) ch[j] = (cs[j] == 1) && tst(AURA[b], Y0 * W + 4 + j);
                          int sx = (dir == 1) ? 3 : 8, dj = (dir == 1) ? 0 : 3;
                          bool hi = ei && tst(AURA[b], Y0 * W + sx) && b != Y0 * W + sx && d != Y0 * W + sx && !(sx == 8 && pd == 0);
                          if (ei && !hi) continue;
                          int cb = b, cd = d; bool bd = false, dd = (ndc == d), id = !hi, chg = true;
                          while (chg) {
                            chg = false;
                            for (int j = 0; j < 4; ++j) if (ch[j]) {
                              int nj = j + dir, tc = Y0 * W + 4 + nj;
                              if (nj >= 0 && nj < 4) { if (!cs[nj] && cb != tc && cd != tc) { cs[nj] = 1; cs[j] = 0; ch[j] = false; chg = true; } }
                              else if (!eb && cb != tc && cd != tc) { cs[j] = 0; ch[j] = false; chg = true; }
                            }
                            if (!id && !cs[dj] && cb != Y0 * W + 4 + dj && cd != Y0 * W + 4 + dj) { cs[dj] = 1; id = true; chg = true; }
                            if (!dd && !(ndc / W == Y0 && (ndc % W) >= 4 && (ndc % W) <= 7 && cs[(ndc % W) - 4]) && cb != ndc) { cd = ndc; dd = true; chg = true; }
                            if (!bd && !(nbc / W == Y0 && (nbc % W) >= 4 && (nbc % W) <= 7 && cs[(nbc % W) - 4]) && cd != nbc) { cb = nbc; bd = true; chg = true; }
                          }
                          if (bd && dd) emit_late(u, cb, cd, 0, cs);
                        }
                      }
                  } else {
                    int sy = Y0 - DY[mv], dy2 = Y0 + DY[mv];
                    for (int ndc : dc) if (ndc != nbc)
                      for (int om = 0; om < 16; ++om) {
                        bool imp = false;
                        for (int j = 0; j < 4; ++j) if ((om >> j) & 1) {
                          int c = Y0 * W + 4 + j, dc2 = dy2 * W + 4 + j;
                          if (sa[j] != 1 || !tst(AURA[b], c) || dy2 < 0 || dy2 >= H || dc2 == nbc || dc2 == ndc) imp = true;
                        }
                        if (imp) continue;
                        for (int im = 0; im < 16; ++im) {
                          int ns[4] = {sa[0], sa[1], sa[2], sa[3]};
                          for (int j = 0; j < 4; ++j) if ((om >> j) & 1) ns[j] = 0;
                          bool bi2 = false;
                          for (int j = 0; j < 4; ++j) if ((im >> j) & 1) {
                            int sc = sy * W + 4 + j, dc2 = Y0 * W + 4 + j;
                            if (sy < 0 || sy >= H || !tst(AURA[b], sc) || sc == b || sc == d || ns[j] || dc2 == nbc || dc2 == ndc) bi2 = true;
                            ns[j] = 1;
                          }
                          if (bi2) continue;
                          if ((nbc / W == Y0 && (nbc % W) >= 4 && (nbc % W) <= 7 && ns[(nbc % W) - 4]) ||
                            (ndc / W == Y0 && (ndc % W) >= 4 && (ndc % W) <= 7 && ns[(ndc % W) - 4])) continue;
                          emit_late(u, nbc, ndc, 0, ns);
                        }
                      }
                  }
                }
              }
            }
          }
    vector<uint32_t> deg(TOTAL + 1, 0);
    for (auto& e : edges) deg[e.second]++;
    for (uint32_t i = 1; i <= TOTAL; ++i) deg[i] += deg[i - 1];
    vector<uint32_t> inv(edges.size()), cur = deg;
    for (auto& e : edges) inv[--cur[e.second]] = e.first;
    vector<pair<uint32_t, uint32_t>>().swap(edges);
    dist.assign(TOTAL, 255);
    vector<uint32_t> q; q.reserve(TOTAL / 2);
    for (int gi = 0; gi < 2; ++gi) {
      int bg = GOALS[gi], dg = GOALS[1 - gi];
      for (int ah = 0; ah < 2; ++ah)
        for (int st = 0; st < 81; ++st) {
          int sa[4] = {st % 3, (st / 3) % 3, (st / 9) % 3, (st / 27) % 3};
          bool bad = false, r3 = true;
          for (int j = 0; j < 4; ++j) if (sa[j] && (bg == Y0 * W + 4 + j || dg == Y0 * W + 4 + j)) bad = true;
          for (int j = 0; j < 3; ++j) if (sa[j] == 0) r3 = false;
          if (bad) continue;
          for (int pd = 0; pd <= (r3 ? 1 : 0); ++pd) {
            uint32_t w = enc(bg, dg, ah, st, pd);
            if (dist[w] == 255) { dist[w] = 0; q.push_back(w); }
          }
        }
    }
    for (size_t qi = 0; qi < q.size(); ++qi) {
      uint32_t v = q[qi]; uint8_t nd = dist[v] + 1;
      for (uint32_t ei = cur[v]; ei < deg[v]; ++ei) { uint32_t u = inv[ei]; if (dist[u] == 255) { dist[u] = nd; q.push_back(u); } }
    }
  }
};
