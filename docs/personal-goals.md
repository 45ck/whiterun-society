# Independent resident goals and measurable activity

Movie view is the main watching experience. Each eligible, loaded resident can hold a personal destination or quiet interval while other residents travel, eat or converse. Their goals are saved state; four concurrent model requests choose a wave of up to 32 decisions. Skyrim runs the physical journeys independently through up to 128 standing-control slots. Foreground interactions retain priority.

![Independent resident loops and measurement](images/independent-lives-metrics.png)

Generated system illustration, not a game screenshot. [Generation prompts](evidence/independent-lives-image-prompt.md).

## Decisions follow state

The decision context contains the resident's needs, personality, own inventory, recent memories, commitments, previous goal, observed time/weather and own physical activity. Other people's private state is excluded. Feasible destinations come from currently observed references in a versioned venue catalogue. Missing, blocked or replaced actors cannot silently receive an old identity's choice. Quiet remains a valid option.

Policy values live in `config/resident-goals.json`; the existing market and nine benches live in `config/places.json`, with authored-map provenance. These are editable scenario data, not automatic discovery of every useful place in Skyrim. Native cell/worldspace, reference, availability and ownership checks still control execution. Changing JSON alone does not make a behaviour intelligent.

Claims are saved before inference, results are validated against current state, and expired or failed claims cannot replay themselves. Policies are copied and hashed into the claim. Arrivals need the expected owned native package, matching goal/reference and independently checked geometry. Arrival creates a memory; it creates no money, goods, wages, recovery or conversation.

The director checks for due personal decisions every five seconds during foreground work. Initial and background waves share a 64-call personal-decision allowance per run. The movie HUD reports attempted and reserved calls separately and explains held or exhausted scheduling. Existing physical goals continue after the allowance is exhausted. This is bounded operation, not an always-on model loop or a qualified 24/7 service.

## Native qualification

The final three-event run included a released dialogue failure, a completed meal and a completed four-line conversation between a Whiterun Guard and Heimskr. Other residents continued their own journeys during the speech.

| Measured result | Final trial |
| --- | ---: |
| Personal inference attempts | 44 in 11 waves |
| Choices accepted against fresh state | 41 / 44 |
| Rejections | 3 resident-unavailable results |
| Retained settled journey arrivals | 41 / 41 |
| Peak owned simultaneous travel tasks | 20 |
| Peak residents with sampled 3D movement | 21 |
| Peak sampled moving residents during voice playback | 15 |
| Delivered voiced turns in completed encounter | 4 |
| Standing-lease failures in the 196.7-second recorded window | 0 |
| Provider-reported personal decision cost | US$0.006731, 44 / 44 receipts |
| Native save/reload and rollback comparisons | 17 / 17 each |

The 41 arrivals are journey events, not 41 distinct people. The final retained population contains 22 residents with an arrived goal, two held unavailable-resident decisions and five without a personal goal. All-resident, all-location autonomy remains incomplete. One dialogue attempt was rejected because its greeting contradicted native time; the scheduler continued other residents after verified release.

![Movement and native voice playback samples](images/personal-goals-movement-chart.png)

