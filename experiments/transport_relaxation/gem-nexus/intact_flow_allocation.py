"""Time-expanded unit-capacity 9-flow allocator with intact-border exclusion.

Strengthens `flow_allocation.allocate_flow` on III-14 (15x7, Part III SHA-256
f66ceb8f...) by excluding initial boundary `#` cells before their first
stationary-Druid harvest (`t < first_harvest[c]`) in addition to heroes, with
standalone witness and min-cut certificate verifiers.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    from . import allocation as _repo_alloc
    from . import model as _repo_model
    _HAS_REPO = True
except Exception:
    _repo_alloc = _repo_model = None
    _HAS_REPO = False

W: int = _repo_model.W if _HAS_REPO else 15
H: int = _repo_model.H if _HAS_REPO else 7
ROWS: Tuple[str, ...] = tuple(_repo_model.ROWS) if _HAS_REPO else (
    "###############",
    "#.............#",
    "#.5.}}}.]]]]].#",
    "#...}}}.]G.G].#",
    "#.D.}}}.]]]]].#",
    "#.............#",
    "###############",
)
BORDER: Tuple[Tuple[int, int], ...] = (
    tuple(_repo_model.BORDER) if _HAS_REPO
    else tuple((x, y) for y in range(H) for x in range(W) if ROWS[y][x] == "#")
)
SWITCHES: Tuple[Tuple[int, int], ...] = (
    tuple(_repo_model.SWITCHES) if _HAS_REPO
    else tuple((x, y) for y in range(H) for x in range(W) if ROWS[y][x] == "}")
)
GOALS: Tuple[Tuple[int, int], ...] = (
    tuple(_repo_model.GOALS) if _HAS_REPO
    else tuple((x, y) for y in range(H) for x in range(W) if ROWS[y][x] == "G")
)
PDOORS: Tuple[Tuple[int, int], ...] = tuple(
    (x, y) for y in range(H) for x in range(W) if ROWS[y][x] == "]"
)
KEYS: str = _repo_model.KEYS if _HAS_REPO else "UDLRA"
DIRECTIONS: Dict[str, Tuple[int, int]] = (
    dict(_repo_model.DIRECTIONS) if _HAS_REPO
    else {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
)
BORDER_INDEX: Dict[Tuple[int, int], int] = {pt: i for i, pt in enumerate(BORDER)}


def hero_point(frame: Dict[str, object], role: str) -> Tuple[int, int]:
    return int(frame[f"{role}_x"]), int(frame[f"{role}_y"])


def step_point(pt: Tuple[int, int], delta: Tuple[int, int]) -> Tuple[int, int]:
    return pt[0] + delta[0], pt[1] + delta[1]


def in_bounds(pt: Tuple[int, int]) -> bool:
    return 0 <= pt[0] < W and 0 <= pt[1] < H


def in_aura(pt: Tuple[int, int], bard: Tuple[int, int]) -> bool:
    return max(abs(pt[0] - bard[0]), abs(pt[1] - bard[1])) <= 2


def is_goal_pair(frame: Dict[str, object]) -> bool:
    b, d = hero_point(frame, "bard"), hero_point(frame, "druid")
    return b != d and {b, d} == set(GOALS)


def normalize_heroes(route: str, hero_frames: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    if _HAS_REPO:
        return list(_repo_alloc._heroes(route, hero_frames))
    if not isinstance(route, str) or any(ch not in KEYS for ch in route):
        raise ValueError("route must be a string over UDLRA")
    if len(hero_frames) != len(route) + 1:
        raise ValueError("hero_frames length mismatch")
    norm = []
    for raw in hero_frames:
        bx, by, dx, dy = int(raw["bard_x"]), int(raw["bard_y"]), int(raw["druid_x"]), int(raw["druid_y"])
        if not (in_bounds((bx, by)) and in_bounds((dx, dy))):
            raise ValueError("hero out of bounds")
        norm.append({"bard_x": bx, "bard_y": by, "druid_x": dx, "druid_y": dy, "active": bool(raw["active"])})
    f0 = norm[0]
    if (f0["bard_x"], f0["bard_y"], f0["druid_x"], f0["druid_y"], f0["active"]) != (2, 2, 2, 4, False):
        raise ValueError("invalid III-14 initial hero frame")
    for idx, key in enumerate(route):
        bf, af = norm[idx], norm[idx + 1]
        b0, b1 = hero_point(bf, "bard"), hero_point(af, "bard")
        d0, d1 = hero_point(bf, "druid"), hero_point(af, "druid")
        if key == "A":
            if b1 != b0 or d1 != d0 or af["active"] == bf["active"]:
                raise ValueError(f"invalid switch at {idx}")
            continue
        if af["active"] != bf["active"]:
            raise ValueError(f"active flip at {idx}")
        delta = DIRECTIONS[key]
        if bf["active"]:
            if b1 not in (b0, step_point(b0, delta)) or (b1 == b0 and d1 != d0):
                raise ValueError(f"invalid Bard move at {idx}")
            if b1 != b0 and d1 not in ({d0} | ({step_point(d0, delta)} if in_aura(d0, b0) else set())):
                raise ValueError(f"invalid carried Druid move at {idx}")
        elif b1 != b0 or d1 not in (d0, step_point(d0, delta)):
            raise ValueError(f"invalid Druid move at {idx}")
    return norm


def first_harvest_frames(
    route: str, heroes: Sequence[Dict[str, object]], upto_frame: Optional[int] = None
) -> Dict[Tuple[int, int], int]:
    limit = len(route) if upto_frame is None else min(len(route), upto_frame)
    out: Dict[Tuple[int, int], int] = {}
    for i in range(limit):
        key, bf, af = route[i], heroes[i], heroes[i + 1]
        if key != "A" and not bf["active"] and hero_point(af, "druid") == hero_point(bf, "druid"):
            tgt = step_point(hero_point(bf, "druid"), DIRECTIONS[key])
            if tgt in BORDER_INDEX and tgt not in out:
                out[tgt] = i + 1
    return out


@dataclass
class FlowEdge:
    to: int
    reverse: int
    capacity: int
    original_capacity: int
    kind: str = "one"
    params: Tuple[object, ...] = ()


class CertifiedDinic:
    def __init__(self) -> None:
        self.labels: List[str] = []
        self.graph: List[List[FlowEdge]] = []
        self.forward_edges: List[Tuple[int, int]] = []

    def add_node(self, label: str) -> int:
        self.labels.append(label)
        self.graph.append([])
        return len(self.graph) - 1

    def add_edge(self, u: int, v: int, capacity: int = 1, kind: str = "one", params: Tuple[object, ...] = ()) -> None:
        if type(capacity) is not int or capacity < 0 or u == v:
            raise ValueError("invalid edge")
        self.forward_edges.append((u, len(self.graph[u])))
        self.graph[u].append(FlowEdge(v, len(self.graph[v]), capacity, capacity, kind, params))
        self.graph[v].append(FlowEdge(u, len(self.graph[u]) - 1, 0, 0, "residual", ()))

    def max_flow(self, source: int, sink: int) -> int:
        total = 0
        while True:
            levels = [-1] * len(self.graph)
            levels[source] = 0
            q = deque([source])
            while q:
                u = q.popleft()
                for e in self.graph[u]:
                    if e.capacity > 0 and levels[e.to] < 0:
                        levels[e.to] = levels[u] + 1
                        q.append(e.to)
            if levels[sink] < 0:
                return total
            cursors = [0] * len(self.graph)
            cap_max = sum(e.capacity for e in self.graph[source])
            while True:
                nodes, limits, path, pushed = [source], [cap_max], [], 0
                while nodes:
                    u = nodes[-1]
                    if u == sink:
                        pushed = limits[-1]
                        for pn, pi in path:
                            fe = self.graph[pn][pi]
                            fe.capacity -= pushed
                            self.graph[fe.to][fe.reverse].capacity += pushed
                        break
                    while cursors[u] < len(self.graph[u]):
                        ce = self.graph[u][cursors[u]]
                        if ce.capacity > 0 and levels[ce.to] == levels[u] + 1:
                            break
                        cursors[u] += 1
                    if cursors[u] == len(self.graph[u]):
                        nodes.pop()
                        limits.pop()
                        if path:
                            cursors[path.pop()[0]] += 1
                        continue
                    ei = cursors[u]
                    ce = self.graph[u][ei]
                    path.append((u, ei))
                    nodes.append(ce.to)
                    limits.append(min(limits[-1], ce.capacity))
                if not pushed:
                    break
                total += pushed

    def min_cut(self, source: int) -> Dict[str, object]:
        reach, q = {source}, deque([source])
        while q:
            u = q.popleft()
            for e in self.graph[u]:
                if e.capacity > 0 and e.to not in reach:
                    reach.add(e.to)
                    q.append(e.to)
        crossing = [
            {
                "from": self.labels[u], "to": self.labels[self.graph[u][i].to],
                "capacity": self.graph[u][i].original_capacity,
                "flow": self.graph[u][i].original_capacity - self.graph[u][i].capacity,
                "kind": self.graph[u][i].kind, "params": list(self.graph[u][i].params),
            }
            for u, i in self.forward_edges
            if u in reach and self.graph[u][i].to not in reach and self.graph[u][i].original_capacity > 0
        ]
        return {
            "capacity": sum(c["capacity"] for c in crossing), "crossing_edges": crossing,
            "source_side": [self.labels[u] for u in sorted(reach)],
            "sink_side_count": len(self.graph) - len(reach),
        }


def verify_9flow_min_cut(net: CertifiedDinic, source: int, sink: int, cut: Dict[str, object]) -> bool:
    lbl_map = {lbl: idx for idx, lbl in enumerate(net.labels)}
    try:
        src_side = {lbl_map[lbl] for lbl in cut.get("source_side", [])}
    except Exception:
        return False
    if source not in src_side or sink in src_side:
        return False
    true_pairs = [
        (net.labels[u], net.labels[net.graph[u][i].to], net.graph[u][i].original_capacity)
        for u, i in net.forward_edges
        if u in src_side and net.graph[u][i].to not in src_side and net.graph[u][i].original_capacity > 0
    ]
    rep_pairs = [(c["from"], c["to"], c["capacity"]) for c in cut.get("crossing_edges", [])]
    return cut.get("capacity") == sum(p[2] for p in true_pairs) and sorted(true_pairs) == sorted(rep_pairs)


def build_intact_9flow_network(
    route: str, heroes: Sequence[Dict[str, object]], landmark_frame: int, constrain_intact_border: bool = True
) -> Tuple[CertifiedDinic, int, int]:
    net = CertifiedDinic()
    src, snk = net.add_node("source"), net.add_node("sink")
    origins = [net.add_node(f"origin_{j}") for j in range(len(BORDER))]
    for j, node in enumerate(origins):
        net.add_edge(src, node, 1, "one", ("origin", j))
    first_harv = first_harvest_frames(route, heroes, landmark_frame)
    cells: Dict[Tuple[int, int, int], Tuple[int, int]] = {}
    for t in range(1, landmark_frame + 1):
        occ = {hero_point(heroes[t], "bard"), hero_point(heroes[t], "druid")}
        for y in range(H):
            for x in range(W):
                pt = (x, y)
                if pt in occ or (constrain_intact_border and pt in BORDER_INDEX and t < first_harv.get(pt, 10**9)):
                    continue
                cin, cout = net.add_node(f"cell_in_{t}_{x}_{y}"), net.add_node(f"cell_out_{t}_{x}_{y}")
                cells[t, x, y] = (cin, cout)
                net.add_edge(cin, cout, 1, "cell_free_intact" if (constrain_intact_border and pt in BORDER_INDEX) else "cell_free", (t, x, y))
    for i, key in enumerate(route[:landmark_frame]):
        bf, af = heroes[i], heroes[i + 1]
        if key != "A" and not bf["active"] and hero_point(af, "druid") == hero_point(bf, "druid"):
            tgt = step_point(hero_point(bf, "druid"), DIRECTIONS[key])
            if tgt in BORDER_INDEX and (i + 1, *tgt) in cells:
                net.add_edge(origins[BORDER_INDEX[tgt]], cells[i + 1, *tgt][0], 1, "release", (i + 1, *tgt))
    for t in range(1, landmark_frame):
        bf, af, key = heroes[t], heroes[t + 1], route[t]
        b0 = hero_point(bf, "bard")
        carries = key != "A" and bf["active"] and hero_point(af, "bard") != b0
        for y in range(H):
            for x in range(W):
                cur = cells.get((t, x, y))
                if cur is None:
                    continue
                if (t + 1, x, y) in cells:
                    net.add_edge(cur[1], cells[t + 1, x, y][0], 1, "one", ("stay", t, x, y))
                if carries and in_aura((x, y), b0):
                    nx, ny = step_point((x, y), DIRECTIONS[key])
                    if (t + 1, nx, ny) in cells:
                        net.add_edge(cur[1], cells[t + 1, nx, ny][0], 1, "carry", (t, x, y, nx, ny))
    for j, sw in enumerate(SWITCHES):
        swn = net.add_node(f"switch_{j}")
        if (landmark_frame, *sw) in cells:
            net.add_edge(cells[landmark_frame, *sw][1], swn, 1, "landmark", (landmark_frame,))
        net.add_edge(swn, snk, 1, "one", ("sink", j))
    return net, src, snk


def verify_9flow_witness(
    route: str, hero_frames: Sequence[Dict[str, object]], landmark_frame: int,
    report: Dict[str, object], constrain_intact_border: bool = True,
) -> bool:
    if not report.get("feasible"):
        return False
    heroes = normalize_heroes(route, hero_frames)
    first_harv = first_harvest_frames(route, heroes, landmark_frame)
    frames = report.get("frames", [])
    if len(frames) != len(route) + 1:
        return False
    origins = {(frames[0]["token_x"][k], frames[0]["token_y"][k]) for k in range(len(SWITCHES))}
    if len(origins) != len(SWITCHES) or not origins.issubset(set(BORDER)):
        return False
    for k, sw in enumerate(SWITCHES):
        if (frames[landmark_frame]["token_x"][k], frames[landmark_frame]["token_y"][k]) != sw or not frames[landmark_frame]["harvested"][k] or frames[0]["harvested"][k]:
            return False
    for t in range(1, landmark_frame + 1):
        bf, af, key = frames[t - 1], frames[t], route[t - 1]
        b0, b1 = hero_point(heroes[t - 1], "bard"), hero_point(heroes[t], "bard")
        d0, d1 = hero_point(heroes[t - 1], "druid"), hero_point(heroes[t], "druid")
        occ_t: List[Tuple[int, int]] = []
        for k in range(len(SWITCHES)):
            p0, p1 = (bf["token_x"][k], bf["token_y"][k]), (af["token_x"][k], af["token_y"][k])
            h0, h1 = bool(bf["harvested"][k]), bool(af["harvested"][k])
            if (not h0 and not h1 and p1 != p0) or (h0 and not h1):
                return False
            if not h0 and h1 and (key == "A" or heroes[t - 1]["active"] or d1 != d0 or p1 != p0 or step_point(d0, DIRECTIONS[key]) != p0):
                return False
            if h0 and h1 and p1 != p0 and (key == "A" or not heroes[t - 1]["active"] or b1 == b0 or not in_aura(p0, b0) or p1 != step_point(p0, DIRECTIONS[key])):
                return False
            if h1:
                if p1 in {b1, d1} or (constrain_intact_border and p1 in BORDER_INDEX and t < first_harv.get(p1, 10**9)):
                    return False
                occ_t.append(p1)
        if len(set(occ_t)) != len(occ_t):
            return False
    return True


def allocate_intact_9flow(
    route: str, hero_frames: Sequence[Dict[str, object]], landmark_frame: int, constrain_intact_border: bool = True
) -> Dict[str, object]:
    if _HAS_REPO and hasattr(_repo_model, "exact"):
        _repo_model.exact._guard_current_source()
    report: Dict[str, object] = {
        "status": "invalid_trajectory", "feasible": None,
        "unharvested_occupancy_constrained": bool(constrain_intact_border),
        "route": route if isinstance(route, str) else None,
        "landmark_frame": landmark_frame if type(landmark_frame) is int else None, "frames": [],
    }
    try:
        heroes = normalize_heroes(route, hero_frames)
    except ValueError as exc:
        report["reason"] = str(exc)
        return report
    report["horizon"] = len(route)
    if type(landmark_frame) is not int or not 0 <= landmark_frame <= len(route):
        report.update(status="invalid_input", reason="landmark_frame out of range")
        return report
    if not is_goal_pair(heroes[-1]):
        report["reason"] = "final heroes must occupy the two distinct goals"
        return report
    if any(is_goal_pair(f) for f in heroes[:-1]):
        report.update(status="unsupported_trajectory", reason="earlier goal pair")
        return report
    net, src, snk = build_intact_9flow_network(route, heroes, landmark_frame, constrain_intact_border)
    flow = net.max_flow(src, snk)
    cut = net.min_cut(src)
    if not verify_9flow_min_cut(net, src, snk, cut) or cut["capacity"] != flow:
        raise RuntimeError("min-cut check failed")
    report.update(flow_value=flow, required_flow=len(SWITCHES), min_cut=cut, min_cut_verified=True)
    if flow < len(SWITCHES):
        report.update(status="infeasible", feasible=False)
        return report
    rem = {(u, i): net.graph[u][i].original_capacity - net.graph[u][i].capacity for u, i in net.forward_edges}
    paths: List[List[str]] = []
    for u, i in net.forward_edges:
        if u != src or rem[u, i] <= 0:
            continue
        cur, lbls = src, [net.labels[src]]
        while cur != snk:
            pick = next(idx for idx in range(len(net.graph[cur])) if rem.get((cur, idx), 0) > 0)
            rem[cur, pick] -= 1
            cur = net.graph[cur][pick].to
            lbls.append(net.labels[cur])
        paths.append(lbls)
    by_sw, matching = {}, []
    for path in paths:
        oi = int(next(s for s in path if s.startswith("origin_")).split("_")[1])
        si = int(next(s for s in path if s.startswith("switch_")).split("_")[1])
        orig = BORDER[oi]
        pos = {int(s.split("_")[2]): (int(s.split("_")[3]), int(s.split("_")[4])) for s in path if s.startswith("cell_in_")}
        rel = min(pos)
        tp = [(*orig, False)] * rel + [(*pos[t], True) for t in range(rel, landmark_frame + 1)]
        tp.extend([tp[-1]] * (len(route) - landmark_frame))
        by_sw[si] = tp
        matching.append({"switch_index": si, "switch": list(SWITCHES[si]), "origin_index": oi, "origin": list(orig), "harvest_frame": rel})
    matching.sort(key=lambda m: m["switch_index"])
    tpaths = [by_sw[j] for j in range(len(SWITCHES))]
    frames, seen, first_lm = [], False, None
    for t, hf in enumerate(heroes):
        sts = [tp[t] for tp in tpaths]
        at_lm = all((s[0], s[1]) == sw for s, sw in zip(sts, SWITCHES))
        first_lm = t if (at_lm and first_lm is None) else first_lm
        seen = seen or at_lm
        frames.append(dict(hf, token_x=[s[0] for s in sts], token_y=[s[1] for s in sts], harvested=[s[2] for s in sts], landmark_seen=seen))
    report.update(status="feasible", feasible=True, frames=frames, first_landmark_frame=first_lm, origins=[m["origin"] for m in matching], matching=matching, flow_paths=paths)
    if not verify_9flow_witness(route, heroes, landmark_frame, report, constrain_intact_border):
        raise RuntimeError("witness verification failed")
    report["witness_verified"] = True
    return report
