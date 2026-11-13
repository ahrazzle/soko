// One-shot hierarchical planner for III-21. Included from iii21.rs.
// Command: ./iii21-seek shot [secs] [width] [cap] [only=name]

const HNAME: [&str; 6] = ["F", "T", "W", "P", "B", "D"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Job {
    GateHeld,
    Shaft(i32),
    WFree,
    Open(i32, i32),
    MidGobsClear,
    RightGobsClear,
    Deliver,
    Win,
}

struct Plan {
    name: &'static str,
    prefix: usize,
    assign: [(i32, i32); 6],
    jobs: Vec<Job>,
}

fn official_assign() -> [(i32, i32); 6] {
    let mut a = [(0i32, 0i32); 6];
    a[P] = (10, 1);
    a[B] = (12, 1);
    a[D] = (10, 6);
    a[T] = (12, 6);
    a[WIZ] = (10, 11);
    a[F] = (12, 11);
    a
}

fn swap_goals(mut a: [(i32, i32); 6], h1: usize, h2: usize) -> [(i32, i32); 6] {
    let t = a[h1];
    a[h1] = a[h2];
    a[h2] = t;
    a
}

fn atax(active: usize, target: usize) -> i32 {
    ((target + HN - active) % HN) as i32
}

fn in_aura(s: &St, h: usize) -> bool {
    if s.heroes[B] == GONE || s.heroes[h] == GONE {
        return false;
    }
    let (bx, by) = xy(s.heroes[B] as u32);
    let (hx, hy) = xy(s.heroes[h] as u32);
    (bx - hx).abs().max((by - hy).abs()) <= 2
}

fn left_gobs(s: &St) -> i32 {
    goblins_in(s, 4, 6, 4, 8)
}

fn east_of_gate(s: &St, h: usize) -> bool {
    if s.heroes[h] == GONE {
        return false;
    }
    let (x, _) = xy(s.heroes[h] as u32);
    x >= 5
}

/// Keys to get Druid west of the leftover goblins at (5,5) and (5,7).
fn est_pass_gate(s: &St) -> i32 {
    if !east_of_gate(s, D) || left_gobs(s) == 0 {
        return 0;
    }
    if gate_held(s) && in_aura(s, D) == false {
        // Priest already on the walkway; Druid still has to walk to it.
        return hmanh(s, D, 4, 6) + atax(s.active as usize, D);
    }
    if s.active as usize == B && in_aura(s, D) && in_aura(s, P) {
        // Bard charms both through (5,6): remaining left-walk of Druid past the gate.
        let (dx, _) = xy(s.heroes[D] as u32);
        return (dx - 3).max(0);
    }
    // Get Priest onto the walkway, then pass. If Bard is cheap, prefer a charm escort.
    let pwalk = if s.active as usize == B && in_aura(s, P) {
        hmanh(s, P, 2, 6)
    } else {
        atax(s.active as usize, P) + hmanh(s, P, 2, 6)
    };
    pwalk + 3
}

fn hmanh(s: &St, h: usize, tx: i32, ty: i32) -> i32 {
    if s.heroes[h] == GONE {
        return 10_000;
    }
    let (x, y) = xy(s.heroes[h] as u32);
    (x - tx).abs() + (y - ty).abs()
}

fn shaft_open(s: &St, x: i32) -> bool {
    inb(x, 8) && inb(x, 9) && !s.walls.get(idx(x, 8)) && !s.walls.get(idx(x, 9))
}

fn gate_held(s: &St) -> bool {
    if s.heroes[P] == GONE {
        return false;
    }
    let (x, y) = xy(s.heroes[P] as u32);
    // Priest on the left walkway, row 6, so a passer at (5,6) can be shielded.
    y == 6 && x <= 6
}

fn goblins_in(s: &St, x0: i32, x1: i32, y0: i32, y1: i32) -> i32 {
    let mut n = 0i32;
    for i in s.gobs.iter() {
        let (x, y) = xy(i);
        if x >= x0 && x <= x1 && y >= y0 && y <= y1 {
            n += 1;
        }
    }
    n
}

fn mid_gobs(s: &St) -> i32 {
    goblins_in(s, 8, 16, 3, 9)
}

fn right_gobs(s: &St) -> i32 {
    goblins_in(s, 16, 22, 3, 11)
}

fn wall_open(s: &St, x: i32, y: i32) -> bool {
    !s.walls.get(idx(x, y))
}

fn needs_convert(s: &St, plan: &Plan, gx: i32, gy: i32, wx: i32, wy: i32) -> bool {
    if wall_open(s, wx, wy) {
        return false;
    }
    for h in 0..HN {
        if plan.assign[h] == (gx, gy) && hmanh(s, h, gx, gy) > 0 {
            return true;
        }
    }
    false
}

fn job_cost(s: &St, job: Job, plan: &Plan, gmask: Bits) -> i32 {
    match job {
        Job::Win => {
            // Deliver is already its own job. Win is only a 0/1 flag so it
            // is not counted twice in the guide.
            if s.win(gmask) { 0 } else { 1 }
        }
        Job::GateHeld => {
            if gate_held(s) && !east_of_gate(s, D) {
                0
            } else if gate_held(s) {
                // Priest is in place; remaining cost is only Druid passing.
                est_pass_gate(s)
            } else if s.active as usize == B && in_aura(s, P) {
                hmanh(s, P, 2, 6)
            } else {
                atax(s.active as usize, P) + hmanh(s, P, 2, 6)
            }
        }
        Job::Shaft(x) => {
            if shaft_open(s, x) {
                return 0;
            }
            let mut walls = 0i32;
            if s.walls.get(idx(x, 8)) {
                walls += 1;
            }
            if s.walls.get(idx(x, 9)) {
                walls += 1;
            }
            // If Bard is already walking Druid left, don't add a switch tax.
            let walk = if s.active as usize == B && in_aura(s, D) {
                hmanh(s, D, x, 7)
            } else {
                atax(s.active as usize, D) + hmanh(s, D, x, 7)
            };
            let mut c = walk + walls + 2 + est_pass_gate(s);
            if s.heroes[D] != GONE {
                let (dx, _) = xy(s.heroes[D] as u32);
                if mid_gobs(s) > 0 && dx >= 8 {
                    c += mid_gobs(s) * 6;
                }
                if right_gobs(s) > 0 && dx >= 16 {
                    c += right_gobs(s) * 6;
                }
            }
            c
        }
        Job::WFree => {
            if wiz_escaped(s) {
                return 0;
            }
            // Cheapest unopened shaft, then A-tax to Wizard and a short swap.
            let sh = [1, 2, 3]
                .iter()
                .map(|&x| job_cost(s, Job::Shaft(x), plan, gmask))
                .min()
                .unwrap_or(8);
            sh + atax(s.active as usize, WIZ) + 2
        }
        Job::Open(x, y) => {
            if wall_open(s, x, y) {
                0
            } else {
                atax(s.active as usize, D) + hmanh(s, D, x, y - 1) + 1
            }
        }
        Job::MidGobsClear => {
            let n = mid_gobs(s);
            if n == 0 {
                0
            } else {
                atax(s.active as usize, F) + n * 12
            }
        }
        Job::RightGobsClear => {
            let n = right_gobs(s);
            if n == 0 {
                0
            } else {
                atax(s.active as usize, F) + n * 10
            }
        }
        Job::Deliver => {
            let mut walk = 0i32;
            let mut unplaced = 0i32;
            let mut first = None;
            for h in 0..HN {
                let (tx, ty) = plan.assign[h];
                let d = hmanh(s, h, tx, ty);
                if d > 0 {
                    unplaced += 1;
                    walk += d;
                    if first.is_none() {
                        first = Some(h);
                    }
                }
            }
            if unplaced == 0 {
                return 0;
            }
            let sw = first.map(|h| atax(s.active as usize, h)).unwrap_or(0);
            let mut conv = 0i32;
            if needs_convert(s, plan, 10, 11, 10, 10) {
                conv += atax(s.active as usize, D) + hmanh(s, D, 10, 9) + 1;
            }
            if needs_convert(s, plan, 12, 11, 12, 10) {
                conv += 1 + hmanh(s, D, 12, 9).min(8);
            }
            // Bard-ride discount: unplaced heroes on one row, Bard nearby.
            let mut discount = 0i32;
            if s.heroes[B] != GONE {
                let (bx, by) = xy(s.heroes[B] as u32);
                let mut row_mates = 0i32;
                for h in 0..HN {
                    if h == B || s.heroes[h] == GONE {
                        continue;
                    }
                    let (hx, hy) = xy(s.heroes[h] as u32);
                    let (tx, ty) = plan.assign[h];
                    if hy == by && (hx - bx).abs() <= 8 && (tx - hx).abs() + (ty - hy).abs() > 0 {
                        row_mates += 1;
                    }
                }
                if row_mates >= 2 {
                    discount = row_mates * 4;
                }
            }
            sw + walk + conv - discount
        }
    }
}

fn job_holds(s: &St, job: Job, plan: &Plan, gmask: Bits) -> bool {
    job_cost(s, job, plan, gmask) == 0 && matches!(job, Job::Win) == s.win(gmask)
}

fn jobs_done(s: &St, plan: &Plan, gmask: Bits) -> u8 {
    plan.jobs
        .iter()
        .filter(|j| job_cost(s, **j, plan, gmask) == 0)
        .count() as u8
}


fn job_done(s: &St, job: Job, _plan: &Plan, gmask: Bits) -> bool {
    match job {
        // Sticky: after Druid has passed, or Wizard is already free, the
        // gate is no longer required even if Priest later leaves the walkway.
        Job::GateHeld => {
            // Priest standing on the walkway is only partial. The job is
            // done once Druid is west of the goblins (or they are gone, or
            // Wizard is already free).
            wiz_escaped(s) || !east_of_gate(s, D) || left_gobs(s) == 0
        }
        Job::Shaft(x) => shaft_open(s, x),
        Job::WFree => wiz_escaped(s),
        Job::Open(x, y) => wall_open(s, x, y),
        Job::MidGobsClear => mid_gobs(s) == 0,
        Job::RightGobsClear => right_gobs(s) == 0,
        Job::Deliver => (0..HN).all(|h| {
            let (tx, ty) = _plan.assign[h];
            hmanh(s, h, tx, ty) == 0
        }),
        Job::Win => s.win(gmask),
    }
}

/// Staged progress: later jobs do not count until earlier ones in the plan
/// are done. Otherwise five heroes sitting on goals, with Wizard still
/// trapped, outrank a shaft that is halfway open, and the official finish
/// falls off the beam.
fn progress(s: &St, plan: &Plan, gmask: Bits) -> i32 {
    let mut p = 0i32;
    for job in &plan.jobs {
        let (complete, partial) = job_progress(s, *job, plan, gmask);
        p += partial;
        if !complete {
            break;
        }
        p += 1000;
    }
    p
}

fn job_progress(s: &St, job: Job, plan: &Plan, gmask: Bits) -> (bool, i32) {
    match job {
        Job::GateHeld => {
            let c = job_done(s, Job::GateHeld, plan, gmask);
            let part = if c {
                20
            } else if gate_held(s) {
                12
            } else {
                (10 - hmanh(s, P, 2, 6).min(10)).max(0)
            };
            (c, part)
        }
        Job::Shaft(x) => {
            let c = shaft_open(s, x);
            let mut u = 0i32;
            if !s.walls.get(idx(x, 8)) {
                u += 12;
            }
            if !s.walls.get(idx(x, 9)) {
                u += 12;
            }
            if c {
                u += 8;
            }
            (c, u)
        }
        Job::WFree => {
            let c = wiz_escaped(s);
            (c, if c { 24 } else { 0 })
        }
        Job::Open(x, y) => {
            let c = wall_open(s, x, y);
            let part = if c {
                24
            } else if s.heroes[D] != GONE {
                (16 - hmanh(s, D, x, y - 1).min(16)).max(0)
            } else {
                0
            };
            (c, part)
        }
        Job::MidGobsClear => {
            let n = mid_gobs(s);
            (n == 0, (4 - n.min(4)) * 6)
        }
        Job::RightGobsClear => {
            let n = right_gobs(s);
            (n == 0, (4 - n.min(4)) * 6)
        }
        Job::Deliver => {
            let mut u = s.hog(gmask) as i32 * 8;
            let mut all = true;
            for h in 0..HN {
                let (tx, ty) = plan.assign[h];
                if hmanh(s, h, tx, ty) == 0 {
                    u += 6;
                } else {
                    all = false;
                }
            }
            (all, u)
        }
        Job::Win => {
            let c = s.win(gmask);
            (c, if c { 100 } else { 0 })
        }
    }
}


fn guide(s: &St, plan: &Plan, gmask: Bits) -> i32 {
    if s.win(gmask) {
        return 0;
    }
    // Sum of remaining job estimates only. Never multiply the current job:
    // a *3 focus weight made h jump when a job was finished, and the beam
    // dropped the official path at the moment it opened the shaft.
    let mut total = 0i32;
    for job in &plan.jobs {
        total += job_cost(s, *job, plan, gmask);
    }
    total -= s.hog(gmask) as i32;
    if total < 0 {
        0
    } else {
        total
    }
}

fn feat(s: &St, gmask: Bits) -> String {
    format!(
        "sh1={}{} sh2={}{} Wfree={} mid={} right={} w1010={} w1210={} gate={} hog={} act={}",
        if s.walls.get(idx(1, 8)) { '#' } else if s.crates.get(idx(1, 8)) { '*' } else { '.' },
        if s.walls.get(idx(1, 9)) { '#' } else if s.crates.get(idx(1, 9)) { '*' } else { '.' },
        if s.walls.get(idx(2, 8)) { '#' } else if s.crates.get(idx(2, 8)) { '*' } else { '.' },
        if s.walls.get(idx(2, 9)) { '#' } else if s.crates.get(idx(2, 9)) { '*' } else { '.' },
        wiz_escaped(s),
        mid_gobs(s),
        right_gobs(s),
        wall_open(s, 10, 10),
        wall_open(s, 12, 10),
        gate_held(s),
        s.hog(gmask),
        HNAME[s.active as usize]
    )
}

fn assign_str(a: &[(i32, i32); 6]) -> String {
    (0..HN)
        .map(|h| format!("{}({},{})", HNAME[h], a[h].0, a[h].1))
        .collect::<Vec<_>>()
        .join(" ")
}

fn jobs_str(jobs: &[Job]) -> String {
    jobs.iter()
        .map(|j| match j {
            Job::GateHeld => "GateHeld".to_string(),
            Job::Shaft(x) => format!("Shaft({})", x),
            Job::WFree => "WFree".to_string(),
            Job::Open(x, y) => format!("Open({},{})", x, y),
            Job::MidGobsClear => "MidGobs".to_string(),
            Job::RightGobsClear => "RightGobs".to_string(),
            Job::Deliver => "Deliver".to_string(),
            Job::Win => "Win".to_string(),
        })
        .collect::<Vec<_>>()
        .join(" > ")
}

fn plan_book() -> Vec<Plan> {
    let off = official_assign();
    let a_wd = swap_goals(off, WIZ, D); // W(10,6) D(10,11)
    let a_wt = swap_goals(off, WIZ, T); // W(12,6) T(10,11) wait T is (12,6), W(12,6) T(10,11)? 
    // official T(12,6) W(10,11) — swap gives W(12,6) T(10,11)
    let a_wf = swap_goals(off, WIZ, F); // W(12,11) F(10,11)
    let a_wp = swap_goals(off, WIZ, P); // W(10,1) P(10,11)
    let finish = vec![Job::GateHeld, Job::Shaft(1), Job::WFree, Job::Open(10, 10), Job::Deliver, Job::Win];
    let early = vec![
        Job::Shaft(1),
        Job::WFree,
        Job::MidGobsClear,
        Job::RightGobsClear,
        Job::Open(12, 10),
        Job::Open(10, 10),
        Job::Deliver,
        Job::Win,
    ];
    let early2 = vec![
        Job::Shaft(2),
        Job::WFree,
        Job::MidGobsClear,
        Job::RightGobsClear,
        Job::Open(12, 10),
        Job::Open(10, 10),
        Job::Deliver,
        Job::Win,
    ];
    let early3 = vec![
        Job::Shaft(3),
        Job::WFree,
        Job::MidGobsClear,
        Job::RightGobsClear,
        Job::Open(12, 10),
        Job::Open(10, 10),
        Job::Deliver,
        Job::Win,
    ];
    let official_rest = vec![
        Job::MidGobsClear,
        Job::RightGobsClear,
        Job::Shaft(1),
        Job::WFree,
        Job::Open(10, 10),
        Job::Deliver,
        Job::Win,
    ];
    let early_bard = vec![
        Job::GateHeld,
        Job::Shaft(1),
        Job::WFree,
        Job::MidGobsClear,
        Job::Open(12, 10),
        Job::Open(10, 10),
        Job::Deliver,
        Job::Win,
    ];
    let from0 = vec![
        Job::GateHeld,
        Job::Shaft(1),
        Job::WFree,
        Job::MidGobsClear,
        Job::RightGobsClear,
        Job::Open(12, 10),
        Job::Open(10, 10),
        Job::Deliver,
        Job::Win,
    ];
    vec![
        Plan { name: "cal_246_official", prefix: 246, assign: off, jobs: finish.clone() },
        Plan { name: "cal_246_A_WD", prefix: 246, assign: a_wd, jobs: finish.clone() },
        Plan { name: "cal_232_official", prefix: 232, assign: off, jobs: finish.clone() },
        Plan { name: "early_esc_85", prefix: 85, assign: off, jobs: early.clone() },
        Plan { name: "early_esc_85_shaft2", prefix: 85, assign: off, jobs: early2 },
        Plan { name: "early_esc_85_shaft3", prefix: 85, assign: off, jobs: early3 },
        Plan { name: "early_esc_85_A_WD", prefix: 85, assign: a_wd, jobs: early.clone() },
        Plan { name: "early_esc_85_A_WT", prefix: 85, assign: a_wt, jobs: early.clone() },
        Plan { name: "early_esc_85_A_WF", prefix: 85, assign: a_wf, jobs: early.clone() },
        Plan { name: "early_esc_85_A_WP", prefix: 85, assign: a_wp, jobs: early.clone() },
        Plan { name: "official_rest_85", prefix: 85, assign: off, jobs: official_rest },
        Plan { name: "early_bard_85", prefix: 85, assign: off, jobs: early_bard },
        Plan { name: "overlap_D_185", prefix: 185, assign: off, jobs: early.clone() },
        Plan { name: "overlap_D_185_A_WD", prefix: 185, assign: a_wd, jobs: early.clone() },
        Plan { name: "early_esc_0", prefix: 0, assign: off, jobs: from0 },
    ]
}

struct GuidedHit {
    path: String,
    won: bool,
    status: &'static str,
    exp: u64,
    seen: usize,
}

fn guided_beam(
    start: St,
    plan: &Plan,
    max_d: i32,
    width: usize,
    secs: f64,
    cap: usize,
    gmask: Bits,
) -> GuidedHit {
    #[derive(Clone)]
    struct Node {
        s: St,
        path: String,
    }
    let t0 = Instant::now();
    if start.win(gmask) {
        return GuidedHit { path: String::new(), won: true, status: "already-win", exp: 0, seen: 1 };
    }
    let mut layer: Vec<Node> = vec![Node { s: start, path: String::new() }];
    let mut seen: HashSet<St> = HashSet::with_capacity(cap.min(2_000_000));
    seen.insert(start);
    let mut exp: u64 = 0;
    let mut best_progress: i32 = i32::MAX;
    println!(
        "  start {} done={} prog={} guide={} {}",
        feat(&start, gmask),
        jobs_done(&start, plan, gmask),
        progress(&start, plan, gmask),
        guide(&start, plan, gmask),
        jobs_str(&plan.jobs)
    );
    let official_rest = if plan.prefix < ROUTE316.len() {
        &ROUTE316[plan.prefix..]
    } else {
        ""
    };
    let mut official_s = start;
    let mut official_alive = true;
    let mut official_dropped_at: Option<i32> = None;
    for d in 0..max_d {
        if t0.elapsed().as_secs_f64() > secs {
            return GuidedHit {
                path: String::new(),
                won: false,
                status: "timeout",
                exp,
                seen: seen.len(),
            };
        }
        let mut nxt: Vec<(i32, i32, u8, Node)> = Vec::with_capacity(layer.len() * 4);
        for node in &layer {
            exp += 1;
            for &k in &KEYS {
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
                    return GuidedHit {
                        path: String::new(),
                        won: false,
                        status: "cap",
                        exp,
                        seen: seen.len(),
                    };
                }
                let mut path = String::with_capacity(node.path.len() + 1);
                path.push_str(&node.path);
                path.push(k);
                if won {
                    println!(
                        "  WIN at d={} {} path_len={}",
                        d + 1,
                        feat(&ns, gmask),
                        path.len()
                    );
                    return GuidedHit {
                        path,
                        won: true,
                        status: "win",
                        exp,
                        seen: seen.len(),
                    };
                }
                let h = guide(&ns, plan, gmask);
                let prog = progress(&ns, plan, gmask);
                nxt.push((prog, h, ns.hog(gmask), Node { s: ns, path }));
            }
        }
        if nxt.is_empty() {
            return GuidedHit {
                path: String::new(),
                won: false,
                status: "exhausted",
                exp,
                seen: seen.len(),
            };
        }
        nxt.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)).then(b.2.cmp(&a.2)));
        if nxt.len() > width {
            nxt.truncate(width);
        }
        let bdone = nxt[0].0;
        let bh = nxt[0].1;
        let mut any_shaft = false;
        let mut any_wfree = false;
        let mut min_dx = 99i32;
        for (_, _, _, n) in &nxt {
            if shaft_open(&n.s, 1) || shaft_open(&n.s, 2) || shaft_open(&n.s, 3) {
                any_shaft = true;
            }
            if wiz_escaped(&n.s) {
                any_wfree = true;
            }
            if n.s.heroes[D] != GONE {
                let (dx, _) = xy(n.s.heroes[D] as u32);
                if dx < min_dx {
                    min_dx = dx;
                }
            }
        }
        // Track whether the official suffix is still on the beam.
        let mut off_note = String::new();
        if official_alive && (d as usize) < official_rest.len() {
            let k = official_rest.as_bytes()[d as usize] as char;
            let (al, won, _ch) = step(&mut official_s, k, gmask);
            if !al || official_s.nheroes() < 6 {
                official_alive = false;
                off_note = format!(" OFFICIAL-DIED at {}", k);
            } else {
                let oh = guide(&official_s, plan, gmask);
                let rank = nxt.iter().position(|(_, _, _, n)| n.s == official_s);
                if rank.is_none() && official_dropped_at.is_none() {
                    official_dropped_at = Some(d + 1);
                }
                let op = progress(&official_s, plan, gmask);
                off_note = format!(
                    " official_h={} official_p={} {} rank={:?}{}",
                    oh,
                    op,
                    feat(&official_s, gmask),
                    rank,
                    if won { " OFFICIAL-WIN" } else { "" }
                );
            }
        }
        if bh < best_progress || d % 5 == 4 || d < 3 || any_shaft || any_wfree || official_dropped_at == Some(d + 1) {
            best_progress = best_progress.min(bh);
            println!(
                "  d={} kept={} prog={} best_h={} {} seen={} t={:.1}s shaft={} wfree={} minDx={}{}",
                d + 1,
                nxt.len(),
                bdone,
                bh,
                feat(&nxt[0].3.s, gmask),
                seen.len(),
                t0.elapsed().as_secs_f64(),
                any_shaft,
                any_wfree,
                min_dx,
                off_note
            );
        }
        layer = nxt.into_iter().map(|(_, _, _, n)| n).collect();
    }
    GuidedHit {
        path: String::new(),
        won: false,
        status: "maxd",
        exp,
        seen: seen.len(),
    }
}


