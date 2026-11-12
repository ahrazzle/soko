"""Independent zero-shared-code flat 1D bitmask oracle for Heroes of Sokoban Parts I, II, & III.

Engineered to satisfy Foundation-0 dual-checker independence (zero imports from `soko_mcp.oracle`):
- Represents static topology and dynamic state via 1D integer cell arrays and Python big-int bitmasks.
- Resolves Bard aura, Goblin/Dragon combat, Priest shielding, and switch/door triggers via bitmask algebra
  rather than 2D string grids or OOP object cloning.
- Produces the identical 64-bit FNV-1a per-frame canonical trajectory digest (`traj_fnv64`) across every
  step `t = 0..L` so `verify_route_dual` enforces fail-closed multi-oracle agreement even without a C++20 compiler.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

# Canonical cell object integer codes (0..20), matching C++20 `DynState` byte encoding
_EMPTY = 0
_ACT_F, _ACT_T, _ACT_W, _ACT_P, _ACT_B, _ACT_D = 1, 2, 3, 4, 5, 6
_INA_1, _INA_2, _INA_3, _INA_4, _INA_5, _INA_6 = 7, 8, 9, 10, 11, 12
_WALL = 13
_CRATE = 14
_GOBLIN = 15
_DRAG_L = 16
_DRAG_R = 17
_YDOOR = 18
_PDOOR = 19
_MGATE = 20

_CHAR_TO_OBJ: Dict[str, int] = {
    "F": _ACT_F,
    "T": _ACT_T,
    "W": _ACT_W,
    "P": _ACT_P,
    "B": _ACT_B,
    "D": _ACT_D,
    "1": _INA_1,
    "2": _INA_2,
    "3": _INA_3,
    "4": _INA_4,
    "5": _INA_5,
    "6": _INA_6,
    "#": _WALL,
    "*": _CRATE,
    "O": _GOBLIN,
    "L": _DRAG_L,
    "R": _DRAG_R,
    "[": _YDOOR,
    "]": _PDOOR,
    "M": _MGATE,
}

_OBJ_TO_CHAR: Dict[int, str] = {v: k for k, v in _CHAR_TO_OBJ.items()}

_STEP_DELTAS: Dict[str, Tuple[int, int]] = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}

_FNV64_OFFSET = 14695981039346656037
_FNV64_PRIME = 1099511628211
_MASK64 = 0xFFFFFFFFFFFFFFFF


def _fnv64_fold_frame(
    acc: int,
    cells: List[int],
    notes_mask: int,
    y_open_eff: int,
    p_open_eff: int,
) -> int:
    h = acc
    for idx, code in enumerate(cells):
        nbit = (notes_mask >> idx) & 1
        bval = (code & 0x1F) | (nbit << 5)
        h = ((h ^ bval) * _FNV64_PRIME) & _MASK64
    door_flags = (y_open_eff & 1) | ((p_open_eff & 1) << 1)
    h = ((h ^ door_flags) * _FNV64_PRIME) & _MASK64
    h = ((h ^ 0xFF) * _FNV64_PRIME) & _MASK64
    return h


class FlatBitmaskOracle:
    """Zero-shared-code flat bitmask state machine for Heroes of Sokoban I, II, & III."""

    def __init__(self, part: int, grid_rows: List[str]) -> None:
        if part not in (1, 2, 3):
            raise ValueError(f"Unsupported game part: {part!r}")
        if not grid_rows or not grid_rows[0]:
            raise ValueError("Grid must be non-empty")
        self.part = part
        self.h = len(grid_rows)
        self.w = len(grid_rows[0])
        if any(len(r) != self.w for r in grid_rows):
            raise ValueError("Non-rectangular grid rows")
        self.n = self.w * self.h
        self.max_slot = 3 if part == 1 else (4 if part == 2 else 6)

        self.goals_mask = 0
        self.ysw_mask = 0
        self.psw_mask = 0
        self.ydoor_init_mask = 0
        self.pdoor_init_mask = 0
        self.cells: List[int] = [_EMPTY] * self.n
        self.notes_mask = 0
        self.y_open = 0
        self.p_open = 0

        # Precompute orthogonal neighbor indices and 5x5 Chebyshev masks per cell
        self.orth_neighbors: List[List[int]] = [[] for _ in range(self.n)]
        self.aura5x5_mask: List[int] = [0] * self.n
        for idx in range(self.n):
            cx, cy = idx % self.w, idx // self.w
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.w and 0 <= ny < self.h:
                    self.orth_neighbors[idx].append(ny * self.w + nx)
            amask = 0
            for ay in range(max(0, cy - 2), min(self.h, cy + 3)):
                for ax in range(max(0, cx - 2), min(self.w, cx + 3)):
                    if ax == cx and ay == cy:
                        continue
                    amask |= 1 << (ay * self.w + ax)
            self.aura5x5_mask[idx] = amask

        # Column-major index scan order (x=0..W-1, y=0..H-1) matching PuzzleScript Action switch scan
        self.col_major_indices: List[int] = [
            y * self.w + x for x in range(self.w) for y in range(self.h)
        ]

        for y, row in enumerate(grid_rows):
            for x, ch in enumerate(row):
                idx = y * self.w + x
                bit = 1 << idx
                if ch == ".":
                    continue
                if ch == "G":
                    self.goals_mask |= bit
                elif ch == "{":
                    self.ysw_mask |= bit
                elif ch == "}":
                    self.psw_mask |= bit
                elif ch in _CHAR_TO_OBJ:
                    code = _CHAR_TO_OBJ[ch]
                    self.cells[idx] = code
                    if code == _YDOOR:
                        self.ydoor_init_mask |= bit
                    elif code == _PDOOR:
                        self.pdoor_init_mask |= bit
                else:
                    raise ValueError(f"Unknown tile {ch!r} at ({x}, {y})")

        if self.part == 3:
            self._apply_late_phase()

    def _is_hero_code(self, c: int) -> bool:
        return _ACT_F <= c <= _INA_6

    def _is_monster_code(self, c: int) -> bool:
        if self.part == 1:
            return False
        if self.part == 2:
            return c in (_GOBLIN, _DRAG_L, _DRAG_R)
        return c == _GOBLIN

    def _is_moveable_code(self, c: int) -> bool:
        return c == _CRATE or (_INA_1 <= c <= _INA_6) or self._is_monster_code(c)

    def _is_static_code(self, c: int) -> bool:
        return c in (_WALL, _YDOOR, _PDOOR, _MGATE)

    def _is_weighing_code(self, c: int) -> bool:
        if self.part == 3 and c == _WALL:
            return True
        return c == _CRATE or self._is_hero_code(c) or self._is_monster_code(c)

    def _recompute_notes_mask(self) -> None:
        self.notes_mask = 0
        if self.part != 3:
            return
        bard_idx = -1
        for i, c in enumerate(self.cells):
            if c == _ACT_B:
                bard_idx = i
                break
        if bard_idx < 0:
            return
        cand = self.aura5x5_mask[bard_idx]
        m = 0
        for i in range(self.n):
            if ((cand >> i) & 1) and self._is_moveable_code(self.cells[i]):
                m |= 1 << i
        self.notes_mask = m

    def _apply_late_phase(self) -> bool:
        """Execute Late rules via bitmasks; return True iff any hero died."""
        if self.part == 3:
            self._recompute_notes_mask()

        dying_mask = 0
        if self.part == 2:
            for y in range(self.h):
                base = y * self.w
                for x in range(self.w):
                    c = self.cells[base + x]
                    if c == _DRAG_R:
                        for nx in range(x + 1, self.w):
                            tc = self.cells[base + nx]
                            if tc == _EMPTY:
                                continue
                            if self._is_hero_code(tc) or self._is_monster_code(tc):
                                dying_mask |= 1 << (base + nx)
                            break
                    elif c == _DRAG_L:
                        for nx in range(x - 1, -1, -1):
                            tc = self.cells[base + nx]
                            if tc == _EMPTY:
                                continue
                            if self._is_hero_code(tc) or self._is_monster_code(tc):
                                dying_mask |= 1 << (base + nx)
                            break

        hero_died = False
        if self.part >= 2:
            for idx, c in enumerate(self.cells):
                if c == _GOBLIN:
                    for nb in self.orth_neighbors[idx]:
                        tc = self.cells[nb]
                        if self._is_hero_code(tc) or self._is_monster_code(tc):
                            dying_mask |= 1 << nb

            if dying_mask:
                shield_mask = 0
                for idx, c in enumerate(self.cells):
                    if c in (_ACT_P, _INA_4):
                        shield_mask |= 1 << idx
                        for nb in self.orth_neighbors[idx]:
                            if self._is_hero_code(self.cells[nb]):
                                shield_mask |= 1 << nb
                dying_mask &= ~shield_mask

                for idx in range(self.n):
                    if (dying_mask >> idx) & 1:
                        tc = self.cells[idx]
                        if self._is_monster_code(tc):
                            self.cells[idx] = _EMPTY
                        elif self._is_hero_code(tc):
                            hero_died = True

        # Yellow switches & doors
        if self.ysw_mask:
            all_weighed = True
            any_weighed = False
            for idx in range(self.n):
                if (self.ysw_mask >> idx) & 1:
                    if self._is_weighing_code(self.cells[idx]):
                        any_weighed = True
                    else:
                        all_weighed = False
            if any_weighed and all_weighed:
                if self.ydoor_init_mask:
                    self.y_open = 1
                    for idx in range(self.n):
                        if ((self.ydoor_init_mask >> idx) & 1) and self.cells[idx] == _YDOOR:
                            self.cells[idx] = _EMPTY
            elif not all_weighed and self.y_open:
                self.y_open = 0
                for idx in range(self.n):
                    if (self.ydoor_init_mask >> idx) & 1:
                        if self._is_hero_code(self.cells[idx]):
                            hero_died = True
                        self.cells[idx] = _YDOOR

        # Purple switches & doors
        if self.psw_mask:
            all_weighed = True
            any_weighed = False
            for idx in range(self.n):
                if (self.psw_mask >> idx) & 1:
                    if self._is_weighing_code(self.cells[idx]):
                        any_weighed = True
                    else:
                        all_weighed = False
            if any_weighed and all_weighed:
                if self.pdoor_init_mask:
                    self.p_open = 1
                    for idx in range(self.n):
                        if ((self.pdoor_init_mask >> idx) & 1) and self.cells[idx] == _PDOOR:
                            self.cells[idx] = _EMPTY
            elif not all_weighed and self.p_open:
                self.p_open = 0
                for idx in range(self.n):
                    if (self.pdoor_init_mask >> idx) & 1:
                        if self._is_hero_code(self.cells[idx]):
                            hero_died = True
                        self.cells[idx] = _PDOOR

        # Monster doors are resolved after colored doors, which can crush the
        # final monster during the same late phase.
        if self.part >= 2 and not any(self._is_monster_code(c) for c in self.cells):
            for idx in range(self.n):
                if self.cells[idx] == _MGATE:
                    self.cells[idx] = _EMPTY

        if self.part == 3 and self.notes_mask:
            clean_notes = 0
            for idx in range(self.n):
                if ((self.notes_mask >> idx) & 1) and self._is_moveable_code(self.cells[idx]):
                    clean_notes |= 1 << idx
            self.notes_mask = clean_notes

        return hero_died

    def is_winning(self) -> bool:
        hero_mask = 0
        for idx, c in enumerate(self.cells):
            if self._is_hero_code(c):
                hero_mask |= 1 << idx
        return hero_mask == self.goals_mask

    def render_ascii(self) -> str:
        out_rows: List[str] = []
        for y in range(self.h):
            chars: List[str] = []
            for x in range(self.w):
                idx = y * self.w + x
                bit = 1 << idx
                c = self.cells[idx]
                if c != _EMPTY:
                    chars.append(_OBJ_TO_CHAR[c])
                elif self.goals_mask & bit:
                    chars.append("G")
                elif self.ysw_mask & bit:
                    chars.append("{")
                elif self.psw_mask & bit:
                    chars.append("}")
                else:
                    chars.append(".")
            out_rows.append("".join(chars))
        return "\n".join(out_rows)

    def fold_digest(self, acc: int) -> int:
        y_eff = 1 if (self.ydoor_init_mask and self.y_open) else 0
        p_eff = 1 if (self.pdoor_init_mask and self.p_open) else 0
        return _fnv64_fold_frame(acc, self.cells, self.notes_mask, y_eff, p_eff)

    def _multi_input(self, key: str) -> Tuple[bool, bool]:
        initial = list(self.cells)
        note_before, yo_before, po_before = self.notes_mask, self.y_open, self.p_open
        players = {i: c for i, c in enumerate(initial) if _ACT_F <= c <= _ACT_D}
        def cancel():
            self.cells = initial
            self.notes_mask, self.y_open, self.p_open = note_before, yo_before, po_before
            return True, self.is_winning()
        if key == "A":
            remaining = set(players)
            for distance in range(1, self.max_slot):
                for code in range(1, self.max_slot + 1):
                    for src in list(remaining):
                        if players[src] != code:
                            continue
                        dest_code = (code - 1 + distance) % self.max_slot + 1
                        dest = next((i for i in self.col_major_indices if self.cells[i] == dest_code + 6), -1)
                        if dest >= 0:
                            self.cells[src] = code + 6
                            self.cells[dest] = dest_code
                            remaining.remove(src)
            if self.part == 2 and any(_ACT_F <= self.cells[i] <= _ACT_D for i in players):
                return cancel()
            return not self._apply_late_phase(), self.is_winning()
        dx, dy = _STEP_DELTAS[key]
        adjacent = [((i // self.w + dy) * self.w + i % self.w + dx) if 0 <= i % self.w + dx < self.w and 0 <= i // self.w + dy < self.h else -1 for i in range(self.n)]
        moving = set(players)
        for src, code in players.items():
            if code == _ACT_F:
                at = adjacent[src]
                while at >= 0 and self._is_moveable_code(self.cells[at]):
                    moving.add(at)
                    at = adjacent[at]
            if code == _ACT_T:
                bx, by = src % self.w - dx, src // self.w - dy
                if 0 <= bx < self.w and 0 <= by < self.h:
                    behind = by * self.w + bx
                    if self._is_moveable_code(self.cells[behind]):
                        moving.add(behind)
        for src, code in players.items():
            if code != _ACT_W:
                continue
            moving.discard(src)
            at = adjacent[src]
            while at >= 0:
                obj = self.cells[at]
                if self._is_static_code(obj):
                    moving.add(src)
                    break
                if self._is_moveable_code(obj):
                    self.cells[src], self.cells[at] = obj, _ACT_W
                    break
                at = adjacent[at]
            if at < 0 and self.part == 3:
                moving.add(src)
        for src, code in players.items():
            if code != _ACT_D or self.cells[src] != code:
                continue
            at = adjacent[src]
            if at < 0 or self.cells[at] == _EMPTY:
                continue
            moving.discard(src)
            obj = self.cells[at]
            if obj in (_CRATE, _GOBLIN, _WALL):
                self.cells[at] = _CRATE if obj == _WALL else _WALL
            elif self._is_hero_code(obj) and obj not in (_ACT_P, _INA_4):
                if not any(self.cells[i] in (_ACT_P, _INA_4) for i in self.orth_neighbors[at]):
                    self.cells[at] = _WALL
        bards = {i for i, c in players.items() if c == _ACT_B and self.cells[i] == _ACT_B}
        if bards:
            pending = {i for i in range(self.n) if (self.notes_mask >> i) & 1 and self._is_moveable_code(self.cells[i])} | bards
            moving -= bards
            while True:
                eligible = [i for i in pending if adjacent[i] >= 0 and (_EMPTY <= self.cells[adjacent[i]] <= _ACT_D and self.cells[adjacent[i]] != _ACT_B)]
                if not eligible:
                    break
                for i in eligible:
                    self.cells[adjacent[i]], self.cells[i] = self.cells[i], _EMPTY
                    pending.remove(i)
            if pending & bards:
                return cancel()
        self.notes_mask = 0
        while True:
            eligible = [i for i in moving if adjacent[i] >= 0 and self.cells[adjacent[i]] == _EMPTY]
            if not eligible:
                break
            for i in eligible:
                self.cells[adjacent[i]], self.cells[i] = self.cells[i], _EMPTY
                moving.remove(i)
        if self.part == 2 and any(_ACT_F <= self.cells[i] <= _ACT_D for i in players):
            return cancel()
        return not self._apply_late_phase(), self.is_winning()

    def step(self, key: str) -> Tuple[bool, bool]:
        if key not in ("U", "D", "L", "R", "A"):
            raise ValueError(f"Unsupported move key {key!r}")

        if sum(_ACT_F <= c <= _ACT_D for c in self.cells) > 1:
            return self._multi_input(key)
        act_idx = -1
        act_code = _EMPTY
        for idx, c in enumerate(self.cells):
            if _ACT_F <= c <= _ACT_D:
                act_idx = idx
                act_code = c
                break
        if act_idx < 0:
            return False, False

        snap_cells = list(self.cells)
        snap_notes = self.notes_mask
        snap_yo = self.y_open
        snap_po = self.p_open

        if key == "A":
            self.notes_mask = 0
            switched = False
            for off in range(1, self.max_slot):
                target_act = ((act_code - 1 + off) % self.max_slot) + 1
                target_ina = target_act + 6
                found_idx = -1
                for scan_i in self.col_major_indices:
                    if self.cells[scan_i] == target_ina:
                        found_idx = scan_i
                        break
                if found_idx >= 0:
                    self.cells[act_idx] = act_code + 6
                    self.cells[found_idx] = target_act
                    switched = True
                    break
            if not switched and self.part <= 2:
                return True, self.is_winning()
            died = self._apply_late_phase()
            return (not died), self.is_winning()

        dx, dy = _STEP_DELTAS[key]
        ax, ay = act_idx % self.w, act_idx // self.w
        nx, ny = ax + dx, ay + dy
        in_bounds = 0 <= nx < self.w and 0 <= ny < self.h
        nidx = ny * self.w + nx if in_bounds else -1
        moved = False

        if act_code == _ACT_F:
            self.notes_mask = 0
            if in_bounds:
                cx, cy = nx, ny
                while 0 <= cx < self.w and 0 <= cy < self.h and self._is_moveable_code(self.cells[cy * self.w + cx]):
                    cx += dx
                    cy += dy
                if 0 <= cx < self.w and 0 <= cy < self.h and self.cells[cy * self.w + cx] == _EMPTY:
                    while (cx, cy) != (ax, ay):
                        px, py = cx - dx, cy - dy
                        self.cells[cy * self.w + cx] = self.cells[py * self.w + px]
                        cx, cy = px, py
                    self.cells[act_idx] = _EMPTY
                    moved = True

        elif act_code == _ACT_T:
            self.notes_mask = 0
            if in_bounds and self.cells[nidx] == _EMPTY:
                bx, by = ax - dx, ay - dy
                self.cells[nidx] = _ACT_T
                if 0 <= bx < self.w and 0 <= by < self.h and self._is_moveable_code(self.cells[by * self.w + bx]):
                    self.cells[act_idx] = self.cells[by * self.w + bx]
                    self.cells[by * self.w + bx] = _EMPTY
                else:
                    self.cells[act_idx] = _EMPTY
                moved = True

        elif act_code == _ACT_W:
            self.notes_mask = 0
            rx, ry = ax, ay
            while True:
                tx, ty = rx + dx, ry + dy
                if not (0 <= tx < self.w and 0 <= ty < self.h):
                    if self.part == 3 and in_bounds and self.cells[nidx] == _EMPTY:
                        self.cells[nidx] = _ACT_W
                        self.cells[act_idx] = _EMPTY
                        moved = True
                    break
                ti = ty * self.w + tx
                tc = self.cells[ti]
                if tc == _EMPTY:
                    rx, ry = tx, ty
                elif self._is_static_code(tc):
                    if in_bounds and self.cells[nidx] == _EMPTY:
                        self.cells[nidx] = _ACT_W
                        self.cells[act_idx] = _EMPTY
                        moved = True
                    break
                elif self._is_moveable_code(tc):
                    self.cells[ti] = _ACT_W
                    self.cells[act_idx] = tc
                    moved = True
                    break
                else:
                    break

        elif act_code == _ACT_P:
            self.notes_mask = 0
            if in_bounds and self.cells[nidx] == _EMPTY:
                self.cells[nidx] = _ACT_P
                self.cells[act_idx] = _EMPTY
                moved = True

        elif act_code == _ACT_D:
            self.notes_mask = 0
            if in_bounds:
                tc = self.cells[nidx]
                if tc == _EMPTY:
                    self.cells[nidx] = _ACT_D
                    self.cells[act_idx] = _EMPTY
                    moved = True
                elif tc in (_CRATE, _GOBLIN):
                    self.cells[nidx] = _WALL
                    moved = True
                elif tc == _WALL:
                    self.cells[nidx] = _CRATE
                    moved = True
                elif tc in (_ACT_P, _INA_4):
                    moved = True
                elif self._is_hero_code(tc):
                    shielded = any(self.cells[nb] in (_ACT_P, _INA_4) for nb in self.orth_neighbors[nidx])
                    if not shielded:
                        self.cells[nidx] = _WALL
                    moved = True

        elif act_code == _ACT_B:
            b_idx = act_idx
            bard_stepped = False
            pending = [i for i in range(self.n) if (self.notes_mask >> i) & 1]
            still_pending = [True] * len(pending)
            progressed = True
            while progressed:
                progressed = False
                for k_i, p_idx in enumerate(pending):
                    if not still_pending[k_i]:
                        continue
                    px, py = (p_idx % self.w) + dx, (p_idx // self.w) + dy
                    if 0 <= px < self.w and 0 <= py < self.h:
                        t_idx = py * self.w + px
                        if self.cells[t_idx] == _EMPTY:
                            self.cells[t_idx] = self.cells[p_idx]
                            self.cells[p_idx] = _EMPTY
                            still_pending[k_i] = False
                            progressed = True
                if not bard_stepped:
                    bx2, by2 = (b_idx % self.w) + dx, (b_idx // self.w) + dy
                    if 0 <= bx2 < self.w and 0 <= by2 < self.h:
                        bt_idx = by2 * self.w + bx2
                        if self.cells[bt_idx] == _EMPTY:
                            self.cells[bt_idx] = _ACT_B
                            self.cells[b_idx] = _EMPTY
                            b_idx = bt_idx
                            bard_stepped = True
                            progressed = True
            if not bard_stepped:
                self.cells = snap_cells
                self.notes_mask = snap_notes
                self.y_open = snap_yo
                self.p_open = snap_po
                return True, self.is_winning()
            self.notes_mask = 0
            moved = True

        if self.part <= 2 and not moved:
            self.cells = snap_cells
            self.notes_mask = snap_notes
            self.y_open = snap_yo
            self.p_open = snap_po
            return True, self.is_winning()

        died = self._apply_late_phase()
        return (not died), self.is_winning()


def replay_flat_oracle(part: int, grid: List[str], route: str) -> Dict[str, Any]:
    """Replay a route on the zero-shared-code FlatBitmaskOracle and return rolling trajectory digest."""
    eng = FlatBitmaskOracle(part, grid)
    clean_route = route.strip().upper()
    digest = eng.fold_digest(_FNV64_OFFSET)
    alive = True
    premature_win = False
    steps_executed = 0

    for idx, ch in enumerate(clean_route):
        ok_alive, won = eng.step(ch)
        steps_executed += 1
        if not ok_alive:
            alive = False
            break
        digest = eng.fold_digest(digest)
        if won and idx + 1 < len(clean_route):
            premature_win = True
            break

    exact_win = alive and (not premature_win) and eng.is_winning()
    return {
        "alive": alive,
        "exact_win": exact_win,
        "premature_win": premature_win,
        "steps_executed": steps_executed,
        "route_len": len(clean_route),
        "route_sha256_12": hashlib.sha256(clean_route.encode("utf-8")).hexdigest()[:12],
        "traj_fnv64": f"{digest:016x}",
        "final_ascii": eng.render_ascii(),
    }
