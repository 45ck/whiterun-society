# Society OKRs and interaction analysis

These are **authored engineering goals**, not validated psychological scales or evidence that simulated characters reproduce human behaviour. The live observer calculates values from the current save lineage and shows each target as `unmeasured`, `insufficient_sample`, `below_target` or `met`. A missing measurement cannot pass. A promising result with too few trials cannot pass. Tests and controlled experiments are labelled separately from emergent behaviour.

The expanded [living city programme](simulation-roadmap.md) supplies planned acceptance protocols for movement, decision continuity, knowledge, drama, economics, 3D geography, urban planning and sustained observation. Its `PLAN-*` targets are future qualification measures; they must not be displayed as measured results before their instrumentation exists.

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

## Versioned executable targets

The main scorecard now contains **51 configured key results** in [`config/quality-goals.json`](../config/quality-goals.json), version 2, evaluated by `quality_goals.py`. A separate six-target spatial configuration lives in [`config/spatial-metrics.json`](../config/spatial-metrics.json). Each definition carries a unit, comparison direction, required sample count and evidence scope. Instrumented values resolve from current evidence; targets without a measurement path remain unmeasured. The existence of 57 configured targets is implementation breadth, not 57 achieved outcomes.

The original 26 targets are preserved below. Thresholds are development choices, not scientific norms; changes require a versioned definition rather than silently regrading old trials.

| Objective | Key results |
| --- | --- |
| Believable encounters | SOC-01: ≥90% uninterrupted accepted-chat completion across ≥30 trials. SOC-02: median reply dispatch ≤2 seconds across ≥30 gaps. SOC-03: zero exact within-scene repeated lines across ≥100 delivered lines. SOC-04/SOC-05: human reply relevance and small-talk naturalness ≥4/5, each across ≥30 independently reviewed scenes. |
| Safe interruption | SOC-06: 100% verified cleanup across ≥10 interruptions. SOC-07: median settlement ≤3 seconds across ≥10 interruptions. |
| Physical credibility | PHY-01: ≥99% uninterrupted issued playback completion across ≥100 deliveries. PHY-02: ≥95% eye-gaze trials within a declared calibrated tolerance across ≥30 trials. PHY-03: ≥95% raycast agreement with labelled scenes across ≥30 trials. PHY-04: lip-sync absolute timing error ≤100 ms across ≥30 trials. |
| Functioning economy | ECO-01: ≥10 committed sales. ECO-02: ≥3 supported traded goods. ECO-03: ≥2 productive transformations. ECO-04: 100% observed gold conservation across ≥30 transfers/production events. ECO-05: ≥5 qualified shortage/recovery scenarios without fabricated assets. ECO-06: ≥3 autonomous profitable business days with input, wage and revenue accounting. |
| Behavioural sensitivity | BEH-01 to BEH-04: hunger→food seeking, fatigue→rest, price→purchase acceptance, personality→social approach. Proposed effect target ≥15 percentage points, ≥30 paired trials each, with uncertainty and confounds reported. These are authored sensitivity expectations, not universal human laws. |
| Social mechanisms | REL-01: favourable known history versus stranger; REL-02: refusal without automatic hostility; REL-03: conflict and later resolution. EVO-01: scarcity and sharing; EVO-02: reciprocity at controlled cost. Each requires ≥30 paired trials. These measure experiment coverage; they do not establish an evolutionary explanation. |

Economic metrics currently include staged protocol experiments, and implementation breadth is not equivalent to market realism. There is no composite “human realism” score, no required percentage of friends and no target to maximize drama artificially. Read the trial receipts and sample counts alongside any number.

## Added agency, economy, consequence and operations targets