#[derive(Clone)]
struct Realized {
    s: St,
    path: String,
}

fn pose_sig(s: &St) -> u64 {
    let mut h = 0xcbf29ce484222325u64;
    for i in 0..HN {
        h ^= s.heroes[i] as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h ^= s.active as u64;
    h = h.wrapping_mul(0x100000001b3);
    h ^= s.walls.a as u64;
    h = h.wrapping_mul(0x100000001b3);
    h ^= s.walls.b as u64;
    h = h.wrapping_mul(0x100000001b3);
    h ^= s.crates.a as u64;
    h = h.wrapping_mul(0x100000001b3);
    h ^= s.gobs.a as u64;
    h
}

fn rebuild_path(
    prevs: &[(u32, u8)],
    roots: &[u16],
    mut i: u32,
    starts: &[Realized],
) -> String {
    let mut chars: Vec<char> = Vec::new();
    loop {
        let (p, ch) = prevs[i as usize];
        if p == u32::MAX {
            let root = roots[i as usize] as usize;
            chars.reverse();
            let suf: String = chars.into_iter().collect();
            return format!("{}{}", starts[root].path, suf);
        }
        chars.push(ch as char);
        i = p;
    }
}

/// Exact packed BFS from several starts to a job predicate. Collects up to
/// `out_k` diverse hits at the first hitting depth, then `extra` more depths.
fn realize_bfs(
    starts: &[Realized],
    pred: impl Fn(&St) -> bool,
    max_d: i32,
    secs: f64,
    cap: usize,
    out_k: usize,
    extra: i32,
    gmask: Bits,
    freeze: u8,
    tag: &str,
) -> (Vec<Realized>, u64, usize, &'static str) {
    let t0 = Instant::now();
    let mut out: Vec<Realized> = Vec::new();
    let mut out_sigs: HashSet<u64> = HashSet::new();
    for r in starts {
        if pred(&r.s) {
            let sig = pose_sig(&r.s);
            if out_sigs.insert(sig) {
                out.push(r.clone());
                if out.len() >= out_k {
                    println!("    bfs {} already {} hits", tag, out.len());
                    return (out, 0, starts.len(), "already");
                }
            }
        }
    }
    if !out.is_empty() && starts.iter().all(|r| pred(&r.s)) {
        println!("    bfs {} already on all starts", tag);
        return (out, 0, starts.len(), "already");
    }

    let mut nodes: Vec<St> = Vec::new();
    let mut prevs: Vec<(u32, u8)> = Vec::new();
    let mut gs: Vec<u16> = Vec::new();
    let mut roots: Vec<u16> = Vec::new();
    let mut seen: HashSet<St> = HashSet::with_capacity(cap.min(2_000_000));
    for (i, r) in starts.iter().enumerate() {
        if pred(&r.s) {
            continue;
        }
        if seen.insert(r.s) {
            nodes.push(r.s);
            prevs.push((u32::MAX, b'?'));
            gs.push(0);
            roots.push(i as u16);
        }
    }
    if nodes.is_empty() {
        let why = if out.is_empty() { "empty" } else { "already" };
        return (out, 0, seen.len(), why);
    }

    let mut qh: usize = 0;
    let mut exp: u64 = 0;
    let mut cur_d = 0u16;
    // d0 tracks the first NEW hit only. Already-complete starts sit in `out`
    // but must not freeze the depth cutoff at 0.
    let mut d0: Option<u16> = None;
    let mut status: &'static str = "exhausted";

    while qh < nodes.len() {
        if t0.elapsed().as_secs_f64() > secs {
            status = "timeout";
            println!(
                "    bfs {} timeout at g={} seen={} exp={} hits={}",
                tag,
                gs.get(qh).copied().unwrap_or(cur_d),
                seen.len(),
                exp,
                out.len()
            );
            break;
        }
        if seen.len() >= cap {
            status = "cap";
            println!(
                "    bfs {} cap at g={} seen={} exp={} hits={}",
                tag,
                gs.get(qh).copied().unwrap_or(cur_d),
                seen.len(),
                exp,
                out.len()
            );
            break;
        }
        let s = nodes[qh];
        let g = gs[qh];
        let idx0 = qh as u32;
        qh += 1;
        if g != cur_d {
            println!(
                "    bfs {} depth {} seen={} exp={} hits={} t={:.1}s",
                tag,
                cur_d,
                seen.len(),
                exp,
                out.len(),
                t0.elapsed().as_secs_f64()
            );
            cur_d = g;
            if let Some(d) = d0 {
                if (g as i32) > (d as i32) + extra {
                    status = "collected";
                    break;
                }
            }
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
            if pred(&ns) {
                if d0.is_none() {
                    d0 = Some(g + 1);
                    println!(
                        "    bfs {} FIRST at g={} {} seen={} t={:.1}s",
                        tag,
                        g + 1,
                        feat(&ns, gmask),
                        seen.len(),
                        t0.elapsed().as_secs_f64()
                    );
                }
                let sig = pose_sig(&ns);
                if out_sigs.insert(sig) && out.len() < out_k {
                    let path = rebuild_path(&prevs, &roots, (nodes.len() - 1) as u32, starts);
                    out.push(Realized { s: ns, path });
                }
            }
        }
    }
    if d0.is_some() && !out.is_empty() && status == "exhausted" {
        status = "collected";
    }
    println!(
        "    bfs {} {} hits={} best_len={} exp={} seen={} t={:.1}s",
        tag,
        status,
        out.len(),
        out.iter().map(|r| r.path.len()).min().unwrap_or(0),
        exp,
        seen.len(),
        t0.elapsed().as_secs_f64()
    );
    (out, exp, seen.len(), status)
}

/// Guided beam that stops when `until` holds (or on a win if `until` is Win).
fn guided_until(
    start: St,
    start_path: &str,
    plan: &Plan,
    until: Job,
    max_d: i32,
    width: usize,
    secs: f64,
    cap: usize,
    gmask: Bits,
    out_k: usize,
) -> (Vec<Realized>, &'static str, u64, usize) {
    #[derive(Clone)]
    struct Node {
        s: St,
        path: String,
    }
    let t0 = Instant::now();
    if job_done(&start, until, plan, gmask) {
        return (
            vec![Realized {
                s: start,
                path: start_path.to_string(),
            }],
            "already",
            0,
            1,
        );
    }
    let mut layer: Vec<Node> = vec![Node {
        s: start,
        path: String::new(),
    }];
    let mut seen: HashSet<St> = HashSet::with_capacity(cap.min(2_000_000));
    seen.insert(start);
    let mut exp: u64 = 0;
    let mut hits: Vec<Realized> = Vec::new();
    let mut hit_sigs: HashSet<u64> = HashSet::new();
    for d in 0..max_d {
        if t0.elapsed().as_secs_f64() > secs {
            return (hits, "timeout", exp, seen.len());
        }
        let mut nxt: Vec<(i32, i32, u8, Node)> = Vec::with_capacity(layer.len() * 4);
        let mut layer_hits: Vec<Realized> = Vec::new();
        for node in &layer {
            exp += 1;
            for &k in &KEYS {
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
                    return (hits, "cap", exp, seen.len());
                }
                let mut path = String::with_capacity(node.path.len() + 1);
                path.push_str(&node.path);
                path.push(k);
                if job_done(&ns, until, plan, gmask) || won {
                    let sig = pose_sig(&ns);
                    if hit_sigs.insert(sig) {
                        layer_hits.push(Realized {
                            s: ns,
                            path: format!("{}{}", start_path, path),
                        });
                    }
                    // Still rank it so siblings can also hit; don't expand past.
                    continue;
                }
                let h = guide(&ns, plan, gmask);
                let prog = progress(&ns, plan, gmask);
                nxt.push((prog, h, ns.hog(gmask), Node { s: ns, path }));
            }
        }
        if !layer_hits.is_empty() {
            println!(
                "    guided {} HIT at d={} n={} {} t={:.1}s",
                format!("{:?}", until),
                d + 1,
                layer_hits.len(),
                feat(&layer_hits[0].s, gmask),
                t0.elapsed().as_secs_f64()
            );
            hits.extend(layer_hits);
            hits.truncate(out_k);
            return (hits, "hit", exp, seen.len());
        }
        if nxt.is_empty() {
            return (hits, "exhausted", exp, seen.len());
        }
        nxt.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)).then(b.2.cmp(&a.2)));
        if nxt.len() > width {
            nxt.truncate(width);
        }
        if d < 3 || d % 5 == 4 {
            println!(
                "    guided {:?} d={} kept={} prog={} h={} {} seen={} t={:.1}s",
                until,
                d + 1,
                nxt.len(),
                nxt[0].0,
                nxt[0].1,
                feat(&nxt[0].3.s, gmask),
                seen.len(),
                t0.elapsed().as_secs_f64()
            );
        }
        layer = nxt.into_iter().map(|(_, _, _, n)| n).collect();
    }
    (hits, "maxd", exp, seen.len())
}


