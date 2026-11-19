"""Standalone vendored prose & duplicate-block hygiene gate (`#95`, zero `~/.hermes` runtime dependency)."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Sequence

from .scrub import scan_leaks

AI_TELL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("em_dash", re.compile("\u2014")),
    ("delve", re.compile(r"\bdelve(?:s|d|ing)?\b", re.IGNORECASE)),
    ("tapestry", re.compile(r"\btapestry\b", re.IGNORECASE)),
    ("testament_to", re.compile(r"\btestament\s+to\b", re.IGNORECASE)),
    ("crucial_pivotal", re.compile(r"\b(?:pivotal|indelible|underscores)\b", re.IGNORECASE)),
    ("not_only_but_also", re.compile(r"\bnot\s+only\b.{1,100}\bbut\s+also\b", re.IGNORECASE)),
    ("its_worth_noting", re.compile(r"\bit(?:'s|\s+is)\s+worth\s+noting\b", re.IGNORECASE)),
    ("announcement_frame", re.compile(r"\b(?:we\s+are\s+excited\s+to|thrilled\s+to\s+announce)\b", re.IGNORECASE)),
)

MAX_PROSE_LINE_CHARS = 420


def check_markdown_text(
    text: str,
    *,
    label: str = "<markdown>",
    check_dupes: bool = True,
) -> list[dict[str, object]]:
    """Audit markdown prose for em dashes, AI-tell phrases, >420-char paragraphs, leaks, and duplicate blocks."""
    findings: list[dict[str, object]] = []

    for leak in scan_leaks(text):
        findings.append({"file": label, "line": 1, "rule": "leak_pattern", "detail": leak})

    in_fence = False
    seen_headings: dict[str, int] = {}
    seen_paragraphs: dict[str, int] = {}

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for rule_name, pat in AI_TELL_PATTERNS:
            if pat.search(raw_line):
                findings.append(
                    {
                        "file": label,
                        "line": lineno,
                        "rule": rule_name,
                        "detail": stripped[:120],
                    }
                )

        if not stripped.startswith("|") and len(raw_line) > MAX_PROSE_LINE_CHARS:
            findings.append(
                {
                    "file": label,
                    "line": lineno,
                    "rule": "prose_line_too_long",
                    "detail": f"{len(raw_line)} chars > {MAX_PROSE_LINE_CHARS}",
                }
            )

        if check_dupes and stripped:
            if stripped.startswith("#"):
                norm_h = re.sub(r"\s+", " ", stripped.lower())
                if norm_h in seen_headings:
                    findings.append(
                        {
                            "file": label,
                            "line": lineno,
                            "rule": "duplicate_heading",
                            "detail": f"Repeats line {seen_headings[norm_h]}: {stripped[:80]}",
                        }
                    )
                else:
                    seen_headings[norm_h] = lineno
            elif not stripped.startswith(("|", "-", "*", ">", "1.", "2.", "3.")):
                norm_p = re.sub(r"\s+", " ", stripped.lower())
                if len(norm_p) >= 60:
                    if norm_p in seen_paragraphs:
                        findings.append(
                            {
                                "file": label,
                                "line": lineno,
                                "rule": "duplicate_paragraph",
                                "detail": f"Repeats line {seen_paragraphs[norm_p]}: {stripped[:80]}",
                            }
                        )
                    else:
                        seen_paragraphs[norm_p] = lineno

    return findings


def check_markdown_files(paths: Sequence[Path], *, check_dupes: bool = True) -> list[dict[str, object]]:
    all_findings: list[dict[str, object]] = []
    for p in paths:
        txt = p.read_text(encoding="utf-8")
        all_findings.extend(check_markdown_text(txt, label=p.name, check_dupes=check_dupes))
    return all_findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone prose & duplicate-block hygiene gate.")
    parser.add_argument("files", nargs="+", type=Path, help="Markdown files to check.")
    parser.add_argument("--dupes", action="store_true", help="Also fail on duplicate headings/paragraphs.")
    args = parser.parse_args(argv)

    findings = check_markdown_files(args.files, check_dupes=bool(args.dupes or True))
    if findings:
        for f in findings:
            sys.stderr.write(f"[prose_gate] {f['file']}:{f['line']} [{f['rule']}] {f['detail']}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
