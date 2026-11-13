// Fast III-21 engine. rustc -O -C target-cpu=native iii21.rs -o iii21
// Part III, six heroes including Bard. Rules match verified Python iii21_eng.py.
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, HashSet, VecDeque};
use std::env;
use std::time::Instant;

const W: i32 = 23;
const H: i32 = 13;
const N: usize = 299;
const DIRS: [(i32, i32); 4] = [(0, -1), (0, 1), (-1, 0), (1, 0)]; // UDLR
const KEYS: [char; 5] = ['U', 'D', 'L', 'R', 'A'];
const GRID: [&str; 13] = [
    "#######################",
    "#.F.*....#G.G#....*.4.#",
    "#...#....#...#....#...#",
    "#######.........#######",
    "#####.#####O#####.#####",
    "#..##O#..#...#..#O##..#",
    "#.2.*....#G.G#....*.5.#",
    "#..##O#..*...#..#O##..#",
    "#####.####...####.#####",
    "#######..#..*O.*#######",
    "#...###.#######...#...#",
    "#.3.###.##G.G##...#.6.#",
    "#######################",
];
const ROUTE316: &str = "RRRDRRDRRRURRDRRUURRRRRLLLLDDAUAADLLULLLLLDDAAALLLULDDDRDLULDDLLUUAAAULLULAAUADLLLLLAAADLAAALDADRAAAALLDAULAALARUAAARRRRRAUAARDRAAARRDRRUADDRRDDRLAAUAAAULLRRURURDDAURULDDRRRRLLLLAAUUAAARDDRRRDRRRRRAAAAAULLULULULLLDUURLDLLUALLLUUAAAALLLLLDLLLDULLULLLLLLLADDRDALDDAUAAALDURADDUUAAAUAARRRRRRRRUUURUUADRDDDAAAUUURDDDAUUL";

const F: usize = 0;
const T: usize = 1;
const WIZ: usize = 2;
const P: usize = 3;
const B: usize = 4;
const D: usize = 5;
const HN: usize = 6;
const GONE: u16 = 0xFFFF;

