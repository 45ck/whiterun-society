# Independent lives in a shared town

The town should continue around an encounter. The background protocol lets up to six residents travel while one disjoint pair uses the conversation channel. **A subsequent live trial observed Amren travelling while Adrianne and Idolaf completed three voiced turns. Heimskr's separate route failed to acquire its package and timed out.** One concurrent traveller and one encounter are qualified; the six-traveller capacity and broad continuous society are not.

![Generated architecture illustration, not a gameplay screenshot](images/independent-lives-observed.png)

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

[Hosted CI for implementation ecc2bb8](https://github.com/45ck/whiterun-society/actions/runs/40146182432) subsequently passed on Windows and Ubuntu: 247 Python tests and 105 JavaScript tests on each platform, plugin builds, and Windows Papyrus compilation.

## Follow-up: an encounter opportunity can disappear

A second trial, `background-20261025-b`, began only after observing three free initiators among Amren, Olfina and Jon, separate from the two proposed travellers. Adrianne again deferred and Idolaf chose the market. During travel, the free pair was no longer eligible; no conversation worker started. The approximately 63-second run used two decision calls, completed one verified journey and preserved all 29 compared inventories. Overlap counters remained zero. [Follow-up receipt](evidence/background-society-followup.json)

This exposes a scheduling limitation: observing a nearby pair before claiming travel does not preserve that encounter while vanilla routines move people. A future encounter reservation must let each person accept, decline or leave, and must qualify physical attendance before speech. Enlarging counters or forcing a chat would not establish that behaviour. Save `WS-BackgroundSociety-20261025-AU`, checkpoint 962, restored all 16 compared fields after this follow-up.

## What remains

Next qualification must repeat the observed overlap across more actors, explain and address failed package acquisition, and exercise six travel slots with a conversation. Persistent resident plans, indoor destinations, multiple conversation channels, resumable work, household schedules and a continuously populated town are still unfinished. Released NPCs can resume vanilla routines. Broad autonomy needs those executable activities and scheduling mechanisms; removing bounds alone would not provide them.

## Recent notices and the first observed overlap

Background cohorts now save the disjoint nearby candidates observed before travel decisions are prepared. For 45 wall-clock seconds in the same game session, those particular people can remain approach options up to 3,000 game units away, provided they are still loaded, uncommitted, unreserved and in the same native coordinate space. Ordinary proximity opportunities retain their 1,500-unit radius. These are authored scheduling bounds, not validated human perception. Neither a notice nor its consumption creates an acquaintance, shared memory, invitation or agreement. Jev may still defer; a partner still chooses whether to chat after an actual approach.

Current native observations include interior-cell/exterior-world identity. Proximity does not compare coordinates across different interiors or worlds. A notice cannot resurrect an unloaded actor, survive a changed game session, or be consumed by two encounters. Only the selected initiator's noticed candidate list enters the conversation record and model context. Lost or expired options are revalidated before execution.

Trial `background-20261025-c` used two Jev travel decisions and twelve conversation calls, with **US$0.001766578 reported** across retained results. Amren completed his market journey but found no seller. Heimskr never owned his expected package and timed out; both travel slots released. Adrianne chose to approach Idolaf, who chose to chat; the conversation ended politely after three delivered turns and released both attendance slots. Native telemetry recorded **2,558 travel/attendance frames and 591 travel/speech frames**. These correlated update counts are not durations or acoustic timestamps. [Compact receipt, transcript and failure](evidence/observed-overlap.json)

The notice was consumed 11.895 seconds after capture. The chosen speakers were already 126 units apart, so this trial does **not** exercise the extended-range branch or establish that notices caused the successful overlap. It does qualify the integrated disjoint travel/attendance/overlay-speech path. All 29 compared inventories were unchanged. Save `WS-Overlap-20261025-AV`, checkpoint 1001, restored all 16 compared fields after completion; mid-overlap save/load remains unqualified.

The encounter took 60.948 seconds. Warm synthesis took 1.234, 1.266 and 1.094 seconds, but the two reply dispatch gaps were **10.587 and 9.389 seconds**. The selected waking-time claim, “I've been up since dawn,” lacks explicit support in the supplied context. Thus the successful execution does not establish human realism or adequate dialogue grounding. [Listen to the three generated utterance assets](https://45ck.github.io/whiterun-society/#voice-example); these are not a recording of the game's audio output.

The observer exposes notices consumed, terminal unused notices, notice-to-start timing and the fraction of background cohorts with observed speech overlap. The previous two zero-overlap trials remain in the denominator: this lineage has one observed overlap among three terminal background cohorts. Local validation passed 253 Python and 106 JavaScript tests; seven focused documentation/service tests passed after adding the audio gallery.

## Occupied residents and released failures

The planner now senses native scene/combat/sleep activity, limits never-acquired packages separately from walking time, and isolates verified released cohort failures. [Behavior, tests and qualification](scene-aware-scheduling.md).
