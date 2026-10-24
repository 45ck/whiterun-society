# Whiterun Society

An experimental, open-source society simulation for Skyrim Special Edition: a city economy you can live inside.

Residents should work, trade with one another, consume goods, remember events and form different opinions. The player can participate as a resident or influence policy. Skyrim supplies the physical world; our simulation owns economic rules, decisions and evidence.

**Active goal:** a Sims-like society with a functioning economy inside Skyrim, where you can watch individual lives and understand why their decisions change the town. Development includes visual architecture updates, actual game screenshots and, next, recorded demonstrations of conversations and economic consequences.

**Visual documentation:** [all 27 finished images](docs/gallery.md) · [gallery website](https://45ck.github.io/whiterun-society/) · [26 measurable development OKRs](docs/society-okrs.md). Images live in `docs/images`; illustrations and captured prototype interfaces are labelled separately.

**Development prototype, not a complete society mod.** The isolated game starts directly in Whiterun with an observer camera. Actual inventory transfers, paid production, food consumption and generated voiced encounters have been demonstrated. Full daily routines, lip sync and sustained audio stability remain unfinished. The autonomous farm–bakery–household model still runs separately.

## The whole simulation

![Generated overview of the Whiterun society simulation and its planned expansion](docs/images/whole-simulation.png)

*Generated system illustration, not a game screenshot. Each panel labels the current foundation; the bottom band describes future work.*

## How one NPC works

![Generated infographic showing the deterministic simulation, Jev, optional language and voice, and Skyrim execution](docs/images/npc-four-systems.png)

**Our code maintains state and valid options → Jev chooses → Skyrim performs the physical task → our code verifies the result and remembers it.** When conversation is appropriate, a language model proposes lines, Jev selects, and local Kokoro voices the chosen words. Walking, work attendance and quiet periods need no continuous model calls. Skyrim handles navigation and movement; choosing a destination does not mean asking a model to calculate every footstep.

[Living development plan: dynamic residents, personal knowledge and RTS mode](docs/development-plan.md) · [Full system guide, NPC loop and data model](docs/system-guide.md) · [Latest verified progress](docs/town-progress.md) · [Video demonstration plan](docs/demo-videos.md)

The language role can use a small, inexpensive model; it does not require frontier reasoning for every line. Cloud inference through OpenRouter is the selected direction. Mercury 2.5 is now the experimental lab default after a complete two-turn voiced encounter: 58.811 seconds including approach and playback, with US$0.000718912 reported across two language requests and six Jev decisions. Grounding failures from earlier probes remain documented; one successful scene is not broad qualification. [Model pricing, measured timings and routing direction](docs/model-routing.md)

## Examples from the running prototype

### Conversations in an established town

Speech now receives game time, the latest heard line, known relationships and actual commitments. Short acknowledgements and goodbyes no longer need padded sentences. The current 20 civilian residents have an explicit initial shared-town acquaintance, separately labelled from earned relationship history; future arrivals can still be strangers. Concurrent town-wide conversation and full routine ownership remain unfinished. [Dialogue context, initial state and evaluation](docs/situated-dialogue.md)

### Hear an actual negotiation

![Generated illustration of the implemented voiced trade protocol, not gameplay](docs/images/voiced-trade-loop.png)

Jev chooses the economic actions; deterministic wording keeps spoken amounts aligned with the terms; local Kokoro speaks them; Skyrim performs movement and inventory changes. A live Amren–Carlotta trial delivered **four turns**: offer 3 gold, refusal, offer 5 gold, refusal. Both actors were released and **no gold or bread transferred**. This proves a voiced refusal/counteroffer path, not a successful sale. [Protocol and limits](docs/voiced-trade.md)

The observer now includes an interruption control, derived friendship bands, small-talk word cues, current native Skyrim race labels and **26 OKRs** spanning social, economic, physical and behavioural experiments. Most psychology, semantic-dialogue and evolutionary-mechanism measures remain **unmeasured**. Friendship bands are authored game rules, not psychological diagnoses. [Definitions and thresholds](docs/society-okrs.md)

### Watch a running society and measure its limits

The control room now has **Start society**, **Stop after encounter**, and **Follow activity**. A bounded session alternates eligible economic and social events, offers nearby conversations when urgent-needs queues would otherwise crowd them out, and lets residents accept or decline. The in-game overlay identifies whether the director is running or idle. Both consenting speakers now receive temporary attendance packages; release must be verified for both.

The **Society quality lab** reports encounter failures, duration, reply gaps, body-facing error, physical economic outcomes and relationship counts. Unknown gaze/raycast accuracy, lip sync and human realism remain unscored. The initial live baseline was **4/6 accepted chats completed**, **zero sales in the current save**, **two production events** and **39 meals**; the ledger includes staged experiments. There is still only one sale good and one production recipe. These are shortcomings to fix, not a high realism score. [Metrics definitions, baseline and acceptance targets](docs/quality-metrics.md)

Conversations now allow up to **six turns**, with a fresh listener decision to reply, close politely or leave quietly. A live three-turn exchange completed with a model-chosen closing and verified native release. A voice worker warmed during approach generated each line in 1.8–2.1 seconds; the full reply gaps were still 10.3–10.6 seconds. The current lineage reached **8/10 completed chats**, but retained dialogue still invents work details and does not execute suggested actions such as sitting. [Transcript, timings and grounding defects](docs/evidence/extended-dialogue-live.json)

[Hear Anoriath and Brenuin's generated voices](docs/media/anoriath-brenuin.wav) · [Playback receipts and retained failure](docs/evidence/visible-conversation.json). This sample concatenates the two generated voice assets from an engine-confirmed encounter; it is **not a recording of the game or proof of physical audio output**.

### Change the town's businesses

The visual observer now creates and edits enterprises for current residents: custodian, wage, shift duration, stock target, and open or closed status. A census no longer creates businesses for a fixed named cast. Residents compare current jobs and independently accept or refuse the offered terms; native inventory backs wages and production. The live four-gold employment trial produced an employer refusal, which is preserved as a real model outcome. [Enterprise controls, execution loop and test evidence](docs/enterprises.md)

### Personal knowledge and the RTS overview

![Generated infographic of personal knowledge, Jev choices, Mercury speech and verified memory](docs/images/personal-knowledge-loop.png)

*Generated implementation guide. Nara's introduction is an illustrative example; the live encounter below did not include an introduction.*

![Actual Skyrim RTS overview with native resident markers](docs/images/rts-live-overview.jpg)

Residents now distinguish strangers from people whose names they heard in an introduction. Seller choices use current enterprise capabilities, and a normal town encounter uses the current population. The browser control room operates the native camera and inspects individual knowledge and relationships. The in-game RTS panel and markers render, but injected mouse and keyboard activation still need qualification. The latest voiced encounter restored all 14 checked state fields from its Skyrim save. [Changes, costs, evidence and remaining work](docs/dynamic-society.md)

### People talk and remember

![Actual Skyrim capture of Adrianne and Idolaf during a generated voiced encounter](docs/images/resident-social-live.png)

Adrianne chose Idolaf, approached, and completed a short generated exchange. Each formed a separate appraisal; both stayed neutral in this trial. The screenshot shows the delivered line and her inspector. She is partly hidden by a post, so camera framing still needs work. These are two-turn exchanges, not yet sustained natural conversations. [Social evidence](docs/resident-social.md)

### Work creates goods and pays wages

![Actual Skyrim capture of completed bread production and the wage transfer](docs/images/paid-work-complete.jpg)

Carlotta offered work and Ysolda accepted. Thirty qualified game minutes converted one grain into two bread and transferred two gold from employer to worker. Native inventories and save/load were checked. This is an authored attendance recipe; an oven animation and sustainable upstream supply are unfinished. [Production evidence](docs/paid-work.md)

### Watch separate lives across town

![Actual connected observer with resident selection, camera controls and independent journey states](docs/images/seven-resident-observer.jpg)

The browser control room selects residents and controls the game camera with follow, zoom, orbit and pan. A bounded director run reached **seven concurrently owned native journeys**, each with its own Jev choice, arrival and release. Some had already finished when this screenshot was captured; the current UI separates peak concurrency from the number travelling now. A failed market visit remains a failed visit, without invented food or hunger relief. [Latest receipts and limitations](docs/town-progress.md)

**Current scope:** 29 initialized adults, 23 decision families across multiple stages, and one executable production recipe. Those families include policies and private appraisals, not 23 physical actions available at once. Whole-town autonomy, connected businesses, families, richer drama and political intervention remain the target. [What counts as meaningful variety](docs/system-guide.md#how-many-possibilities)

## Development evidence history

<details>
<summary>Earlier milestones, experiments and retained limitations</summary>

**Voiced encounters:** Ysolda and Carlotta discussed their bread disagreement using generated voices. A language model proposed intentions, Jev chose, and deterministic code delivered speech and recorded heard claims only after playback. Those memories reached Carlotta's next stock decision. The latest two-turn encounter took 47.098 seconds, including local synthesis and playback, with US$0.001638432 in reported model cost. Voices currently use the overlay audio channel; native audio is disabled for crash diagnosis. [Voiced encounters and evidence](docs/voiced-encounters.md) · [Finite market day](docs/market-day.md) · [Paid work](docs/paid-work.md) · [Human behaviour design](docs/human-behaviour.md).

![Generated speech and speaker close-up in the actual Skyrim observer overlay](docs/images/conversation-closeup.jpg)

Save-linked trade history, factual memories, trust and settled decision plans restored correctly from actual before/after Skyrim saves. Earlier audio-thread crashes still prevent accepting sustained save/load stability; active-plan recovery needs live qualification. Economic events still settle one at a time. The independent-journey pool now runs separate native travel tasks concurrently; ordinary Skyrim routines resume after release. [Evidence and limitations](docs/acceptance.md) · [Agent control](docs/agent-control.md).

**Population milestone:** 26 loaded adult NPCs now have persistent starting needs, traits and household records, with two business charters referencing real inventories. Actual before/after Skyrim saves restored the population correctly. This does not yet extend native routine ownership to all of them. [Population state, visual overview and evidence](docs/population.md).

**Daily-life milestone:** the roster has expanded to 29 residents. Game-clock reviews advance needs, preserve quiet periods and queue feasible decisions without constant model calls. Live reviews and the later save restored correctly; an earlier restore exposed differing guard purses, so whole-town inventory persistence remains unresolved. The Papyrus router is now deployed and connected to decisions; see the newer routing experiment below. [Daily life, limitations and evidence](docs/daily-life.md).

**Routing experiment:** Idolaf took an owned task outside the original three-resident system, travelled from 3,840 to 247 units and returned to a vanilla package. Separate Jev trials selected a nearby visit and a deferral. The daily planner can now offer supported food errands to other loaded adults. Save P restored all compared fields; save N exposed gold differences in named residents as well as guards. [Routing, decisions and retained failures](docs/papyrus-routing.md).

**Resource milestone:** all 29 initialized residents received finite, once-per-lineage native grants: 660 gold, 58 bread and 20 grain in total, with 340 gold, 42 bread and 80 grain left in the explicit external pool. A cold restart restored all 29 funded inventories exactly. A subsequent game-clock review led a guard, Amren and Adrianne to choose and consume one loaf each; the post-meal save also restored correctly. Earlier unfunded guard-purse failures remain documented. [Resources, scheduled meals and evidence](docs/founding-resources.md).

**Latest employment experiment:** the planner now supports eligible workers beyond Ysolda, business stock reviews, bilateral job consent and save-bound contracts. Live trials completed 25 further meals, a stock review and two employer refusals across 28 decisions. Carlotta retained her reserve policy and did not hire; no new worker's completed shift is claimed. The final state restored correctly. [Employment, economic bottlenecks and evidence](docs/resident-employment.md).

**Live observer:** select any initialized resident, inspect needs, personality, memories and existing relationships, and control Skyrim's camera with follow, zoom, orbit and pan. Browser controls were exercised against the game; a tour-control conflict was found and fixed. The earlier rest-launch failure is retained; a later explicitly enabled trial now verifies seated recovery. [Control room, screenshot and exact limits](docs/live-observer.md).

**Resident-chosen social encounters:** Amren chose Saffir; Adrianne chose Idolaf. Both pairs approached under owned tasks, accepted, completed generated voiced exchanges and separately appraised what they heard. Amren and Saffir felt supported; Adrianne and Idolaf stayed neutral. Both settled saves restored correctly. [Social decisions, actual game screenshot, costs and limits](docs/resident-social.md).

**Rest milestone:** Idolaf chose a bench, walked there, completed 30 observed game minutes seated and recovered simulated fatigue only after verified release. Save/load preserved the result. The plugin remains experimental; a successful retry does not explain the earlier hang. [Native rest, save diagnostics and limits](docs/seated-rest.md).

**Known destinations:** Idolaf chose to check the public market while Carlotta was unloaded, completed the native walk and remembered that no seller was nearby. All 29 native inventories stayed unchanged, and the result survived saving and loading. The observer now displays public destinations and travel intentions. [Evidence and limits](docs/known-destinations.md).

**Concurrent journeys:** the first trial verified Amren and Adrianne travelling together. A later bounded director run verified seven concurrent journeys, with all seven outcomes preserved after save/load. Eight slots are built; seven have now been qualified live. [Architecture and initial evidence](docs/parallel-routines.md) · [Seven-person follow-up](docs/town-progress.md).

</details>

## Run the tests

Python 3.12+, no third-party Python dependencies:

```sh
python -m unittest discover -s tests -v
python town.py --days 30
node --test tests/bridge.test.cjs tests/inventory-transfers.test.cjs tests/movement.test.cjs tests/agent-routines.test.cjs tests/papyrus-router.test.cjs tests/endowments.test.cjs tests/production.test.cjs tests/speech.test.cjs tests/rest.test.cjs tests/observer-camera.test.cjs
```

The tests exercise conservation of currency and stock, insufficient resources, duplicate delivery, persistence and separate simulation checkpoints. A passing unit test is not proof that an NPC acted inside Skyrim.

## Architecture

1. Skyrim owns native items and gold. A local service records observations, economic journals, needs, decisions and beliefs in save-linked SQLite checkpoints.
2. A Skyrim Platform bridge and Papyrus packages report game state and perform bounded commands. Native navigation executes chosen destinations.
3. Event-triggered reviews build feasible options. Jev chooses; deterministic rules validate both the decision and its observed consequences.
4. The language adapter proposes dialogue alternatives; Jev selects and local Kokoro generates speech. Verified nearby playback becomes a source-tagged memory, not proof that the statement is true.

See the [complete flow and data model](docs/system-guide.md) for authority boundaries, current action counts and the next acceptance targets.

An unloaded citizen can participate in abstract simulation, but we must not claim they physically walked or spoke unless the game reports it. Pausing or closing the game should pause progression by default.

## Development setup

Use a legitimately owned copy of Skyrim Special Edition. The initial experiment targets runtime 1.6.1170 with SKSE 2.2.6 and the locally installed Skyrim Platform 2.9 build using NirnLab UI. The live connection has been demonstrated on that setup; compatibility with other distributions is untested.

`tools/prepare_runtime.py --source "YOUR_GAME_DIRECTORY" --root "SEPARATE_LAB_DIRECTORY"` copies selected local game assets and existing bridge dependencies into an independent experiment directory and downloads the official Mod Organizer 2.5.2 portable archive. It does not modify the source game or copy saves. Profile and save isolation must be verified before launching. This script is an experimental development helper, not a general mod installer.

Do not commit game files, mod binaries, model weights, saves, credentials or runtime databases. This repository distributes only our source code and documentation. Skyrim and other dependencies retain their respective ownership and licenses.

## Observer launch

After completing the portable Mod Organizer setup with profile-specific saves and INIs and an executable named `SKSE` pointing at the isolated loader:

```powershell
python tools/launch_demo.py --root D:\WhiterunLab
```

The helper starts the local service, deploys the bridge, and launches the isolated profile. It waits up to three minutes for a new game session to report a loaded player, cell and actor. A stale heartbeat cannot prove a new launch succeeded. Progress and timings appear in the console; `runtime/last-launch.json` records readiness evidence. By default the profile starts a fresh Whiterun observation scenario automatically, bypassing character creation and Helgen. Add `--save WS-YOUR-SAVE` to restore an existing managed scenario and verify its recorded local proof. This does not import a campaign save.

Observer mode protects the player from combat and uses a raised free camera. The game runs while unfocused so development does not stop NPC routines. Nearby actors are read from the engine, filtered for loaded 3D, and reported every two seconds. Only numeric form IDs survive between frames; native handles are reacquired before commands. The separate economic simulation is not yet driving those actors. A prepared playable character and a return-to-player control are future work.

## Physical trade journal

The authenticated local /world/trade endpoint quotes against observed bread and gold. It writes an immutable prepared checkpoint in timeline.sqlite, asks Skyrim to bind that checkpoint, and only then transfers goods and payment. The next committed checkpoint includes the confirmed trade, factual memories and trust changes. Loading a save selects its checkpoint rather than the latest database state. Retries with the same event ID return the original record.

A changed save/session, unexpected inventory or incomplete operation places the command on hold. Further physical trades stop until it is reconciled. Before/after save restoration now passes for inventories, trade history, memories and trust; recurring audio crashes and in-game mid-trade restore still require qualification. The older `/scenario/trade` endpoint and `society.sqlite` remain standalone test simulation; their balances are not game inventory.

## First playable acceptance criteria

- A real in-game handshake and observed NPC action.
- NPC-to-NPC buying and selling with finite stocks and budgets.
- Production, wages and consumption recorded with explicit causes.
- One shortage with competing interests and a consequential player intervention.
- Duplicate-safe commands and correct reconciliation after loading an older save.
- Evidence from a real play session, including response latency and player feedback.

## License

MIT for the original code in this repository. No affiliation with Bethesda or the creators of Skyrim, Cities: Skylines, SKSE or Skyrim Platform is implied.


### In-game spectator demo

![Actual in-game spectator overlay and resident camera](docs/images/spectator-ui.jpg)

Captured in the running isolated Skyrim installation; this is not a mockup.

The isolated game now displays a transparent society panel over Whiterun: observed resident inventories, actor positions, and a receipt for the verified physical bread trade. A guided camera tour changes every 12 seconds between the market, Carlotta, Ysolda, the trade pair, and the approach. It starts without player input.

**Verified in the live game:** camera repositioning and close-ups, changing actor counts, actual gold/bread inventory, and the completed trade receipt. **Browser controls now verified:** resident selection, follow, zoom and orbit. The local `/observer` control room also exposes map panning, needs, memories and relationships. Native overlay mouse delivery remains separately unqualified. Camera collision avoidance is not implemented, so moving NPCs can occasionally cause occlusion. The standalone production simulation does not yet autonomously drive these NPCs.

The deployer hashes the UI into the bridge revision so HTML changes trigger hot reload. No game restart is needed for this development loop. The browser UI never receives the local service bearer token.

<!-- IMAGE_GALLERY_START -->
<details>

<summary>Browse every finished project image (27)</summary>

### Npc four systems

Generated system illustration — not gameplay

![Npc four systems](docs/images/npc-four-systems.png)

### Personal knowledge loop

Generated system illustration — not gameplay

![Personal knowledge loop](docs/images/personal-knowledge-loop.png)

### Voiced trade loop

Generated system illustration — not gameplay

![Voiced trade loop](docs/images/voiced-trade-loop.png)

### Whole simulation

Generated system illustration — not gameplay

![Whole simulation](docs/images/whole-simulation.png)

### Agent task panel

Captured game or observer interface — historical prototype

![Agent task panel](docs/images/agent-task-panel.jpg)

### Agent travel in game

Captured game or observer interface — historical prototype

![Agent travel in game](docs/images/agent-travel-in-game.jpg)

### Conversation closeup

Captured game or observer interface — historical prototype

![Conversation closeup](docs/images/conversation-closeup.jpg)

### Food consumption restored

Captured game or observer interface — historical prototype

![Food consumption restored](docs/images/food-consumption-restored.jpg)

### Jev resident decisions

Captured game or observer interface — historical prototype

![Jev resident decisions](docs/images/jev-resident-decisions.jpg)

### Live control room

Captured game or observer interface — historical prototype

![Live control room](docs/images/live-control-room.jpg)

### Local ai in game

Captured game or observer interface — historical prototype

![Local ai in game](docs/images/local-ai-in-game.jpg)

### Market day complete

Captured game or observer interface — historical prototype

![Market day complete](docs/images/market-day-complete.jpg)

### Market observer

Captured game or observer interface — historical prototype

![Market observer](docs/images/market-observer.jpg)

### Market travel live

Captured game or observer interface — historical prototype

![Market travel live](docs/images/market-travel-live.png)

### Negotiation reconsideration

Captured game or observer interface — historical prototype

![Negotiation reconsideration](docs/images/negotiation-reconsideration.jpg)

### Negotiation restored

Captured game or observer interface — historical prototype

![Negotiation restored](docs/images/negotiation-restored.jpg)

### Paid work complete

Captured game or observer interface — historical prototype

![Paid work complete](docs/images/paid-work-complete.jpg)

### Paid work in progress

Captured game or observer interface — historical prototype

![Paid work in progress](docs/images/paid-work-in-progress.jpg)

### Parallel native

Captured game or observer interface — historical prototype

![Parallel native](docs/images/parallel-native.png)

### Parallel observer

Captured game or observer interface — historical prototype

![Parallel observer](docs/images/parallel-observer.jpg)

### Resident follow live

Captured game or observer interface — historical prototype

![Resident follow live](docs/images/resident-follow-live.png)

### Resident social live

Captured game or observer interface — historical prototype

![Resident social live](docs/images/resident-social-live.png)

### Rest seated live

Captured game or observer interface — historical prototype

![Rest seated live](docs/images/rest-seated-live.png)

### Rts live overview

Captured game or observer interface — historical prototype

![Rts live overview](docs/images/rts-live-overview.jpg)

### Seven resident observer

Captured game or observer interface — historical prototype

![Seven resident observer](docs/images/seven-resident-observer.jpg)

### Social control room

Captured game or observer interface — historical prototype

![Social control room](docs/images/social-control-room.jpg)

### Spectator ui

Captured game or observer interface — historical prototype

![Spectator ui](docs/images/spectator-ui.jpg)

</details>
<!-- IMAGE_GALLERY_END -->
