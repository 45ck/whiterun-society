# Independent lives in a shared town

The town should continue around an encounter. The new background protocol lets up to six residents travel while one disjoint pair uses the conversation channel. The code and integration tests cover that overlap. **The first live trial qualified one background journey and a voluntary deferral, with no eligible conversation pair; simultaneous native travel and speech remain unverified.**

![Generated architecture illustration, not a gameplay screenshot](images/independent-lives.png)

## Ownership and the three decision layers

Each resident receives their own needs, personality, memories and relationships. Jev chooses an allowed action, including doing nothing. A language model proposes contextual dialogue when an encounter reaches a speech stage; Jev selects a proposal. Deterministic code validates decisions, persists inference claims before model calls, reserves the participating actors, and accepts only matching native outcomes. Skyrim supplies navigation, package execution and the physical scene. Local Kokoro supplies the voice.

| Resource | Allocation | Release evidence |
|---|---|---|
| Background journeys | Up to six `WhiterunLanes.esp` slots, 0–5 | Each actor arrives or fails independently; its package and quest must release |
| One conversation | Slots 6–7 | Both attendance packages must be owned before speech and released at the end |
| Native foreground effects | One save-bound command channel | Matching command/session acknowledgement |
| Economic transactions | Serialized | Native inventory evidence, not speech or arrival alone |

An actor with an unfinished or unverified travel lease cannot become either speaker. Free residents remain eligible. The native bridge rejects a conflicting speaker or walking command too. A completed journey updates its own batch and memories without overwriting an in-flight speech command or inference claim. If release is uncertain, new activity stays blocked while an existing conversation can still clean up. Reloading an unfinished cohort holds it without repeating inference or replaying travel.

The named smith and Imperial resident are examples, not special-case conversation partners. The scenario's initial acquaintances are described in [established-town state](situated-dialogue.md). The native arrival check now receives seller IDs from current public food businesses rather than a fixed Carlotta ID. It still checks only currently observed, nearby sellers in a valid public place.

## Scheduling and bounds

The observer's bounded director enables parallel journeys. If at least two food-search opportunities and a spare social event fit the run budget, it uses background mode and can offer one conversation to a disjoint pair. The pair can defer, decline, end early or leave. No nearby eligible pair means no speech worker and no language calls. This is currently a food-search cohort, not persistent full-day planning for every resident.

A background cohort uses at most six Jev calls, with at most four requests in flight. Its optional six-turn encounter is capped at 21 further model calls. Both members and the encounter count against the director event budget. The worker retains separate travel and social receipts; it does not retry failed inference. On parent failure it requests a hold for its own child encounter and waits for the child's voice cleanup. A child that exceeds that cleanup bound is explicitly reported as still running rather than silently counted complete.

## Live trial: quiet night

`background-20261025-a` selected two existing affordable food-search opportunities without changing resources, NPC positions or acceptance decisions. Adrianne chose to defer; Idolaf chose to check the market. His route covered approximately 4,170 to 249 game units, then released correctly. No current public seller was observed at arrival. No suitable free social pair was found, so no conversation worker started.

The trial used two decision calls. Native peak ownership was one; travel/attendance overlap and travel/speech overlap were both zero. Deferral and a failed search do not satisfy hunger, create a sale or earn a realism score. [Compact native receipt](evidence/background-society-live.json)

The observer now shows travel/attendance and travel/speech frame counts separately. These are correlated update samples, not independent observations, durations, eye-contact accuracy, acoustic measurements or human realism ratings. The integration test runs the actual routing and attendance controllers against a mock native platform; that is code-level evidence, not a substitute for Skyrim qualification.

The native save `WS-BackgroundSociety-20261025-AT`, checkpoint 957, restored all 16 compared fields, including people, town, the completed background batch and inventories. All 29 inventory accounts compared before and after the trial were unchanged. This qualifies persistence of the completed outcome, not a save taken during simultaneous speech and travel.

Local validation passed the full 244-test Python suite, three subsequently added worker-cleanup tests, and all 105 JavaScript tests. Six quality/document-route tests and three director-control tests also passed after the final changes. The observer script passed syntax checking, and the local documentation server returned the exact new image bytes. Hosted validation is tracked separately in GitHub Actions.

## What remains

Next qualification must observe owned travel packages and disjoint attendance packages while native audio reports playing, then verify both independent releases and save/load. Persistent resident plans, indoor destinations, multiple conversation channels, resumable work, household schedules and a continuously populated town are still unfinished. Released NPCs can resume vanilla routines. Broad autonomy needs those executable activities and scheduling mechanisms; removing bounds alone would not provide them.
