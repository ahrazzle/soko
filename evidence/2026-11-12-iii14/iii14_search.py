#!/usr/bin/env python3
"""Fast III-14 engine + window/beam search for a route shorter than 48."""
from __future__ import annotations

import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/workspace/soko")
from soko_mcp.oracle import FRONTIER_ROOMS, PuzzleScriptOracle
from soko_mcp.engine_bridge import verify_route_dual

ROOM = FRONTIER_ROOMS["III-14-15x7"]
GRID = ROOM["grid"]
SEED = ROOM["reference_route"]
W, H = 15, 7
MOVES = "UDLRA"
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}

# cells
def idx(x, y):
    return y * W + x

SWITCHES = tuple(idx(x, y) for y in (2, 3, 4) for x in (4, 5, 6))
DOORS = tuple(
    idx(x, y)
    for (x, y) in (
        (8, 2), (9, 2), (10, 2), (11, 2), (12, 2),
        (8, 3), (12, 3),
        (8, 4), (9, 4), (10, 4), (11, 4), (12, 4),
    )
)
GOALS = (idx(9, 3), idx(11, 3))
SWITCH_MASK = sum(1 << c for c in SWITCHES)
DOOR_MASK = sum(1 << c for c in DOORS)
GOAL_MASK = sum(1 << c for c in GOALS)
ALL = (1 << (W * H)) - 1

# In-bounds interior is everything; movement checks bounds via x,y


def bit(c):
    return 1 << c


@dataclass(slots=True)
class S:
    walls: int
    crates: int
    doors: int  # closed door bits, subset of DOOR_MASK
    bx: int
    by: int
    dx: int
    dy: int
    bard_active: bool
    notes: int  # moveable cells with notes (crates + inactive hero)

    def pack(self):
        return (
            self.walls,
            self.crates,
            self.doors,
            self.bx,
            self.by,
            self.dx,
            self.dy,
            self.bard_active,
            self.notes,
        )

    @staticmethod
    def unpack(p) -> "S":
        return S(*p)

    def occupied(self) -> int:
        occ = self.walls | self.crates | self.doors
        occ |= bit(idx(self.bx, self.by))
        occ |= bit(idx(self.dx, self.dy))
        return occ

    def weights(self) -> int:
        occ = self.walls | self.crates
        occ |= bit(idx(self.bx, self.by))
        occ |= bit(idx(self.dx, self.dy))
        return occ & SWITCH_MASK

    def all_weighed(self) -> bool:
        return self.weights() == SWITCH_MASK

    def win(self) -> bool:
        h = bit(idx(self.bx, self.by)) | bit(idx(self.dx, self.dy))
        return h == GOAL_MASK


def start_state() -> S:
    o = PuzzleScriptOracle(3, GRID)
    walls = crates = doors = 0
    bx = by = dx_ = dy_ = 0
    bard_active = False
    for y in range(H):
        for x in range(W):
            c = idx(x, y)
            obj = o.obj[y][x]
            if obj == "#":
                walls |= bit(c)
            elif obj == "*":
                crates |= bit(c)
            elif obj == "]":
                doors |= bit(c)
            elif obj in ("B", "5"):
                bx, by = x, y
                bard_active = obj == "B"
            elif obj in ("D", "6"):
                dx_, dy_ = x, y
    return S(walls, crates, doors, bx, by, dx_, dy_, bard_active, 0)


def _update_doors_and_notes(s: S) -> Optional[S]:
    """Late phase. Returns None if a hero is crushed."""
    if s.weights() == SWITCH_MASK:
        s.doors = 0
    else:
        # closing: crush heroes on open door cells (currently doors==0 there)
        hb = bit(idx(s.bx, s.by)) | bit(idx(s.dx, s.dy))
        currently_open = DOOR_MASK & ~s.doors
        if hb & currently_open:
            return None
        s.doors = DOOR_MASK
    # recompute notes if bard active
    if s.bard_active:
        notes = 0
        bx, by = s.bx, s.by
        for ny in range(max(0, by - 2), min(H, by + 3)):
            for nx in range(max(0, bx - 2), min(W, bx + 3)):
                if nx == bx and ny == by:
                    continue
                c = idx(nx, ny)
                # moveable: crate or inactive druid
                if s.crates & bit(c):
                    notes |= bit(c)
                elif nx == s.dx and ny == s.dy:
                    notes |= bit(c)
        s.notes = notes
    else:
        s.notes = 0
    return s


