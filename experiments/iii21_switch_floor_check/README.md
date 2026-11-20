# III-21 floor check: do the published 74 / 75 / 76 count switch presses?

Scripts that test, on the repo's own oracle and assignment code, what the published
handoff floors for Room III-21 can and cannot say about the cost of hero-switch presses.

Run from `scripts/` with Python 3 (standard library only). Each script also runs under
`python3 -O -B -W error`. Each has a control that must fail.

| Script | What it checks |
| --- | --- |
| `layer_table.py` | Positions left to exclude when the floors rise by k = 0..6, for targets 270, 271, 272, from the published handoff tables in `web/`. |
| `winding_identity.py` | For every Part III catalog route, the count of A presses equals the winding of the activation order. |
| `sample_handoffs.py`, `sample_lower.py` | Breadth-first search from record-route states to real positions right after the crate enters the Druid's chamber. |
| `floor_compare.py` | For each sampled position: least move total over the 720 hero-to-exit assignments, least switch presses, their sum, and the repo's operator-counting bound. |
| `round_search.py` | Bounded exact searches from the record handoff: first Druid visit, and the active hero alone. |

`out/` holds the recorded outputs. `web/` holds copies of the published tables and verdict used as input (source claims).
