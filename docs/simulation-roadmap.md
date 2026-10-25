# Living city programme and quantitative acceptance plan

Updated 25 October 2026. This is the active implementation programme for a **movie-first, RTS-only** economy and social simulation inside Skyrim. It is a plan for work and experiments, not a claim that the full society exists. The executable scorecard is documented in [Society OKRs](society-okrs.md); this page also specifies measurements that still need implementation.

The desired experience is a town whose residents pursue their own changing goals while the viewer watches conversations, work, trade, relationships and consequences. All eligible residents can hold and execute goals concurrently. Model inference happens when a decision is due or a meaningful stimulus warrants reconsideration. Walking, animation, accounting, perception sampling and valid action execution continue through deterministic and native code. Continuous thought is represented by continuing state, goals and attention; a queued inference is not active reasoning.

## Data-driven behaviour contract

Resident identities, capabilities, businesses, resources, beliefs, destinations, commitments and policies belong in versioned scenario or save state. Normal scheduling must work with added, removed, renamed and replaced residents. It must not require a named Skyrim character, a fixed conversational pair, a fixed outcome or a hidden quota of successful sales or dramatic incidents.

Agents choose from currently feasible actions using their own observations, remembered claims, needs and commitments. Language models propose contextual speech and interpretations; decision models choose actions and responses; validators authorize effects against current state. A speech claim does not create a fact, a promise does not complete an action, and arrival does not produce goods, wages or recovery.

Rules still exist. The implementation must define numerical representation, identity checks, resource conservation, permissions, path execution and failure handling. Authored policy values, experimental targets, action capability definitions and scenario geography should be explicit data with provenance and versions. Moving a fixed choice table into JSON alone does not establish agent autonomy. The acceptance question is whether changing relevant state changes feasible choices and subsequent observed behaviour without editing resident-specific code.

| State area | Required information and provenance | Required change behaviour |
| --- | --- | --- |
| Resident | Stable identity, native reference/base identity, capabilities, household, needs, personality parameters, current availability | Newcomers initialize from scenario policy; missing actors suspend rather than silently die; replacement identities do not inherit unrelated private memory |
| Knowledge and attention | Subject, claim, source, time, confidence, direct observation versus hearsay, expiry | Decisions receive only accessible information; contradictory observations can revise beliefs; attention has a bounded budget |
| Goal and action | Chosen purpose, feasible options, claim ID, policy/model version, preconditions, destination, participant reservations, progress and terminal receipt | Reconsider after meaningful change, arrival, failure or due time; no duplicate effects or reissued unresolved inference |
| Relationship and commitment | Directional familiarity, affinity, trust, witnessed interactions, promised action, deadline, evidence of fulfilment or breach | Hearing and consequences update the affected people; friendship and forgiveness are outcomes, not quotas |
| Enterprise and resource | Owner/custodian, offered capabilities, inventory provenance, prices/wages, production recipe, capacity, inputs, obligations | Entry, closure, shortages, price changes and loss affect choices; accounting does not create missing money or items |
| Place and city | Native worldspace/cell/reference, access capability, observed position, public/private knowledge, capacity and opening conditions | Current available places drive destination options; routes and service access respond to closures and changed supply |
| Observation and evidence | Session/save/checkpoint, observation time, native receipt, model usage, missing fields, experiment label | Reloads do not inherit future state; telemetry gaps stay gaps; staged tests remain distinguishable from unforced events |

These are the target data contracts. Existing implementation covers parts of each; unsupported fields and mechanisms must remain absent or explicitly unmeasured rather than be fabricated for a dashboard.

## Evidence and scorecard rules

Every quantitative result needs an ID, unit, window, population, numerator/denominator or distribution sample count, source, inclusion rules and missing-data coverage. Show failures and insufficient samples. Record software revision, scenario/configuration version, model/provider version, save/checkpoint and native environment for each qualification run. Compare like-for-like windows when presenting changes.

Separate five evidence classes: deterministic tests; controlled native protocol experiments; unforced model-driven native outcomes; sampled live telemetry; independent human evaluation. None substitutes for another. Report intention, model selection, native execution, delivered speech and committed economic effect separately. A high number of model calls, options, moving actors or negative statements is not evidence of intelligence, economic depth, drama or realism.

The `PLAN-*` identifiers below are **planned acceptance measures**. Their targets are authored engineering choices. They are not current dashboard values and cannot pass until the stated instrumentation and protocol exist. Sample sizes are initial minimums; causal studies must also justify precision or power and report uncertainty. Targets may change through a recorded policy revision, never retroactively to make a failed trial pass.

