// Bounded beam with novelty-first selection (after BFWS, Lipovetzky & Geffner 2017).
//
// Same layer-by-layer search as experiments/bounded_beam: drop any child with
// g + h > B (h is the prove_lb heuristic, admissible, so this never cuts a route
// of length <= B), deduplicate by state hash and best g, keep W children. The
// difference is which W. bounded_beam keeps the lowest h and lost III-14's 48-key
// route at g = 30, where 403,523 candidates had lower h. Here each candidate gets
// a novelty w: 1 if it makes some atom true for the first time among kept states
// with the same h, 2 if some pair of atoms, 3 otherwise. Selection sorts by
// (w, h, seeded tie). Atoms are the cells that differ from the start position
// (cell, object), Bard note cells and door flags. The tuple table is a hashed
// bitset, so a hash clash can only make a state look less novel.
//
// A route printed here is only a candidate: it must still be replayed by the
// Python oracles and the pinned original build.
//
// Input (stdin): part w h bound width seed share, then h grid rows. share is the
// percentage of the width filled in novelty order (100 = pure novelty first).
// (seed 0: read a reference route after the grid and report whether each of its
// states survives selection).
#define main soko_engine_main
#include "../../cpp/soko_engine.cpp"
#undef main

int main() {
    int part, w, h, bound, width, share; uint64_t seed;
    cin >> part >> w >> h >> bound >> width >> seed >> share;
    vector<string> rows(h);
    for (auto& r : rows) cin >> r;
    auto [M, s0] = parse_level(part, w, h, rows);

    // The same admissible heuristic prove_lb uses.
    bool has_druid = false, has_wizard = false, has_fighter = false;
    for (int i = 0; i < M.n; ++i) {
        if (s0.obj[i] == 6 || s0.obj[i] == 12) has_druid = true;
        if (s0.obj[i] == 3 || s0.obj[i] == 9) has_wizard = true;
        if (s0.obj[i] == 1 || s0.obj[i] == 7) has_fighter = true;
    }
    vector<int> goal_dist(M.n, 999);
    {
        queue<int> q;
        for (int g : M.goals) { goal_dist[g] = 0; q.push(g); }
        while (!q.empty()) {
            int u = q.front(); q.pop();
            for (int d = 0; d < 4; ++d) {
                int nx = u % M.w + DX[d], ny = u / M.w + DY[d];
                if (nx < 0 || nx >= M.w || ny < 0 || ny >= M.h) continue;
                int ni = ny * M.w + nx;
                if (!has_druid && s0.obj[ni] == 13) continue;
                if (goal_dist[ni] > goal_dist[u] + 1) { goal_dist[ni] = goal_dist[u] + 1; q.push(ni); }
            }
        }
    }
    PairAtomQuotientPDB ppdb; ppdb.try_build(M, s0);
    BardDruidQuotientPDB qpdb; qpdb.try_build(M, s0);
    WizardRayGoalBound wiz; if (has_wizard) wiz.build(M, s0, has_druid, has_fighter);
    auto hfun = [&](const DynState& s) -> int {
        if (check_win(M, s)) return 0;
        int hero_cnt = 0, best = 1;
        for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) hero_cnt++;
        if (hero_cnt < (int)M.goals.size()) return 999;
        if (!has_wizard) {
            for (int i = 0; i < M.n; ++i) if (is_hero(s.obj[i])) best = max(best, goal_dist[i]);
            if (!M.has_bard && !has_fighter) {
                int unc = 0; for (int g : M.goals) if (!is_hero(s.obj[g])) unc++;
                best = max(best, unc);
            }
        } else if (wiz.enabled) best = max(best, wiz.lookup(M, s));
        if (qpdb.enabled) best = max(best, qpdb.lookup(M, s));
        if (ppdb.enabled) best = max(best, ppdb.lookup(M, s));
        return best;
    };

    // Novelty table: 2^32 bits, keyed by hash(h, tuple).
    const uint64_t TBITS = 1ULL << 32;
    vector<uint64_t> table(TBITS / 64, 0);
    auto tkey = [&](uint64_t hv, uint64_t a, uint64_t b) {
        uint64_t z = hv * 0x9e3779b97f4a7c15ULL ^ (a << 32 | b);
        z ^= z >> 30; z *= 0xbf58476d1ce4e5b9ULL; z ^= z >> 27; z *= 0x94d049bb133111ebULL; z ^= z >> 31;
        return z & (TBITS - 1);
    };
    auto tget = [&](uint64_t k) { return (table[k >> 6] >> (k & 63)) & 1ULL; };
    auto tset = [&](uint64_t k) { table[k >> 6] |= 1ULL << (k & 63); };
    auto atoms_of = [&](const DynState& s, vector<uint32_t>& out) {
        out.clear();
        for (int i = 0; i < M.n; ++i) if (s.obj[i] != s0.obj[i]) out.push_back((uint32_t)(i * 32 + (s.obj[i] & 31)));
        if (M.has_bard) for (int i = 0; i < M.n; ++i) if (s.has_note(i) != s0.has_note(i)) out.push_back((uint32_t)(M.n * 32 + i));
        out.push_back((uint32_t)(M.n * 33 + s.y_open));
        out.push_back((uint32_t)(M.n * 33 + 256 + s.p_open));
    };
    const uint64_t SINGLE = 0xFFFFFFFFULL;
    auto novelty = [&](const DynState& s, int hv, vector<uint32_t>& at) {
        atoms_of(s, at);
        for (auto a : at) if (!tget(tkey(hv, a, SINGLE))) return 1;
        for (size_t x = 0; x < at.size(); ++x)
            for (size_t y = x + 1; y < at.size(); ++y)
                if (!tget(tkey(hv, min(at[x], at[y]), max(at[x], at[y])))) return 2;
        return 3;
    };
    auto mark = [&](const DynState& s, int hv, vector<uint32_t>& at) {
        atoms_of(s, at);
        for (auto a : at) tset(tkey(hv, a, SINGLE));
        for (size_t x = 0; x < at.size(); ++x)
            for (size_t y = x + 1; y < at.size(); ++y) tset(tkey(hv, min(at[x], at[y]), max(at[x], at[y])));
    };
    { vector<uint32_t> at; mark(s0, hfun(s0), at); }

    if (bound < 0) {
        // Diagnostic: read a route and print g + h along it. A value above the
        // route's length means h overestimates there, so pruning would cut it.
        string route; cin >> route;
        DynState cur = s0; int worst = 0, worst_at = 0;
        cout << "{\"f_profile\":[";
        for (int g = 0; g <= (int)route.size(); ++g) {
            int f = g + hfun(cur);
            if (f > worst) { worst = f; worst_at = g; }
            cout << (g ? "," : "") << f;
            if (g < (int)route.size()) step_state(M, cur, d_idx(route[g]), false);
        }
        cout << "],\"route_len\":" << route.size() << ",\"max_f\":" << worst << ",\"max_f_at\":" << worst_at << "}\n";
        return 0;
    }
    // Full states are kept only for the current layer; older layers keep parent
    // pointers and keys. Duplicates are detected by 64-bit state hash with the
    // best g seen (lossy: a collision can drop a state, never accept a bad route).
    struct Trace { int parent; char mv; };
    vector<vector<Trace>> trace(1, vector<Trace>{{-1, 0}});
    vector<DynState> cur = {s0};
    unordered_map<uint64_t, uint8_t> best_g;
    best_g.reserve((size_t)width * 8);
    best_g[s0.hash64(M.n, M.has_bard)] = 0;
    vector<uint64_t> ref_keys; vector<int> ref_h;
    if (seed == 0) {  // diagnostic: read a reference route after the grid and track it
        string route; cin >> route; DynState cur2 = s0;
        for (char c : route) { step_state(M, cur2, d_idx(c), false); ref_keys.push_back(cur2.hash64(M.n, M.has_bard)); ref_h.push_back(hfun(cur2)); }
    }
    int h0 = hfun(s0);
    cout << "{\"start_h\":" << h0 << ",\"bound\":" << bound << ",\"width\":" << width
         << ",\"qpdb\":" << qpdb.enabled << ",\"ppdb\":" << ppdb.enabled << "}\n" << flush;
    auto t0 = chrono::steady_clock::now();
    for (int g = 0; g < bound; ++g) {
        struct Cand { int parent; char mv; uint16_t h; uint64_t tie; uint64_t key; };
        // Expansion runs on all hardware threads. best_g is only read here; it is
        // written in the single-threaded selection step below.
        unsigned nt = max(1u, min(16u, thread::hardware_concurrency()));
        vector<vector<Cand>> tc(nt); vector<vector<DynState>> ts(nt);
        vector<string> found_route(nt);
        auto expand = [&](unsigned tid) {
            size_t lo = cur.size() * tid / nt, hi = cur.size() * (tid + 1) / nt;
            for (size_t i = lo; i < hi && found_route[tid].empty(); ++i)
                for (int mv = 0; mv < 5; ++mv) {
                    DynState ns = cur[i];
                    int res = step_state(M, ns, mv, true);
                    if (res < 0) continue;
                    if (res == 1) {
                        string route(1, DCH[mv]);
                        int li = (int)i;
                        for (int lg = g; lg > 0; --lg) { route.push_back(trace[lg][li].mv); li = trace[lg][li].parent; }
                        reverse(route.begin(), route.end());
                        found_route[tid] = route;
                        break;
                    }
                    int hn = hfun(ns);
                    if (g + 1 + hn > bound) continue;
                    uint64_t key = ns.hash64(M.n, M.has_bard);
                    auto it = best_g.find(key);
                    if (it != best_g.end() && it->second <= g + 1) continue;
                    uint64_t tie = key ^ (seed * 0x9e3779b97f4a7c15ULL);
                    tie ^= tie >> 29; tie *= 0xbf58476d1ce4e5b9ULL; tie ^= tie >> 32;
                    tc[tid].push_back({(int)i, DCH[mv], (uint16_t)hn, tie, key});
                    ts[tid].push_back(ns);
                }
        };
        { vector<thread> pool; for (unsigned t = 1; t < nt; ++t) pool.emplace_back(expand, t); expand(0); for (auto& t : pool) t.join(); }
        for (auto& r : found_route) if (!r.empty()) {
            double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
            cout << "{\"found\":" << r.size() << ",\"seconds\":" << secs << ",\"route\":\"" << r << "\"}\n";
            return 0;
        }
        vector<Cand> cands; vector<DynState> cstates;
        for (unsigned t = 0; t < nt; ++t) {
            cands.insert(cands.end(), tc[t].begin(), tc[t].end()); vector<Cand>().swap(tc[t]);
            cstates.insert(cstates.end(), ts[t].begin(), ts[t].end()); vector<DynState>().swap(ts[t]);
        }
        vector<uint8_t> wv(cands.size(), 3);
        {
            unsigned nt2 = max(1u, min(16u, thread::hardware_concurrency()));
            auto nov = [&](unsigned tid) {
                vector<uint32_t> at;
                for (size_t i = tid; i < cands.size(); i += nt2) wv[i] = (uint8_t)novelty(cstates[i], cands[i].h, at);
            };
            vector<thread> pool; for (unsigned t = 1; t < nt2; ++t) pool.emplace_back(nov, t); nov(0); for (auto& t : pool) t.join();
        }
        // Split beam: the first (100 - share)% of the width is filled in (h, tie)
        // order, the rest in (w, h, tie) order.
        vector<int> by_h(cands.size()), by_w(cands.size());
        iota(by_h.begin(), by_h.end(), 0); iota(by_w.begin(), by_w.end(), 0);
        sort(by_h.begin(), by_h.end(), [&](int a, int b) {
            return cands[a].h != cands[b].h ? cands[a].h < cands[b].h : cands[a].tie < cands[b].tie; });
        sort(by_w.begin(), by_w.end(), [&](int a, int b) {
            if (wv[a] != wv[b]) return wv[a] < wv[b];
            return cands[a].h != cands[b].h ? cands[a].h < cands[b].h : cands[a].tie < cands[b].tie; });
        vector<DynState> next; vector<Trace> tnext;
        int min_h = -1; size_t kept_w[4] = {0, 0, 0, 0};
        vector<uint32_t> at_mark;
        int h_quota = (int)((int64_t)width * (100 - share) / 100);
        for (int pass = 0; pass < 2; ++pass) {
            int cap = pass == 0 ? h_quota : width;
            for (int idx : (pass == 0 ? by_h : by_w)) {
                if ((int)next.size() >= cap) break;
                auto& c = cands[idx];
                auto it = best_g.find(c.key);
                if (it != best_g.end() && it->second <= g + 1) continue;
                best_g[c.key] = (uint8_t)(g + 1);
                if (min_h < 0 || c.h < min_h) min_h = c.h;
                kept_w[wv[idx]]++;
                mark(cstates[idx], c.h, at_mark);
                next.push_back(cstates[idx]); tnext.push_back({c.parent, c.mv});
            }
        }
        if (seed == 0 && g < (int)ref_keys.size()) {
            bool in_cands = false, kept = false; int better = 0;
            for (auto& c : cands) { if (c.key == ref_keys[g]) in_cands = true; if (c.h < ref_h[g]) better++; }
            for (auto& st : next) if (st.hash64(M.n, M.has_bard) == ref_keys[g]) { kept = true; break; }
            cout << "{\"ref_g\":" << g + 1 << ",\"ref_h\":" << ref_h[g] << ",\"in_candidates\":" << in_cands
                 << ",\"kept\":" << kept << ",\"candidates_with_lower_h\":" << better << "}\n";
        }
        cur.swap(next); trace.push_back(move(tnext));
        double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        cout << "{\"g\":" << g + 1 << ",\"kept\":" << cur.size() << ",\"candidates\":" << cands.size()
             << ",\"min_h\":" << min_h << ",\"kept_w1\":" << kept_w[1] << ",\"kept_w2\":" << kept_w[2]
             << ",\"kept_w3\":" << kept_w[3] << ",\"seconds\":" << secs << "}\n" << flush;
        if (cur.empty()) { cout << "{\"exhausted_at\":" << g + 1 << "}\n"; return 0; }
    }
    cout << "{\"not_found_within\":" << bound << "}\n";
    return 0;
}
