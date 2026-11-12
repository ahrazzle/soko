# What the original evaluation actually asks

Assessment on 2026-11-12, after reading banteg's [Eight moves to the exit](https://banteg.xyz/posts/sokoban/) (published 2026-11-10), the [live Frontier](https://soko.banteg.xyz/frontier/), its public read-only room endpoints, and Ostroff's original Part I source.

## Two different tasks

The [original race](https://banteg.xyz/posts/sokoban/#the-race) measures an agent playing 66 rooms across three sequential games. It receives the visible board, an image and tutorial text. Each game allows five active hours, 1,000 replies and 10,000 keys. Responses must be one bare JSON object; formatting mistakes consume resources. Moves, switches, undo and restart all affect how a run uses its budget.

In the [Python condition](https://banteg.xyz/posts/sokoban/#giving-the-wizard-a-python-interpreter), the notebook has no network, game files or referee access. Cells have a four-second limit and the VM freezes between calls. A source-aware MCP with preloaded puzzle implementations is therefore an unrestricted research helper, not a comparable entrant in either scored condition.

The Frontier is a different, open optimization challenge. It accepts shorter routes and reproducible lower-bound claims. Its rules say routes replay in Jonah Ostroff's original PuzzleScript build and must first clear on the final input. A valid route below a claimed bound refutes the bound. Local interpreter agreement is useful preparation, not original-engine acceptance.

## Current targets

The public `/api/frontier` response inspected on 2026-11-12 lists 66 rooms, with every current record equal to the displayed shortest-known length. Three rooms still have a proof gap:

| Room | Displayed lower bound | Shortest known/current record | Current holder |
| --- | ---: | ---: | --- |
| III-14 | 43 | 48 | SJanuskas |
| III-20 | 74 | 84 | a1kindus |
| III-21 | 268 | 316 | futarchist |

These are dated observations of the service, not independently reproduced proofs. A useful Frontier result must shorten one of these accepted routes or raise a defensible lower bound. The local 11-to-9 canary in the [MCP exercise](../evidence/2026-11-12-mcp-exercise/README.md) does neither.

## A confirmed instance mismatch

The article begins with eight right moves. The [original Part I game](https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban.html) contains this opening room:

```text
#############
#...........#
#.F.......G.#
#...........#
#############
```

The embedded PuzzleScript source captured on 2026-11-12 has SHA-256 `81a1d27115fc40c04f27bb39d0ef12ebffbea513e3fe9f550b5173bb683728a3`. The public `/api/play/1/1` response independently reports a 13-by-5 board, and `/api/frontier` reports an eight-key optimum/record.

The repository's `I-1` is a different 12-by-5 fixture whose hero and goal are nine steps apart. All three local replay engines accept eight rights on the original board and reject nine as a premature win. Agreement among local engines did not reveal the wrong fixture identity.

The earlier exercise remains a valid regression on its explicitly recorded repository fixture, but must not be presented as a solve or improvement of original I-1. Historical evidence is preserved rather than silently relabeled. Replacing the registry requires an authoritative instance import and corresponding provenance/tests; this assessment does not silently change those inputs.

## What transfers to the next attempt

- **Probe mechanics before relying on a model.** The [chain-pushing example](https://banteg.xyz/posts/sokoban/#how-many-crates-can-you-push) shows how standard Sokoban assumptions fail, and a rule-order change can agree for twelve frames before diverging. The wizard's one-key swap experiment is a better foundation than guessing its ability from a hint.
- **Plan, then use a small model where it helps.** Fable skipped Python in 43 of 66 rooms and never built a general solver. Its 88 notebook calls contrasted with Opus's 735; room-specific simulation helped test proposed routes. The article supports selective planning and model repair, not a claim that larger generic BFS is sufficient.
- **Preserve state and budget.** Context resets, repeated restarts, long batches and invalid reply formats changed outcomes independently of puzzle-solving ability. A useful agent loop needs checkpoints, short diagnostic actions and explicit resource accounting.
- **Distinguish capability from familiarity.** The article reports one scored run per model/condition and discusses [prior recognition](https://banteg.xyz/posts/sokoban/#have-you-played-this-before). Reproducing a known route does not establish generalization to unseen puzzles.

The next serious exercise should start with an authoritative open-room capture and original-engine baseline replay. A room-specific plan can then identify useful subgoals, reversible local changes, and small search spaces. Every proposed improvement should be replayed against the same original instance. For a stronger floor, an abstraction needs an explicit mapping that preserves the relevant transitions and costs; a local search status is not a substitute.

Sources and credit: evaluation and write-up by banteg; game rules and puzzles by Jonah Ostroff; current route-holder attribution above comes from the service. No route or proof was submitted as part of this assessment.
