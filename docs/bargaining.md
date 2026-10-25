# Resident bargaining

Initialized towns now use resident-selected bids and seller counteroffers instead of the previous fixed 3/5-septim sequence. Current actors, enterprises and personal transaction memories determine the choices. Old in-flight plans retain their previous protocol for save compatibility.

![Illustrated resident bargaining loop](images/resident-bargaining-loop.png)

*Generated system illustration, not gameplay. [Full prompt and provenance](bargaining-image-prompt.md).*

## What chooses and what executes

1. Our code builds feasible actions from the resident's own wallet, needs, food policy and completed transactions. The buyer sees the public seller opportunity, not private seller stock, wealth or motives.
2. Jev chooses whether to approach, an affordable opening bid, and whether to accept a seller's price, make one higher final bid after refusal, or leave. The seller independently chooses acceptance, refusal or a counteroffer on the first bid.
3. Deterministic wording carries the exact amount into spoken terms. Kokoro synthesizes each line. The current economic protocol does not ask an LLM to invent prices or receipts; the separate social dialogue system still uses language alternatives.
4. Native attendance and speech receipts precede the agreed exchange. Code checks stock, money, current consent and policy again before issuing the physical inventory command. A changed quote cannot silently consume reserved household food.
5. Only a verified exchange becomes a completed trade and personal price memory. Refused bids remain offers, never paid-price evidence.

There are at most two buyer bids and six economic decision calls. The authored search space contains integer prices 1–12, selected wider steps up to 100, the affordable bound and neighbours of personally remembered prices. This is bounded bargaining, not a market-clearing model or proof of economic realism. Wages, the single recipe and household policy remain authored simulation rules.

## Actual Skyrim qualification — 25 October 2026

| Evidence | Model-selected negotiation | Controlled native protocol test |
| --- | --- | --- |
| Participants | Fralia Gray-Mane and Carlotta Valentia | Same pair in a restored branch |
| Selection | Operator selected a feasible pending food review; Jev selected all subsequent actions | Authored inference responses to exercise counteroffer acceptance |
| Terms | Buyer bids 5; seller refuses; buyer bids 6; seller refuses | Buyer bids 4; seller asks 7; buyer accepts |
| Speech | Four delivered turns, nearby throughout | Four delivered turns, nearby throughout |
| Result | No sale or inventory exchange | One bread transferred for 7 septims |
| Buyer | Unchanged by the negotiation | 34 gold / 0 bread → 27 gold / 1 bread |
| Seller | Unchanged by the negotiation | 102 gold / 4 bread → 109 gold / 3 bread |
| Inference | Five Jev calls; provider-reported US$0.001063608 | No external inference; explicitly tagged fixture |
| Persistence | Retained in checkpoint 2037 | Rolled back afterward; all 17 save comparisons matched |

The controlled sale conserves 136 total septims and four loaves across both parties. The seller's household policy stayed unchanged; only the agreed loaf was released. It validates the protocol's physical effects, not an autonomous model choosing that sale. Provider-reported usage is not a billing invoice.

![Actual Skyrim view after the controlled counteroffer sale](images/bargaining-native-fixture.jpg)

*Actual post-trade capture from the controlled test. The two actors and exchange status are visible; this is not a capture during spoken dialogue.*

[Structured evidence and transcripts](bargaining-evidence.json) · [Listen to all eight generated utterances](https://45ck.github.io/whiterun-society/#voice-example). The WAVs are synthesized assets used by the encounters, not recordings of physical game output.

## Observer corrections

The economy panel separately counts buyer bids, seller asks and verified paid prices. Histograms and medians come from stored events, including explicitly labelled fixtures when present. The trade camera now targets the active economic pair before a previous social pair. Economic timing uses that plan's decision and audio timings rather than stale social-conversation metrics. Controlled tests are labelled in the encounter pipeline.

The capture used the observer camera API. Native injected mouse coordinates remain incorrect, so this is not proof of working in-game button selection. A roof obscured one initial angle; manual yaw and distance corrected it. Automatic camera occlusion avoidance remains unfinished.

## Verification and remaining work

Regression coverage includes affordable bids, private-information isolation, reserved-stock consent, stale-quote rejection, final-refusal termination, heard acceptance before inventory effects, old-save rollback, price metrics and camera pair selection. The complete local suite passed: **329 Python tests** (545.780 seconds) and **155 JavaScript tests** (2.229 seconds). The first Python run retained one outdated arrival-phase expectation; it was corrected from `consent` to `quote`, then the full suite passed. Hosted CI remains unverified.

Still required: an unforced model counteroffer sale, repeated production/trade/consumption cycles, more goods and upstream inputs, persistent price learning across many trades, fuller daily routines, low-latency natural conversation, lip sync, native RTS input and recorded game audio/video. The society director remains paused after qualification; no continuous livestream was started.
