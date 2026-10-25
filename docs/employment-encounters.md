# Employment becomes a visible encounter

Voiced job searches now happen face to face. A resident chooses a public opportunity, approaches its employer, asks aloud, and waits to hear an offer or refusal. The employer and worker choose separately. A contract is recorded only after completed nearby acceptance speech; inventory verification, not dialogue, establishes wages and production.

![Employment choices, speech, work and verification](images/employment-encounter-loop.png)

Generated explanatory illustration, not gameplay. The noticeboard and productive artwork are metaphors: public jobs currently come from operator-authored enterprise charters, and crafting animation remains unfinished. [Built-in image generation prompts](employment-image-prompt.md).

## Live model choice

On 25 October 2026, the operator selected the nearest eligible queued needs review. **Olfina Gray-Mane chose to seek work**, approached Carlotta Valentia and asked about the advertised ten-minute bread-making shift. **Carlotta chose not to offer it.** Both statements completed native overlay playback; no goods or money moved.

![Carlotta declining Olfina's employment request in Skyrim](images/employment-refusal-native.jpg)

The sampled worker interval was **38.322 seconds**. Two Jev calls reported **US$0.000366072**, with inference times of 0.859 and 6.453 seconds. These are provider-reported usage costs, not a billing audit. The words were deterministic economic terms voiced by local Kokoro; the language model did not generate this dialogue.

Olfina's personal memory now records only the heard refusal, its business identity, public revision and game time. It does not disclose Carlotta's private reason. Her next needs review is due after 15 game minutes instead of one hour. The same unchanged job is omitted for one game hour for Olfina alone; a revised public charter or elapsed hour allows reconsideration. Other work and needs remain available. These intervals are authored simulation rules, not psychological measurements. The scheduling and alternative-action branch are unit-tested; a subsequent unforced live review was not qualified here.

## Controlled accepted work

A separate native fixture selected Fralia Gray-Mane as the nearest currently feasible worker and authored the employer's offer and worker's acceptance. It used existing public terms and resources, with no grant or charter change.

![The controlled employment agreement, spoken before work](images/employment-agreement-fixture.jpg)

Four utterances completed: request, offer, acceptance and receipt. Ten game minutes of qualified attendance converted **one grain into two loaves**. Carlotta's purse changed **102 → 98**, and Fralia's **34 → 38**: their combined **136 septims** stayed conserved. The completion receipt was spoken only after native inventory verification. The sampled interval was **87.312 seconds**. This qualifies the accepted-work protocol, not autonomous hiring or believable crafting animation.

[Native receipts, model choices, costs and personal memory](employment-evidence.json) · [Listen to the six utterances](https://45ck.github.io/whiterun-society/#voice-example). Audio assets are the synthesized clips used by the game, not recordings of system output.

## Implementation and verification

The existing bounded economic worker now drives employment speech through the same nearby attendance and completed-playback checks as trade. After acceptance, both participants release the conversation packages before the worker acquires the work package. Receipt attendance gets a fresh command identity, so the bridge cannot silently reuse its earlier completed meeting. Interrupted audio does not teach the listener a refusal or create a contract. Changed terms before heard acceptance hold the plan.

The observer distinguishes employment from trade, shows work progress between agreement and receipt, and reports employment requests, outcomes and spoken acts separately from goods negotiations. Non-voiced legacy employment paths retain their existing compatibility behaviour; normal voiced society operation uses the new encounter path.

The full Python suite passed **345 tests**, followed by **6 employment tests** and **10 metrics tests** covering the final additions. All **172 JavaScript tests** pass, including the working-state progress panel. The panel's final change has automated coverage and is deployed; it was not separately recaptured during another native work cycle. Restoring `WS-Employment-20261025-BL` matched all **17 compared save fields**, including resources, contracts and memories. Trial effects were rolled back; source, clips and evidence remain.

Still required: unforced hiring and repeated profitable production/trade, productive locations and animations, replenished agricultural inputs, natural work dialogue, lip sync, physical audio qualification over long runs, and reliable RTS input. One refusal and one controlled paid shift do not establish a complete autonomous economy.
