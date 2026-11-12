#!/usr/bin/env python3
"""Cheap reproducible macro trace of III-21's 316-key reference route."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from soko_mcp.catalog import get_room
from soko_mcp.flat_oracle import FlatBitmaskOracle


def main():
    room = get_room('III-21')
    route = room['reference_route']
    o = FlatBitmaskOracle(3, room['grid'])
    segments = []
    changes = []
    current = None
    for step, key in enumerate(route, 1):
        actor = next(c for c in o.cells if 1 <= c <= 6)
        old = o.cells.copy()
        alive, won = o.step(key)
        assert alive
        if key == 'A':
            current = None
        else:
            if current is None:
                current = {'start': step, 'actor': actor, 'route': ''}
                segments.append(current)
            current['end'] = step
            current['route'] += key
        for idx, (before, after) in enumerate(zip(old, o.cells)):
            if (before == 13) != (after == 13):
                changes.append({'step': step, 'key': key,
                                'position': [idx % o.w, idx // o.w],
                                'wall_created': after == 13})
    assert won
    print(json.dumps({'length': len(route), 'actions': route.count('A'),
                      'directional_keys': len(route) - route.count('A'),
                      'segments': segments, 'wall_changes': changes}, indent=2))

if __name__ == '__main__':
    main()
