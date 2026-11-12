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
    "1": "Fighter (pushes chains of Moveables)",
    "2": "Thief (pulls 1 Moveable behind)",
    "3": "Wizard (teleports/swaps with line-of-sight Moveable)",
    "4": "Priest (immune Healer; shields orthogonal heroes)",
    "5": "Bard (5x5 Chebyshev Note aura rigid translation)",
    "6": "Druid (transmutes Wall <-> Crate and Moveable -> Wall)",
}

_CANON_OBJ_CODE: Dict[Optional[str], int] = {
    None: 0,
    "F": 1,
    "T": 2,
    "W": 3,
    "P": 4,
    "B": 5,
    "D": 6,
    "1": 7,
    "2": 8,
    "3": 9,
    "4": 10,
    "5": 11,
    "6": 12,
    "#": 13,
    "*": 14,
    "O": 15,
    "L": 16,
    "R": 17,
    "[": 18,
    "]": 19,
    "M": 20,
}

CYCLE_ORDER_STD = ["1", "2", "3", "4", "5", "6"]
CYCLE_ORDER_BUG09 = ["1", "3", "2", "4", "5", "6"]

DIRS: Dict[str, Tuple[int, int]] = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}

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
        if part not in (1, 2, 3):
            raise ValueError(f"part must be 1, 2, or 3 (got {part!r})")
        if not rows or not rows[0]:
            raise ValueError("rows must be a non-empty rectangular ASCII grid")
        self.part = part
        self.flags = flags
        self.h = len(rows)
        self.w = len(rows[0])
        if any(len(r) != self.w for r in rows):
            raise ValueError("All grid rows must have identical width")

        self.floor: List[List[Optional[str]]] = [[None] * self.w for _ in range(self.h)]
        self.obj: List[List[Optional[str]]] = [[None] * self.w for _ in range(self.h)]
        self.notes: Set[Tuple[int, int]] = set()
        self.has_ydoors_init = False
        self.has_pdoors_init = False

        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == ".":
                    continue
                elif ch in ("G", "{", "}"):
                    self.floor[y][x] = ch
                elif ch in ("#", "*", "O", "L", "R", "[", "]", "M") or ch in ACTIVE_HEROES or ch in INACTIVE_HEROES:
                    self.obj[y][x] = ch
                    if ch == "[":
                        self.has_ydoors_init = True
                    elif ch == "]":
                        self.has_pdoors_init = True
                else:
                    raise ValueError(f"Unrecognized level symbol {ch!r} at ({x}, {y})")

        if self.part == 3:
            self._run_late()

    def clone(self) -> "PuzzleScriptOracle":
        cp = PuzzleScriptOracle.__new__(PuzzleScriptOracle)
        cp.part = self.part
        cp.flags = self.flags
        cp.h, cp.w = self.h, self.w
        cp.floor = [r[:] for r in self.floor]
        cp.obj = [r[:] for r in self.obj]
        cp.notes = set(self.notes)
        cp.has_ydoors_init = self.has_ydoors_init
        cp.has_pdoors_init = self.has_pdoors_init
        return cp

    def render_ascii(self) -> str:
        lines: List[str] = []
        for y in range(self.h):
            line = []
            for x in range(self.w):
                o = self.obj[y][x]
                f = self.floor[y][x]
                if o is not None:
                    line.append("X" if o == "CORPSE" else o)
                elif f in ("G", "{", "}"):
                    line.append(f)
                else:
                    line.append(".")
            lines.append("".join(line))
        return "\n".join(lines)

    def fold_canonical_digest(self, acc: int) -> int:
        """Fold exact full-state frame (objects + Note aura + open-door layers) into 64-bit FNV-1a digest."""
        prime = 1099511628211
        mask64 = 0xFFFFFFFFFFFFFFFF
        h = acc
        y_open_eff = 0
        p_open_eff = 0
        for y in range(self.h):
            for x in range(self.w):
                f = self.floor[y][x]
                if f == "YO":
                    y_open_eff = 1
                elif f == "PO":
                    p_open_eff = 1
                code = _CANON_OBJ_CODE.get(self.obj[y][x], 31)
                nbit = 1 if (x, y) in self.notes else 0
                bval = (code & 0x1F) | (nbit << 5)
                h = ((h ^ bval) * prime) & mask64
        door_flags = (y_open_eff & 1) | ((p_open_eff & 1) << 1)
        h = ((h ^ door_flags) * prime) & mask64
        h = ((h ^ 0xFF) * prime) & mask64
        return h

    def state_signature(self) -> Tuple:
        return (
            tuple(tuple(r) for r in self.obj),
            tuple(tuple(r) for r in self.floor),
            frozenset(self.notes),
        )

    def find_active(self) -> Optional[Tuple[int, int, str]]:
        for y in range(self.h):
            for x in range(self.w):
                o = self.obj[y][x]
                if o in ACTIVE_HEROES:
                    return (x, y, o)
        return None

    def is_hero(self, o: Optional[str]) -> bool:
        return (o in ACTIVE_HEROES) or (o in INACTIVE_HEROES)

    def is_healer(self, o: Optional[str]) -> bool:
        if self.part == 1:
            return False
        if self.flags.bug_id == "BUG_07_PRIEST_INACTIVE_NO_HEAL":
            return o == "P"
        return o in ("P", "4")

    def is_monster(self, o: Optional[str]) -> bool:
        if self.part == 1:
            return False
        return o in ("O", "L", "R") if self.part == 2 else (o == "O")

    def is_moveable(self, o: Optional[str]) -> bool:
        return o == "*" or (o in INACTIVE_HEROES) or self.is_monster(o)

    def is_static(self, o: Optional[str]) -> bool:
        return o in ("#", "[", "]", "M")

    def is_vulnerable(self, o: Optional[str]) -> bool:
        return self.is_hero(o) or self.is_monster(o)

    def is_weighing(self, o: Optional[str]) -> bool:
        if self.part in (1, 2) or self.flags.bug_id == "BUG_05_WALL_NOT_WEIGHING_PART_III":
            return o == "*" or self.is_hero(o) or self.is_monster(o)
        return o == "*" or o == "#" or self.is_hero(o) or self.is_monster(o)

    def _compute_notes(self) -> None:
        self.notes.clear()
        if self.part != 3:
            return
        act = self.find_active()
        if act is None or act[2] != "B":
            return
        bx, by, _ = act
        for ny in range(max(0, by - 2), min(self.h, by + 3)):
            for nx in range(max(0, bx - 2), min(self.w, bx + 3)):
                if (nx, ny) == (bx, by):
                    continue
                if self.flags.bug_id == "BUG_03_BARD_MANHATTAN_RADIUS":
                    if abs(nx - bx) + abs(ny - by) > 2:
                        continue
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
                    if o == "R":
                        for nx in range(x + 1, self.w):
                            no = self.obj[y][nx]
                            if no is None:
                                continue
                            if self.is_vulnerable(no):
                                dying.add((nx, y))
                            break
                    elif o == "L":
                        for nx in range(x - 1, -1, -1):
                            no = self.obj[y][nx]
                            if no is None:
                                continue
                            if self.is_vulnerable(no):
                                dying.add((nx, y))
                            break

        corpse = False
        if self.part >= 2:
            if self.flags.bug_id == "BUG_08_GOBLIN_SEQUENTIAL_KILL":
                for y in range(self.h):
                    for x in range(self.w):
                        if self.obj[y][x] == "O":
                            for ddx, ddy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                                nx, ny = x + ddx, y + ddy
                                if 0 <= nx < self.w and 0 <= ny < self.h:
                                    vo = self.obj[ny][nx]
                                    if vo == "O":
                                        self.obj[ny][nx] = None
                                    elif self.is_hero(vo) and not self.is_healer(vo):
                                        adj_h = any(
                                            0 <= nx + hx < self.w
                                            and 0 <= ny + hy < self.h
                                            and self.is_healer(self.obj[ny + hy][nx + hx])
                                            for hx, hy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                                        )
                                        if not adj_h:
                                            self.obj[ny][nx] = "CORPSE"
                                            corpse = True
            else:
                for y in range(self.h):
                    for x in range(self.w):
                        if self.obj[y][x] == "O":
                            for ddx, ddy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                                nx, ny = x + ddx, y + ddy
                                if 0 <= nx < self.w and 0 <= ny < self.h and self.is_vulnerable(self.obj[ny][nx]):
                                    dying.add((nx, ny))

                for x, y in list(dying):
                    if self.is_healer(self.obj[y][x]):
                        dying.remove((x, y))
                for y in range(self.h):
                    for x in range(self.w):
                        if self.is_healer(self.obj[y][x]):
                            for ddx, ddy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                                nx, ny = x + ddx, y + ddy
                                if (nx, ny) in dying and self.is_hero(self.obj[ny][nx]):
                                    dying.remove((nx, ny))

                for x, y in dying:
                    if self.is_monster(self.obj[y][x]):
                        self.obj[y][x] = None
                    elif self.is_hero(self.obj[y][x]):
                        self.obj[y][x] = "CORPSE"
                        corpse = True

        for sw_ch, door_ch, open_ch in (("{", "[", "YO"), ("}", "]", "PO")):
            sw = [(x, y) for y in range(self.h) for x in range(self.w) if self.floor[y][x] == sw_ch]
            if sw:
                any_w = any(self.is_weighing(self.obj[y][x]) for x, y in sw)
                any_u = any(not self.is_weighing(self.obj[y][x]) for x, y in sw)
                if any_w and not any_u:
                    for y in range(self.h):
                        for x in range(self.w):
                            if self.obj[y][x] == door_ch:
                                self.obj[y][x] = None
                                self.floor[y][x] = open_ch
                elif any_u:
                    for y in range(self.h):
                        for x in range(self.w):
                            if self.floor[y][x] == open_ch:
                                if self.is_hero(self.obj[y][x]):
                                    corpse = True
                                self.floor[y][x] = None
                                self.obj[y][x] = door_ch

        if self.part >= 2 and not any(self.is_monster(self.obj[y][x]) for y in range(self.h) for x in range(self.w)):
            for y in range(self.h):
                for x in range(self.w):
                    if self.obj[y][x] == "M":
                        self.obj[y][x] = None

        if self.part == 3:
            self.notes = {(x, y) for (x, y) in self.notes if self.is_moveable(self.obj[y][x])}
        return corpse

    def check_win(self) -> bool:
        for y in range(self.h):
            for x in range(self.w):
                if self.is_hero(self.obj[y][x]) != (self.floor[y][x] == "G"):
                    return False
        return True

    def step(self, key: str) -> Tuple[bool, bool]:
        if key not in ("U", "D", "L", "R", "A"):
            raise ValueError(f"Invalid key {key!r}; expected U, D, L, R, or A")
        act = self.find_active()
        if act is None:
            return False, False
        ax, ay, ah = act
        snap = self.clone()

        if key == "A":
            self.notes.clear()
            order = CYCLE_ORDER_BUG09 if self.flags.bug_id == "BUG_09_HERO_CYCLE_SWIZARD_STHIEF_ORDER" else CYCLE_ORDER_STD
            max_h = 3 if self.part == 1 else (4 if self.part == 2 else 6)
            sub_order = order[:max_h]
            cur_inact = TO_INACTIVE[ah]
            cur_pos = sub_order.index(cur_inact)
            switched = False
            for offset in range(1, max_h):
                target_inact = sub_order[(cur_pos + offset) % max_h]
                found = None
                for x in range(self.w):
                    for y in range(self.h):
                        if self.obj[y][x] == target_inact:
                            found = (x, y)
                            break
                    if found:
                        break
                if found:
                    fx, fy = found
                    self.obj[ay][ax] = cur_inact
                    self.obj[fy][fx] = TO_ACTIVE[target_inact]
                    switched = True
                    break
            if not switched and self.part <= 2 and self.flags.bug_id != "BUG_10_PART_II_NO_CANCEL_ON_BLOCKED_MOVE":
                return True, self.check_win()
            corpse = self._run_late()
            return (not corpse), self.check_win()

        dx, dy = DIRS[key]
        nx, ny = ax + dx, ay + dy
        moved = False

        if ah == "F":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h:
                if self.flags.bug_id in ("BUG_01_IMABAYASHI_SINGLE_PUSH", "BUG_02_FIGHTER_RULE_ORDER_SWAP"):
                    if self.obj[ny][nx] is None:
                        self.obj[ny][nx] = "F"
                        self.obj[ay][ax] = None
                        moved = True
                    elif self.is_moveable(self.obj[ny][nx]):
                        nnx, nny = nx + dx, ny + dy
                        if 0 <= nnx < self.w and 0 <= nny < self.h and self.obj[nny][nnx] is None:
                            self.obj[nny][nnx] = self.obj[ny][nx]
                            self.obj[ny][nx] = "F"
                            self.obj[ay][ax] = None
                            moved = True
                else:
                    cx, cy = nx, ny
                    while 0 <= cx < self.w and 0 <= cy < self.h and self.is_moveable(self.obj[cy][cx]):
                        cx += dx
                        cy += dy
                    if 0 <= cx < self.w and 0 <= cy < self.h and self.obj[cy][cx] is None:
                        while (cx, cy) != (ax, ay):
                            px, py = cx - dx, cy - dy
                            self.obj[cy][cx] = self.obj[py][px]
                            cx, cy = px, py
                        self.obj[ay][ax] = None
                        moved = True

        elif ah == "T":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                bx, by = ax - dx, ay - dy
                self.obj[ny][nx] = "T"
                if 0 <= bx < self.w and 0 <= by < self.h and self.is_moveable(self.obj[by][bx]):
                    self.obj[ay][ax] = self.obj[by][bx]
                    self.obj[by][bx] = None
                else:
                    self.obj[ay][ax] = None
                moved = True

        elif ah == "W":
            self.notes.clear()
            wx, wy = ax, ay
            steps_out = 0
            while True:
                tx, ty = wx + dx, wy + dy
                steps_out += 1
                if not (0 <= tx < self.w and 0 <= ty < self.h):
                    if self.part == 3 and 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                        self.obj[ny][nx] = "W"
                        self.obj[ay][ax] = None
                        moved = True
                    break
                tobj = self.obj[ty][tx]
                if tobj is None:
                    wx, wy = tx, ty
                elif self.is_static(tobj):
                    if self.obj[ny][nx] is None:
                        self.obj[ny][nx] = "W"
                        self.obj[ay][ax] = None
                        moved = True
                    break
                elif self.is_moveable(tobj):
                    if self.flags.bug_id == "BUG_06_WIZARD_ADJACENT_NO_SWAP" and steps_out == 1:
                        break
                    self.obj[ty][tx] = "W"
                    self.obj[ay][ax] = tobj
                    moved = True
                    break

        elif ah == "P":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                self.obj[ny][nx] = "P"
                self.obj[ay][ax] = None
                moved = True

        elif ah == "D":
            self.notes.clear()
            if 0 <= nx < self.w and 0 <= ny < self.h:
                tobj = self.obj[ny][nx]
                if tobj is None:
                    self.obj[ny][nx] = "D"
                    self.obj[ay][ax] = None
                    moved = True
                elif tobj in ("*", "O"):
                    self.obj[ny][nx] = "#"
                    moved = True
                elif tobj == "#":
                    self.obj[ny][nx] = "*"
                    moved = True
                elif self.is_healer(tobj):
                    moved = True
                elif self.is_hero(tobj):
                    adj_h = any(
                        0 <= nx + hx < self.w and 0 <= ny + hy < self.h and self.is_healer(self.obj[ny + hy][nx + hx])
                        for hx, hy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                    )
                    if not adj_h:
                        self.obj[ny][nx] = "#"
                    moved = True

        elif ah == "B":
            if self.flags.bug_id == "BUG_04_BARD_POST_MOVE_CHARM":
                if 0 <= nx < self.w and 0 <= ny < self.h and self.obj[ny][nx] is None:
                    self.obj[ny][nx] = "B"
                    self.obj[ay][ax] = None
                    self._compute_notes()
                    for cx, cy in list(self.notes):
                        tx, ty = cx + dx, cy + dy
                        if 0 <= tx < self.w and 0 <= ty < self.h and self.obj[ty][tx] is None:
                            self.obj[ty][tx] = self.obj[cy][cx]
                            self.obj[cy][cx] = None
                    moved = True
                else:
                    return True, self.check_win()
            else:
                bard_pos = (ax, ay)
                bard_moved = False
                charmed = set(self.notes)
                changed = True
                while changed:
                    changed = False
                    for cx, cy in list(charmed):
                        tx, ty = cx + dx, cy + dy
                        if 0 <= tx < self.w and 0 <= ty < self.h and self.obj[ty][tx] is None:
                            self.obj[ty][tx] = self.obj[cy][cx]
                            self.obj[cy][cx] = None
                            charmed.remove((cx, cy))
                            changed = True
                    if not bard_moved:
                        tx, ty = bard_pos[0] + dx, bard_pos[1] + dy
                        if 0 <= tx < self.w and 0 <= ty < self.h and self.obj[ty][tx] is None:
                            self.obj[ty][tx] = "B"
                            self.obj[bard_pos[1]][bard_pos[0]] = None
                            bard_pos = (tx, ty)
                            bard_moved = True
                            changed = True
                if not bard_moved:
                    self.floor, self.obj, self.notes = snap.floor, snap.obj, snap.notes
                    return True, self.check_win()
                moved = True
            self.notes.clear()

        if self.part <= 2 and not moved and self.flags.bug_id != "BUG_10_PART_II_NO_CANCEL_ON_BLOCKED_MOVE":
            self.floor, self.obj = snap.floor, snap.obj
            return True, self.check_win()

        corpse = self._run_late()
        return (not corpse), self.check_win()