## M1 — Independent lives that remain observable

Save-bound personal goals and native standing travel below encounter priority are implemented. The initial 26-choice trial exposed shared lease expiry; the repaired 44-call trial retained 41 arrivals and movement during a four-line conversation. Later work adds food/rest/work/social review purposes, source-linked follow-through, fair queue attention and frozen run budgets. A controlled zero-model owner-work trial verified stationary attendance, the exact grain/bread recipe effect and resumption of the earlier standing journey. These are distinct evidence stages, not sustained all-resident acceptance. [Personal-goal trials](personal-goals.md) · [Purposeful reviews and work qualification](purposeful-agency.md).

| Planned measure | Initial target and denominator | Qualification protocol |
| --- | --- | --- |
| PLAN-AGT-01 — Eligible goal coverage | ≥95% of eligible loaded managed resident-seconds have an explicit goal or documented quiet/wait state, over three ≥30-minute sessions | Exclude genuinely unloaded/blocked time with counts shown; a technical hold does not count as purposeful quiet |
| PLAN-AGT-02 — Decision freshness | ≥95% of due, eligible decisions are claimed within the configured decision deadline, over ≥100 due decisions | Record due, claimed, inference start/end and commit times; queued and actively inferring are separate |
| PLAN-AGT-03 — Trigger responsiveness | ≥95% of ≥100 meaningful stimuli produce a justified reconsideration or explicit retained-plan decision within the configured deadline | Include depleted stock, partner departure, route failure, new commitment and changed opening conditions; repeated identical stimulus is deduplicated |
| PLAN-AGT-04 — Journey reliability | ≥95% valid issued journeys reach their destination across ≥100 terminal journeys, with all failed attempts retained | Require matching goal, native package ownership, current geometry and receipt; count unavailable, invalidated and timed-out journeys separately |
| PLAN-AGT-05 — Concurrent execution | At least 20 independently selected native activities overlap during each of three ≥10-minute qualification windows | Report current eligible population and observed overlap seconds; do not force meaningless walking to satisfy the target |
| PLAN-AGT-06 — Unexplained inactivity | ≤5% of eligible observed resident-seconds are stationary with no goal, justified wait, interaction or technical reason | Stationary work, sleep, listening and rest are valid activity; missing telemetry is unknown, not idle |
| PLAN-AGT-07 — Action follow-through | ≥90% of ≥50 accepted commitments reach an evidenced completion or an explicit, remembered renegotiation/breach outcome | A review request, visit or spoken promise alone does not count as fulfilment |
| PLAN-AGT-08 — Roster independence | 100% of a ≥30-case changed-roster matrix preserves valid identity and effect handling | Rename, add, unload, replace and remove participants/suppliers; retain tests with unresolved commitments and older saves |
| PLAN-AGT-09 — Duplicate prevention | Zero duplicated model claims or native economic effects across ≥100 replay/reload/timeout injection cases | Keep receipt IDs and attempted retries; unknown provider outcomes stop replay rather than silently spend again |

Movement rate, stationary-time distribution and action-family diversity are diagnostics, not targets to maximize. A calm town can be valid; a town frozen by unavailable capabilities cannot be labelled calm.

## M2 — Situated conversation, knowledge and relationships

| Planned measure | Initial target and denominator | Qualification protocol |
| --- | --- | --- |
| PLAN-SOC-01 — Conversation timing | Median reply dispatch ≤2 seconds and p95 ≤5 seconds across ≥100 replies | Measure end-of-playback to next dispatch separately from acoustic onset, inference and synthesis; include failures in completion statistics |
| PLAN-SOC-02 — Context grounding | ≥95% supported factual claims across ≥200 independently annotated delivered claims | Source-label time, weather, activity, familiarity and economic assertions; report annotator agreement and unsupported claims |
| PLAN-SOC-03 — Opening and ending appropriateness | Median ≥4/5 across ≥30 independently reviewed scenes per opening/closing category | Anchored rubric for familiar/stranger, interruption, refusal, morning/evening and quiet departure; not a validated psychometric score |
| PLAN-SOC-04 — Knowledge isolation | Zero private-state leaks across ≥100 adversarial stranger/hearsay/unheard-speech/reload cases | Test prompt inputs as well as delivered lines; a globally visible operator statistic must not enter resident knowledge without a source |
| PLAN-SOC-05 — Memory consequence | ≥30 paired counterfactual trials per memory mechanism with effect estimate and confidence interval | Hold opportunities and costs constant; compare remembered refusal, reliable fulfilment, betrayal and neutral history; no assumed positive effect |
| PLAN-SOC-06 — Physical attendance | ≥99% valid nearby attendance during issued speech across ≥100 deliveries | Report both actor-time coverage and independent encounter counts; body facing, head/eye gaze and occlusion remain separate |
| PLAN-SOC-07 — Relationship evolution | At least three qualified mechanisms with ≥30 paired trials each | Familiarity from heard interaction, trust from observed fulfilment, and affinity from appraisal; separate seeded background from later changes |
| PLAN-SOC-08 — Dialogue-to-action consistency | ≥95% of ≥100 action-bearing utterances either receive matching observed follow-through or an explicit unresolved/broken commitment | “I am working” requires observed work; “I will work” creates a possible commitment, not completed output |

