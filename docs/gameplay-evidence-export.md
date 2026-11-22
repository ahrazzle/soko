# Soko gameplay-evidence/v0.1 export

The zero-new-dependency adapter in `soko_mcp/gameplay_evidence.py` exports the
genuine minimal `heroes-of-sokoban-ascii-v1` `F.G` / `RR` route certificate.
The exact source bytes are stored at:

`evidence/2026-11-22-gameplay-evidence/heroes-rr-three-engine-certificate.json`

They were produced by the repository's existing
`verify_route_dual(1, ["F.G"], "RR", require_cpp=True)`, not by the exchange
adapter. Export repeats that verifier with required C++ and runs
`verify_certificate_gate`; any difference in the verdict, route/trajectory,
checker pins, controls, or certificate digest fails closed.

```bash
python3 -m soko_mcp.integrity
python3 -m soko_mcp.gameplay_evidence export \
  --certificate evidence/2026-11-22-gameplay-evidence/heroes-rr-three-engine-certificate.json \
  --simgrammar-root /tmp/rmmz-converge.awcxGe/simgrammar \
  --output evidence/2026-11-22-gameplay-evidence/heroes-rr-gameplay-evidence-v0.1.json
python3 -m soko_mcp.gameplay_evidence validate \
  evidence/2026-11-22-gameplay-evidence/heroes-rr-gameplay-evidence-v0.1.json --reverify
python3 -m unittest tests.test_gameplay_evidence -v
```

`--revision` overrides the 40-hex producer/checker commit; the default is the
current Git `HEAD`. Omitting `--output` writes the artifact to stdout. The
module and CLI do not import or require mcproof.

## Evidence boundary

- Source `VERIFIED` maps only to `model_replay`, never `model_proof`. This is
  not a formal proof, route-minimality result, or live original-engine replay.
- The exact source JSON, its raw SHA-256 and certificate digest, original source
  status, checker pins, raw route SHA-256, trajectory FNV-1a digest, all three
  must-fail controls, and source limitations remain represented in the envelope.
- `agent-pathfinding.yaml` was inspected. It defines agent route search and
  least-cost paths; this certificate only replays supplied keys and proves no
  search or minimality. Consequently `mechanics=[]`, with an explicit unbound
  limitation. `direct-avatar` is also not pinned because its real-time embodied
  controller semantics exceed this replay-only evidence. A missing/unreadable
  SimGrammar root likewise yields `mechanics=[]` and an explicit limitation;
  pins are never fabricated.
- Validation reconstructs the deterministic source projection as well as
  checking all commitments, so re-signing raw, payload, action, trajectory,
  source-label, or control mutations does not make them valid.

See `tests/test_gameplay_evidence.py` for positive, CLI, raw-tamper,
payload/action/trajectory-tamper, label-promotion, dropped-control, and
certificate-digest-mismatch coverage.
