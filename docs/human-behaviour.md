# A resident is more than a shopping policy

Calvin's target is a psychologically informed, embodied society inside Skyrim.
The food errand is an integration experiment, not the definition of a person or
the final scope. Believability must come from persistent causes and consequences,
including apparently irrational choices, rather than random mistakes or extra
dialogue. The design below is a research-informed hypothesis, not a validated
model of all human behaviour.

## What the resident model needs

| Domain | State and mechanisms to model | Evidence required |
| --- | --- | --- |
| Perception and attention | Own viewpoint, line of sight, occlusion, audible events, distance, salience, distraction, familiar people and places | An unseen or unheard event does not become knowledge; a nearby salient event can interrupt a task |
| Body and time | Hunger, fatigue, health, pain, comfort, sleep, travel time and limited daily time | Needs evolve on game time, pause appropriately, and change after actual eating/resting rather than merely buying food |
| Personal identity | Big Five tendencies, background, values, aspirations, learned skills, self-image, commitments and habitual routines | Stable differences across repeated situations, with room for context-dependent change |
| Emotion and appraisal | Concern about threats, progress toward goals, perceived control, anger at unfair treatment, shame, relief and recovery | An event changes an appropriate state; the effect decays or is revised, and can alter a later choice |
| Knowledge and memory | Episodic experiences, source-tagged rumours, confidence, freshness, forgetting, mistaken interpretations and reflective summaries | False beliefs remain distinct from world truth; only exposed residents learn an event; corrections can change beliefs |
| Social life | Family obligations, friendship, affection, trust, resentment, reputation, reciprocity, status, promises, norms and institutions | A relationship has a traceable history and changes relevant interaction, including repair and forgiveness |
| Economic life | Household versus business assets, wages, jobs, skills, production inputs, stock, consumption, savings, debt, rent, prices, bargaining, search costs, risk and outside options | Every transfer reconciles; production and consumption have causes; shortages propagate through actual constraints |
| Imperfect judgment | Satisficing, limited attention, reference points, loss sensitivity, present bias, anchoring, social influence, habit and uncertainty | Controlled scenarios show the intended effect without making every person identically biased or globally foolish |
| Agency | Long-term aims, daily plans, short tasks, alternatives, interruptions, negotiation, refusal and replanning | A model-selected intention changes observed activity and can be abandoned when its premise fails |
| Expression | Dialogue, tone, turn-taking, gaze, gesture, voice and lip sync | Expression agrees with the resident's knowledge and the outcome; a fluent explanation is not proof of the underlying mechanism |

We should not fill every field with arbitrary numbers and call that psychology.
Start with mechanisms whose effects we can observe, record parameter provenance,
then compare hypotheses and calibrate. Authored traits and the current +0.35
meal-time hunger increment are demo parameters, not empirical estimates.

## Reasoning at different timescales

1. Skyrim handles navigation, animation and immediate physical execution.
2. Cheap deterministic updates maintain conserved resources, elapsed time and
   routine progression. A small decision model can select among meaningful
   alternatives when a stimulus matters.
3. A language model can interpret ambiguous social events, propose a plan,
   negotiate, produce dialogue and reflect on experience. Plans must use an
   explicit action vocabulary with observable preconditions and effects.
4. The scheduler requests new reasoning after changed needs, a failed plan,
   an offer/refusal, a relevant perception, an important memory or a scheduled
   review. It does not prompt every resident every frame. Inactivity is valid.

The decision policy should predict this character's plausible choice, not always
maximize gold or hunger relief. Deterministic rules enforce physical and accounting
facts; they do not need to prescribe every preference. Model probabilities are
uncertainty about outputs, not automatically a person's emotions or a calibrated
distribution of human actions.

## Knowledge boundary

The engine observes world truth for validation. The resident receives their own
resources, perceived events, prior knowledge, memories and beliefs. Another
resident's pocket contents, motives and unseen conversations are not public.
Public stalls, displayed prices or spoken offers require an actual observation
or an explicitly authored starting fact. Failure to find stock should be possible.

The experimental sensor adds a line-of-sight filter, an authored 2,000-game-unit
range and 162-degree cone, sampling at most eight nearby visible actors. These
are engineering approximations, not a physiological vision model. They do not
recognize objects in pixels, hear dialogue, infer facial expressions or model
peripheral attention. Future image-model tests should use the resident's view,
not the omniscient spectator camera, and be triggered by relevant events.

Live samples initially returned no visible actors. A subsequent diagnostic saw
one actor from Adrianne's viewpoint, but controlled occlusion and viewpoint tests
are still missing. The sensor therefore reports `available: false` to residents;
its diagnostics are excluded from their decision context. Unavailable vision must
not be interpreted as an empty street. Earlier Jev experiments preceded this
qualification guard and retained their original inputs as evidence.

