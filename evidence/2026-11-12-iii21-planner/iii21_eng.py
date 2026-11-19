#!/usr/bin/env python3
"""Fast III-21 engine. Part III, six heroes including Bard. Match PuzzleScriptOracle."""
from __future__ import annotations
import sys, time, heapq, itertools
from collections import deque
from array import array

W, H, N = 23, 13, 23 * 13
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
DIRLIST = [(0, -1), (0, 1), (-1, 0), (1, 0)]
KEYS = "UDLRA"
# hero cycle F T W P B D  == 1 2 3 4 5 6
# indices 0..5
F, T, WIZ, P, B, D = 0, 1, 2, 3, 4, 5
HN = 6
NAMES_A = "FTWPBD"
NAMES_I = "123456"
TO_I = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}  # unused

GRID = [
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
]
ROUTE316 = 'RRRDRRDRRRURRDRRUURRRRRLLLLDDAUAADLLULLLLLDDAAALLLULDDDRDLULDDLLUUAAAULLULAAUADLLLLLAAADLAAALDADRAAAALLDAULAALARUAAARRRRRAUAARDRAAARRDRRUADDRRDDRLAAUAAAULLRRURURDDAURULDDRRRRLLLLAAUUAAARDDRRRDRRRRRAAAAAULLULULULLLDUURLDLLUALLLUUAAAALLLLLDLLLDULLULLLLLLLADDRDALDDAUAAALDURADDUUAAAUAARRRRRRRRUUURUUADRDDDAAAUUURDDDAUUL'
assert len(ROUTE316) == 316, len(ROUTE316)

GOALS = []
for y, row in enumerate(GRID):
    for x, c in enumerate(row):
        if c == "G":
            GOALS.append(y * W + x)
GOALS = tuple(GOALS)
GOALSET = set(GOALS)

def idx(x, y):
    return y * W + x

def xy(i):
    return i % W, i // W

def inb(x, y):
    return 0 <= x < W and 0 <= y < H

# board codes in bytearray:
# 0 empty, 1 wall, 2 crate, 3 goblin
# heroes stored separately
WALL, CRATE, GOB = 1, 2, 3

class St:
    __slots__ = ("b", "heroes", "active", "notes")
    # b: array('B') length N
    # heroes: list of 6 ints, -1 gone
    # active: 0..5
    # notes: int bitboard (Python int, 299 bits) — notes after last late

    def __init__(self):
        self.b = array("B", [0]) * N
        self.heroes = [-1] * 6
        self.active = 0
        self.notes = 0

    def clone(self):
        s = St.__new__(St)
        s.b = array("B", self.b)
        s.heroes = self.heroes[:]
        s.active = self.active
        s.notes = self.notes
        return s

    def pack(self):
        return (self.b.tobytes(), tuple(self.heroes), self.active, self.notes)

    def hero_at(self, i):
        for h, p in enumerate(self.heroes):
            if p == i:
                return h
        return None

    def occupied(self, i):
        return self.b[i] != 0 or self.hero_at(i) is not None

    def empty(self, i):
        return self.b[i] == 0 and self.hero_at(i) is None

    def moveable(self, i):
        o = self.b[i]
        if o == CRATE or o == GOB:
            return True
        h = self.hero_at(i)
        return h is not None and h != self.active

    def is_healer_at(self, i):
        return self.heroes[P] == i

    def hog(self):
        n = 0
        for p in self.heroes:
            if p in GOALSET:
                n += 1
        return n

    def win(self):
        for p in self.heroes:
            if p < 0 or p not in GOALSET:
                return False
        return True

    def nheroes(self):
        return sum(1 for p in self.heroes if p >= 0)

    def render(self):
        gset = GOALSET
        lines = []
        for y in range(H):
            row = []
            for x in range(W):
                i = idx(x, y)
                o = self.b[i]
                if o == WALL:
                    row.append("#")
                elif o == CRATE:
                    row.append("*")
                elif o == GOB:
                    row.append("O")
                else:
                    h = self.hero_at(i)
                    if h is not None:
                        row.append(NAMES_A[h] if h == self.active else NAMES_I[h])
                    elif i in gset:
                        row.append("G")
                    else:
                        row.append(".")
            lines.append("".join(row))
        return "\n".join(lines)


