// Splice public winning routes: shortest path through the union of their
// trajectories, plus bounded BFS "bridges" from any union state into any other.
//
// Every route's trajectory is a path of exact native states. Merging equal
// states gives a graph; its shortest start-to-win path recombines prefixes and
// suffixes of different routes wherever they meet. A bridge search then runs a
// bounded BFS from each union state u (cost g(u) from the start) and looks for
// any union state v with a known cost-to-win c(v); g(u) + d + c(v) below the
// incumbent is a shorter candidate. Improvements are folded back in and the
// search repeats.
//
// Input (stdin): part w h depth node_cap threads n_routes, h grid rows, then
// n_routes routes, one per line. Output: JSON lines. Every candidate printed
// here must still be replayed by the Python oracles and the original build.
#define main soko_engine_main
#include "../../cpp/soko_engine.cpp"
#undef main

#include <atomic>
#include <mutex>

struct Union {
    const LevelMeta& M;
    vector<DynState> states;
    vector<vector<pair<int, char>>> out;   // edges u -> v with key
    unordered_map<uint64_t, vector<int>> index;
    int win_id = -1;                        // all winning states share this sink
    explicit Union(const LevelMeta& m) : M(m) {}
    int find(const DynState& s) const {
        auto it = index.find(s.hash64(M.n, M.has_bard));
        if (it == index.end()) return -1;
        for (int id : it->second) if (states[id].eq(s, M.n, M.has_bard)) return id;
        return -1;
    }
    int intern(const DynState& s) {
        int id = find(s);
        if (id >= 0) return id;
        id = (int)states.size();
        states.push_back(s); out.emplace_back();
        index[s.hash64(M.n, M.has_bard)].push_back(id);
        return id;
    }
    bool add_route(const DynState& s0, const string& route) {
        DynState cur = s0;
        int u = intern(cur);
        for (size_t i = 0; i < route.size(); ++i) {
            int res = step_state(M, cur, d_idx(route[i]), false);
            if (res < 0) return false;
            bool last = i + 1 == route.size();
            if (res == 1 && !last) return false;  // premature win
            if (last && res != 1) return false;
            int v;
            if (res == 1) { if (win_id < 0) { win_id = (int)states.size(); states.push_back(cur); out.emplace_back(); } v = win_id; }
            else v = intern(cur);
            out[u].push_back({v, route[i]});
            u = v;
        }
        return true;
    }
};