fn official_rest(prefix: usize) -> &'static str {
    if prefix < ROUTE316.len() {
        &ROUTE316[prefix..]
    } else {
        ""
    }
}

fn total_est(r: &Realized, plan: &Plan, gmask: Bits) -> i32 {
    r.path.len() as i32
        + plan
            .jobs
            .iter()
            .map(|&j| job_cost(&r.s, j, plan, gmask))
            .sum::<i32>()
}

fn seed_official(plan: &Plan, job: Job, gmask: Bits) -> Option<Realized> {
    let rest = official_rest(plan.prefix);
    let mut os = apply_prefix(plan.prefix);
    if job_done(&os, job, plan, gmask) {
        return Some(Realized {
            s: os,
            path: String::new(),
        });
    }
    let mut op = String::new();
    for k in rest.chars() {
        let (al, _w, _c) = step(&mut os, k, gmask);
        if !al || os.nheroes() < 6 {
            return None;
        }
        op.push(k);
        if job_done(&os, job, plan, gmask) {
            return Some(Realized { s: os, path: op });
        }
    }
    None
}

fn official_finish(r: &Realized, plan: &Plan, gmask: Bits) -> Option<Realized> {
    let rest = official_rest(plan.prefix);
    if !rest.starts_with(&r.path) {
        return None;
    }
    let remaining = &rest[r.path.len()..];
    let mut s = r.s;
    let mut path = r.path.clone();
    for k in remaining.chars() {
        let (al, won, _c) = step(&mut s, k, gmask);
        if !al || s.nheroes() < 6 {
            return None;
        }
        path.push(k);
        if won {
            return Some(Realized { s, path });
        }
    }
    None
}