Big Five parameters are gameplay inputs. Their presence does not prove personality fidelity, neurotypicality or psychological validity. Behavioural sensitivity tests should vary one need, trait, price or history dimension while controlling the rest, retain quiet/refusal outcomes, and test whether the chosen mechanism behaves consistently. Race is native game metadata; it must not silently determine real-world psychological assumptions.

## M3 — Drama with causes and consequences

Drama needs a traceable sequence: a contested resource, belief or commitment; participants with different knowledge and incentives; an action; witnessed consequences; and later choices. Sentiment labels and insults alone are insufficient.

| Planned measure | Initial target and denominator | Qualification protocol |
| --- | --- | --- |
| PLAN-DRA-01 — Causal event coverage | ≥90% of ≥50 social consequence events link to a recorded precipitating event and affected belief/relationship/commitment | Preserve cause IDs, who witnessed what, and alternative explanations; a generated story summary cannot create missing causes |
| PLAN-DRA-02 — Mechanism breadth | Four distinct implemented mechanisms, each with ≥10 native end-to-end cases | Initial candidates: broken promise, disputed price/work terms, scarce-resource competition, and inaccurate hearsay correction |
| PLAN-DRA-03 — Conflict persistence and recovery | ≥30 paired trials for each qualified persistence/reconciliation mechanism | Track later cooperation, trust and explicit resolutions; no forced hostility after refusal and no required percentage of reconciliations |
| PLAN-DRA-04 — Multi-party knowledge | ≥30 three-person trials with zero unauthorized transfer of private facts | Witnessing, overhearing, retelling and correcting must each have receipt-backed information transfer |
| PLAN-DRA-05 — Consequence coherence | Median ≥4/5 across ≥30 independently reviewed causal chains | Reviewers receive event evidence and an anchored rubric; report disagreements and failures, not model self-grades |

Initial appraisal and affinity already support limited social consequences. Multi-party conflict, obligations, reconciliation and institutions require implementation and qualification. The plan does not claim evolutionary explanation or real-world behavioural validity.

## M4 — A connected, accountable city economy

| Planned measure | Initial target and denominator | Qualification protocol |
| --- | --- | --- |
| PLAN-ECO-01 — Production depth | At least five traded goods and three distinct productive transformations in one connected native session | Count actual recipe/input/output mechanisms; reselling or renaming a good does not add a transformation |
| PLAN-ECO-02 — Unforced chain completion | ≥20 unforced input purchase → production → sale → consumption chains across ≥3 game days | Link receipt IDs and distinguish autonomous decisions from controlled protocol fixtures; no external stock injection hidden in the chain |
| PLAN-ECO-03 — Accounting integrity | 100% reconciled money and item provenance across ≥500 committed effects | Explain grants, consumption, transformation, losses and transfers; conservation applies according to declared operation semantics |
| PLAN-ECO-04 — Business accounts | ≥5 businesses with reconciled revenue, input cost, wages, assets and liabilities over ≥3 game days | Shared custodian wallets are insufficient for independent profit claims; define cost recognition and accounting period |
| PLAN-ECO-05 — Prices and substitution | ≥30 paired trials per price/shortage/substitution intervention with effect and uncertainty reported | Measure offered versus paid prices, refusal, quantity and alternative choice; no presumption that every market clears |
| PLAN-ECO-06 — Shock recovery | Five qualified supply/demand shock scenarios with ≥10 repetitions each | Report stockouts, unmet need, price dispersion, recovery time, failed businesses and remaining external support |
| PLAN-ECO-07 — Entry, closure and insolvency | ≥30 cases spanning formation, voluntary closure, cash shortfall and insolvency resolution | Assets/obligations remain accounted; model choice cannot erase debt or mint starting capital |
| PLAN-ECO-08 — Participation and concentration | Report buyer/seller coverage, trade-network degree and revenue shares per game day over ≥3 days | These are distributions, not quotas; distinguish lack of opportunity from deliberate non-participation |
| PLAN-ECO-09 — Wages and labour | ≥30 paid and refused work offers across varied wage/input/need conditions | Match heard agreement, actual attendance, work receipt, wage transfer and productive output |
| PLAN-ECO-10 — Capital and investment | Three implemented investment mechanisms, each with ≥10 native qualification cases | Define capacity change, financing source, depreciation/maintenance where modeled, and failure/loss; do not infer investment from renamed inventory |

