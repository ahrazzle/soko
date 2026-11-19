"""Standalone `pytest + numpy` verification suite for `mde_soko` (`python3 -O -B -m pytest` safe, zero bare asserts)."""

from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from soko_mcp.catalog import get_room, list_rooms
from soko_mcp.integrity import verify_source_manifest

from mde_soko import (
    FixedRadixCertificate,
    PRE_REGISTERED_GATE_POLICY,
    SokoDomainOracle,
    SokoEvalBudget,
    SokoPlaySession,
    audit_soko_certificate,
    audit_zero_import_cell,
    board_sha256_lf,
    execute_sandbox_cell,
    verify_route_dual_strict,
    verify_soko_lineage,
    verify_wfsl_slab,
    verify_zero_byte_rederivation,
)
from mde_soko.compiler import load_strict_certificate_json
from mde_soko.datasets_builder import verify_soko_datasets_integrity
from mde_soko.prose_gate import check_markdown_files, check_markdown_text
from mde_soko.runner import compute_lexicographic_eval_score
from mde_soko.scrub import scan_leaks

REPO_ROOT = Path(__file__).resolve().parents[1]
MDE_DIR = REPO_ROOT / "mde_soko"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_locked_soko_tcb_and_plane1_lineage() -> None:
    tcb = verify_source_manifest(REPO_ROOT, REPO_ROOT / "SHA256SUMS")
    _require(bool(tcb["source_integrity_verified"]), f"Locked soko SHA256SUMS integrity failed: {tcb}")
    _require(int(tcb["files_verified"]) == 21, f"Expected 21 locked TCB files, got {tcb['files_verified']}")

    lin = verify_soko_lineage(repo_root=REPO_ROOT)
    _require(bool(lin["ok"]), f"mde_soko Plane 1 lineage verification failed: {lin}")