int main() {
    int part, w, h, depth, threads, n_routes; size_t cap;
    cin >> part >> w >> h >> depth >> cap >> threads >> n_routes;
    vector<string> rows(h);
    for (auto& r : rows) cin >> r;
    vector<string> routes(n_routes);
    for (auto& r : routes) cin >> r;
    auto [M, s0] = parse_level(part, w, h, rows);
    Union U(M);
    int accepted = 0;
    for (auto& r : routes) accepted += U.add_route(s0, r);
    cout << "{\"routes\":" << n_routes << ",\"accepted\":" << accepted << ",\"union_states\":" << U.states.size() << "}\n" << flush;
    auto t0 = chrono::steady_clock::now();
    for (int round = 0;; ++round) {
        const int N = (int)U.states.size();
        // Forward BFS from the start over union edges, keeping one parent per node.
        vector<int> g(N, INT_MAX), par(N, -1); vector<char> pk(N, 0);
        deque<int> q; int start = U.find(s0); g[start] = 0; q.push_back(start);
        while (!q.empty()) { int u = q.front(); q.pop_front();
            for (auto [v, k] : U.out[u]) if (g[v] == INT_MAX) { g[v] = g[u] + 1; par[v] = u; pk[v] = k; q.push_back(v); } }
        // Reverse BFS from the win sink gives the cost to win and the next key.
        vector<vector<pair<int, char>>> in(N);
        for (int u = 0; u < N; ++u) for (auto [v, k] : U.out[u]) in[v].push_back({u, k});
        vector<int> c(N, INT_MAX), nxt(N, -1); vector<char> nk(N, 0);
        c[U.win_id] = 0; q.push_back(U.win_id);
        while (!q.empty()) { int v = q.front(); q.pop_front();
            for (auto [u, k] : in[v]) if (c[u] == INT_MAX) { c[u] = c[v] + 1; nxt[u] = v; nk[u] = k; q.push_back(u); } }
        int best = g[U.win_id];
        auto suffix_from = [&](int v) { string s; while (v != U.win_id) { s.push_back(nk[v]); v = nxt[v]; } return s; };
        auto prefix_to = [&](int u) { string s; while (u != start) { s.push_back(pk[u]); u = par[u]; } reverse(s.begin(), s.end()); return s; };
        string incumbent = prefix_to(U.win_id);
        double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        cout << "{\"round\":" << round << ",\"union_shortest\":" << best << ",\"union_states\":" << N
             << ",\"seconds\":" << secs << ",\"route\":\"" << incumbent << "\"}\n" << flush;
        if (depth <= 0) return 0;
        // Bridges: from every union node u with g(u) + c-lower-bound room, bounded BFS.
        atomic<int> next_u{0}; mutex mu;
        int best_total = best; string best_route;
        auto worker = [&]() {
            for (int u; (u = next_u.fetch_add(1)) < N;) {
                if (u == U.win_id || g[u] == INT_MAX) continue;
                if (g[u] + 1 >= best_total) continue;
                struct Node { DynState s; int prev; char mv; int d; };
                vector<Node> bq; bq.push_back({U.states[u], -1, 0, 0});
                unordered_map<uint64_t, vector<int>> seen; seen[U.states[u].hash64(M.n, M.has_bard)].push_back(0);
                int local_best = INT_MAX; string local_route;
                for (size_t qi = 0; qi < bq.size(); ++qi) {
                    int dd = bq[qi].d;
                    if (dd >= depth || g[u] + dd + 1 >= best_total) break;
                    for (int mv = 0; mv < 5; ++mv) {
                        DynState ns = bq[qi].s;
                        int res = step_state(M, ns, mv, true);
                        if (res < 0) continue;
                        int d1 = dd + 1;
                        auto path = [&]() { string m(1, DCH[mv]); for (int cur = (int)qi; cur > 0; cur = bq[cur].prev) m.push_back(bq[cur].mv); reverse(m.begin(), m.end()); return m; };
                        if (res == 1) {
                            int tot = g[u] + d1;
                            if (tot < local_best) { local_best = tot; local_route = prefix_to(u) + path(); }
                            continue;
                        }
                        int v = U.find(ns);
                        if (v >= 0 && c[v] != INT_MAX) {
                            int tot = g[u] + d1 + c[v];
                            if (tot < local_best) { local_best = tot; local_route = prefix_to(u) + path() + suffix_from(v); }
                        }
                        if (d1 < depth && bq.size() < cap) {
                            auto& b = seen[ns.hash64(M.n, M.has_bard)];
                            bool dup = false; for (int vi : b) if (ns.eq(bq[vi].s, M.n, M.has_bard)) { dup = true; break; }
                            if (!dup) { b.push_back((int)bq.size()); bq.push_back({ns, (int)qi, DCH[mv], d1}); }
                        }
                    }
                }
                if (local_best < INT_MAX) {
                    lock_guard<mutex> lk(mu);
                    if (local_best < best_total) { best_total = local_best; best_route = local_route; }
                }
            }
        };
        vector<thread> pool; for (int t = 0; t < threads; ++t) pool.emplace_back(worker);
        for (auto& t : pool) t.join();
        if (best_route.empty()) {
            cout << "{\"final\":" << best << ",\"bridge_depth\":" << depth << ",\"seconds\":"
                 << chrono::duration<double>(chrono::steady_clock::now() - t0).count() << "}\n";
            return 0;
        }
        cout << "{\"bridge_found\":" << best_total << ",\"route\":\"" << best_route << "\"}\n" << flush;
        if (!U.add_route(s0, best_route)) { cout << "{\"error\":\"bridge route failed replay\"}\n"; return 1; }
    }
}