def step(s: S, key: str) -> Optional[S]:
    """Return new state, or None if dead. No-ops (cancelled bard) return a new equal state."""
    ns = S(
        s.walls, s.crates, s.doors, s.bx, s.by, s.dx, s.dy, s.bard_active, s.notes
    )
    if key == "A":
        ns.bard_active = not ns.bard_active
        ns.notes = 0
        return _update_doors_and_notes(ns)

    ddx, ddy = DIRS[key]
    if ns.bard_active:
        # Bard charm + move; cancel entirely if bard cannot move
        # Iterate notes in sorted cell index for determinism; retry like the oracle
        charmed = []
        notes = ns.notes
        # include only still-moveable
        for c in range(W * H):
            if notes & (1 << c):
                charmed.append(c)
        bard_c = idx(ns.bx, ns.by)
        bard_moved = False
        pending = set(charmed)
        hero_druid = idx(ns.dx, ns.dy)

        def is_empty(c: int, bpos: int, dpos: int) -> bool:
            if c < 0 or c >= W * H:
                return False
            # also need x,y bounds for wrap: caller must check
            if ns.walls & (1 << c):
                return False
            if ns.crates & (1 << c):
                return False
            if ns.doors & (1 << c):
                return False
            if c == bpos or c == dpos:
                return False
            return True

        def xy(c):
            return c % W, c // W

        def dest(c):
            x, y = xy(c)
            nx, ny = x + ddx, y + ddy
            if not (0 <= nx < W and 0 <= ny < H):
                return -1
            return idx(nx, ny)

        bpos = bard_c
        dpos = hero_druid
        changed = True
        moved_set = set()
        while changed:
            changed = False
            for c in list(pending):
                t = dest(c)
                if t < 0:
                    continue
                if is_empty(t, bpos, dpos):
                    # move crate or druid
                    if ns.crates & (1 << c):
                        ns.crates &= ~(1 << c)
                        ns.crates |= 1 << t
                    elif c == dpos:
                        dpos = t
                        ns.dx, ns.dy = xy(t)
                    pending.discard(c)
                    moved_set.add(c)
                    changed = True
            if not bard_moved:
                t = dest(bpos)
                if t >= 0 and is_empty(t, bpos, dpos):
                    bpos = t
                    ns.bx, ns.by = xy(t)
                    bard_moved = True
                    changed = True
        if not bard_moved:
            # cancel: return original (alive no-op)
            return S(s.walls, s.crates, s.doors, s.bx, s.by, s.dx, s.dy, s.bard_active, s.notes)
        ns.notes = 0
        return _update_doors_and_notes(ns)

    # Druid move
    nx, ny = ns.dx + ddx, ns.dy + ddy
    if not (0 <= nx < W and 0 <= ny < H):
        ns.notes = 0
        return _update_doors_and_notes(ns)
    t = idx(nx, ny)
    tb = 1 << t
    # empty?
    occ_no_druid = ns.walls | ns.crates | ns.doors | bit(idx(ns.bx, ns.by))
    if not (occ_no_druid & tb):
        ns.dx, ns.dy = nx, ny
    elif ns.crates & tb:
        ns.crates &= ~tb
        ns.walls |= tb
    elif ns.walls & tb:
        ns.walls &= ~tb
        ns.crates |= tb
    elif nx == ns.bx and ny == ns.by:
        # petrify bard into wall
        ns.walls |= tb
        # bard is gone — illegal for a win, keep a dummy off-board? mark dead
        return None
    # else blocked (door, etc.): no object change
    ns.notes = 0
    return _update_doors_and_notes(ns)


def from_oracle(o: PuzzleScriptOracle) -> S:
    walls = crates = doors = notes = 0
    bx = by = dx_ = dy_ = 0
    bard_active = False
    for y in range(H):
        for x in range(W):
            c = idx(x, y)
            obj = o.obj[y][x]
            if obj == "#":
                walls |= bit(c)
            elif obj == "*":
                crates |= bit(c)
            elif obj == "]":
                doors |= bit(c)
            elif obj in ("B", "5"):
                bx, by = x, y
                bard_active = obj == "B"
            elif obj in ("D", "6"):
                dx_, dy_ = x, y
    for (x, y) in o.notes:
        notes |= bit(idx(x, y))
    return S(walls, crates, doors, bx, by, dx_, dy_, bard_active, notes)


def eq_oracle(s: S, o: PuzzleScriptOracle) -> bool:
    t = from_oracle(o)
    return s.pack() == t.pack()


def replay(route: str) -> tuple[S, bool, bool]:
    s = start_state()
    for k in route:
        ns = step(s, k)
        if ns is None:
            return s, False, False
        s = ns
    return s, True, s.win()


