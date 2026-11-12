# Isolated III-14 search

This snapshot is the method, sources and recorded runs of an isolated III-14
search. It credits the isolated III-21 / III-14 search work. The files are
offered as methods and evidence. They do not establish a new room minimum.

## Best recorded route

`best.txt` is a 48-key route. Its first line is `48` and its second line is
`LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR`.

## The search author's claims

The search author stated, as claims accompanying this snapshot:

- A winning III-14 route shorter than 48 did not turn up in this search.
- Suffix-tree results from key 28, and from keys 33, 34, 38, 40 and 41,
  were called VERIFIED.
- A second 48-key example,
  `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURURAU`, has a different ending
  from `best.txt`.
- Beams from shorter harvests were a search result, not a proof that 48 is the
  room minimum.

What the checked-in logs record:

- `search.log` ends `FINAL 48` with the `best.txt` route.
- `exact_late.log` records `verified=True` 48-key wins at cut41, cut40, cut38
  and cut34, each finishing with `best=48` and an empty queue. The second
  48-key route is the one in those wins. The same file records cut33 ending
  at 45.0 s with `best=none`, and cut28 ending at 60.0 s with `best=none`.

## Files

- `iii14_search.py` is the Python engine with window and beam search.
- `exact_bfs.py` runs exact shortest-win BFS from prefixes of known routes.
- `iii14.rs`, `iii14_from.rs`, `beam.rs` and `beam2.rs` are the Rust engines
  for exact A*/BFS and beam search.
- `search.log`, `exact.log`, `exact_late.log`, `rust_search.log`,
  `beam_cuts.log`, `beam_harvest.log` and `beam2_run.log` are recorded runs.
- `SHA256SUMS` lists the snapshot files.

`iii14_search.py` and `exact_bfs.py` had their `/workspace/soko-search` paths
rewritten. Both now write `best.txt` in the working directory, and
`exact_bfs.py` imports `iii14_search` from its own directory. Their lines in
`SHA256SUMS` were updated to match. Every other listed file keeps its original
hash. `rust_search.log` is the original recorded log, so it still mentions the
original workspace path.

## Reproduction

From this directory:

```sh
rustc -O -C target-cpu=native iii14.rs -o iii14
./iii14 search 25 23 150 bfs
PYTHONPATH=/path/to/soko python3 iii14_search.py
PYTHONPATH=/path/to/soko python3 exact_bfs.py
```

`./iii14 search 25 23 150 bfs` is the invocation recorded in
`rust_search.log`. `PYTHONPATH` should include this repository's root so the scripts can import
the package's Python oracles. They also insert `/workspace/soko`, the original
checkout. A run that finds a route rewrites `best.txt`, so copy the tree first
to keep the recorded file.
