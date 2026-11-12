#!/usr/bin/env python3
"""Exercise the installed CLI and MCP from an arbitrary working directory.

Requires the optional original-browser dependencies. Retains real requests,
responses and command outputs; reproducing baselines is not a record gain.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from mcp_smoke import Client, source_hashes

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, default=Path.cwd(), help='Use outside the checkout to test installed imports')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {'schema_version': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
              'python': sys.executable, 'cwd': str(args.cwd.resolve()),
              'source_hashes_before': source_hashes(ROOT), 'commands': [], 'mcp': [],
              'new_record_claimed': False, 'passed': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def command(*arguments):
        argv = [sys.executable, '-m', 'soko_mcp', *arguments]
        proc = subprocess.run(argv, cwd=args.cwd, capture_output=True, text=True, timeout=45)
        entry = {'command': argv, 'returncode': proc.returncode, 'stderr': proc.stderr}
        record['commands'].append(entry)
        entry['stdout'] = json.loads(proc.stdout) if proc.stdout else None
        if proc.returncode:
            raise RuntimeError(f'Command failed: {arguments[0]}: {proc.stderr}')
        return entry['stdout']

    def require(condition, description):
        if not condition:
            raise AssertionError(description)

    client = None
    try:
        require(command('catalog')['room_count'] == 66, 'installed catalog must have all rooms')
        room = command('get-room', '--room', 'III-21')
        require((room['width'], room['height']) == (23, 13), 'canonical III-21 must be discoverable')
        require(command('verify', '--room', 'I-1', '--route', 'R' * 8)['valid_winning_route'], 'original I-1 local replay')
        command('solve', '--room', 'I-2', '--max-depth', '30', '--budget-sec', '2', '--beam-width', '40000')
        checkpoint = str(output / 'checkpoint.json')
        command('play', '--room', 'I-2', '--keys', 'R', '--checkpoint-out', checkpoint)
        resumed = command('play', '--checkpoint-in', checkpoint, '--keys', 'R', '--checkpoint-out', checkpoint)
        require(resumed['route'] == 'RR', 'checkpoint must resume across CLI processes')

        client = Client(args.cwd.resolve(), timeout=45)

        def call(name, arguments, expect_error=False):
            event = client.call('tools/call', {'name': name, 'arguments': arguments})
            record['mcp'].append(event)
            envelope = event['response']['result']
            require(bool(envelope.get('isError')) == expect_error, f'unexpected MCP outcome: {name}')
            return envelope.get('structuredContent')

        record['mcp'].append(client.call('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {}}))
        original = call('soko_replay_original', {'room_id': 'II-12', 'baseline': True})
        require(original['valid_winning_route'], 'original Part II baseline replay')
        end = call('soko_play', {'room_id': 'I-22', 'keys': 'R' * 10})
        require(end['terminal'] and end['replay']['valid_winning_route'], 'simultaneous heroes win in original I-22')
        call('soko_play', {'checkpoint': end['checkpoint'], 'keys': 'R'}, expect_error=True)
        undone = call('soko_play', {'checkpoint': end['checkpoint'], 'action': 'undo'})
        require(undone['route'] == 'R' * 9 and not undone['terminal'], 'undo reconstructs pre-win state')
        reset = call('soko_play', {'checkpoint': undone['checkpoint'], 'action': 'reset'})
        require(reset['route'] == '' and not reset['terminal'], 'reset reconstructs initial state')
        require(call('soko_verify_route', {'room_id': 'I-22', 'route': 'R' * 10})['valid_winning_route'], 'local multi-active replay')
        record['passed'] = True
    except Exception as error:
        record.update(error_type=type(error).__name__, error=str(error))
    finally:
        if client is not None:
            client.close()
        record['source_hashes_after'] = source_hashes(ROOT)
        record['sources_unchanged'] = record['source_hashes_before'] == record['source_hashes_after']
        record['passed'] = record['passed'] and record['sources_unchanged']
        (output / 'report.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'passed': record['passed'], 'commands': len(record['commands']), 'mcp_events': len(record['mcp']),
                      'error': record.get('error')}))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