def test_engine() -> None:
    s = start_state()
    o = PuzzleScriptOracle(3, GRID)
    assert eq_oracle(s, o), "start mismatch"
    s2 = s
    o2 = o
    for i, k in enumerate(SEED, 1):
        o2 = o2.clone()
        alive, won = o2.step(k)
        ns = step(s2, k)
        if ns is None:
            raise SystemExit(f"fast engine died at {i} {k}, oracle alive={alive}")
        if not eq_oracle(ns, o2):
            print(f"MISMATCH at step {i} {k}")
            print("oracle ascii:")
            print(o2.render_ascii())
            print("oracle notes", sorted(o2.notes), "active", o2.find_active())
            print("fast", ns)
            print("from_oracle", from_oracle(o2))
            # show diffs
            t = from_oracle(o2)
            for name in ("walls", "crates", "doors", "bx", "by", "dx", "dy", "bard_active", "notes"):
                a, b = getattr(ns, name), getattr(t, name)
                if a != b:
                    print(f"  {name}: fast={a} ora={b}")
            raise SystemExit("mismatch")
        s2 = ns
    print(f"engine matches 48-key seed, final win={s2.win()}")

    # random prefix mutations vs oracle
    import random
    rng = random.Random(0)
    mismatches = 0
    checked = 0
    for trial in range(400):
        o = PuzzleScriptOracle(3, GRID)
        s = start_state()
        for stepn in range(40):
            k = rng.choice(list(MOVES))
            alive, won = o.step(k)
            ns = step(s, k)
            checked += 1
            if (ns is None) and (not alive):
                break
            if (ns is None) != (not alive):
                print("alive mismatch", trial, stepn, k, "fast_dead", ns is None, "ora_alive", alive)
                mismatches += 1
                break
            if ns is None:
                break
            if not eq_oracle(ns, o):
                mismatches += 1
                if mismatches <= 5:
                    print(f"rand mismatch trial={trial} step={stepn} {k}")
                    print(o.render_ascii())
                    print("notes ora", sorted(o.notes), "act", o.find_active())
                    t = from_oracle(o)
                    for name in ("walls", "crates", "doors", "bx", "by", "dx", "dy", "bard_active", "notes"):
                        a, b = getattr(ns, name), getattr(t, name)
                        if a != b:
                            print(f"  {name}: fast={a} ora={b}")
                break
            s = ns
            if won:
                if not s.win():
                    print("win mismatch")
                    mismatches += 1
                break
    print(f"random checks={checked} mismatches={mismatches}")
    if mismatches:
        raise SystemExit("engine not faithful enough")


def traj_states(route: str) -> list[tuple]:
    s = start_state()
    out = [s.pack()]
    for k in route:
        s = step(s, k)
        if s is None:
            break
        out.append(s.pack())
    return out


def window_search(route: str, win: int, max_seen: int, time_budget: float) -> Optional[str]:
    """BFS at every offset; return a shorter verified route if found."""
    t0 = time.perf_counter()
    states = traj_states(route)
    n = len(route)
    if len(states) != n + 1:
        return None
    # map signature -> earliest index
    for left in range(0, n):
        if time.perf_counter() - t0 > time_budget:
            break
        right = min(n, left + win)
        targets = {}
        for k in range(left + 1, right + 1):
            targets.setdefault(states[k], k)
        start = states[left]
        # also: any win earlier than n-left
        max_d = (right - left) - 0  # can be equal and not improve unless win or shorter to target
        # we want paths with len < (target_index - left)
        q = deque()
        q.append((start, ""))
        seen = {start}
        while q:
            if time.perf_counter() - t0 > time_budget:
                break
            if len(seen) > max_seen:
                break
            cur, path = q.popleft()
            if len(path) >= (right - left):
                continue
            st = S.unpack(cur)
            for mv in MOVES:
                ns = step(st, mv)
                if ns is None:
                    continue
                np = path + mv
                pk = ns.pack()
                if ns.win() and left + len(np) < n:
                    return route[:left] + np
                if pk in targets and len(np) < (targets[pk] - left):
                    return route[:left] + np + route[targets[pk]:]
                if len(np) < (right - left) and pk not in seen:
                    seen.add(pk)
                    q.append((pk, np))
    return None