def start_state():
    s = St()
    for y, row in enumerate(GRID):
        for x, c in enumerate(row):
            i = idx(x, y)
            if c == "#":
                s.b[i] = WALL
            elif c == "O":
                s.b[i] = GOB
            elif c == "*":
                s.b[i] = CRATE
            elif c == "F":
                s.heroes[F] = i
                s.active = F
            elif c == "1":
                s.heroes[F] = i
            elif c == "2":
                s.heroes[T] = i
            elif c == "T":
                s.heroes[T] = i
                s.active = T
            elif c == "3":
                s.heroes[WIZ] = i
            elif c == "W":
                s.heroes[WIZ] = i
                s.active = WIZ
            elif c == "4":
                s.heroes[P] = i
            elif c == "P":
                s.heroes[P] = i
                s.active = P
            elif c == "5":
                s.heroes[B] = i
            elif c == "B":
                s.heroes[B] = i
                s.active = B
            elif c == "6":
                s.heroes[D] = i
            elif c == "D":
                s.heroes[D] = i
                s.active = D
    s.notes = compute_notes(s)
    return s


def compute_notes(s):
    if s.active != B:
        return 0
    bp = s.heroes[B]
    if bp < 0:
        return 0
    bx, by = xy(bp)
    notes = 0
    for ny in range(max(0, by - 2), min(H, by + 3)):
        for nx in range(max(0, bx - 2), min(W, bx + 3)):
            if nx == bx and ny == by:
                continue
            i = idx(nx, ny)
            if s.moveable(i):
                notes |= 1 << i
    return notes


def late(s):
    """Mutate s: goblin dying. Return True if a hero died. Then recompute notes."""
    dying = 0
    # goblins
    for i in range(N):
        if s.b[i] != GOB:
            continue
        x, y = xy(i)
        for dx, dy in DIRLIST:
            nx, ny = x + dx, y + dy
            if inb(nx, ny):
                j = idx(nx, ny)
                if s.b[j] == GOB or s.hero_at(j) is not None:
                    dying |= 1 << j
    if dying:
        pc = s.heroes[P]
        if pc >= 0:
            dying &= ~(1 << pc)
            x, y = xy(pc)
            for dx, dy in DIRLIST:
                nx, ny = x + dx, y + dy
                if inb(nx, ny):
                    j = idx(nx, ny)
                    if s.hero_at(j) is not None:
                        dying &= ~(1 << j)
        dead = False
        i = 0
        d = dying
        while d:
            if d & 1:
                if s.b[i] == GOB:
                    s.b[i] = 0
                elif s.hero_at(i) is not None:
                    dead = True
            d >>= 1
            i += 1
        s.notes = compute_notes(s)
        return dead
    s.notes = compute_notes(s)
    return False


def xfer(s, frm, to):
    o = s.b[frm]
    if o == CRATE or o == GOB:
        s.b[frm] = 0
        s.b[to] = o
        return
    h = s.hero_at(frm)
    if h is not None:
        s.heroes[h] = to