This chart uses sampled native geometry. It separates displacement from intended travel; purple bands mark observed overlay playback. It does not establish continuous tracking, clear camera sightlines, physical speaker audibility, lip sync or human conversational realism. The four selected clips are in the [voice gallery](index.html#voice-example).

[Machine-readable receipts, metrics and save proof](personal-goals-evidence.json).

## Failures retained and repaired

An initial 26-decision trial reached 25 destinations and held one journey, then exposed shared native lease expiry during checkpoint writes. Existing validated leases now renew while a new checkpoint binds, without applying uncommitted assignments.

The first integrated test then exposed a lost approach acknowledgement: a personal arrival checkpoint superseded the foreground receipt. Foreground outcomes now settle first, and repeated command IDs re-deliver their cached receipt without repeating the effect. Both conversation and economic-travel regressions cover this ordering. The failed trial remains in the evidence file.

HTTP retries are restricted to an explicit, pre-mutation checkpoint conflict in the same native session. Network failures, provider failures and completed effects are not automatically replayed. Queued inference starts have a 120-second wave scheduling deadline and bounded per-call socket waits; a trickling network peer is not a hard process-kill deadline.

## Subsequent watching run — retained failure

Run `society-ba50565eb00140f1` completed four foreground events before its fifth event was held by the bounded context-size validator:

| Event | Recorded outcome |
| --- | --- |
| `daily-55-225366` | `rested_at_bench` |
| `daily-58-108162` | `seller_declined` |
| `encounter-6c5b1982c6b945c2bc5e` | `continued_quietly` |
| `daily-27-225386` | `ate_bread` |
| `encounter-4eb28d60fade4d15af78` | Held: `Decision request exceeds the bounded context size` |

The run used its configured **64 personal-decision calls**, spread across seven completed waves. Exhausting that allowance correctly stopped further personal inference; the director's terminal hold was caused by the fifth foreground event's context rejection, not by budget exhaustion. Previously selected physical goals could continue without more model calls.

![Actual Skyrim observer showing the held watching run, exhausted personal-decision allowance and context error](images/personal-goals-budget-hold.jpg)

Actual captured game interface in the paused/held state. The 64-call allowance and context error are diagnostic evidence, not proof of a successful watching session.

The context-construction repair is implemented and passed a new three-event native qualification below. The four completed events remain valid retained outcomes, including refusal and quiet passage; this run is not a completed six-event session. It is separate from the earlier 44-call, 41-arrival trial above and does not replace that trial's measurements or save proof.

## Quantitative acceptance

The versioned scorecard has **51 main targets plus six spatial targets**. At the retained trial baseline: **one met, eight below target, thirteen insufficient-sample and thirty-five unmeasured**. The met result is spatial telemetry coverage, not simulation realism. The separate roadmap contains 50 planned acceptance protocols.

The current destination layer offers quiet or visiting a feasible place. In this trial all accepted personal choices were visits: many reference IDs do not create many distinct behaviour mechanisms. Economics, relationships and speech are measured separately. Increasing the number of moves, calls or chart lines is not an acceptance criterion.

[OKR definitions](society-okrs.md) · [Spatial sampling and exclusions](spatial-metrics.md) · [Ambitious acceptance roadmap](simulation-roadmap.md).

Validation: 419 tests passed in the complete Python run; subsequent focused tests cover acknowledgement ordering, scheduling, context and metric refinements. The final JavaScript suite passed 196 tests; the context repair passed 52 focused Python tests. These checks supplement the native evidence above. Natural dialogue, productive routines, richer drama, broad supply chains, robust camera visibility and sustained-operation qualification remain active work.


## Context repair and fresh native qualification

The rejected case's exact decision payload was reduced from **16,297 to 11,265 bytes** while retaining **all 18 candidates and all 19 ordered choices**. The actor's full 32-memory history stayed in the save; eight recent or relevant memories entered the decision. Repeated provenance is referenced once, execution telemetry is excluded from recollections, and appraisals have a bounded recent window. The 16 KB provider limit is unchanged. `config/context-window.json` controls attention limits. Larger crowds may receive an explicitly reported nearby-candidate attention window; omitted people still exist.

Fresh run `society-48b1c8dd7d4f4df8` completed all three events: a five-line social conversation, a seller refusal and an employer refusal. Every selected social clip has an unmuted overlay-ended receipt with both participants nearby throughout. This run records no successful sale. Its 64 personal calls cost US$0.013716528 across reported personal receipts, excluding foreground calls. The 298-sample window lasted 364.10 seconds, reached 24 observed moving residents and reached 13 moving during playback. These measurements are a separate trial from the earlier 44-call baseline.

![Conversation during the context-repair trial](images/context-window-live-conversation.jpg)

Actual native screenshot during the five-line conversation. This capture precedes the follow-card spacing repair; that overlap is retained as historical UI evidence. The wording is still formal, and body orientation is not eye contact or line-of-sight proof. Physical audio output and lip sync remain unqualified.

Save `WS-ContextWindow-20261025-BT` reloaded with all 17 checked fields matching. The original oversized claim remains held and was never replayed. [Compact context, native receipts, speech clips and save verification](context-window-evidence.json).

![Completed trial after HUD spacing repair](images/context-window-completed-hud.jpg)

Actual native screenshot after completion and deployment of the spacing fix. The camera-follow card now yields space to visible left-side panels; the native idle layout was checked, with active-phase transitions covered by UI tests. Long panels remain scrollable, but reliable native pointer input is still open.

## Native RTS input remains a priority

Observed CEF pointer events can land on the page outside the intended sidebar. Source inspection suggests NirnLab's cached Skyrim virtual-cursor coordinates rather than disabled CSS scrolling. Only inspected source fragments and the installed binary are currently available locally, without a complete native build toolchain and dependency set. No guessed coordinate multiplier or native binary patch has been deployed. Acquire a pinned, licensed complete build or implement a supported adapter, then qualify real selection, follow, wheel zoom, sidebar scroll and drag controls in Skyrim. DOM tests do not close this requirement.