def beam_from(start_route_prefix: str, start: S, beam: int, depth: int, time_budget: float, cap: int) -> Optional[str]:
    """Layered beam search. Rank by heuristic, look for a win shorter than cap - len(prefix)."""
    t0 = time.perf_counter()
    prefix = start_route_prefix
    remain = cap - len(prefix)
    if remain <= 0:
        return None

    def h(s: S) -> int:
        w = bin(s.weights()).count("1")
        # permanent weights: crates+walls on switches
        perm = bin((s.walls | s.crates) & SWITCH_MASK).count("1")
        need = max(0, 9 - perm)
        # hero-goal manhattan, after doors: if not all weighed, extra
        g1x, g1y = 9, 3
        g2x, g2y = 11, 3
        def md(x, y, gx, gy):
            return abs(x - gx) + abs(y - gy)
        # assign heroes to goals
        dA = md(s.bx, s.by, g1x, g1y) + md(s.dx, s.dy, g2x, g2y)
        dB = md(s.bx, s.by, g2x, g2y) + md(s.dx, s.dy, g1x, g1y)
        hd = min(dA, dB)
        doors_closed = 1 if s.doors else 0
        return need * 2 + hd + doors_closed * 2 + (0 if s.all_weighed() else 1)

    layer = [(h(start), start.pack(), "")]
    seen = {start.pack(): 0}
    best = None
    for d in range(remain):
        if time.perf_counter() - t0 > time_budget:
            break
        layer.sort(key=lambda t: t[0])
        layer = layer[:beam]
        nxt = []
        for _, pk, path in layer:
            st = S.unpack(pk)
            for mv in MOVES:
                ns = step(st, mv)
                if ns is None:
                    continue
                np = path + mv
                if ns.win():
                    cand = prefix + np
                    if best is None or len(cand) < len(best):
                        best = cand
                        remain = min(remain, len(np) - 1)
                    continue
                k = ns.pack()
                g = len(np)
                if k in seen and seen[k] <= g:
                    continue
                if g >= remain:
                    continue
                seen[k] = g
                nxt.append((h(ns) + g, k, np))
        if not nxt:
            break
        layer = nxt
    return best


def iterative_improve(route: str, seconds: float) -> str:
    t_end = time.perf_counter() + seconds
    best = route
    rounds = 0
    while time.perf_counter() < t_end:
        rounds += 1
        left = t_end - time.perf_counter()
        # widen windows over rounds
        for win, seen, frac in (
            (8, 80000, 0.15),
            (10, 120000, 0.15),
            (12, 200000, 0.2),
            (14, 250000, 0.2),
            (16, 300000, 0.15),
            (18, 300000, 0.15),
        ):
            budget = max(2.0, left * frac)
            if time.perf_counter() >= t_end:
                break
            found = window_search(best, win, seen, budget)
            if found and len(found) < len(best):
                # verify
                v = verify_route_dual(3, GRID, found)
                if v["valid_winning_route"]:
                    print(f"  WINDOW win={win} improved {len(best)} -> {len(found)} : {found}", flush=True)
                    best = v["route"]
                    break
                else:
                    print(f"  window candidate failed verify len={len(found)}", flush=True)
        else:
            # no improvement this round; try beam from a few prefixes
            states = traj_states(best)
            for cut in (0, 18, 19, 25, 33, 41):
                if cut >= len(best) or time.perf_counter() >= t_end:
                    continue
                s = S.unpack(states[cut])
                bud = min(20.0, t_end - time.perf_counter())
                found = beam_from(best[:cut], s, beam=8000, depth=len(best) - cut - 1, time_budget=bud, cap=len(best))
                if found and len(found) < len(best):
                    v = verify_route_dual(3, GRID, found)
                    if v["valid_winning_route"]:
                        print(f"  BEAM from {cut} improved {len(best)} -> {len(found)} : {found}", flush=True)
                        best = v["route"]
                        break
            else:
                if rounds >= 3:
                    break
    print(f"iterative rounds={rounds} best={len(best)}")
    return best


def main():
    print("=== testing engine ===", flush=True)
    t0 = time.perf_counter()
    test_engine()
    # speed
    s = start_state()
    n = 0
    t1 = time.perf_counter()
    while time.perf_counter() - t1 < 0.5:
        s2 = start_state()
        for k in SEED:
            s2 = step(s2, k)
            n += 1
    dt = time.perf_counter() - t1
    print(f"fast engine {n/dt:.0f} steps/s", flush=True)

    seeds = [
        SEED,
        "LLULULUULRUADRRRRDAULULDLDDRDRDARULDRUUALULRURARDR",  # 50
        "LLULULUULRUADRDRRRAULUDLDDRDRDLARULRUULADLRUUARRRDD",  # 51
        "LLULULUULRUADRDRRRAULUDLDDRDRDARULRUULAUULLUURARRRDD",  # 52
    ]
    best = SEED
    for sd in seeds:
        v = verify_route_dual(3, GRID, sd)
        print(f"seed len={len(sd)} valid={v['valid_winning_route']}", flush=True)
        print(f"=== improving {len(sd)} ===", flush=True)
        found = iterative_improve(sd, seconds=90.0)
        if len(found) < len(best):
            best = found
    print("BEST", len(best), best)
    Path("best.txt").write_text(f"{len(best)}\n{best}\n")


if __name__ == "__main__":
    main()
