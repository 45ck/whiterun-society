# Society quality lab

Latest additions: [situated dialogue and established acquaintances](situated-dialogue.md), [26 quantitative development OKRs](society-okrs.md), [voiced transaction protocol](voiced-trade.md), and [all finished visual documentation](gallery.md). Historical baselines below retain their original counts and limitations.

Two controlled playing-turn interruptions released both speakers in approximately 1.74 and 1.68 seconds. The second also recorded an explicit native audio-controller stop acknowledgement. Neither created a heard turn. The first lacks a stop acknowledgement, and neither measures acoustic stop latency. Deliberate observer interruption is reported separately from technical failure; uninterrupted completion rates exclude it while raw rates retain it. [Receipts and save restoration](evidence/society-okr-live.json)

The observer's live metrics come from the **current save lineage**. They are not cumulative across reloads and not a representative population study. Explicit test-model encounters and pre-census authored conversations are excluded from autonomous social rates. All counts carry denominators or scope. Changing the names of potential partners does not increase semantic action diversity.

## Initial live baseline — 25 October 2026

Before the new paired-attendance trial, the current save contained six terminal, model-driven accepted chats: four completed and two held. That is **66.67% completion**, with one rejected language output and one listener departure. Nine issued audio turns had completed nearby playback; that 9/9 result does **not** erase the failed encounters, and does not prove physical speaker output. The newest completed exchange took **56.889 seconds** according to its worker receipt, including approach, inference, synthesis, playback and appraisal. Historical encounters without timestamps remain absent from timing distributions.

The physical ledger contained **0 committed sales, 2 production events and 39 meals**. Both production events conserved gold, but this includes staged integration work; it is not two proved autonomous employment cycles. Two enterprise charters existed. Implementation breadth remains **one sale good, one production recipe and one transformation step**. Pricing is a choice among authored quotes, not a market-clearing mechanism.

There were eight directed relationship records, four with positive affinity and none with negative affinity. That is not evidence of rich drama. The current drama mechanism is subjective appraisal and affinity; multi-party conflict, escalation, reconciliation and institutions remain incomplete.

## What each number means

| Metric | Definition | What it cannot prove |
| --- | --- | --- |
| Accepted chat completion | Completed social exchanges / terminal encounters where the listener chose `chat` | Whether dialogue is natural or interesting |
| Encounter resolution | Complete / (complete + held), including legitimate quiet choices and refusals | Number of actual conversations |
| Failure categories | Terminal held encounters grouped by language, attendance, playback, routing, save/session or other cause | Root cause without inspecting the retained receipt |
| Duration | Wall time from persisted encounter creation to terminal completion/hold | Continuous speech duration; waits are included |
| Reply dispatch gap | Next audio prepared time minus previous witnessed playback end | Acoustic time to first audible sample; native dispatch adds delay |
| p95 | Nearest-rank 95th percentile, shown with sample count | A stable tail estimate with one or two samples |
| Issued playback completion | Delivered turns / issued delivery IDs retained in this lineage | Success of language generation before a delivery was issued |
| Nearby delivered playback | Delivered turns with native nearby-throughout confirmation / delivered turns | Unobstructed vision, acoustic occlusion or gaze |
| Body-facing error | Absolute wrapped yaw error towards the other actor, sampled for each actor during speech; mean and maximum | Head or eye orientation. Frame samples are correlated, not independent trials |
| Gold conservation | Committed trade/production records with equal total gold before/after / records with observed balances | Price realism, fair bargaining, profitability or supply-chain viability |
| Economic breadth | Supported sale goods, recipes and transformation steps; observed sales/prices separately | Autonomous business creation or an emergent market |
| Social diversity | Semantic choice counts and Shannon entropy over retained social decisions; partner IDs normalized | Intelligence, human realism or a count of meaningful possible futures |
| Known model cost | Sum of usage cost on retained accepted result envelopes, with coverage count | The total provider bill: rejected responses are retained separately in worker receipts |

`metrics.py` calculates the save-derived metrics. `conversation.py` stamps new encounter, prepared-speech and witnessed-completion boundaries. `bridge/speech.js` samples body yaw when the native getter is available. Unsupported or missing measurement stays `null`, never zero error or 100% accuracy. No body orientation sample is backfilled into old encounters.

## Deliberately unscored

Eye gaze, head gaze, line-of-sight raycasts, lip-sync timing, physical output audio, psychological validity, human dialogue realism and interoperability have no qualified measurements yet. A successful `setLookAt` request is not gaze measurement. Completing protocol tests is not an interoperability score.

A future human review sheet should rate opening appropriateness, reply relevance, factual grounding, personality consistency, believable incentives and scene coherence on anchored 1–5 scales, with reviewer identity, event IDs, independently reviewed samples and disagreement reported. This would be an authored evaluation rubric, not a validated psychometric instrument. Model-generated self-ratings must be shown separately from human ratings.

## Proposed engineering targets, not achieved claims

- At least 30 accepted-chat trials across changed participants and conditions; completion above 90%, with every failed attempt retained.
- Reply dispatch gap median under two seconds and p95 under five seconds; separately measure actual acoustic onset before calling this audible latency.
- Paired attendance maintained throughout speech and model waits; verify release for both participants after success, refusal, interruption and reload.
- Expand to at least three traded goods and two linked productive transformations, then test shortages, stock recovery, wage affordability and market clearing. Preserve money and item provenance throughout.
- Demonstrate disagreements that affect later choices and can resolve; count distinct causal mechanisms rather than negative lines or high sentiment scores.
- Add calibrated body/head/eye measurements and occlusion raycasts before proposing gaze thresholds. Validate geometry against captured scenes.
- Test restore, schema migration, missing actor, provider failure, malformed outputs, duplicated commands and plugin compatibility independently. Report pass counts and environment versions; do not combine them into a single unsupported interoperability percentage.

