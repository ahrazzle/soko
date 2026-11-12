# Installed-agent workflow exercise

The package was installed editable into a separate virtual environment, then
invoked from `/tmp`, outside the checkout. The environment reused the existing
Playwright/Chromium installation. `report.json` retains six CLI invocations and
seven MCP JSON-RPC events, their outputs, and matching before/after source hashes.
`checkpoint.json` is the portable checkpoint produced by the CLI exercise.

The exercise checked all 66 rooms are discoverable, III-21 loads by its canonical
ID, original I-1 verifies at eight keys, local I-2 search respects its configured
limits, and I-2 play resumes across separate CLI processes. Through the real MCP
stdio interface it replayed the Part II baseline, won I-22 with three active
heroes, rejected extra keys after winning, undid the winning key, reset the
room, and verified I-22 locally.

Result: **passed**. No new record or public submission is claimed.

After installing the package and optional browser dependencies, repeat from any
working directory with a fresh output directory:

```sh
python3 /path/to/soko/experiments/agent_workflow_smoke.py \
  --cwd /tmp --output-dir /tmp/agent-workflow-new
```

The full 66-room mechanics comparison is recorded separately in
[the corpus parity evidence](../2026-11-12-trilogy-corpus-parity/README.md).
