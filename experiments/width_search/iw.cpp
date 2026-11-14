// Iterated Width, IW(k), on the native engine (Lipovetzky & Geffner 2012; the
// same search reached strong Atari scores in Lipovetzky, Ramirez & Geffner 2015).
//
// Breadth-first search that keeps a generated state only if it makes some tuple
// of at most k atoms true for the first time. An atom is one (cell, object) fact,
// one Bard note cell, or one door flag. Duplicates fall out for free, because a
// repeated state has no new tuple. The number of kept states is bounded by the
// number of tuples, so IW(2) is cheap even where exact BFS is hopeless, and it
// does not use a heuristic, so it is not stuck on heuristic plateaus.
//
// IW(k) is breadth-first, so the first route found is the shortest one among the
// states it kept. It is not a proof of anything: pruning can cut the optimal
// route. Every route printed here is only a candidate, to be replayed by the
// Python oracles and the pinned original build.
//
// Input (stdin): part w h k max_depth, then h grid rows.
// Output: one JSON line per depth, then the result.
#define main soko_engine_main
#include "../../cpp/soko_engine.cpp"
#undef main

int main() {
    int part, w, h, K, max_depth;
    cin >> part >> w >> h >> K >> max_depth;
    vector<string> rows(h);
    for (auto& r : rows) cin >> r;
    auto [M, s0] = parse_level(part, w, h, rows);
    bool has_druid = false;
    for (int i = 0; i < M.n; ++i) if (s0.obj[i] == 6 || s0.obj[i] == 12) has_druid = true;

    // Atom ids: cell*32 + object, then notes, then two flag blocks.
    const int A = M.n * 32 + M.n + 2 * 256;
    auto atoms_of = [&](const DynState& s, vector<int>& out) {
        out.clear();
        for (int i = 0; i < M.n; ++i) {
            uint8_t v = s.obj[i];
            if (v == 0) continue;
            if (v == 13 && !has_druid) continue;  // walls cannot change without a druid
            out.push_back(i * 32 + (v & 31));
        }
        if (M.has_bard) for (int i = 0; i < M.n; ++i) if (s.has_note(i)) out.push_back(M.n * 32 + i);
        out.push_back(M.n * 33 + s.y_open);
        out.push_back(M.n * 33 + 256 + s.p_open);
    };
    vector<uint8_t> seen1(A, 0);
    vector<uint64_t> seen2;
    if (K >= 2) seen2.assign(((size_t)A * A + 63) / 64, 0);
    auto test_and_mark = [&](const vector<int>& at) {
        bool novel = false;
        for (int a : at) if (!seen1[a]) { novel = true; break; }
        if (!novel && K >= 2) {
            for (size_t x = 0; x < at.size() && !novel; ++x)
                for (size_t y = x + 1; y < at.size(); ++y) {
                    size_t idx = (size_t)min(at[x], at[y]) * A + max(at[x], at[y]);
                    if (!((seen2[idx >> 6] >> (idx & 63)) & 1)) { novel = true; break; }
                }
        }
        if (!novel) return false;
        for (int a : at) seen1[a] = 1;
        if (K >= 2)
            for (size_t x = 0; x < at.size(); ++x)
                for (size_t y = x + 1; y < at.size(); ++y) {
                    size_t idx = (size_t)min(at[x], at[y]) * A + max(at[x], at[y]);
                    seen2[idx >> 6] |= 1ULL << (idx & 63);
                }
        return true;
    };

    struct Trace { int parent; char mv; };
    vector<vector<Trace>> trace(1, vector<Trace>{{-1, 0}});
    vector<DynState> cur = {s0};
    vector<int> at;
    atoms_of(s0, at); test_and_mark(at);
    auto t0 = chrono::steady_clock::now();
    size_t total = 1;
    for (int g = 0; g < max_depth; ++g) {
        vector<DynState> next; vector<Trace> tnext;
        for (size_t i = 0; i < cur.size(); ++i)
            for (int mv = 0; mv < 5; ++mv) {
                DynState ns = cur[i];
                int res = step_state(M, ns, mv, true);
                if (res < 0) continue;
                if (res == 1) {
                    string route(1, DCH[mv]);
                    int li = (int)i;
                    for (int lg = g; lg > 0; --lg) { route.push_back(trace[lg][li].mv); li = trace[lg][li].parent; }
                    reverse(route.begin(), route.end());
                    double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
                    cout << "{\"found\":" << route.size() << ",\"k\":" << K << ",\"kept_states\":" << total
                         << ",\"seconds\":" << secs << ",\"route\":\"" << route << "\"}\n";
                    return 0;
                }
                atoms_of(ns, at);
                if (!test_and_mark(at)) continue;
                next.push_back(ns); tnext.push_back({(int)i, DCH[mv]});
            }
        total += next.size();
        cur.swap(next); trace.push_back(move(tnext));
        double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        cout << "{\"g\":" << g + 1 << ",\"kept\":" << cur.size() << ",\"total\":" << total << ",\"seconds\":" << secs << "}\n" << flush;
        if (cur.empty()) { cout << "{\"exhausted_at\":" << g + 1 << ",\"k\":" << K << ",\"kept_states\":" << total << "}\n"; return 0; }
    }
    cout << "{\"not_found_within\":" << max_depth << "}\n";
    return 0;
}
