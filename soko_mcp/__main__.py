"""MCP stdio entry point and JSON CLI for local analysis and original play."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .server import dispatch_tool_call, serve_stdio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='soko-verified-mcp', description='Original trilogy replay/play and separately labeled local differential search.')
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser('serve', help='Run MCP JSON-RPC over stdio (default).')
    for cmd, help_text in [('capabilities', 'Report available backends.'), ('audit', 'Run local mutation audit.'), ('tcb-lock', 'Verify portable source manifest.')]:
        sub.add_parser(cmd, help=help_text)
    for cmd in ('catalog', 'list-rooms'):
        p = sub.add_parser(cmd, help='List all 66 canonical original rooms.')
        p.add_argument('--include-fixtures', action='store_true')
    p = sub.add_parser('get-room', help='Get canonical grid, tutorials, source and baseline provenance.')
    p.add_argument('--room', required=True)
    for cmd in ('inspect', 'verify', 'solve', 'optimize', 'prove-floor'):
        p = sub.add_parser(cmd, help='Local interpreter analysis/search; original replay is a separate command.')
        inputs = p.add_mutually_exclusive_group(required=True)
        inputs.add_argument('--room', help='Canonical room ID, or explicit fixture:<legacy-id>.')
        inputs.add_argument('--instance', help='JSON file containing custom part and grid (use - for stdin).')
        if cmd == 'verify':
            p.add_argument('--route', required=True)
        if cmd == 'optimize':
            p.add_argument('--route', default=None, help='Seed route; defaults to reference baseline.')
            p.add_argument('--window-len', type=int, default=14)
        if cmd in ('solve', 'optimize'):
            p.add_argument('--beam-width', type=int, default=40000, help='Total retained state cap.')
        if cmd == 'solve':
            p.add_argument('--max-depth', type=int, default=120)
        if cmd == 'prove-floor':
            p.add_argument('--max-bound', type=int, default=32)
        if cmd in ('solve', 'optimize', 'prove-floor'):
            p.add_argument('--budget-sec', type=int, default={'solve': 20, 'optimize': 35, 'prove-floor': 10}[cmd])
    p = sub.add_parser('replay-original', help='Replay a prefix or winning route in the source-pinned original browser engine.')
    p.add_argument('--room', required=True)
    routes = p.add_mutually_exclusive_group(required=True)
    routes.add_argument('--route')
    routes.add_argument('--baseline', action='store_true')
    p.add_argument('--include-frames', action='store_true')
    p = sub.add_parser('play', help='Reconstruct original state from portable route checkpoints; no process session required.')
    p.add_argument('--room')
    p.add_argument('--prefix', default='')
    p.add_argument('--keys', default='')
    p.add_argument('--action', choices=['step', 'undo', 'reset', 'observe'], default='step')
    p.add_argument('--checkpoint-in', help='Read checkpoint JSON, or a previous full play report.')
    p.add_argument('--checkpoint-out', help='Write portable checkpoint JSON after successful play.')
    args = parser.parse_args(argv)
    if args.cmd in (None, 'serve'):
        return serve_stdio()
    try:
        mapping = {'capabilities': 'soko_capabilities', 'audit': 'soko_run_planted_bug_audit', 'tcb-lock': 'soko_verify_tcb_lock',
                   'catalog': 'soko_list_rooms', 'list-rooms': 'soko_list_rooms', 'get-room': 'soko_get_room',
                   'inspect': 'soko_inspect_room', 'verify': 'soko_verify_route', 'solve': 'soko_solve_room',
                   'optimize': 'soko_optimize_route', 'prove-floor': 'soko_prove_floor',
                   'replay-original': 'soko_replay_original', 'play': 'soko_play'}
        payload = {}
        if getattr(args, 'room', None):
            payload['room_id'] = args.room
        if getattr(args, 'instance', None):
            raw = sys.stdin.read() if args.instance == '-' else Path(args.instance).read_text()
            instance = json.loads(raw)
            if not isinstance(instance, dict) or 'part' not in instance or 'grid' not in instance:
                raise ValueError('instance JSON must be an object with part and grid')
            payload.update(part=instance['part'], grid=instance['grid'])
        for key in ('beam_width', 'window_len', 'budget_sec', 'max_depth', 'max_bound', 'include_fixtures', 'include_frames'):
            if hasattr(args, key):
                payload[key] = getattr(args, key)
        if hasattr(args, 'route') and args.route is not None:
            payload['seed_route' if args.cmd == 'optimize' else 'route'] = args.route
        if getattr(args, 'baseline', False):
            payload['baseline'] = True
        if args.cmd == 'play':
            payload.update(prefix=args.prefix, keys=args.keys, action=args.action)
            if args.checkpoint_in:
                checkpoint = json.loads(Path(args.checkpoint_in).read_text())
                payload['checkpoint'] = checkpoint.get('checkpoint', checkpoint) if isinstance(checkpoint, dict) else checkpoint
        out = dispatch_tool_call(mapping[args.cmd], payload)
        if args.cmd == 'play' and args.checkpoint_out:
            Path(args.checkpoint_out).write_text(json.dumps(out['checkpoint'], indent=2) + '\n')
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'command': args.cmd}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
