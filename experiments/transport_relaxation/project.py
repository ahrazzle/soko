"""Project the original III-14 reference execution to the transport relaxation.

Material identities are independently propagated through transmutation, prior-note
Bard movement, cancellation, and door crushing. The nine identities are selected
retrospectively at the first frame with material on every switch.
"""
from dataclasses import dataclass
from typing import Optional

from experiments.exact_frontier.iii14_smt import ROWS, ROUTE, W, H, oracle_state
from soko_mcp.oracle import DIRS, PuzzleScriptOracle

SWITCHES = tuple((x, y) for y, row in enumerate(ROWS) for x, c in enumerate(row) if c == "}")


@dataclass(frozen=True)
class ProjectionFrame:
    bard_x: int
    bard_y: int
    druid_x: int
    druid_y: int
    active: bool
    token_x: tuple[int, ...]
    token_y: tuple[int, ...]
    harvested: tuple[bool, ...]
    landmark_seen: bool


@dataclass(frozen=True)
class Projection:
    route: str
    origins: tuple[tuple[int, int], ...]
    landmark: int
    frames: tuple[ProjectionFrame, ...]


def _point(mask: int) -> tuple[int, int]:
    if mask.bit_count() != 1:
        raise ValueError("expected exactly one surviving hero")
    index = mask.bit_length() - 1
    return index % W, index // W


def _moving_positions(oracle, delta):
    """Compute prior-note fixed point on the pre-move occupancy, independently."""
    dx, dy = delta
    bx, by, _ = oracle.find_active()
    bard = (bx, by)
    pending = set(oracle.notes) | {bard}
    movable = set()
    while True:
        new = set()
        for x, y in pending - movable:
            q = (x + dx, y + dy)
            if 0 <= q[0] < W and 0 <= q[1] < H and (
                oracle.obj[q[1]][q[0]] is None or q in movable
            ):
                new.add((x, y))
        if not new:
            break
        movable.update(new)
    return movable if bard in movable else set()


def project(route: str = ROUTE) -> Projection:
    """Replay and track all original wall identities, returning the nine selected tokens.

    Raises ValueError if the execution loses a hero, fails material identity
    checks, never reaches the landmark, or does not win at its final input.
    """
    oracle = PuzzleScriptOracle(3, ROWS)
    # Each identity is its initial boundary cell. Track type as well as location
    # to detect a mistaken identity assignment even across transmutations.
    tokens = {(x, y): ((x, y), "#", False) for y, row in enumerate(ROWS)
              for x, c in enumerate(row) if c == "#"}
    history = []
    landmark = None
    selected = None

    def record():
        nonlocal landmark, selected
        walls, crates, bard, druid, active, _, _ = oracle_state(oracle)
        expected = {(i % W, i // W): "#" if (walls >> i) & 1 else "*"
                    for i in range(W * H) if ((walls | crates) >> i) & 1}
        actual = {pos: kind for pos, kind, _ in tokens.values() if pos is not None}
        if len(actual) != sum(pos is not None for pos, _, _ in tokens.values()) or actual != expected:
            raise ValueError("material identity tracking disagrees with oracle occupancy")
        if landmark is None and all(p in actual for p in SWITCHES):
            landmark = len(history)
            reverse = {pos: origin for origin, (pos, _, _) in tokens.items() if pos is not None}
            selected = tuple(reverse[p] for p in SWITCHES)
        history.append((_point(bard), _point(druid), bool(active), dict(tokens)))

    record()
    for i, key in enumerate(route):
        if key not in 'UDLRA':
            raise ValueError(f"unsupported input {key!r}")
        active = oracle.find_active()
        if active is None:
            raise ValueError("missing active hero")
        if key != 'A':
            dx, dy = DIRS[key]
            if active[2] == 'D':
                target = (active[0] + dx, active[1] + dy)
                for origin, (pos, kind, harvested) in list(tokens.items()):
                    if pos == target:
                        tokens[origin] = (pos, '*' if kind == '#' else '#',
                                          harvested or (kind == '#' and pos == origin))
            else:
                moved = _moving_positions(oracle, (dx, dy))
                for origin, (pos, kind, harvested) in list(tokens.items()):
                    if pos in moved:
                        tokens[origin] = ((pos[0] + dx, pos[1] + dy), kind, harvested)
        alive, won = oracle.step(key)
        if not alive:
            raise ValueError(f"hero lost at input {i + 1}")
        # Doors close in the late phase and may destroy material. No other
        # disappearance is allowed; it is detected by the occupancy check.
        for origin, (pos, kind, harvested) in list(tokens.items()):
            if pos is not None and oracle.obj[pos[1]][pos[0]] in ('[', ']'):
                tokens[origin] = (None, kind, harvested)
        record()
        if won and i + 1 != len(route):
            raise ValueError("route continues after its first win")
    if not route or not oracle.check_win():
        raise ValueError("route does not end in a win")
    if selected is None or landmark is None or len(set(selected)) != 9:
        raise ValueError("no nine-identity material landmark")
    last_positions = list(selected)
    frames = []
    for t, (bard, druid, active, snapshot) in enumerate(history):
        positions, harvested = [], []
        for j, origin in enumerate(selected):
            pos, _, flag = snapshot[origin]
            if pos is not None:
                last_positions[j] = pos
            elif t < landmark:
                raise ValueError("selected token deleted before landmark")
            positions.append(last_positions[j])
            harvested.append(flag)
        frames.append(ProjectionFrame(*bard, *druid, active,
                      tuple(p[0] for p in positions), tuple(p[1] for p in positions),
                      tuple(harvested), t >= landmark))
    return Projection(route, selected, landmark, tuple(frames))


def pin_projection(solver, action_rows, model_frames, projection: Projection) -> None:
    """Constrain a relaxation instance to every action and field in a projection."""
    from dataclasses import asdict
    from experiments.transport_relaxation.model import frame_constraints

    if len(action_rows) != len(projection.route) or len(model_frames) != len(projection.frames):
        raise ValueError("projection and model horizons differ")
    for row, key in zip(action_rows, projection.route):
        if len(row) != 5:
            raise ValueError("expected UDLRA action row")
        solver.add(*(flag == (key == ch) for flag, ch in zip(row, 'UDLRA')))
    for model_frame, projected in zip(model_frames, projection.frames):
        solver.add(*frame_constraints(model_frame, asdict(projected)))
