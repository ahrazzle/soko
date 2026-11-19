"""Self-contained CPU `float64` `BetaEdit` null-space compiler, GGUF v3 LoRA emitter, and integer certificate verifier for `mde:soko-eval`."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .lineage import compute_soko_plane1_lineage
from .scrub import soko_repo_root, to_repo_rel_or_tag, write_clean_json_atomic

GGUF_MAGIC = b"GGUF"
GGUF_VERSION = 3
GGUF_ALIGNMENT = 32
GGML_TYPE_F16 = 1

GGUF_VAL_UINT32 = 4
GGUF_VAL_FLOAT32 = 6
GGUF_VAL_STRING = 8

WFSL_MAGIC = b"WFSL\x00\x01"
TARGET_TENSOR_GGUF = "blk.31.ffn_up.weight"
TARGET_TENSOR_ST = "model.language_model.layers.31.mlp.up_proj.weight"
PROJECTOR_EPOCH = 1
WMCP_LINEAGE_VENDOR_KEY = "com.siliconcordat.warp.lineage/v1"


@dataclass(frozen=True)
class GatePolicy:
    max_frob_sq_num: int
    max_frob_sq_den: int = 100
    max_spectral_sq_num: int = 1000
    max_spectral_sq_den: int = 100
    max_leakage_num: int = 50000
    max_leakage_den: int = 1000
    max_safety_dot_sq_num: int = 500
    max_safety_dot_sq_den: int = 10000


# Fixed pre-registered Stage 2 certificate policy (never self-calibrated from compiled factors).
PRE_REGISTERED_GATE_POLICY = GatePolicy(
    max_frob_sq_num=2500,        # ||dW||_F^2 <= 25.00
    max_frob_sq_den=100,
    max_spectral_sq_num=1800,    # ||dW||_2^2 <= 18.00
    max_spectral_sq_den=100,
    max_leakage_num=35000,       # Tr(dW C_K0 dW^T) <= 35.000
    max_leakage_den=1000,
    max_safety_dot_sq_num=50,    # max_s <dW, S_s>^2 / ||S_s||_F^2 <= 5e-4
    max_safety_dot_sq_den=100000,
)

P2B_EXPECTED_FILES: tuple[str, ...] = (
    "soko-eval.p2b.f16.gguf",
    "soko-eval.p2b.f16.wfsl",
    "soko-eval.p2b.int4_int8.wfsl",
    "soko-eval.p2b.int4_f16.wfsl",
    "soko-eval.p2b.certificate.json",
    "soko-eval.p2b.binding.json",
    "soko-eval.p2b.gate_policy.json",
    "soko-eval.p2b.warp_bundle.json",
    "soko-eval.p2b.wmcp_meta.json",
)


@dataclass(frozen=True)
class FixedRadixCertificate:
    """Division-free integer post-quantization certificate (`radix_scale_exp2 = 24`)."""

    factor_digest: str
    quant_dtype: str
    projector_epoch: int
    radix_scale_exp2: int
    frobenius_sq_scaled: int
    spectral_norm_sq_scaled: int
    leakage_energy_scaled: int
    max_safety_dot_sq_scaled: int

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def verify_division_free(self, policy: GatePolicy) -> tuple[bool, list[str]]:
        problems: list[str] = []
        for fname in (
            "projector_epoch",
            "radix_scale_exp2",
            "frobenius_sq_scaled",
            "spectral_norm_sq_scaled",
            "leakage_energy_scaled",
            "max_safety_dot_sq_scaled",
        ):
            val = getattr(self, fname)
            if type(val) is not int or abs(val) > 10**60:
                problems.append(f"non_strict_int_field:{fname}")
        if problems:
            return False, problems
        scale = 1 << self.radix_scale_exp2
        if self.frobenius_sq_scaled * policy.max_frob_sq_den > policy.max_frob_sq_num * scale:
            problems.append("frobenius_sq_exceeds_cap")
        if self.spectral_norm_sq_scaled * policy.max_spectral_sq_den > policy.max_spectral_sq_num * scale:
            problems.append("spectral_norm_sq_exceeds_cap")
        if self.leakage_energy_scaled * policy.max_leakage_den > policy.max_leakage_num * scale:
            problems.append("leakage_energy_exceeds_cap")
        if self.max_safety_dot_sq_scaled * policy.max_safety_dot_sq_den > policy.max_safety_dot_sq_num * scale:
            problems.append("safety_dot_sq_exceeds_cap")
        return len(problems) == 0, problems


def load_strict_certificate_json(raw_json: str) -> FixedRadixCertificate:
    """Parse certificate JSON rejecting floats, NaN/Infinity, duplicate keys, and bool-as-int (`#116`)."""

    def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"Duplicate JSON key in certificate: {k!r}")
            out[k] = v
        return out

    def _no_float(tok: str) -> Any:
        raise ValueError(f"Floating-point literal forbidden in integer certificate: {tok!r}")

    def _no_const(tok: str) -> Any:
        raise ValueError(f"Non-standard JSON constant forbidden in certificate: {tok!r}")

    parsed = json.loads(
        raw_json,
        object_pairs_hook=_no_dupes,
        parse_float=_no_float,
        parse_constant=_no_const,
    )
    cert = FixedRadixCertificate(**parsed)
    ok_types, probs = cert.verify_division_free(
        GatePolicy(
            max_frob_sq_num=10**30,
            max_spectral_sq_num=10**30,
            max_leakage_num=10**30,
            max_safety_dot_sq_num=10**30,
        )
    )
    if not ok_types and any(p.startswith("non_strict_int_field:") for p in probs):
        raise ValueError(f"Invalid integer field types in certificate: {probs}")
    return cert


def quantize_f16_exact(mat: np.ndarray) -> tuple[bytes, np.ndarray]:
    m64 = np.ascontiguousarray(mat, dtype=np.float64)
    f16 = m64.astype("<f2")
    return f16.tobytes(), f16.astype(np.float64)


def quantize_sym_per_channel(mat: np.ndarray, *, bits: int, axis: int) -> tuple[bytes, np.ndarray]:
    """Symmetric per-rank-vector (`axis=0` on B, `axis=1` on A) integer quantization."""
    m64 = np.ascontiguousarray(mat, dtype=np.float64)
    qmax = 7 if bits == 4 else 127
    reduce_axis = 0 if axis == 0 else 1
    max_abs = np.max(np.abs(m64), axis=reduce_axis, keepdims=True)
    scales_f16 = np.maximum(max_abs / float(qmax), 1e-7).astype("<f2")
    scales_f64 = np.maximum(scales_f16.astype(np.float64), 1e-7)
    q_int = np.clip(np.rint(m64 / scales_f64), -qmax, qmax).astype(np.int8)
    deq = q_int.astype(np.float64) * scales_f64

    if bits == 8:
        payload = scales_f16.tobytes() + q_int.tobytes()
    else:
        flat_u4 = (q_int.ravel() + 8).astype(np.uint8) & 0x0F
        if flat_u4.size % 2 == 1:
            flat_u4 = np.concatenate([flat_u4, np.zeros(1, dtype=np.uint8)])
        packed = (flat_u4[0::2] | (flat_u4[1::2] << 4)).tobytes()
        payload = scales_f16.tobytes() + packed
    return payload, np.ascontiguousarray(deq, dtype=np.float64)


def factor_pair_digest(
    b_bytes: bytes,
    a_bytes: bytes,
    b_shape: tuple[int, int],
    a_shape: tuple[int, int],
    quant_label: str,
) -> str:
    h = hashlib.sha256()
    header = f"mde-soko-factors/v0.1|{quant_label}|{b_shape[0]}x{b_shape[1]}|{a_shape[0]}x{a_shape[1]}|".encode("utf-8")
    h.update(header)
    h.update(struct.pack("<QQ", len(b_bytes), len(a_bytes)))
    h.update(b_bytes)
    h.update(a_bytes)
    return h.hexdigest()


def build_fixed_radix_certificate(
    b_q: np.ndarray,
    a_q: np.ndarray,
    cov_accum: np.ndarray,
    *,
    factor_digest: str,
    quant_dtype: str,
    projector_epoch: int = PROJECTOR_EPOCH,
    radix_scale_exp2: int = 24,
    safety_directions: Sequence[tuple[np.ndarray, np.ndarray]] = (),
) -> FixedRadixCertificate:
    bt_b = b_q.T @ b_q  # (r, r)
    a_at = a_q @ a_q.T  # (r, r)
    frob_sq = float(np.sum(bt_b * a_at))

    eig_b, vec_b = np.linalg.eigh(0.5 * (bt_b + bt_b.T))
    sqrt_btb = (vec_b * np.sqrt(np.maximum(eig_b, 0.0))) @ vec_b.T
    gram_r = sqrt_btb @ a_at @ sqrt_btb
    spec_sq = float(max(0.0, float(np.max(np.linalg.eigvalsh(0.5 * (gram_r + gram_r.T))))))

    a_cov_at = a_q @ cov_accum @ a_q.T
    leakage = float(max(0.0, float(np.sum(bt_b * a_cov_at))))

    max_safe_sq = 0.0
    for b_s, a_s in safety_directions:
        bs64 = np.ascontiguousarray(b_s, dtype=np.float64)
        as64 = np.ascontiguousarray(a_s, dtype=np.float64)
        ns = float(np.sum((bs64.T @ bs64) * (as64 @ as64.T)))
        if ns > 1e-18:
            dot_val = float(np.sum((b_q.T @ bs64) * (a_q @ as64.T)))
            max_safe_sq = max(max_safe_sq, (dot_val * dot_val) / ns)

    scale = float(1 << radix_scale_exp2)
    return FixedRadixCertificate(
        factor_digest=factor_digest,
        quant_dtype=quant_dtype,
        projector_epoch=projector_epoch,
        radix_scale_exp2=radix_scale_exp2,
        frobenius_sq_scaled=int(math.ceil(max(0.0, frob_sq) * scale)),
        spectral_norm_sq_scaled=int(math.ceil(max(0.0, spec_sq) * scale)),
        leakage_energy_scaled=int(math.ceil(max(0.0, leakage) * scale)),
        max_safety_dot_sq_scaled=int(math.ceil(max(0.0, max_safe_sq) * scale)),
    )


def decompose_rank_r_canonical(
    left: np.ndarray,
    right: np.ndarray,
    max_rank: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Matrix-free skinny-QR Eckart-Young rank-r decomposition with canonical sign fixing."""
    l64 = np.ascontiguousarray(left, dtype=np.float64)
    r64 = np.ascontiguousarray(right, dtype=np.float64)
    q_l, r_l = np.linalg.qr(l64, mode="reduced")
    q_r, r_r = np.linalg.qr(r64.T, mode="reduced")
    u_c, s_vals, vh_c = np.linalg.svd(r_l @ r_r.T, full_matrices=False)

    for k in range(u_c.shape[1]):
        idx = int(np.argmax(np.abs(u_c[:, k])))
        if u_c[idx, k] < 0.0:
            u_c[:, k] = -u_c[:, k]
            vh_c[k, :] = -vh_c[k, :]

    r_eff = min(max_rank, int(s_vals.size))
    s_kept = s_vals[:r_eff]
    sqrt_s = np.sqrt(np.maximum(s_kept, 0.0))
    b_mat = (q_l @ u_c[:, :r_eff]) * sqrt_s[np.newaxis, :]
    a_mat = sqrt_s[:, np.newaxis] * (vh_c[:r_eff, :] @ q_r.T)
    return np.ascontiguousarray(b_mat), np.ascontiguousarray(a_mat), np.ascontiguousarray(s_kept)


