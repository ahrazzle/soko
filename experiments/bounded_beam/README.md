# Bounded beam search

`bounded_beam.cpp` looks for a route of at most `B` keys. It works layer by layer
(g = keys so far). Every child with `g + h > B` is dropped, where `h` is the same
heuristic `prove_lb` uses: goal distance, the quotient pattern databases and the
wizard ray bound. If `h` is admissible, that pruning never removes a route of length
`<= B`, so the beam width is the only incompleteness. States are deduplicated by
64-bit hash with the best g seen; a collision can drop a state but never accept a bad
route. Each layer keeps the `W` children with the smallest `h`, optionally capped
per bucket of hero positions for diversity. Expansion runs on all hardware threads.

```sh
g++ -O3 -pthread -std=c++20 experiments/bounded_beam/bounded_beam.cpp -o /tmp/bounded_beam
# stdin: part w h bound width seed per_bucket, then the grid rows
# bound < 0: read a route after the grid and print g + h along it
# seed == 0: also read a reference route and report, per layer, whether the beam kept it
```

## Recorded result (2026-11-14): the positive control fails on III-14

The heuristic is admissible along the known 48-key III-14 route (`max_f` = 48). Even
so, a bound-48 beam does not find that route at widths 20k, 50k, 200k or 1M, with or
without diversity buckets. The reference-tracking mode shows why. Around g = 25–34 the
route sits on an `h` plateau (h = 7–8 while f climbs from 33 to 42): it spends keys
setting up later progress. At g = 30, 403,523 candidates have strictly lower `h`, and a
much larger set ties with the route's `h` = 8. The 1M beam drops the route at g = 30.

Since the method cannot reproduce 48, a bound-47 run would say nothing about whether a
shorter route exists. Ordering by `h` alone is the problem here, not the pruning. A
useful version needs a better tie-breaker on plateaus (a learned or second heuristic)
or far more width than fits in this container.
