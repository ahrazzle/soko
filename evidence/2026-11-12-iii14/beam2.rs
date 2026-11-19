// Fast III-14 engine + exact A*/BFS. rustc -O -C target-cpu=native iii14.rs
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, HashSet, VecDeque};
use std::env;
use std::fs;
use std::time::Instant;

const W: i32 = 15;
const H: i32 = 7;
const N: usize = 105;
const DIRS: [(i32, i32); 4] = [(0, -1), (0, 1), (-1, 0), (1, 0)]; // UDLR
const KEYS: [char; 5] = ['U', 'D', 'L', 'R', 'A'];

#[inline]
fn idx(x: i32, y: i32) -> u32 {
    (y * W + x) as u32
}
#[inline]
fn bit(c: u32) -> u128 {
    1u128 << c
}
#[inline]
fn xy(c: u32) -> (i32, i32) {
    ((c as i32) % W, (c as i32) / W)
}

fn mask_cells(cells: &[(i32, i32)]) -> u128 {
    let mut m = 0u128;
    for &(x, y) in cells {
        m |= bit(idx(x, y));
    }
    m
}

fn start_walls() -> u128 {
    let mut w = 0u128;
    for x in 0..W {
        w |= bit(idx(x, 0)) | bit(idx(x, H - 1));
    }
    for y in 0..H {
        w |= bit(idx(0, y)) | bit(idx(W - 1, y));
    }
    w
}

fn switch_mask() -> u128 {
    mask_cells(&[
        (4, 2), (5, 2), (6, 2),
        (4, 3), (5, 3), (6, 3),
        (4, 4), (5, 4), (6, 4),
    ])
}
fn door_mask() -> u128 {
    mask_cells(&[
        (8, 2), (9, 2), (10, 2), (11, 2), (12, 2),
        (8, 3), (12, 3),
        (8, 4), (9, 4), (10, 4), (11, 4), (12, 4),
    ])
}
fn goal_mask() -> u128 {
    mask_cells(&[(9, 3), (11, 3)])
}

#[derive(Clone, Copy, Debug)]
struct St {
    walls: u128,
    crates: u128,
    doors: u128,
    bx: u8,
    by: u8,
    dx: u8,
    dy: u8,
    bard: bool,
    notes: u128,
}

