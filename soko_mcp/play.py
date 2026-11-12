"""Portable original-engine play: checkpoints contain inputs, never engine objects."""
from __future__ import annotations

from .evidence import digest


def _route(value: str) -> str:
    if not isinstance(value, str) or any(key not in 'UDLRA' for key in value):
        raise ValueError('keys and prefix must contain only uppercase U D L R A')
    if len(value) > 10000:
        raise ValueError('route must contain at most 10000 keys')
    return value


def _terminal(result: dict) -> bool:
    return result.get('first_win') is not None or result.get('first_death') is not None


def _replay(room: dict, route: str) -> dict:
    from .original import replay
    return replay(room['part'], room['room'], route)


def play(*, room_id: str | None = None, prefix: str = '', checkpoint: dict | None = None,
         action: str = 'step', keys: str = '') -> dict:
    """Reconstruct exact hidden state by replaying a pinned source and route history."""
    from .catalog import get_room
    if action not in ('step', 'undo', 'reset', 'observe'):
        raise ValueError('action must be step, undo, reset, or observe')
    keys, prefix = _route(keys), _route(prefix)
    expected_pins = None
    if checkpoint is not None:
        if not isinstance(checkpoint, dict):
            raise ValueError('checkpoint must be a JSON object')
        body = {key: value for key, value in checkpoint.items() if key != 'sha256'}
        if checkpoint.get('format') != 'soko-original-play-v1' or checkpoint.get('sha256') != digest(body):
            raise ValueError('checkpoint format or integrity digest is invalid')
        if room_id is not None and room_id != checkpoint.get('room_id'):
            raise ValueError('checkpoint room_id does not match requested room')
        if prefix:
            raise ValueError('prefix cannot be combined with checkpoint')
        room_id = checkpoint.get('room_id')
        prefix = _route(checkpoint.get('route'))
        expected_pins = checkpoint.get('source_pins')
        if not isinstance(expected_pins, dict) or not expected_pins:
            raise ValueError('checkpoint must bind nonempty source_pins')
    if not room_id:
        raise ValueError('room_id is required without a checkpoint')
    room = get_room(room_id)
    if action != 'step' and keys:
        raise ValueError('keys are only accepted for step')
    if action == 'step':
        route = _route(prefix + keys)
    elif action == 'undo':
        route = prefix[:-1]
    elif action == 'reset':
        route = ''
    else:
        route = prefix
    result = _replay(room, route)
    if result.get('again_limit_hit'):
        raise ValueError('original engine did not settle within its again limit; no checkpoint was created')
    if result.get('steps_executed') != len(route):
        raise ValueError('original engine did not execute the complete route; shorten keys or recover from the prior checkpoint')
    pins = result.get('source_pins')
    if not isinstance(pins, dict) or not pins:
        raise ValueError('original replay did not provide source_pins')
    if expected_pins is not None and expected_pins != pins:
        raise ValueError('checkpoint source pins do not match current source')
    # A batch is accepted only through its first terminal key. Extra keys cannot
    # silently start another level or continue after a death/restart.
    for field in ('first_win', 'first_death'):
        terminal_at = result.get(field)
        if terminal_at is not None and terminal_at < len(route):
            raise ValueError('route contains keys after terminal win/death; shorten keys')
    saved = {'format': 'soko-original-play-v1', 'room_id': room_id,
             'source_pins': pins, 'route': route}
    saved['sha256'] = digest(saved)
    return {'room_id': room_id, 'action': action, 'route': route,
            'current_key_count': len(route), 'cost_scope': 'current route; no record or benchmark budget claim',
            'terminal': _terminal(result), 'checkpoint': saved, 'replay': result}