fn union_official(next: &mut Vec<Realized>, plan: &Plan, job: Job, gmask: Bits) {
    if !plan.name.starts_with("cal_") {
        return;
    }
    if let Some(off) = seed_official(plan, job, gmask) {
        if !next.iter().any(|r| r.path == off.path) {
            println!(
                "    seed official {:?} at {} {}",
                job,
                off.path.len(),
                feat(&off.s, gmask)
            );
            next.push(off);
        }
    }
}

fn rank_by_total(beam: &mut Vec<Realized>, plan: &Plan, gmask: Bits, keep: usize) {
    beam.sort_by_key(|r| total_est(r, plan, gmask));
    if beam.len() > keep {
        beam.truncate(keep);
    }
    if !beam.is_empty() {
        println!(
            "    selected n={} best_total_est={} {} path_len={}",
            beam.len(),
            total_est(&beam[0], plan, gmask),
            feat(&beam[0].s, gmask),
            beam[0].path.len()
        );
    }
}

fn run_plan(
    plan: &Plan,
    secs: f64,
    width: usize,
    cap: usize,
    gmask: Bits,
) -> Option<Realized> {
    let start = apply_prefix(plan.prefix);
    let budget = (316 - plan.prefix).max(1);
    let mut beam: Vec<Realized> = vec![Realized {
        s: start,
        path: String::new(),
    }];
    println!(
        "  start {} done={} prog={} guide={} {}",
        feat(&start, gmask),
        jobs_done(&start, plan, gmask),
        progress(&start, plan, gmask),
        guide(&start, plan, gmask),
        jobs_str(&plan.jobs)
    );
    let mut i = 0usize;
    while i < plan.jobs.len() {
        let job = plan.jobs[i];
        if beam.is_empty() {
            println!("  FAIL empty beam before {:?}", job);
            return None;
        }
        let used = beam.iter().map(|r| r.path.len()).min().unwrap_or(0);
        let left = (budget as i32 - used as i32).max(0);
        let n_done = beam.iter().filter(|r| job_done(&r.s, job, plan, gmask)).count();
        println!(
            "  -- {:?} states={} already={} path={} left={}",
            job,
            beam.len(),
            n_done,
            used,
            left
        );
        if left == 0 && n_done == 0 {
            println!("  FAIL no budget for {:?}", job);
            return None;
        }
        // Deliver and Win are one finishing beam to a full win.
        if matches!(job, Job::Deliver | Job::Win) {
            let mut found: Option<Realized> = None;
            // Calibration control: keep the official Open pose and play its
            // known remaining suffix. A 70-key recovery is CALIBRATION OK;
            // the beam below still looks for a shorter finish.
            if plan.name.starts_with("cal_") {
                if let Some(off) = seed_official(plan, Job::Open(10, 10), gmask) {
                    if !beam.iter().any(|r| r.path == off.path) {
                        println!(
                            "    seed official Open for finish at {} {}",
                            off.path.len(),
                            feat(&off.s, gmask)
                        );
                        beam.push(off);
                    }
                }
                for r in beam.iter() {
                    if let Some(win) = official_finish(r, plan, gmask) {
                        println!(
                            "    official suffix WIN at {} {}",
                            win.path.len(),
                            feat(&win.s, gmask)
                        );
                        found = Some(win);
                        break;
                    }
                }
            }
            let official_win = found.take();
            rank_by_total(&mut beam, plan, gmask, 8);
            for (j, r) in beam.iter().take(8).enumerate() {
                let md = (budget as i32 - r.path.len() as i32).max(1);
                println!(
                    "    finish beam {} path={} maxd={} {}",
                    j,
                    r.path.len(),
                    md,
                    feat(&r.s, gmask)
                );
                let hit = guided_beam(r.s, plan, md, width, secs, cap, gmask);
                println!(
                    "    finish {} exp={} seen={} path_len={}",
                    hit.status,
                    hit.exp,
                    hit.seen,
                    hit.path.len()
                );
                if hit.won {
                    let path = format!("{}{}", r.path, hit.path);
                    println!("    finish WIN at {}", path.len());
                    let better = official_win
                        .as_ref()
                        .map(|o| path.len() < o.path.len())
                        .unwrap_or(true);
                    if better {
                        found = Some(Realized { s: r.s, path });
                        break;
                    }
                }
            }
            if found.is_none() {
                found = official_win;
            }
            return found;
        }
        if n_done == beam.len() {
            println!("    already done");
            i += 1;
            continue;
        }
        let est = beam
            .iter()
            .map(|r| job_cost(&r.s, job, plan, gmask))
            .min()
            .unwrap_or(20);
        // Exact BFS for short jobs. Shaft is two phases (first wall, then
        // both), with Wizard and Priest frozen: Wizard cannot leave the
        // alcove, and Priest has already done the escort.
        let use_exact = est <= 36
            && matches!(job, Job::GateHeld | Job::Shaft(_) | Job::WFree | Job::Open(_, _));
        let freeze_shaft = (1u8 << WIZ) | (1u8 << P);
        let mut next: Vec<Realized> = Vec::new();
        let mut why = "none";
        if use_exact {
            if let Job::Shaft(x) = job {
                let md1 = left.min(16);
                let (h1, _e, _n, st1) = realize_bfs(
                    &beam,
                    |s| !s.walls.get(idx(x, 8)) || !s.walls.get(idx(x, 9)),
                    md1,
                    secs,
                    cap,
                    8,
                    4,
                    gmask,
                    freeze_shaft,
                    &format!("Shaft({})-wall1", x),
                );
                why = st1;
                if !h1.is_empty() {
                    println!(
                        "    shaft wall1 n={} best_len={} {}",
                        h1.len(),
                        h1[0].path.len(),
                        feat(&h1[0].s, gmask)
                    );
                    let md2 = left.min(24);
                    let (h2, _e2, _n2, st2) = realize_bfs(
                        &h1,
                        |s| shaft_open(s, x),
                        md2,
                        secs,
                        cap,
                        8,
                        3,
                        gmask,
                        freeze_shaft,
                        &format!("Shaft({})-open", x),
                    );
                    why = st2;
                    next = h2;
                }
            } else {
                let md = left.min((est * 2 + 12).max(24)).min(48);
                let extra = if matches!(job, Job::WFree) { 12 } else { 3 };
                let out_k = if matches!(job, Job::WFree | Job::Open(_, _)) { 16 } else { 8 };
                // Open(10,10) is a Druid convert; other heroes only press A.
                let fr = if matches!(job, Job::Open(_, _)) {
                    (1u8 << F) | (1u8 << T) | (1u8 << WIZ) | (1u8 << P) | (1u8 << B)
                } else {
                    0
                };
                let (hits, _e, _n, st) = realize_bfs(
                    &beam,
                    |s| job_done(s, job, plan, gmask),
                    md,
                    secs,
                    cap,
                    out_k,
                    extra,
                    gmask,
                    fr,
                    &format!("{:?}", job),
                );
                why = st;
                next = hits;
            }
        }
        if next.is_empty() {
            // Guided fallback, or primary for long jobs (early escape from 85 / 0).
            println!(
                "    guided {:?} est={} exact_hits=0 ({})",
                job, est, why
            );
            for r in beam.iter().take(4) {
                let md = left.min(if use_exact { 40 } else { left });
                let (hits, st, exp, seen) = guided_until(
                    r.s,
                    &r.path,
                    plan,
                    job,
                    md,
                    width,
                    secs,
                    cap,
                    gmask,
                    8,
                );
                println!(
                    "    guided {:?} {} hits={} exp={} seen={}",
                    job,
                    st,
                    hits.len(),
                    exp,
                    seen
                );
                next.extend(hits);
                if next.len() >= 8 {
                    break;
                }
            }
            next.truncate(8);
        }
        if next.is_empty() {
            println!("  FAIL {:?} not realized", job);
            return None;
        }
        union_official(&mut next, plan, job, gmask);
        rank_by_total(&mut next, plan, gmask, 8);
        next.sort_by_key(|r| r.path.len());
        println!(
            "    realized {:?} n={} best_len={} {} path={}",
            job,
            next.len(),
            next[0].path.len(),
            feat(&next[0].s, gmask),
            next[0].path
        );
        // Re-rank by estimated total so the next job prefers a cheap finish
        // over a cheap first step.
        rank_by_total(&mut next, plan, gmask, 8);
        let dir = std::path::Path::new("planner/runs");
        let _ = std::fs::create_dir_all(dir);
        let dump = dir.join(format!("intermediates-{}-{:?}.txt", plan.name, job));
        let body: String = next
            .iter()
            .map(|r| format!("{} {}\n", r.path.len(), r.path))
            .collect();
        let _ = std::fs::write(&dump, body);
        beam = next;
        i += 1;
    }
    beam.into_iter().find(|r| r.s.win(gmask))
}

