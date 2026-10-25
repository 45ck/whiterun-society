# Whiterun Society

An experimental, open-source society simulation for Skyrim Special Edition: an RTS city economy and social simulation you can watch and direct.

Residents should work, trade with one another, consume goods, remember events and form different opinions. The current product is RTS-only: select, inspect, follow and watch residents in movie view. Player movement, fighting and activation are disabled in the lab; participating through voice is a later extension. Skyrim supplies the physical world; our simulation owns economic rules, decisions and evidence.

**Fresh livelihoods, source implementation:** an explicit starting-background scenario gives recipe knowledge to a seeded, identity-bound cohort. It creates no businesses, money, stock or work history. Residents can then choose their own charter, procure inputs and work. Current actor/base identity is checked before decisions and speech; changed or unbound census identities are held without inheriting another resident's history. The inspector separates authored knowledge from verified production learning, and startup tools preview before applying a checkpoint-bound change. [Initialization loop and evidence limits](docs/livelihood-backgrounds.md).

![Observe identities, assign explicit backgrounds, let residents choose, then verify production before learning](docs/images/livelihood-startup.png)

*Generated system illustration, not gameplay. [Built-in image generation prompt](docs/images/livelihood-startup.prompt.md). New source is not installed in Skyrim.*

**Paid employment is currently held:** an audit found that the legacy execution path could accept balances without sufficient attendance and payment witnesses. New paid admissions and native replay are disabled; historical records remain readable. Independent owner production uses its separate witnessed protocol. [Required replacement protocol and acceptance tests](docs/paid-employment-protocol.md).

**Configured input markets, source implementation:** a resident derives demand from their own stock and learned recipes, discovers explicit public seller listings, and chooses a supplier and quantity. Negotiation binds the commodity, quantity, unit price and total to the exact agreement. The exchange saves a native permit before moving goods and payment, witnesses both sides of each transfer, and holds uncertain accounts instead of replaying them. The observer shows actual terms and separates verified sales from held exchanges. Default goods remain bread and grain; additional goods are test fixtures, not deployed industries. [Decision loop, data contracts and qualification limits](docs/generic-procurement.md).

![Resident need, public opportunities, agent choice, heard agreement, verified exchange and consequences](docs/images/generic-market-cycle.png)

*Generated architecture illustration, not gameplay. [Full generation prompt](docs/images/generic-market-cycle.prompt.md). This source has not been installed in Skyrim.*

