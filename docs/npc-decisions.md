# Event-driven residents

The target is a society that makes consequential decisions without continuously
running language-model agents. Ordinary navigation, work and idle behaviour remain
Skyrim routines. A delivery failure, unmet need, conversation or scheduled review
can request a decision. Idle residents do not submit model prompts.

## Personality and circumstances

The first three authored profiles use openness, conscientiousness, extraversion,
agreeableness and neuroticism. These are tendencies, not destiny. The intended
decision context combines those traits with changing needs, emotions, goals,
relationships, limited beliefs and remembered events. Panic, loyalty, pride and
incorrect information can produce imperfect choices with understandable causes.

Currently only the profiles, explicit rumour, real carried inventories and an
authored starting hunger/stress value are supplied. Memories are empty. No claim
is made that dynamic needs, learned opinions or relationships are implemented.
The profiles are demo interpretations, not canonical psychological assessments.

## First local inference, 24 October 2026

Pinned Qwen3.5-2B Q4_K_M runs through llama.cpp b11849 on four CPU threads. The
local server listens on 127.0.0.1:17842, requires a generated local key and has
agent tools and web UI disabled. The model is resident but inference happens only
when the explicit event runner calls it. No cloud inference has been tested.

Run `python tools/prepare_model.py --root D:\WhiterunLab`, then
`python tools/launch_model.py --root D:\WhiterunLab` once. With the game bridge
ready, run `python tools/run_decision_event.py --runtime D:\WhiterunLab\runtime --event-id UNIQUE-ID`.
The runner never executes game actions. Its proposals appear in the native
observer overlay; they are not spoken dialogue.

The first run exposed a poor choice set: no resident carried bread, so only
continuing the routine was available. The second run added proposals to ask about
the rumour or warn a neighbour. It produced:

| Resident | Selected proposal | Latency | Quality observation |
| --- | --- | ---: | --- |
| Carlotta | Ask about delivery | 5.672 s | Wants confirmation before a food decision |
| Ysolda | Ask about delivery | 4.641 s | Wants confirmation before risking money |
| Adrianne | Ask about delivery | 5.312 s | Explanation says she will not waste time on rumours; inconsistent with selected action |

Three valid JSON responses do not prove believable personality differences. All
three chose the same action; the third explanation contradicts it. This baseline
fails the intended behavioural-quality gate. It does prove local event-triggered
inference, real inventory context and presentation in the running game. An exact
event retry returned `duplicate: true, model_calls: 0`.

A third run strengthened the action/explanation instruction. Adrianne's text then
agreed with asking, but Carlotta's and Ysolda's explanations became analytical and
ran into the schema's length limit. The revised instruction still fails the
natural-dialogue requirement. Latencies were 8.172, 5.797 and 5.797 seconds.

The second run is preserved in `docs/evidence/local-ai-proposals.json`. Results
are session-bound. A changed game session or actor inventory during inference
holds the event. Only one event can be running; interrupted events require
explicit investigation rather than an automatic retry. Completed proposals may
be displayed as historical proposals, never as current executable commands.

## Next acceptance gates

1. Consistent action and explanation across a recorded scenario set; measure
   invalid output, contradiction and unsupported factual claims separately.
2. Counterfactual tests varying traits and needs while keeping other inputs fixed;
   measure effects instead of forcing every person to choose differently.
3. Both parties consent before commerce; recheck resources and save lineage before
   execution. No model can mint currency, inventory or arbitrary engine commands.
4. Confirmed outcomes change bounded memories, trust and needs. The corresponding
   game save restores exactly those states, including mid-transaction recovery.
5. Show an actual choice -> movement/action -> outcome -> changed later decision.
6. Add generated voice and lips after that loop works, then compare local and cloud
   quality, latency, resource use and cost on the same recorded scenarios.

Sources: [Qwen model card](https://huggingface.co/Qwen/Qwen3.5-2B),
[quantized model](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF),
[llama.cpp](https://github.com/ggml-org/llama.cpp).
