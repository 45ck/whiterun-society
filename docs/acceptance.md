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

The custom bridge received and acknowledged a look-at command. That proves execution of the native call, not yet a close visual measurement of head movement. The observer screenshot and structured evidence are retained; selected screenshots document the running prototype. Game asset archives and third-party binaries are not distributed with this source repository.

Cold-start testing exposed an incomplete SKSE script library in the initial isolated copy. Installing all 62 compiled scripts from the official matching 2.2.6 package fixed the cold startup. Native NPC handles expire between callbacks in this runtime; the bridge now keeps only IDs and resolves fresh handles before actions. These failures are covered separately from the standalone economy tests.

### First live inventory trade

Experiment `live-purchase-20261024-001` transferred one loaf from Carlotta Valentia (0x1a675) to Ysolda (0x1a69a) for 3 gold. Before: Carlotta 10 gold / 1 loaf; Ysolda 9 gold / 0 loaves. After: Carlotta 13 gold / 0 loaves; Ysolda 6 gold / 1 loaf. These are actual game inventory observations, not seeded simulation accounts. The journal committed only after the native acknowledgement and subsequent inventory observation agreed. Repeating the same request returned the existing committed record and left the inventories unchanged.

This was an externally requested probe. It does not demonstrate autonomous shopping, physical navigation to a seller, generated speech, or save/load restoration. Trade effects are applied in two native transfer legs; partial or ambiguous effects are held for reconciliation. The system does not claim a cross-container atomic game transaction.


## Visual spectator slice — 24 October 2026

Observed inside the live lab Skyrim process: transparent society overlay at 1280x720; live resident cards and inventory counts; an inventory-verified trade receipt; automatic market, resident, trade-pair and street cameras. The closer resident offset avoids the foreground stall obstruction seen in the first camera experiment. This is runtime visual evidence, not a claim of autonomous shopping or human believability.

Manual mouse events did not reach the UI reliably during qualification. Manual controls are disabled while this is investigated. Automated tour messages did reach the native bridge and changed the actual game camera. Camera raycasts/occlusion handling, save-lineage restoration, autonomous commerce, conversation and speech/lip sync remain open.


## Save marker proof — 24 October 2026

The original minimal `WhiterunSociety.esp` contains a non-constant float global (local form 0x800). Skyrim loaded it, and a real save/load experiment produced 101 -> 202 -> 101. The save and SKSE cosave were written into the isolated Mod Organizer profile. This proves the engine marker round trip; it does not yet prove restoration of the external economy or NPC memories.

Initial save requests produced no file. The installed NirnLab overlay's always-open MultiLayerMenu omitted `kAllowSaving`. Source inspection and disassembly located `or dword ptr [rdi+0x1c], 0x18002`; adding only flag 0x800 allowed the next save to be written. `tools/patch_overlay_save.py` refuses every binary except the exact inspected SHA-256, retains the original DLL, and distributes no third-party binary. Source: https://github.com/kkEngine/NirnLabUIPlatform/blob/main/src/UIPlatform/Menus/MultiLayerMenu.cpp ; flag definition: https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/main/include/RE/I/IMenu.h . This is a narrowly scoped local compatibility patch, not a general fix for other builds.

The prior unsaved trade experiment and both SQLite databases were archived before this test's fresh city start. No claim is made that the earlier unsaved trade survived a restart. Its evidence remains valid for that earlier run.

The marker test was followed by an XAudio2_7.dll access violation on the audio thread after 79 seconds of process uptime. The crash log identifies the isolated game process. This does not establish a cause, but it means save/load stability is not accepted. A subsequent cold observer launch succeeded in 42.5 seconds. The save-marker result must not be promoted to a stable save/load claim.

## First local AI proposals — 24 October 2026

Three actual local model requests used observed Skyrim inventories and authored Big Five profiles. The resulting proposals appeared in the live observer overlay. The second run took 4.641–5.672 seconds per resident; replaying its event ID made zero additional model calls. This is a bounded event runner, not an always-running agent loop. See [decision design and measured limitations](npc-decisions.md).

All three residents selected the same proposal, and one explanation contradicted its action. A third run with an explicit consistency instruction removed that particular contradiction but produced overly analytical, sometimes cut-off explanations (5.797–8.172 seconds). Neither run establishes believable personality effects. No proposal has been executed as an autonomous game action, and no memories or relationships were changed.

## Save-linked trade and memory: subsequent experiment

Timeline-20261024-01 explicitly provisioned Carlotta with three starting loaves, without minting gold. Save A bound checkpoint 1: Carlotta 13 gold / 3 bread; Ysolda 18 gold / 0 bread; no trade memories. An externally requested purchase bound prepared checkpoint 2 before touching inventory. The verified exchange then bound checkpoint 3: Carlotta 16 gold / 2 bread; Ysolda 15 gold / 1 bread. Both residents acquired a factual trade memory and one trust point under an authored rule. This is not a validated psychological model.

Loading A restored checkpoint 1, its exact inventories, empty trade history and empty memories/trust. Loading B restored checkpoint 3, its exact inventories, committed history and memories/trust. A duplicate trade request changed none of those. The structured evidence and save hashes are in [save-lineage-live.json](evidence/save-lineage-live.json).