FRONTIER_ROOMS: Dict[str, Dict[str, Any]] = {
    "I-1": {
        "part": 1,
        "title": "Part I, Room 1 (Opening Hall)",
        "proven_floor": 9,
        "shortest_known": 9,
        "frontier_record": 9,
        "reference_route": "RRRRRRRRRR",
        "grid": [
            "############",
            "#..........#",
            "#F........G#",
            "#..........#",
            "############",
        ],
    },
    "II-22": {
        "part": 2,
        "title": "Part II, Room 22 (Monster Gate Finale)",
        "proven_floor": 92,
        "shortest_known": 92,
        "frontier_record": 94,
        "reference_route": "ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR",
        "grid": [
            "#############",
            "#...#O.O#...#",
            "#.F.#G.G#.2.#",
            "#...#.O.#...#",
            "##.###*###.##",
            "#R*L.....R*L#",
            "#.#.......#.#",
            "#R*L.....R*L#",
            "##.###M###.##",
            "#...#...#...#",
            "#.3.#G.G#.4.#",
            "#...#...#...#",
            "#############",
        ],
    },
    "III-14": {
        "part": 3,
        "title": "Part III, Room 14 (Bard, Druid, and Nine Purple Switches - 14x7)",
        "proven_floor": 43,
        "shortest_known": 48,
        "frontier_record": 48,
        "reference_route": "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR",
        "grid": [
            "##############",
            "#............#",
            "#.5.}}}.]]]]]#",
            "#...}}}.]G.G]#",
            "#.D.}}}.]]]]]#",
            "#............#",
            "##############",
        ],
    },
    "III-14-15x7": {
        "part": 3,
        "title": "Part III, Room 14 (Verbatim 15x7 PuzzleScript Editor Variant)",
        "proven_floor": 43,
        "shortest_known": 48,
        "frontier_record": 48,
        "reference_route": "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR",
        "grid": [
            "###############",
            "#.............#",
            "#.5.}}}.]]]]].#",
            "#...}}}.]G.G].#",
            "#.D.}}}.]]]]].#",
            "#.............#",
            "###############",
        ],
    },
    "III-15": {
        "part": 3,
        "title": "Part III, Room 15 (Wizard and Druid Tunnel)",
        "proven_floor": 69,
        "shortest_known": 69,
        "frontier_record": 69,
        "reference_route": "AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU",
        "grid": [
            "#########",
            "#G#####W#",
            "#########",
            "#G#####6#",
            "#########",
        ],
    },
    "III-20": {
        "part": 3,
        "title": "Part III, Room 20 (Goblin Corridor - Chiral Record 84)",
        "proven_floor": 74,
        "shortest_known": 84,
        "frontier_record": 84,
        "prior_record_route_87": "RAUUURRRADAAADLURAAUAAALULLALAUAAARRDLRDRULURURDDAARAULLRRRRRDDRARRRRALUURDRUURARRDDRDR",
        "reference_route": "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR",
        "alternate_route_84": "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU",
        "grid": [
            "###############",
            "#....#O.O#...G#",
            "#..##W...1##..#",
            "#..#O..O..O#.G#",
            "#4.#..OGO..#..#",
            "#..#O..O..O#.G#",
            "#..##2...6##..#",
            "#....#O.O#...G#",
            "###############",
        ],
    },
    "III-22": {
        "part": 3,
        "title": "Part III, Room 22 (Six-Hero Finale)",
        "proven_floor": 9,
        "shortest_known": 9,
        "frontier_record": 9,
        "reference_route": "RRRRRRRRR",
        "grid": [
            "###############",
            "#.............#",
            "#.1.4......G.G#",
            "#.............#",
            "#.2.B......G.G#",
            "#.............#",
            "#.3.6......G.G#",
            "#.............#",
            "###############",
        ],
    },
}