The existing grain/bread work demonstrates protocol pieces and one productive recipe. It does not establish the multi-good, multi-day, autonomous economy targeted here. Economic complexity is described by connected mechanisms, dependency depth, participant diversity and adaptation to shocks—not a single unexplained score.

## M5 — Spatial behaviour and urban planning

Native positions establish where an actor was observed. Straight-line separation is not walkable distance; sampled movement is not proof of a complete navmesh route; package ownership is intention/execution control rather than measured displacement. Distances across unrelated cells/worldspaces must not be combined.

| Planned measure | Initial target and denominator | Qualification protocol |
| --- | --- | --- |
| PLAN-SPA-01 — Spatial observation coverage | ≥95% valid spatial samples for eligible loaded resident-seconds over three ≥30-minute sessions | Report sampling cadence, gaps, coordinate validity, space identity, unloading and pauses |
| PLAN-SPA-02 — Route completion and delay | ≥95% destination completion across ≥100 issued valid journeys, with travel-time p50/p95 | Separate pathfinding failure, congestion, interruptions and unavailable destinations; route efficiency needs a verified walkable baseline |
| PLAN-SPA-03 — Stuck detection | ≥95% detection and ≤5% false positives across ≥50 labelled stationary/trapped/action cases | Waiting, listening, work and rest are legitimate stationary states; preserve time-to-detection and recovery outcome |
| PLAN-SPA-04 — Destination usage | At least ten public destinations with measured visits and dwell coverage in a qualification scenario | Availability is scenario data; report concentration and unused sites without forcing residents to visit each site |
| PLAN-SPA-05 — Crowding measurement | ≥95% agreement within a declared tolerance across ≥50 labelled occupancy observations | Define place geometry/capacity, time window and counting rule; proximity alone is not social interaction |
| PLAN-URB-01 — Service access | Measure reachable food, work and rest access for ≥95% of eligible households in one configured town scenario | Use opening conditions, affordability/capabilities and verified routes; distinguish physical access from permission or funds |
| PLAN-URB-02 — Accessibility intervention | ≥30 matched trials for each of three interventions | Relocate/close a service, alter opening/capacity, or change a route; report travel burden, unmet need and economic displacement |
| PLAN-URB-03 — Distributional impact | Report medians, tails and subgroup coverage for access, spending and unmet need over ≥3 game days | Use explicit gameplay cohorts such as households/resources; missing accounts remain unknown; no unexplained fairness score |
| PLAN-URB-04 — Location economics | ≥30 matched trials of location/capacity differences with costs held explicit | Measure footfall, actual purchases, service queues, earnings and displacement; correlation does not establish causation |
| PLAN-URB-05 — Planning controls | Three reversible, save-bound policy interventions with ten reload/rollback cases each | Candidate controls: market opening/capacity, resource allocation and service permits; construction/navmesh editing remains a separate engine integration |

Policies should act on the same resources, routes and information that residents use. A Jarl-style control should create observable incentives and constraints, with costs and distributional effects. It should not secretly choose NPC dialogue or guarantee the policy succeeds.

## M6 — Watchable operation and reproducible evidence