The first restore attempt exposed event ordering: the engine loadGame callback arrived before SKSE preLoadGame. Pairing SKSE preLoadGame with postLoadGame fixed the stuck observation barrier; both subsequent restores passed without hot reload between them. The distinct events are declared in the [upstream API definitions](https://github.com/skyrim-multiplayer/skymp/blob/main/skyrim-platform/src/platform_se/codegen/convert-files/Definitions.txt).

The game subsequently crashed again in XAudio2_7.dll on the audio thread. Therefore state restoration is demonstrated, but sustained runtime/save-load stability is still not accepted. The lab was relaunched into a fresh zero-marker world; the two tested saves and their immutable checkpoints remain retained. The latest world is not represented as the restored trade world.

The timeline database is now authoritative for managed commerce and social state. The older world.sqlite journal remains historical and is not automatically imported. Unknown/corrupt markers block commerce; a new zero-marker world requires explicit bootstrap. Prepared saves retain the original before/after trade intent so existing transfer logic can reconcile partial effects. Mid-trade restore is covered by tests but has not yet been demonstrated with an actual Skyrim save. Keep the timeline database together with the game saves; external backup/deletion recovery remains to be qualified.

## Agent ownership of routines

Location and routine decisions must come from the society planner. Custom quest packages now demonstrably override Ysolda's ordinary schedule: one trip to Adrianne covered 4,116.88 to 247.98 game units in 47 seconds, and another to Carlotta covered 698.91 to 248.93 units in about 7 seconds. Both reported the expected custom package while travelling, then its release. [Forge evidence](evidence/agent-package-forge.json), [market evidence](evidence/agent-package-market.json).

These destinations were test-selected. Autonomous choice, continuous daily routines, multi-resident scheduling and save-linked plans are still open. The in-game panel shows the traveller, destination, phase and distance, explicitly labelled as a test. [Agent control acceptance and build instructions](agent-control.md).

![Observed travel result in Skyrim](images/agent-task-panel.jpg)

## Resident-selected choices, consent and memory

The later Jev experiment replaces test-selected destinations with a bounded
resident decision. Two real meal-time events selected seeking bread from Carlotta,
obtained a seller refusal, released the task and preserved inventories. The first
travelled from 762.52 to 249.63 units under our package; the second started within
200.98 units, proving package ownership at proximity but no new journey.
The second event received the first refusal in
both participants' memories, yet repeated the choice. Memory retrieval is proven;
adaptive judgement is not. [Run evidence and reproduction](agent-control.md#resident-selected-errand-and-consent).

The prototype now persists planner stages with the game checkpoint, and tests
cover restoration and stale model-call claims. Actual Skyrim save/load of those
new stages is still open. A model-approved completed purchase is covered by the
integration test but has not occurred in these live Jev runs. The prior externally
requested physical purchase remains separate evidence.

The observer panel shows provider, selected actions, timings and remembered
events. Labels explicitly distinguish choices from spoken dialogue. Vision is
experimental and excluded from resident knowledge pending controlled validation.
Full economy, adaptive daily routines, speech and player experience remain open.

![Actual resident choices and refusal memories](images/jev-resident-decisions.jpg)

## Reconsideration and settled-plan save/load

The subsequent negotiation run selected a higher five-gold offer after an initial
three-gold refusal. The seller independently refused again. Both offer outcomes
were remembered and the task released without moving inventory. A bounded choice
changed the plan; the two-offer limit is authored, not learned. Physical acceptance
of a revised offer is tested but has not occurred in-game.

Actual save A/B restores now match complete settled plans, people, memories,
inventories and trade journals at checkpoints 23 and 45. The new verifier checks
save/cosave hashes and a fresh game session. This closes the settled-plan restore
gap; in-flight planning/trade recovery and sustained audio stability remain open.
[Detailed evidence and limitations](agent-control.md#revised-offer-and-actual-plan-restoration).

Validation for this slice: 46 Python and 31 JavaScript tests passed locally,
UI script syntax checked, actual observer rendering inspected, and fresh bridge
reattachment observed in 1.2 seconds. Human believability, continuous daily life,
consumption, production integration, voice/lips and player participation remain
requirements, not implied by these checks.

## Resident reserves and physical consumption

Carlotta selected a household reserve policy and then native food use. Observed
bread decreased 3 to 2, gold stayed 5, and simulated hunger decreased only after
inventory confirmation. The current food save and the preceding negotiation save
restored their corresponding plans, people, inventory and journals. A repeated
meal made zero model calls; a request to buy reserved stock was rejected unchanged.
[Evidence and detailed limits](food-economy.md).

Current local validation: **54 Python and 36 JavaScript tests passed**. The UI was
inspected in Skyrim. Hosted CI remains unverified. Native consumption animation,
interrupted consumption recovery in-game and continuous metabolism remain open.

Correction to earlier release evidence: a generic bridge acknowledgement could
precede actual package removal. This path is fixed and regression-tested, but the
fix still needs a new live release qualification. Earlier walking and arrival
observations are unaffected; release acknowledgements alone were insufficient.

## Paid work with finite inputs

The next live run independently selected employer offer and worker acceptance.
Observed attendance for 30 game minutes preceded conversion of one grain into two
loaves and a conserved two-gold wage. Both people remembered the result. Actual
before/after saves restored the matching production, imports, inventory and
memories. Duplicate event delivery did not repeat inference or pay again.
The corrected native release path now has a successful in-game acknowledgement
after the package disappeared. [Detailed evidence](paid-work.md).

Current local validation: **59 Python and 43 JavaScript tests passed**. A new audio
stack crash occurred while loading the older food save; the lab restarted and
both later work-save restores succeeded. Sustained stability remains open.
Production is an authored grain conversion with observed attendance; oven
animation, a daily labour market, fatigue, separate firm accounts and a complete
player shortage scenario remain unfinished.