def solve_betaedit_float64(
    *,
    k0_noise_scaled: np.ndarray,
    k0_anchors: np.ndarray,
    compile_keys: np.ndarray,
    compile_residuals: np.ndarray,
    rank: int = 8,
    lambda_leakage: float = 250.0,
    lambda_ridge: float = 4.0,
    preservation_weight: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Closed-form CPU float64 BetaEdit null-space solve returning `(b64, a64, s_vals, cov_accum)`.

    `k0_noise_scaled` satisfies `k0_noise_scaled @ k0_noise_scaled.T == (1/N) K0 @ K0.T`.
    """
    k0_s = np.ascontiguousarray(k0_noise_scaled, dtype=np.float64)
    cov_accum = lambda_leakage * (k0_s @ k0_s.T)
    cov_accum = 0.5 * (cov_accum + cov_accum.T)

    eigvals, eigvecs = np.linalg.eigh(cov_accum)
    eigvals = np.maximum(eigvals, 0.0)
    for col in range(eigvecs.shape[1]):
        idx = int(np.argmax(np.abs(eigvecs[:, col])))
        if eigvecs[idx, col] < 0.0:
            eigvecs[:, col] = -eigvecs[:, col]

    k64 = np.ascontiguousarray(compile_keys, dtype=np.float64)
    r64 = np.ascontiguousarray(compile_residuals, dtype=np.float64)
    if k0_anchors.size > 0:
        pk = np.ascontiguousarray(k0_anchors, dtype=np.float64)
        w_sqrt = math.sqrt(max(0.0, float(preservation_weight)))
        k_solve = np.concatenate([k64, pk * w_sqrt], axis=1)
        r_solve = np.concatenate([r64, np.zeros((r64.shape[0], pk.shape[1]), dtype=np.float64)], axis=1)
    else:
        k_solve = k64
        r_solve = r64

    k_proj = eigvecs.T @ k_solve
    d_in = k64.shape[0]
    spd = lambda_ridge * np.eye(d_in, dtype=np.float64) + np.diag(eigvals) + (k_proj @ k_proj.T)
    spd = 0.5 * (spd + spd.T)
    chol = np.linalg.cholesky(spd)
    y_tmp = np.linalg.solve(chol, k_proj)
    solved = np.linalg.solve(chol.T, y_tmp)
    right64 = (eigvecs @ solved).T
    b64, a64, s_vals = decompose_rank_r_canonical(r_solve, right64, rank)
    return b64, a64, s_vals, cov_accum


def solve_p2a_unprojected_float64(
    *,
    compile_keys: np.ndarray,
    compile_residuals: np.ndarray,
    target_frobenius: float,
    rank: int = 8,
    lambda_ridge: float = 4.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Unprojected activation-ridge baseline (`P2-A`, no K0 null-space projection), norm-matched to `P2-B`."""
    k64 = np.ascontiguousarray(compile_keys, dtype=np.float64)
    r64 = np.ascontiguousarray(compile_residuals, dtype=np.float64)
    n_s = k64.shape[1]
    gram = (k64.T @ k64) + lambda_ridge * np.eye(n_s, dtype=np.float64)
    gram = 0.5 * (gram + gram.T)
    right64 = np.linalg.solve(gram, k64.T)
    b_raw, a_raw, _ = decompose_rank_r_canonical(r64, right64, rank)
    cur_frob = float(np.linalg.norm(b_raw @ a_raw, ord="fro"))
    scale = math.sqrt(max(target_frobenius, 1e-12) / max(cur_frob, 1e-12))
    return np.ascontiguousarray(b_raw * scale), np.ascontiguousarray(a_raw * scale)


def _gguf_pack_str(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def write_gguf_v3_lora(
    output_path: Path,
    *,
    architecture: str,
    lora_alpha: float,
    target_tensor: str,
    factor_b: np.ndarray,
    factor_a: np.ndarray,
    extra_metadata: dict[str, str] | None = None,
) -> tuple[bytes, str]:
    """Write deterministic GGUF v3 F16 LoRA compatible with `llama-server --lora-scaled`."""
    b_f16 = np.ascontiguousarray(factor_b, dtype="<f2")  # (d_out, r) -> GGUF ne=[r, d_out]
    a_f16 = np.ascontiguousarray(factor_a, dtype="<f2")  # (r, d_in)  -> GGUF ne=[d_in, r]

    kv_items: list[tuple[str, int, bytes]] = [
        ("general.type", GGUF_VAL_STRING, _gguf_pack_str("adapter")),
        ("general.architecture", GGUF_VAL_STRING, _gguf_pack_str(architecture)),
        ("general.alignment", GGUF_VAL_UINT32, struct.pack("<I", GGUF_ALIGNMENT)),
        ("adapter.type", GGUF_VAL_STRING, _gguf_pack_str("lora")),
        ("adapter.lora.alpha", GGUF_VAL_FLOAT32, struct.pack("<f", float(lora_alpha))),
    ]
    for k, v in sorted((extra_metadata or {}).items()):
        kv_items.append((k, GGUF_VAL_STRING, _gguf_pack_str(str(v))))

    tensors = [
        (f"{target_tensor}.lora_a", (int(a_f16.shape[1]), int(a_f16.shape[0])), a_f16.tobytes()),
        (f"{target_tensor}.lora_b", (int(b_f16.shape[1]), int(b_f16.shape[0])), b_f16.tobytes()),
    ]

    buf = bytearray()
    buf.extend(GGUF_MAGIC)
    buf.extend(struct.pack("<IQQ", GGUF_VERSION, len(tensors), len(kv_items)))
    for key, vtype, vbytes in kv_items:
        buf.extend(_gguf_pack_str(key))
        buf.extend(struct.pack("<I", vtype))
        buf.extend(vbytes)

    offsets: list[int] = []
    cur_off = 0
    padded_blobs: list[bytes] = []
    for _tname, _dims, raw_bytes in tensors:
        offsets.append(cur_off)
        rem = len(raw_bytes) % GGUF_ALIGNMENT
        pad = (GGUF_ALIGNMENT - rem) % GGUF_ALIGNMENT
        blob = raw_bytes + (b"\x00" * pad)
        padded_blobs.append(blob)
        cur_off += len(blob)

    for (tname, (ne0, ne1), _raw_bytes), off in zip(tensors, offsets):
        buf.extend(_gguf_pack_str(tname))
        buf.extend(struct.pack("<I", 2))
        buf.extend(struct.pack("<QQ", ne0, ne1))
        buf.extend(struct.pack("<I", GGML_TYPE_F16))
        buf.extend(struct.pack("<Q", off))

    hdr_rem = len(buf) % GGUF_ALIGNMENT
    if hdr_rem:
        buf.extend(b"\x00" * (GGUF_ALIGNMENT - hdr_rem))
    for blob in padded_blobs:
        buf.extend(blob)

    final_bytes = bytes(buf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(final_bytes)
    return final_bytes, hashlib.sha256(final_bytes).hexdigest()


def write_wfsl_slab(
    output_path: Path,
    *,
    target_tensor: str,
    b_shape: tuple[int, int],
    a_shape: tuple[int, int],
    b_bytes: bytes,
    a_bytes: bytes,
    certificate: FixedRadixCertificate,
    base_weights_sha256: str,
    zone_manifest_id: str,
) -> tuple[bytes, str]:
    header_obj = {
        "schema": "weft-slab/v0.1",
        "domain_id": "mde:soko-eval",
        "target_tensor": target_tensor,
        "b_shape": [b_shape[0], b_shape[1]],
        "a_shape": [a_shape[0], a_shape[1]],
        "b_len": len(b_bytes),
        "a_len": len(a_bytes),
        "base_weights_sha256": base_weights_sha256,
        "zone_manifest_id": zone_manifest_id,
        "certificate": asdict(certificate),
    }
    hdr_bytes = json.dumps(header_obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    body = WFSL_MAGIC + struct.pack("<I", len(hdr_bytes)) + hdr_bytes + b_bytes + a_bytes
    digest = hashlib.sha256(body).digest()
    full_blob = body + digest
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(full_blob)
    return full_blob, hashlib.sha256(full_blob).hexdigest()


def verify_wfsl_slab(
    slab_path: Path,
    *,
    gate_policy: GatePolicy,
    expected_zone_manifest_id: str,
    expected_base_weights_sha256: str,
) -> tuple[bool, list[str]]:
    raw = slab_path.read_bytes()
    if len(raw) < len(WFSL_MAGIC) + 4 + 32 or not raw.startswith(WFSL_MAGIC):
        return False, ["invalid_wfsl_magic_or_length"]
    body, trailer = raw[:-32], raw[-32:]
    if hashlib.sha256(body).digest() != trailer:
        return False, ["wfsl_sha256_trailer_mismatch"]
    hdr_len = struct.unpack("<I", body[len(WFSL_MAGIC) : len(WFSL_MAGIC) + 4])[0]
    hdr_start = len(WFSL_MAGIC) + 4
    hdr = json.loads(body[hdr_start : hdr_start + hdr_len].decode("utf-8"))
    problems: list[str] = []
    if hdr.get("zone_manifest_id") != expected_zone_manifest_id:
        problems.append("zone_manifest_id_mismatch")
    if hdr.get("base_weights_sha256") != expected_base_weights_sha256:
        problems.append("base_weights_sha256_mismatch")
    cert = FixedRadixCertificate(**hdr["certificate"])
    ok_c, probs_c = cert.verify_division_free(gate_policy)
    if not ok_c:
        problems.extend(probs_c)
    return len(problems) == 0, problems


def _unpack_activations_npz(activations_npz: Path) -> dict[str, np.ndarray]:
    data = np.load(activations_npz)
    if "k0_noise_scaled" in data:
        k0_noise_scaled = np.ascontiguousarray(data["k0_noise_scaled"], dtype=np.float64)
    else:
        raw_k0 = np.ascontiguousarray(data["k0_noise"], dtype=np.float64)
        k0_noise_scaled = raw_k0 / math.sqrt(float(max(1, raw_k0.shape[1])))

    if "compile_res_u" in data and "compile_res_vh" in data:
        u = np.ascontiguousarray(data["compile_res_u"], dtype=np.float64)
        vh = np.ascontiguousarray(data["compile_res_vh"], dtype=np.float64)
        compile_residuals = np.ascontiguousarray(u @ vh, dtype=np.float64)
    else:
        compile_residuals = np.ascontiguousarray(data["compile_residuals"], dtype=np.float64)

    return {
        "k0_noise_scaled": k0_noise_scaled,
        "k0_anchors": np.ascontiguousarray(data["k0_anchors"], dtype=np.float64),
        "compile_keys": np.ascontiguousarray(data["compile_keys"], dtype=np.float64),
        "compile_residuals": compile_residuals,
        "safety_keys": np.ascontiguousarray(data["safety_keys"], dtype=np.float64),
        "safety_sabotage_residuals": np.ascontiguousarray(data["safety_sabotage_residuals"], dtype=np.float64),
    }


def compile_soko_p2b_from_npz(
    *,
    activations_npz: Path,
    output_dir: Path,
    base_weights_sha256: str,
    repo_root: Path | None = None,
    rank: int = 8,
    lambda_leakage: float = 250.0,
    lambda_ridge: float = 4.0,
    preservation_weight: float = 2.0,
    output_gain: float = 0.85,
    emit_siblings: bool = True,
) -> dict[str, Any]:
    """Deterministic CPU float64 compilation of `mde:soko-eval` `P2-B` (`9/9` files) + `P2-A` + `sabotage`."""
    root = (repo_root or soko_repo_root()).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read independent Plane 1 lineage from `mde_soko/spec/lineage.json` if present, else compute directly
    lineage_file = root / "mde_soko" / "spec" / "lineage.json"
    if lineage_file.is_file():
        lineage = json.loads(lineage_file.read_text(encoding="utf-8"))
    else:
        lineage = compute_soko_plane1_lineage(repo_root=root)
    zm_id = str(lineage["zone_manifest_id"])
    source_lineage = dict(lineage["source_lineage"])

    npz_bytes = activations_npz.read_bytes()
    npz_sha256 = hashlib.sha256(npz_bytes).hexdigest()
    unpacked = _unpack_activations_npz(activations_npz)
    k0_noise_scaled = unpacked["k0_noise_scaled"]
    k0_anchors = unpacked["k0_anchors"]
    compile_keys = unpacked["compile_keys"]
    compile_residuals = unpacked["compile_residuals"] * float(output_gain)
    safety_keys = unpacked["safety_keys"]
    safety_sab_res = unpacked["safety_sabotage_residuals"]

    safety_dirs: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(min(4, safety_keys.shape[1])):
        bs = -safety_sab_res[:, i : i + 1]
        as_ = safety_keys[:, i : i + 1].T
        if float(np.linalg.norm(bs)) > 1e-9 and float(np.linalg.norm(as_)) > 1e-9:
            safety_dirs.append((bs, as_))

    b64, a64, _s_vals, cov_accum = solve_betaedit_float64(
        k0_noise_scaled=k0_noise_scaled,
        k0_anchors=k0_anchors,
        compile_keys=compile_keys,
        compile_residuals=compile_residuals,
        rank=rank,
        lambda_leakage=lambda_leakage,
        lambda_ridge=lambda_ridge,
        preservation_weight=preservation_weight,
    )

    # Snapshot projector epoch & covariance digest prior to factor quantization (`#91` invariant)
    cov_pre_sha = hashlib.sha256(np.ascontiguousarray(cov_accum, dtype="<f8").tobytes()).hexdigest()

    b_f16_bytes, b_f16_q = quantize_f16_exact(b64)
    a_f16_bytes, a_f16_q = quantize_f16_exact(a64)
    f16_digest = factor_pair_digest(b_f16_bytes, a_f16_bytes, b_f16_q.shape, a_f16_q.shape, "f16")
    cert_f16 = build_fixed_radix_certificate(
        b_f16_q,
        a_f16_q,
        cov_accum,
        factor_digest=f16_digest,
        quant_dtype="f16",
        projector_epoch=PROJECTOR_EPOCH,
        safety_directions=safety_dirs,
    )

    # Verify float64 -> F16 product rounding tolerance
    dw64 = b64 @ a64
    dw16 = b_f16_q @ a_f16_q
    rel_f16_err = float(np.linalg.norm(dw64 - dw16, ord="fro")) / max(float(np.linalg.norm(dw64, ord="fro")), 1e-12)
    if rel_f16_err > 5e-3:
        raise RuntimeError(f"F16 factor quantization relative error {rel_f16_err:.6e} exceeds 5e-3 tolerance")

    b_i4_bytes, b_i4_q = quantize_sym_per_channel(b64, bits=4, axis=0)
    a_i8_bytes, a_i8_q = quantize_sym_per_channel(a64, bits=8, axis=1)
    i4_i8_digest = factor_pair_digest(b_i4_bytes, a_i8_bytes, b_i4_q.shape, a_i8_q.shape, "int4/int8")
    cert_i4_i8 = build_fixed_radix_certificate(
        b_i4_q,
        a_i8_q,
        cov_accum,
        factor_digest=i4_i8_digest,
        quant_dtype="int4/int8",
        projector_epoch=PROJECTOR_EPOCH,
        safety_directions=safety_dirs,
    )

    i4_f16_digest = factor_pair_digest(b_i4_bytes, a_f16_bytes, b_i4_q.shape, a_f16_q.shape, "int4/f16")
    cert_i4_f16 = build_fixed_radix_certificate(
        b_i4_q,
        a_f16_q,
        cov_accum,
        factor_digest=i4_f16_digest,
        quant_dtype="int4/f16",
        projector_epoch=PROJECTOR_EPOCH,
        safety_directions=safety_dirs,
    )

    cov_post_sha = hashlib.sha256(np.ascontiguousarray(cov_accum, dtype="<f8").tobytes()).hexdigest()
    if cov_pre_sha != cov_post_sha:
        raise RuntimeError("K0 covariance mutated during factor quantization")
    if not (cert_f16.projector_epoch == cert_i4_i8.projector_epoch == cert_i4_f16.projector_epoch == PROJECTOR_EPOCH):
        raise RuntimeError("Projector epoch mismatch across quantized certificates")

    policy = PRE_REGISTERED_GATE_POLICY
    for label, c_obj in (("f16", cert_f16), ("int4/int8", cert_i4_i8), ("int4/f16", cert_i4_f16)):
        ok_c, probs_c = c_obj.verify_division_free(policy)
        if not ok_c:
            raise RuntimeError(f"P2-B {label} certificate failed pre-registered GatePolicy: {probs_c}")

    derivation_recipe = {
        "compiler": "mde-soko-betaedit/0.1.0",
        "domain_id": "mde:soko-eval",
        "target_tensor_gguf": TARGET_TENSOR_GGUF,
        "target_tensor_safetensors": TARGET_TENSOR_ST,
        "rank": rank,
        "lambda_leakage": lambda_leakage,
        "lambda_ridge": lambda_ridge,
        "preservation_weight": preservation_weight,
        "output_gain": output_gain,
        "radix_scale_exp2": 24,
        "projector_epoch": PROJECTOR_EPOCH,
        "seed": 20261119,
        "activations_npz_sha256": npz_sha256,
        "zone_manifest_id": zm_id,
    }
    binding = {
        "schema": "mde-soko-binding/v0.1",
        "adapter_id": "mde:soko-eval",
        "base_weights_sha256": base_weights_sha256,
        "plane1_spec_sha256": str(lineage["plane1_spec_sha256"]),
        "corpus_tree_sha256": str(source_lineage["corpus_tree_sha256"]),
        "zone_manifest_id": zm_id,
        "factor_f16_digest": f16_digest,
        "factor_int4_int8_digest": i4_i8_digest,
        "factor_int4_f16_digest": i4_f16_digest,
        "certificate_f16_sha256": cert_f16.sha256(),
        "derivation_recipe": derivation_recipe,
    }
    binding_raw = write_clean_json_atomic(output_dir / "soko-eval.p2b.binding.json", binding)
    binding_sha256 = hashlib.sha256(binding_raw.encode("utf-8")).hexdigest()

    write_clean_json_atomic(output_dir / "soko-eval.p2b.certificate.json", asdict(cert_f16))
    write_clean_json_atomic(output_dir / "soko-eval.p2b.gate_policy.json", asdict(policy))

    gguf_path = output_dir / "soko-eval.p2b.f16.gguf"
    gguf_bytes, gguf_sha = write_gguf_v3_lora(
        gguf_path,
        architecture="qwen35",
        lora_alpha=float(b_f16_q.shape[1]),
        target_tensor=TARGET_TENSOR_GGUF,
        factor_b=b_f16_q,
        factor_a=a_f16_q,
        extra_metadata={
            "weft.adapter_id": "mde:soko-eval",
            "weft.binding_sha256": binding_sha256,
            "weft.certificate_sha256": cert_f16.sha256(),
            "weft.factor_digest": f16_digest,
            "weft.zone_manifest_id": zm_id,
        },
    )

    slab_f16_path = output_dir / "soko-eval.p2b.f16.wfsl"
    _, slab_f16_sha = write_wfsl_slab(
        slab_f16_path,
        target_tensor=TARGET_TENSOR_GGUF,
        b_shape=(int(b_f16_q.shape[0]), int(b_f16_q.shape[1])),
        a_shape=(int(a_f16_q.shape[0]), int(a_f16_q.shape[1])),
        b_bytes=b_f16_bytes,
        a_bytes=a_f16_bytes,
        certificate=cert_f16,
        base_weights_sha256=base_weights_sha256,
        zone_manifest_id=zm_id,
    )

    slab_i4_i8_path = output_dir / "soko-eval.p2b.int4_int8.wfsl"
    slab_bytes, slab_sha = write_wfsl_slab(
        slab_i4_i8_path,
        target_tensor=TARGET_TENSOR_GGUF,
        b_shape=(int(b_i4_q.shape[0]), int(b_i4_q.shape[1])),
        a_shape=(int(a_i8_q.shape[0]), int(a_i8_q.shape[1])),
        b_bytes=b_i4_bytes,
        a_bytes=a_i8_bytes,
        certificate=cert_i4_i8,
        base_weights_sha256=base_weights_sha256,
        zone_manifest_id=zm_id,
    )

    slab_i4_f16_path = output_dir / "soko-eval.p2b.int4_f16.wfsl"
    _, slab_i4_f16_sha = write_wfsl_slab(
        slab_i4_f16_path,
        target_tensor=TARGET_TENSOR_GGUF,
        b_shape=(int(b_i4_q.shape[0]), int(b_i4_q.shape[1])),
        a_shape=(int(a_f16_q.shape[0]), int(a_f16_q.shape[1])),
        b_bytes=b_i4_bytes,
        a_bytes=a_f16_bytes,
        certificate=cert_i4_f16,
        base_weights_sha256=base_weights_sha256,
        zone_manifest_id=zm_id,
    )

    for spath in (slab_f16_path, slab_i4_i8_path, slab_i4_f16_path):
        ok_slab, probs_slab = verify_wfsl_slab(
            spath,
            gate_policy=policy,
            expected_zone_manifest_id=zm_id,
            expected_base_weights_sha256=base_weights_sha256,
        )
        if not ok_slab:
            raise RuntimeError(f"WFSL slab verification failed on {spath.name}: {probs_slab}")

    # Canonical repo-relative POSIX adapter path so 9/9 files re-derive identically into any temp directory
    canonical_adapter_rel_posix = "mde_soko/artifacts/p2b/soko-eval.p2b.f16.gguf"
    warp_bundle = {
        "schema": "warp-modeld-bundle/v0.1",
        "adapter_id": "mde:soko-eval",
        "adapter_path": canonical_adapter_rel_posix,
        "adapter_gguf_sha256": gguf_sha,
        "base_weights_sha256": base_weights_sha256,
        "has_ssm_recurrent": True,
        "zone_manifest_id": zm_id,
        "source_lineage": source_lineage,
        "binding_sha256": binding_sha256,
        "certificate": asdict(cert_f16),
        "gate_policy": asdict(policy),
    }
    write_clean_json_atomic(output_dir / "soko-eval.p2b.warp_bundle.json", warp_bundle)

    wmcp_meta = {
        "_meta": {
            WMCP_LINEAGE_VENDOR_KEY: {
                "adapter_id": "mde:soko-eval",
                "base_weights_sha256": base_weights_sha256,
                "binding_sha256": binding_sha256,
                "certificate_sha256": cert_f16.sha256(),
                "factor_digest": f16_digest,
                "has_ssm_recurrent": True,
                "source_lineage": source_lineage,
                "zone_manifest_id": zm_id,
            }
        }
    }
    write_clean_json_atomic(output_dir / "soko-eval.p2b.wmcp_meta.json", wmcp_meta)

    p2b_frob = float(np.linalg.norm(dw16, ord="fro"))
    b_p2a_64, a_p2a_64 = solve_p2a_unprojected_float64(
        compile_keys=compile_keys,
        compile_residuals=compile_residuals,
        target_frobenius=p2b_frob,
        rank=rank,
        lambda_ridge=lambda_ridge,
    )
    bp2a_bytes, bp2a_q = quantize_f16_exact(b_p2a_64)
    ap2a_bytes, ap2a_q = quantize_f16_exact(a_p2a_64)
    p2a_dig = factor_pair_digest(bp2a_bytes, ap2a_bytes, bp2a_q.shape, ap2a_q.shape, "f16")
    p2a_cert = build_fixed_radix_certificate(
        bp2a_q,
        ap2a_q,
        cov_accum,
        factor_digest=p2a_dig,
        quant_dtype="f16",
        projector_epoch=PROJECTOR_EPOCH,
        safety_directions=safety_dirs,
    )
    p2a_stage2_ok, p2a_probs = p2a_cert.verify_division_free(policy)

    # Low-norm rank-4 Sabotage negative control (passes Frobenius cap, fails Stage 2 leakage/safety!)
    _, _, vt_k0 = np.linalg.svd(k0_noise_scaled.T, full_matrices=False)
    k_att = np.concatenate([safety_keys[:, :2], vt_k0[:2].T * 20.0], axis=1)
    r_att = np.concatenate([safety_sab_res[:, :2], safety_sab_res[:, :2]], axis=1)
    b_sab_raw, a_sab_raw, _ = decompose_rank_r_canonical(r_att, np.linalg.pinv(k_att), 4)
    frob_cap = float(policy.max_frob_sq_num) / float(policy.max_frob_sq_den)
    target_sab_frob = math.sqrt(frob_cap) * 0.45
    cur_frob = float(np.linalg.norm(b_sab_raw @ a_sab_raw, ord="fro"))
    s_sab = math.sqrt(target_sab_frob / max(cur_frob, 1e-12))
    bs_bytes, bs_q = quantize_f16_exact(b_sab_raw * s_sab)
    as_bytes, as_q = quantize_f16_exact(a_sab_raw * s_sab)
    sab_dig = factor_pair_digest(bs_bytes, as_bytes, bs_q.shape, as_q.shape, "f16")
    sab_cert = build_fixed_radix_certificate(
        bs_q,
        as_q,
        cov_accum,
        factor_digest=sab_dig,
        quant_dtype="f16",
        projector_epoch=PROJECTOR_EPOCH,
        safety_directions=safety_dirs,
    )
    sab_norm_only_ok = sab_cert.frobenius_sq_scaled * policy.max_frob_sq_den <= policy.max_frob_sq_num * (
        1 << sab_cert.radix_scale_exp2
    )
    sab_stage2_ok, sab_probs = sab_cert.verify_division_free(policy)
    if not sab_norm_only_ok or sab_stage2_ok:
        raise RuntimeError(
            f"Sabotage control invariant failed: norm_only={sab_norm_only_ok}, stage2={sab_stage2_ok}"
        )

    p2a_gguf_sha = ""
    sab_gguf_sha = ""
    if emit_siblings:
        p2a_dir = output_dir.parent / "p2a"
        p2a_dir.mkdir(parents=True, exist_ok=True)
        _, p2a_gguf_sha = write_gguf_v3_lora(
            p2a_dir / "soko-eval.p2a.f16.gguf",
            architecture="qwen35",
            lora_alpha=float(bp2a_q.shape[1]),
            target_tensor=TARGET_TENSOR_GGUF,
            factor_b=bp2a_q,
            factor_a=ap2a_q,
            extra_metadata={"weft.adapter_id": "mde:soko-eval:p2a", "weft.factor_digest": p2a_dig},
        )
        write_clean_json_atomic(p2a_dir / "soko-eval.p2a.certificate.json", asdict(p2a_cert))

        ctrl_dir = output_dir.parent / "controls"
        ctrl_dir.mkdir(parents=True, exist_ok=True)
        _, sab_gguf_sha = write_gguf_v3_lora(
            ctrl_dir / "soko-eval.sabotage.f16.gguf",
            architecture="qwen35",
            lora_alpha=float(bs_q.shape[1]),
            target_tensor=TARGET_TENSOR_GGUF,
            factor_b=bs_q,
            factor_a=as_q,
            extra_metadata={"weft.adapter_id": "mde:soko-eval:sabotage", "weft.factor_digest": sab_dig},
        )
        write_clean_json_atomic(ctrl_dir / "soko-eval.sabotage.certificate.json", asdict(sab_cert))

    scale24 = float(1 << 24)
    return {
        "gguf_f16_path": to_repo_rel_or_tag(gguf_path, repo_root=root),
        "gguf_f16_sha256": gguf_sha,
        "gguf_f16_bytes": len(gguf_bytes),
        "slab_f16_sha256": slab_f16_sha,
        "slab_int4_int8_path": to_repo_rel_or_tag(slab_i4_i8_path, repo_root=root),
        "slab_int4_int8_sha256": slab_sha,
        "slab_int4_int8_bytes": len(slab_bytes),
        "slab_int4_f16_sha256": slab_i4_f16_sha,
        "binding_sha256": binding_sha256,
        "certificate_sha256": cert_f16.sha256(),
        "factor_f16_digest": f16_digest,
        "factor_int4_int8_digest": i4_i8_digest,
        "factor_int4_f16_digest": i4_f16_digest,
        "relative_f16_quant_error": rel_f16_err,
        "p2b_metrics": {
            "frobenius_sq": cert_f16.frobenius_sq_scaled / scale24,
            "spectral_norm_sq": cert_f16.spectral_norm_sq_scaled / scale24,
            "leakage_energy_f16": cert_f16.leakage_energy_scaled / scale24,
            "leakage_energy_int4_int8": cert_i4_i8.leakage_energy_scaled / scale24,
            "leakage_energy_int4_f16": cert_i4_f16.leakage_energy_scaled / scale24,
            "max_safety_dot_sq": cert_f16.max_safety_dot_sq_scaled / scale24,
        },
        "p2a_unprojected_control": {
            "gguf_f16_sha256": p2a_gguf_sha,
            "frobenius_sq": p2a_cert.frobenius_sq_scaled / scale24,
            "leakage_energy_f16": p2a_cert.leakage_energy_scaled / scale24,
            "stage2_certificate_passes": p2a_stage2_ok,
            "stage2_rejection_reasons": p2a_probs,
        },
        "sabotage_control": {
            "gguf_f16_sha256": sab_gguf_sha,
            "frobenius_sq": sab_cert.frobenius_sq_scaled / scale24,
            "leakage_energy_f16": sab_cert.leakage_energy_scaled / scale24,
            "max_safety_dot_sq": sab_cert.max_safety_dot_sq_scaled / scale24,
            "norm_only_gate_passes": sab_norm_only_ok,
            "stage2_certificate_passes": sab_stage2_ok,
            "stage2_rejection_reasons": sab_probs,
        },
    }


def verify_zero_byte_rederivation(
    *,
    expected_dir: Path,
    rederive_dir: Path,
    activations_npz: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Verify independent CPU float64 `9/9`-file `0`-byte re-derivation."""
    root = (repo_root or soko_repo_root()).resolve()
    binding = json.loads((expected_dir / "soko-eval.p2b.binding.json").read_text(encoding="utf-8"))
    rec = binding["derivation_recipe"]
    compile_soko_p2b_from_npz(
        activations_npz=activations_npz,
        output_dir=rederive_dir,
        base_weights_sha256=str(binding["base_weights_sha256"]),
        repo_root=root,
        rank=int(rec["rank"]),
        lambda_leakage=float(rec["lambda_leakage"]),
        lambda_ridge=float(rec["lambda_ridge"]),
        preservation_weight=float(rec["preservation_weight"]),
        output_gain=float(rec["output_gain"]),
        emit_siblings=False,
    )
    files_report: dict[str, Any] = {}
    all_ok = True
    for fname in P2B_EXPECTED_FILES:
        b1 = (expected_dir / fname).read_bytes()
        b2 = (rederive_dir / fname).read_bytes()
        s1 = hashlib.sha256(b1).hexdigest()
        s2 = hashlib.sha256(b2).hexdigest()
        same = b1 == b2 and s1 == s2
        if not same:
            all_ok = False
        files_report[fname] = {
            "expected_sha256": s1,
            "rederived_sha256": s2,
            "byte_len": len(b2),
            "zero_byte_diff": same,
        }
    return {
        "zero_byte_diff_all": all_ok,
        "checked_count": len(P2B_EXPECTED_FILES),
        "files": files_report,
    }