def step(s, key):
    """Mutate s. Returns (alive, won, changed). Bard-cancel restores and skips late."""
    before_b = array("B", s.b)
    before_h = s.heroes[:]
    before_a = s.active
    before_n = s.notes

    def restore():
        s.b = before_b
        s.heroes = before_h
        s.active = before_a
        s.notes = before_n

    def changed():
        return s.b != before_b or s.heroes != before_h or s.active != before_a or s.notes != before_n

    ai = s.active
    ap = s.heroes[ai]
    if ap < 0:
        return False, False, False
    ax, ay = xy(ap)

    if key == "A":
        for off in range(1, HN):
            t = (ai + off) % HN
            if s.heroes[t] >= 0:
                s.active = t
                break
        if late(s):
            return False, False, True
        return True, s.win(), changed()

    if key not in DIRS:
        return True, s.win(), False
    dx, dy = DIRS[key]
    nx, ny = ax + dx, ay + dy

    if ai == F:
        if inb(nx, ny):
            cx, cy = nx, ny
            while inb(cx, cy) and s.moveable(idx(cx, cy)):
                cx += dx
                cy += dy
            if inb(cx, cy) and s.empty(idx(cx, cy)):
                while (cx, cy) != (ax, ay):
                    px, py = cx - dx, cy - dy
                    xfer(s, idx(px, py), idx(cx, cy))
                    cx, cy = px, py
                s.heroes[F] = idx(nx, ny)
    elif ai == T:
        if inb(nx, ny) and s.empty(idx(nx, ny)):
            s.heroes[T] = idx(nx, ny)
            bx, by = ax - dx, ay - dy
            if inb(bx, by) and s.moveable(idx(bx, by)):
                xfer(s, idx(bx, by), ap)
    elif ai == WIZ:
        wx, wy = ax, ay
        while True:
            tx, ty = wx + dx, wy + dy
            if not inb(tx, ty):
                if inb(nx, ny) and s.empty(idx(nx, ny)):
                    s.heroes[WIZ] = idx(nx, ny)
                break
            ti = idx(tx, ty)
            if s.empty(ti):
                wx, wy = tx, ty
            elif s.b[ti] == WALL:
                if s.empty(idx(nx, ny)):
                    s.heroes[WIZ] = idx(nx, ny)
                break
            elif s.moveable(ti):
                xfer(s, ti, ap)
                s.heroes[WIZ] = ti
                break
            else:
                break
    elif ai == P:
        if inb(nx, ny) and s.empty(idx(nx, ny)):
            s.heroes[P] = idx(nx, ny)
    elif ai == D:
        if inb(nx, ny):
            ti = idx(nx, ny)
            if s.empty(ti):
                s.heroes[D] = ti
            elif s.b[ti] == CRATE or s.b[ti] == GOB:
                s.b[ti] = WALL
            elif s.b[ti] == WALL:
                s.b[ti] = CRATE
            elif s.is_healer_at(ti):
                pass
            elif s.hero_at(ti) is not None:
                hx, hy = xy(ti)
                adj = False
                for ddx, ddy in DIRLIST:
                    qx, qy = hx + ddx, hy + ddy
                    if inb(qx, qy) and s.is_healer_at(idx(qx, qy)):
                        adj = True
                        break
                if not adj:
                    h = s.hero_at(ti)
                    s.heroes[h] = -1
                    s.b[ti] = WALL
    elif ai == B:
        # official: charm from prior notes; cancel + skip late if bard doesn't move
        charmed = s.notes
        bard = ap
        bard_moved = False
        # iterate until stable; process charms in cell-index order (row-major)
        while True:
            changed_m = False
            # collect current charmed cells that still have a moveable
            cells = []
            bits = charmed
            i = 0
            while bits:
                if bits & 1:
                    cells.append(i)
                bits >>= 1
                i += 1
            for c in cells:
                if not (charmed & (1 << c)):
                    continue
                # object may have already been moved off c
                if not s.moveable(c) and s.hero_at(c) is None and s.b[c] == 0:
                    charmed &= ~(1 << c)
                    continue
                x, y = xy(c)
                tx, ty = x + dx, y + dy
                if inb(tx, ty) and s.empty(idx(tx, ty)):
                    xfer(s, c, idx(tx, ty))
                    charmed &= ~(1 << c)
                    changed_m = True
            if not bard_moved:
                bx, by = xy(bard)
                tx, ty = bx + dx, by + dy
                if inb(tx, ty) and s.empty(idx(tx, ty)):
                    s.heroes[B] = idx(tx, ty)
                    bard = s.heroes[B]
                    bard_moved = True
                    changed_m = True
            if not changed_m:
                break
        if not bard_moved:
            restore()
            return True, s.win(), False
        s.notes = 0

    if late(s):
        return False, False, True
    return True, s.win(), changed()


def apply_route(s, route):
    for i, ch in enumerate(route):
        alive, won, _ = step(s, ch)
        if not alive:
            return False, False, i + 1
        if won and i + 1 != len(route):
            return True, False, i + 1  # premature
    return True, s.win(), len(route)


def apply_prefix(n, route=ROUTE316):
    s = start_state()
    apply_route(s, route[:n])
    return s


def manh(a, b):
    ax, ay = xy(a)
    bx, by = xy(b)
    return abs(ax - bx) + abs(ay - by)


