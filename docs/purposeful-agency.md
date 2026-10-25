# Personal purpose, fair attention and stationary owner work

![From intention to consequence](images/intention-to-consequence.png)

Generated architecture illustration, not gameplay. [Generation prompt](images/intention-to-consequence.prompt.md).

The personal-goal layer now offers state-dependent food, rest, work and social reviews as well as quiet intervals and visits. A resident can choose a review immediately or visit a suitable observed place and reconsider there. The selected purpose is carried into the ordinary economic or social decision process, where current resources, availability and consent are checked again.

This connects destination choice to a subsequent decision. It does not make arriving at a bench count as rest, a food review count as a meal, or a work intention count as production. The current changes are implemented and locally tested; the native owner-work trial below is a controlled protocol fixture, not proof of autonomous purposeful behaviour across the town.

## What the resident can choose

`goal_opportunities.py` derives opportunities from the current resident's resources, public charters and eligible native observations. The enabled focus list, priority floor and retained source bound are versioned in [`config/goal-opportunities.json`](../config/goal-opportunities.json). The current focus set is food, rest, work and social life.

| Goal family | Current feasibility evidence | What happens next |
| --- | --- | --- |
| Food review | Carried bread, or funds and a public seller/search opportunity | A normal needs review can choose eating, seeking food or another feasible action; no purchase is guaranteed |
| Rest review | An observed available bench opportunity | A later validated rest action must establish furniture attendance before recovery |
| Work review | An owned production charter with own input stock, or a reachable public employer charter | The resident rechecks own production or asks about work; a public charter does not reveal employer stock, a vacancy or consent |
| Social review | Current eligible nearby people | Partner selection and listener consent still occur; quiet passage or refusal remains legitimate |
| Visit to review | A suitable current destination and feasible focus | The journey must receive a matching native arrival receipt before the focus is queued for reconsideration |
| Quiet or ordinary visit | Current personal-goal policy and observed destination options | No invented need relief, social benefit or economic output |

Only enabled, currently feasible choices are offered. The context includes personal state and public opportunities rather than another resident's private resources or memories. A changed population, unavailable place or changed actor identity can invalidate a result before execution. Fixed NPC names do not select normal outcomes.

## A traceable follow-through loop

1. Save the claim, options and policy snapshot before inference.
2. Validate the returned choice against current identity, current opportunities and the claimed action family.
3. Save the goal and its focus. Immediate reviews enter `review_pending`; destination goals travel first.
4. Create one source-linked review, or annotate a compatible pending review. An already started action is not overwritten. A still-unaccepted invitation may be superseded by the resident's explicit new intent.
5. Pass the goal source and focus to the later decision. The resident can reconsider; the validator does not force the originally imagined outcome.
6. Record the linked queue event's completion or hold back into `follow_through`, including its outcome. A completed review is recorded as `reviewed`, which does not imply successful trade, work, rest or conversation.

Pending goal reviews prevent another personal wave from repeatedly replacing the same resident's unresolved purpose. The queue preserves goal ID, actor, focus, decision/queue times, trigger, policy version and model provenance. Arrival, a queued review, heard words and committed effects remain distinct evidence stages.

This is a follow-through mechanism for revisiting intentions. It is not yet a general commitment system with promises, deadlines, negotiated obligations, breach remedies or multi-person joint plans.

## Fairness means attention, not forced choices

[`config/dispatch-policy.json`](../config/dispatch-policy.json) now controls queue attention. With the current policy, priority at or above 0.8 becomes overdue after 60 observed game minutes; other requests become overdue after 240 game minutes. Known overdue requests receive oldest-first attention across kinds. Otherwise one follow-up request alternates with ordinary attention, and ordinary social/economic reviews alternate where available.

A new discretionary social opportunity cannot overtake unfinished follow-up or overdue work. Urgent work with unknown age also prevents insertion. Parallel travel batches use consecutive compatible requests at the front of the fair queue, so batching cannot skip an earlier meaningful review simply because a later action is easier to run concurrently.

The queue reports pending requests, known and unknown ages, maximum observed wait, overdue count and follow-up count. These rules limit overtaking. They do not guarantee a completion deadline: unloading, unavailable opportunities, model latency and native failures can still delay or hold work. The scheduler chooses whose opportunity receives attention; the resident still chooses the action and other participants retain consent.

## Larger bounded budgets, frozen per run

[`config/director-policy.json`](../config/director-policy.json) replaces the fixed 64-personal-call allowance for new sessions. The earlier 64-call watching-run result remains historical evidence in [personal goals](personal-goals.md).

| Mode | Default / maximum foreground events | Scheduling window | Personal inference allowance | Due-review interval |
| --- | ---: | ---: | ---: | ---: |
| Sample | 6 / 12 | 600 seconds | 192 calls | 5 seconds |
| Play | 96 / 96 | 3,600 seconds | 768 calls | 5 seconds |

