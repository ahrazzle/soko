#!/usr/bin/env python3
"""Reproduce structural III-14 candidate states; no optimality claim.

The synthetic exit state is a local transition witness, not a reachable-state
certificate. Its boundary has been taken from the reference after creation so
that its nine imported objects respect the original material total.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from soko_mcp.catalog import get_room
from soko_mcp.flat_oracle import FlatBitmaskOracle

ROOM = get_room('III-14')
PACKING_PREFIX = ROOM['reference_route'][:25] + 'RRDRUL'


def replay(route):
    o = FlatBitmaskOracle(3, ROOM['grid'])
    for key in route:
        alive, _ = o.step(key)
        assert alive
    return o


def main():
    packing = replay(PACKING_PREFIX)
    exit_state = replay(ROOM['reference_route'][:18])
    # Clear all mobile material and heroes; retain exactly the nine border holes.
    for i, c in enumerate(exit_state.cells):
        if c in (5, 6, 11, 12, 14):
            exit_state.cells[i] = 0
    for y in (2, 3, 4):
        for x in (4, 5, 6):
            exit_state.cells[y * 15 + x] = 13 if x == 6 and y in (3, 4) else 14
    exit_state.cells[5 * 15 + 6] = 5
    exit_state.cells[5 * 15 + 8] = 12
    exit_state._apply_late_phase()
    before = exit_state.render_ascii()
    for key in 'RRRUU':
        alive, won = exit_state.step(key)
        assert alive
    assert won
    print(json.dumps({
        'schema': 1,
        'candidate_prefix': PACKING_PREFIX,
        'candidate_prefix_length': len(PACKING_PREFIX),
        'candidate_prefix_state': packing.render_ascii(),
        'candidate_prefix_doors_open': bool(packing.p_open),
        'synthetic_exit_state': before,
        'exit_route': 'RRRUU',
        'exit_route_wins': bool(won),
        'limits': 'Prefix is reachable but no winning suffix is known. Synthetic exit state is locally verified, not proved reachable. No optimality or new record claim.',
    }, indent=2))

if __name__ == '__main__':
    main()