fn write_candidate(name: &str, full: &str, won_rust: bool) {
    let dir = std::path::Path::new("planner/runs");
    let _ = std::fs::create_dir_all(dir);
    let path = dir.join(format!("candidate-{}-{}.txt", name, full.len()));
    let body = format!("name={}\nlen={}\nrust_win={}\nroute={}\n", name, full.len(), won_rust, full);
    let _ = std::fs::write(&path, body);
    // append index
    let idxp = dir.join("candidates.txt");
    let line = format!("{} {} rust_win={} {}\n", name, full.len(), won_rust, path.display());
    let mut existing = std::fs::read_to_string(&idxp).unwrap_or_default();
    existing.push_str(&line);
    let _ = std::fs::write(&idxp, existing);
    println!("  wrote {}", path.display());
}

fn shot_main(args: &[String]) {
    let secs: f64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(60.0);
    let width: usize = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(40_000);
    let cap: usize = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(6_000_000);
    let only: Option<&str> = args.iter().find_map(|a| a.strip_prefix("only="));
    let gmask = goals();
    let mut plans = plan_book();
    if let Some(name) = only {
        plans.retain(|p| p.name == name || p.name.contains(name));
        if plans.is_empty() {
            eprintln!("no plan matches only={}", name);
            return;
        }
    }
    println!(
        "SHOT plans={} secs={} width={} cap={}",
        plans.len(),
        secs,
        width,
        cap
    );
    let mut best_len: usize = 316;
    let mut best_name = String::new();
    let mut cal_ok = false;
    for plan in &plans {
        println!(
            "\n======== {} prefix={} remaining<= {} assign={}",
            plan.name,
            plan.prefix,
            316 - plan.prefix,
            assign_str(&plan.assign)
        );
        println!("  jobs {}", jobs_str(&plan.jobs));
        let found = run_plan(plan, secs, width, cap, gmask);
        if plan.name.starts_with("cal_246_official") {
            match &found {
                Some(r) if plan.prefix + r.path.len() <= 316 => {
                    cal_ok = true;
                    println!(
                        "  CALIBRATION OK total={}",
                        plan.prefix + r.path.len()
                    );
                }
                _ => println!("  CALIBRATION MISSED (chain or finish beam needs work)"),
            }
        }
        if let Some(r) = found {
            let full = format!("{}{}", &ROUTE316[..plan.prefix], r.path);
            let mut s2 = St::start();
            let (al, w, k) = apply_route(&mut s2, &full, gmask);
            println!(
                "  rust-verify alive={} win={} steps={} total={}",
                al,
                w,
                k,
                full.len()
            );
            if al && w && k == full.len() {
                write_candidate(plan.name, &full, true);
                if full.len() < best_len {
                    best_len = full.len();
                    best_name = plan.name.to_string();
                }
                if full.len() < 316 {
                    println!("  CANDIDATE SHORTER THAN 316: {} {}", plan.name, full.len());
                }
            }
        }
    }
    println!(
        "\nSHOT DONE cal_ok={} best={} {}",
        cal_ok,
        best_len,
        best_name
    );
}
