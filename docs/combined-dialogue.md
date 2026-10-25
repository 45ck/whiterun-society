# Choosing a reply and whether to continue together

![The reply choice and confirmed-memory pipeline](images/reply-is-a-choice.png)

*Generated architecture illustration, not gameplay. [Built-in generation prompt and provenance](images/reply-is-a-choice.prompt.md). Partner selection and consent happen before this reply loop.*

The old loop asked Jev whether to continue, asked the language model for two lines, then asked Jev which line to use. Each inference also needed a persisted claim and result checkpoint. That made three sequential model calls for an ordinary reply.

New conversations combine continuation and utterance selection. After a delivered line, the language model proposes **one relevant reply and one polite ending**. Jev sees the actual words, its own needs, personality, relationships and memories, and chooses either line or a quiet departure. The deterministic layer validates the choice and text, preserves native attendance, synthesizes voice and waits for completed nearby playback before recording heard speech.

This keeps the decision model in control of continuing or ending the exchange. It removes a redundant round trip rather than assuming that every proposed line must be spoken. The opening still offers two opening alternatives; a refusal offers two courteous refusal alternatives; the final allowed turn offers two closings. The six-turn limit remains binding.

## Costs and silence

A six-turn accepted encounter now permits at most six language calls, six utterance decisions, partner selection, partner consent and two private appraisals: **16 calls instead of 21**. Four delivered turns use twelve calls instead of fifteen. Those counts do not include unrelated economic events.

A resident can still decline before a conversation, without any language proposal. Choosing silence after a line proposal has incurred that proposal's cost. The unspoken alternatives and decision are retained separately from delivered turns, and included exactly once in cost telemetry. They receive no audio, heard-memory record or invented farewell. Quiet departure is therefore not guaranteed to be cheaper than the older pre-proposal departure decision.

## Checkpoints and scheduling

Claims still bind before inference. Results still bind before a later stage uses them. Audio still binds before playback, and save/session changes still reject stale results. The worker polls outstanding checkpoints every 100 milliseconds and other native waits every 200 milliseconds; it no longer adds a fixed sleep immediately after submitting a mutation. No checkpoint acknowledgement is skipped.

The service and workers default new encounters to `combined_choice`. Existing saves without a reply-policy field keep `separate_choice`; reusing an encounter ID with a different policy is rejected. The direct worker supports `--reply-policy separate_choice` for explicit legacy runs. Completed or interrupted claims are not automatically rerun.

Malformed language responses retain a finite validation category, model, elapsed time and sanitized usage. The receipt is bound to the persisted proposal claim and counted exactly once, even though no line is delivered. Reusing the claim with a changed receipt or another session is rejected. Older failures remain in their worker receipts; the metrics are not an account-wide bill.

A failed social encounter no longer needs to freeze unrelated residents. The director can continue only after the same encounter has settled, its native release receipt confirms attendance release, any outstanding audio stop is acknowledged, and no checkpoint, command, inventory effect or other activity remains unresolved. The failed event remains visible and consumes its event budget. Observer interruptions and uncertain release still stop continuation. This recovery does not repeat the failed inference.

## Evidence

The first native run of the combined choice protocol completed a quiet opportunity, one meal and an Amren–Saffir conversation with four delivered turns. The conversation used four language calls, four utterance choices and four social decisions. Its three reply dispatch gaps were **7.586, 7.210 and 7.861 seconds**. The previous two-encounter director run measured 9.995–12.578 seconds. Different residents, lines, providers' response times and travel conditions prevent treating this as a controlled performance comparison.

The following faster-polling trial completed a deferred need, a market visit without an observed seller and a quiet social opportunity. It produced no voiced latency sample. A third trial rejected the first language proposal before speech, then released both participants. The old receipt records the billed failure but cannot identify which candidate rule failed; the new finite categories are not retroactively inferred.

Controlled tests cover polite endings, silent departures without heard memory, billed but unspoken proposals, the six-turn cap, closing-slot validation, old-policy retention, stale save/claim rejection and waiting for every checkpoint. Dialogue policy metrics separate the protocols and retain sample sizes. Reply dispatch is neither acoustic latency nor a rating of human realism; gaze, lip sync and natural conversation quality remain separate unfinished work.


The final four-event live run completed Ysolda–Sigurd (four turns), Sigurd's meal, Adrianne–Idolaf (two turns), and a guard's meal. Its 22 model calls reported $0.002527982. Both conversations released their native attendance. This run produced no new invalid response, so automatic continuation after a failed chat remains integration-tested rather than live-qualified. The Ysolda reply still invents an unsupported work explanation: successful playback is not grounding acceptance.

The isolated save `WS-CombinedDialogue-20261025-AX`, checkpoint 1233, restored all 16 compared fields. Local validation passed 276 Python tests; the existing full bridge suite passed 111 JavaScript tests, and the updated observer script passed syntax validation. [Four trials, quiet outcomes, failed inference, costs and inventory changes](evidence/combined-dialogue.json) · [Listen to the four Amren–Saffir voice assets](https://45ck.github.io/whiterun-society/#voice-example). These assets were used by confirmed overlay playback; they are not game-audio recordings.