impl St {
    fn vis(self) -> Vis {
        Vis {
            walls: self.walls,
            crates: self.crates,
            bx: self.bx,
            by: self.by,
            dx: self.dx,
            dy: self.dy,
            bard: self.bard,
        }
    }
    fn weights(self, sw: u128) -> u128 {
        let mut occ = self.walls | self.crates;
        occ |= bit(idx(self.bx as i32, self.by as i32));
        occ |= bit(idx(self.dx as i32, self.dy as i32));
        occ & sw
    }
    fn all_weighed(self, sw: u128) -> bool {
        self.weights(sw) == sw
    }
    fn win(self, goals: u128) -> bool {
        let h = bit(idx(self.bx as i32, self.by as i32)) | bit(idx(self.dx as i32, self.dy as i32));
        h == goals
    }
    fn hero_bits(self) -> u128 {
        bit(idx(self.bx as i32, self.by as i32)) | bit(idx(self.dx as i32, self.dy as i32))
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct Vis {
    walls: u128,
    crates: u128,
    bx: u8,
    by: u8,
    dx: u8,
    dy: u8,
    bard: bool,
}

fn compute_notes(s: &St) -> u128 {
    if !s.bard {
        return 0;
    }
    let bx = s.bx as i32;
    let by = s.by as i32;
    let mut notes = 0u128;
    let y0 = (by - 2).max(0);
    let y1 = (by + 3).min(H);
    let x0 = (bx - 2).max(0);
    let x1 = (bx + 3).min(W);
    for ny in y0..y1 {
        for nx in x0..x1 {
            if nx == bx && ny == by {
                continue;
            }
            let c = idx(nx, ny);
            if s.crates & bit(c) != 0 {
                notes |= bit(c);
            } else if nx == s.dx as i32 && ny == s.dy as i32 {
                notes |= bit(c);
            }
        }
    }
    notes
}

fn late(mut s: St, sw: u128, doors_m: u128) -> Option<St> {
    if s.all_weighed(sw) {
        s.doors = 0;
    } else {
        let currently_open = doors_m & !s.doors;
        if s.hero_bits() & currently_open != 0 {
            return None; // crushed
        }
        s.doors = doors_m;
    }
    s.notes = compute_notes(&s);
    Some(s)
}

#[inline]
fn dest(c: u32, ddx: i32, ddy: i32) -> i32 {
    let (x, y) = xy(c);
    let nx = x + ddx;
    let ny = y + ddy;
    if nx < 0 || nx >= W || ny < 0 || ny >= H {
        return -1;
    }
    idx(nx, ny) as i32
}

#[inline]
fn is_empty(s: &St, c: u32, bpos: u32, dpos: u32) -> bool {
    let b = bit(c);
    if s.walls & b != 0 {
        return false;
    }
    if s.crates & b != 0 {
        return false;
    }
    if s.doors & b != 0 {
        return false;
    }
    if c == bpos || c == dpos {
        return false;
    }
    true
}

fn step(s: St, key: usize, sw: u128, doors_m: u128) -> Option<St> {
    // key 0..4 = UDLRA
    let mut ns = s;
    if key == 4 {
        ns.bard = !ns.bard;
        ns.notes = 0;
        return late(ns, sw, doors_m);
    }
    let (ddx, ddy) = DIRS[key];
    if ns.bard {
        let mut pending = ns.notes;
        let mut bpos = idx(ns.bx as i32, ns.by as i32);
        let mut dpos = idx(ns.dx as i32, ns.dy as i32);
        let mut bard_moved = false;
        let mut changed = true;
        while changed {
            changed = false;
            let mut left = pending;
            while left != 0 {
                let c = left.trailing_zeros();
                left &= left - 1;
                let t = dest(c, ddx, ddy);
                if t < 0 {
                    continue;
                }
                let tu = t as u32;
                if is_empty(&ns, tu, bpos, dpos) {
                    if ns.crates & bit(c) != 0 {
                        ns.crates &= !bit(c);
                        ns.crates |= bit(tu);
                    } else if c == dpos {
                        dpos = tu;
                        let (x, y) = xy(tu);
                        ns.dx = x as u8;
                        ns.dy = y as u8;
                    }
                    pending &= !bit(c);
                    changed = true;
                }
            }
            if !bard_moved {
                let t = dest(bpos, ddx, ddy);
                if t >= 0 && is_empty(&ns, t as u32, bpos, dpos) {
                    let tu = t as u32;
                    bpos = tu;
                    let (x, y) = xy(tu);
                    ns.bx = x as u8;
                    ns.by = y as u8;
                    bard_moved = true;
                    changed = true;
                }
            }
        }
        if !bard_moved {
            return Some(s); // cancel no-op
        }
        ns.notes = 0;
        return late(ns, sw, doors_m);
    }
    // Druid
    let nx = ns.dx as i32 + ddx;
    let ny = ns.dy as i32 + ddy;
    if nx < 0 || nx >= W || ny < 0 || ny >= H {
        ns.notes = 0;
        return late(ns, sw, doors_m);
    }
    let t = idx(nx, ny);
    let tb = bit(t);
    let occ_no_druid = ns.walls | ns.crates | ns.doors | bit(idx(ns.bx as i32, ns.by as i32));
    if occ_no_druid & tb == 0 {
        ns.dx = nx as u8;
        ns.dy = ny as u8;
    } else if ns.crates & tb != 0 {
        ns.crates &= !tb;
        ns.walls |= tb;
    } else if ns.walls & tb != 0 {
        ns.walls &= !tb;
        ns.crates |= tb;
    } else if nx == ns.bx as i32 && ny == ns.by as i32 {
        return None; // petrify
    }
    ns.notes = 0;
    late(ns, sw, doors_m)
}

fn start_state(sw: u128, doors_m: u128) -> St {
    St {
        walls: start_walls(),
        crates: 0,
        doors: doors_m,
        bx: 2,
        by: 2,
        dx: 2,
        dy: 4,
        bard: false,
        notes: 0,
    }
}

fn parse_u128(s: &str) -> u128 {
    s.parse().expect("u128")
}

fn md(x: i32, y: i32, gx: i32, gy: i32) -> i32 {
    (x - gx).abs() + (y - gy).abs()
}

fn heur(s: &St, sw: u128) -> i32 {
    if s.win(goal_mask()) {
        return 0;
    }
    let d1 = md(s.bx as i32, s.by as i32, 9, 3);
    let d2 = md(s.dx as i32, s.dy as i32, 11, 3);
    let d3 = md(s.bx as i32, s.by as i32, 11, 3);
    let d4 = md(s.dx as i32, s.dy as i32, 9, 3);
    let man = d1.max(d2).min(d3.max(d4));
    if s.all_weighed(sw) {
        man
    } else {
        // opening move may reduce manhattan by 1
        1.max(man)
    }
}

#[derive(Copy, Clone, Eq, PartialEq)]
struct Node {
    f: i32,
    g: i32,
    idx: usize,
}
impl Ord for Node {
    fn cmp(&self, other: &Self) -> Ordering {
        // min-heap
        other.f.cmp(&self.f).then_with(|| other.g.cmp(&self.g))
    }
}
impl PartialOrd for Node {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

fn reconstruct(parents: &[(St, i32, u8)], mut i: usize) -> String {
    let mut keys = Vec::new();
    loop {
        let (_, p, mv) = parents[i];
        if p < 0 {
            break;
        }
        keys.push(KEYS[mv as usize]);
        i = p as usize;
    }
    keys.reverse();
    keys.into_iter().collect()
}

fn bfs_or_astar(
    start: St,
    mut max_depth: i32,
    time_limit: f64,
    sw: u128,
    doors_m: u128,
    goals: u128,
    label: &str,
    use_astar: bool,
) -> Option<String> {
    let t0 = Instant::now();
    let mut parents: Vec<(St, i32, u8)> = Vec::with_capacity(1 << 20);
    parents.push((start, -1, 0));
    let mut best_g: HashMap<Vis, i32> = HashMap::with_capacity(1 << 20);
    best_g.insert(start.vis(), 0);
    let mut expanded = 0u64;
    let mut best: Option<(i32, String)> = None;
    let mut last_print = 0.0;

    let mut heap: BinaryHeap<Node> = BinaryHeap::new();
    let mut q: VecDeque<(i32, usize)> = VecDeque::new();
    if use_astar {
        heap.push(Node {
            f: heur(&start, sw),
            g: 0,
            idx: 0,
        });
    } else {
        q.push_back((0, 0));
    }

    loop {
        let (g, idx) = if use_astar {
            match heap.pop() {
                Some(Node { g, idx, .. }) => (g, idx),
                None => break,
            }
        } else {
            match q.pop_front() {
                Some(v) => v,
                None => break,
            }
        };
        let el = t0.elapsed().as_secs_f64();
        if el > time_limit {
            break;
        }
        if el - last_print > 5.0 {
            let open = if use_astar { heap.len() } else { q.len() };
            eprintln!(
                "  [{}] t={:.1}s exp={} seen={} open={} g={} best={:?}",
                label,
                el,
                expanded,
                best_g.len(),
                open,
                g,
                best.as_ref().map(|b| b.0)
            );
            last_print = el;
        }
        let (st, _, _) = parents[idx];
        if g > max_depth {
            continue;
        }
        if *best_g.get(&st.vis()).unwrap_or(&i32::MAX) < g {
            continue;
        }
        expanded += 1;
        for mv in 0..5 {
            let Some(ns) = step(st, mv, sw, doors_m) else {
                continue;
            };
            let ng = g + 1;
            if ns.win(goals) {
                let mut path = reconstruct(&parents, idx);
                path.push(KEYS[mv]);
                if best.as_ref().map(|b| ng < b.0).unwrap_or(true) {
                    eprintln!(
                        "  [{}] WIN {} t={:.2}s exp={} {}",
                        label,
                        ng,
                        t0.elapsed().as_secs_f64(),
                        expanded,
                        path
                    );
                    best = Some((ng, path));
                    max_depth = ng - 1;
                }
                continue;
            }
            if ng > max_depth {
                continue;
            }
            if ng + heur(&ns, sw) > max_depth {
                continue;
            }
            let v = ns.vis();
            if let Some(&og) = best_g.get(&v) {
                if og <= ng {
                    continue;
                }
            }
            best_g.insert(v, ng);
            let nidx = parents.len();
            parents.push((ns, idx as i32, mv as u8));
            if use_astar {
                heap.push(Node {
                    f: ng + heur(&ns, sw),
                    g: ng,
                    idx: nidx,
                });
            } else {
                q.push_back((ng, nidx));
            }
        }
    }
    eprintln!(
        "[{}] done t={:.2}s exp={} seen={} best={:?} exhausted={}",
        label,
        t0.elapsed().as_secs_f64(),
        expanded,
        best_g.len(),
        best.as_ref().map(|b| b.0),
        if use_astar { heap.is_empty() } else { q.is_empty() }
    );
    best.map(|b| b.1)
}

fn parse_state_line(parts: &[&str], off: usize) -> St {
    St {
        walls: parse_u128(parts[off]),
        crates: parse_u128(parts[off + 1]),
        doors: parse_u128(parts[off + 2]),
        bx: parts[off + 3].parse().unwrap(),
        by: parts[off + 4].parse().unwrap(),
        dx: parts[off + 5].parse().unwrap(),
        dy: parts[off + 6].parse().unwrap(),
        bard: parts[off + 7] != "0",
        notes: parse_u128(parts[off + 8]),
    }
}

fn test_traj(sw: u128, doors_m: u128) {
    let text = fs::read_to_string("/tmp/iii14_traj.txt").expect("traj");
    let mut mismatches = 0;
    for (li, line) in text.lines().enumerate() {
        let p: Vec<&str> = line.split_whitespace().collect();
        // 0 S walls ...   or  i K walls ...
        if li == 0 {
            let s = start_state(sw, doors_m);
            let want = parse_state_line(&p, 2);
            if !eq_state(s, want) {
                eprintln!("start mismatch\n got {:?}\nwant {:?}", s, want);
                mismatches += 1;
            }
            continue;
        }
    }
    // replay
    let mut s = start_state(sw, doors_m);
    for (li, line) in text.lines().enumerate() {
        if li == 0 {
            continue;
        }
        let p: Vec<&str> = line.split_whitespace().collect();
        let k = p[1].chars().next().unwrap();
        let mv = KEYS.iter().position(|&c| c == k).unwrap();
        s = step(s, mv, sw, doors_m).expect("died");
        let want = parse_state_line(&p, 2);
        if !eq_state(s, want) {
            eprintln!("mismatch at {} {}\n got {:?}\nwant {:?}", p[0], k, s, want);
            mismatches += 1;
            if mismatches >= 5 {
                break;
            }
        }
    }
    if mismatches == 0 {
        let win = s.win(goal_mask());
        eprintln!("RUST engine matches 48-key traj, win={}", win);
    } else {
        eprintln!("RUST mismatches={}", mismatches);
        std::process::exit(1);
    }
}

fn eq_state(a: St, b: St) -> bool {
    a.walls == b.walls
        && a.crates == b.crates
        && a.doors == b.doors
        && a.bx == b.bx
        && a.by == b.by
        && a.dx == b.dx
        && a.dy == b.dy
        && a.bard == b.bard
        && a.notes == b.notes
}

fn load_traj_state(stepn: usize) -> St {
    let text = fs::read_to_string("/tmp/iii14_traj.txt").expect("traj");
    let line = text.lines().nth(stepn).expect("step");
    let p: Vec<&str> = line.split_whitespace().collect();
    let off = 2;
    parse_state_line(&p, off)
}


fn perm_w(s: &St, sw: u128) -> u32 {
    ((s.walls | s.crates) & sw).count_ones()
}

fn man_goals(s: &St) -> i64 {
    let d1 = md(s.bx as i32, s.by as i32, 9, 3);
    let d2 = md(s.dx as i32, s.dy as i32, 11, 3);
    let d3 = md(s.bx as i32, s.by as i32, 11, 3);
    let d4 = md(s.dx as i32, s.dy as i32, 9, 3);
    d1.max(d2).min(d3.max(d4)) as i64
}

fn score(s: &St, sw: u128) -> i64 {
    if s.win(goal_mask()) {
        return 1_000_000_000;
    }
    let pw = perm_w(s, sw) as i64;
    let walls_sw = (s.walls & sw).count_ones() as i64;
    let man = man_goals(s);
    let mut near = 0i64;
    let mut cr = s.crates;
    while cr != 0 {
        let c = cr.trailing_zeros();
        cr &= cr - 1;
        let (x, y) = xy(c);
        if (3..8).contains(&x) && (1..6).contains(&y) {
            near += 1;
        }
    }
    let mut sc = pw * 2_000_000 + walls_sw * 80_000 + near * 300;
    if pw == 9 {
        // permanent 9: doors stay open without heroes; race to goals
        sc += 200_000_000 - man * 20_000;
        // prefer inactive bard (druid can walk in without charm) when close
        if !s.bard {
            sc += 5_000;
        }
    } else {
        sc -= man * 15;
    }
    sc + if s.bard { 10 } else { 0 }
}

/// Shortest win from a permanent-9 (or any) state, memory-light BFS, prune optional.
fn finish_bfs(start: St, max_depth: i32, time_limit: f64, sw: u128, doors_m: u128, goals: u128) -> Option<String> {
    if start.win(goals) {
        return Some(String::new());
    }
    let t0 = Instant::now();
    let mut parents: Vec<(St, i32, u8)> = Vec::with_capacity(1 << 16);
    parents.push((start, -1, 0));
    let mut seen: HashMap<Vis, i32> = HashMap::with_capacity(1 << 16);
    seen.insert(start.vis(), 0);
    let mut q = VecDeque::new();
    q.push_back(0usize);
    let mut best: Option<(i32, String)> = None;
    let mut max_d = max_depth;
    while let Some(idx) = q.pop_front() {
        if t0.elapsed().as_secs_f64() > time_limit { break; }
        let (st, _, _) = parents[idx];
        let g = seen[&st.vis()];
        if g >= max_d { continue; }
        for mv in 0..5 {
            let Some(ns) = step(st, mv, sw, doors_m) else { continue; };
            let ng = g + 1;
            if ns.win(goals) {
                let mut path = reconstruct(&parents, idx);
                path.push(KEYS[mv]);
                if best.as_ref().map(|b| ng < b.0).unwrap_or(true) {
                    best = Some((ng, path));
                    max_d = ng - 1;
                }
                continue;
            }
            if ng > max_d { continue; }
            // weak prune: if remaining can't meet manhattan
            if ng + man_goals(&ns) as i32 > max_d { continue; }
            let v = ns.vis();
            if seen.contains_key(&v) { continue; }
            seen.insert(v, ng);
            let nidx = parents.len();
            parents.push((ns, idx as i32, mv as u8));
            q.push_back(nidx);
        }
    }
    best.map(|b| b.1)
}

struct Packed {
    st: St,
    parent: u32, // index in previous layer vec, or u32::MAX for start
    mv: u8,
}

fn beam_search(
    start: St,
    max_depth: i32,
    beam: usize,
    time_limit: f64,
    sw: u128,
    doors_m: u128,
    goals: u128,
    label: &str,
    seed_suffix: Option<&str>,
) -> Option<String> {
    let t0 = Instant::now();
    // layers for reconstruction: each layer is Vec<Packed>
    let mut layers: Vec<Vec<Packed>> = Vec::new();
    layers.push(vec![Packed { st: start, parent: u32::MAX, mv: 0 }]);
    // seen: vis -> best g
    let mut seen: HashMap<Vis, i32> = HashMap::with_capacity(beam * 8);
    seen.insert(start.vis(), 0);
    let mut best: Option<(i32, String)> = None;
    let mut first_99: Option<(i32, String, St)> = None;
    let mut n99 = 0u64;

    // If a seed suffix is given, compute its states to inject (keep seed in beam)
    let mut seed_states: Vec<St> = Vec::new();
    if let Some(suf) = seed_suffix {
        let mut s = start;
        seed_states.push(s);
        for c in suf.chars() {
            let mv = KEYS.iter().position(|&k| k == c).unwrap();
            match step(s, mv, sw, doors_m) {
                Some(ns) => { s = ns; seed_states.push(s); }
                None => break,
            }
        }
        eprintln!("[{}] seed suffix {} loaded, {} states, seed_win={}",
            label, suf.len(), seed_states.len(), s.win(goals));
    }

    for d in 1..=max_depth {
        if t0.elapsed().as_secs_f64() > time_limit {
            eprintln!("[{}] timeout at depth {}", label, d-1);
            break;
        }
        let prev = &layers[d as usize - 1];
        let mut cand: Vec<(i64, Packed)> = Vec::with_capacity(prev.len() * 5);
        let mut wins_this = 0;
        for (pi, p) in prev.iter().enumerate() {
            for mv in 0..5 {
                let Some(ns) = step(p.st, mv, sw, doors_m) else { continue; };
                let ng = d;
                if ns.win(goals) {
                    // reconstruct
                    let mut path = Vec::new();
                    path.push(KEYS[mv]);
                    let mut layer_i = (d as usize) - 1;
                    let mut idx = pi as u32;
                    while layer_i > 0 {
                        let node = &layers[layer_i][idx as usize];
                        path.push(KEYS[node.mv as usize]);
                        idx = node.parent;
                        layer_i -= 1;
                    }
                    path.reverse();
                    let s: String = path.into_iter().collect();
                    if best.as_ref().map(|b| ng < b.0).unwrap_or(true) {
                        eprintln!("  [{}] WIN {} t={:.2}s {}", label, ng, t0.elapsed().as_secs_f64(), s);
                        best = Some((ng, s));
                    }
                    wins_this += 1;
                    continue;
                }
                if first_99.is_none() && perm_w(&ns, sw) == 9 {
                    // reconstruct this path too (duplicate walk)
                    let mut path = Vec::new();
                    path.push(KEYS[mv]);
                    let mut layer_i = (d as usize) - 1;
                    let mut idx = pi as u32;
                    while layer_i > 0 {
                        let node = &layers[layer_i][idx as usize];
                        path.push(KEYS[node.mv as usize]);
                        idx = node.parent;
                        layer_i -= 1;
                    }
                    path.reverse();
                    let s: String = path.into_iter().collect();
                    eprintln!("  [{}] first PERM9 at {} t={:.2}s B=({},{}) D=({},{}) {}",
                        label, ng, t0.elapsed().as_secs_f64(), ns.bx, ns.by, ns.dx, ns.dy, s);
                    first_99 = Some((ng, s, ns));
                }
                if ns.all_weighed(sw) {
                    n99 += 1;
                }
                let v = ns.vis();
                if let Some(&og) = seen.get(&v) {
                    if og <= ng { continue; }
                }
                seen.insert(v, ng);
                cand.push((score(&ns, sw), Packed { st: ns, parent: pi as u32, mv: mv as u8 }));
            }
        }
        if cand.is_empty() {
            eprintln!("[{}] no candidates at depth {}", label, d);
            break;
        }
        // inject seed state at this depth if present
        if (d as usize) < seed_states.len() {
            let ss = seed_states[d as usize];
            let v = ss.vis();
            let in_cand = cand.iter().any(|(_,p)| p.st.vis() == v);
            if !in_cand {
                // find parent in previous layer
                let parent_v = seed_states[d as usize - 1].vis();
                let mut pidx: u32 = 0;
                for (i, p) in prev.iter().enumerate() {
                    if p.st.vis() == parent_v { pidx = i as u32; break; }
                }
                let mvchar = seed_suffix.unwrap().chars().nth(d as usize - 1).unwrap();
                let mv = KEYS.iter().position(|&k| k == mvchar).unwrap() as u8;
                cand.push((i64::MAX / 2, Packed { st: ss, parent: pidx, mv }));
                seen.insert(v, d);
            }
        }
        cand.sort_by(|a,b| b.0.cmp(&a.0));
        let keep = beam.min(cand.len());
        // also keep a slice of diverse mid-score to avoid collapse: already top-k by score
        let next: Vec<Packed> = cand.into_iter().take(keep).map(|(_,p)| p).collect();
        let best_sc = score(&next[0].st, sw);
        let wtop = next[0].st.weights(sw).count_ones();
        if d % 2 == 0 || d <= 4 {
            eprintln!("  [{}] d={} kept={} seen={} top_sc={} top_sw={}/9 9/9cum={} t={:.1}s",
                label, d, next.len(), seen.len(), best_sc, wtop, n99, t0.elapsed().as_secs_f64());
        }
        // Try short finishes from the best permanent-9 states this layer
        let remain_cap = best.as_ref().map(|b| b.0 - d).unwrap_or(max_depth - d);
        if remain_cap >= 1 {
            let mut p9: Vec<&Packed> = next.iter().filter(|p| perm_w(&p.st, sw) == 9).collect();
            p9.sort_by_key(|p| man_goals(&p.st));
            let mut tried = 0;
            for p in p9.iter().take(40) {
                tried += 1;
                let budget = (0.05_f64).min(time_limit - t0.elapsed().as_secs_f64()).max(0.0);
                if budget < 0.01 { break; }
                if let Some(fin) = finish_bfs(p.st, remain_cap, budget, sw, doors_m, goals) {
                    let total = d + fin.len() as i32;
                    // reconstruct prefix to this node
                    let mut path = Vec::new();
                    path.push(KEYS[p.mv as usize]);
                    let mut layer_i = (d as usize) - 1;
                    let mut idx = p.parent;
                    while layer_i > 0 {
                        let node = &layers[layer_i][idx as usize];
                        path.push(KEYS[node.mv as usize]);
                        idx = node.parent;
                        layer_i -= 1;
                    }
                    path.reverse();
                    let mut s: String = path.into_iter().collect();
                    s.push_str(&fin);
                    if best.as_ref().map(|b| total < b.0).unwrap_or(true) {
                        eprintln!("  [{}] P9-FINISH {} (pack {} + fin {}) t={:.2}s {}",
                            label, total, d, fin.len(), t0.elapsed().as_secs_f64(), s);
                        best = Some((total, s));
                    }
                }
            }
            if tried > 0 && d % 2 == 0 {
                eprintln!("  [{}] d={} perm9_in_beam={} tried_finish={}", label, d, p9.len(), tried);
            }
        }
        layers.push(next);
        if let Some((bg,_)) = &best {
            if d >= *bg { break; }
        }
    }
    eprintln!("[{}] done t={:.2}s seen={} best={:?} first99={:?}",
        label, t0.elapsed().as_secs_f64(), seen.len(),
        best.as_ref().map(|b| b.0),
        first_99.as_ref().map(|t| t.0));
    best.map(|b| b.1)
}

fn main() {
    let sw = switch_mask();
    let doors_m = door_mask();
    let goals = goal_mask();
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 || args[1] == "test" {
        test_traj(sw, doors_m);
        return;
    }
    // beam cut <cut> <max_d> <beam> <secs> [seed_suffix]
    // beam from walls ... notes max_d beam secs [seed]
    if args[1] == "beam" {
        let (start, max_d, beam, secs, seed, label) = if args[2] == "cut" {
            let cut: usize = args[3].parse().unwrap();
            let max_d: i32 = args[4].parse().unwrap();
            let beam: usize = args[5].parse().unwrap();
            let secs: f64 = args[6].parse().unwrap();
            let seed = args.get(7).cloned();
            (load_traj_state(cut), max_d, beam, secs, seed, format!("cut{cut}"))
        } else if args[2] == "from" {
            let start = St {
                walls: parse_u128(&args[3]),
                crates: parse_u128(&args[4]),
                doors: parse_u128(&args[5]),
                bx: args[6].parse().unwrap(),
                by: args[7].parse().unwrap(),
                dx: args[8].parse().unwrap(),
                dy: args[9].parse().unwrap(),
                bard: args[10] != "0",
                notes: parse_u128(&args[11]),
            };
            let max_d: i32 = args[12].parse().unwrap();
            let beam: usize = args[13].parse().unwrap();
            let secs: f64 = args[14].parse().unwrap();
            let seed = args.get(15).cloned();
            (start, max_d, beam, secs, seed, "from".into())
        } else {
            eprintln!("usage: beam cut <c> <max_d> <beam> <secs> [seed]");
            std::process::exit(2);
        };
        eprintln!("BEAM {} max_d={} beam={} t={} B=({},{}) D=({},{}) bard={} crates={} seed={}",
            label, max_d, beam, secs, start.bx, start.by, start.dx, start.dy, start.bard,
            start.crates.count_ones(), seed.is_some());
        let r = beam_search(start, max_d, beam, secs, sw, doors_m, goals, &label, seed.as_deref());
        match r {
            Some(s) => println!("SUFFIX {} {}", s.len(), s),
            None => println!("NONE"),
        }
    }
}