def heuristic(s):
    unplaced = []
    free = []
    for h in range(HN):
        p = s.heroes[h]
        if p < 0:
            return 1_000_000
        if p not in GOALSET:
            unplaced.append(p)
    for g in GOALS:
        if s.hero_at(g) is None:
            free.append(g)
    if not unplaced:
        return 0
    if len(unplaced) != len(free):
        return 1_000_000
    k = len(unplaced)
    best = 10 ** 9
    for perm in itertools.permutations(free, k):
        tot = 0
        for i in range(k):
            tot += manh(unplaced[i], perm[i])
            if tot >= best:
                break
        else:
            if tot < best:
                best = tot
    active_on = s.heroes[s.active] in GOALSET
    sw = k if active_on else max(k - 1, 0)
    return best + sw


def verify():
    import pickle
    data = pickle.load(open("/tmp/iii21-316-frames.pkl", "rb"))
    frames = data["frames"]
    s = start_state()
    r0 = s.render()
    if r0 != frames[0]:
        print("START MISMATCH")
        print("eng:\n", r0)
        print("ora:\n", frames[0])
        return False
    for i, ch in enumerate(ROUTE316, 1):
        alive, won, _ = step(s, ch)
        r = s.render()
        if r != frames[i]:
            print(f"FRAME {i} {ch} MISMATCH alive={alive} win={won}")
            print("eng:\n" + r)
            print("ora:\n" + frames[i])
            return False
        if not alive:
            print(f"DIED at {i}")
            return False
        if won and i != 316:
            print(f"PREMATURE WIN at {i}")
            return False
    print(f"VERIFY 316 OK  win={s.win()} hog={s.hog()} notes={s.notes.bit_count()}")
    return True


def astar(start, max_d, secs, find_known=None):
    """A* for a win of length <= max_d. h may be inadmissible (wizard swaps)."""
    t0 = time.time()
    h0 = heuristic(start)
    # heap: (f, g, seq, counter, state)
    c = 0
    heap = [(h0, 0, "", 0, start)]
    seen = {start.pack(): 0}
    exp = 0
    best = None
    while heap:
        if time.time() - t0 > secs:
            return best, exp, len(seen), "timeout"
        f, g, path, _, s = heapq.heappop(heap)
        if g > max_d:
            continue
        if seen.get(s.pack(), 10**9) < g:
            continue
        exp += 1
        if s.win() and g > 0:
            return path, exp, len(seen), "found"
        if g == max_d:
            continue
        for k in KEYS:
            ns = s.clone()
            alive, won, chg = step(ns, k)
            if not alive:
                continue
            if not chg and k != "A":
                # prune movement no-ops; A may be needed? A that doesn't change is cycle of 1 hero — prune
                continue
            if not chg:
                continue
            ng = g + 1
            pk = ns.pack()
            if seen.get(pk, 10**9) <= ng:
                continue
            seen[pk] = ng
            if won:
                return path + k, exp, len(seen), "found"
            # h can overestimate (wizard swaps), so use it only for ordering, never to prune
            h = heuristic(ns)
            c += 1
            heapq.heappush(heap, (ng + h, ng, path + k, c, ns))
    return best, exp, len(seen), "exhausted"


def bfs(start, max_d, secs):
    t0 = time.time()
    q = deque([(start, "")])
    seen = {start.pack()}
    exp = 0
    while q:
        if time.time() - t0 > secs:
            return None, exp, len(seen), "timeout"
        s, path = q.popleft()
        g = len(path)
        exp += 1
        if g >= max_d:
            continue
        for k in KEYS:
            ns = s.clone()
            alive, won, chg = step(ns, k)
            if not alive or not chg:
                continue
            pk = ns.pack()
            if pk in seen:
                continue
            np = path + k
            if won:
                return np, exp, len(seen), "found"
            seen.add(pk)
            q.append((ns, np))
    return None, exp, len(seen), "exhausted"