These are maximum allowances, not a requirement to spend them. Existing native goals run between model decisions. The observer controller writes an exclusive per-run policy file before starting the worker. The file contains the resolved limits, versioned source snapshot and hashes. The worker validates it and checks that its event/time arguments agree. Later edits to the source configuration cannot silently change a running session's limits.

The displayed maximum model-call count includes the foreground event ceiling plus the personal allowance. The personal scheduler accounts for attempted and reserved calls. Exhaustion stops new personal inference without inventing a completed goal or cancelling already accepted physical work. The scheduling window is checked around bounded work; it is not a hard process-kill deadline for an effect already underway. This remains a finite session, not a self-restarting or 24/7 agent service.

## Stationary owner production

An owner-production review can interrupt a resident's standing journey without counting travel as labour. The native continuity controller temporarily substitutes a self-targeted work lease identified as `owner-work-<event>`. It retains the suspended standing-goal identity. Production verifies the exact owned package, actor/target mailbox, acknowledged serial and lease status before accumulating work time near the recorded anchor.

For the current owner-work contract, the resident must remain within 100 native units of the anchor. A break in attendance earns no work credit; failure to resume within 30 wall seconds holds the work. Paused time earns no credit, and a backwards or excessive game-clock jump is rejected. The existing recipe consumes one observed grain and creates two bread after qualified labour. It does not pay an owner a wage or create money. After terminal work and release of its foreground claim, the original standing assignment can resume.

This establishes stationary attendance at the resident's current anchor. It does not establish an appropriate production building, use of a crafting station, a verified labour animation or a fully data-defined recipe catalogue. Those remain separate implementation requirements.

## Controlled native qualification

![Controlled owner-work attendance and inventory timeline](images/owner-work-fixture-timeline.png)

[Sanitized sampled data](owner-attendance-timeline.json). The plot uses observed sample times; it does not invent a timestamp for the separately observed resumed journey.

The isolated native trial used **zero model calls** and explicitly authored choices. It selected a personal journey for actor `108149`, then exercised owner production in event `daily-68-108149` while that journey was active. The local source receipt is `work/owner-attendance-native.json`; full native state snapshots are not reproduced here.

| Observed item | Result |
| --- | --- |
| Trial classification | Controlled native protocol fixture; not autonomous behaviour |
| Owner work outcome | `owner_work_completed` |
| Gold | 102 → 102 |
| Bread | 4 → 6 |
| Grain | 20 → 19 |
| Credited work | 10 / 10 game minutes |
| Final recorded attendance | Owned stationary lease verified; approximately 0.092 native units from anchor |
| Standing journey afterward | Same original goal and destination resumed with an owned travelling package |
| Local observation samples | 86 samples covering approximately 38.1 wall seconds from first to last recorded work sample |

The resumed journey had its original goal ID and destination, with a later lease serial. This proves the exercised suspend → stationary work → resume protocol. It does not prove that an unforced agent chose production, that the destination was reached afterward, or that a connected autonomous supply chain completed. The unchanged gold and exact grain/bread delta qualify this recipe's physical effect, not profitability or economic realism.

The original baseline was restored successfully across all 17 compared fields. [Sanitized native receipt](owner-attendance-evidence.json).

## Personal context admission

An independent review reproduced oversized personal-goal prompts for 25 of 26 residents in a saved native snapshot. The largest unbounded context was 28,373 bytes. Goal contexts now preserve every action, destination, executable mapping, resource and public economic term while reducing duplicated history and bounding actor-owned attention. All 26 actual request payloads fit the unchanged 16 KB provider guard offline; the largest was 14,049 bytes. The original memory store is preserved. This is request-admission evidence, not model-quality or autonomous-behaviour evidence.

The first live attempt was deliberately stopped after one completed employer refusal while this gap was repaired. Its 27 personal attempts and 25 overdue reviews remain recorded locally. Queue ages accumulated in the saved test lineage; these are evidence of a backlog, not a steady-state fairness benchmark.

[Offline request-size evidence](goal-context-window-evidence.json). Expired, unstarted social intentions with no available partner now release their follow-through instead of trapping the resident indefinitely. Started interactions retain their existing settlement protocol. A resident's body heading no longer rotates a continuous single-subject movie shot, though geometry clearance remains unverified. Paused runs are labelled Paused rather than complete.

## Autonomous native run and retained failure

The next bounded run completed seven foreground activities: three spoken employer refusals, three verified seated rests and one meal. Six goal-linked reviews completed, while 20 remained pending. Rest intentions sometimes led to asking about work or eating after reconsideration; the original focus did not force the later action.

