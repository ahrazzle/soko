"""Iterative integer Dinic max-flow and standalone s-t min-cut certificate checker."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class FlowEdge:
    to: int
    reverse: int
    capacity: int
    original_capacity: int
    kind: str = "one"
    params: Tuple[object, ...] = ()


class CertifiedDinic:
    """Iterative Dinic unit-network solver with arc metadata for global cut lifting."""

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
            levels[source], q = 0, deque([source])
            while q:
                u = q.popleft()
                for e in self.graph[u]:
                    if e.capacity > 0 and levels[e.to] < 0:
                        levels[e.to] = levels[u] + 1
                        q.append(e.to)
            if levels[sink] < 0:
                return total
            cursors, cap_max = [0] * len(self.graph), sum(e.capacity for e in self.graph[source])
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
        reach: Set[int] = {source}
        q = deque([source])
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
    """Independently certify an s-t cut capacity without trusting Dinic's residuals."""
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
