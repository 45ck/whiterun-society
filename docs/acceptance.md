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
| Unattended launch | Start directly in Whiterun without playing the opening | Clean launch reached observer readiness in 27.56 seconds; 26 actors detected |
| World consistency | Inventory and ledger agree after trades and reloads | One live inventory trade and duplicate retry verified; save/load still unimplemented |
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

## Live evidence, 24 October 2026

The isolated game launched from the helper without character setup or manual play. Its new bridge session reported WhiterunOrigin (0x1a27f), a loaded player and 26 loaded actors after 27.56 seconds. Counts include guards and animals; they are not a count of fully simulated citizens. Live names included Ysolda, Nazeem, Carlotta Valentia and Adrianne Avenicci.

The custom bridge received and acknowledged a look-at command. That proves execution of the native call, not yet a close visual measurement of head movement. The observer screenshot and structured evidence are retained locally. Existing game assets and screenshots are not distributed with this source repository.

Cold-start testing exposed an incomplete SKSE script library in the initial isolated copy. Installing all 62 compiled scripts from the official matching 2.2.6 package fixed the cold startup. Native NPC handles expire between callbacks in this runtime; the bridge now keeps only IDs and resolves fresh handles before actions. These failures are covered separately from the standalone economy tests.

### First live inventory trade

Experiment `live-purchase-20261024-001` transferred one loaf from Carlotta Valentia (0x1a675) to Ysolda (0x1a69a) for 3 gold. Before: Carlotta 10 gold / 1 loaf; Ysolda 9 gold / 0 loaves. After: Carlotta 13 gold / 0 loaves; Ysolda 6 gold / 1 loaf. These are actual game inventory observations, not seeded simulation accounts. The journal committed only after the native acknowledgement and subsequent inventory observation agreed. Repeating the same request returned the existing committed record and left the inventories unchanged.

This was an externally requested probe. It does not demonstrate autonomous shopping, physical navigation to a seller, generated speech, or save/load restoration. Trade effects are applied in two native transfer legs; partial or ambiguous effects are held for reconciliation. The system does not claim a cross-container atomic game transaction.


## Visual spectator slice — 24 October 2026

Observed inside the live lab Skyrim process: transparent society overlay at 1280x720; live resident cards and inventory counts; an inventory-verified trade receipt; automatic market, resident, trade-pair and street cameras. The closer resident offset avoids the foreground stall obstruction seen in the first camera experiment. This is runtime visual evidence, not a claim of autonomous shopping or human believability.

Manual mouse events did not reach the UI reliably during qualification. Manual controls are disabled while this is investigated. Automated tour messages did reach the native bridge and changed the actual game camera. Camera raycasts/occlusion handling, save-lineage restoration, autonomous commerce, conversation and speech/lip sync remain open.
