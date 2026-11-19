#!/usr/bin/env python3
"""Screen public Frontier gaps; this does not certify bounds or optimality."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = 'https://soko.banteg.xyz/api/frontier'
CATALOG = Path(__file__).resolve().parents[2] / 'soko_mcp/data/catalog.json'
ROMAN = {1: 'I', 2: 'II', 3: 'III'}
CANONICAL = {f'{ROMAN[p]}-{r}' for p in ROMAN for r in range(1, 23)}


def integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    return value


def instant(value):
    if not isinstance(value, str):
        raise ValueError('observation time must be ISO 8601 with timezone')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.utcoffset() is None:
            raise ValueError('timezone required')
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError('observation time must be ISO 8601 with timezone') from exc


def identity(row):
    if not isinstance(row, dict):
        raise ValueError('room must be an object')
    part = integer(row.get('part'), 'part')
    room = integer(row.get('room'), 'room')
    if part not in ROMAN or not 1 <= room <= 22:
        raise ValueError('noncanonical room')
    return f'{ROMAN[part]}-{room}'


def entry_age(row, history, observed):
    """Only an unambiguous entry for this record can supply its age."""
    if not isinstance(history, list):
        return None
    matches = [e for e in history if isinstance(e, dict) and type(e.get('id')) is int and e['id'] == row['id']]
    if not matches:
        return None
    times = set()
    for entry in matches:
        if any(type(entry.get(k)) is not int or entry[k] != row[k] for k in ('part', 'room', 'length')):
            return None
        at = entry.get('at')
        try:
            if type(at) is int:
                dt = datetime.fromtimestamp(at, timezone.utc)
            else:
                dt = instant(at)
        except (ValueError, OverflowError, OSError):
            return None
        if dt > observed:
            return None
        times.add(dt)
    if len(times) != 1:
        return None
    return (observed - times.pop()).total_seconds()


def strict_json(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f'invalid JSON constant: {value}')

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f'nonfinite JSON number: {value}')
        return result

    return json.loads(raw, object_pairs_hook=object_pairs,
                      parse_constant=invalid_constant, parse_float=finite_float)


def build_report(snapshot_raw, catalog_raw, observed_at, exclusions=()):
    observed = instant(observed_at)
    snapshot, catalog = strict_json(snapshot_raw), strict_json(catalog_raw)
    if not isinstance(catalog, dict) or not isinstance(catalog.get('rooms'), list):
        raise ValueError('catalog rooms must be a list')
    ids = []
    for row in catalog['rooms']:
        name = identity(row)
        if row.get('id') != name:
            raise ValueError('catalog room ID mismatch')
        ids.append(name)
    if len(ids) != 66 or set(ids) != CANONICAL:
        raise ValueError('catalog must contain each canonical room exactly once')
    excluded = set(exclusions)
    if excluded - CANONICAL:
        raise ValueError('unknown exclusion: ' + ', '.join(sorted(excluded - CANONICAL)))
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('rooms'), list):
        raise ValueError('snapshot rooms must be a list')
    rows = []
    seen = set()
    record_ids = set()
    for row in snapshot['rooms']:
        name = identity(row)
        if name in seen:
            raise ValueError(f'duplicate room: {name}')
        seen.add(name)
        record = integer(row.get('length'), 'length')
        floor = integer(row.get('lower'), 'lower')
        record_id = integer(row.get('id'), 'id')
        if record_id in record_ids:
            raise ValueError(f'duplicate record ID: {record_id}')
        record_ids.add(record_id)
        if floor > record:
            raise ValueError(f'inconsistent reported interval: {name}')
        rows.append({'room': name, 'part': row['part'], 'room_number': row['room'],
                     'reported_record': record, 'reported_floor': floor,
                     'reported_gap': record - floor, 'record_id': record_id,
                     'incumbent_entry_age_seconds': entry_age(row, snapshot.get('log'), observed),
                     'excluded': name in excluded,
                     'exclusion_reason': 'user exclusion' if name in excluded else None})
    if seen != CANONICAL or len(rows) != 66:
        raise ValueError('snapshot must contain each canonical room exactly once')
    rows.sort(key=lambda r: (r['part'], r['room_number']))
    queue = sorted((r for r in rows if r['reported_gap'] > 0 and not r['excluded']),
                   key=lambda r: (-r['reported_gap'], r['part'], r['room_number']))
    return {'schema': 'soko.frontier-room-triage.v1', 'source_url': SOURCE_URL,
            'observed_at': observed.isoformat(),
            'snapshot_sha256': hashlib.sha256(snapshot_raw).hexdigest(),
            'catalog_sha256': hashlib.sha256(catalog_raw).hexdigest(),
            'status': 'reported values; not locally certified',
            'semantics': {'reported_record': 'public incumbent length',
                          'reported_floor': 'public floor; not locally certified',
                          'reported_gap': 'reported record minus reported floor; zero is not an optimality certificate',
                          'ranked_queue': 'positive reported gaps descending for screening; not a probability or difficulty estimate',
                          'incumbent_entry_age_seconds': 'age of matching current record entry, not necessarily when that length was first achieved; null means unknown',
                          'proofs': 'public proofs are not checked and do not upgrade reported floors'},
            'rows': rows, 'excluded_rows': [r for r in rows if r['excluded']], 'ranked_queue': queue}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='saved raw Frontier response')
    parser.add_argument('--observed-at', help='observation time in ISO 8601 with timezone; required with --snapshot')
    parser.add_argument('--exclude', action='append', default=[], metavar='ROOM')
    parser.add_argument('--save-snapshot', type=Path, help='save the raw response from a live fetch')
    args = parser.parse_args(argv)
    if bool(args.snapshot) != bool(args.observed_at):
        parser.error('--snapshot and --observed-at must be supplied together')
    if args.snapshot and args.save_snapshot:
        parser.error('--save-snapshot applies only to a live fetch')
    try:
        if args.snapshot:
            raw = args.snapshot.read_bytes()
            observed = args.observed_at
        else:
            request = Request(SOURCE_URL, headers={'User-Agent': 'soko-room-triage/1.0',
                                                    'Accept': 'application/json'})
            with urlopen(request, timeout=30) as response:
                raw = response.read()
            observed = datetime.now(timezone.utc).isoformat()
            if args.save_snapshot:
                args.save_snapshot.write_bytes(raw)
        print(json.dumps(build_report(raw, CATALOG.read_bytes(), observed, args.exclude), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
