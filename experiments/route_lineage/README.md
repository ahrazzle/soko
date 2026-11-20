# Route lineage (2026-11-20)

These tools ask whether a set of winning routes are independent attempts or one plan polished many times. The 2026-11-13 [stall result](../../evidence/2026-11-13-seeded-search-stall/README.md) explains why that matters: searches that share a starting route count as one observation.

- `fetch_public.py` downloads every public record route for some Frontier rooms.
- `lineage.py` replays each route in the spec oracle and lists its milestones: `open x,y` (a wall stops being a wall), `wall x,y` (a cell becomes a wall), `kill x,y` (the goblin that started at (x,y) dies) and `petrify x,y` (that goblin is turned into a wall). Goblins keep their identity through pushes, swaps and carries, so a moved goblin is never counted as dead. It compares every pair of routes in a room three ways:
  - **milestones:** Jaccard overlap of the milestone sets;
  - **order:** order agreement on the milestones both routes share;
  - **states:** Jaccard overlap of the exact board states visited.
- `report.py` prints three tables: plan families (single-linkage clusters on milestone overlap), each record against the record it replaced, and when a chosen milestone happens.

```sh
python3 experiments/route_lineage/fetch_public.py --output /tmp/public.json
python3 experiments/route_lineage/lineage.py /tmp/public.json --output /tmp/lineage.json
python3 experiments/route_lineage/report.py /tmp/lineage.json --room III-21 --opening "kill 13,9"
```

Known-answer tests are in `tests/test_route_lineage.py`. Results for the open rooms are in [evidence/2026-11-20-public-route-lineage](../../evidence/2026-11-20-public-route-lineage/README.md).

## Limits

- Milestones are a coarse plan. They split plans apart, but they cannot certify that two plans match in every respect.
- Shared exact states point to shared lineage only on rooms with room to move. On III-10, an independent cold route shares 45% of its states with the reference.
- Heavy rewriting erases the state trace. An optimizer pass that turns a 91-key route into 52 keys keeps under 1% of its states.
