"""Concrete Part III projection and Z3 symbolic builders for non-stuttering cuts.

Provides:
  - `project_concrete_win(route)`: labeled-identity Part III III-14 concrete
    execution projector extracting exact `(x, y, harvested, is_wall)` witnesses.
  - `add_z3_nonstuttering_constraints(solver, frames, actions)`: attaches
    Freeze-State (`is_wall`) + 40-atom conservation + Exact Unblocked-Crate
    Non-Stuttering clauses directly to `experiments.transport_relaxation.model`.
  - `symbolic_intact_cut(master, crossing_edges)`: lifts intact-border 9-flow
    min-cuts into global `PbGe` cuts on `global_master.Master`.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set, Tuple

try:
    from . import intact_flow_allocation as _flow
except ImportError:
    import intact_flow_allocation as _flow

try:
    import z3 as _z3
except ImportError:
    _z3 = None

W, H = _flow.W, _flow.H
BORDER, SWITCHES, GOALS, PDOORS = _flow.BORDER, _flow.SWITCHES, _flow.GOALS, _flow.PDOORS
PDOOR_SET = set(PDOORS)
BORDER_INDEX = _flow.BORDER_INDEX
DIRECTIONS = _flow.DIRECTIONS
TokenState = Tuple[int, int, bool, bool]


def project_concrete_win(route: str) -> Dict[str, object]:
    """Replay Part III III-14 concretely and project the 9 landmark switch identities."""
    board: Dict[Tuple[int, int], Tuple[Tuple[int, int], bool]] = {o: (o, True) for o in BORDER}
    open_pd: Set[Tuple[int, int]] = set()
    bard, druid, bard_active = (2, 2), (2, 4), False
    history = [{"board": dict(board), "open_pd": set(open_pd), "bard": bard, "druid": druid, "active": bard_active}]

    for key in route:
        closed_pd = PDOOR_SET - open_pd
        if key == "A":
            bard_active = not bard_active
        elif not bard_active:
            nx, ny = _flow.step_point(druid, DIRECTIONS[key])
            if _flow.in_bounds((nx, ny)) and (nx, ny) != bard and (nx, ny) not in closed_pd:
                if (nx, ny) in board:
                    orig, iw = board[(nx, ny)]
                    board[(nx, ny)] = (orig, not iw)
                else:
                    druid = (nx, ny)
        else:
            dx, dy = DIRECTIONS[key]
            bx, by = bard
            crates = [[p, board[p][0], _flow.in_aura(p, (bx, by))] for p in sorted(board) if not board[p][1]]
            d_ch, b_mv, chg = _flow.in_aura(druid, (bx, by)), False, True
            while chg:
                chg = False
                for item in crates:
                    if not item[2]:
                        continue
                    tx, ty = item[0][0] + dx, item[0][1] + dy
                    if _flow.in_bounds((tx, ty)) and (tx, ty) not in board and (tx, ty) not in closed_pd and (tx, ty) not in (bard, druid):
                        del board[item[0]]
                        board[(tx, ty)] = (item[1], False)
                        item[0], item[2], chg = (tx, ty), False, True
                if d_ch:
                    tx, ty = druid[0] + dx, druid[1] + dy
                    if _flow.in_bounds((tx, ty)) and (tx, ty) not in board and (tx, ty) not in closed_pd and (tx, ty) != bard:
                        druid, d_ch, chg = (tx, ty), False, True
                if not b_mv:
                    tx, ty = bard[0] + dx, bard[1] + dy
                    if _flow.in_bounds((tx, ty)) and (tx, ty) not in board and (tx, ty) not in closed_pd and (tx, ty) != druid:
                        bard, b_mv, chg = (tx, ty), True, True
            if not b_mv:
                prev = history[-1]
                board, bard, druid = dict(prev["board"]), prev["bard"], prev["druid"]
        weighing = set(board.keys()) | {bard, druid}
        open_pd = set(PDOORS) if all(sw in weighing for sw in SWITCHES) else (open_pd & weighing)
        history.append({"board": dict(board), "open_pd": set(open_pd), "bard": bard, "druid": druid, "active": bard_active})

    enc = {(9, 3), (10, 3), (11, 3)}
    lm_t = next(t for t, s in enumerate(history) if s["bard"] in enc and s["druid"] in enc) - 1
    chosen = [history[lm_t]["board"][sw][0] for sw in SWITCHES]
    heroes = [{"bard_x": s["bard"][0], "bard_y": s["bard"][1], "druid_x": s["druid"][0], "druid_y": s["druid"][1], "active": s["active"]} for s in history]
    tok_states: List[List[TokenState]] = [[] for _ in SWITCHES]
    for k, orig in enumerate(chosen):
        conv = False
        for t in range(len(history)):
            if t > lm_t:
                tok_states[k].append(tok_states[k][-1])
                continue
            pos, iw = next((p, v[1]) for p, v in history[t]["board"].items() if v[0] == orig)
            conv = conv or (not iw) or (pos != orig)
            tok_states[k].append((pos[0], pos[1], conv, iw))
    return {
        "valid_win": {history[-1]["bard"], history[-1]["druid"]} == set(GOALS),
        "landmark_frame": lm_t,
        "heroes": heroes,
        "chosen_origins": chosen,
        "token_states": tok_states,
        "doors_open": [len(s["open_pd"]) == len(PDOORS) for s in history],
    }


def symbolic_intact_cut(master: object, crossing_edges: Iterable[Dict[str, object]], required_flow: int = 9):
    """Lift a verified intact-border 9-flow min-cut into a Z3 PbGe cut on `global_master.Master`."""
    if _z3 is None:
        raise RuntimeError("z3-solver required")
    grouped: Dict[Tuple[str, Tuple[object, ...]], List[object]] = {}
    for edge in crossing_edges:
        kind, params = str(edge["kind"]), tuple(edge["params"])
        if (kind, params) in grouped:
            grouped[kind, params][1] += int(edge.get("capacity", 1))
            continue
        if kind == "one":
            pred = _z3.BoolVal(True)
        elif kind == "landmark":
            pred = master.landmarks[int(params[0]) - 1]
        elif kind in ("cell_free", "cell_free_intact"):
            t, x, y = int(params[0]), int(params[1]), int(params[2])
            f = master.frames[t]
            pred = _z3.And(_z3.Not(_z3.And(f.bard_x == x, f.bard_y == y)), _z3.Not(_z3.And(f.druid_x == x, f.druid_y == y)))
            if kind == "cell_free_intact" and (x, y) in BORDER_INDEX:
                rels = []
                for s in range(1, t + 1):
                    bf, af = master.frames[s - 1], master.frames[s]
                    stay = _z3.And(bf.druid_x == af.druid_x, bf.druid_y == af.druid_y)
                    pokes = [_z3.And(master.actions[s - 1][i], bf.druid_x + dx == x, bf.druid_y + dy == y) for i, (dx, dy) in enumerate(DIRECTIONS.values())]
                    rels.append(_z3.And(_z3.Not(bf.active), stay, _z3.Or(*pokes)))
                pred = _z3.And(pred, _z3.Or(*rels) if rels else _z3.BoolVal(False))
        elif kind == "release":
            t, x, y = int(params[0]), int(params[1]), int(params[2])
            bf, af = master.frames[t - 1], master.frames[t]
            stay = _z3.And(bf.druid_x == af.druid_x, bf.druid_y == af.druid_y)
            pokes = [_z3.And(master.actions[t - 1][i], bf.druid_x + dx == x, bf.druid_y + dy == y) for i, (dx, dy) in enumerate(DIRECTIONS.values())]
            pred = _z3.And(_z3.Not(bf.active), stay, _z3.Or(*pokes))
        elif kind == "carry":
            t, x, y, nx, ny = (int(v) for v in params)
            bf, af = master.frames[t], master.frames[t + 1]
            moved = _z3.Or(bf.bard_x != af.bard_x, bf.bard_y != af.bard_y)
            dirs = [_z3.And(master.actions[t][i], af.bard_x == bf.bard_x + dx, af.bard_y == bf.bard_y + dy) for i, (dx, dy) in enumerate(DIRECTIONS.values()) if (x + dx, y + dy) == (nx, ny)]
            near = _z3.And(_z3.ULE(_z3.If(_z3.UGE(bf.bard_x, x), bf.bard_x - x, x - bf.bard_x), 2), _z3.ULE(_z3.If(_z3.UGE(bf.bard_y, y), bf.bard_y - y, y - bf.bard_y), 2))
            pred = _z3.And(bf.active, moved, near, _z3.Or(*dirs))
        else:
            raise ValueError(f"unknown arc kind: {kind!r}")
        grouped[kind, params] = [pred, int(edge.get("capacity", 1))]
    expr = _z3.PbGe([(p[0], p[1]) for p in grouped.values()], required_flow)
    master.solver.add(expr)
    return expr


def add_z3_nonstuttering_constraints(solver: object, frames: Sequence[object], actions: Sequence[Sequence[object]]) -> Dict[str, object]:
    """Attach Freeze-State (`is_wall`) and Exact Non-Stuttering clauses to a Z3 model."""
    if _z3 is None:
        raise RuntimeError("z3-solver required")
    hz, n_tok = len(actions), len(SWITCHES)
    is_wall = [[_z3.Bool(f"ns_is_wall_{t}_{k}") for k in range(n_tok)] for t in range(hz + 1)]
    b_harv = [[_z3.Bool(f"ns_bharv_{t}_{b}") for b in range(len(BORDER))] for t in range(hz + 1)]
    d_open = [_z3.Bool(f"ns_dopen_{t}") for t in range(hz + 1)]
    ublk = [[_z3.Bool(f"ns_ublk_{t}_{k}") for k in range(n_tok)] for t in range(hz)]
    for k in range(n_tok):
        solver.add(is_wall[0][k])
    for b in range(len(BORDER)):
        solver.add(_z3.Not(b_harv[0][b]))
    solver.add(_z3.Not(d_open[0]))
    dirs = list(DIRECTIONS.items())
    for t in range(hz):
        bf, af = frames[t], frames[t + 1]
        pre_lm = _z3.Not(bf.landmark_seen)
        d_hold = _z3.And(af.druid_x == bf.druid_x, af.druid_y == bf.druid_y)
        b_moved = _z3.Or(af.bard_x != bf.bard_x, af.bard_y != bf.bard_y)
        for bi, (bx, by) in enumerate(BORDER):
            pokes = _z3.And(_z3.Not(bf.active), d_hold, _z3.Or(*[_z3.And(actions[t][i], bf.druid_x + dx == bx, bf.druid_y + dy == by) for i, (_, (dx, dy)) in enumerate(dirs)]))
            solver.add(b_harv[t + 1][bi] == _z3.Or(b_harv[t][bi], pokes))
        pb = [(ublk[t][k], 1) for k in range(n_tok)] + [(bf.harvested[m], 1) for m in range(n_tok)] + [(_z3.Not(b_harv[t][b]), 1) for b in range(len(BORDER))]
        solver.add(_z3.Implies(pre_lm, _z3.PbLe(pb, len(BORDER))))
        for k in range(n_tok):
            pk = _z3.And(_z3.Not(bf.active), d_hold, _z3.Or(*[_z3.And(actions[t][i], bf.druid_x + dx == bf.token_x[k], bf.druid_y + dy == bf.token_y[k]) for i, (_, (dx, dy)) in enumerate(dirs)]))
            solver.add(_z3.Implies(pre_lm, _z3.If(_z3.Not(bf.harvested[k]), is_wall[t + 1][k] == _z3.Not(af.harvested[k]), is_wall[t + 1][k] == _z3.Xor(is_wall[t][k], pk))))
            stayed = _z3.And(af.token_x[k] == bf.token_x[k], af.token_y[k] == bf.token_y[k])
            solver.add(_z3.Implies(_z3.And(pre_lm, is_wall[t][k]), stayed))
            solver.add(_z3.Implies(_z3.And(pre_lm, af.harvested[k]), _z3.And(_z3.Or(af.token_x[k] != af.bard_x, af.token_y[k] != af.bard_y), _z3.Or(af.token_x[k] != af.druid_x, af.token_y[k] != af.druid_y))))
            for m in range(k + 1, n_tok):
                solver.add(_z3.Implies(_z3.And(pre_lm, af.harvested[k], af.harvested[m]), _z3.Or(af.token_x[k] != af.token_x[m], af.token_y[k] != af.token_y[m])))
            near = _z3.And(_z3.ULE(_z3.If(_z3.UGE(bf.token_x[k], bf.bard_x), bf.token_x[k] - bf.bard_x, bf.bard_x - bf.token_x[k]), 2), _z3.ULE(_z3.If(_z3.UGE(bf.token_y[k], bf.bard_y), bf.token_y[k] - bf.bard_y, bf.bard_y - bf.token_y[k]), 2))
            for i, (_, (dx, dy)) in enumerate(dirs):
                oob = (bf.token_x[k] == 0) if dx == -1 else (bf.token_x[k] == W - 1) if dx == 1 else (bf.token_y[k] == 0) if dy == -1 else (bf.token_y[k] == H - 1)
                nx, ny = bf.token_x[k] + dx, bf.token_y[k] + dy
                pd_hit = _z3.Or(*[_z3.And(nx == px, ny == py) for px, py in PDOORS])
                ib_hit = _z3.Or(*[_z3.And(nx == bx, ny == by, _z3.Not(b_harv[t][bi])) for bi, (bx, by) in enumerate(BORDER)])
                hr_hit = _z3.Or(_z3.And(af.bard_x == nx, af.bard_y == ny), _z3.And(af.druid_x == nx, af.druid_y == ny))
                tk_hit = _z3.Or(*[_z3.And(bf.harvested[m], af.token_x[m] == nx, af.token_y[m] == ny) for m in range(n_tok) if m != k])
                guard = _z3.And(pre_lm, actions[t][i], bf.active, b_moved, bf.harvested[k], _z3.Not(is_wall[t][k]), near, stayed)
                solver.add(_z3.Implies(guard, _z3.Or(oob, _z3.And(pd_hit, _z3.Not(d_open[t])), ib_hit, hr_hit, tk_hit, ublk[t][k])))
    return {"is_wall": is_wall, "border_harv": b_harv, "doors_open": d_open, "untracked_blk": ublk}
