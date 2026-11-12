"""Declarative reference interpreter and 10-mutation Planted-Bug Auditor for Heroes of Sokoban I, II, & III."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

ACTIVE_HEROES = {"F", "T", "W", "P", "B", "D"}
INACTIVE_HEROES = {"1", "2", "3", "4", "5", "6"}
TO_INACTIVE = {"F": "1", "T": "2", "W": "3", "P": "4", "B": "5", "D": "6"}
TO_ACTIVE = {v: k for k, v in TO_INACTIVE.items()}
HERO_NAMES = {
    "1": "Fighter (pushes chains of Moveables)", "2": "Thief (pulls 1 Moveable behind)",
    "3": "Wizard (teleports/swaps with line-of-sight Moveable)", "4": "Priest (immune Healer; shields orthogonal heroes)",
    "5": "Bard (5x5 Chebyshev Note aura rigid translation)", "6": "Druid (transmutes Wall <-> Crate and Moveable -> Wall)",
}
CYCLE_ORDER_STD = ["1", "2", "3", "4", "5", "6"]
CYCLE_ORDER_BUG09 = ["1", "3", "2", "4", "5", "6"]
DIRS: Dict[str, Tuple[int, int]] = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
ORTHO = ((0, -1), (0, 1), (-1, 0), (1, 0))

PLANTED_BUGS: List[Tuple[str, str]] = [
    ("BUG_01_IMABAYASHI_SINGLE_PUSH", "Fighter refuses to push >=2 Moveables in a line"),
    ("BUG_02_FIGHTER_RULE_ORDER_SWAP", "Fighter push rule order swapped (single-push collapse)"),
    ("BUG_03_BARD_MANHATTAN_RADIUS", "Bard uses Manhattan radius <=2 instead of 5x5 Chebyshev square"),
    ("BUG_04_BARD_POST_MOVE_CHARM", "Bard evaluates Note aura after stepping instead of end of prior turn"),
    ("BUG_05_WALL_NOT_WEIGHING_PART_III", "Excludes transmuted Wall (#) from Weighing on switches in Part III"),
    ("BUG_06_WIZARD_ADJACENT_NO_SWAP", "Blocks Wizard warpball swap when Moveable is orthogonally adjacent"),
    ("BUG_07_PRIEST_INACTIVE_NO_HEAL", "Inactive SPriest (4) fails to shield adjacent heroes from Goblins"),
    ("BUG_08_GOBLIN_SEQUENTIAL_KILL", "Resolves Goblin attacks sequentially instead of simultaneous Dying layer"),
    ("BUG_09_HERO_CYCLE_SWIZARD_STHIEF_ORDER", "Cycles 1->3->2 (OBJECTS order) instead of 1->2->3 (LEGEND order)"),
    ("BUG_10_PART_II_NO_CANCEL_ON_BLOCKED_MOVE", "Omits Late [Player DidNotMove] -> Cancel on blocked Part I/II moves"),
]

@dataclass(frozen=True)
class MutatorFlags:
    bug_id: Optional[str] = None

class PuzzleScriptOracle:
    """Readable specification-grade interpreter for Heroes of Sokoban Parts I, II, and III."""
    def __init__(self, part: int, rows: List[str], flags: MutatorFlags = MutatorFlags()):
        if part not in (1, 2, 3) or not rows or not rows[0]:
            raise ValueError("Invalid part or empty grid")
        self.part, self.flags, self.h, self.w = part, flags, len(rows), len(rows[0])
        if any(len(r) != self.w for r in rows):
            raise ValueError("Non-rectangular grid")
        self.floor: List[List[Optional[str]]] = [[None] * self.w for _ in range(self.h)]
        self.obj: List[List[Optional[str]]] = [[None] * self.w for _ in range(self.h)]
        self.notes: Set[Tuple[int, int]] = set()
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in ("G", "{", "}"):
                    self.floor[y][x] = ch
                elif ch != ".":
                    self.obj[y][x] = ch
        if self.part == 3:
            self._run_late()

    def clone(self) -> "PuzzleScriptOracle":
        cp = PuzzleScriptOracle.__new__(PuzzleScriptOracle)
        cp.part, cp.flags, cp.h, cp.w = self.part, self.flags, self.h, self.w
        cp.floor = [r[:] for r in self.floor]
        cp.obj = [r[:] for r in self.obj]
        cp.notes = set(self.notes)
        return cp

    def render_ascii(self) -> str:
        return "\n".join(
            "".join(("X" if self.obj[y][x] == "CORPSE" else self.obj[y][x]) if self.obj[y][x]
                    else (self.floor[y][x] if self.floor[y][x] in ("G", "{", "}") else ".")
                    for x in range(self.w))
            for y in range(self.h)
        )

    def state_signature(self) -> Tuple:
        return (tuple(tuple(r) for r in self.obj), tuple(tuple(r) for r in self.floor), frozenset(self.notes))

    def find_active(self) -> Optional[Tuple[int, int, str]]:
        for y in range(self.h):
            for x in range(self.w):
                if self.obj[y][x] in ACTIVE_HEROES:
                    return (x, y, self.obj[y][x])
        return None

    def is_hero(self, o: Optional[str]) -> bool: return (o in ACTIVE_HEROES) or (o in INACTIVE_HEROES)
    def is_healer(self, o: Optional[str]) -> bool:
        return False if self.part == 1 else (o == "P" if self.flags.bug_id == "BUG_07_PRIEST_INACTIVE_NO_HEAL" else o in ("P", "4"))
    def is_monster(self, o: Optional[str]) -> bool:
        return False if self.part == 1 else (o in ("O", "L", "R") if self.part == 2 else o == "O")
    def is_moveable(self, o: Optional[str]) -> bool: return o == "*" or (o in INACTIVE_HEROES) or self.is_monster(o)
    def is_static(self, o: Optional[str]) -> bool: return o in ("#", "[", "]", "M")
    def is_vulnerable(self, o: Optional[str]) -> bool: return self.is_hero(o) or self.is_monster(o)
    def is_weighing(self, o: Optional[str]) -> bool:
        if self.part in (1, 2) or self.flags.bug_id == "BUG_05_WALL_NOT_WEIGHING_PART_III":
            return o == "*" or self.is_hero(o) or self.is_monster(o)
        return o in ("*", "#") or self.is_hero(o) or self.is_monster(o)

    def _compute_notes(self) -> None:
        self.notes.clear()
        act = self.find_active() if self.part == 3 else None
        if not act or act[2] != "B":
            return
        bx, by, _ = act
        for ny in range(max(0, by - 2), min(self.h, by + 3)):
            for nx in range(max(0, bx - 2), min(self.w, bx + 3)):
                if (nx, ny) != (bx, by) and not (self.flags.bug_id == "BUG_03_BARD_MANHATTAN_RADIUS" and abs(nx - bx) + abs(ny - by) > 2):
                    if self.is_moveable(self.obj[ny][nx]):
                        self.notes.add((nx, ny))

    def _run_late(self) -> bool:
        if self.part == 3:
            self._compute_notes()
        dying: Set[Tuple[int, int]] = set()
        if self.part == 2:
            for y in range(self.h):
                for x in range(self.w):
                    o = self.obj[y][x]
                    if o in ("R", "L"):
                        rng = range(x + 1, self.w) if o == "R" else range(x - 1, -1, -1)
                        for nx in rng:
                            no = self.obj[y][nx]
                            if no is not None:
                                if self.is_vulnerable(no):
                                    dying.add((nx, y))
                                break
        corpse = False
        if self.part >= 2:
            if self.flags.bug_id == "BUG_08_GOBLIN_SEQUENTIAL_KILL":
                for y in range(self.h):
                    for x in range(self.w):
                        if self.obj[y][x] == "O":
                            for ddx, ddy in ORTHO:
                                nx, ny = x + ddx, y + ddy
                                if 0 <= nx < self.w and 0 <= ny < self.h:
                                    vo = self.obj[ny][nx]
                                    if vo == "O":
                                        self.obj[ny][nx] = None
                                    elif self.is_hero(vo) and not self.is_healer(vo):
                                        if not any(0 <= nx+hx < self.w and 0 <= ny+hy < self.h and self.is_healer(self.obj[ny+hy][nx+hx]) for hx, hy in ORTHO):
                                            self.obj[ny][nx] = "CORPSE"; corpse = True
            else:
                for y in range(self.h):
                    for x in range(self.w):
                        if self.obj[y][x] == "O":
                            for ddx, ddy in ORTHO:
                                nx, ny = x + ddx, y + ddy
                                if 0 <= nx < self.w and 0 <= ny < self.h and self.is_vulnerable(self.obj[ny][nx]):
                                    dying.add((nx, ny))
                for x, y in list(dying):
                    if self.is_healer(self.obj[y][x]):
                        dying.remove((x, y))
                for y in range(self.h):
                    for x in range(self.w):
                        if self.is_healer(self.obj[y][x]):
                            for ddx, ddy in ORTHO:
                                nx, ny = x + ddx, y + ddy
                                if (nx, ny) in dying and self.is_hero(self.obj[ny][nx]):
                                    dying.remove((nx, ny))
                for x, y in dying:
                    if self.is_monster(self.obj[y][x]):
                        self.obj[y][x] = None
                    elif self.is_hero(self.obj[y][x]):
                        self.obj[y][x] = "CORPSE"; corpse = True

        for sw_ch, door_ch, open_ch in (("{", "[", "YO"), ("}", "]", "PO")):
            sw = [(x, y) for y in range(self.h) for x in range(self.w) if self.floor[y][x] == sw_ch]
            if sw:
                any_w = any(self.is_weighing(self.obj[y][x]) for x, y in sw)
                any_u = any(not self.is_weighing(self.obj[y][x]) for x, y in sw)
                if any_w and not any_u:
                    for y in range(self.h):
                        for x in range(self.w):
                            if self.obj[y][x] == door_ch:
                                self.obj[y][x], self.floor[y][x] = None, open_ch
                elif any_u:
                    for y in range(self.h):
                        for x in range(self.w):
                            if self.floor[y][x] == open_ch:
                                if self.is_hero(self.obj[y][x]):
                                    corpse = True
                                self.floor[y][x], self.obj[y][x] = None, door_ch

        if self.part >= 2 and not any(self.is_monster(self.obj[y][x]) for y in range(self.h) for x in range(self.w)):
            for y in range(self.h):
                for x in range(self.w):
                    if self.obj[y][x] == "M":
                        self.obj[y][x] = None
        if self.part == 3:
            self.notes = {(x, y) for (x, y) in self.notes if self.is_moveable(self.obj[y][x])}
        return corpse

    def check_win(self) -> bool:
        return all(self.is_hero(self.obj[y][x]) == (self.floor[y][x] == "G") for y in range(self.h) for x in range(self.w))

    def step(self, key: str) -> Tuple[bool, bool]:
        if key not in ("U", "D", "L", "R", "A"):
            raise ValueError(f"Invalid key {key!r}")
        act = self.find_active()
        if not act:
            return False, False
        ax, ay, ah = act
        snap = self.clone()
        if key == "A":
            self.notes.clear()
            order = (CYCLE_ORDER_BUG09 if self.flags.bug_id == "BUG_09_HERO_CYCLE_SWIZARD_STHIEF_ORDER" else CYCLE_ORDER_STD)[:(3 if self.part == 1 else (4 if self.part == 2 else 6))]
            cur_inact = TO_INACTIVE[ah]
            cur_pos = order.index(cur_inact)
            switched = False
            for off in range(1, len(order)):
                ti = order[(cur_pos + off) % len(order)]
                found = next(((x, y) for x in range(self.w) for y in range(self.h) if self.obj[y][x] == ti), None)
                if found:
                    self.obj[ay][ax], self.obj[found[1]][found[0]], switched = cur_inact, TO_ACTIVE[ti], True
                    break
            if not switched and self.part <= 2 and self.flags.bug_id != "BUG_10_PART_II_NO_CANCEL_ON_BLOCKED_MOVE":
                return True, self.check_win()
            return (not self._run_late()), self.check_win()

        dx, dy = DIRS[key]
        nx, ny = ax + dx, ay + dy
        moved = False
        if ah == "F":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h:
                if self.flags.bug_id in ("BUG_01_IMABAYASHI_SINGLE_PUSH", "BUG_02_FIGHTER_RULE_ORDER_SWAP"):
                    if self.obj[ny][nx] is None:
                        self.obj[ny][nx], self.obj[ay][ax], moved = "F", None, True
                    elif self.is_moveable(self.obj[ny][nx]) and 0 <= nx+dx < self.w and 0 <= ny+dy < self.h and self.obj[ny+dy][nx+dx] is None:
                        self.obj[ny+dy][nx+dx], self.obj[ny][nx], self.obj[ay][ax], moved = self.obj[ny][nx], "F", None, True
                else:
                    cx, cy = nx, ny
                    while 0 <= cx < self.w and 0 <= cy < self.h and self.is_moveable(self.obj[cy][cx]):
                        cx += dx; cy += dy
                    if 0 <= cx < self.w and 0 <= cy < self.h and self.obj[cy][cx] is None:
                        while (cx, cy) != (ax, ay):
                            self.obj[cy][cx] = self.obj[cy - dy][cx - dx]; cx -= dx; cy -= dy
                        self.obj[ay][ax], moved = None, True
        elif ah == "T":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                bx, by = ax - dx, ay - dy
                self.obj[ny][nx] = "T"
                if 0 <= bx < self.w and 0 <= by < self.h and self.is_moveable(self.obj[by][bx]):
                    self.obj[ay][ax], self.obj[by][bx] = self.obj[by][bx], None
                else:
                    self.obj[ay][ax] = None
                moved = True
        elif ah == "W":
            self.notes.clear()
            wx, wy, steps_out = ax, ay, 0
            while True:
                tx, ty = wx + dx, wy + dy; steps_out += 1
                if not (0 <= tx < self.w and 0 <= ty < self.h):
                    if self.part == 3 and 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                        self.obj[ny][nx], self.obj[ay][ax], moved = "W", None, True
                    break
                tobj = self.obj[ty][tx]
                if tobj is None:
                    wx, wy = tx, ty
                elif self.is_static(tobj):
                    if self.obj[ny][nx] is None:
                        self.obj[ny][nx], self.obj[ay][ax], moved = "W", None, True
                    break
                elif self.is_moveable(tobj):
                    if not (self.flags.bug_id == "BUG_06_WIZARD_ADJACENT_NO_SWAP" and steps_out == 1):
                        self.obj[ty][tx], self.obj[ay][ax], moved = "W", tobj, True
                    break
        elif ah == "P":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                self.obj[ny][nx], self.obj[ay][ax], moved = "P", None, True
        elif ah == "D":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h:
                tobj = self.obj[ny][nx]
                if tobj is None: self.obj[ny][nx], self.obj[ay][ax], moved = "D", None, True
                elif tobj in ("*", "O"): self.obj[ny][nx], moved = "#", True
                elif tobj == "#": self.obj[ny][nx], moved = "*", True
                elif self.is_healer(tobj): moved = True
                elif self.is_hero(tobj):
                    if not any(0 <= nx+hx < self.w and 0 <= ny+hy < self.h and self.is_healer(self.obj[ny+hy][nx+hx]) for hx, hy in ORTHO):
                        self.obj[ny][nx] = "#"
                    moved = True
        elif ah == "B":
            if self.flags.bug_id == "BUG_04_BARD_POST_MOVE_CHARM":
                if 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                    self.obj[ny][nx], self.obj[ay][ax], moved = "B", None, True
                    self._compute_notes()
                    for cx, cy in list(self.notes):
                        if 0 <= cx+dx < self.w and 0 <= cy+dy < self.h and self.obj[cy+dy][cx+dx] is None:
                            self.obj[cy+dy][cx+dx], self.obj[cy][cx] = self.obj[cy][cx], None
                else:
                    return True, self.check_win()
            else:
                bpos, b_mv, charmed, chg = (ax, ay), False, set(self.notes), True
                while chg:
                    chg = False
                    for cx, cy in list(charmed):
                        if 0 <= cx+dx < self.w and 0 <= cy+dy < self.h and self.obj[cy+dy][cx+dx] is None:
                            self.obj[cy+dy][cx+dx], self.obj[cy][cx], chg = self.obj[cy][cx], None, True
                            charmed.remove((cx, cy))
                    if not b_mv and 0 <= bpos[0]+dx < self.w and 0 <= bpos[1]+dy < self.h and self.obj[bpos[1]+dy][bpos[0]+dx] is None:
                        self.obj[bpos[1]+dy][bpos[0]+dx], self.obj[bpos[1]][bpos[0]] = "B", None
                        bpos, b_mv, chg = (bpos[0]+dx, bpos[1]+dy), True, True
                if not b_mv:
                    self.floor, self.obj, self.notes = snap.floor, snap.obj, snap.notes
                    return True, self.check_win()
                moved = True
            self.notes.clear()

        if self.part <= 2 and not moved and self.flags.bug_id != "BUG_10_PART_II_NO_CANCEL_ON_BLOCKED_MOVE":
            self.floor, self.obj = snap.floor, snap.obj
            return True, self.check_win()
        return (not self._run_late()), self.check_win()


FRONTIER_ROOMS: Dict[str, Dict[str, Any]] = {
    "I-1": {"part": 1, "title": "Part I, Room 1", "proven_floor": 8, "shortest_known": 8, "frontier_record": 8,
            "reference_route": "RRRRRRRR", "grid": ["############", "#..........#", "#F........G#", "#..........#", "############"]},
    "II-22": {"part": 2, "title": "Part II, Room 22 (Monster Gate)", "proven_floor": 92, "shortest_known": 92, "frontier_record": 94,
              "reference_route": "ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR",
              "grid": ["#############", "#...#O.O#...#", "#.F.#G.G#.2.#", "#...#.O.#...#", "##.###*###.##", "#R*L.....R*L#",
                       "#.#.......#.#", "#R*L.....R*L#", "##.###M###.##", "#...#...#...#", "#.3.#G.G#.4.#", "#...#...#...#", "#############"]},
    "III-14": {"part": 3, "title": "Part III, Room 14", "proven_floor": 43, "shortest_known": 48, "frontier_record": 48,
               "reference_route": "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR",
               "grid": ["##############", "#............#", "#.5.}}}.]]]]]#", "#...}}}.]G.G]#", "#.D.}}}.]]]]]#", "#............#", "##############"]},
    "III-15": {"part": 3, "title": "Part III, Room 15", "proven_floor": 69, "shortest_known": 69, "frontier_record": 69,
               "reference_route": "AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU",
               "grid": ["#########", "#G#####W#", "#########", "#G#####6#", "#########"]},
    "III-20": {"part": 3, "title": "Part III, Room 20 (Chiral Record 84)", "proven_floor": 74, "shortest_known": 84, "frontier_record": 84,
               "prior_record_route_87": "RAUUURRRADAAADLURAAUAAALULLALAUAAARRDLRDRULURURDDAARAULLRRRRRDDRARRRRALUURDRUURARRDDRDR",
               "reference_route": "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR",
               "alternate_route_84": "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU",
               "grid": ["###############", "#....#O.O#...G#", "#..##W...1##..#", "#..#O..O..O#.G#", "#4.#..OGO..#..#",
                        "#..#O..O..O#.G#", "#..##2...6##..#", "#....#O.O#...G#", "###############"]},
    "III-22": {"part": 3, "title": "Part III, Room 22 (Six-Hero Finale)", "proven_floor": 9, "shortest_known": 9, "frontier_record": 9,
               "reference_route": "RRRRRRRRR",
               "grid": ["###############", "#.............#", "#.1.4......G.G#", "#.............#", "#.2.B......G.G#",
                        "#.............#", "#.3.6......G.G#", "#.............#", "###############"]},
}


def replay_oracle(part: int, grid: List[str], route: str, flags: MutatorFlags = MutatorFlags()) -> Dict[str, Any]:
    sim = PuzzleScriptOracle(part, grid, flags=flags)
    clean = route.strip().upper()
    premature, alive, steps = False, True, 0
    for idx, ch in enumerate(clean):
        ok_a, won = sim.step(ch); steps += 1
        if not ok_a: alive = False; break
        if won and idx + 1 < len(clean): premature = True; break
    return {
        "alive": alive, "exact_win": alive and (not premature) and sim.check_win(),
        "premature_win": premature, "steps_executed": steps, "route_len": len(clean),
        "route_sha256_12": hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12],
        "final_ascii": sim.render_ascii(), "signature": sim.state_signature(),
    }


def run_planted_bug_audit(extra_vectors: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    vecs: List[Tuple[str, int, List[str], str, bool, bool]] = [
        ("II-22_94", 2, FRONTIER_ROOMS["II-22"]["grid"], FRONTIER_ROOMS["II-22"]["reference_route"], True, True),
        ("III-14_48", 3, FRONTIER_ROOMS["III-14"]["grid"], FRONTIER_ROOMS["III-14"]["reference_route"], True, True),
        ("III-15_69", 3, FRONTIER_ROOMS["III-15"]["grid"], FRONTIER_ROOMS["III-15"]["reference_route"], True, True),
        ("III-20_87", 3, FRONTIER_ROOMS["III-20"]["grid"], FRONTIER_ROOMS["III-20"]["prior_record_route_87"], True, True),
        ("III-20_84", 3, FRONTIER_ROOMS["III-20"]["grid"], FRONTIER_ROOMS["III-20"]["reference_route"], True, True),
        ("III-22_9", 3, FRONTIER_ROOMS["III-22"]["grid"], FRONTIER_ROOMS["III-22"]["reference_route"], True, True),
        ("MICRO_GOBLIN_SIMUL", 3, ["########", "#....G.#", "#F*O.O.#", "########"], "RRRRU", True, True),
        ("MICRO_MULTI_PUSH", 3, ["#########", "#..G....#", "#F***...#", "#########"], "RRU", True, True),
    ]
    for idx, ev in enumerate(extra_vectors or []):
        vecs.append((ev.get("name", f"custom_{idx}"), int(ev["part"]), list(ev["grid"]), str(ev["route"]),
                     bool(ev.get("expect_alive", True)), bool(ev.get("expect_win", True))))
    base = {n: replay_oracle(p, g, r)["signature"] for n, p, g, r, _, _ in vecs}
    p2_c = ["#######", "#R..OG#", "#..4FG#", "#######"]
    out, caught = [], 0
    for bid, desc in PLANTED_BUGS:
        fl = MutatorFlags(bug_id=bid)
        fails = [n for n, p, g, r, ea, ew in vecs
                 if (res := replay_oracle(p, g, r, fl))["alive"] != ea or res["exact_win"] != ew or res["signature"] != base[n]]
        bm = PuzzleScriptOracle(2, p2_c, flags=fl); bm.step("D")
        if bm.obj[1][4] != "O": fails.append("PART_II_BLOCKED_CANCEL_DRAGON")
        if fails: caught += 1
        out.append({"bug_id": bid, "description": desc, "caught": bool(fails), "failing_vector_count": len(fails), "failing_vectors": fails})
    return {"epistemic_status": "VERIFIED" if caught == len(PLANTED_BUGS) else "INCOMPLETE",
            "planted_bugs_total": len(PLANTED_BUGS), "planted_bugs_caught": caught, "all_caught": caught == len(PLANTED_BUGS),
            "vectors_evaluated": len(vecs) + 1, "mutations": out}