def beam(start, max_d, width, secs, tag=""):
    t0 = time.time()
    # entries: (s, path)
    cur = [(start, "")]
    seen = {start.pack(): 0}
    exp = 0
    best_win = None
    best_hog = start.hog()
    milestones = []
    while cur:
        if time.time() - t0 > secs:
            return best_win, exp, len(seen), "timeout", milestones
        nxt = []
        for s, path in cur:
            g = len(path)
            if g >= max_d:
                continue
            exp += 1
            for k in KEYS:
                ns = s.clone()
                alive, won, chg = step(ns, k)
                if not alive or not chg:
                    continue
                np = path + k
                ng = g + 1
                pk = ns.pack()
                if seen.get(pk, 10**9) <= ng:
                    continue
                seen[pk] = ng
                if won:
                    if best_win is None or len(np) < len(best_win):
                        best_win = np
                        print(f"  BEAM {tag} WIN {len(np)} {np}", flush=True)
                    continue
                hog = ns.hog()
                if hog > best_hog:
                    best_hog = hog
                    h = heuristic(ns)
                    milestones.append((ng, hog, h, np, ns.render()))
                    print(f"  BEAM {tag} hog={hog} at {ng} h={h} {np[-20:]}", flush=True)
                nxt.append((ns, np))
        if not nxt:
            break
        def score(item):
            s, path = item
            h = heuristic(s)
            hog = s.hog()
            # prefer hog, then low g+h, then low h
            return (-hog, len(path) + h, h, len(path))
        if len(nxt) > width * 3:
            # pre-filter roughly
            nxt.sort(key=score)
            nxt = nxt[: width * 3]
        nxt.sort(key=score)
        # diversity: keep some variety of (hog, active, parked-set)
        picked = []
        groups = {}
        for item in nxt:
            s, path = item
            parked = tuple(1 if s.heroes[h] in GOALSET else 0 for h in range(HN))
            key = (s.hog(), s.active, parked)
            groups.setdefault(key, 0)
            if groups[key] < max(2, width // 20) or len(picked) < width:
                if groups[key] < max(4, width // 10):
                    picked.append(item)
                    groups[key] += 1
            if len(picked) >= width:
                break
        cur = picked[:width]
    return best_win, exp, len(seen), "done", milestones


def window_search(route, a, b, secs):
    """Shorter path from exact state at cut a to exact state at cut b."""
    sa = apply_prefix(a, route)
    sb = apply_prefix(b, route)
    target = sb.pack()
    # ignore notes? notes are part of pack. Must match exact including notes.
    t0 = time.time()
    q = deque([(sa, "")])
    seen = {sa.pack()}
    exp = 0
    need = b - a
    while q:
        if time.time() - t0 > secs:
            return None, exp, len(seen), "timeout"
        s, path = q.popleft()
        if len(path) >= need:
            continue
        exp += 1
        for k in KEYS:
            ns = s.clone()
            alive, won, chg = step(ns, k)
            if not alive or not chg:
                continue
            pk = ns.pack()
            np = path + k
            if pk == target:
                return np, exp, len(seen), "found"
            if won:
                # early win — even better
                return np, exp, len(seen), "early_win"
            if pk not in seen and len(np) < need:
                seen.add(pk)
                q.append((ns, np))
    return None, exp, len(seen), "exhausted"


def speed():
    s = start_state()
    t0 = time.time()
    n = 0
    while time.time() - t0 < 1.0:
        s2 = s.clone()
        for ch in "UDLRA":
            step(s2, ch)
            n += 1
            s2 = s.clone()  # unfair
    # better: clone+step
    t0 = time.time()
    n = 0
    base = start_state()
    apply_route(base, ROUTE316[:80])
    while time.time() - t0 < 1.0:
        s2 = base.clone()
        step(s2, "R")
        n += 1
    print(f"clone+step /s from cut 80: {n}")
    t0 = time.time()
    n = 0
    s2 = base.clone()
    keys = "UDLRA" * 200
    while time.time() - t0 < 1.0:
        step(s2, keys[n % len(keys)])
        n += 1
        if n % 50 == 0:
            s2 = base.clone()
    print(f"step /s (reset every 50): {n}")


def dual_verify(route):
    """Verify a candidate with both this engine and the Python oracle."""
    s = start_state()
    alive, won, k = apply_route(s, route)
    print(f"eng  len={len(route)} alive={alive} win={won} steps={k} hog={s.hog()}")
    if not (alive and won and k == len(route)):
        return False
    sys.path.insert(0, "/workspace/soko")
    from soko_mcp.oracle import replay_oracle
    r = replay_oracle(3, GRID, route)
    print("oracle", {kk: r[kk] for kk in ("alive", "exact_win", "premature_win", "steps_executed")})
    return r.get("exact_win") and r.get("alive") and not r.get("premature_win")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "test":
        ok = verify()
        speed()
        sys.exit(0 if ok else 1)
    cmd = args[0]
    if cmd == "prefix":
        n = int(args[1])
        s = apply_prefix(n)
        print(s.render())
        print(f"hog={s.hog()} h={heuristic(s)} active={NAMES_A[s.active]} g+h={n+heuristic(s)}")
        return
    if cmd == "astar":
        cut = int(args[1])
        maxd = int(args[2])
        secs = float(args[3]) if len(args) > 3 else 30
        s = apply_prefix(cut)
        print(f"A* from {cut} maxd={maxd} h={heuristic(s)} hog={s.hog()} secs={secs}", flush=True)
        path, exp, seen, st = astar(s, maxd, secs)
        print(f"result {st} exp={exp} seen={seen} path={path} len={len(path) if path else None}")
        if path:
            full = ROUTE316[:cut] + path
            print(f"FULL {len(full)}")
            print("DUAL", dual_verify(full))
        return
    if cmd == "bfs":
        cut = int(args[1])
        maxd = int(args[2])
        secs = float(args[3]) if len(args) > 3 else 30
        s = apply_prefix(cut)
        print(f"BFS from {cut} maxd={maxd} h={heuristic(s)} hog={s.hog()} secs={secs}", flush=True)
        path, exp, seen, st = bfs(s, maxd, secs)
        print(f"result {st} exp={exp} seen={seen} path={path} len={len(path) if path else None}")
        if path:
            full = ROUTE316[:cut] + path
            print(f"FULL {len(full)}")
            print("DUAL", dual_verify(full))
        return
    if cmd == "beam":
        cut = int(args[1])
        maxd = int(args[2])
        width = int(args[3])
        secs = float(args[4]) if len(args) > 4 else 30
        s = apply_prefix(cut)
        print(f"BEAM from {cut} maxd={maxd} w={width} h={heuristic(s)} hog={s.hog()} secs={secs}", flush=True)
        path, exp, seen, st, ms = beam(s, maxd, width, secs, tag=f"c{cut}")
        print(f"result {st} exp={exp} seen={seen} path={path} len={len(path) if path else None}")
        if path:
            full = ROUTE316[:cut] + path
            print(f"FULL {len(full)}")
            print("DUAL", dual_verify(full))
        return
    if cmd == "window":
        a, b = int(args[1]), int(args[2])
        secs = float(args[3]) if len(args) > 3 else 10
        path, exp, seen, st = window_search(ROUTE316, a, b, secs)
        print(f"window {a}->{b} {st} exp={exp} seen={seen} len={len(path) if path else None} saved={(b-a)-len(path) if path else 0}")
        if path:
            full = ROUTE316[:a] + path + ROUTE316[b:]
            print(f"FULL {len(full)} {path}")
            print("DUAL", dual_verify(full))
        return
    if cmd == "windows":
        # sweep useful cuts
        cuts = [0, 23, 29, 47, 57, 87, 120, 137, 164, 182, 200, 223, 246, 253, 259, 262, 289, 296, 302, 312]
        secs = float(args[1]) if len(args) > 1 else 4
        for i, a in enumerate(cuts):
            for b in cuts[i + 1 :]:
                if b - a > 80:
                    continue
                path, exp, seen, st = window_search(ROUTE316, a, b, secs)
                mark = ""
                if path and len(path) < b - a:
                    mark = f"  SAVE {b-a-len(path)} FULL {a+len(path)+316-b}"
                    print(f"  {a}->{b} {st} {len(path)} vs {b-a}{mark}", flush=True)
                    full = ROUTE316[:a] + path + ROUTE316[b:]
                    print("  DUAL", dual_verify(full), flush=True)
                elif st != "exhausted" and st != "timeout":
                    print(f"  {a}->{b} {st} {len(path) if path else '-'} vs {b-a} exp={exp}", flush=True)
        return
    if cmd == "verify-route":
        route = args[1]
        print("DUAL", dual_verify(route))
        return
    print("unknown", cmd)

if __name__ == "__main__":
    main()