## Evidence that motivates the design

- [Simon, 1955](https://doi.org/10.2307/1884852) motivates bounded rationality:
  decisions are made under limits on information and computation. Our use of
  limited search and satisfactory alternatives is a design interpretation.
- [Kahneman and Tversky, 1979](https://web.mit.edu/curhan/www/docs/Articles/15341_Readings/Behavioral_Decision_Theory/Kahneman_Tversky_1979_Prospect_theory.pdf)
  motivates reference-dependent evaluation and unequal treatment of losses and
  gains under risk. It does not justify a single universal bias coefficient.
- [Generative Agents, 2023](https://arxiv.org/abs/2304.03442) connects observation,
  memory retrieval, reflection and planning, with ablations assessing believability.
  This supports testing those components separately rather than attributing all
  improvement to a larger prompt.
- [Humanoid Agents, 2023](https://arxiv.org/abs/2310.05418) integrates basic needs,
  emotions and relationship closeness into generative agents. It is relevant
  architecture evidence, not proof that our Skyrim residents resemble humans.
- [A recent Jev bias study, preprint](https://arxiv.org/abs/2610.19619) reports
  sensitivity to wording, response order and irrelevant numbers. We therefore
  retain probabilities and test reordered alternatives, rather than checking only
  whether an action ID is syntactically valid.

## Jev's role and the first comparison

[TypeSafe Jev 1.14 on OpenRouter](https://openrouter.ai/typesafe/jev-1.14) is a typed
decision model. It is separate from Jev Router, which routes requests to other
models, and unrelated to Meta's JEPA video world-model family. Our adapter uses
OpenRouter's [Decisions API](https://openrouter.ai/docs/guides/community/jev-tutorial).
Jev does not generate our dialogue. Its displayed action descriptions are authored
labels, and its emotion is recorded as unspecified rather than invented.

Four calls to served snapshot `typesafe/jev-1.14-20261014` used the same resident
context and three controlled variants. The live-context case selected seeking
bread (0.90 reported probability); reversing the option order preserved it (0.89).
Low hunger selected deferral; a synthetic bad-trade memory selected visiting
Adrianne. Latencies were 0.516–0.922 seconds. Reported total cost was US$0.00014721.
The synthetic memory was never inserted into the actual town. This is a diagnostic
with four cases, not a statistical validation or evidence of consciousness.

## What counts as progress toward humanlike behaviour

- Paired scenarios isolate hunger, trust, risk, deadlines or framing while holding
  other inputs fixed. Repeat with option permutations and multiple seeds/providers.
- Perception tests separate witnessing, hearing a report, remembering and never
  encountering an event. Track false-knowledge rate and source attribution.
- Longitudinal tests check habit, changing trust, repaired relationships, unmet
  needs and competing commitments across saved days, not one attractive response.
- Economy tests measure conservation, unmet needs, stockouts, price response,
  insolvency, unequal resources and recovery after shocks.
- Behavioural evaluation records contradictory actions, repetitive loops,
  unsupported claims and sensitivity to prompt wording. Do not force everyone to
  act differently just to make the demo look diverse.
- Player evaluation uses observation and participation: can the player understand
  what happened, influence it, recognize a resident later and encounter meaningful
  consequences? Frame time, decision latency and cost are measured alongside it.

The current loop is intentionally limited: one event and one traveller at a time,
bounded action choices, authored 3/5-gold offers, no unrestricted bargaining, no real
speech, no consumption and no full work/sleep schedule. Those remain requirements;
they are not replaced by a passing shopping or refusal demonstration.

## Reconsidering a failed plan

An initial refusal now records a source-tagged memory before asking the buyer
what to do next. The buyer can leave, switch to visiting Adrianne, or make one
final five-gold offer if affordable and still nearby. The seller independently
accepts or refuses the revised terms. A second refusal ends this bounded
negotiation. Changing destination creates a new native task ID so the bridge's
duplicate protection cannot mistake the changed plan for an already completed
trip. Accepted prices pass into the same conserved inventory-transfer protocol.

This is deliberately an authored negotiation protocol: limiting repetition is
an execution rule, not evidence that the model spontaneously learned social
etiquette. Choosing between revised terms and a different activity is the model's
part. Neither a refusal nor a higher price reveals the seller's hidden motive.
No refusal automatically damages trust. The longer-term requirement remains
learning which alternatives to try across days, with outside options, personal
commitments and household versus business stock represented explicitly.