def test_disjoint_66_room_partition_and_zero_spoiler_benchmark() -> None:
    ds_ver = verify_soko_datasets_integrity(repo_root=REPO_ROOT)
    _require(bool(ds_ver["ok"]), f"Datasets SHA256SUMS mismatch: {ds_ver}")

    ds_dir = MDE_DIR / "datasets"
    bench = json.loads((ds_dir / "benchmark_18_rooms.json").read_text(encoding="utf-8"))
    comp_rows = [json.loads(ln) for ln in (ds_dir / "compile.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    val_rows = [json.loads(ln) for ln in (ds_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]

    bench_ids = {r["room_id"] for r in bench["rooms"]}
    comp_ids = {r["room_id"] for r in comp_rows}
    val_ids = {r["room_id"] for r in val_rows}
    all_catalog_ids = {r["id"] for r in list_rooms()}

    _require(len(bench_ids) == 18, f"Expected 18 benchmark rooms, got {len(bench_ids)}")
    _require(len(comp_ids) == 32, f"Expected 32 compile rooms, got {len(comp_ids)}")
    _require(len(val_ids) == 16, f"Expected 16 validation rooms, got {len(val_ids)}")
    _require(len(bench_ids & comp_ids) == 0, "Overlap between benchmark and compile splits")
    _require(len(bench_ids & val_ids) == 0, "Overlap between benchmark and validation splits")
    _require(len(comp_ids & val_ids) == 0, "Overlap between compile and validation splits")
    _require((bench_ids | comp_ids | val_ids) == all_catalog_ids, "Splits do not cover exact 66 trilogy rooms")

    for room_entry in bench["rooms"]:
        _require("reference_route" not in room_entry, f"Spoiler route leaked in {room_entry['room_id']}")
        _require("keys" not in room_entry, f"Spoiler keys leaked in {room_entry['room_id']}")

    iii14 = next(r for r in bench["rooms"] if r["room_id"] == "III-14")
    _require(
        iii14["board_sha256_lf"] == "300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c",
        f"Unexpected III-14 canonical board_sha256_lf: {iii14['board_sha256_lf']}",
    )

    oracle = SokoDomainOracle(repo_root=REPO_ROOT)
    for row in comp_rows + val_rows:
        pos_res = oracle.grade_item(row, row["positive_completion"])
        _require(bool(pos_res["passed"]), f"Gold completion failed on {row['id']}: {pos_res}")
        neg_res = oracle.grade_item(row, row["negative_completion"])
        _require(not bool(neg_res["passed"]), f"Negative completion passed on {row['id']}")


def test_domain_oracle_label_free_inference_and_dual_semantics() -> None:
    oracle = SokoDomainOracle(repo_root=REPO_ROOT)
    r_i1 = get_room("I-1")
    grid_i1 = [str(x) for x in r_i1["grid"]]

    exact_8 = verify_route_dual_strict(1, grid_i1, "RRRRRRRR")
    _require(bool(exact_8["exact_win"]) and bool(exact_8["dual_oracle_parity"]), f"I-1 8-key win failed: {exact_8}")

    overstep_9 = verify_route_dual_strict(1, grid_i1, "RRRRRRRRR")
    _require(not bool(overstep_9["exact_win"]) and bool(overstep_9["premature_win"]), "I-1 9-key overstep must fail")

    val_rows = [
        json.loads(ln)
        for ln in (MDE_DIR / "datasets" / "validation.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    rule_item = next(r for r in val_rows if r["family"] == "H_RULE")
    true_reply = json.dumps(
        {"bug_id": rule_item["planted_bug_id"], "diverges_on_probe": True, "epistemic_tier": "VERIFIED"}
    )
    false_reply = json.dumps(
        {"bug_id": rule_item["planted_bug_id"], "diverges_on_probe": False, "epistemic_tier": "VERIFIED"}
    )
    inf_true = oracle.grade_candidate(rule_item, true_reply)
    inf_false = oracle.grade_candidate(rule_item, false_reply)
    _require(
        inf_true.passed and inf_false.passed,
        "Inference-time grade_candidate must remain label-free on H_RULE boolean while enforcing tier & schema",
    )
    eval_true = oracle.grade_item(rule_item, true_reply)["passed"]
    eval_false = oracle.grade_item(rule_item, false_reply)["passed"]
    _require(eval_true != eval_false, "Post-hoc grade_item must distinguish true vs false divergence")

    ctx = oracle.retrieve_plane1_context({"family": "S3", "prompt": "Bard Druid switch"}, max_tokens=500)
    _require(len(ctx) > 50, "Expected non-empty Plane 1 excerpt")


def test_stateful_play_session_and_zero_import_sandbox() -> None:
    r_i1 = get_room("I-1")
    sess = SokoPlaySession(room_id="I-1", budget=SokoEvalBudget(max_replies=8, max_keys=80, max_cells=0))
    obs0 = sess.observe()
    _require(board_sha256_lf(obs0["board_ascii"].splitlines()) == board_sha256_lf(r_i1["grid"]), "Board hash mismatch")

    p1 = sess.apply_reply_json('{"action": "probe", "key": "R"}')
    _require(bool(p1["ok"]) and p1["action"] == "probe" and sess.current_route == "", f"Bad probe: {p1}")

    s1 = sess.apply_reply_json('{"action": "step", "keys": "RRRRRRRR"}')
    _require(bool(s1["cleared"]) and sess.current_route == "RRRRRRRR", f"Stateful I-1 solve failed: {s1}")

    # Chunk-segmentation invariance (#116 eumemic/stdhttp-verify read_split/pull_split):
    # stepping u="RRR" then v="RRRRR" matches terminal trajectory digest of single-shot u+v="RRRRRRRR"
    seg_sess = SokoPlaySession(room_id="I-1", budget=SokoEvalBudget(max_replies=8, max_keys=80, max_cells=0))
    seg_sess.apply_reply_json('{"action": "step", "keys": "RRR"}')
    seg_sess.apply_reply_json('{"action": "step", "keys": "RRRRR"}')
    obs_seg = seg_sess.observe()
    full_ver = verify_route_dual_strict(1, r_i1["grid"], "RRRRRRRR")
    _require(
        obs_seg["traj_fnv64"] == full_ver["traj_fnv64"] and obs_seg["board_ascii"] == full_ver["final_ascii"],
        "Stateful chunk-segmentation desynchronized from terminal dual-oracle replay",
    )

    _require(len(audit_zero_import_cell("from soko_mcp.catalog import get_room\n")) >= 1, "Must block soko_mcp import")
    _require(len(audit_zero_import_cell("import os\n")) >= 1, "Must block os import")
    _require(len(audit_zero_import_cell("open('SHA256SUMS')\n")) >= 1, "Must block open() call")
    _require(len(audit_zero_import_cell("().__class__.__base__.__subclasses__()\n")) >= 1, "Must block dunders")

    t0 = time.monotonic()
    to_res = execute_sandbox_cell("while True:\n    pass\n", timeout_sec=0.6)
    elapsed = time.monotonic() - t0
    _require(bool(to_res["timed_out"]) and not bool(to_res["ok"]) and elapsed < 3.0, f"Timeout failed: {to_res}")

    bfs_cell = (
        "from collections import deque\nimport json\n"
        f"grid = {r_i1['grid']!r}\n"
        "fx, fy = next((x, y) for y, r in enumerate(grid) for x, c in enumerate(r) if c == 'F')\n"
        "gx, gy = next((x, y) for y, r in enumerate(grid) for x, c in enumerate(r) if c == 'G')\n"
        "q = deque([(fx, fy, '')])\nseen = {(fx, fy)}\nans = ''\n"
        "while q:\n"
        "    x, y, p = q.popleft()\n"
        "    if (x, y) == (gx, gy):\n        ans = p; break\n"
        "    for k, (dx, dy) in [('U',(0,-1)),('D',(0,1)),('L',(-1,0)),('R',(1,0))]:\n"
        "        nx, ny = x + dx, y + dy\n"
        "        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] != '#' and (nx, ny) not in seen:\n"
        "            seen.add((nx, ny)); q.append((nx, ny, p + k))\n"
        "print(json.dumps({'keys': ans}))\n"
    )
    ok_cell = execute_sandbox_cell(bfs_cell, timeout_sec=3.0)
    _require(bool(ok_cell["ok"]) and json.loads(ok_cell["stdout"])["keys"] == "RRRRRRRR", f"BFS cell failed: {ok_cell}")


def test_f01_through_f08_certificate_soundness_detectors() -> None:
    valid_cert = {
        "epistemic_status": "VERIFIED",
        "differential_match": True,
        "oracles_checked": ["PuzzleScriptOracle", "FlatBitmaskOracle"],
        "state_hash_mode": "full_canonical_tuple",
        "includes_hidden_state": True,
        "tcb_pins": {
            "tcb_manifest_verified": True,
            "checker_auditor_py_sha256": "a" * 64,
        },
        "proven_floor": 8,
        "exact_optimum_reached": True,
        "witness_route": "RRRRRRRR",
        "step_consistency_violations": 0,
        "witness_or_proof_sha256": "b" * 64,
    }
    clean_audit = audit_soko_certificate(valid_cert)
    _require(bool(clean_audit["passed"]), f"Valid certificate rejected: {clean_audit}")

    corruptions = [
        ("F01", {**valid_cert, "oracles_checked": ["PuzzleScriptOracle"]}),
        ("F02", {**valid_cert, "state_hash_mode": "ascii_only"}),
        ("F03", {**valid_cert, "tcb_pins": {"tcb_manifest_verified": False, "checker_auditor_py_sha256": ""}}),
        ("F04", {**valid_cert, "witness_route": "", "exact_optimum_reached": False}),
        ("F05", {**valid_cert, "step_consistency_violations": 2}),
        ("F06", {**valid_cert, "proof_mode": "inductive_potential", "complete_space": False}),
        ("F07", {**valid_cert, "epistemic_status": "PROVEN", "impl_invariant_checked": False}),
        ("F08", {**valid_cert, "witness_or_proof_sha256": "ab"}),
    ]
    for prefix, bad_cert in corruptions:
        res = audit_soko_certificate(bad_cert)
        _require(
            (not bool(res["passed"])) and any(str(f["rule"]).startswith(prefix) for f in res["findings"]),
            f"Expected {prefix} rejection, got {res}",
        )


def test_independent_9_of_9_zero_byte_rederivation_and_gate_separation(tmp_path: Path) -> None:
    npz_path = MDE_DIR / "artifacts" / "harvested_soko_activations.npz"
    _require(npz_path.is_file() and npz_path.stat().st_size < 1_048_576, "NPZ missing or >= 1 MiB")

    p2b_dir = MDE_DIR / "artifacts" / "p2b"
    red = verify_zero_byte_rederivation(
        expected_dir=p2b_dir,
        rederive_dir=tmp_path / "rederived_p2b",
        activations_npz=npz_path,
        repo_root=REPO_ROOT,
    )
    _require(bool(red["zero_byte_diff_all"]) and int(red["checked_count"]) == 9, f"Re-derivation failed: {red}")

    binding = json.loads((p2b_dir / "soko-eval.p2b.binding.json").read_text(encoding="utf-8"))
    for slab_name in ("soko-eval.p2b.f16.wfsl", "soko-eval.p2b.int4_int8.wfsl", "soko-eval.p2b.int4_f16.wfsl"):
        ok_s, probs_s = verify_wfsl_slab(
            p2b_dir / slab_name,
            gate_policy=PRE_REGISTERED_GATE_POLICY,
            expected_zone_manifest_id=binding["zone_manifest_id"],
            expected_base_weights_sha256=binding["base_weights_sha256"],
        )
        _require(ok_s, f"Slab {slab_name} failed pre-registered GatePolicy: {probs_s}")

    p2a_cert = FixedRadixCertificate(
        **json.loads((MDE_DIR / "artifacts" / "p2a" / "soko-eval.p2a.certificate.json").read_text(encoding="utf-8"))
    )
    ok_p2a, probs_p2a = p2a_cert.verify_division_free(PRE_REGISTERED_GATE_POLICY)
    _require((not ok_p2a) and ("leakage_energy_exceeds_cap" in probs_p2a), f"P2-A must fail leakage gate: {probs_p2a}")

    sab_cert = load_strict_certificate_json(
        (MDE_DIR / "artifacts" / "controls" / "soko-eval.sabotage.certificate.json").read_text(encoding="utf-8")
    )
    ok_sab, probs_sab = sab_cert.verify_division_free(PRE_REGISTERED_GATE_POLICY)
    _require((not ok_sab) and ("safety_dot_sq_exceeds_cap" in probs_sab), f"Sabotage must fail safety gate: {probs_sab}")

    # Strict parse-time certificate guard (#116 CrocSwap/integer-mult-bounds): reject duplicate keys, floats, and bool-as-int
    with pytest.raises(ValueError):
        load_strict_certificate_json('{"a": 1, "a": 2}')
    with pytest.raises(ValueError):
        load_strict_certificate_json('{"frobenius_sq_scaled": 1.5}')
    bool_cert = FixedRadixCertificate(
        factor_digest="a" * 64,
        quant_dtype="f16",
        projector_epoch=True,  # type: ignore[arg-type]
        radix_scale_exp2=24,
        frobenius_sq_scaled=1,
        spectral_norm_sq_scaled=1,
        leakage_energy_scaled=1,
        max_safety_dot_sq_scaled=0,
    )
    ok_bool, probs_bool = bool_cert.verify_division_free(PRE_REGISTERED_GATE_POLICY)
    _require((not ok_bool) and "non_strict_int_field:projector_epoch" in probs_bool, "Must reject bool subclass of int")


def test_vendored_prose_gate_and_zero_path_ip_leaks() -> None:
    # Verify lexicographic gate + unsolved horizon charging (#114 AITrafficControlBench pattern)
    honest_rows = [{"solved": True, "route_len": 8}, {"solved": False, "route_len": 0}]
    disqualified_rows = [{"solved": True, "route_len": 4}, {"solved": True, "route_len": 4}]
    s_honest = compute_lexicographic_eval_score(honest_rows, horizon_keys=240, protocol_violations=0)
    s_disq = compute_lexicographic_eval_score(disqualified_rows, horizon_keys=240, protocol_violations=1)
    _require(
        s_honest["horizon_charged_total_keys"] == 248 and s_honest["lexicographic_key"] > s_disq["lexicographic_key"],
        f"Lexicographic horizon gate failed: {s_honest} vs {s_disq}",
    )

    bad = check_markdown_text("We are excited to announce \u2014 delve into this tapestry.", check_dupes=True)
    _require(len(bad) >= 3, f"Prose gate failed to detect planted tells: {bad}")

    md_files = sorted(MDE_DIR.rglob("*.md"))
    _require(len(md_files) >= 1, "Expected markdown files under mde_soko/")
    findings = check_markdown_files(md_files, check_dupes=True)
    _require(len(findings) == 0, f"Prose gate findings in mde_soko/*.md: {findings}")

    text_exts = {".py", ".md", ".json", ".jsonl", ".gitattributes"}
    for fpath in sorted(MDE_DIR.rglob("*")):
        if fpath.is_file() and (fpath.suffix in text_exts or fpath.name in ("SHA256SUMS", ".gitattributes")):
            leaks = scan_leaks(fpath.read_text(encoding="utf-8"))
            _require(len(leaks) == 0, f"Forbidden path/IP leak in {fpath.relative_to(REPO_ROOT)}: {leaks}")

    with pytest.raises(AssertionError):
        _require(False, "verify _require helper raises AssertionError under python -O")
