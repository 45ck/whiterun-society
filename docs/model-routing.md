# Cheap language models for NPC dialogue

Ordinary dialogue should use the least expensive model that meets the scene's quality and latency requirements. The current language role proposes wording and conversational intentions; Jev makes constrained selections, code enforces consequences, and Skyrim executes movement. A larger reasoning model is not required on every utterance. Small models can also reason; model size is not an authority boundary.

The current runtime configuration remains GPT-4.1 mini. Smaller candidates were tested without changing the game or its model configuration. A future escalation policy for difficult planning or social negotiation is a design target, not an implemented automatic router.

## External shortlist

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