| Measured item | Result and scope |
| --- | --- |
| Observation | 545 samples across 667.448 wall seconds, including terminal observation |
| Personal inference | 29 calls; two completed waves and one held wave |
| Peak movement | 27 position-observed movers; 25 owned travelling packages; 23 travel intentions, sampled separately |
| Voice delivery | Six ended native overlay playback receipts, 33.379 seconds total |
| Economic effects | No new sales or production; one carried bread consumed; aggregate gold and grain unchanged |
| Completed self-care | Three verified rests and one meal |
| Personal follow-through | Six completed goal-linked reviews out of 26; 20 still pending |
| Reported provider cost | US$0.009839528; excludes local compute and is not a billing reconciliation |

[Sanitized terminal evidence](purposeful-run-evidence.json) · [Six selected synthesized voice assets](https://45ck.github.io/whiterun-society/#voice-example).

The dialogue remains too formal and repetitive. An initiator says “Thanks for asking” while making the inquiry, and another reply uses “Thank you for reaching out.” Measured reply preparation gaps were 9.07–12.38 seconds. Ended playback does not establish natural timing, role-appropriate wording, lip sync or human realism.

![Native run showing retained personal-goal failure](images/purposeful-run-held-goal-lane.jpg)

The personal-goal lane held after a valid model result was stored while a foreground rest occupied the native action channel beyond a 40-second settlement window. The original run retains that failure. After it settled, explicit reconciliation applied the same still-valid claim and stored result, with **zero additional model calls** and the original receipt unchanged. The resulting goal was accepted and travelled; this was recovery, not a new autonomous trial. [Separate reconciliation receipt](retained-goal-reconciliation.json).

The resulting save `WS-Purposeful-20261025-BV` at checkpoint 3054 restored all 17 compared fields. This proves the captured save state, including goal follow-through; it does not prove long-term stability.

The worker repair retains paid results while waiting for native effects, bounded by 600 seconds and the saved claim lifetime. Only an explicit same-session, pre-mutation busy response permits result-submission retry. Inference is not repeated. Failures now preserve their stage and exception category. The extended wait has regression coverage; a fresh long-native-effect overlap is still unqualified.

The native screenshot before the UI correction also exposed a historical scripted scenario appearing as current activity. That card is now removed from live movie view; retained scenarios appear in collapsed, explicitly controlled history using actual saved actors and outcomes.

![Earlier native rest review with the misleading historical card](images/purposeful-live-rest-review.jpg)

The most important remaining throughput issue is structural: foreground rest/work occupies the shared action channel, so other meaningful reviews wait. [The next concurrent-activity slice](simulation-roadmap.md) separates long attendance from short serialized effect commits. Quiet and legitimate rest remain valid; waiting behind an unrelated long action is a capacity defect.

## Test scope

Revision `e702d19` passed **535 Python tests and 209 JavaScript tests on both hosted Windows and Linux**, including generated plugin builds and Windows Papyrus compilation. These validate the exercised rules, queue ordering, policy snapshots, follow-through contracts and native adapter behaviour. The controlled in-game trial adds physical evidence for stationary owner work. Neither test counts nor that fixture establish all-resident agency or human realism.

Later deadline enforcement exposed six legacy fixtures that omitted a positive scheduling window. Their action/release assertions were preserved and their clocks made deterministic. Revision `e8b82bd` passed the complete 519-test Python suite and JavaScript checks on both hosted Windows and Linux; the current local JavaScript suite passed 209 tests. The settlement repair has 31 additional focused checks; its hosted result is tracked separately.

## Final native goal qualification

The follow-up exposed two further defects before inference: evolved goal state exceeded the context limit, and claim identity was inspected before the checkpoint containing it had bound. The first is repaired with a lossless compact action catalogue and bounded prior-goal execution metadata. The second now waits for binding before validating identity. Their failed records remain distinct from the repaired trial.

A fresh native wave then made **nine model calls, accepted all nine decisions and confirmed all nine arrivals**. All 29 compared inventory accounts remained unchanged, and no rest recovery was granted merely for arrival. Reported provider cost was **US$0.002328732**. Every choice was rest-oriented travel, so this validates execution in a tired population, not broad behavioural variety. The new save at checkpoint 3091 restored all 17 compared fields. [Final qualification and retained failures](purposeful-final-qualification.json).

The lab remains paused after the bounded trials. No continuous broadcast or automatic paid loop was started.

Required next evidence includes unforced focus selection followed by actual meals/rest/work/conversations, repeated fair dispatch under a backlog, foreground speech while meaningful goals progress, save/resume of unresolved follow-through and owner work, and native failures that release cleanly without duplicated effects. Broader supply chains, causal relationship consequences, verified productive places/animations and long-run observation remain active work.

Full native RTS input qualification also remains blocked. An automatic policy review blocked the offline toolchain-layout action before execution; the native input rebuild remains **unbuilt**. This is separate from the implemented JavaScript/UI controls and cannot be reported as a successful native input fix. See [RTS input evidence](rts-input.md).

[Development plan](development-plan.md) · [Quantitative roadmap](simulation-roadmap.md) · [OKR definitions](society-okrs.md) · [Earlier personal-goal native trials](personal-goals.md).
