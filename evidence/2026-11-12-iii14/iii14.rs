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

fn main() {
    let sw = switch_mask();
    let doors_m = door_mask();
    let goals = goal_mask();
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 || args[1] == "test" {
        test_traj(sw, doors_m);
        // speed
        let t0 = Instant::now();
        let mut n = 0u64;
        let seed = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
        while t0.elapsed().as_secs_f64() < 0.5 {
            let mut s = start_state(sw, doors_m);
            for c in seed.chars() {
                let mv = KEYS.iter().position(|&k| k == c).unwrap();
                s = step(s, mv, sw, doors_m).unwrap();
                n += 1;
            }
        }
        eprintln!("speed {:.0} steps/s", n as f64 / t0.elapsed().as_secs_f64());
        return;
    }
    if args[1] == "search" {
        // search <cut> <max_depth> <seconds> [astar|bfs]
        let cut: usize = args[2].parse().unwrap();
        let max_d: i32 = args[3].parse().unwrap();
        let secs: f64 = args[4].parse().unwrap();
        let use_astar = args.get(5).map(|s| s == "astar").unwrap_or(true);
        let start = load_traj_state(cut);
        eprintln!(
            "search cut={} max_d={} t={} astar={} B=({},{}) D=({},{}) bard={} crates={}",
            cut,
            max_d,
            secs,
            use_astar,
            start.bx,
            start.by,
            start.dx,
            start.dy,
            start.bard,
            start.crates.count_ones()
        );
        let suffix = bfs_or_astar(start, max_d, secs, sw, doors_m, goals, &format!("cut{cut}"), use_astar);
        if let Some(suf) = suffix {
            // print prefix+suffix: we'll print suffix only, python adds prefix
            println!("SUFFIX {} {}", suf.len(), suf);
        } else {
            println!("NONE");
        }
    }
}