#[inline]
fn idx(x: i32, y: i32) -> u32 {
    (y * W + x) as u32
}
#[inline]
fn xy(c: u32) -> (i32, i32) {
    ((c as i32) % W, (c as i32) / W)
}
#[inline]
fn inb(x: i32, y: i32) -> bool {
    x >= 0 && x < W && y >= 0 && y < H
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
struct Bits {
    a: u128, // 0..127
    b: u128, // 128..255
    c: u64,  // 256..298
}
impl Bits {
    #[inline]
    fn get(self, i: u32) -> bool {
        if i < 128 {
            (self.a & (1u128 << i)) != 0
        } else if i < 256 {
            (self.b & (1u128 << (i - 128))) != 0
        } else {
            (self.c & (1u64 << (i - 256))) != 0
        }
    }
    #[inline]
    fn set(&mut self, i: u32) {
        if i < 128 {
            self.a |= 1u128 << i;
        } else if i < 256 {
            self.b |= 1u128 << (i - 128);
        } else {
            self.c |= 1u64 << (i - 256);
        }
    }
    #[inline]
    fn clear(&mut self, i: u32) {
        if i < 128 {
            self.a &= !(1u128 << i);
        } else if i < 256 {
            self.b &= !(1u128 << (i - 128));
        } else {
            self.c &= !(1u64 << (i - 256));
        }
    }
    #[inline]
    fn is_empty(self) -> bool {
        self.a == 0 && self.b == 0 && self.c == 0
    }
    fn iter(self) -> BitIter {
        BitIter { a: self.a, b: self.b, c: self.c }
    }
}
struct BitIter {
    a: u128,
    b: u128,
    c: u64,
}
impl Iterator for BitIter {
    type Item = u32;
    fn next(&mut self) -> Option<u32> {
        if self.a != 0 {
            let t = self.a.trailing_zeros();
            self.a &= self.a - 1;
            return Some(t);
        }
        if self.b != 0 {
            let t = self.b.trailing_zeros();
            self.b &= self.b - 1;
            return Some(128 + t);
        }
        if self.c != 0 {
            let t = self.c.trailing_zeros();
            self.c &= self.c - 1;
            return Some(256 + t);
        }
        None
    }
}

fn goals() -> Bits {
    let mut g = Bits::default();
    for y in 0..H {
        for x in 0..W {
            if GRID[y as usize].as_bytes()[x as usize] == b'G' {
                g.set(idx(x, y));
            }
        }
    }
    g
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
struct St {
    walls: Bits,
    crates: Bits,
    gobs: Bits,
    notes: Bits,
    heroes: [u16; 6],
    active: u8,
}

impl St {
    fn start() -> St {
        let mut walls = Bits::default();
        let mut crates = Bits::default();
        let mut gobs = Bits::default();
        let mut heroes = [GONE; 6];
        let mut active = 0u8;
        for y in 0..H {
            for x in 0..W {
                let c = GRID[y as usize].as_bytes()[x as usize];
                let i = idx(x, y) as u16;
                match c {
                    b'#' => walls.set(idx(x, y)),
                    b'O' => gobs.set(idx(x, y)),
                    b'*' => crates.set(idx(x, y)),
                    b'F' => {
                        heroes[F] = i;
                        active = F as u8;
                    }
                    b'1' => heroes[F] = i,
                    b'2' => heroes[T] = i,
                    b'T' => {
                        heroes[T] = i;
                        active = T as u8;
                    }
                    b'3' => heroes[WIZ] = i,
                    b'W' => {
                        heroes[WIZ] = i;
                        active = WIZ as u8;
                    }
                    b'4' => heroes[P] = i,
                    b'P' => {
                        heroes[P] = i;
                        active = P as u8;
                    }
                    b'5' => heroes[B] = i,
                    b'B' => {
                        heroes[B] = i;
                        active = B as u8;
                    }
                    b'6' => heroes[D] = i,
                    b'D' => {
                        heroes[D] = i;
                        active = D as u8;
                    }
                    _ => {}
                }
            }
        }
        let mut s = St { walls, crates, gobs, notes: Bits::default(), heroes, active };
        s.notes = compute_notes(&s);
        s
    }

    #[inline]
    fn hero_at(&self, i: u32) -> Option<usize> {
        let iu = i as u16;
        for h in 0..HN {
            if self.heroes[h] == iu {
                return Some(h);
            }
        }
        None
    }
    #[inline]
    fn empty(&self, i: u32) -> bool {
        !self.walls.get(i) && !self.crates.get(i) && !self.gobs.get(i) && self.hero_at(i).is_none()
    }
    #[inline]
    fn moveable(&self, i: u32) -> bool {
        if self.crates.get(i) || self.gobs.get(i) {
            return true;
        }
        if let Some(h) = self.hero_at(i) {
            return h != self.active as usize;
        }
        false
    }
    #[inline]
    fn is_healer_at(&self, i: u32) -> bool {
        self.heroes[P] == i as u16
    }
    fn win(&self, g: Bits) -> bool {
        for h in 0..HN {
            if self.heroes[h] == GONE || !g.get(self.heroes[h] as u32) {
                return false;
            }
        }
        true
    }
    fn hog(&self, g: Bits) -> u8 {
        let mut n = 0u8;
        for h in 0..HN {
            if self.heroes[h] != GONE && g.get(self.heroes[h] as u32) {
                n += 1;
            }
        }
        n
    }
    fn nheroes(&self) -> u8 {
        self.heroes.iter().filter(|&&p| p != GONE).count() as u8
    }
    fn render(&self) -> String {
        let g = goals();
        let mut s = String::with_capacity((W as usize + 1) * H as usize);
        for y in 0..H {
            for x in 0..W {
                let i = idx(x, y);
                let ch = if self.walls.get(i) {
                    '#'
                } else if self.crates.get(i) {
                    '*'
                } else if self.gobs.get(i) {
                    'O'
                } else if let Some(h) = self.hero_at(i) {
                    if h == self.active as usize {
                        ['F', 'T', 'W', 'P', 'B', 'D'][h]
                    } else {
                        ['1', '2', '3', '4', '5', '6'][h]
                    }
                } else if g.get(i) {
                    'G'
                } else {
                    '.'
                };
                s.push(ch);
            }
            if y + 1 != H {
                s.push('\n');
            }
        }
        s
    }
}

fn compute_notes(s: &St) -> Bits {
    let mut notes = Bits::default();
    if s.active as usize != B {
        return notes;
    }
    let bp = s.heroes[B];
    if bp == GONE {
        return notes;
    }
    let (bx, by) = xy(bp as u32);
    for ny in (by - 2).max(0)..(by + 3).min(H) {
        for nx in (bx - 2).max(0)..(bx + 3).min(W) {
            if nx == bx && ny == by {
                continue;
            }
            let i = idx(nx, ny);
            if s.moveable(i) {
                notes.set(i);
            }
        }
    }
    notes
}

fn late(s: &mut St) -> bool {
    let mut dying = Bits::default();
    for gi in s.gobs.iter() {
        let (x, y) = xy(gi);
        for &(dx, dy) in &DIRS {
            let nx = x + dx;
            let ny = y + dy;
            if inb(nx, ny) {
                let j = idx(nx, ny);
                if s.gobs.get(j) || s.hero_at(j).is_some() {
                    dying.set(j);
                }
            }
        }
    }
    if !dying.is_empty() {
        let pc = s.heroes[P];
        if pc != GONE {
            dying.clear(pc as u32);
            let (x, y) = xy(pc as u32);
            for &(dx, dy) in &DIRS {
                let nx = x + dx;
                let ny = y + dy;
                if inb(nx, ny) {
                    let j = idx(nx, ny);
                    if s.hero_at(j).is_some() {
                        dying.clear(j);
                    }
                }
            }
        }
        let mut dead = false;
        let cells: Vec<u32> = dying.iter().collect();
        for j in cells {
            if s.gobs.get(j) {
                s.gobs.clear(j);
            } else if s.hero_at(j).is_some() {
                dead = true;
            }
        }
        s.notes = compute_notes(s);
        return dead;
    }
    s.notes = compute_notes(s);
    false
}

fn xfer(s: &mut St, from: u32, to: u32) {
    if s.crates.get(from) {
        s.crates.clear(from);
        s.crates.set(to);
    } else if s.gobs.get(from) {
        s.gobs.clear(from);
        s.gobs.set(to);
    } else if let Some(h) = s.hero_at(from) {
        s.heroes[h] = to as u16;
    }
}

/// Step. Returns (alive, won, changed). Bard-cancel restores and skips late.
fn step(s: &mut St, key: char, g: Bits) -> (bool, bool, bool) {
    let before = *s;
    let ai = s.active as usize;
    let ap = s.heroes[ai];
    if ap == GONE {
        return (false, false, false);
    }
    let (ax, ay) = xy(ap as u32);

    if key == 'A' {
        for off in 1..HN {
            let t = (ai + off) % HN;
            if s.heroes[t] != GONE {
                s.active = t as u8;
                break;
            }
        }
        if late(s) {
            return (false, false, true);
        }
        return (true, s.win(g), *s != before);
    }

    let (dx, dy) = match key {
        'U' => (0, -1),
        'D' => (0, 1),
        'L' => (-1, 0),
        'R' => (1, 0),
        _ => return (true, s.win(g), false),
    };
    let nx = ax + dx;
    let ny = ay + dy;

    match ai {
        F => {
            if inb(nx, ny) {
                let mut cx = nx;
                let mut cy = ny;
                while inb(cx, cy) && s.moveable(idx(cx, cy)) {
                    cx += dx;
                    cy += dy;
                }
                if inb(cx, cy) && s.empty(idx(cx, cy)) {
                    while (cx, cy) != (ax, ay) {
                        let px = cx - dx;
                        let py = cy - dy;
                        xfer(s, idx(px, py), idx(cx, cy));
                        cx = px;
                        cy = py;
                    }
                    s.heroes[F] = idx(nx, ny) as u16;
                }
            }
        }
        T => {
            if inb(nx, ny) && s.empty(idx(nx, ny)) {
                s.heroes[T] = idx(nx, ny) as u16;
                let bx = ax - dx;
                let by = ay - dy;
                if inb(bx, by) && s.moveable(idx(bx, by)) {
                    xfer(s, idx(bx, by), ap as u32);
                }
            }
        }
        WIZ => {
            let mut wx = ax;
            let mut wy = ay;
            loop {
                let tx = wx + dx;
                let ty = wy + dy;
                if !inb(tx, ty) {
                    if inb(nx, ny) && s.empty(idx(nx, ny)) {
                        s.heroes[WIZ] = idx(nx, ny) as u16;
                    }
                    break;
                }
                let ti = idx(tx, ty);
                if s.empty(ti) {
                    wx = tx;
                    wy = ty;
                } else if s.walls.get(ti) {
                    if s.empty(idx(nx, ny)) {
                        s.heroes[WIZ] = idx(nx, ny) as u16;
                    }
                    break;
                } else if s.moveable(ti) {
                    xfer(s, ti, ap as u32);
                    s.heroes[WIZ] = ti as u16;
                    break;
                } else {
                    break;
                }
            }
        }
        P => {
            if inb(nx, ny) && s.empty(idx(nx, ny)) {
                s.heroes[P] = idx(nx, ny) as u16;
            }
        }
        D => {
            if inb(nx, ny) {
                let ti = idx(nx, ny);
                if s.empty(ti) {
                    s.heroes[D] = ti as u16;
                } else if s.crates.get(ti) || s.gobs.get(ti) {
                    s.crates.clear(ti);
                    s.gobs.clear(ti);
                    s.walls.set(ti);
                } else if s.walls.get(ti) {
                    s.walls.clear(ti);
                    s.crates.set(ti);
                } else if s.is_healer_at(ti) {
                } else if s.hero_at(ti).is_some() {
                    let (hx, hy) = xy(ti);
                    let mut adj = false;
                    for &(ddx, ddy) in &DIRS {
                        let qx = hx + ddx;
                        let qy = hy + ddy;
                        if inb(qx, qy) && s.is_healer_at(idx(qx, qy)) {
                            adj = true;
                            break;
                        }
                    }
                    if !adj {
                        if let Some(h) = s.hero_at(ti) {
                            s.heroes[h] = GONE;
                        }
                        s.walls.set(ti);
                    }
                }
            }
        }
        B => {
            let mut charmed = s.notes;
            let mut bard = ap as u32;
            let mut bard_moved = false;
            loop {
                let mut changed_m = false;
                let cells: Vec<u32> = charmed.iter().collect();
                for c in cells {
                    if !charmed.get(c) {
                        continue;
                    }
                    if !s.moveable(c) && s.hero_at(c).is_none() && s.empty(c) {
                        charmed.clear(c);
                        continue;
                    }
                    // moveable check: a charmed cell should still have the object
                    // (if it was already moved this pass, it isn't at c)
                    if !s.moveable(c) {
                        // object gone or is the now-active bard? skip
                        continue;
                    }
                    let (x, y) = xy(c);
                    let tx = x + dx;
                    let ty = y + dy;
                    if inb(tx, ty) && s.empty(idx(tx, ty)) {
                        xfer(s, c, idx(tx, ty));
                        charmed.clear(c);
                        changed_m = true;
                    }
                }
                if !bard_moved {
                    let (bx, by) = xy(bard);
                    let tx = bx + dx;
                    let ty = by + dy;
                    if inb(tx, ty) && s.empty(idx(tx, ty)) {
                        s.heroes[B] = idx(tx, ty) as u16;
                        bard = s.heroes[B] as u32;
                        bard_moved = true;
                        changed_m = true;
                    }
                }
                if !changed_m {
                    break;
                }
            }
            if !bard_moved {
                *s = before;
                return (true, s.win(g), false);
            }
            s.notes = Bits::default();
        }
        _ => {}
    }

    if late(s) {
        return (false, false, true);
    }
    (true, s.win(g), *s != before)
}

fn apply_route(s: &mut St, route: &str, g: Bits) -> (bool, bool, usize) {
    for (i, ch) in route.chars().enumerate() {
        let (alive, won, _) = step(s, ch, g);
        if !alive {
            return (false, false, i + 1);
        }
        if won && i + 1 != route.len() {
            return (true, false, i + 1);
        }
    }
    (true, s.win(g), route.len())
}

fn apply_prefix(n: usize) -> St {
    let g = goals();
    let mut s = St::start();
    apply_route(&mut s, &ROUTE316[..n], g);
    s
}

fn manh(a: u32, b: u32) -> i32 {
    let (ax, ay) = xy(a);
    let (bx, by) = xy(b);
    (ax - bx).abs() + (ay - by).abs()
}

fn heuristic(s: &St, g: Bits) -> i32 {
    let mut unplaced: Vec<u32> = Vec::new();
    let mut free: Vec<u32> = Vec::new();
    for h in 0..HN {
        let p = s.heroes[h];
        if p == GONE {
            return 1_000_000;
        }
        if !g.get(p as u32) {
            unplaced.push(p as u32);
        }
    }
    for i in 0..N as u32 {
        if g.get(i) && s.hero_at(i).is_none() {
            free.push(i);
        }
    }
    if unplaced.is_empty() {
        return 0;
    }
    if unplaced.len() != free.len() {
        return 1_000_000;
    }
    let k = unplaced.len();
    let mut best = 1_000_000;
    fn rec(u: &[u32], f: &mut [u32], i: usize, cur: i32, best: &mut i32) {
        if cur >= *best {
            return;
        }
        if i == u.len() {
            *best = cur;
            return;
        }
        for j in i..f.len() {
            f.swap(i, j);
            rec(u, f, i + 1, cur + manh(u[i], f[i]), best);
            f.swap(i, j);
        }
    }
    rec(&unplaced, &mut free, 0, 0, &mut best);
    let active_on = g.get(s.heroes[s.active as usize] as u32);
    let sw = if active_on { k as i32 } else { (k as i32 - 1).max(0) };
    best + sw
}

fn verify() {
    let g = goals();
    assert_eq!(ROUTE316.len(), 316);
    let mut s = St::start();
    // compare frames against a dump if present — just check win
    let (alive, won, k) = apply_route(&mut s, ROUTE316, g);
    println!(
        "RUST 316 alive={} win={} steps={} hog={} active={}",
        alive, won, k, s.hog(g), s.active
    );
    if !alive || !won || k != 316 {
        println!("{}", s.render());
        std::process::exit(1);
    }
    println!("{}", s.render());
}

fn speed() {
    let g = goals();
    let base = apply_prefix(80);
    let t0 = Instant::now();
    let mut n = 0u64;
    while t0.elapsed().as_secs_f64() < 1.0 {
        let mut s = base;
        step(&mut s, 'R', g);
        n += 1;
    }
    println!("copy+step /s from cut 80: {}", n);
}

// ---------- A* (h only for ordering; may be inadmissible) ----------
#[derive(Clone, Eq, PartialEq)]
struct Node {
    f: i32,
    g: i32,
    s: St,
}
impl Ord for Node {
    fn cmp(&self, o: &Self) -> Ordering {
        o.f.cmp(&self.f).then_with(|| o.g.cmp(&self.g))
    }
}
impl PartialOrd for Node {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}

fn reconstruct(parent: &HashMap<St, (St, char)>, start: St, end: St) -> String {
    let mut route = Vec::new();
    let mut cur = end;
    while let Some(&(p, k)) = parent.get(&cur) {
        route.push(k);
        cur = p;
        if cur == start {
            break;
        }
    }
    route.reverse();
    route.into_iter().collect()
}

fn astar(start: St, max_d: i32, secs: f64, gmask: Bits) -> (Option<String>, u64, usize, &'static str) {
    let t0 = Instant::now();
    if start.win(gmask) {
        return (Some(String::new()), 0, 1, "win");
    }
    let h0 = heuristic(&start, gmask);
    let mut heap = BinaryHeap::new();
    heap.push(Node { f: h0, g: 0, s: start });
    let mut best_g: HashMap<St, u16> = HashMap::new();
    best_g.insert(start, 0);
    let mut parent: HashMap<St, (St, char)> = HashMap::new();
    let mut exp: u64 = 0;
    let mut found: Option<St> = None;
    let mut found_g = 0i32;
    while let Some(Node { f: _, g, s }) = heap.pop() {
        if t0.elapsed().as_secs_f64() > secs {
            return (None, exp, best_g.len(), "timeout");
        }
        if let Some(&bg) = best_g.get(&s) {
            if g > bg as i32 {
                continue;
            }
        }
        if s.win(gmask) && g > 0 {
            found = Some(s);
            found_g = g;
            break;
        }
        if g >= max_d {
            continue;
        }
        exp += 1;
        for &k in &KEYS {
            let mut ns = s;
            let (alive, won, changed) = step(&mut ns, k, gmask);
            if !alive || (!changed && !won) {
                continue;
            }
            if ns.nheroes() < 6 {
                continue;
            }
            let ng = g + 1;
            if ng > max_d {
                continue;
            }
            if let Some(&bg) = best_g.get(&ns) {
                if ng >= bg as i32 {
                    continue;
                }
            }
            let nh = heuristic(&ns, gmask);
            best_g.insert(ns, ng as u16);
            parent.insert(ns, (s, k));
            if won {
                found = Some(ns);
                found_g = ng;
                // don't break from key loop via goto; handle below
                heap.clear();
                break;
            }
            heap.push(Node { f: ng + nh, g: ng, s: ns });
        }
        if found.is_some() {
            break;
        }
    }
    if let Some(end) = found {
        let r = reconstruct(&parent, start, end);
        if r.len() as i32 != found_g {
            // start may equal end only if g=0
        }
        return (Some(r), exp, best_g.len(), "found");
    }
    if t0.elapsed().as_secs_f64() > secs {
        (None, exp, best_g.len(), "timeout")
    } else {
        (None, exp, best_g.len(), "exhausted")
    }
}

fn bfs(start: St, max_d: i32, secs: f64, gmask: Bits) -> (Option<String>, u64, usize, &'static str) {
    let t0 = Instant::now();
    if start.win(gmask) {
        return (Some(String::new()), 0, 1, "win");
    }
    let mut q = VecDeque::new();
    q.push_back((start, 0u16));
    let mut parent: HashMap<St, (St, char)> = HashMap::new();
    parent.insert(start, (start, '?'));
    let mut exp: u64 = 0;
    while let Some((s, g)) = q.pop_front() {
        if t0.elapsed().as_secs_f64() > secs {
            return (None, exp, parent.len(), "timeout");
        }
        if g as i32 >= max_d {
            continue;
        }
        exp += 1;
        for &k in &KEYS {
            let mut ns = s;
            let (alive, won, changed) = step(&mut ns, k, gmask);
            if !alive || (!changed && !won) {
                continue;
            }
            if ns.nheroes() < 6 {
                continue;
            }
            if parent.contains_key(&ns) {
                continue;
            }
            parent.insert(ns, (s, k));
            if won {
                let r = reconstruct(&parent, start, ns);
                return (Some(r), exp, parent.len(), "found");
            }
            q.push_back((ns, g + 1));
        }
    }
    (None, exp, parent.len(), "exhausted")
}

fn beam(start: St, max_d: i32, width: usize, secs: f64, gmask: Bits, cut: usize) -> (Option<String>, u64, usize) {
    let budget = (316 - cut) as i32; // known record remaining; beat this

    let t0 = Instant::now();
    let mut cur: Vec<(St, String)> = vec![(start, String::new())];
    let mut seen: HashMap<St, u16> = HashMap::new();
    seen.insert(start, 0);
    let mut exp: u64 = 0;
    let mut best_win: Option<String> = None;
    let mut best_hog = start.hog(gmask);
    while !cur.is_empty() {
        if t0.elapsed().as_secs_f64() > secs {
            return (best_win, exp, seen.len());
        }
        let mut nxt: Vec<(St, String, i32, u8, i32)> = Vec::new();
        for (s, path) in &cur {
            let g = path.len() as i32;
            if g >= max_d {
                continue;
            }
            exp += 1;
            for &k in &KEYS {
                let mut ns = *s;
                let (alive, won, changed) = step(&mut ns, k, gmask);
                if !alive || (!changed && !won) {
                    continue;
                }
                if ns.nheroes() < 6 {
                    continue;
                }
                let np = {
                    let mut t = path.clone();
                    t.push(k);
                    t
                };
                let ng = np.len() as u16;
                if let Some(&bg) = seen.get(&ns) {
                    if ng >= bg {
                        continue;
                    }
                }
                seen.insert(ns, ng);
                if won {
                    println!("  BEAM WIN {} {}", np.len(), np); // full
                    if best_win.as_ref().map_or(true, |b| np.len() < b.len()) {
                        best_win = Some(np);
                    }
                    continue;
                }
                let hog = ns.hog(gmask);
                let h = heuristic(&ns, gmask);
                if hog > best_hog {
                    best_hog = hog;
                    println!("  BEAM hog={} at {} h={} {}", hog, ng, h, np);
                    let remain = budget - ng as i32 - 1; // must beat 316
                    if remain > 0 && remain < 80 {
                        let secs_f = if hog >= 4 { 20.0 } else { 8.0 };
                        let (fp, fexp, fseen, fst) = astar(ns, remain, secs_f, gmask);
                        println!("    A* finish remain={} {} exp={} seen={} {:?}", remain, fst, fexp, fseen, fp.as_ref().map(|p| p.len()));
                        if let Some(fin) = fp {
                            let full = format!("{}{}", np, fin);
                            println!("    BEAM+A* WIN from cut via {} keys: {}", full.len(), full);
                            if best_win.as_ref().map_or(true, |b| full.len() < b.len()) {
                                best_win = Some(full);
                            }
                        }
                    }
                }
                nxt.push((ns, np, g + 1 + h, hog, h));
            }
        }
        if nxt.is_empty() {
            break;
        }
        nxt.sort_by_key(|t| (-(t.3 as i32), t.2, t.4, t.1.len() as i32));
        // diversity
        let mut picked: Vec<(St, String)> = Vec::new();
        let mut groups: HashMap<(u8, u8, u8), usize> = HashMap::new();
        for (s, p, _, hog, _) in nxt {
            let mut parked = 0u8;
            for h in 0..HN {
                if gmask.get(s.heroes[h] as u32) {
                    parked |= 1 << h;
                }
            }
            let key = (hog, s.active, parked);
            let c = groups.entry(key).or_insert(0);
            let cap = (width / 12).max(4);
            if *c < cap || picked.len() < width {
                if *c < cap * 2 {
                    picked.push((s, p));
                    *c += 1;
                }
            }
            if picked.len() >= width {
                break;
            }
        }
        cur = picked;
    }
    (best_win, exp, seen.len())
}

fn window_search(a: usize, b: usize, secs: f64, gmask: Bits) -> (Option<String>, u64, usize, &'static str) {
    let sa = apply_prefix(a);
    let sb = apply_prefix(b);
    let t0 = Instant::now();
    let mut q = VecDeque::new();
    q.push_back((sa, 0u16));
    let mut parent: HashMap<St, (St, char)> = HashMap::new();
    parent.insert(sa, (sa, '?'));
    let need = (b - a) as i32;
    let mut exp: u64 = 0;
    while let Some((s, g)) = q.pop_front() {
        if t0.elapsed().as_secs_f64() > secs {
            return (None, exp, parent.len(), "timeout");
        }
        if g as i32 >= need {
            continue;
        }
        exp += 1;
        for &k in &KEYS {
            let mut ns = s;
            let (alive, won, changed) = step(&mut ns, k, gmask);
            if !alive || (!changed && !won) {
                continue;
            }
            if parent.contains_key(&ns) {
                continue;
            }
            parent.insert(ns, (s, k));
            if ns == sb {
                let r = reconstruct(&parent, sa, ns);
                return (Some(r), exp, parent.len(), "found");
            }
            if won {
                let r = reconstruct(&parent, sa, ns);
                return (Some(r), exp, parent.len(), "early_win");
            }
            q.push_back((ns, g + 1));
        }
    }
    (None, exp, parent.len(), "exhausted")
}


fn wiz_escaped(s: &St) -> bool {
    if s.heroes[WIZ] == GONE {
        return false;
    }
    let (x, y) = xy(s.heroes[WIZ] as u32);
    !(x <= 3 && y >= 10)
}

fn crate_at_19(s: &St) -> bool {
    s.crates.get(idx(1, 9))
}

fn wall19_open(s: &St) -> bool {
    !s.walls.get(idx(1, 9))
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum SeekGoal {
    Escape,
    Crate19,
    Open19,
    Win,
}

fn goal_hit(s: &St, goal: SeekGoal, won: bool) -> bool {
    if won {
        return true;
    }
    match goal {
        SeekGoal::Escape => wiz_escaped(s),
        SeekGoal::Crate19 => crate_at_19(s),
        SeekGoal::Open19 => wall19_open(s),
        SeekGoal::Win => false, // won is passed separately
    }
}

/// Packed-parent BFS. `freeze` is a bitmask of hero indices that may only press A.
fn seek_wescape(
    start: St,
    max_d: i32,
    secs: f64,
    cap: usize,
    gmask: Bits,
    freeze: u8,
    goal: SeekGoal,
) -> (Option<String>, u64, usize, &'static str) {
    let t0 = Instant::now();
    if goal_hit(&start, goal, false) {
        return (Some(String::new()), 0, 1, "already");
    }
    let mut nodes: Vec<St> = Vec::with_capacity(cap.min(2_000_000));
    let mut prevs: Vec<(u32, u8)> = Vec::with_capacity(cap.min(2_000_000));
    let mut gs: Vec<u16> = Vec::with_capacity(cap.min(2_000_000));
    let mut seen: HashSet<St> = HashSet::with_capacity(cap.min(2_000_000));
    nodes.push(start);
    prevs.push((u32::MAX, b'?'));
    gs.push(0);
    seen.insert(start);
    let mut qh: usize = 0;
    let mut exp: u64 = 0;
    let mut cur_d = 0u16;
    let mut layer_start_exp = 0u64;
    while qh < nodes.len() {
        if t0.elapsed().as_secs_f64() > secs {
            println!(
                "  stop timeout at g={} seen={} exp={}",
                gs.get(qh).copied().unwrap_or(cur_d),
                seen.len(),
                exp
            );
            return (None, exp, seen.len(), "timeout");
        }
        if seen.len() >= cap {
            println!(
                "  stop cap at g={} seen={} exp={}",
                gs.get(qh).copied().unwrap_or(cur_d),
                seen.len(),
                exp
            );
            return (None, exp, seen.len(), "cap");
        }
        let s = nodes[qh];
        let g = gs[qh];
        let idx0 = qh as u32;
        qh += 1;
        if g != cur_d {
            println!(
                "  completed depth {} exp_layer={} seen={} t={:.2}s",
                cur_d,
                exp - layer_start_exp,
                seen.len(),
                t0.elapsed().as_secs_f64()
            );
            cur_d = g;
            layer_start_exp = exp;
        }
        if g as i32 >= max_d {
            continue;
        }
        exp += 1;
        let frozen_active = (freeze & (1u8 << s.active)) != 0;
        for &k in &KEYS {
            if frozen_active && k != 'A' {
                continue;
            }
            let mut ns = s;
            let (alive, won, changed) = step(&mut ns, k, gmask);
            if !alive || (!changed && !won) {
                continue;
            }
            if ns.nheroes() < 6 {
                continue;
            }
            if seen.contains(&ns) {
                continue;
            }
            seen.insert(ns);
            nodes.push(ns);
            prevs.push((idx0, k as u8));
            gs.push(g + 1);
            if goal_hit(&ns, goal, won) {
                let mut path = Vec::new();
                let mut i = (nodes.len() - 1) as u32;
                while i != 0 {
                    let (p, ch) = prevs[i as usize];
                    path.push(ch as char);
                    i = p;
                }
                path.reverse();
                let r: String = path.into_iter().collect();
                let why = if won {
                    "win"
                } else if wiz_escaped(&ns) {
                    "escaped"
                } else if crate_at_19(&ns) {
                    "crate19"
                } else {
                    "open19"
                };
                return (Some(r), exp, seen.len(), why);
            }
        }
    }
    println!(
        "  exhausted after depth {} seen={} exp={}",
        cur_d, seen.len(), exp
    );
    (None, exp, seen.len(), "exhausted")
}

/// Domain-guided beam toward opening (1,9) and freeing W. Discovery, not a proof.
fn score_escape(s: &St, gmask: Bits) -> i32 {
    let c18 = idx(1, 8);
    let c19 = idx(1, 9);
    if wiz_escaped(s) {
        return 2_000_000 + s.hog(gmask) as i32 * 10;
    }
    let mut sc: i32 = s.hog(gmask) as i32 * 30;
    if s.crates.get(c19) {
        sc += 80_000;
    } else if !s.walls.get(c19) {
        sc += 60_000;
    }
    if s.crates.get(c18) {
        sc += 10_000;
    } else if !s.walls.get(c18) {
        sc += 7_000;
    }
    if s.heroes[D] != GONE {
        let (x, y) = xy(s.heroes[D] as u32);
        let (tx, ty) = if s.walls.get(c18) {
            (1, 7)
        } else if s.walls.get(c19) {
            (1, 8)
        } else {
            (1, 6)
        };
        sc -= ((x - tx).abs() + (y - ty).abs()) * 120;
        // bonus: D standing on the convert cell
        if !s.walls.get(c18) && x == 1 && y == 7 {
            sc += 2_000;
        }
        if !s.walls.get(c19) == false && !s.walls.get(c18) && x == 1 && y == 8 {
            sc += 4_000;
        }
    }
    if s.heroes[F] != GONE {
        let (x, y) = xy(s.heroes[F] as u32);
        sc -= ((x - 12).abs() + (y - 11).abs()) * 8;
    }
    sc
}

fn seek_beam(
    start: St,
    max_d: i32,
    width: usize,
    secs: f64,
    cap: usize,
    gmask: Bits,
    freeze: u8,
) -> (Option<String>, u64, usize, &'static str) {
    let t0 = Instant::now();
    if wiz_escaped(&start) {
        return (Some(String::new()), 0, 1, "already");
    }
    // parent map: we store path on the beam node to avoid huge parent tables
    #[derive(Clone)]
    struct Node {
        s: St,
        path: String,
    }
    let mut layer: Vec<Node> = vec![Node { s: start, path: String::new() }];
    let mut seen: HashSet<St> = HashSet::new();
    seen.insert(start);
    let mut exp: u64 = 0;
    let mut best: Option<(i32, String, St)> = None;
    for d in 0..max_d {
        if t0.elapsed().as_secs_f64() > secs {
            return (
                best.as_ref().map(|b| b.1.clone()),
                exp,
                seen.len(),
                if best.is_some() { "timeout-best" } else { "timeout" },
            );
        }
        let mut nxt: Vec<(i32, Node)> = Vec::new();
        for node in &layer {
            exp += 1;
            let frozen_active = (freeze & (1u8 << node.s.active)) != 0;
            for &k in &KEYS {
                if frozen_active && k != 'A' {
                    continue;
                }
                let mut ns = node.s;
                let (alive, won, changed) = step(&mut ns, k, gmask);
                if !alive || (!changed && !won) {
                    continue;
                }
                if ns.nheroes() < 6 {
                    continue;
                }
                if seen.contains(&ns) {
                    continue;
                }
                seen.insert(ns);
                if seen.len() >= cap {
                    return (
                        best.as_ref().map(|b| b.1.clone()),
                        exp,
                        seen.len(),
                        if best.is_some() { "cap-best" } else { "cap" },
                    );
                }
                let mut path = String::with_capacity(node.path.len() + 1);
                path.push_str(&node.path);
                path.push(k);
                let sc = score_escape(&ns, gmask);
                if wiz_escaped(&ns) || won {
                    println!(
                        "  beam hit {} at d={} score={} path={}",
                        if won { "WIN" } else { "ESCAPE" },
                        d + 1,
                        sc,
                        path
                    );
                    return (Some(path), exp, seen.len(), if won { "win" } else { "escaped" });
                }
                if crate_at_19(&ns) {
                    let ev = (sc, path.clone(), ns);
                    let take = match &best {
                        None => true,
                        Some(b) => ev.0 > b.0 || (ev.0 == b.0 && ev.1.len() < b.1.len()),
                    };
                    if take {
                        println!("  beam crate19 at d={} score={} path={}", d + 1, sc, path);
                        best = Some(ev);
                    }
                }
                nxt.push((sc, Node { s: ns, path }));
            }
        }
        if nxt.is_empty() {
            break;
        }
        nxt.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.path.len().cmp(&b.1.path.len())));
        if nxt.len() > width {
            nxt.truncate(width);
        }
        if d % 2 == 1 || d >= 10 {
            println!(
                "  beam d={} kept={} best_sc={} seen={} t={:.2}s crate19={}",
                d + 1,
                nxt.len(),
                nxt[0].0,
                seen.len(),
                t0.elapsed().as_secs_f64(),
                best.as_ref().map(|b| b.1.len()).unwrap_or(0)
            );
        }
        layer = nxt.into_iter().map(|(_, n)| n).collect();
    }
    if let Some(b) = best {
        (Some(b.1), exp, seen.len(), "crate19")
    } else {
        (None, exp, seen.len(), "none")
    }
}


fn states_equal(a: &St, b: &St) -> bool {
    a == b
}

/// Packed BFS from start to an exact target state.
fn seek_state(
    start: St,
    target: St,
    max_d: i32,
    secs: f64,
    cap: usize,
    gmask: Bits,
    freeze: u8,
) -> (Option<String>, u64, usize, &'static str) {
    let t0 = Instant::now();
    if start == target {
        return (Some(String::new()), 0, 1, "already");
    }
    let mut nodes: Vec<St> = Vec::with_capacity(cap.min(2_000_000));
    let mut prevs: Vec<(u32, u8)> = Vec::with_capacity(cap.min(2_000_000));
    let mut gs: Vec<u16> = Vec::with_capacity(cap.min(2_000_000));
    let mut seen: HashSet<St> = HashSet::with_capacity(cap.min(2_000_000));
    nodes.push(start);
    prevs.push((u32::MAX, b'?'));
    gs.push(0);
    seen.insert(start);
    let mut qh: usize = 0;
    let mut exp: u64 = 0;
    let mut cur_d = 0u16;
    let mut layer_start_exp = 0u64;
    while qh < nodes.len() {
        if t0.elapsed().as_secs_f64() > secs {
            println!(
                "  stop timeout at g={} seen={} exp={}",
                gs.get(qh).copied().unwrap_or(cur_d),
                seen.len(),
                exp
            );
            return (None, exp, seen.len(), "timeout");
        }
        if seen.len() >= cap {
            println!(
                "  stop cap at g={} seen={} exp={}",
                gs.get(qh).copied().unwrap_or(cur_d),
                seen.len(),
                exp
            );
            return (None, exp, seen.len(), "cap");
        }
        let s = nodes[qh];
        let g = gs[qh];
        let idx0 = qh as u32;
        qh += 1;
        if g != cur_d {
            println!(
                "  completed depth {} exp_layer={} seen={} t={:.2}s",
                cur_d,
                exp - layer_start_exp,
                seen.len(),
                t0.elapsed().as_secs_f64()
            );
            cur_d = g;
            layer_start_exp = exp;
        }
        if g as i32 >= max_d {
            continue;
        }
        exp += 1;
        let frozen_active = (freeze & (1u8 << s.active)) != 0;
        for &k in &KEYS {
            if frozen_active && k != 'A' {
                continue;
            }
            let mut ns = s;
            let (alive, won, changed) = step(&mut ns, k, gmask);
            if !alive || (!changed && !won) {
                continue;
            }
            if ns.nheroes() < 6 {
                continue;
            }
            if seen.contains(&ns) {
                continue;
            }
            seen.insert(ns);
            nodes.push(ns);
            prevs.push((idx0, k as u8));
            gs.push(g + 1);
            if ns == target || won {
                let mut path = Vec::new();
                let mut i = (nodes.len() - 1) as u32;
                while i != 0 {
                    let (p, ch) = prevs[i as usize];
                    path.push(ch as char);
                    i = p;
                }
                path.reverse();
                let r: String = path.into_iter().collect();
                return (
                    Some(r),
                    exp,
                    seen.len(),
                    if won { "win" } else { "match" },
                );
            }
        }
    }
    println!(
        "  exhausted after depth {} seen={} exp={}",
        cur_d, seen.len(), exp
    );
    (None, exp, seen.len(), "exhausted")
}

include!("shot.rs");

fn main() {
    let args: Vec<String> = env::args().collect();
    let g = goals();
    if args.len() < 2 || args[1] == "test" {
        verify();
        speed();
        return;
    }
    let cmd = args[1].as_str();
    match cmd {
        "prefix" => {
            let n: usize = args[2].parse().unwrap();
            let s = apply_prefix(n);
            println!("{}", s.render());
            println!(
                "hog={} h={} active={} g+h={}",
                s.hog(g),
                heuristic(&s, g),
                s.active,
                n as i32 + heuristic(&s, g)
            );
        }
        "astar" => {
            let cut: usize = args[2].parse().unwrap();
            let maxd: i32 = args[3].parse().unwrap();
            let secs: f64 = if args.len() > 4 { args[4].parse().unwrap() } else { 30.0 };
            let s = apply_prefix(cut);
            println!(
                "A* from {} maxd={} h={} hog={} secs={}",
                cut, maxd, heuristic(&s, g), s.hog(g), secs
            );
            let (path, exp, seen, st) = astar(s, maxd, secs, g);
            println!(
                "result {} exp={} seen={} path={:?} len={:?}",
                st, exp, seen, path, path.as_ref().map(|p| p.len())
            );
            if let Some(p) = path {
                let full = format!("{}{}", &ROUTE316[..cut], p);
                println!("FULL {}", full.len());
                let mut s2 = St::start();
                let (a, w, k) = apply_route(&mut s2, &full, g);
                println!("verify alive={} win={} steps={}", a, w, k);
            }
        }
        "bfs" => {
            let cut: usize = args[2].parse().unwrap();
            let maxd: i32 = args[3].parse().unwrap();
            let secs: f64 = if args.len() > 4 { args[4].parse().unwrap() } else { 30.0 };
            let s = apply_prefix(cut);
            println!(
                "BFS from {} maxd={} h={} hog={} secs={}",
                cut, maxd, heuristic(&s, g), s.hog(g), secs
            );
            let (path, exp, seen, st) = bfs(s, maxd, secs, g);
            println!(
                "result {} exp={} seen={} path={:?} len={:?}",
                st, exp, seen, path, path.as_ref().map(|p| p.len())
            );
            if let Some(p) = path {
                let full = format!("{}{}", &ROUTE316[..cut], p);
                println!("FULL {}", full.len());
                let mut s2 = St::start();
                let (a, w, k) = apply_route(&mut s2, &full, g);
                println!("verify alive={} win={} steps={}", a, w, k);
            }
        }
        "beam" => {
            let cut: usize = args[2].parse().unwrap();
            let maxd: i32 = args[3].parse().unwrap();
            let width: usize = args[4].parse().unwrap();
            let secs: f64 = if args.len() > 5 { args[5].parse().unwrap() } else { 30.0 };
            let s = apply_prefix(cut);
            println!(
                "BEAM from {} maxd={} w={} h={} hog={} secs={}",
                cut, maxd, width, heuristic(&s, g), s.hog(g), secs
            );
            let (path, exp, seen) = beam(s, maxd, width, secs, g, cut);
            println!(
                "result exp={} seen={} path={:?} len={:?}",
                exp, seen, path, path.as_ref().map(|p| p.len())
            );
            if let Some(p) = path {
                let full = format!("{}{}", &ROUTE316[..cut], p);
                println!("FULL {}", full.len());
                let mut s2 = St::start();
                let (a, w, k) = apply_route(&mut s2, &full, g);
                println!("verify alive={} win={} steps={}", a, w, k);
            }
        }
        "window" => {
            let a: usize = args[2].parse().unwrap();
            let b: usize = args[3].parse().unwrap();
            let secs: f64 = if args.len() > 4 { args[4].parse().unwrap() } else { 8.0 };
            let (path, exp, seen, st) = window_search(a, b, secs, g);
            println!(
                "window {}->{} {} exp={} seen={} len={:?} saved={}",
                a, b, st, exp, seen,
                path.as_ref().map(|p| p.len()),
                path.as_ref().map(|p| (b - a) - p.len()).unwrap_or(0)
            );
            if let Some(p) = path {
                if p.len() < b - a {
                    let full = format!("{}{}{}", &ROUTE316[..a], p, &ROUTE316[b..]);
                    println!("FULL {} {}", full.len(), p);
                    let mut s2 = St::start();
                    let (al, w, k) = apply_route(&mut s2, &full, g);
                    println!("verify alive={} win={} steps={}", al, w, k);
                }
            }
        }
        "seek" | "seek-beam" => {
            let cut: usize = args[2].parse().unwrap();
            let maxd: i32 = args[3].parse().unwrap();
            let secs: f64 = if args.len() > 4 { args[4].parse().unwrap() } else { 60.0 };
            let cap: usize = if args.len() > 5 { args[5].parse().unwrap() } else { 6_000_000 };
            let mut s = apply_prefix(cut);
            let mut freeze: u8 = 0;
            let mut goal = SeekGoal::Escape;
            let mut width: usize = 200_000;
            let mut extra = String::new();
            for a in args.iter().skip(6) {
                let au = a.as_str();
                if let Some(rest) = au.strip_prefix("freeze=") {
                    for c in rest.chars() {
                        let i = match c {
                            'F' | 'f' => F,
                            'T' | 't' => T,
                            'W' | 'w' => WIZ,
                            'P' | 'p' => P,
                            'B' | 'b' => B,
                            'D' | 'd' => D,
                            _ => {
                                eprintln!("bad freeze hero {}", c);
                                continue;
                            }
                        };
                        freeze |= 1u8 << i;
                    }
                } else if let Some(rest) = au.strip_prefix("goal=") {
                    goal = match rest {
                        "escape" => SeekGoal::Escape,
                        "crate19" => SeekGoal::Crate19,
                        "open19" => SeekGoal::Open19,
                        "win" => SeekGoal::Win,
                        _ => {
                            eprintln!("bad goal {}", rest);
                            goal
                        }
                    };
                } else if let Some(rest) = au.strip_prefix("width=") {
                    width = rest.parse().unwrap();
                } else {
                    extra = au.to_uppercase();
                    let (_a, _w, k) = apply_route(&mut s, &extra, g);
                    println!("applied extra {} ({} keys)", extra, k);
                }
            }
            let (wx, wy) = if s.heroes[WIZ] != GONE {
                xy(s.heroes[WIZ] as u32)
            } else {
                (-1, -1)
            };
            println!(
                "SEEK {} from cut={} extra={} W=({},{}) esc={} crate19={} open19={} maxd={} hog={} secs={} cap={} freeze={:06b} active={}",
                if cmd == "seek-beam" { "beam" } else { "bfs" },
                cut,
                extra,
                wx,
                wy,
                wiz_escaped(&s),
                crate_at_19(&s),
                wall19_open(&s),
                maxd,
                s.hog(g),
                secs,
                cap,
                freeze,
                s.active
            );
            let (path, exp, seen, st) = if cmd == "seek-beam" {
                seek_beam(s, maxd, width, secs, cap, g, freeze)
            } else {
                seek_wescape(s, maxd, secs, cap, g, freeze, goal)
            };
            println!(
                "result {} exp={} seen={} path={:?} len={:?}",
                st,
                exp,
                seen,
                path,
                path.as_ref().map(|p| p.len())
            );
            if let Some(p) = &path {
                let full = if extra.is_empty() {
                    format!("{}{}", &ROUTE316[..cut], p)
                } else {
                    format!("{}{}{}", &ROUTE316[..cut], extra, p)
                };
                println!("ESCAPE_PATH {}", p);
                println!("FULL_LEN {}", full.len());
                let mut s2 = St::start();
                let (a, w, k) = apply_route(&mut s2, &full, g);
                println!(
                    "verify alive={} win={} steps={} W_esc={} crate19={} board:\n{}",
                    a,
                    w,
                    k,
                    wiz_escaped(&s2),
                    crate_at_19(&s2),
                    s2.render()
                );
            }
        }
        "to-state" => {
            let a: usize = args[2].parse().unwrap();
            let b: usize = args[3].parse().unwrap();
            let secs: f64 = if args.len() > 4 { args[4].parse().unwrap() } else { 60.0 };
            let cap: usize = if args.len() > 5 { args[5].parse().unwrap() } else { 8_000_000 };
            let mut freeze: u8 = 0;
            for arg in args.iter().skip(6) {
                if let Some(rest) = arg.strip_prefix("freeze=") {
                    for c in rest.chars() {
                        let i = match c {
                            'F' | 'f' => F,
                            'T' | 't' => T,
                            'W' | 'w' => WIZ,
                            'P' | 'p' => P,
                            'B' | 'b' => B,
                            'D' | 'd' => D,
                            _ => continue,
                        };
                        freeze |= 1u8 << i;
                    }
                }
            }
            let start = apply_prefix(a);
            let target = apply_prefix(b);
            let official = &ROUTE316[a..b];
            let maxd = (b - a) as i32 - 1;
            println!(
                "TO-STATE {}->{} official_len={} maxd={} freeze={:06b} secs={} cap={} official={}",
                a, b, b - a, maxd, freeze, secs, cap, official
            );
            if start == target {
                println!("start already equals target");
            }
            let (path, exp, seen, st) = seek_state(start, target, maxd, secs, cap, g, freeze);
            println!(
                "result {} exp={} seen={} path={:?} len={:?} saved={:?}",
                st,
                exp,
                seen,
                path,
                path.as_ref().map(|p| p.len()),
                path.as_ref().map(|p| (b - a) as i32 - p.len() as i32)
            );
            if let Some(p) = &path {
                if (p.len() as usize) < b - a {
                    let full = format!("{}{}{}", &ROUTE316[..a], p, &ROUTE316[b..]);
                    println!("SHORTER {} {}", full.len(), p);
                    let mut s2 = St::start();
                    let (al, w, k) = apply_route(&mut s2, &full, g);
                    println!("verify alive={} win={} steps={}", al, w, k);
                }
            }
        }
        "shot" => shot_main(&args),
        _ => eprintln!("unknown {}", cmd),
    }
}