| Planned measure | Initial target and denominator | Qualification protocol |
| --- | --- | --- |
| PLAN-OPS-01 — Movie usability | ≥95% relevant subjects visible/readable across ≥100 independently labelled shots | Include night, clutter, moving actors, transitions and two-person scenes; camera requests do not prove clear framing |
| PLAN-OPS-02 — Live data freshness | p95 displayed-data age ≤5 seconds over three ≥30-minute sessions | Show stale/disconnected state and observation age; never animate charts as if missing data were current |
| PLAN-OPS-03 — Bounded costs | 100% of inference attempts have a claim, configured budget and reconciled receipt status across ≥500 attempts | Report known cost and coverage; missing usage is unknown, not free; separate local synthesis from cloud inference |
| PLAN-OPS-04 — Persistence | 100% of declared state fields match across ≥30 save/resume/rollback cases | Include active goals, relationship changes, obligations, businesses and interrupted work; older-save restore removes later knowledge |
| PLAN-OPS-05 — Fault recovery | ≥50 provider/native/audio/service fault cases with zero duplicated economic effects | Report held work, cleanup and other residents' continuation; automatic retries need proven idempotency and an explicit budget |
| PLAN-OPS-06 — Sustained observation | Three two-hour sessions, then one eight-hour qualification session, before 24-hour qualification | Record throughput, failure rate, stale time, resource use, memory growth, cost and audit coverage; no public broadcast implied |
| PLAN-OPS-07 — Demonstration evidence | Three reproducible videos: ordinary conversation, an unforced economic chain, and a social consequence sequence | Each links timeline events, native audio/video, relevant metrics and build/configuration; generated infographics are labelled illustrations |
| PLAN-OPS-08 — Physical audio | ≥30 captured playback trials on the chosen output, with attribution and acoustic onset measurements | Native playback completion is a different measurement from audible speaker output; include missed/overlapping deliveries |

No continuous livestream or 24/7 automation has been launched by this plan. A future public stream needs a separate launch action after durable recovery, bounded costs, audio/camera quality and long-run evidence are qualified.

## Delivery order and exit conditions

1. **Extend qualified concurrent goals.** Preserve the repaired lease/receipt ordering and demonstrated movement alongside speech; qualify the new purposeful follow-through and stationary-work paths under unforced decisions, backlog, interruption and save/resume. Exit with a complete bounded native run and retained failures.
2. **Instrument before claiming depth.** Add save-aware activity/spatial time series, explicit sample coverage, data-driven targets and per-resident inspection. Exit with replayable evidence exports and tested missing-data/reload behaviour.
3. **Connect meaningful daily life.** Turn arrival into a new, state-informed opportunity for actual work, trade, rest or social interaction. Add commitment completion/breach records. Exit with unforced chains, truthful speech and observed consequences.
4. **Expand the economy and social mechanisms.** Add finite upstream supply, multi-stage production, enterprise accounting and causally linked disagreements/reconciliation. Exit against the relevant multi-trial acceptance protocols above.
5. **Add city interventions and sustained viewing.** Implement reversible policy controls, spatial/access experiments, clearer movie composition and reproducible recordings. Exit with qualified long-run sessions before attempting continuous broadcast.

These phases can have parallel implementation work, but later visual polish or a larger option count cannot waive an earlier accounting, identity, execution or evidence failure. The [development plan](development-plan.md) records implementation milestones; [Society OKRs](society-okrs.md) distinguishes the current executable scorecard from this planned programme.

## Current integrated slice and remaining gates

The current slice implements meaningful review purposes, review-source propagation, overdue-first/bounded-follow-up dispatch, and per-run frozen inference budgets. New sample/play policies allow 192/768 personal calls respectively, with 600/3,600-second scheduling windows and five-second due reviews. These settings are explicit data and their actual resolved values are hashed into each run. Increasing a budget does not establish improved behaviour; cost, completion, delay and observed consequences must still be compared.

Stationary owner work now has native fixture evidence: zero model calls, ten credited game minutes, gold 102 → 102, bread 4 → 6, grain 20 → 19, followed by the original journey resuming. It qualifies attendance and effects for that authored case; it does not qualify autonomous production choice, a workplace/animation, profitability or an unforced supply chain. The integrated test baseline is 501 Python tests, five later focused integration checks and 204 JavaScript tests passing.

Native RTS input remains a separate unresolved gate. Automatic policy review blocked the offline toolchain-layout action before execution, so the native input rebuild is unbuilt. The full society, reliable native controls, long-run autonomy, richer economic/social mechanisms and continuous-broadcast qualification remain active work rather than achieved outcomes.


## Integrated evidence update

The first lease and acknowledgement failures are retained alongside their repairs. The repaired three-event native run completed a meal and a four-line conversation with up to 15 residents moving during playback; 44 personal decisions yielded 41 accepted journey arrivals. A rejected time-of-day greeting released cleanly, and three unavailable-resident results were not applied. See [full denominators, chart, receipts and 17-field save verification](personal-goals.md). This qualifies a bounded integration slice; it does not close the remaining programme milestones.
