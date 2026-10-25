# Independent activity lanes

The first concurrency slice lets two residents take independently observed seated breaks while a disjoint resident event uses the existing conversation or economic pipeline. This addresses an observed bottleneck: one 30-game-minute rest previously occupied the foreground worker for roughly 150 wall seconds, leaving other purposeful reviews queued. Rest is valid behavior; freezing unrelated residents behind it is not.

**First native result:** two explicitly authored rest choices completed in separate Skyrim slots, and a disjoint autonomous encounter completed a brief spoken refusal. The required simultaneous two-seat voice overlap was **0 seconds against a 10-second target**. Trial C1 is therefore **not qualified** for that acceptance case. The contracts also have automated test coverage, but neither the fixture nor one encounter proves autonomous rest selection, natural dialogue, or a continuously productive town. This slice does not make all work, commerce, or conversations concurrent: those still use the existing foreground pipeline.

![Architecture illustration of two independent rest lanes and a foreground conversation](images/concurrent-resident-lives.png)

*Generated architecture illustration, not gameplay or proof that the illustrated overlap occurred. [Complete generation and correction prompts](images/concurrent-resident-lives.prompt.md).*

## Native trial C1: completed rests, missed overlap

Trial `rest-voice-ff2d1be667d44e08` admitted two authored rest decisions with **zero model calls for those choices**. Each job retained its own actor, seat, slot, source plan and native receipt. Both finished as `rested_at_bench`, verified release, and received durable acknowledgement. The first used actor `108138`, seat `586076`, slot `0`; the second used actor `108170`, seat `945258`, slot `1`. These IDs describe this trial's observed assignments, not special-case identities required by the scheduler.

The separate conversation made **six model calls**, chose a brief refusal, and verified one **2.836-second** playback with proximity maintained. Its final software telemetry reported `muted=false` and `volume=1`. That is playback evidence, not a microphone recording or confirmation that the user heard the output. The encounter was allowed to decline; it was not lengthened to satisfy a concurrency quota.

The sampler retained **120 observations** over a last-sample elapsed time of **133.937 seconds**. Both exact seats were verified in **71 samples**, from sampled times **37.922 to 113.328 seconds**. Speech was playing in three samples earlier in the run. These are correlated samples, not independent trials; the first and last seated timestamps alone do not prove an uninterrupted interval. The strict overlap calculation counts only adjacent samples at most 1.75 seconds apart with both seats verified, the same speech playing, and subsequent verified playback completion. Cumulative verified overlap and longest continuous verified overlap were both **0 seconds**; the **10-second acceptance target was not met**. No sale or production occurred in this qualification case. [Curated native evidence and selected samples](concurrent-rest-first-trial.json).

Both completed job records were saved at checkpoint **3125** in `WS-ConcurrentRest-20261025-BY`; a fresh-session restore matched **18 of 18 compared fields**, including independent activity history. Separately, `WS-GoalsContext-20261025-BX` restored **17 of 17 compared fields** with `WhiterunActivities.esp` allowed as an appended plugin. The [curated evidence](concurrent-rest-first-trial.json) includes match maps, native save hashes and plugin manifests, without full state snapshots. Those save checks are separate from the C1 overlap measurement; they do not qualify a save/load in the middle of two seated jobs and voice playback.

![Actual Skyrim screenshot: activity telemetry visible but movie view obstructed by scene geometry](images/concurrent-rest-camera-occlusion.jpg)

*Actual prototype screenshot during the trial. The activity card shows two observed resting jobs and one foreground assignment; the selected dialogue is visible in the UI. Scene geometry obscures the residents. This is evidence of a camera defect, not a successful cinematic encounter, simultaneous playback proof, or lip sync. Collision-aware framing and clear participant visibility remain unfinished.*

## Ownership and progress

An accepted rest decision creates a saved `activity_jobs` record containing a source plan ID, actor, optional base identity, seat, native slot, session, epoch, policy snapshot, phase, and receipt state. The source plan becomes `delegated`; the daily opportunity remains unfinished. The latest foreground plan remains the latest entry for existing consumers, while settlement finds its original source by ID.

Each job reserves its actor, seat, and one of two native slots. This is an initial execution capacity, not a claim about the maximum population. Other activities cannot borrow a reserved actor or seat. A separate resident may begin a foreground event. Conversations select available participants; an existing actor reservation must remain respected throughout that event.

`activity_start_rest` acknowledges admission quickly. The bridge then ticks both native rest controllers independently of the foreground command. The native slots use the additive `WhiterunActivities.esp`; ordinary Skyrim pathfinding, furniture interaction, and package evaluation execute movement. The model chooses among permitted intentions; deterministic code enforces identities, resources, evidence, and state transitions.

## Completion and save correctness

The bridge retains a terminal receipt. Acceptance and elapsed wall time never prove rest. Recovery requires matching assignment identity, current session, a consistent game clock, observed seated samples, exact furniture, and verified release. The service persists the receipt and changes simulated fatigue once, then acknowledges the durable record. The actor and seat remain reserved until acknowledgement. A held receipt may later prove release without changing the failed attendance into successful rest.

Receipt settlement can write a checkpoint. It therefore waits while a foreground inventory operation, travel command, conversation attendance command, or speech command is outstanding. The pending-command order is checkpoint binding, foreground inventory effect, foreground speech/travel/attendance, then activity admission or acknowledgement. Native activity time may continue while a receipt waits to be persisted.

A new game session invalidates previous elapsed attendance. Cold controller recovery holds saved work and releases native ownership rather than resuming an unknown clock. Loading an older checkpoint may leave a future native receipt with no saved intention: it is quarantined solely for release reconciliation. It must not import future fatigue recovery, memories, plans, or economic changes into the older lineage.

## Review and qualification

`tests/test_activity_integration.py` exercises real `TimelineEconomy` SQLite snapshots and checkpoint transitions with authored native observations. It covers two delegated rests plus disjoint consumption, reservation rejection, idempotent original event admission, source-plan settlement preserving a newer plan, database reopen without duplicate recovery, and checkpoint deferral during inventory, travel, attendance, and speech. A rollback case exercises orphan receipt reconciliation without importing recovery. Bridge and job-module tests cover the lower-level lane and receipt contracts.

The native acceptance scenario is two distinct residents resting at different registered seats while separate participants complete an audible interaction or resource transaction. Evidence should capture overlapping native attendance intervals, the foreground event's own start/end and receipt, exact actor/seat/slot identities, release, and no duplicate fatigue or ledger effects. Then repeat with interruption, lost attendance, an older save, and a cold controller restart. Preserve failures and report incomplete native cases as unmeasured.

Next expansion should follow measured waiting time and resource conflicts: independent self-care, independent owner work, then compatible multi-participant economic events. Actor locks alone are insufficient for shared inventory, business capacity, or contracts; those require resource reservations and atomic settlement before broader concurrency is enabled. No motion or conversation quota should force needless activity merely to make the town look busy.

See the [simulation roadmap](simulation-roadmap.md), [purposeful agency](purposeful-agency.md), and [quantitative goals](society-okrs.md).
