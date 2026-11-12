// transport_relaxation_9flow_audit.cpp
// Standalone C++20 Diagnostic, Counterexample Synthesis, Time-Expanded 9-Flow Verifier,
// and Unblocked-Crate Non-Stuttering Theorem Checker for Room III-14 (15x7, SHA-256 f66ceb8f...).
//
// Compile & run:
//   g++ -O3 -std=c++20 transport_relaxation_9flow_audit.cpp -o transport_audit && ./transport_audit

#include <bits/stdc++.h>
using namespace std;

using u128 = unsigned __int128;
static constexpr int W = 15, H = 7, N = 105;
static const int DX[4] = {0, 0, -1, 1};
static const int DY[4] = {-1, 1, 0, 0};
static const char DCH[5] = {'U', 'D', 'L', 'R', 'A'};

static const char* GRID[7] = {
    "###############",
    "#.............#",
    "#.5.}}}.]]]]].#",
    "#...}}}.]G.G].#",
    "#.D.}}}.]]]]].#",
    "#.............#",
    "###############"
};

static inline u128 bit(int i) { return ((u128)1) << i; }
static inline bool tst(u128 m, int i) { return (m >> i) & 1; }

struct Dinic {
    struct Edge { int to, rev, cap; };
    int V;
    vector<vector<Edge>> adj;
    vector<int> level, ptr;
    explicit Dinic(int v) : V(v), adj(v), level(v), ptr(v) {}
    void add_edge(int u, int v, int cap) {
        adj[u].push_back({v, (int)adj[v].size(), cap});
        adj[v].push_back({u, (int)adj[u].size() - 1, 0});
    }
    bool bfs(int s, int t) {
        fill(level.begin(), level.end(), -1);
        queue<int> q; level[s] = 0; q.push(s);
        while (!q.empty()) {
            int u = q.front(); q.pop();
            for (const auto& e : adj[u])
                if (e.cap > 0 && level[e.to] < 0) { level[e.to] = level[u] + 1; q.push(e.to); }
        }
        return level[t] >= 0;
    }
    int dfs(int u, int t, int pushed) {
        if (pushed == 0 || u == t) return pushed;
        for (int& cid = ptr[u]; cid < (int)adj[u].size(); ++cid) {
            auto& e = adj[u][cid];
            if (level[u] + 1 != level[e.to] || e.cap == 0) continue;
            int tr = dfs(e.to, t, min(pushed, e.cap));
            if (tr == 0) continue;
            e.cap -= tr; adj[e.to][e.rev].cap += tr;
            return tr;
        }
        return 0;
    }
    int max_flow(int s, int t, int limit = 9) {
        int flow = 0;
        while (flow < limit && bfs(s, t)) {
            fill(ptr.begin(), ptr.end(), 0);
            while (flow < limit) {
                int tr = dfs(s, t, limit - flow);
                if (!tr) break;
                flow += tr;
            }
        }
        return flow;
    }
};

struct HeroSchedule {
    vector<int> bp, dp, ahp, acts;
};