| IDs | Configured acceptance target | Evidence boundary |
| --- | --- | --- |
| AGT-01 | ≥95% of initialized residents have a current goal; at least 20 initialized residents | Snapshot across initialized residents, including unloaded residents. Quiet and arrived goals count; failed goals do not. This is different from loaded resident-time coverage. |
| AGT-02 / AGT-07 | ≥98% validated personal decision results and ≤1% inference failure rate, each with ≥100 results | A validated choice is not an executed action. Provider failure and stale/invalid choice are distinct categories. |
| AGT-03 | ≥95% native-confirmed arrivals across ≥100 terminal journey outcomes | Goal-linked native receipts; unresolved journeys remain separately reported. Known test-model outcomes are excluded; legacy unknown provenance is explicit. |
| AGT-04 / AGT-05 | Personal-decision provider p95 ≤3 seconds and 100% billing receipt coverage, each with ≥100 results | Provider latency does not include all scheduling/native delays; missing billing is unknown cost, not zero cost. |
| AGT-06 | At least four normalized personal action classes across ≥100 accepted choices | Different destination IDs are normalized. The current destination/quiet repertoire is limited and cannot meet the target merely by adding NPC names. |
| AGT-08 to AGT-10 | Unresolved inactivity p95 ≤60 seconds; stimulus-to-replanning p95 ≤5 seconds; decision-to-action consistency ≥99%; ≥100 relevant cases each | Unmeasured until correlated time-series classification, stimulus receipts and cross-action effect checks exist. |
| ECO-07 / ECO-08 / ECO-09 | Five actually traded goods; 20 trading residents; 100% party-identity coverage; ≥100 relevant committed receipts | Actual receipt graph and commodity counts, including controlled qualification transactions. These are not autonomous market or fairness claims. |
| ECO-10 / ECO-11 / ECO-12 | Ten unforced connected supply chains; recovery within three game days across ≥5 supply-shock scenarios; 100% business-period profit reconciliation across ≥30 periods | Unmeasured until linked provenance, prespecified shocks and enterprise accounting are present. |
| DRA-01 | ≥80% of ≥50 recorded directed relationships have heard history | Seeded background relationships are separately counted. This is history coverage, not a friendship or drama quota. |
| DRA-02 / DRA-03 / DRA-04 | Ten conflict → changed action → resolution chains; ≥90% traceable belief revisions across ≥30 cases; ≥95% memory-consistent later decisions across ≥100 cases | Event-linked consequences and independent evaluation are required. Keywords, affinity signs and the existence of memory text cannot satisfy these targets. |
| BEH-05 / BEH-06 / REL-04 | ≥90% repeated-condition reproducibility across ≥30 trials; paired-intervention coverage of nine need/trait dimensions; 30 reciprocity trials with verified costs | Record stochastic uncertainty, confounds and failed hypotheses. These are authored mechanism experiments, not real-world psychological validation. |
| OPS-01 / OPS-02 | 24-hour bounded-cost observation qualification; 100% save/reload equality across ≥20 scenarios | Requires runtime/audio/camera health, retained failures and multi-field restore receipts. No 24/7 service or public broadcast is implied. |

## Spatial observation and city targets

The spatial sampler uses a configurable five-second minimum cadence, up to 720 frames within one hour, and 60 chart points. Its current policy rejects intervals over 15 seconds for movement measurement. It segments on session changes and backwards checkpoint/game-clock movement. Motion requires valid paired positions in the same native space while game time advances. Missing, unloaded, paused, invalid and teleport-like intervals are excluded from usable movement time and counted explicitly.

These measurements support an honest distinction between a chosen journey and observed movement. They do not establish navmesh distance, camera visibility, eye gaze, an unobstructed route, service capacity or affordable access. See [spatial definitions and limitations](spatial-metrics.md).

| ID | Configured target | Denominator and status boundary |
| --- | --- | --- |
| SPA-01 | ≥90% usable tracked actor-time | At least 300 candidate actor-seconds; invalid/gap/paused intervals do not become stationary activity |
| SPA-02 | ≥95% sampled personal-goal coverage | At least 300 loaded resident samples; a goal does not prove useful output or continuous model reasoning |
| SPA-03 | ≥95% verified reachable food destinations | At least 100 qualified route/access probes; unmeasured until routes, stock, opening conditions and affordability are checked |
| SPA-04 | Five route-disruption/recovery scenarios | Blocked-route interventions with observed replanning/recovery; unmeasured |
| SPA-05 | Neighbourhood food-access p90/p10 ratio ≤2 | At least 100 valid access observations with household geography and affordability; unmeasured and an authored planning objective |
| SPA-06 | ≥90% of businesses have measured queues and throughput | At least 30 businesses; requires service capacity and request/completion timestamps; unmeasured |

The initial town may be too small to satisfy a population-based target. The scorecard must show insufficient sample rather than lower its denominator or create synthetic residents. Later urban planning experiments will measure changes in travel burden, unmet need, congestion, business viability and distributional effects under explicit policy interventions.

## How to use the numbers

Show current level and change over a declared interval, with observation freshness and coverage. Keep the save-derived cumulative ledger distinct from rolling sampled telemetry. A reload may legitimately restore fewer events and must not appear as negative production, broken relationships or reversed motion. Keep exact evidence exports for each qualification run so charts can be reproduced.

For headline complexity, present a small set of interpretable dimensions: executed action families, connected production depth, traded goods, participating residents, supply-chain completion, linked social consequences, service access and adaptation to controlled shocks. Retain the detailed counts, latency distributions, failures, model costs and missing metrics underneath. A large scalar score would conceal the very gaps this programme is intended to expose.
