"""Live `llama-server` deterministic evaluation runner (`validation.jsonl` + `S0`-`S3` 18-room Sokoban Eval)."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import tempfile
import time
from typing import Any, Sequence
import urllib.error
import urllib.request

from .domain_oracle import (
    MAX_CELL_TIMEOUT_SEC,
    SokoDomainOracle,
    SokoEvalBudget,
    SokoPlaySession,
    board_sha256_lf,
    execute_sandbox_cell,
    extract_python_cell,
    parse_bare_or_embedded_json,
    sanitize_text,
    verify_route_dual_strict,
)
from .harvester import resolve_default_base_gguf
from .scrub import soko_repo_root, to_repo_rel_or_tag, write_clean_json_atomic


def sha256_file_stream(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def probe_git_head_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    sha = proc.stdout.strip()
    if len(sha) != 40:
        raise RuntimeError(f"Unexpected git HEAD output: {sha!r}")
    return sha


def probe_llama_binary_version(llama_bin: str) -> dict[str, str]:
    proc = subprocess.run(
        [llama_bin, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    combined = (proc.stdout + "\n" + proc.stderr).splitlines()
    vline = next((ln.strip() for ln in combined if "version:" in ln.lower()), "")
    if "commit " not in vline:
        raise RuntimeError(f"Could not parse commit from llama-server --version: {vline!r}")
    commit = vline.split("commit ", 1)[1].rstrip(")").strip()
    return {"version_line": sanitize_text(vline), "commit": commit}


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _render_qwen35_chatml(messages: Sequence[dict[str, str]]) -> str:
    parts: list[str] = []
    for m in messages:
        parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    return "".join(parts)


class LlamaServerHarness:
    """Managed local `llama-server` process with DeltaNet per-slot erase, multi-LoRA scaling, and file logging."""

    def __init__(
        self,
        *,
        base_gguf: Path,
        lora_paths: Sequence[Path] = (),
        llama_bin: str | None = None,
        parallel_slots: int = 8,
        ctx_per_slot: int = 4096,
    ) -> None:
        self.base_gguf = base_gguf.resolve()
        self.lora_paths = [p.resolve() for p in lora_paths]
        self.llama_bin = llama_bin or os.environ.get("LLAMA_SERVER_BIN", "/opt/homebrew/bin/llama-server")
        self.parallel_slots = int(parallel_slots)
        self.ctx_per_slot = int(ctx_per_slot)
        self.port = _pick_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._tmp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._slot_queue: queue.Queue[int] = queue.Queue()
        for sid in range(self.parallel_slots):
            self._slot_queue.put(sid)
        self.server_props: dict[str, Any] = {}

    def __enter__(self) -> "LlamaServerHarness":
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="mde_soko_llama_")
        tmp_root = Path(self._tmp_dir.name)
        slot_dir = tmp_root / "slots"
        slot_dir.mkdir(parents=True, exist_ok=True)
        log_path = tmp_root / "llama_server.log"

        cmd = [
            self.llama_bin,
            "-m",
            str(self.base_gguf),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "-ngl",
            "99",
            "--parallel",
            str(self.parallel_slots),
            "-c",
            str(self.parallel_slots * self.ctx_per_slot),
            "--slots",
            "--no-cache-idle-slots",
            "--slot-prompt-similarity",
            "0.0",
            "--ctx-checkpoints",
            "0",
            "--slot-save-path",
            str(slot_dir),
            "--chat-template-kwargs",
            '{"enable_thinking":false}',
        ]
        if self.lora_paths:
            scaled_arg = ",".join(f"{lp}:0.0" for lp in self.lora_paths)
            cmd.extend(["--lora-scaled", scaled_arg, "--lora-init-without-apply"])

        log_fh = log_path.open("w", encoding="utf-8")
        try:
            self._proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, text=True)
        finally:
            log_fh.close()

        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                err_tail = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
                self.close()
                raise RuntimeError(f"llama-server exited early: {sanitize_text(err_tail)}")
            try:
                with urllib.request.urlopen(f"{self.base_url}/health", timeout=1.5) as resp:
                    if resp.status == 200:
                        with urllib.request.urlopen(f"{self.base_url}/props", timeout=3.0) as presp:
                            raw_props = json.loads(presp.read().decode("utf-8"))
                            self.server_props = {
                                "total_slots": raw_props.get("total_slots"),
                                "chat_template_present": bool(raw_props.get("chat_template")),
                            }
                        return self
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
                _wait_note = str(exc)
            time.sleep(0.25)
        self.close()
        raise RuntimeError("Timed out waiting for llama-server /health")

    def close(self) -> None:
        if self._proc is not None:
            if self._proc.poll() is None:
                self._proc.terminate()
            try:
                self._proc.wait(timeout=8.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=4.0)
            self._proc = None
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()
            self._tmp_dir = None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _post_json(self, url: str, payload: dict[str, Any], timeout: float = 180.0) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 512,
        lora_scales: Sequence[tuple[int, float]] = (),
        top_logprobs: int = 0,
    ) -> dict[str, Any]:
        slot_id = self._slot_queue.get()
        try:
            self._post_json(f"{self.base_url}/slots/{slot_id}?action=erase", {}, timeout=15.0)
            rendered = _render_qwen35_chatml(messages)
            payload: dict[str, Any] = {
                "prompt": rendered,
                "n_predict": int(max_tokens),
                "temperature": 0.0,
                "top_p": 1.0,
                "seed": 20261119,
                "cache_prompt": False,
                "stop": ["<|im_end|>", "<|endoftext|>"],
                "id_slot": slot_id,
                "lora": [{"id": int(idx), "scale": float(sc)} for idx, sc in lora_scales],
            }
            if top_logprobs > 0:
                payload["n_probs"] = int(top_logprobs)
                payload["post_sampling_probs"] = False

            t0 = time.monotonic()
            data = self._post_json(f"{self.base_url}/completion", payload, timeout=180.0)
            wall_ms = (time.monotonic() - t0) * 1000.0
            content = str(data.get("content") or "")
            return {
                "content": content,
                "prompt_tokens": int(data.get("tokens_evaluated", 0)),
                "completion_tokens": int(data.get("tokens_predicted", 0)),
                "wall_ms": round(wall_ms, 2),
                "completion_probabilities": data.get("completion_probabilities"),
            }
        finally:
            self._slot_queue.put(slot_id)


def _extract_step0_logprob_dict(resp: dict[str, Any]) -> tuple[str, float, dict[str, float]]:
    cp_list = resp.get("completion_probabilities")
    if not isinstance(cp_list, list) or not cp_list:
        raise ValueError("Missing or empty completion_probabilities in step0 retention response")
    first_step = cp_list[0]
    top_list = first_step.get("top_logprobs")
    if not isinstance(top_list, list) or not top_list:
        raise ValueError("Empty top_logprobs at step0")

    by_id: dict[str, float] = {}
    for entry in top_list:
        key = str(entry.get("id") if entry.get("id") is not None else entry.get("token"))
        by_id[key] = float(entry["logprob"])
    top1_entry = top_list[0]
    top1_key = str(top1_entry.get("id") if top1_entry.get("id") is not None else top1_entry.get("token"))
    return top1_key, float(top1_entry["logprob"]), by_id


def evaluate_step0_anchor_retention(
    server: LlamaServerHarness,
    anchors: Sequence[dict[str, Any]],
    *,
    lora_id: int,
    lora_scale: float = 1.0,
) -> dict[str, Any]:
    """Measure live `step0` top-1 agreement and exact token-ID logprob delta on `y=0` anchors."""
    if not anchors:
        raise ValueError("Anchor list must be non-empty")

    agree = 0
    abs_deltas: list[float] = []
    for rec in anchors:
        msgs = [{"role": "user", "content": str(rec["prompt"])}]
        r_base = server.chat(msgs, max_tokens=1, lora_scales=(), top_logprobs=10)
        r_arm = server.chat(msgs, max_tokens=1, lora_scales=((lora_id, lora_scale),), top_logprobs=10)
        t_base, lp_base, _map_base = _extract_step0_logprob_dict(r_base)
        t_arm, _lp_arm, map_arm = _extract_step0_logprob_dict(r_arm)
        if t_base == t_arm:
            agree += 1
        if t_base in map_arm:
            abs_deltas.append(abs(lp_base - map_arm[t_base]))
        else:
            min_tail = min(map_arm.values())
            abs_deltas.append(abs(lp_base - min_tail))

    return {
        "n_anchors": len(anchors),
        "step0_top1_agreement_count": agree,
        "step0_top1_agreement_rate": round(agree / float(len(anchors)), 6),
        "mean_abs_top1_logprob_delta": round(sum(abs_deltas) / float(len(abs_deltas)), 6),
        "max_abs_top1_logprob_delta": round(max(abs_deltas), 6),
    }


def compute_lexicographic_eval_score(
    room_rows: Sequence[dict[str, Any]],
    *,
    horizon_keys: int = 240,
    protocol_violations: int = 0,
) -> dict[str, Any]:
    """Lexicographic benchmark score with full-horizon charging on unsolved rooms (`AITrafficControlBench` `#114`).

    1. `qualified` is True iff `protocol_violations == 0` (invalid certificates or sandbox escapes disqualify).
    2. Unsolved or abstained rooms incur `horizon_keys` rather than dropping out of the denominator.
    3. Wall-clock latency is excluded from the replay-verified deterministic tuple (`soko#53` A3).
    """
    n_total = len(room_rows)
    if n_total == 0:
        raise ValueError("room_rows must be non-empty")
    qualified = int(protocol_violations) == 0
    solved_n = 0
    charged_keys_sum = 0
    for r in room_rows:
        is_solved = bool(r.get("solved") or r.get("solved_at_k4"))
        if is_solved:
            solved_n += 1
            charged_keys_sum += int(r.get("route_len", 0))
        else:
            charged_keys_sum += int(horizon_keys)

    return {
        "qualified": qualified,
        "protocol_violations": int(protocol_violations),
        "solved_count": solved_n,
        "total_rooms": n_total,
        "horizon_keys_cap": int(horizon_keys),
        "horizon_charged_total_keys": charged_keys_sum,
        "horizon_charged_mean_keys": round(charged_keys_sum / float(n_total), 4),
        "lexicographic_key": [1 if qualified else 0, solved_n, -charged_keys_sum],
    }


def _ast_structural_hash(code: str) -> str:
    try:
        tree = ast.parse(code)
        dumped = ast.dump(tree, annotate_fields=True, include_attributes=False)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
    except SyntaxError:
        norm = " ".join(code.split())
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _run_s0_or_s1_room(
    server: LlamaServerHarness,
    room: dict[str, Any],
    *,
    lora_scales: Sequence[tuple[int, float]],
) -> dict[str, Any]:
    rid = str(room["room_id"])
    part = int(room["part"])
    grid = [str(r) for r in room["grid"]]
    tut = "; ".join(room.get("tutorial_messages") or []) or "(none)"
    grid_txt = "\n".join(grid)
    prompt = (
        f"Sokoban Eval Room {rid} (Part {part}, {room['width']}x{room['height']})\n"
        f"Tutorial: {tut}\n"
        f"Board:\n{grid_txt}\n\n"
        'Return ONE bare JSON object `{"keys": "..."}` using only U, D, L, R, A so every hero lands on G '
        "on the exact final key with zero hero deaths and zero markdown fences."
    )
    resp = server.chat([{"role": "user", "content": prompt}], max_tokens=256, lora_scales=lora_scales)
    is_bare, parsed = parse_bare_or_embedded_json(resp["content"])
    keys = str(parsed.get("keys", "")) if isinstance(parsed, dict) else ""
    ver = verify_route_dual_strict(part, grid, keys) if (parsed is not None and "keys" in parsed) else {
        "exact_win": False,
        "premature_win": False,
        "alive": False,
        "dual_oracle_parity": True,
        "route_len": 0,
        "steps_executed": 0,
        "failure_rule": "MISSING_JSON_KEYS",
        "failure_message": "Model did not emit JSON keys.",
    }
    return {
        "room_id": rid,
        "part": part,
        "bare_json": bool(is_bare and parsed is not None and "keys" in parsed),
        "solved": bool(ver["exact_win"]),
        "premature_win": bool(ver.get("premature_win", False)),
        "alive": bool(ver.get("alive", False)),
        "failure_rule": str(ver.get("failure_rule", "")),
        "route_len": int(ver.get("route_len", 0)),
        "prompt_tokens": resp["prompt_tokens"],
        "completion_tokens": resp["completion_tokens"],
        "wall_ms": resp["wall_ms"],
    }


def _run_s2_stateful_room(
    server: LlamaServerHarness,
    oracle: SokoDomainOracle,
    room: dict[str, Any],
    *,
    lora_scales: Sequence[tuple[int, float]],
    max_turns: int = 14,
) -> dict[str, Any]:
    rid = str(room["room_id"])
    part = int(room["part"])
    grid = [str(r) for r in room["grid"]]
    tut = "; ".join(room.get("tutorial_messages") or []) or "(none)"
    spec_pack = oracle.retrieve_plane1(
        task_family="H_PROBE",
        prompt_text="\n".join(grid) + " probe step stateful",
        max_tokens=500,
    )
    session = SokoPlaySession(
        room_id=rid,
        budget=SokoEvalBudget(max_replies=max_turns, max_keys=240, max_cells=0),
    )

    sys_msg = (
        "You are operating the stateful Sokoban Eval (`S2`) loop. Reply with ONE bare JSON object per turn:\n"
        '- Probe 1 key reversibly: `{"action": "probe", "key": "R"}`\n'
        '- Execute 1 to 6 keys: `{"action": "step", "keys": "RRU"}` (stop immediately on exact goal completion)\n'
        '- Undo last step: `{"action": "undo"}` or reset: `{"action": "reset"}`\n\n'
        f"Plane 1 Reference:\n{spec_pack['excerpt']}"
    )

    prev_sig = ""
    stagnation_events = 0
    probes_used = 0
    fatal_rollbacks = 0
    total_prompt_toks = 0
    total_comp_toks = 0
    last_feedback = "INITIAL_BOARD"

    for turn_idx in range(max_turns):
        if session.cleared or session.budget.exhausted():
            break
        obs = session.observe()
        cur_sig = f"{obs['traj_fnv64']}:{last_feedback}"
        stag_hint = ""
        if cur_sig == prev_sig and turn_idx > 0:
            stagnation_events += 1
            stag_hint = (
                "\nSTAGNATION WARNING: Board state hash did not advance. Probe an untested orthogonal key "
                "or cycle active hero with `A`."
            )
        prev_sig = cur_sig

        user_msg = (
            f"Room {rid} (Part {part}, Tutorial: {tut}) | Turn {turn_idx + 1}/{max_turns}\n"
            f"Current route len: {obs['current_route_len']} | Keys used: {session.budget.keys_used}/240 | "
            f"Probes used: {probes_used}\n"
            f"Last feedback: {last_feedback}\n"
            f"Current Board:\n{obs['board_ascii']}{stag_hint}\n\n"
            "Emit your next bare JSON action:"
        )
        resp = server.chat(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            max_tokens=160,
            lora_scales=lora_scales,
        )
        total_prompt_toks += resp["prompt_tokens"]
        total_comp_toks += resp["completion_tokens"]

        act_res = session.apply_reply_json(resp["content"])
        act_kind = str(act_res.get("action") or act_res.get("error") or "unknown")
        if act_kind == "probe":
            probes_used += 1
            last_feedback = (
                f"PROBE key={act_res.get('key')} alive={act_res.get('probe_alive')} "
                f"changed={act_res.get('board_changed')}"
            )
        elif act_kind == "step":
            ver_s = act_res.get("verification") or {}
            if not act_res.get("ok"):
                fatal_rollbacks += 1
                last_feedback = f"REJECTED_STEP ({ver_s.get('failure_rule', 'INVALID')}): rolled back safely"
            else:
                last_feedback = f"STEP_OK +{len(str(act_res.get('keys_submitted', '')))} keys"
        else:
            last_feedback = f"ACTION={act_kind}"

    final_ver = verify_route_dual_strict(part, grid, session.current_route) if session.current_route else {
        "exact_win": False,
        "failure_rule": "EMPTY_COMMITTED_ROUTE",
    }
    return {
        "room_id": rid,
        "part": part,
        "solved": bool(session.cleared and final_ver["exact_win"]),
        "turns_used": session.budget.replies_used,
        "probes_used": probes_used,
        "probed_before_commit": probes_used > 0,
        "resets_used": session.budget.restarts_used,
        "fatal_rollbacks": fatal_rollbacks,
        "stagnation_events": stagnation_events,
        "route_len": len(session.current_route),
        "failure_rule": "" if (session.cleared and final_ver["exact_win"]) else str(final_ver.get("failure_rule", "UNSOLVED_BUDGET")),
        "prompt_tokens": total_prompt_toks,
        "completion_tokens": total_comp_toks,
    }


def _run_s3_sandbox_repair_room(
    server: LlamaServerHarness,
    oracle: SokoDomainOracle,
    room: dict[str, Any],
    *,
    lora_scales: Sequence[tuple[int, float]],
    max_cells: int = 4,
) -> dict[str, Any]:
    rid = str(room["room_id"])
    part = int(room["part"])
    grid = [str(r) for r in room["grid"]]
    tut = "; ".join(room.get("tutorial_messages") or []) or "(none)"
    grid_txt = "\n".join(grid)
    spec_pack = oracle.retrieve_plane1(
        task_family="S3",
        prompt_text=grid_txt + " python cell bfs solver",
        max_tokens=680,
    )

    sys_msg = (
        "You are operating the Sokoban Eval (`S3`) 4-second zero-import Python solver loop.\n"
        "Write ONE self-contained ```python ... ``` cell using ONLY Python stdlib (`collections.deque`, `heapq`, `json`).\n"
        "FORBIDDEN imports: `soko_mcp`, `os`, `sys`, `subprocess`, `socket`, `pathlib`, `open`.\n"
        "Your script must finish in < 4.0 seconds and print ONE bare JSON line: `{\"keys\": \"...\"}`.\n\n"
        f"Plane 1 Specification:\n{spec_pack['excerpt']}"
    )

    seen_ast_hashes: set[str] = set()
    seen_fail_sigs: set[str] = set()
    stagnation_events = 0
    stagnation_recovered = False
    had_stagnation = False
    forbidden_imports = 0
    timeouts = 0
    solved_turn: int | None = None
    winning_len = 0
    turn_trace: list[dict[str, Any]] = []
    total_prompt_toks = 0
    total_comp_toks = 0

    feedback_block = ""
    pivot_instruction = ""

    for turn in range(1, max_cells + 1):
        user_msg = (
            f"Room {rid} (Part {part}, {room['width']}x{room['height']}, Tutorial: {tut})\n"
            f"GRID = {grid!r}\n"
            f"Board:\n{grid_txt}\n"
            f"{feedback_block}{pivot_instruction}\n"
            "Write ONE self-contained ```python ... ``` BFS/A* solver cell that prints `{\"keys\": \"...\"}`:"
        )
        resp = server.chat(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            max_tokens=960,
            lora_scales=lora_scales,
        )
        total_prompt_toks += resp["prompt_tokens"]
        total_comp_toks += resp["completion_tokens"]

        code = extract_python_cell(resp["content"])
        failure_rule = ""
        failure_detail = ""
        steps_exec = 0
        ast_h = ""

        if code is not None:
            ast_h = _ast_structural_hash(code)
            sb = execute_sandbox_cell(code, timeout_sec=MAX_CELL_TIMEOUT_SEC)
            if not sb["ok"]:
                if sb.get("timed_out"):
                    timeouts += 1
                if sb.get("ast_rejected"):
                    forbidden_imports += 1
                f0 = sb["findings"][0] if sb["findings"] else {"rule": "CELL_ERROR", "message": sb["stderr"]}
                failure_rule = str(f0["rule"])
                failure_detail = str(f0["message"])
            else:
                _b, parsed_out = parse_bare_or_embedded_json(sb["stdout"])
                if parsed_out is None or "keys" not in parsed_out:
                    failure_rule = "CELL_MISSING_JSON_KEYS"
                    failure_detail = f"Cell stdout did not contain JSON keys. Stdout tail: {sb['stdout'][-140:]!r}"
                else:
                    cand_keys = str(parsed_out["keys"])
                    ver = verify_route_dual_strict(part, grid, cand_keys)
                    steps_exec = int(ver.get("steps_executed", 0))
                    if ver["exact_win"]:
                        solved_turn = turn
                        winning_len = int(ver["route_len"])
                        if had_stagnation:
                            stagnation_recovered = True
                        turn_trace.append({"turn": turn, "passed": True, "route_len": winning_len})
                        break
                    failure_rule = str(ver["failure_rule"])
                    failure_detail = f"{ver['failure_message']} (candidate keys len={len(cand_keys)})"
        else:
            _b, direct_json = parse_bare_or_embedded_json(resp["content"])
            if direct_json is not None and "keys" in direct_json:
                ver = verify_route_dual_strict(part, grid, str(direct_json["keys"]))
                steps_exec = int(ver.get("steps_executed", 0))
                if ver["exact_win"]:
                    solved_turn = turn
                    winning_len = int(ver["route_len"])
                    if had_stagnation:
                        stagnation_recovered = True
                    turn_trace.append({"turn": turn, "passed": True, "route_len": winning_len})
                    break
                failure_rule = str(ver["failure_rule"])
                failure_detail = str(ver["failure_message"])
            else:
                failure_rule = "MISSING_PYTHON_CELL"
                failure_detail = "Response lacked a ```python ... ``` solver cell."

        fail_sig = f"{failure_rule}:{steps_exec}"
        is_stagnant = (bool(ast_h) and ast_h in seen_ast_hashes) or (fail_sig in seen_fail_sigs)
        if ast_h:
            seen_ast_hashes.add(ast_h)
        seen_fail_sigs.add(fail_sig)

        if is_stagnant:
            stagnation_events += 1
            had_stagnation = True
            if failure_rule == "CELL_TIMEOUT_EXCEEDED":
                pivot_instruction = (
                    "\nSTAGNATION PIVOT: Your prior search timed out (>4.0s). Switch strategy immediately: "
                    "use compact tuple states `(active_idx, hero_positions, crate_frozenset)`, deduplicate with a "
                    "`visited` set on enqueue, and prune deadlocked crates pushed into non-goal corners.\n"
                )
            else:
                pivot_instruction = (
                    "\nSTAGNATION PIVOT: Your prior cell repeated the exact same failure signature "
                    f"(`{fail_sig}`). Do NOT re-emit the same transition function: verify ALL-switch door opening "
                    "(`all(p in weighed for p in switches)`), Wizard ray-first Moveable swap, Thief pull from `(x-dx, y-dy)`, "
                    "and exact hero-switch `A` ordering (`1->2->3->4->5->6`).\n"
                )
        else:
            pivot_instruction = ""

        feedback_block = (
            f"\nTurn {turn} Tier 2 Diagnostic [{failure_rule}]: {sanitize_text(failure_detail)}\n"
        )
        turn_trace.append(
            {
                "turn": turn,
                "passed": False,
                "failure_rule": failure_rule,
                "stagnant": is_stagnant,
            }
        )

    last_fail = turn_trace[-1].get("failure_rule", "") if (turn_trace and solved_turn is None) else ""
    return {
        "room_id": rid,
        "part": part,
        "solved": solved_turn is not None,
        "solved_at_k1": solved_turn == 1,
        "solved_at_k2": solved_turn is not None and solved_turn <= 2,
        "solved_at_k4": solved_turn is not None and solved_turn <= 4,
        "solved_turn": solved_turn,
        "route_len": winning_len,
        "stagnation_events": stagnation_events,
        "stagnation_recovered": stagnation_recovered,
        "forbidden_import_rejections": forbidden_imports,
        "cell_timeouts": timeouts,
        "final_failure_rule": last_fail,
        "turns": turn_trace,
        "prompt_tokens": total_prompt_toks,
        "completion_tokens": total_comp_toks,
    }


def run_full_soko_live_evaluation(
    *,
    repo_root: Path | None = None,
    base_gguf: Path | None = None,
    parallel_slots: int = 8,
) -> dict[str, Any]:
    """Run live `validation.jsonl` (`16` items + `24` step0 anchors) and 18-room `S0`-`S3` Sokoban Eval."""
    root = (repo_root or soko_repo_root()).resolve()
    gguf_path = (base_gguf or resolve_default_base_gguf(root)).resolve()
    p2a_gguf = root / "mde_soko" / "artifacts" / "p2a" / "soko-eval.p2a.f16.gguf"
    p2b_gguf = root / "mde_soko" / "artifacts" / "p2b" / "soko-eval.p2b.f16.gguf"

    git_head = probe_git_head_sha(root)
    base_sha = sha256_file_stream(gguf_path)
    p2a_sha = sha256_file_stream(p2a_gguf)
    p2b_sha = sha256_file_stream(p2b_gguf)

    llama_bin = os.environ.get("LLAMA_SERVER_BIN", "/opt/homebrew/bin/llama-server")
    bin_info = probe_llama_binary_version(llama_bin)

    oracle = SokoDomainOracle(repo_root=root)
    ds_dir = root / "mde_soko" / "datasets"
    val_items = [json.loads(ln) for ln in (ds_dir / "validation.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    k0_items = [json.loads(ln) for ln in (ds_dir / "hybrid_k0.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    y0_anchors = [r for r in k0_items if bool(r.get("y0"))]
    bench_18 = json.loads((ds_dir / "benchmark_18_rooms.json").read_text(encoding="utf-8"))["rooms"]

    with LlamaServerHarness(
        base_gguf=gguf_path,
        lora_paths=(p2a_gguf, p2b_gguf),
        llama_bin=llama_bin,
        parallel_slots=parallel_slots,
    ) as server:
        # 1. Public validation.jsonl (16 items): B0 vs P2-A vs P2-B
        def _eval_val_arm(scales: Sequence[tuple[int, float]]) -> dict[str, Any]:
            def _one(item: dict[str, Any]) -> dict[str, Any]:
                max_t = 768 if item["family"] == "H_CELL" else 256
                r = server.chat([{"role": "user", "content": str(item["prompt"])}], max_tokens=max_t, lora_scales=scales)
                g = oracle.grade_item(item, r["content"])
                return {
                    "id": item["id"],
                    "room_id": item["room_id"],
                    "family": item["family"],
                    "passed": bool(g["passed"]),
                    "wall_ms": r["wall_ms"],
                }

            with ThreadPoolExecutor(max_workers=parallel_slots) as pool:
                rows = list(pool.map(_one, val_items))
            passed_n = sum(1 for x in rows if x["passed"])
            by_fam: dict[str, dict[str, int]] = {}
            for x in rows:
                st = by_fam.setdefault(x["family"], {"passed": 0, "total": 0})
                st["total"] += 1
                if x["passed"]:
                    st["passed"] += 1
            return {
                "passed": passed_n,
                "total": len(rows),
                "pass_rate": round(passed_n / float(len(rows)), 6),
                "by_family": by_fam,
                "items": rows,
            }

        val_b0 = _eval_val_arm(())
        val_p2a = _eval_val_arm(((0, 1.0),))
        val_p2b = _eval_val_arm(((1, 1.0),))

        ret_p2a = evaluate_step0_anchor_retention(server, y0_anchors, lora_id=0, lora_scale=1.0)
        ret_p2b = evaluate_step0_anchor_retention(server, y0_anchors, lora_id=1, lora_scale=1.0)

        # 2. Frozen 18-room original trilogy benchmark: S0, S1, S2, S3
        with ThreadPoolExecutor(max_workers=parallel_slots) as pool:
            s0_rows = list(pool.map(lambda r: _run_s0_or_s1_room(server, r, lora_scales=()), bench_18))
            s1_rows = list(pool.map(lambda r: _run_s0_or_s1_room(server, r, lora_scales=((1, 1.0),)), bench_18))
            s2_rows = list(pool.map(lambda r: _run_s2_stateful_room(server, oracle, r, lora_scales=((1, 1.0),)), bench_18))
            s3_rows = list(pool.map(lambda r: _run_s3_sandbox_repair_room(server, oracle, r, lora_scales=((1, 1.0),)), bench_18))

        props_snap = dict(server.server_props)

    def _summarize_open(rows: list[dict[str, Any]]) -> dict[str, Any]:
        solved = [r["room_id"] for r in rows if r["solved"]]
        bare = sum(1 for r in rows if r["bare_json"])
        fail_hist: dict[str, int] = {}
        for r in rows:
            if not r["solved"] and r["failure_rule"]:
                fail_hist[r["failure_rule"]] = fail_hist.get(r["failure_rule"], 0) + 1
        return {
            "solved_count": len(solved),
            "total_rooms": len(rows),
            "solved_rate": round(len(solved) / float(len(rows)), 6),
            "solved_rooms": solved,
            "bare_json_count": bare,
            "bare_json_rate": round(bare / float(len(rows)), 6),
            "lexicographic_score": compute_lexicographic_eval_score(rows, horizon_keys=240, protocol_violations=0),
            "failure_histogram": fail_hist,
            "rooms": rows,
        }

    s2_solved = [r["room_id"] for r in s2_rows if r["solved"]]
    s2_probed = sum(1 for r in s2_rows if r["probed_before_commit"])
    s2_summary = {
        "solved_count": len(s2_solved),
        "total_rooms": len(s2_rows),
        "solved_rate": round(len(s2_solved) / float(len(s2_rows)), 6),
        "solved_rooms": s2_solved,
        "probed_rooms_count": s2_probed,
        "probed_rooms_rate": round(s2_probed / float(len(s2_rows)), 6),
        "total_fatal_rollbacks_recovered": sum(int(r["fatal_rollbacks"]) for r in s2_rows),
        "total_stagnation_events": sum(int(r["stagnation_events"]) for r in s2_rows),
        "lexicographic_score": compute_lexicographic_eval_score(s2_rows, horizon_keys=240, protocol_violations=0),
        "rooms": s2_rows,
    }

    s3_k1 = [r["room_id"] for r in s3_rows if r["solved_at_k1"]]
    s3_k2 = [r["room_id"] for r in s3_rows if r["solved_at_k2"]]
    s3_k4 = [r["room_id"] for r in s3_rows if r["solved_at_k4"]]
    s3_fail_hist: dict[str, int] = {}
    for r in s3_rows:
        for t in r["turns"]:
            if not t.get("passed") and t.get("failure_rule"):
                fr = str(t["failure_rule"])
                s3_fail_hist[fr] = s3_fail_hist.get(fr, 0) + 1
    s3_forb = sum(int(r["forbidden_import_rejections"]) for r in s3_rows)
    s3_summary = {
        "solved_at_k1_count": len(s3_k1),
        "solved_at_k2_count": len(s3_k2),
        "solved_at_k4_count": len(s3_k4),
        "total_rooms": len(s3_rows),
        "solved_at_k1_rate": round(len(s3_k1) / float(len(s3_rows)), 6),
        "solved_at_k2_rate": round(len(s3_k2) / float(len(s3_rows)), 6),
        "solved_at_k4_rate": round(len(s3_k4) / float(len(s3_rows)), 6),
        "solved_rooms_k1": s3_k1,
        "solved_rooms_k2": s3_k2,
        "solved_rooms_k4": s3_k4,
        "total_stagnation_events": sum(int(r["stagnation_events"]) for r in s3_rows),
        "stagnation_recoveries": sum(1 for r in s3_rows if r["stagnation_recovered"]),
        "forbidden_import_rejections": s3_forb,
        "cell_timeouts": sum(int(r["cell_timeouts"]) for r in s3_rows),
        "lexicographic_score": compute_lexicographic_eval_score(s3_rows, horizon_keys=240, protocol_violations=0),
        "turn_failure_histogram": s3_fail_hist,
        "rooms": s3_rows,
    }

    receipt = {
        "schema": "mde-soko-eval-receipt/v0.1",
        "domain_id": "mde:soko-eval",
        "provenance": {
            "git_head_sha": git_head,
            "base_gguf_filename": gguf_path.name,
            "base_gguf_sha256": base_sha,
            "p2a_lora_relpath": to_repo_rel_or_tag(p2a_gguf, repo_root=root),
            "p2a_lora_sha256": p2a_sha,
            "p2b_lora_relpath": to_repo_rel_or_tag(p2b_gguf, repo_root=root),
            "p2b_lora_sha256": p2b_sha,
            "llama_server_version": bin_info["version_line"],
            "llama_server_commit": bin_info["commit"],
            "server_props": props_snap,
            "sampling": {"temperature": 0.0, "top_p": 1.0, "seed": 20261119, "thinking": False},
        },
        "validation_16": {
            "B0": val_b0,
            "P2-A": val_p2a,
            "P2-B": val_p2b,
        },
        "step0_y0_anchor_retention": {
            "P2-A_vs_B0": ret_p2a,
            "P2-B_vs_B0": ret_p2b,
        },
        "benchmark_18_trilogy": {
            "S0_b0_open_loop": _summarize_open(s0_rows),
            "S1_p2b_open_loop": _summarize_open(s1_rows),
            "S2_p2b_stateful_probe_loop": s2_summary,
            "S3_p2b_plane1_python_cell_repair": s3_summary,
        },
    }
    res_dir = root / "mde_soko" / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    write_clean_json_atomic(res_dir / "soko_eval_live_receipt.json", receipt)
    return receipt