## Running the society

The service process needs the credential referenced by the local `jev-config.json` and `language-config.json` in its environment. The control room never receives that credential. Sessions allow 1–12 resident events (the UI offers 2, 6 or 12), with at most 21 model calls per social event: six language proposals, six speech selections and nine partner/consent/continuation/appraisal decisions. Economic events retain their five-call ceiling. The ten-minute observation window is checked between events; an event already underway may finish afterward within its own bounded worker timeout. This is not an always-on agent loop.

Stop requests settle the current encounter or transaction before ending. They do not kill a model call, stop the game, or erase inventory effects. A native/load failure holds the run visibly. No session restarts itself after a service restart or save change.

Economic need reviews and social opportunities are interleaved. When no queued social event is available, a bounded nearby opportunity lets a resident choose a partner or defer. Such events are labelled director/operator opportunities, not invented urgent social needs. Speech and relationship appraisal remain separate from inventory-changing trade/work decisions: **business negotiation is not yet fully spoken end to end**.

After mutual conversation acceptance, the bridge uses two existing `WhiterunLanes.esp` aliases for attendance. Both must show owned packages before speech preparation. Lost ownership holds the encounter, and both packages must be released. At this historical milestone, society serialization prevented overlap with travel. The subsequent [background protocol](concurrent-society.md) assigns attendance to slots 6–7 and background travel to slots 0–5; native travel/speech overlap is still unqualified.

## Paired-attendance live qualification

Two subsequent model-driven encounters completed with both native attendance packages observed and both released. The retained accepted-chat completion rate became **6/8 (75%)**, preserving the previous language and attendance failures. Across these two timed scenes, median duration was **64.057 seconds**, and median reply dispatch gap was **15.8 seconds** (p95 15.881, n=2). This latency is well outside the proposed natural-conversation target. Body yaw error averaged **0.27 degrees**, with a **15.157-degree maximum** across **3,008 correlated actor-frame samples**; this is not head/eye accuracy.

The mixed four-event run completed two chats and one meal, then held when another resident left observation before eating. That intended meal is not a consumed loaf. The current ledger then contained 40 meals. The current save `WS-VoiceQuality-20261025-AP`, checkpoint 810, restored all **16 compared fields**, including conversation, people, economy and inventories. [Compact live evidence, failures and metrics](evidence/society-quality-live.json)

A developer-model review also flagged an unsupported claim about steady smithing workload in a delivered line. The opening prompt was tightened afterward, but that is not proof the grounding issue is solved. Human realism ratings remain unknown. The full local suite passed 208 Python tests and 99 JavaScript tests; seven focused metrics/service tests passed after the final metrics and root-route edits. These test results do not replace live experience or human evaluation.

## Extended dialogue and warm voice — subsequent trial

New autonomous conversations allow two to six turns (default six). After each delivered line, the listener independently chooses to reply, close politely with speech, or leave quietly. A six-turn ceiling forces the final generated line to close the exchange. The limit is a bound, not a requirement to keep talking. Early endings are counted by reason, separately from technical failure. Legacy two-turn encounters remain readable.

The local voice subprocess loads during approach, serves only this encounter's bounded requests, then exits. Its environment excludes the configured cloud model credentials. It has no listening socket, retries or background agent loop. An authenticated service shutdown route rejects restart while society effects are in flight; it does not stop the game.

One live trial produced **three delivered turns**, with a Jev-selected polite closing, both native attendance packages retained and both released. It used **12 calls** (three proposals, three speech selections, six social choices), taking **68.032 seconds** including the worker's startup/settlement overhead. Voice model initialization took 1.719 seconds; each warm synthesis took **1.813, 1.875 and 2.094 seconds**. Reply dispatch gaps were **10.630 and 10.256 seconds**. These are shorter than the prior two-sample 15.8-second median, but the participants, lines, call count and runtime conditions were not controlled. This is evidence of functioning warm synthesis, not a causal performance benchmark. Ten-second gaps still miss the conversational target.

The current lineage now contains **8/10 completed accepted chats (80%)**, 18 delivered turns, zero committed sales, two production events and 40 meals. The old failures remain counted. Six earlier authored encounters are excluded from autonomous rates. Neither the increased completion rate nor a longer transcript establishes realism.

**Grounding remains inadequate:** the opening asserted forge warmth without explicit temperature evidence; the listener suggested sitting without an executed sitting action; the closing invented unfinished pieces and a nightfall deadline. These are developer-model observations of the retained transcript, not human scores. The three lines and native playback evidence are retained in [the compact trial receipt](evidence/extended-dialogue-live.json). Speech-to-economic-action integration remains incomplete.

The full updated local suite passed **215 Python tests**. All **99 JavaScript tests** passed across the main suite and attendance suite; the hosted workflow now includes the four attendance tests previously omitted from its explicit list. Seven focused metrics/service tests passed after the final assertions, including refusal to shut down during an unsettled checkpoint. The new native save `WS-LongDialogue-20261025-AQ`, checkpoint 877, restored all **16 compared fields**. Tests prove the exercised contracts, not human experience.
