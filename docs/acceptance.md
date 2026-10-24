# What counts as working

## Objective: a society whose actions change the playable world

Initial demonstration: a farm, a bakery, three households, finite gold and food, and a failed harvest. A player can inspect what happened and later intervene. This is the first vertical slice; full Whiterun, politics, rent, trade routes and richer relationships are later increments.

| Measure | Initial acceptance | Current evidence |
|---|---|---|
| Money accounting | Every transfer balanced; every mint/burn explicit | Standalone tests pass; no mint/burn in baseline |
| Goods accounting | Trades conserve stock; production/consumption record transformations | Standalone tests and event ledger |
| Autonomous commerce | NPC-to-NPC wages, input purchases and household purchases | Standalone farm/bakery/household loop |
| Resilience | Retry never charges twice; partial failure rolls back | Standalone tests pass |
| Scarcity | Harvest failure causes measurable unmet food demand | Standalone scenario test passes |
| Visible action | One observed NPC moves or responds to our command | Not demonstrated |
| World consistency | Inventory and ledger agree after trades and reloads | Not implemented |
| Save lineage | Loading an older save restores its matching society state | Not implemented |
| Conversation | NPC answers reflect witnessed events and personal interests | Rule-based opinion example only |
| Voice | Spoken response and matching lip movement in-game | Not implemented |
| Enjoyment | Player can explain a consequence and chooses to continue | Requires actual playtesting |

Targets are acceptance criteria, not claimed results. Track p50/p95 response latency, FPS impact, failed navigation, duplicate actions, contradictions and player ratings once the relevant path actually runs. Do not use language-model self-ratings as evidence of player enjoyment.

## Development cycle

1. Change a small part of the simulation or bridge.
2. Run focused tests and syntax checks; commit the verified slice.
3. Push to public GitHub; check the exact commit's Windows/Linux CI results.
4. Deploy only our plugin to the isolated game profile.
5. Reobserve the game; inspect both the visible result and structured bridge events.
6. Record failures as failures, adjust, and repeat.

The initial implementation uses Python's standard library and JavaScript, avoiding a native compile for each experiment. Skyrim Platform advertises script hot reload, but reload cleanup and live behavior must be verified locally. Native changes or unsafe state changes require a fresh game process.

## Boundaries

- Only game facts enter the simulation. Real email, browser history, workplace data and personal accounts are outside its scope.
- The local development bridge accepts an explicit small command set, not arbitrary code or shell commands.
- The existing Steam install and saves are not the test target.
- No generated dialogue may mint currency, invent stock or rewrite the authoritative ledger.
- A simulated off-screen transaction is distinct from a visually observed physical action.

## Sources for integration

- [Skyrim Platform](https://github.com/skyrim-multiplayer/skymp/blob/main/skyrim-platform/README.md)
- [SKSE](https://skse.silverlock.org/)
- [Mod Organizer releases](https://github.com/ModOrganizer2/modorganizer/releases)

The development installation currently targets Skyrim 1.6.1170 and SKSE 2.2.6. Do not automatically replace them with a newer version without checking compatibility.