def replay_oracle(part: int, grid: List[str], route: str, flags: MutatorFlags = MutatorFlags()) -> Dict[str, Any]:
    sim = PuzzleScriptOracle(part, grid, flags=flags)
    clean_route = route.strip().upper()
    digest = sim.fold_canonical_digest(14695981039346656037)
    premature_win = False
    alive = True
    steps_executed = 0
    for idx, ch in enumerate(clean_route):
        ok_alive, won = sim.step(ch)
        steps_executed += 1
        if not ok_alive:
            alive = False
            break
        digest = sim.fold_canonical_digest(digest)
        if won and idx + 1 < len(clean_route):
            premature_win = True
            break
    exact_win = alive and (not premature_win) and sim.check_win()
    return {
        "alive": alive,
        "exact_win": exact_win,
        "premature_win": premature_win,
        "steps_executed": steps_executed,
        "route_len": len(clean_route),
        "route_sha256_12": hashlib.sha256(clean_route.encode("utf-8")).hexdigest()[:12],
        "traj_fnv64": f"{digest:016x}",
        "final_ascii": sim.render_ascii(),
        "signature": sim.state_signature(),
    }


def run_planted_bug_audit(extra_vectors: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Run the 10-mutation Proven-Commons Planted-Bug Suite AND cross-engine parity check against FlatBitmaskOracle."""
    from .flat_oracle import replay_flat_oracle

    vectors: List[Tuple[str, int, List[str], str, bool, bool]] = [("I-1_9", 1, FRONTIER_ROOMS["I-1"]["grid"], FRONTIER_ROOMS["I-1"]["reference_route"], True, True),
                                                                  
        ("II-22_94", 2, FRONTIER_ROOMS["II-22"]["grid"], FRONTIER_ROOMS["II-22"]["reference_route"], True, True),
        ("III-14_48", 3, FRONTIER_ROOMS["III-14"]["grid"], FRONTIER_ROOMS["III-14"]["reference_route"], True, True),
        ("III-14_15x7_48", 3, FRONTIER_ROOMS["III-14-15x7"]["grid"], FRONTIER_ROOMS["III-14-15x7"]["reference_route"], True, True),
        ("III-15_69", 3, FRONTIER_ROOMS["III-15"]["grid"], FRONTIER_ROOMS["III-15"]["reference_route"], True, True),
        ("III-20_87", 3, FRONTIER_ROOMS["III-20"]["grid"], FRONTIER_ROOMS["III-20"]["prior_record_route_87"], True, True),
        ("III-20_84", 3, FRONTIER_ROOMS["III-20"]["grid"], FRONTIER_ROOMS["III-20"]["reference_route"], True, True),
        ("III-20_84_ALT", 3, FRONTIER_ROOMS["III-20"]["grid"], FRONTIER_ROOMS["III-20"]["alternate_route_84"], True, True),
        ("III-22_9", 3, FRONTIER_ROOMS["III-22"]["grid"], FRONTIER_ROOMS["III-22"]["reference_route"], True, True),
        ("MICRO_GOBLIN_SIMUL", 3, ["########", "#....G.#", "#F*O.O.#", "########"], "RRRRU", True, True),
        ("MICRO_MULTI_PUSH", 3, ["#########", "#..G....#", "#F***...#", "#########"], "RRU", True, True),
    ]
    for idx, ev in enumerate(extra_vectors or []):
        vectors.append((
            ev.get("name", f"custom_{idx}"),
            int(ev["part"]),
            list(ev["grid"]),
            str(ev["route"]),
            bool(ev.get("expect_alive", True)),
            bool(ev.get("expect_win", True)),
        ))

    baseline: Dict[str, Tuple] = {}
    cross_engine_mismatches: List[str] = []
    for name, part, grid, route, exp_alive, exp_win in vectors:
        res = replay_oracle(part, grid, route)
        flat_res = replay_flat_oracle(part, grid, route)
        if res["alive"] != exp_alive or res["exact_win"] != exp_win:
            return {
                "epistemic_status": "FAILED_BASELINE",
                "failed_vector": name,
                "detail": {k: v for k, v in res.items() if k != "signature"},
            }
        if (
            flat_res["alive"] != res["alive"]
            or flat_res["exact_win"] != res["exact_win"]
            or flat_res["premature_win"] != res["premature_win"]
            or flat_res["traj_fnv64"] != res["traj_fnv64"]
            or flat_res["final_ascii"] != res["final_ascii"]
        ):
            cross_engine_mismatches.append(name)
        baseline[name] = (res["signature"], flat_res["traj_fnv64"])

    if cross_engine_mismatches:
        return {
            "epistemic_status": "FAILED_CROSS_ORACLE_PARITY",
            "cross_engine_mismatches": cross_engine_mismatches,
        }

    p2_cancel_dragon = ["#######", "#R..OG#", "#..4FG#", "#######"]
    b_clean = PuzzleScriptOracle(2, p2_cancel_dragon)
    b_clean.step("D")
    assert b_clean.obj[1][4] == "O"

    results = []
    caught_count = 0
    for bug_id, desc in PLANTED_BUGS:
        flags = MutatorFlags(bug_id=bug_id)
        failing_vectors: List[str] = []
        for name, part, grid, route, exp_alive, exp_win in vectors:
            r = replay_oracle(part, grid, route, flags=flags)
            sig_ref, traj_ref = baseline[name]
            if r["alive"] != exp_alive or r["exact_win"] != exp_win or r["signature"] != sig_ref or r["traj_fnv64"] != traj_ref:
                failing_vectors.append(name)
        b_mut = PuzzleScriptOracle(2, p2_cancel_dragon, flags=flags)
        b_mut.step("D")
        if b_mut.obj[1][4] != "O":
            failing_vectors.append("PART_II_BLOCKED_CANCEL_DRAGON")
        caught = len(failing_vectors) > 0
        if caught:
            caught_count += 1
        results.append({
            "bug_id": bug_id,
            "description": desc,
            "caught": caught,
            "failing_vector_count": len(failing_vectors),
            "failing_vectors": failing_vectors,
        })

    all_ok = (caught_count == len(PLANTED_BUGS)) and (len(cross_engine_mismatches) == 0)
    return {
        "epistemic_status": "VERIFIED" if all_ok else "INCOMPLETE",
        "planted_bugs_total": len(PLANTED_BUGS),
        "planted_bugs_caught": caught_count,
        "all_caught": all_ok,
        "cross_oracle_parity_vectors": len(vectors),
        "cross_oracle_mismatches": 0,
        "vectors_evaluated": len(vectors) + 1,
        "mutations": results,
    }