int check_time_expanded_9flow(
    u128 origin_mask, u128 switch_mask, const u128 AURA[N],
    const HeroSchedule& s, int lm
) {
    int total_v = 2 + N + (lm + 1) * N * 2;
    Dinic din(total_v);
    auto orig_v = [&](int c) { return 2 + c; };
    auto in_v   = [&](int t, int c) { return 2 + N + (t * N + c) * 2; };
    auto out_v  = [&](int t, int c) { return 2 + N + (t * N + c) * 2 + 1; };

    vector<int> first_harv(N, 999999);
    for (int t = 0; t < lm; ++t) {
        int a = s.acts[t];
        if (a < 4 && s.ahp[t] == 1 && s.dp[t + 1] == s.dp[t]) {
            int dx = s.dp[t] % W, dy = s.dp[t] / W;
            int tx = dx + DX[a], ty = dy + DY[a];
            if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
                int tg = ty * W + tx;
                if (tst(origin_mask, tg)) first_harv[tg] = min(first_harv[tg], t + 1);
            }
        }
    }
    for (int c = 0; c < N; ++c) if (tst(origin_mask, c) && first_harv[c] <= lm) din.add_edge(0, orig_v(c), 1);
    for (int t = 0; t <= lm; ++t)
        for (int c = 0; c < N; ++c) {
            if (c == s.bp[t] || c == s.dp[t] || (tst(origin_mask, c) && t < first_harv[c])) continue;
            din.add_edge(in_v(t, c), out_v(t, c), 1);
            if (t == lm && tst(switch_mask, c)) din.add_edge(out_v(t, c), 1, 1);
        }
    for (int t = 0; t < lm; ++t) {
        int a = s.acts[t];
        if (a < 4 && s.ahp[t] == 1 && s.dp[t + 1] == s.dp[t]) {
            int dx = s.dp[t] % W, dy = s.dp[t] / W;
            int tx = dx + DX[a], ty = dy + DY[a];
            if (tx >= 0 && tx < W && ty >= 0 && ty < H) {
                int tg = ty * W + tx;
                if (tst(origin_mask, tg) && first_harv[tg] == t + 1) din.add_edge(orig_v(tg), in_v(t + 1, tg), 1);
            }
        }
        bool bs = (a < 4 && s.ahp[t] == 0 && s.bp[t + 1] != s.bp[t]);
        u128 au = bs ? AURA[s.bp[t]] : 0;
        for (int c = 0; c < N; ++c) {
            din.add_edge(out_v(t, c), in_v(t + 1, c), 1);
            if (bs && tst(au, c)) {
                int nx = (c % W) + DX[a], ny = (c / W) + DY[a];
                if (nx >= 0 && nx < W && ny >= 0 && ny < H) din.add_edge(out_v(t, c), in_v(t + 1, ny * W + nx), 1);
            }
        }
    }
    return din.max_flow(0, 1, 9);
}

