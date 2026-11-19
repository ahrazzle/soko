// Long-range trajectory shortcut search over the native engine.
//
// For every prefix position L of a winning route, run an exact breadth-first
// search from the trajectory state at L (depth <= D, node cap per L) and look
// up each reached state among ALL later trajectory states k. A state reached at
// depth d that equals traj[k] with k - L > d shortens the route by k - L - d.
// A winning state reached early also counts. Unlike exact_window_shortcut, the
// replaced segment is not limited to the BFS depth, so a short detour can
// replace a long stretch of the reference route.
//
// Input (stdin): part w h depth node_cap threads, then h grid rows, then route.
// Output: one JSON line per applied improvement and a final summary line.
// Every candidate this prints must still be replayed by the Python oracles and
// the pinned original build; this tool only proposes routes.
#define main soko_engine_main
#include "../../cpp/soko_engine.cpp"
#undef main

#include <atomic>
#include <mutex>

struct Hit { int gain = 0, L = -1, k = -1; string mid; };

static vector<DynState> trajectory(const LevelMeta& M, const DynState& s0, const string& route) {
    vector<DynState> traj = {s0};
    for (char c : route) { DynState nx = traj.back(); step_state(M, nx, d_idx(c), false); traj.push_back(nx); }
    return traj;
}

static Hit search_from(const LevelMeta& M, const vector<DynState>& traj,
                       const unordered_map<uint64_t, vector<int>>& index,
                       int L, int depth, size_t cap) {
    const int N = (int)traj.size() - 1;
    struct Node { DynState s; int prev; char mv; int d; };
    vector<Node> q; q.reserve(min<size_t>(cap, 1 << 20));
    q.push_back({traj[L], -1, 0, 0});
    unordered_map<uint64_t, vector<int>> seen;
    seen[traj[L].hash64(M.n, M.has_bard)].push_back(0);
    Hit best;
    auto path_to = [&](int qi, char last) {
        string mid(1, last);
        for (int cur = qi; cur > 0; cur = q[cur].prev) mid.push_back(q[cur].mv);
        reverse(mid.begin(), mid.end());
        return mid;
    };
    for (size_t qi = 0; qi < q.size(); ++qi) {
        if (q[qi].d >= depth) break;
        for (int mv = 0; mv < 5; ++mv) {
            DynState ns = q[qi].s;
            int res = step_state(M, ns, mv, true);
            if (res < 0) continue;
            int d = q[qi].d + 1;
            if (res == 1) {
                int gain = N - (L + d);
                if (gain > best.gain) best = {gain, L, N, path_to((int)qi, DCH[mv])};
                continue;
            }
            uint64_t h = ns.hash64(M.n, M.has_bard);
            auto it = index.find(h);
            if (it != index.end())
                for (int k : it->second)
                    if (k - L - d > best.gain && ns.eq(traj[k], M.n, M.has_bard))
                        best = {k - L - d, L, k, path_to((int)qi, DCH[mv])};
            if (d < depth && q.size() < cap) {
                auto& bucket = seen[h];
                bool dup = false;
                for (int vi : bucket) if (ns.eq(q[vi].s, M.n, M.has_bard)) { dup = true; break; }
                if (!dup) { bucket.push_back((int)q.size()); q.push_back({ns, (int)qi, DCH[mv], d}); }
            }
        }
    }
    return best;
}

int main() {
    int part, w, h, depth; size_t cap; int threads;
    cin >> part >> w >> h >> depth >> cap >> threads;
    vector<string> rows(h);
    for (auto& r : rows) cin >> r;
    string route; cin >> route;
    auto [M, s0] = parse_level(part, w, h, rows);
    auto t0 = chrono::steady_clock::now();
    int rounds = 0;
    while (true) {
        auto traj = trajectory(M, s0, route);
        const int N = (int)route.size();
        if (!check_win(M, traj.back())) { cout << "{\"error\":\"route_does_not_win\"}\n"; return 1; }
        unordered_map<uint64_t, vector<int>> index;
        for (int k = 0; k <= N; ++k) index[traj[k].hash64(M.n, M.has_bard)].push_back(k);
        atomic<int> next{0};
        mutex mu;
        Hit best;
        auto worker = [&]() {
            for (int L; (L = next.fetch_add(1)) < N;) {
                Hit hit = search_from(M, traj, index, L, depth, cap);
                lock_guard<mutex> g(mu);
                if (hit.gain > best.gain) best = hit;
            }
        };
        vector<thread> pool;
        for (int t = 0; t < threads; ++t) pool.emplace_back(worker);
        for (auto& t : pool) t.join();
        double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        if (best.gain <= 0) {
            cout << "{\"final_len\":" << N << ",\"rounds\":" << rounds << ",\"seconds\":" << secs
                 << ",\"route\":\"" << route << "\"}\n";
            return 0;
        }
        route = route.substr(0, best.L) + best.mid + route.substr(best.k);
        ++rounds;
        cout << "{\"round\":" << rounds << ",\"gain\":" << best.gain << ",\"L\":" << best.L << ",\"k\":" << best.k
             << ",\"mid\":\"" << best.mid << "\",\"len\":" << route.size() << ",\"seconds\":" << secs
             << ",\"route\":\"" << route << "\"}\n" << flush;
    }
}
