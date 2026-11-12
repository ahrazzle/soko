#!/usr/bin/env python3
"""Rebuild the trilogy catalog from pinned upstream HTML and public replay IDs.

HTML/replay responses stay in an external cache. Network access is read-only,
limited to three workers; --offline rebuilds entirely from that cache.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'soko_mcp' / 'data'
FRONTIER = 'https://soko.banteg.xyz'
ROMAN = {1: 'I', 2: 'II', 3: 'III'}
SOURCE_FILES = (
    ('Heroes_of_Sokoban.html', '9811b0538cc7dd73cb7ef271d8f5ff5d4395329a7b87c6cf18c94d7a126bf311'),
    ('Heroes_of_Sokoban_II_Monsters.html', 'a91a1e38706a1bf70a3d1d612a89370b1f5f7c86eefbe86e13a0e2288415f14e'),
    ('Heroes_of_Sokoban_III_The_Bard_and_The_Druid.html', '380d343ad35a8f8caf6863341172a7771d0d28ced2824a7a3085990614562105'),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def extract_source(raw: bytes) -> str:
    match = re.search(r'\b(?:var\s+)?sourceCode\s*=\s*("(?:\\.|[^"\\])*")', raw.decode('utf-8'))
    if match is None:
        raise ValueError('Pinned HTML has no JSON sourceCode string')
    return json.loads(match.group(1))


def parse_levels(source: str) -> tuple[list[dict], list[dict]]:
    """Preserve original grid coordinates and count messages in compiled indices."""
    section = re.split(r'^LEVELS\s*$', source, flags=re.M | re.I)[-1]
    entries: list[dict] = []
    rows: list[str] = []
    pending: list[str] = []
    rooms: list[dict] = []

    def flush() -> None:
        if rows:
            grid = rows.copy()
            if len({len(row) for row in grid}) != 1:
                raise ValueError('Original grid is not rectangular')
            item = {'room': len(rooms) + 1, 'compiled_level_index': len(entries),
                    'grid': grid, 'tutorial_messages': pending.copy()}
            rooms.append(item)
            entries.append({'room': item['room']})
            rows.clear()
            pending.clear()

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or set(line) == {'='}:
            flush()
        elif line.lower().startswith('message '):
            flush()
            message = line[8:].strip()
            pending.append(message)
            entries.append({'message': message})
        else:
            rows.append(line)
    flush()
    if len(rooms) != 22:
        raise ValueError(f'Expected 22 rooms, found {len(rooms)}')
    return rooms, entries


def cached_response(url: str, destination: Path, offline: bool) -> tuple[bytes, str]:
    stamp = destination.with_suffix(destination.suffix + '.observed-at')
    if not destination.exists():
        if offline:
            raise FileNotFoundError(f'Offline cache missing: {destination}')
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (SokoCatalog/1.0; read-only research)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        stamp.write_text(datetime.now(timezone.utc).isoformat())
    # A manually seeded source cache has no observation timestamp; its bytes are
    # still checked against the pin. API captures must always retain their date.
    observed = stamp.read_text().strip() if stamp.exists() else 'unknown'
    return destination.read_bytes(), observed


def build_catalog(cache: Path, frontier: dict, offline: bool = False) -> dict:
    sources = []
    rooms = {}
    for part, (filename, expected_hash) in enumerate(SOURCE_FILES, 1):
        url = 'https://sites.math.washington.edu/~ostroff/puzzles/' + filename
        raw, observed = cached_response(url, cache / filename, offline)
        if sha256(raw) != expected_hash:
            raise ValueError(f'Original HTML checksum mismatch for part {part}')
        source = extract_source(raw)
        parsed, entries = parse_levels(source)
        title = re.search(r'^title\s+(.+)$', source, re.M | re.I).group(1).strip()
        source_meta = {'part': part, 'title': title, 'author': 'Jonah Ostroff', 'url': url,
                       'html_sha256': expected_hash, 'source_sha256': sha256(source.encode()),
                       'compiled_entries': entries,
                       'attribution': 'Original puzzle design and PuzzleScript implementation: Jonah Ostroff.'}
        sources.append(source_meta)
        for entry in parsed:
            room_id = f'{ROMAN[part]}-{entry["room"]}'
            rooms[room_id] = dict(entry, id=room_id, part=part, title=f'{title} — Room {entry["room"]}',
                source={key: value for key, value in source_meta.items() if key != 'compiled_entries'},
                coordinates={'origin': 'top-left', 'x_direction': 'right', 'y_direction': 'down',
                             'transform': 'identity', 'grid_order': 'rows',
                             'original_compiled_object_order': 'column-major'},
                width=len(entry['grid'][0]), height=len(entry['grid']))

    records = frontier['rooms']
    expected_ids = {(part, room) for part in ROMAN for room in range(1, 23)}
    if len(records) != 66 or {(r['part'], r['room']) for r in records} != expected_ids:
        raise ValueError('Frontier snapshot must contain exactly the 66 trilogy rooms')

    def replay_record(record: dict) -> tuple[dict, dict]:
        url = f'{FRONTIER}/api/replay/{record["id"]}'
        raw, observed = cached_response(url, cache / f'replay-{record["id"]}.json', offline)
        if observed == 'unknown':
            raise ValueError(f'Replay {record["id"]} has no observation timestamp')
        replay = json.loads(raw)
        if (replay['part'], replay['room']) != (record['part'], record['room']):
            raise ValueError('Replay room does not match Frontier snapshot')
        route = replay['keys']
        if len(route) != record['length'] or any(key not in 'UDLRA' for key in route):
            raise ValueError('Replay keys or length do not match Frontier snapshot')
        if replay.get('handle') != record.get('handle'):
            raise ValueError('Replay holder does not match Frontier snapshot')
        baseline = {'route': route, 'length': len(route), 'holder': replay.get('handle'),
                    'record_id': record['id'], 'url': url, 'replay_url': f'{FRONTIER}/frontier/?room={ROMAN[record["part"]]}-{record["room"]}&record={record["id"]}',
                    'observed_at': observed, 'response_sha256': sha256(raw),
                    'uid': replay.get('uid'), 'model': replay.get('model'), 'seed': replay.get('seed'),
                    'attribution': 'Public accepted route credited to the named Frontier holder.',
                    'status': 'public_accepted_baseline',
                    'limits': 'Dated public observation; lower bounds are reported by Frontier and not reproved by this import.'}
        return record, baseline

    with ThreadPoolExecutor(max_workers=3) as pool:
        for record, baseline in pool.map(replay_record, records):
            room = rooms[f'{ROMAN[record["part"]]}-{record["room"]}']
            room.update(reference_route=baseline['route'], shortest_known=record['known'],
                        proven_floor=record['lower'], frontier_record=record['length'],
                        frontier_observation=record.copy(), baseline=baseline)
    return {'version': 1, 'captured_at': max(r['baseline']['observed_at'] for r in rooms.values()),
            'frontier_snapshot_sha256': sha256(json.dumps(frontier, sort_keys=True, separators=(',', ':')).encode()),
            'sources': sources, 'rooms': list(rooms.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, default=Path.home() / '.cache' / 'soko-catalog')
    parser.add_argument('--frontier', type=Path, default=DATA / 'frontier_snapshot.json')
    parser.add_argument('--output', type=Path, default=DATA / 'catalog.json')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    catalog = build_catalog(args.cache_dir, json.loads(args.frontier.read_text()), args.offline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    print(f'Imported {len(catalog["rooms"])} rooms into {args.output}')


if __name__ == '__main__':
    main()
