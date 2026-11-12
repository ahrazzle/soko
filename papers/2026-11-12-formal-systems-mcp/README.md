# Green Tests, Unsound Certificates

Version 2.0 preprint draft, dated November 12, 2026, by Ahraz Arifuddin. It is a short experience report on unsound certificates in agent-written verifiers, aimed at an agent-tooling workshop or a cs.SE / cs.AI preprint. The subject is soko-verified-mcp, the MCP server in this repository.

This version replaces the v1.0 draft "Self-Auditing Formal-Systems MCP Kernels for Autonomous Agents" from the vaultofsouls Drive drop (paper.tex sha256 6b09eddabb54ad1b42569e0a7131b825bb0f8b21e0b839878ab1a8cbd0c2437f, paper.pdf sha256 784a0fc82ebc63282035d497c4184e5fd9b0f11907f50bd99b425de3eb8c4e1a). The revision follows an independent audit of v1.0 against main and keeps only the claims that hold on this tree.

## Files

| File | Bytes | sha256 |
| --- | --- | --- |
| paper.tex | 26098 | 1e41a47b7932d97661d3dd4b8daecae53fcf8c1aafaa80201b2979b760c8cb4d |
| paper.pdf | 89483 | 2aac621ded8ee2f450296b1ba662c5b5b17f06211c167ecca5efdb22d0348aff |

paper.pdf is 6 pages, A4.

## Build

    tectonic paper.tex

The build is clean with Tectonic 0.17.0 (no warnings). PDF bytes differ between builds because of embedded timestamps, so the sha256 above pins the checked-in file.

## What the paper claims

- Defect catalog for soko-verified-mcp v0.1.0 to v0.3.0 (F-01 to F-06). F-01 and F-02 are fixed. F-03 is fixed in part. F-04 is open: the lower-bound wrapper can return VERIFIED for a floor with no witness and an unfinished search, and tests/test_search_bounds.py (8 tests) fails. The F-06 change of I-1 from 8 to 9 was wrong; canonical I-1 is 8.
- The v1.0 III-14 lower bound of 35 is withdrawn. A rerun of the C++ prover on the 14x7 fixture reaches a layer at 36 and then aborts with STEP INCONSISTENCY and no FINAL_CERT.
- Proposition 1 (quotient lower bound) is a classical result. The code checks its premises only in formal_certify_lower_bound quotient mode on a closed finite graph. The C++ pair-atom database is a separate argument.
- Table 2 is rebuilt from soko_mcp/data/catalog.json. I-1 (8) and III-22 (9) close locally with matching witnesses. II-22, III-11, III-15 and III-14 are replayed upper bounds. III-20 is VERIFIED at 84 on three local engines. III-21 is KNOWN at 316. The public III-14 floor 43 is labeled KNOWN.
- Reproduced results: two 84-key III-20 routes (eecbea96b091, 4edff1ad8c90), the 5-step unfenced lease trace and the 486-state fenced check, the 4-job schedule at 19, and the planted-bug audit at 10/10.
- The 14x7 III-14 numbers are fixture results, and the column-6 explanation of the 43 to 48 gap is a conjecture.
- Limitations: the F-04 witness hole, truncated potentials (bound 15 against a true cost of 10), PROVEN reading the spec invariant only, and VERIFIED from formal_triage_portfolio and formal_export_ledger without a proof.
- Prior art: Junghanns and Schaeffer (Rolling Stone), Culberson and Schaeffer (pattern databases), Pereira et al. (SoCS 2013, IJCAI 2016), Shoham and Schaeffer (FESS, Festival). The 3,819 figure cites banteg's 11 November 2026 announcement on X.

The tool count is 19 (12 soko_* and 7 formal_*), with 6 resources.
