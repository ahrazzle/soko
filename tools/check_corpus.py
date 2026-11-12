#!/usr/bin/env python3
"""Bounded original-versus-local parity check on the 66 public baseline routes.

This compares the initial state and each settled input frame, including all
persistent object layers. It establishes evidence for these routes only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from soko_mcp import original
from soko_mcp.catalog import get_room, list_rooms
from soko_mcp.engine_bridge import get_soko_checker_pins, verify_route_dual
from soko_mcp.oracle import PuzzleScriptOracle

GLYPHS = {
    'F': 'fighter', 'T': 'thief', 'W': 'wizard', 'P': 'priest', 'B': 'bard', 'D': 'druid',
    '1': 'sfighter', '2': 'sthief', '3': 'swizard', '4': 'spriest', '5': 'sbard', '6': 'sdruid',
    '#': 'wall', '*': 'crate', 'O': 'goblin', 'L': 'dragonleft', 'R': 'dragonright',
    '[': 'yellowdoor', ']': 'purpledoor', 'M': 'monsterdoor', 'CORPSE': 'corpse',
    'G': 'goal', '{': 'yellowswitch', '}': 'purpleswitch', 'YO': 'yellowopen', 'PO': 'purpleopen',
}
PERSISTENT = set(GLYPHS.values()) | {'note'}
# These are implementation bookkeeping/temporary effects, not persistent board
# objects. They are explicitly excluded even when present in a settled frame.
IGNORED = {'background', 'temp', 'warpball', 'shadowdoor', 'dying', 'saved',
           'hassaved', 'hassaveddoor', 'lfireball', 'rfireball', 'didnotmove'}
SCOPE = {
    'comparison': 'initial state and every settled key frame on the selected catalog baseline routes',
    'included': sorted(PERSISTENT), 'excluded': sorted(IGNORED),
    'excluded_reason': 'background and original implementation bookkeeping/temporary effect markers',
    'coordinates': 'identity: top-left origin, x right, y down; original arrays decoded column-major',
    'limits': 'Bounded replay evidence only; no universal transition-system equivalence or optimality claim.',
    'formal_proof_checked': False,
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def project_original(report: dict, words: list[int]) -> list[list[list[str]]]:
    """Decode every persistent layer; reject unknown names, IDs, and set bits."""
    width, height, stride = report['width'], report['height'], report['stride']
    ids = report['object_ids']
    unknown = set(ids) - PERSISTENT - IGNORED
    if unknown:
        raise ValueError(f'Unknown original persistent objects: {sorted(unknown)}')
    if type(stride) is not int or stride < 1 or len(words) != width * height * stride:
        raise ValueError('Original object array dimensions do not match')
    masks = [0] * stride
    for name, oid in ids.items():
        if type(oid) is not int or oid < 0 or oid >= 32 * stride:
            raise ValueError(f'Invalid original object ID for {name}')
        masks[oid >> 5] |= 1 << (oid & 31)
    for index, word in enumerate(words):
        if type(word) is not int or word & 0xFFFFFFFF & ~masks[index % stride]:
            raise ValueError('Unknown original object bits')
    return [[sorted(name for name, oid in ids.items() if name in PERSISTENT
                    and words[(x * height + y) * stride + (oid >> 5)] & (1 << (oid & 31)))
             for x in range(width)] for y in range(height)]


def project_local(sim: PuzzleScriptOracle) -> list[list[list[str]]]:
    layers = []
    for y in range(sim.h):
        row = []
        for x in range(sim.w):
            cell = []
            for glyph in (sim.obj[y][x], sim.floor[y][x]):
                if glyph is not None:
                    if glyph not in GLYPHS:
                        raise ValueError(f'Unknown local persistent object {glyph!r}')
                    cell.append(GLYPHS[glyph])
            if (x, y) in sim.notes:
                cell.append('note')
            row.append(sorted(cell))
        layers.append(row)
    return layers


def validate_original_report(report: dict, room: dict) -> None:
    """Fail closed on stale, altered, incomplete, or wrong-instance cache data."""
    unsigned = {key: value for key, value in report.items() if key != 'certificate_sha256'}
    if report.get('certificate_sha256') != digest(unsigned):
        raise ValueError('Original report certificate hash mismatch')
    part, number, route = room['part'], room['room'], room['reference_route']
    url, html_hash, source_hash = original.SOURCES[part]
    checker = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
    expected = {'part': part, 'room': number, 'route': route, 'route_len': len(route),
                'route_sha256': hashlib.sha256(route.encode()).hexdigest(),
                'source_url': url, 'html_sha256': html_hash,
                'puzzlescript_source_sha256': source_hash, 'checker_sha256': checker,
                'width': room['width'], 'height': room['height'],
                'compiled_level_index': room['compiled_level_index']}
    for key, value in expected.items():
        if report.get(key) != value:
            raise ValueError(f'Original report {key} mismatch for {room["id"]}')
    if html_hash != room['source']['html_sha256'] or source_hash != room['source']['source_sha256']:
        raise ValueError('Catalog/source pin mismatch')
    if report.get('source_pins') != {key: report[key] for key in
            ('html_sha256', 'puzzlescript_source_sha256', 'checker_sha256', 'source_url')}:
        raise ValueError('Original source_pins mismatch')
    frames = report.get('frames')
    if not isinstance(frames, list) or len(frames) != len(route) or report.get('steps_executed') != len(frames):
        raise ValueError('Original report missing complete settled frames')
    if report.get('trajectory_sha256') != digest(frames):
        raise ValueError('Original report trajectory hash mismatch')
    identity = {key: report[key] for key in ('html_sha256', 'part', 'room', 'width', 'height', 'stride', 'initial_objects')}
    if report.get('instance_sha256') != digest(identity):
        raise ValueError('Original report instance hash mismatch')
    if not frames or frames[-1]['objects'] != report.get('final_objects'):
        raise ValueError('Original final object array mismatch')
    for step, frame in enumerate(frames, 1):
        if frame.get('step') != step or frame.get('key') != route[step - 1]:
            raise ValueError('Original frame step/key mismatch')
    first_win = next((f['step'] for f in frames if f['winning']), None)
    first_death = next((f['step'] for f in frames if f['dead']), None)
    if report.get('first_win') != first_win or report.get('first_death') != first_death:
        raise ValueError('Original report first win/death mismatch')
    if report.get('valid_winning_route') != original.accepted(report, len(route)):
        raise ValueError('Original accepted-route metadata mismatch')
    project_original(report, report['initial_objects'])
    for frame in frames:
        project_original(report, frame['objects'])


def frame_difference(step: int, key: str | None, actual: list, expected: list,
                     original_control: dict, local_control: dict) -> dict | None:
    differences = []
    for y, (actual_row, expected_row) in enumerate(zip(actual, expected)):
        for x, (original_cell, local_cell) in enumerate(zip(actual_row, expected_row)):
            if original_cell != local_cell:
                differences.append({'x': x, 'y': y, 'original': original_cell, 'local': local_cell})
    controls = {name: {'original': value, 'local': local_control[name]}
                for name, value in original_control.items() if value != local_control[name]}
    if differences or controls:
        return {'step': step, 'key': key, 'coordinate_differences': differences, 'control_differences': controls}
    return None


def compare_room(room: dict, report: dict, *, require_cpp: bool = True) -> dict:
    validate_original_report(report, room)
    sim = PuzzleScriptOracle(room['part'], room['grid'])
    first_divergence = None
    mismatch_count = 0
    original_hashes, local_hashes = [], []
    local_first_win = None
    local_first_death = None
    alive = True
    frames = [{'step': 0, 'key': None, 'objects': report['initial_objects'],
               'winning': False, 'dead': False, 'restarts': 0}] + report['frames']
    for frame in frames:
        if frame['step']:
            alive_now, won = sim.step(frame['key'])
            alive = alive and alive_now
            if won and local_first_win is None:
                local_first_win = frame['step']
            if not alive_now and local_first_death is None:
                local_first_death = frame['step']
        else:
            won = False
        projected_original = project_original(report, frame['objects'])
        projected_local = project_local(sim)
        original_hashes.append(digest(projected_original))
        local_hashes.append(digest(projected_local))
        divergence = frame_difference(frame['step'], frame['key'], projected_original, projected_local,
            {'alive': not frame['dead'], 'winning': frame['winning'], 'restarts': frame['restarts']},
            {'alive': alive, 'winning': won, 'restarts': 0})
        if divergence:
            mismatch_count += 1
            if first_divergence is None:
                first_divergence = divergence
    dual = verify_route_dual(room['part'], room['grid'], room['reference_route'], require_cpp=require_cpp)
    original_success = original.accepted(report, len(room['reference_route']))
    local_success = alive and local_first_win == len(room['reference_route'])
    passed = (mismatch_count == 0 and original_success and local_success
              and dual['differential_match'] and dual['trajectory_digest_match']
              and dual['triple_oracle_checked'] and dual['valid_winning_route'])
    result = {'schema_version': 1, 'id': room['id'], 'part': room['part'], 'room': room['room'],
        'passed': passed, 'scope': SCOPE, 'formal_proof_checked': False,
        'grid_sha256': digest(room['grid']), 'catalog_source': room['source'],
        'compiled_level_index': room['compiled_level_index'],
        'route_sha256': report['route_sha256'], 'route_length': len(room['reference_route']),
        'baseline_provenance': room['baseline'],
        'original_pins': report['source_pins'], 'original_report_sha256': report['certificate_sha256'],
        'original_instance_sha256': report['instance_sha256'], 'original_trajectory_sha256': report['trajectory_sha256'],
        'initial_and_settled_frames_compared': len(frames), 'mismatched_frames': mismatch_count,
        'original_projected_frame_sha256': original_hashes, 'local_projected_frame_sha256': local_hashes,
        'first_divergence': first_divergence,
        'original_first_win': report['first_win'], 'local_first_win': local_first_win,
        'original_first_death': report['first_death'], 'local_first_death': local_first_death,
        'original_accepted': original_success, 'local_accepted': local_success, 'dual': dual,
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    result['certificate_sha256'] = digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--room', action='append', help='Canonical ID; repeat to select multiple rooms')
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory, never overwritten')
    parser.add_argument('--cache-dir', type=Path, help='External original HTML cache directory')
    parser.add_argument('--replay-cache-dir', type=Path, help='Read original framed reports instead of launching Chromium')
    parser.add_argument('--timeout-sec', type=float, default=30, help='Per-room original worker time budget')
    args = parser.parse_args()
    rooms = [get_room(room_id) for room_id in args.room] if args.room else list_rooms()
    if len({r['id'] for r in rooms}) != len(rooms):
        parser.error('Duplicate selected room IDs')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    certificates = []
    for room in rooms:
        try:
            if args.replay_cache_dir:
                report = json.loads((args.replay_cache_dir / f'{room["id"]}.json').read_text())
            else:
                report = original.replay(room['part'], room['room'], room['reference_route'],
                                         include_frames=True, cache_dir=args.cache_dir, timeout_sec=args.timeout_sec)
            result = compare_room(room, report)
        except Exception as error:
            result = {'id': room['id'], 'passed': False, 'error_type': type(error).__name__, 'error': str(error)}
            result['certificate_sha256'] = digest(result)
        (args.output_dir / f'{room["id"]}.json').write_text(json.dumps(result, indent=2) + '\n')
        certificates.append({key: result[key] for key in ('id', 'passed', 'certificate_sha256')})
        print(f'{room["id"]}: {"PASS" if result["passed"] else "FAIL"} '
              f'{result.get("error", "")}', flush=True)
    reports = [json.loads((args.output_dir / f'{r["id"]}.json').read_text()) for r in rooms]
    summary = {'schema_version': 1, 'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': SCOPE,
        'rooms_checked': len(rooms), 'rooms_passed': sum(r['passed'] for r in reports),
        'all_passed': all(r['passed'] for r in reports),
        'initial_and_settled_frames_compared': sum(r.get('initial_and_settled_frames_compared', 0) for r in reports),
        'settled_input_frames_compared': sum(r.get('route_length', 0) for r in reports),
        'mismatched_frames': sum(r.get('mismatched_frames', 0) for r in reports),
        'catalog_sha256': hashlib.sha256((ROOT / 'soko_mcp/data/catalog.json').read_bytes()).hexdigest(),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'local_checker_pins': get_soko_checker_pins(), 'rooms': certificates}
    summary['certificate_sha256'] = digest(summary)
    (args.output_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['all_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