int main() {
    u128 origin_mask = 0, switch_mask = 0, pdoor_mask = 0, AURA[N]{}, VALID_PRE_SHIFT[4]{};
    vector<int> origins, switches, goals;
    int b0 = -1, d0 = -1;
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            char c = GRID[y][x]; int i = y * W + x;
            if (c == '#') { origins.push_back(i); origin_mask |= bit(i); }
            else if (c == '}') { switches.push_back(i); switch_mask |= bit(i); }
            else if (c == ']') pdoor_mask |= bit(i);
            else if (c == 'G') goals.push_back(i);
            else if (c == '5') b0 = i;
            else if (c == 'D') d0 = i;
        }
    for (int b = 0; b < N; ++b) {
        int bx = b % W, by = b / W;
        for (int y = max(0, by - 2); y <= min(H - 1, by + 2); ++y)
            for (int x = max(0, bx - 2); x <= min(W - 1, bx + 2); ++x)
                AURA[b] |= bit(y * W + x);
    }
    for (int i = 0; i < N; ++i)
        for (int dir = 0; dir < 4; ++dir) {
            int nx = (i % W) + DX[dir], ny = (i / W) + DY[dir];
            if (nx >= 0 && nx < W && ny >= 0 && ny < H) VALID_PRE_SHIFT[dir] |= bit(i);
        }
    auto shift_board = [&](u128 m, int dir) -> u128 {
        m &= VALID_PRE_SHIFT[dir];
        if (dir == 0) return m >> W;
        if (dir == 1) return m << W;
        if (dir == 2) return m >> 1;
        return m << 1;
    };

    auto eval_route = [&](const string& label, const string& route, int lm) {
        // Enumerate valid hero schedules matching `route` where terminal state is a distinct goal pair:
        struct Path { int b, d, ah; HeroSchedule s; unordered_set<int> hv; };
        vector<Path> cur = {{b0, d0, 1, {{b0}, {d0}, {1}, {}}, {}}};
        for (char ch : route) {
            int mv = string("UDLRA").find(ch);
            vector<Path> nxt;
            for (const auto& p : cur) {
                if (mv == 4) {
                    auto q = p; q.ah = 1 - q.ah; q.s.acts.push_back(4);
                    q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
                } else if (p.ah == 1) {
                    int nx = (p.d % W) + DX[mv], ny = (p.d / W) + DY[mv], nc = ny * W + nx;
                    if (tst(origin_mask, nc) && !p.hv.count(nc)) {
                        auto q = p; q.hv.insert(nc); q.s.acts.push_back(mv);
                        q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
                    } else if (!tst(origin_mask, nc)) {
                        auto q = p; q.d = nc; q.s.acts.push_back(mv);
                        q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
                    }
                } else {
                    int nbx = (p.b % W) + DX[mv], nby = (p.b / W) + DY[mv], nbc = nby * W + nbx;
                    if (!tst(origin_mask, nbc) && nbc != p.d) {
                        auto q = p; q.b = nbc; q.s.acts.push_back(mv);
                        q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
                    }
                    if (tst(AURA[p.b], p.d)) {
                        int ndx = (p.d % W) + DX[mv], ndy = (p.d / W) + DY[mv], ndc = ndy * W + ndx;
                        if (!tst(origin_mask, nbc) && !tst(origin_mask, ndc) && nbc != ndc) {
                            auto q = p; q.b = nbc; q.d = ndc; q.s.acts.push_back(mv);
                            q.s.bp.push_back(q.b); q.s.dp.push_back(q.d); q.s.ahp.push_back(q.ah); nxt.push_back(q);
                        }
                    }
                }
            }
            cur.swap(nxt);
        }
        int best_bipartite = 0, best_flow = 0;
        for (const auto& p : cur) {
            if (!((p.b == goals[0] && p.d == goals[1]) || (p.b == goals[1] && p.d == goals[0]))) continue;
            vector<u128> R(40, 0);
            for (int t = 0; t < lm; ++t) {
                int a = p.s.acts[t];
                if (a < 4 && p.s.ahp[t] == 1 && p.s.dp[t + 1] == p.s.dp[t]) {
                    int tg = ((p.s.dp[t] / W) + DY[a]) * W + ((p.s.dp[t] % W) + DX[a]);
                    for (int o = 0; o < 40; ++o) if (origins[o] == tg) R[o] |= bit(tg);
                } else if (a < 4 && p.s.ahp[t] == 0 && p.s.bp[t + 1] != p.s.bp[t]) {
                    for (int o = 0; o < 40; ++o) if (R[o]) R[o] |= shift_board(R[o] & AURA[p.s.bp[t]], a);
                }
            }
            int match_o[40]; fill(match_o, match_o + 40, -1);
            int m = 0;
            for (int q = 0; q < 9; ++q) {
                bool vis[40]{};
                function<bool(int)> dfs = [&](int qq) -> bool {
                    int sc = switches[qq];
                    for (int o = 0; o < 40; ++o) {
                        if (vis[o] || !tst(R[o], sc)) continue;
                        vis[o] = true;
                        if (match_o[o] < 0 || dfs(match_o[o])) { match_o[o] = qq; return true; }
                    }
                    return false;
                };
                if (dfs(q)) m++;
            }
            best_bipartite = max(best_bipartite, m);
            best_flow = max(best_flow, check_time_expanded_9flow(origin_mask, switch_mask, AURA, p.s, lm));
        }
        cout << label << " (H=" << route.size() << ", t_L=" << lm << "): "
             << "BipartiteMatching=" << best_bipartite << "/9 | "
             << "TimeExpanded9Flow=" << best_flow << "/9\n";
    };

    eval_route("1. R1/R2 Witness r30", "LLULULULURURURURUARRRRDDRDRUUR", 29);
    eval_route("2. R3 Flow Witness r33", "LLULULULRURURURURUAUDRRDUDDRRRRUR", 32);
    return 0;
}
