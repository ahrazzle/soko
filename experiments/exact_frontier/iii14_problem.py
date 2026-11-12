"""Reusable global III-14 bounded problem and independent calibration controls.

`build_problem(n)` imposes only the modeled game rules and win by n.  Calibration
is separate and never changes the constraints on the global problem.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import random
import sys
import z3
from pathlib import Path

# Permit direct execution, as well as importing from a repository-root driver.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.exact_frontier import iii14_smt as model
from soko_mcp.oracle import PuzzleScriptOracle

oracle_state = model.oracle_state

MODEL_CONTRACT = {
    "version": 1,
    "room": "III-14",
    "board": "original 15x7",
    "objective": "first win at or before horizon inputs",
    "state": ["walls", "crates", "bard", "druid", "bard_active", "notes", "door_open"],
    "state_encoding": "105-bit masks for walls, crates, each hero and notes; booleans for active hero and door",
    "actions": ["U", "D", "L", "R", "A"],
    "action_encoding": "one-hot Boolean variables named action_{zero_based_step}_{action}",
    "goal_absorbing": True,
    "all_board_cells_modeled": True,
    "hero_loss_pruned": "Druid petrifying Bard and closing door on either hero are losing because both heroes are necessary for the two goals",
    "bard_movement": "prior note aura; fixed point allows each blocked charmed object to remain independently; blocked Bard cancels the turn",
    "door_behavior": "opens when all switches are weighed; closing can remove walls and crates or kill heroes",
    "noops": "permitted where the game permits them",
    "redundant_global_landmarks": {
        "all_material_switches": "some full-history frame has all nine switches occupied by walls or crates",
        "wall_to_crate_events": "at least nine Druid wall-to-crate events occur before victory",
        "proof": "Before both heroes first enter the three-cell goal enclosure, a hero occupies a door while neither is on a switch; therefore nine material tokens weigh the switches. Each began as a boundary wall and must have been converted to a crate to reach a switch. A door closure can delete, but not create, material. See structure_system.md.",
        "guard": "exact original grid and catalog source hash checked before enabling",
    },
    "external_lower_bound_assumed": False,
    "prefix_or_neighborhood_restriction": False,
    "solver_result_semantics": {"sat": "candidate requiring independent original-game replay", "unsat": "no modeled win at or before horizon, subject to model correctness", "unknown": "inconclusive"},
    "calibration_limits": "sampled oracle agreement is evidence, not a proof of model equivalence",
}


EXPECTED_ROWS = (
    "###############", "#.............#", "#.5.}}}.]]]]].#",
    "#...}}}.]G.G].#", "#.D.}}}.]]]]].#", "#.............#",
    "###############",
)
EXPECTED_SOURCE_SHA256 = "f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0"


def _verify_landmark_source(rows, catalog_rows, source_sha):
    """Refuse topology-specific clauses if either board or source differs."""
    if (tuple(rows) != EXPECTED_ROWS or tuple(catalog_rows) != EXPECTED_ROWS
            or source_sha != EXPECTED_SOURCE_SHA256 or model.W != 15 or model.H != 7
            or model.SW != model.mask('}') or model.DOOR != model.mask(']')
            or model.GOAL != model.mask('G')):
        raise ValueError("III-14 landmark source/grid guard failed")


def _guard_current_source():
    catalog = json.loads((ROOT / 'soko_mcp/data/catalog.json').read_text())
    matches = [room for room in catalog['rooms'] if room['id'] == 'III-14']
    if len(matches) != 1:
        raise ValueError("III-14 landmark source/grid guard failed")
    room = matches[0]
    _verify_landmark_source(model.ROWS, room['grid'], room['source']['source_sha256'])


def build_problem(horizon: int, *, use_landmarks: bool = True):
    """Return (solver, per-step action booleans, state variables) for <= horizon.

    No prefix, guide, milestone, or public lower bound is used.  Two proven
    full-history landmarks are enabled by default, guarded by the exact source
    and grid. The solver has no finite timeout; the caller sets its budget.
    """
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 0:
        raise ValueError("horizon must be a nonnegative integer")
    # The experimental builder prints status; the reusable API is silent.
    if use_landmarks:
        _guard_current_source()
    with redirect_stdout(io.StringIO()):
        solver, actions, states = model.build(horizon, timeout=0, construct_only=True, onehot=True)
    if use_landmarks:
        solver.add(z3.Or(*[((frame[0] | frame[1]) & model.BV(model.SW)) == model.BV(model.SW)
                           for frame in states]))
        events = []
        for i, frame in enumerate(states[:-1]):
            walls, _, bard, druid, bard_active, _, _ = frame
            before_win = (bard | druid) != model.BV(model.GOAL)
            events.append(z3.And(before_win, z3.Not(bard_active), z3.Or(*[
                z3.And(actions[i][j], (model.shift(druid, direction) & walls) != model.Z)
                for j, direction in enumerate('UDLR')
            ])))
        solver.add(z3.PbGe([(event, 1) for event in events], 9) if len(events) >= 9 else z3.BoolVal(False))
    return solver, actions, states


def calibrate(initial_samples: int = 500, near_samples: int = 100) -> dict:
    """Replay baseline and seeded random traces against the Python oracle.

    Loss branches are deliberately rejected by the model and counted separately.
    A mismatch raises AssertionError and therefore cannot be reported as success.
    This routine uses no solver and imposes no restrictions on build_problem.
    """
    if initial_samples < 0 or near_samples < 0:
        raise ValueError("sample counts must be nonnegative")
    assert model.validate(model.ROUTE)
    oracle = PuzzleScriptOracle(3, model.ROWS)
    win_steps = []
    door_open_steps = []
    for i, action in enumerate(model.ROUTE, 1):
        alive, won = oracle.step(action)
        assert alive
        if any(oracle.floor[y][x] == 'PO' for y in range(model.H) for x in range(model.W)):
            door_open_steps.append(i)
        if won:
            win_steps.append(i)
    assert win_steps == [len(model.ROUTE)]
    assert door_open_steps

    rng = random.Random(7314)
    initial_survived = 0
    for _ in range(initial_samples):
        route = ''.join(rng.choice('UDLRA') for _ in range(rng.randrange(1, 31)))
        initial_survived += model.validate(route)

    rng = random.Random(149314)
    near_survived = 0
    for _ in range(near_samples):
        n = rng.randrange(20, 47)
        route = model.ROUTE[:n] + ''.join(rng.choice('UDLRA') for _ in range(rng.randrange(1, 16)))
        near_survived += model.validate(route)
    return {
        "status": "passed",
        "baseline": {"route": model.ROUTE, "length": len(model.ROUTE), "first_win": win_steps[0], "door_open_steps": door_open_steps},
        "initial_random": {"seed": 7314, "attempted": initial_samples, "surviving_and_matched": initial_survived, "losing_pruned": initial_samples - initial_survived},
        "baseline_prefix_random": {"seed": 149314, "attempted": near_samples, "surviving_and_matched": near_survived, "losing_pruned": near_samples - near_survived},
        "oracle": "soko_mcp.oracle.PuzzleScriptOracle",
        "original_game_replay_required_for_witness": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--contract', action='store_true')
    p.add_argument('--initial-samples', type=int, default=500)
    p.add_argument('--near-samples', type=int, default=100)
    args = p.parse_args()
    result = MODEL_CONTRACT if args.contract else calibrate(args.initial_samples, args.near_samples)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
