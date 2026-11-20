"""Sokoban Evaluation Multi-Domain Pack (`mde:soko-eval`) for `ahrazzle/soko`."""

from __future__ import annotations

from .compiler import (
    FixedRadixCertificate,
    GatePolicy,
    P2B_EXPECTED_FILES,
    PRE_REGISTERED_GATE_POLICY,
    compile_soko_p2b_from_npz,
    verify_wfsl_slab,
    verify_zero_byte_rederivation,
)
from .domain_oracle import (
    DomainDiagnostic,
    DomainGradeResult,
    SokoDomainOracle,
    SokoEvalBudget,
    SokoPlaySession,
    audit_soko_certificate,
    audit_zero_import_cell,
    board_sha256_lf,
    execute_sandbox_cell,
    verify_route_dual_strict,
)
from .lineage import compute_soko_plane1_lineage, verify_soko_lineage

__version__ = "0.1.0"
DOMAIN_ID = "mde:soko-eval"

__all__ = [
    "DOMAIN_ID",
    "DomainDiagnostic",
    "DomainGradeResult",
    "FixedRadixCertificate",
    "GatePolicy",
    "P2B_EXPECTED_FILES",
    "PRE_REGISTERED_GATE_POLICY",
    "SokoDomainOracle",
    "SokoEvalBudget",
    "SokoPlaySession",
    "__version__",
    "audit_soko_certificate",
    "audit_zero_import_cell",
    "board_sha256_lf",
    "compile_soko_p2b_from_npz",
    "compute_soko_plane1_lineage",
    "execute_sandbox_cell",
    "verify_route_dual_strict",
    "verify_soko_lineage",
    "verify_wfsl_slab",
    "verify_zero_byte_rederivation",
]
