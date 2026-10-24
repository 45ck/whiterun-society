# Cheap language models for NPC dialogue

Ordinary dialogue should use the least expensive model that meets the scene's quality and latency requirements. The current language role proposes wording and conversational intentions; Jev makes constrained selections, code enforces consequences, and Skyrim executes movement. A larger reasoning model is not required on every utterance. Small models can also reason; model size is not an authority boundary.

The current runtime configuration remains GPT-4.1 mini. Smaller candidates were tested without changing the game or its model configuration. A future escalation policy for difficult planning or social negotiation is a design target, not an implemented automatic router.

## Latest shortlist: August–October 2026 releases

Researched on 25 October 2026 using [Artificial Analysis releases](https://artificialanalysis.ai/models/releases) and the live OpenRouter catalog. GPT-4.1 mini is the existing baseline, not the recommended destination. The earlier Ministral probe below is a narrow historical experiment, not a comparison of the latest models.

Prices are USD per million input/output tokens from this [public catalog snapshot](evidence/model-catalog-20261025.json). They exclude caching and extra reasoning tokens; catalog listing timestamps are not release dates. All six cloud candidates advertise structured outputs, but none has yet passed our dialogue adapter and scene-grounding tests.

| Candidate | OpenRouter input / output | Evidence and intended experiment |
| --- | ---: | --- |
| `ibm-granite/granite-4.2-8b` | $0.06 / $0.25 | Genuine 8B open-weight model, released August. [AA](https://artificialanalysis.ai/models/granite-4-2-8b/) reports about 92 output tokens/s and 0.71s TTFT on IBM's API. Its tested variant reasons: TTFT does not establish time to a usable answer. First compact API candidate to qualify with minimal thinking. |
| `inception/mercury-2.5` | $0.04 / $0.15 | September diffusion model; parameter count not established here. [AA](https://artificialanalysis.ai/models/mercury-2-5) reports about 742 tokens/s and 3.59s TTFT. [OpenRouter](https://openrouter.ai/inception/mercury-2.5/) labels this pricing an 80% discount and reports different route performance. Attractive cloud-cost candidate, not demonstrated local SLM. |
| `inception/mercury-3` | $0.10 / $0.35 | Newer catalog entry, listed October 16. Independent AA performance was not found in this research. Keep as an unqualified candidate, not an AA-confirmed winner. |
| `anthropic/claude-haiku-5.5` | $0.10 / $0.50 | October release, undisclosed size. [AA's Low setting](https://artificialanalysis.ai/models/claude-haiku-5-5-low) reports about 176 tokens/s; its [release comparison](https://artificialanalysis.ai/models/releases/claude-haiku-5-5) reports about 6.6s to the first answer. Candidate for harder dialogue, not an automatic low-latency speech choice. |
| `upstage/solar-mini4` | $0.05 / $0.20 | September release; [AA](https://artificialanalysis.ai/models/solar-mini4) reports about 95 tokens/s for a reasoning variant. Cheap API pricing alone does not qualify it for short conversational turns. |
| `inclusionai/ling-3.1-flash` | $0.075 / $0.225 | October release; [AA comparison](https://artificialanalysis.ai/models/comparisons/ling-3-1-flash-vs-glm-5-3-flash) lists 560B total / 25B active parameters and about 11s to first answer. Cheap cloud inference, not a small local model. |

The genuine tiny local shortlist is [K2 Horizon 3.7B](https://artificialanalysis.ai/models/k2-horizon-3-7b) and [MiniCPM5-2B](https://artificialanalysis.ai/models/minicpm5-2b), both September releases. AA lists 3.7B and 2.6B parameters respectively, with open weights. No OpenRouter route was found for either in this catalog snapshot, and no speed under this PC's Skyrim workload has been measured. K2's benchmarked variant reasons, so small size alone does not guarantee quick replies. Quantization, runtime support and GPU contention need qualification before installation becomes a default.

Recommended next experiment: Granite 4.2 8B and Mercury 2.5 for cloud dialogue, then K2 Horizon 3.7B versus MiniCPM5-2B locally. Use matched short scenes, an explicit reasoning budget or supported thinking-off mode, and measure p50/p95 time to **validated usable line** and **audible speech**, grounding failures, repetition, JSON validity and actual billed cost. Check provider support before sending reasoning controls. Keep deterministic fallbacks when inference is late; never block the economy waiting for a sentence.

For scale, an illustrative 1,000-input + 100-output-token utterance costs $0.000055 on Mercury 2.5, $0.000085 on Granite, or $0.00056 on the existing GPT-4.1 mini baseline. At 10,000 such utterances that is $0.55, $0.85 or $5.60 respectively, excluding reasoning, retries and TTS. These are arithmetic estimates, not measured production bills. Shortening and grounding context can matter as much as the model choice.

AA measurements use its benchmark workloads and routes, not our game prompts. Search snapshots and live measurements fluctuate. Do not combine an OpenRouter discount with AA's first-party throughput and present it as one measured service. AA's general intelligence score also does not directly measure believable NPC conversation.

## Earlier external shortlist

Checked on 25 October 2026. Artificial Analysis measures intelligence, output speed and latency separately. Its [Ministral 3 3B report](https://artificialanalysis.ai/models/ministral-3-3b) lists approximately 207 output tokens/second; its [Mistral comparison](https://artificialanalysis.ai/models/creators/mistral) lists approximately 0.68 seconds to the first answer token. Those are external measurements, not this game's complete dialogue latency or a test of character consistency.

The [OpenRouter public model catalog](https://openrouter.ai/api/v1/models) reported these standard input/output prices, excluding caching and provider-specific variation:

| Exact model | Input USD / million tokens | Output USD / million tokens |
| --- | ---: | ---: |
| `mistralai/ministral-3b-2512` | 0.10 | 0.10 |
| `mistralai/ministral-8b-2512` | 0.15 | 0.15 |
| `google/gemini-2.5-flash-lite` | 0.10 | 0.40 |
| `openai/gpt-4.1-mini` | 0.40 | 1.60 |

[Ministral's provider page](https://openrouter.ai/mistralai/ministral-3b-2512) also lists JSON-schema structured outputs, which our adapter requires. Low token prices and high throughput are shortlist criteria; they do not establish correctness or low end-to-end latency for short responses.

## Nine language-only probes

Each of three models received the same three cases: Ysolda remembering a seller's refusal, Carlotta replying, and a polite refusal of an invitation. The first two contexts came from the saved voice demonstration. The refusal case is an explicitly synthetic fixture with no shared history. Each request used the existing `language.propose` adapter, temperature 0.7, maximum 500 output tokens, and two proposed lines of 8–30 words. There were no automatic retries and no Jev, synthesis or game commands.

| Model | Existing parser accepted | Both lines within 8–30 words | Mean request wall time | Reported cost |
| --- | ---: | ---: | ---: | ---: |
| Ministral 3 3B | 3/3 | 0/3 | 1.604 s | US$0.00039648 |
| Ministral 3 8B | 2/3 | 1/3 | 3.380 s | US$0.00032007, incomplete |
| GPT-4.1 mini | 3/3 | 3/3 | 1.448 s | US$0.00191080 |

The 8B mean includes its failed request. Its failed response did not survive the adapter's validation, so its usage is unavailable; its reported cost is not the total billed cost. The combined US$0.00262735 is likewise only the cost reported by accepted responses. Word limits were checked separately because the current runtime validator enforces its JSON/character constraints, not that requested word range.

The 3B result was about 4.8 times cheaper across the three accepted calls, but it was not faster in this sample. It claimed to have eaten its last loaf despite an observed loaf remaining. The 8B reply invented a mill, crops and prior-week history absent from the context. GPT-4.1 mini met the mechanical checks, but also used language such as shared worries that deserves grounding review. Passing a schema or word limit is not equivalent to behaving naturally or truthfully.

This is one sample per case per model, with unpinned OpenRouter provider routing. It is not a statistically reliable speed ranking or a broad NPC quality benchmark. [Inputs, outputs and timings](evidence/dialogue-model-probe.json)

## Where the encounter time went

The resumed two-turn encounter took 145.124 seconds. Its language calls totalled **4.906 seconds**, Jev calls **1.141 seconds**, and local synthesis workers **13.703 seconds**. Approximately **95.68 seconds** elapsed between the meeting and first proposal phases, including approach and orchestration. Playback, checkpoint synchronization and other waits account for the remainder. These categories are measured from different worker/stage timers and are not a precise profiler trace.

Changing language models alone cannot eliminate the travel time or synthesis startup. Preserve physical causality while improving staging, reusing a warm speech engine and measuring time to audible speech. Do not teleport residents or claim instant conversation merely to improve a latency chart.

## Next routing policy

1. Use deterministic code for scheduling, candidate validation, economic accounting, memory selection and native verification.
2. Keep Jev for bounded action and consent decisions while measuring its contribution against simpler baselines.
3. Trial a small non-reasoning language model with a compact fact capsule and a shorter, model-appropriate prompt. Test factual role consistency, private-state boundaries, refusal, reply relevance, repetition and speech length.
4. Use stronger reasoning only for a genuinely harder planning task or an explicit bounded escalation. No hidden cascade of paid retries exists today.
5. Compare local inference under the actual Skyrim GPU/CPU load before claiming that offline is faster or cheaper overall.

No default switch was made on the basis of this probe. The next candidate must improve cost without losing grounded, watchable dialogue.
