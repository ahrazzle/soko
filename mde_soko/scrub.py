"""Portable path normalization, LF/control-byte checks, and zero-leak receipt guards."""

from __future__ import annotations

import getpass
import hashlib
import json
import re
from pathlib import Path
from typing import Any

_CONTROL_BYTES_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _build_forbidden_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    seat_user = re.escape(getpass.getuser())
    pats: list[tuple[str, re.Pattern[str]]] = [
        ("macos_users_path", re.compile("\x2f" + "Users" + "\x2f")),
        ("linux_home_path", re.compile("\x2f" + "home" + "\x2f")),
        ("macos_temp_path", re.compile(r"/(?:private/)?var/folders/")),
        ("private_vault_name", re.compile(r"\b" + "\x68afiz" + r"\b", re.IGNORECASE)),
        ("seat_alias", re.compile(r"\b" + "orda" + "-" + "aska" + r"\b", re.IGNORECASE)),
        ("invalid_email", re.compile("ci@" + r"example\.invalid", re.IGNORECASE)),
        ("lan_ipv4", re.compile(r"\b192" + r"\.168\.\d{1,3}\.\d{1,3}\b")),
        ("tailscale_ipv4", re.compile(r"\b100" + r"\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
        ("tailscale_ipv6", re.compile("fd7a" + r":115c:[0-9a-fA-F:]+")),
    ]
    if seat_user and seat_user.lower() not in ("runner", "root", "ubuntu"):
        pats.append(("seat_username", re.compile(rf"\b{seat_user}\b", re.IGNORECASE)))
    return tuple(pats)


FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = _build_forbidden_patterns()


def soko_repo_root() -> Path:
    """Return root of the `ahrazzle/soko` checkout containing `mde_soko/`."""
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_lf_bytes(path: Path) -> tuple[str, int]:
    """Verify zero NUL/CR control bytes and return `(sha256_hex, byte_length)`."""
    raw = path.read_bytes()
    if b"\r" in raw:
        raise ValueError(f"{path.name}: contains CR byte (expected LF line endings)")
    for idx, b in enumerate(raw):
        if b < 32 and b not in (9, 10):
            raise ValueError(f"{path.name}: forbidden control byte 0x{b:02x} at offset {idx}")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def to_repo_rel_or_tag(path: Path | str, *, repo_root: Path | None = None) -> str:
    root = (repo_root or soko_repo_root()).resolve()
    p = Path(str(path))
    if p.is_absolute():
        resolved = p.resolve()
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            return f"<external>/{resolved.name}"
    return p.as_posix()


def sanitize_text(text: str) -> str:
    cleaned = _CONTROL_BYTES_RE.sub("", text)
    r_str = str(soko_repo_root().resolve())
    if r_str in cleaned:
        cleaned = cleaned.replace(r_str, "<repo>")
    parent_str = str(soko_repo_root().resolve().parent)
    if parent_str in cleaned:
        cleaned = cleaned.replace(parent_str, "<workspace>")
    seat_user = getpass.getuser()
    if seat_user and seat_user.lower() not in ("runner", "root", "ubuntu") and seat_user in cleaned:
        cleaned = cleaned.replace(seat_user, "<user>")
    cleaned = re.sub(r"/(?:private/)?var/folders/[^\s\"':]+", "<tmpdir>", cleaned)
    cleaned = re.sub("\x2f" + r"Users/[^\s\"'/]+", "<user_home>", cleaned)
    cleaned = re.sub("\x2f" + r"home/[^\s\"'/]+", "<user_home>", cleaned)
    return cleaned


def sanitize_nested(obj: Any) -> Any:
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, Path):
        return to_repo_rel_or_tag(obj)
    if isinstance(obj, dict):
        return {sanitize_text(str(k)): sanitize_nested(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_nested(x) for x in obj]
    return obj


def scan_leaks(text: str) -> list[str]:
    """Return all forbidden path, seat, or private IP rule names matched in `text`."""
    hits: list[str] = []
    if "\x00" in text:
        hits.append("nul_byte")
    for rule_name, pat in FORBIDDEN_PATTERNS:
        if pat.search(text) is not None:
            hits.append(rule_name)
    return hits


def assert_clean_serialized(serialized: str, *, label: str = "payload") -> None:
    if "\x00" in serialized:
        raise ValueError(f"{label}: contains NUL byte")
    for rule_name, pat in FORBIDDEN_PATTERNS:
        m = pat.search(serialized)
        if m is not None:
            snippet = serialized[max(0, m.start() - 20) : min(len(serialized), m.end() + 20)]
            raise ValueError(f"{label}: forbidden pattern {rule_name!r} matched near {snippet!r}")


def write_clean_json_atomic(path: Path, payload: Any) -> str:
    clean_obj = sanitize_nested(payload)
    raw = json.dumps(clean_obj, indent=2, sort_keys=True, allow_nan=False) + "\n"
    assert_clean_serialized(raw, label=path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(path)
    return raw


def append_clean_jsonl(path: Path, row: dict[str, Any]) -> None:
    clean_row = sanitize_nested(row)
    line = json.dumps(clean_row, sort_keys=True, allow_nan=False) + "\n"
    assert_clean_serialized(line, label=path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
