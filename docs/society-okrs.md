# Society OKRs and interaction analysis

These are **authored engineering goals**, not validated psychological scales or evidence that simulated characters reproduce human behaviour. The live observer calculates values from the current save lineage and shows each target as `unmeasured`, `insufficient_sample`, `below_target` or `met`. A missing measurement cannot pass. A promising result with too few trials cannot pass. Tests and controlled experiments are labelled separately from emergent behaviour.

## Relationships you can inspect

Affinity runs from −100 to +100 displayed gameplay points; familiarity runs from 0 to 100%. Relationships are directional. One NPC considering another a friend does not imply reciprocity. Missing relationship records mean no evidence, not dislike.

| Level | Authored rule |
| --- | --- |
| Stranger | No qualifying heard history or familiarity |
| Acquaintance | Some heard history or familiarity, but no stronger band |
| Friend | Affinity ≥25 points, familiarity ≥25%, at least six heard turns |
| Close friend | Affinity ≥60 points, familiarity ≥60%, at least twelve heard turns |
| Strained | Affinity ≤−25 points |

The dashboard counts directed levels, mutual friend pairs and one-sided friendships. The game inspector shows the same derived bands. No relationship level is granted merely to make the demonstration look active. Romance, family, kinship, rivalry narratives and persistent conflict resolution remain incomplete.

## Interruptions

The observer's **Interrupt social encounter** control records the request, interrupted phase and number of already delivered turns. It cancels the matching active native speech controller, releases attendance, and preserves completed heard memories. Unfinished speech creates no heard memory. A late provider result cannot replace the recorded interruption or trigger an automatic retry. This control is for social conversations, not cancellation of an inventory transaction.

Metrics report operator interruptions, technical failures, interruption stages, release verification and request-to-terminal settlement time. The native stop acknowledgement is separate, and historical trials without it remain unmeasured. Neither settlement nor a native stop acknowledgement proves exact acoustic stop latency. All-attempt completion and uninterrupted completion are both retained, so deliberate failure-injection experiments are not silently erased or mistaken for spontaneous reliability failures.

## Small talk and interaction analysis

Delivered English lines are scanned for greeting, courtesy, farewell, weather, business and conflict cues, plus question marks. Categories overlap. Exact repeated lines and repeated greetings within a scene are counted, alongside unique speakers, pairs and largest-speaker share. These are transparent lexical heuristics: “sorry” may be politeness, not conflict; a question mark says nothing about whether a response answered it. Semantic topic coherence, answer relevance and human small-talk ratings remain unmeasured.

## Race and personality

The observer reads the loaded actor's native Skyrim race ID and label when the API provides them. Labels can include engine categories such as “Old People Race”; they are game metadata, not real-world biological categories. Unloaded or unavailable observations remain unknown. The dashboard shows current loaded counts and means of authored Big Five traits. Traits are seeded independently of race. These counts do not establish race effects, causation or psychological validity. Controlled counterfactual experiments would be required before claiming that a trait, need or social history changes a decision.

## Twenty-six proposed key results

The executable definitions live in `quality_goals.py`. Each row includes units, direction, required sample count and evidence scope. Thresholds below are development choices, not scientific norms.

| Objective | Key results |
| --- | --- |
| Believable encounters | SOC-01: ≥90% uninterrupted accepted-chat completion across ≥30 trials. SOC-02: median reply dispatch ≤2 seconds across ≥30 gaps. SOC-03: zero exact within-scene repeated lines across ≥100 delivered lines. SOC-04/SOC-05: human reply relevance and small-talk naturalness ≥4/5, each across ≥30 independently reviewed scenes. |
| Safe interruption | SOC-06: 100% verified cleanup across ≥10 interruptions. SOC-07: median settlement ≤3 seconds across ≥10 interruptions. |
| Physical credibility | PHY-01: ≥99% uninterrupted issued playback completion across ≥100 deliveries. PHY-02: ≥95% eye-gaze trials within a declared calibrated tolerance across ≥30 trials. PHY-03: ≥95% raycast agreement with labelled scenes across ≥30 trials. PHY-04: lip-sync absolute timing error ≤100 ms across ≥30 trials. |
| Functioning economy | ECO-01: ≥10 committed sales. ECO-02: ≥3 supported traded goods. ECO-03: ≥2 productive transformations. ECO-04: 100% observed gold conservation across ≥30 transfers/production events. ECO-05: ≥5 qualified shortage/recovery scenarios without fabricated assets. ECO-06: ≥3 autonomous profitable business days with input, wage and revenue accounting. |
| Behavioural sensitivity | BEH-01 to BEH-04: hunger→food seeking, fatigue→rest, price→purchase acceptance, personality→social approach. Proposed effect target ≥15 percentage points, ≥30 paired trials each, with uncertainty and confounds reported. These are authored sensitivity expectations, not universal human laws. |
| Social mechanisms | REL-01: favourable known history versus stranger; REL-02: refusal without automatic hostility; REL-03: conflict and later resolution. EVO-01: scarcity and sharing; EVO-02: reciprocity at controlled cost. Each requires ≥30 paired trials. These measure experiment coverage; they do not establish an evolutionary explanation. |

Economic metrics currently include staged protocol experiments, and implementation breadth is not equivalent to market realism. There is no composite “human realism” score, no required percentage of friends and no target to maximize drama artificially. Read the trial receipts and sample counts alongside any number.