[Full generic-market validation](https://github.com/45ck/whiterun-society/actions/runs/40201564112) passed on Windows and Ubuntu at revision `20269b4`: **1,039 Python tests per platform (1,038 passed and one initial generated-file skip), 420 JavaScript tests and six generated-plugin readback tests**. The skipped check passed after generation; Windows compiled both Papyrus scripts. An 18-resident fixture keeps all 68 purchase alternatives reachable with a maximum 8,186-byte decision context. A separate integrated fixture exchanged 15 gold for five ore using the actual JavaScript controller with simulated native APIs. [Machine-readable evidence and limits](docs/evidence/generic-market-validation.json).

**Finite resources from scenario data, source implementation:** starting allocations now come from one reviewed manifest, with uniform defaults instead of a privileged NPC branch. The saved program separates available, reserved and settled imports. A native permit is saved before delivery; each resource addition requires its own issued/observed witness. A lost session or witness holds the reservation without replay. This is an external import mechanism, not autonomous production or earned income. [Contract, historical evidence and native qualification still required](docs/founding-resources.md).

![Finite scenario resources, saved permits, witnessed delivery and uncertain-delivery holds](docs/images/finite-resource-delivery-flow.png)

*Generated system illustration. Service accounting is durable; native effect witnesses are live only, so there is no exactly-once guarantee across crashes. [Full generation prompts](docs/images/finite-resource-delivery-flow.full.prompt.md).*

[Full resource-scenario validation](https://github.com/45ck/whiterun-society/actions/runs/40197789995) passed on Windows and Ubuntu: **908 Python tests per platform (907 passed, one initial generated-file skip), 358 JavaScript tests and six generated-plugin readback tests**. The skipped test passed after generation. Windows also compiled both Papyrus scripts. [Exact revision and machine-readable evidence](docs/evidence/resource-scenario-validation.json).

**Independent activities, controlled native overlap:** two authored rests and four authored local-voice turns achieved **28.359 cumulative seconds** of verified two-seat/voice overlap, passing the 10-second cumulative target with **zero cloud calls**. The longest continuous interval was **7.375 seconds**. This proves the bounded execution protocol, not autonomous choices or human realism; C1's zero-overlap refusal and obstructed camera remain documented. [Architecture, actual screenshots and limits](docs/concurrent-activities.md) · [C2 evidence](docs/concurrent-rest-controlled-trial.json) · [C1 evidence](docs/concurrent-rest-first-trial.json).

![Independent owner work, rest and conversation architecture](docs/images/independent-owner-work.png)

*Generated design illustration; the workbench animation is conceptual, and independent owner-work execution is not yet native-qualified. [Work-state contract and acceptance plan](docs/independent-owner-work.md) · [Full image prompt](docs/images/independent-owner-work.prompt.md).*

**Data-defined economy, source implementation:** a shared versioned catalog now drives commodity identity, owner-recipe quantities, enterprise recipe policies and verified-recipe learning, with hashes pinned to inventory intents. The default remains three commodities and the existing bread recipe; trade/consumption paths are still limited, and native generic production is unqualified. Verified iron-smelting metadata remains disabled pending workstation and knowledge gates. [Data → decision → effect diagram and migration limits](docs/economy-catalog.md) · [Remaining economy gaps](docs/data-driven-economy-gap.md).

**Uniform resident routing, source implementation:** new trips use the same observed mailbox capability for every resident, without a privileged three-NPC route table. Event requests require an explicit resident; population reports distinguish available, unavailable and unmeasured capability. Old fixed journeys require release instead of silent replay, and new conversation meetings bind their participants and session before accepting arrival. This migration is tested separately from native installation; explicit demonstration casts and authored resource rules still remain. [Contracts, recovery and remaining exceptions](docs/data-driven-economy-gap.md#npc-identity-migration-and-remaining-exceptions).

![From world state to verified economy: catalog, agent choices and physical receipts](docs/images/economy-catalog-flow.png)

*Generated architecture illustration, not gameplay. Depicted crafting is conceptual; native generic production and smelter access remain unqualified. [Image prompt](docs/images/economy-catalog-flow.prompt.md).*

**Population and conversation admission, source implementation:** fresh bootstrap starts with no invented residents. An explicit census initializes observed adults under one seed policy; old saves retain their profiles and history. Ordinary social opportunities preserve partner choice, quiet deferral and refusal. Directed encounters require an explicit scenario definition with saved participants and a content hash. Uncertain native cleanup reserves affected residents until resolved. [Scenario contract and recovery](docs/conversation-scenarios.md) · [Population model](docs/population.md).

![Observed residents, saved personal state and two explicit conversation flows](docs/images/resident-initialization-flow.png)

*Generated system illustration; in-game qualification remains pending. [Full image prompt](docs/images/resident-initialization-flow.prompt.md).*

[Population and conversation validation](https://github.com/45ck/whiterun-society/actions/runs/40195842462) passed on Windows and Ubuntu: 832 Python tests per platform with one initial skip, 300 JavaScript tests and six generated-plugin readback checks. The skipped generated-file test passed after plugin generation; Windows also compiled both Papyrus scripts. [Exact revision and evidence](docs/evidence/population-scenario-validation.json).

**Native UI candidate:** [hosted run 40191256470](https://github.com/45ck/whiterun-society/actions/runs/40191256470) built the separate unchanged baseline and reviewed saving/focus/mouse-routing candidate. All 159 C++ policy checks passed, all 158 artifact hashes verified, and both DLL/PDB pairs match. Status is **`compiled-unqualified`**: the candidate is not installed and RTS input has not been verified in Skyrim. [Build evidence and limits](docs/native-ui-build.md).

**RTS input follow-up:** camera gestures now preserve the observed pose and reject stale acknowledgements; F8 release and missed mouse-up handling have regression coverage. Native automated input remains intermittent and roster clicking is unqualified. [Runtime evidence and remaining work](docs/rts-input.md).

**RTS controls and charts:** [implementation and runtime qualification](docs/rts-experience.md). Play starts resident decisions; Pause settles the current interaction. Movie view follows current activity, with no automatic tours.

**Resident ownership and voices:** [native continuity qualification](docs/resident-continuity.md): 29 enrolled residents, separate standby/task charts, two completed four-line encounters, and saved policy recovery. Standby and audible output are verified separately from natural dialogue and economic success.

**Trade choices and audio:** sellers can reconsider one reserved loaf for an actual offer without unlocking their remaining household stock. A live four-line negotiation ended in refusal with unchanged inventories; the charts distinguish refusal, technical failure and committed sale. NPC voice output is now set to Realtek, with software output signal verified. [Implementation, audio and limits](docs/reserve-reconsideration.md).

**Aerial observer and owned production:** actual Whiterun map, seven identity-checked NPC portraits and septim symbols are now in the UI. A native recipe fixture converted owned grain into bread with conserved money; the real model review chose eating first. [Screenshots, evidence and remaining input limits](docs/aerial-observer.md).

**Resident-selected prices:** buyers now choose bids, sellers can counteroffer, and spoken terms are checked against the physical exchange. A real Jev negotiation ended in two refusals; a separate controlled native test exchanged one loaf for 7 septims and was rolled back. [Diagram, screenshot, audio and evidence](docs/bargaining.md).

**Connected input market:** dynamic bakeries can buy grain, negotiate, produce bread and sell it for consumption. A controlled native chain completed both sales, production and a meal, with seven spoken lines and conserved money. The real model trial and its context-size failure are documented separately. [Infographic, screenshot, audio, receipts and limits](docs/grain-market.md).

**Movie camera:** conversations now use a stable pair shot instead of the wide RTS framing. A controlled native four-line negotiation kept both residents visible through a one-loaf, seven-septim sale. [Screenshots, telemetry and remaining collision limits](docs/movie-camera.md).

**Historical voiced employment:** a live Jev search ended in a spoken refusal; a separate controlled legacy shift recorded four spoken turns, two loaves and a four-septim wage. The current source holds that execution path pending stronger attendance and payment witnesses; these historical observations do not qualify safe replay. [Infographic, screenshots, audio and historical receipts](docs/employment-encounters.md).

**Resident-owned enterprise decisions:** residents can now register and revise services from their own resources and recipe knowledge. Two unforced reviews chose food or employment; a controlled registration survived native reload with unchanged assets. [Flow diagram, screenshots, voices and evidence](docs/entrepreneurship.md).

**Contextual economic voices:** Mercury proposes phrasing around code-preserved terms; Jev chooses the wording and local Kokoro speaks it. Three native trials are published, including fallback failures. The final two-line work inquiry completed with generated wording, but formal language and a 20.5-second reply gap remain quality defects. [Infographic, actual clips, state flow and measured results](docs/economic-wording.md).

**Movie view is the default:** recurring 12-second cards show actual economy, activity and queue updates. Economic candidate voices prepare while Jev chooses; only selected speech plays. A native work inquiry/refusal completed with a 10.997-second reply gap, still too slow for natural dialogue. [Screenshots, measurements and the remaining all-resident autonomy gap](docs/movie-watch.md).

**Active goal:** a Sims-like society with a functioning economy inside Skyrim, where you can watch individual lives and understand why their decisions change the town. Development includes visual architecture updates, actual game screenshots and, next, recorded demonstrations of conversations and economic consequences.

**Visual documentation:** [all 75 finished images](docs/gallery.md) · [gallery and voice examples](https://45ck.github.io/whiterun-society/) · [57 configurable development OKRs](docs/society-okrs.md). Images live in `docs/images`; illustrations and captured prototype interfaces are labelled separately.

**Development prototype, not a complete society mod.** The isolated game starts directly in Whiterun with an observer camera. Actual inventory transfers, paid production, food consumption and generated voiced encounters have been demonstrated. Full daily routines, lip sync and sustained audio stability remain unfinished. The autonomous farm–bakery–household model still runs separately.

## Independent lives and measurable progress

![From intention to consequence](docs/images/intention-to-consequence.png)

**Purposeful activity:** personal food, rest, work and social goals now lead to source-linked decisions after verified arrival. Fair dispatch exposes overdue waits; per-run budgets and policy hashes make each session reproducible. A controlled native test stopped an owner travelling, verified stationary production of two bread from one grain, then resumed the same journey. All 17 baseline fields restored afterward. A subsequent autonomous run completed three spoken work refusals, three rests and one meal, but no new sales or production. Its personal-goal settlement failure remains recorded; sustained town-wide productivity is unfinished. [Implementation, quantitative evidence and remaining work](docs/purposeful-agency.md) · [Native fixture receipt](docs/owner-attendance-evidence.json).

*Generated architecture illustration, not gameplay. [Full image-generation prompt](docs/images/intention-to-consequence.prompt.md).*

![Independent NPC loops and measurement](docs/images/independent-lives-metrics.png)

Movie view now follows independent personal goals as well as conversations. In one repaired native trial, 44 personal decisions produced 41 validated journeys; up to 15 residents moved while a four-line NPC conversation played. The same trial retained an invalid-greeting failure and three unavailable-resident choices. [Implementation, movement chart, voice clips and save proof](docs/personal-goals.md).

The scorecard defines **57 configurable OKRs**, with **50 further acceptance protocols** covering economics, relationships, behavioural sensitivity, movement and urban systems. The trial baseline passed only one target—telemetry coverage. Unknown realism is not assigned a success score. [Definitions](docs/society-okrs.md) · [Roadmap](docs/simulation-roadmap.md).

## The whole simulation

![Generated overview of the Whiterun society simulation and its planned expansion](docs/images/whole-simulation.png)

*Generated system illustration, not a game screenshot. Each panel labels the current foundation; the bottom band describes future work.*

## How one NPC works

![Generated infographic showing the deterministic simulation, Jev, optional language and voice, and Skyrim execution](docs/images/npc-four-systems.png)

**Our code maintains state and valid options → Jev chooses → Skyrim performs the physical task → our code verifies the result and remembers it.** When conversation is appropriate, a language model proposes lines, Jev selects, and local Kokoro voices the chosen words. Walking, work attendance and quiet periods need no continuous model calls. Skyrim handles navigation and movement; choosing a destination does not mean asking a model to calculate every footstep.

[Living development plan: dynamic residents, personal knowledge and RTS mode](docs/development-plan.md) · [Full system guide, NPC loop and data model](docs/system-guide.md) · [Latest verified progress](docs/town-progress.md) · [Video demonstration plan](docs/demo-videos.md)

The language role can use a small, inexpensive model; it does not require frontier reasoning for every line. Cloud inference through OpenRouter is the selected direction. Mercury 2.5 is now the experimental lab default after a complete two-turn voiced encounter: 58.811 seconds including approach and playback, with US$0.000718912 reported across two language requests and six Jev decisions. Grounding failures from earlier probes remain documented; one successful scene is not broad qualification. [Model pricing, measured timings and routing direction](docs/model-routing.md)

The observer now offers **Agent priority over native scenes**: persist a handoff, stop the exact observed scene once, verify release, then let the resident choose from current opportunities. Individual scene-release controls and receipts are available in the resident inspector. Scene scripts may affect quests; combat and sleep transitions still require appropriate native handling. [Scene handover and live qualification](docs/native-scene-handoff.md) · [Scheduling behavior](docs/scene-aware-scheduling.md).

Residents can now choose food, rest or work reviews after heard conversations, with source links carried into the next action decision. Blanket guard/duty exclusions and the nearest-six candidate truncation are removed. In Skyrim, a guard and Idolaf spoke, chose food reviews, then respectively ate a loaf and visited a market without finding a seller. Dialogue grounding, latency and native quest-scene takeover remain unfinished. [Behavior, restrictions and evidence](docs/conversation-actions.md).

## Examples from the running prototype

### Choosing a reply or ending

![Language alternatives, Jev choice, deterministic playback and heard memory](docs/images/reply-is-a-choice.png)

*Generated architecture illustration, not gameplay. Language proposes alternatives; Jev chooses whether to reply, end politely or leave quietly; deterministic game logic handles validation, voice playback and confirmed speech memory.* [Image prompt and provenance](docs/images/reply-is-a-choice.prompt.md). [Implementation, live trials and known defects](docs/combined-dialogue.md).

### Independent lives around a conversation

![Independent lives, shared world: resident knowledge and needs feed Jev and language models, deterministic rules allocate travel and conversation, and Skyrim executes the result](docs/images/independent-lives-observed.png)

*Generated architecture infographic. One live overlap is observed; full independent daily lives remain unfinished. The earlier illustration is retained in the gallery.*

Background travel now has six native slots, leaving two for one disjoint conversation. Actor reservations prevent a traveller from also being selected as a speaker; arrival receipts preserve another encounter's pending speech. The observer reports travel/attendance and travel/speech overlap separately. Current businesses provide seller IDs dynamically.

**Observed in Skyrim:** Adrianne and Idolaf completed three voiced turns while Amren travelled. Native telemetry recorded 591 travel/speech overlap frames and verified independent release. Heimskr's separate route never acquired its package and timed out; that failure remains counted. All 29 compared inventories stayed unchanged. [Listen to the generated utterances](https://45ck.github.io/whiterun-society/#voice-example) · [Architecture, receipts and limitations](docs/concurrent-society.md).

### Conversations in an established town

Speech now receives game time, the latest heard line, known relationships and actual commitments. Short acknowledgements and goodbyes no longer need padded sentences. The current 20 civilian residents have an explicit initial shared-town acquaintance, separately labelled from earned relationship history; future arrivals can still be strangers. Concurrent town-wide conversation and full routine ownership remain unfinished. [Dialogue context, initial state and evaluation](docs/situated-dialogue.md)

### Hear an actual negotiation

![Generated illustration of the implemented voiced trade protocol, not gameplay](docs/images/voiced-trade-loop.png)

Jev chooses the economic actions; deterministic wording keeps spoken amounts aligned with the terms; local Kokoro speaks them; Skyrim performs movement and inventory changes. A live Amren–Carlotta trial delivered **four turns**: offer 3 gold, refusal, offer 5 gold, refusal. Both actors were released and **no gold or bread transferred**. This proves a voiced refusal/counteroffer path, not a successful sale. [Protocol and limits](docs/voiced-trade.md)

The observer now includes an interruption control, derived friendship bands, small-talk word cues, current native Skyrim race labels and **57 configurable OKRs** spanning social, economic, physical, spatial and behavioural experiments. Most psychology, semantic-dialogue and evolutionary-mechanism measures remain **unmeasured**. Friendship bands are authored game rules, not psychological diagnoses. [Definitions and thresholds](docs/society-okrs.md)

### Watch a running society and measure its limits

The control room now has **Start society**, **Stop after encounter**, and **Follow activity**. A bounded session alternates eligible economic and social events, offers nearby conversations when urgent-needs queues would otherwise crowd them out, and lets residents accept or decline. The in-game overlay identifies whether the director is running or idle. Both consenting speakers now receive temporary attendance packages; release must be verified for both.

The **Society quality lab** reports encounter failures, duration, reply gaps, body-facing error, physical economic outcomes and relationship counts. Unknown gaze/raycast accuracy, lip sync and human realism remain unscored. The initial live baseline was **4/6 accepted chats completed**, **zero sales in that save**, **two production events** and **39 meals**; the ledger includes staged experiments. Implementation now supports two sale goods and one production recipe, with separate grain and bread prices. These are breadth counts, not a high realism score. [Metrics definitions, baseline and acceptance targets](docs/quality-metrics.md)

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

The RTS observer uses a raised free camera and disables player movement, fighting and activation. The game runs while unfocused. Nearby actors are read from the engine and reported every two seconds; native handles are reacquired before commands. Native society rules now drive bounded resident choices, exchanges and encounters. The standalone farm–bakery simulation remains separate, and meaningful persistent routines remain unfinished. Direct player participation is deferred.

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

<summary>Browse every finished project image (75)</summary>

### Concurrent resident lives

Generated system illustration — not gameplay

![Concurrent resident lives](docs/images/concurrent-resident-lives.png)

### Economic speech layers

Generated system illustration — not gameplay

![Economic speech layers](docs/images/economic-speech-layers.png)

### Economy catalog flow

Generated system illustration — not gameplay

![Economy catalog flow](docs/images/economy-catalog-flow.png)

### Employment encounter loop

Generated system illustration — not gameplay

![Employment encounter loop](docs/images/employment-encounter-loop.png)

### Finite resource delivery flow

Generated system illustration — not gameplay

![Finite resource delivery flow](docs/images/finite-resource-delivery-flow.png)

### Generic market cycle

Generated system illustration — not gameplay

![Generic market cycle](docs/images/generic-market-cycle.png)

### Grain market loop

Generated system illustration — not gameplay

![Grain market loop](docs/images/grain-market-loop.png)

### Independent lives metrics

Generated system illustration — not gameplay

![Independent lives metrics](docs/images/independent-lives-metrics.png)

### Independent lives observed

Generated system illustration — not gameplay

![Independent lives observed](docs/images/independent-lives-observed.png)

### Independent lives

Generated system illustration — not gameplay

![Independent lives](docs/images/independent-lives.png)

### Independent owner work

Generated system illustration — not gameplay

![Independent owner work](docs/images/independent-owner-work.png)

### Intention to consequence

Generated system illustration — not gameplay

![Intention to consequence](docs/images/intention-to-consequence.png)

### Livelihood startup

Generated system illustration — not gameplay

![Livelihood startup](docs/images/livelihood-startup.png)

### Npc four systems

Generated system illustration — not gameplay

![Npc four systems](docs/images/npc-four-systems.png)

### Personal knowledge loop

Generated system illustration — not gameplay

![Personal knowledge loop](docs/images/personal-knowledge-loop.png)

### Reply is a choice

Generated system illustration — not gameplay

![Reply is a choice](docs/images/reply-is-a-choice.png)

### Resident bargaining loop

Generated system illustration — not gameplay

![Resident bargaining loop](docs/images/resident-bargaining-loop.png)

### Resident enterprise loop

Generated system illustration — not gameplay

![Resident enterprise loop](docs/images/resident-enterprise-loop.png)

### Resident initialization flow

Generated system illustration — not gameplay

![Resident initialization flow](docs/images/resident-initialization-flow.png)

### Voiced trade loop

Generated system illustration — not gameplay

![Voiced trade loop](docs/images/voiced-trade-loop.png)

### Whole simulation

Generated system illustration — not gameplay

![Whole simulation](docs/images/whole-simulation.png)

### Aerial portrait inspector

Captured game or observer interface — historical prototype

![Aerial portrait inspector](docs/images/aerial-portrait-inspector.jpg)

### Agent task panel

Captured game or observer interface — historical prototype

![Agent task panel](docs/images/agent-task-panel.jpg)

### Agent travel in game

Captured game or observer interface — historical prototype

![Agent travel in game](docs/images/agent-travel-in-game.jpg)

### Bargaining native fixture

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Bargaining native fixture](docs/images/bargaining-native-fixture.jpg)

### Concurrent rest camera occlusion

Captured game or observer interface — historical prototype

![Concurrent rest camera occlusion](docs/images/concurrent-rest-camera-occlusion.jpg)

### Concurrent rest voice native

Captured game or observer interface — historical prototype

![Concurrent rest voice native](docs/images/concurrent-rest-voice-native.jpg)

### Context window completed hud

Captured game or observer interface — historical prototype

![Context window completed hud](docs/images/context-window-completed-hud.jpg)

### Context window live conversation

Captured game or observer interface — historical prototype

![Context window live conversation](docs/images/context-window-live-conversation.jpg)

### Conversation closeup

Captured game or observer interface — historical prototype

![Conversation closeup](docs/images/conversation-closeup.jpg)

### Economic wording initial native

Captured game or observer interface — historical prototype

![Economic wording initial native](docs/images/economic-wording-initial-native.jpg)

### Employment agreement fixture

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Employment agreement fixture](docs/images/employment-agreement-fixture.jpg)

### Employment refusal native

Captured game or observer interface — historical prototype

![Employment refusal native](docs/images/employment-refusal-native.jpg)

### Enterprise livelihood choice native

Captured game or observer interface — historical prototype

![Enterprise livelihood choice native](docs/images/enterprise-livelihood-choice-native.jpg)

### Enterprise registration fixture

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Enterprise registration fixture](docs/images/enterprise-registration-fixture.jpg)

### Food consumption restored

Captured game or observer interface — historical prototype

![Food consumption restored](docs/images/food-consumption-restored.jpg)

### Grain chain camera obstruction

Captured game or observer interface — historical prototype

![Grain chain camera obstruction](docs/images/grain-chain-camera-obstruction.jpg)

### Grain trade native fixture

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Grain trade native fixture](docs/images/grain-trade-native-fixture.jpg)

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

### Movie broadcast native

Captured game or observer interface — historical prototype

![Movie broadcast native](docs/images/movie-broadcast-native.jpg)

### Movie pair receipt fixture

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Movie pair receipt fixture](docs/images/movie-pair-receipt-fixture.jpg)

### Movie pair speaking fixture

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Movie pair speaking fixture](docs/images/movie-pair-speaking-fixture.jpg)

