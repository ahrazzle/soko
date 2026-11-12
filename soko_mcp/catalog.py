"""Offline, source-pinned catalog of all 66 original trilogy rooms.

Canonical IDs are I-1 through III-22. Every public route is a dated baseline,
not an independent optimality proof. Returned metadata is safe to mutate.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict]:
    data = json.loads(files('soko_mcp').joinpath('data/catalog.json').read_text(encoding='utf-8'))
    return {room['id']: room for room in data['rooms']}


def load_catalog() -> dict[str, dict]:
    """Return all canonical rooms, keyed by ID, with independent metadata."""
    return deepcopy(_catalog())


def get_room(room_id: str) -> dict:
    """Return one canonical room; unknown IDs raise KeyError."""
    return deepcopy(_catalog()[room_id])


def list_rooms() -> list[dict]:
    """Return rooms in original part/room order with independent metadata."""
    return deepcopy(list(_catalog().values()))