### Negotiation reconsideration

Captured game or observer interface — historical prototype

![Negotiation reconsideration](docs/images/negotiation-reconsideration.jpg)

### Negotiation restored

Captured game or observer interface — historical prototype

![Negotiation restored](docs/images/negotiation-restored.jpg)

### Owner production aerial ui

Captured game or observer interface — historical prototype

![Owner production aerial ui](docs/images/owner-production-aerial-ui.jpg)

### Owner work fixture timeline

Controlled native protocol fixture — authored choices, not autonomous behaviour

![Owner work fixture timeline](docs/images/owner-work-fixture-timeline.png)

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

### Personal goals budget hold

Captured game or observer interface — historical prototype

![Personal goals budget hold](docs/images/personal-goals-budget-hold.jpg)

### Personal goals movement chart

Measured native trial chart — sampled evidence, not a screenshot or human-realism score

![Personal goals movement chart](docs/images/personal-goals-movement-chart.png)

### Portrait 108138

Captured game or observer interface — historical prototype

![Portrait 108138](docs/images/portrait-108138.jpg)

### Portrait 108140

Captured game or observer interface — historical prototype

![Portrait 108140](docs/images/portrait-108140.jpg)

### Portrait 108149

Captured game or observer interface — historical prototype

![Portrait 108149](docs/images/portrait-108149.jpg)

### Portrait 108156

Captured game or observer interface — historical prototype

![Portrait 108156](docs/images/portrait-108156.jpg)

### Portrait 108160

Captured game or observer interface — historical prototype

![Portrait 108160](docs/images/portrait-108160.jpg)

### Portrait 108186

Captured game or observer interface — historical prototype

![Portrait 108186](docs/images/portrait-108186.jpg)

### Portrait 182543

Captured game or observer interface — historical prototype

![Portrait 182543](docs/images/portrait-182543.jpg)

### Prepared speech native

Captured game or observer interface — historical prototype

![Prepared speech native](docs/images/prepared-speech-native.jpg)

### Purposeful live rest review

Captured game or observer interface — historical prototype

![Purposeful live rest review](docs/images/purposeful-live-rest-review.jpg)

### Purposeful run held goal lane

Captured game or observer interface — historical prototype

![Purposeful run held goal lane](docs/images/purposeful-run-held-goal-lane.jpg)

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

### Whiterun aerial reference

Captured game or observer interface — historical prototype

![Whiterun aerial reference](docs/images/whiterun-aerial-reference.jpg)

</details>
<!-- IMAGE_GALLERY_END -->
