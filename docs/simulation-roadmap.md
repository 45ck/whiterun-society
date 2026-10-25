# Living city programme and quantitative acceptance plan

Updated 26 October 2026. This is the active implementation programme for a **movie-first, RTS-only** economy and social simulation inside Skyrim. It is a plan for work and experiments, not a claim that the full society exists. The executable scorecard is documented in [Society OKRs](society-okrs.md); this page also specifies measurements that still need implementation.

The desired experience is a town whose residents pursue their own changing goals while the viewer watches conversations, work, trade, relationships and consequences. All eligible residents can hold and execute goals concurrently. Model inference happens when a decision is due or a meaningful stimulus warrants reconsideration. Walking, animation, accounting, perception sampling and valid action execution continue through deterministic and native code. Continuous thought is represented by continuing state, goals and attention; a queued inference is not active reasoning.

## Current source milestones and integration boundaries

Revision `9ef9476` implements fresh bootstrap with empty people, a historical inventory snapshot, then explicit census using one seeded policy for observed adults. Existing saved profiles, memories and trust remain intact. New ordinary conversation requests require a nonempty census; explicit authored scenarios freeze participants, turn limit, provenance and definition hash through a separate API. Ordinary pairing/consent remains agent-selected; an authored scenario starts its directed meeting without claiming that choice. Invalid saved identity or ambiguous release holds the affected reservations. These changes are **source-implemented and not installed or in-game qualified**. [Contracts and mode boundaries](conversation-scenarios.md) · [Population evidence](population.md).

The [exact-revision hosted validation record](evidence/population-scenario-validation.json) reports Windows and Ubuntu passing independently: 832 Python tests per platform (831 passed, one generated-artifact check initially skipped and later passed during readback), 300 JavaScript tests and six plugin readback checks. This verifies source/build behavior rather than native interaction or any planned programme score.

Current catalogue/owner-work source supports validated single-input/single-output recipes and complete-account receipt checks. The default remains the authored bread recipe; iron metadata does not activate smelting. Finite founding resources now use a reviewed manifest with uniform 20 gold/2 bread/2 grain grants, optional explicit actor/base overrides and a fixed 1,000/100/100 pool. The source engine no longer branches on a named founding recipient. Saved available/reserved/delivered accounting, effect-free arm and a persisted permit precede witnessed delivery. Native effects remain live-witnessed, not crash-durable; ambiguity holds reservations rather than replaying. [Resource contract](founding-resources.md). No native installation/qualification of this replacement is claimed.

Generic trade/procurement is also source-implemented: explicit public goods, known-recipe input demand, quantity alternatives, exact voiced terms and two-account goods/payment witnesses. The synthetic three-test cycle includes five units of fixture-only ore for 15 gold using the actual JavaScript controller with fake native actor APIs; it proves neither an installed fourth commodity nor metal production. [Procurement contract and evidence limits](generic-procurement.md). The former context overflow now has a source repair: staged `purchase_select` groups retain the full frozen choice set, with at most six alternatives per leaf, eight branches and 16 navigation/selection decisions separate from the unchanged six economic decisions. The final offline 18-resident/17-supplier fixture reached all 68 alternatives across 44 nodes plus the overview; contexts peaked at 8,186 bytes under the unchanged 12,000-byte bound, with at most three navigation/selection calls to any leaf after initial inspection. Seven purchase-attention and three worker tests passed. That graph traversal is not a single model event or native qualification. Model selection cost/latency, budget exhaustion and larger-market behavior still need evidence.

Further source milestones now include [optional authored livelihood backgrounds](livelihood-backgrounds.md), [generic paid-employment v2](paid-employment-v2.md) and [employer movement/social activity during paid attendance](employment-concurrency.md). Authored recipe priors remain distinct from receipt-backed learning. Paid jobs require separate consent, attendance, input/output and wage witnesses; physical employer freedom does not release either financial account. Their linked exact-revision validation and native-qualification limits remain authoritative; earlier gameplay trials do not qualify these later migrations.

The current source-implemented milestone is [independent reviews and purposeful follow-through](independent-followthrough.md): separate decision claims/plans for disjoint residents to delegate rest or owner work while an unrelated foreground encounter continues, sharing the worker's full model budget and one inventory writer. Four offline controller/service integration cases passed. Their positive fixture retained a foreground conversation at proposal after route admission, with no spoken turn; independent rest settled, and owner production waited for foreground release. Actual controllers used mocked game APIs and authored choices. Hosted full-suite qualification is pending, and this is not a native acceptance result. Source generality, historical controlled bread/grain trials and new native qualification remain separate claims. Catalog-v2 multi-input/output effects, actual workstation access, upstream replenishment, distinct business accounts, broader learning mechanisms and spoken bilateral commitments remain future work. Recipe registration does not bootstrap resident knowledge. The full movie-first, RTS-only society goal is active; none of these source milestones establishes all-resident autonomy or a complete economy.

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

## Next state-driven integration cases

These are **new planned acceptance cases**, not executable dashboard scores or completed trials. Freeze software/configuration and the starting save before each case. Record every attempted admission and failed outcome; separate source tests, controlled native mechanics and unforced model decisions. Use the existing `PLAN-*` programme for longer-run claims rather than treating this smaller integration gate as full acceptance.

| Next case | Concrete work and initial quantitative gate | Required evidence and interpretation |
| --- | --- | --- |
| Fresh population and encounter migration | Run at least 12 controlled cases covering fresh bootstrap, two different censuses, added/absent/replaced residents, ordinary no-census rejection, authored definition changes, duplicates and old-save recovery. Require zero unintended profile resets, stock deltas or private-knowledge grants in all 12. | Save snapshots and differences, request source mode, observed identities, admission/rejection reason, provider attempt count and cleanup evidence. Test passing does not establish native speech. |
| Finite resources as scenario data | Frozen definitions, durable reservations/permits/terminal receipts and live native leg witnesses are now implemented in source. The focused service suite includes 43 fault cases; native qualification remains pending. Run at least 30 controlled replay, partial-delivery, exhausted-pool, changed-definition and actor-replacement cases with zero duplicate imports and exact available/reserved/settled reconciliation. | [Resource protocol and evidence limits](founding-resources.md). Pin scenario/catalog digests and source identity. Matching final inventory alone cannot prove delivery. Native witnesses are not crash-durable: uncertainty retains reservations without replay. Preserve legacy receipts; a new scenario cannot refill an old program. Source tests do not qualify these game trials. |
| Independent owner production | Qualify two disjoint owner jobs while a third disjoint pair speaks, with at least 10 cumulative seconds of verified overlapping attendance and delivered playback. Across at least 10 terminal admitted owner jobs, require exact configured input/output deltas, unchanged other balances and zero duplicated effects; report completed and held jobs separately. | Native identity, lease/attendance, mutation-lane queue time, before/intermediate/after accounts, receipt and release. Keep the default bread recipe for the initial controlled case. At least 30 fault/replay cases must produce zero unverified output. A held job is not production, and attendance is not workstation animation. |
| Independent review admission beside a foreground encounter | First qualify a controlled four-resident case: a foreground pair continues while two disjoint residents review and delegate one rest and one owner job. Then retain at least 30 eligible review outcomes across three bounded sessions, including deferral, foreground handback and holds. Require every delegated job to retain its exact claim/source plan and zero unverified duplicate consequences. | [Claim and source-plan contract](independent-followthrough.md). Separate queue delay, inference, admission, paired physical overlap and settlement delay. The shared call budget must account for all attempts. Foreground command and inventory ownership remain serialized; source tests do not qualify a native run. |
| Ordinary social choices | Collect at least 30 offered or scheduled opportunities across three bounded sessions with a changing roster. Attribute 100% to an explicit source and terminal/held state; retain defer, refusal, acceptance, interrupted delivery and no-candidate outcomes without requiring a chat rate. | Pair selection, knowledge view, meeting receipt, delivered turns, timing and cleanup. Record provider calls and audible capture separately. Use `PLAN-SOC-01` only after its 100-reply minimum; do not rate human realism from this small pilot. |
| State-linked economic follow-through | Across at least 30 eligible need/stock/commitment reviews, retain the full option set, choice and later effect/refusal/hold. Then qualify repeated unforced procurement → production → consensual sale → consumption chains; target at least three completed chains across at least three residents and report all attempted chains. | Link stimulus, plan, charter/recipe versions, knowledge source and exact transaction receipts. No forced success, free replenishment or selective omission of refused offers. Three chains are an integration milestone, not equilibrium, profitability or the broader M4 acceptance. |

Movie-first RTS presentation must show which phase is intended, travelling, attending, speaking, settling or held. Record actors out of view and unknown observations, rather than filling the gaps with animation. Public broadcasting and native installation are not implied by these planned experiments.

## Delivery order and exit conditions

1. **Qualify the source migrations and independent activity integration.** Two independent seated breaks plus a disjoint authored voice encounter passed the cumulative native overlap target in C2; C1's autonomous refusal did not. Preserve that evidence while qualifying the new empty-bootstrap/census/scenario boundaries and catalog-bound owner-work lifecycle. Next qualify rest with a meal/trade, overlapping owner attendance, interrupted active-job recovery, unforced choices and measured queue fairness.
2. **Instrument before claiming depth.** Add save-aware activity/spatial time series, explicit sample coverage, data-driven targets and per-resident inspection. Exit with replayable evidence exports and tested missing-data/reload behaviour.
3. **Connect meaningful daily life.** Turn arrival into a new, state-informed opportunity for actual work, trade, rest or social interaction. Add commitment completion/breach records. Exit with unforced chains, truthful speech and observed consequences.
4. **Expand the economy and social mechanisms.** Add finite upstream supply, multi-stage production, enterprise accounting and causally linked disagreements/reconciliation. Exit against the relevant multi-trial acceptance protocols above.
5. **Add city interventions and sustained viewing.** Implement reversible policy controls, spatial/access experiments, clearer movie composition and reproducible recordings. Exit with qualified long-run sessions before attempting continuous broadcast.

These phases can have parallel implementation work, but later visual polish or a larger option count cannot waive an earlier accounting, identity, execution or evidence failure. The [development plan](development-plan.md) records implementation milestones; [Society OKRs](society-okrs.md) distinguishes the current executable scorecard from this planned programme.

Two substantive follow-up audits are saved in [independent follow-through](independent-followthrough.md#next-work-audit-catalog-v2-and-variable-recipe-legs). Catalog v2 needs bounded multi-input/output definitions, variable-leg owner journals, verification of every paid output before wages/completion, and explicit stock-target/batch-demand policy. Enlarging the JSON alone cannot deliver that migration. [Spoken bilateral commitments](independent-followthrough.md#next-work-audit-spoken-bilateral-commitments) need heard matching proposals/acceptances, due-condition and cancellation semantics, receipt-backed fulfilment, unresolved/breach handling and private knowledge boundaries. Current conversation follow-ups queue a person's own review; they are not that agreement lifecycle. Neither audit is implemented by this milestone.

## Current integrated slice and remaining gates

The current slice implements meaningful review purposes, review-source propagation, overdue-first/bounded-follow-up dispatch, and per-run frozen inference budgets. New sample/play policies allow 192/768 personal calls respectively, with 600/3,600-second scheduling windows and five-second due reviews. These settings are explicit data and their actual resolved values are hashed into each run. Increasing a budget does not establish improved behaviour; cost, completion, delay and observed consequences must still be compared.

Stationary owner work has historical native fixture evidence: zero model calls, ten credited game minutes, gold 102 → 102, bread 4 → 6, grain 20 → 19, followed by the original journey resuming. It qualifies attendance and effects for that authored case; it does not qualify the later catalog-bound concurrent work implementation, autonomous production choice, a workplace/animation, profitability or an unforced supply chain. That earlier integrated test baseline was 501 Python tests, five later focused integration checks and 204 JavaScript tests; it is not a count for the latest revision.

Native RTS input remains a separate unresolved gate. Hosted run `40191256470` compiled the unchanged baseline and a separately reviewed saving/focus/mouse-routing candidate, passed 159 C++ policy checks, and produced two DLL/PDB pairs whose debug signatures matched in read-only verification. The candidate includes proposed source fixes; both artifacts remain `compiled-unqualified`, with neither local execution nor deployment and no verified native input/save behavior. [Build evidence](native-ui-build.md). The full society, reliable native controls, long-run autonomy, richer economic/social mechanisms and continuous-broadcast qualification remain active work rather than achieved outcomes.

## Concurrent self-care — implemented slice and remaining gates

The motivating live run exposed a bottleneck beyond model-call capacity. A 30-game-minute seated break occupied roughly 150 wall seconds while about 25 overdue reviews remained queued. Personal goals could still be chosen and journeys could finish, but meaningful follow-up actions waited behind the single foreground action. These were diagnostic observations, not a completed long-run benchmark. Valid rest is purposeful stationary activity; preventing unrelated residents from acting throughout that rest was the execution limitation addressed by this slice.

Previously, `Rest.plan_rest` stored the full rest in `active['pending']`, and the worker waited for terminal attendance. When the two-slot capability is available, it now delegates to `ActivityJobs`: `activity_start_rest` acknowledges admission promptly, two native controllers tick independently, and `activity_ack_receipt` frees durable completed/held leases after verified release. The old foreground path remains the compatibility fallback without that capability. Conversations and inventory mutations still use one foreground pipeline.

### Qualified mechanism; autonomous and economic gates remain

The implemented slice supports **two independent rest jobs at distinct observed benches while a disjoint foreground event progresses**. C2 used authored rest choices and four authored local Kokoro turns, with zero cloud calls. It verified **28.359 cumulative seconds** of two-seat/voice overlap against a **10-second cumulative target**; the longest continuous interval was **7.375 seconds**. Both rests completed and released. C1 retained its zero-overlap autonomous brief refusal. [Native evidence, actual screenshots and limits](concurrent-activities.md) · [C2 compact receipt](concurrent-rest-controlled-trial.json).

An accepted rest decision hands off to a saved background job without becoming completed merely to free the foreground slot. The worker returns `delegated` only after committed native admission; the daily event stays `started` until completion or hold. The director can schedule another eligible resident during attendance. This mechanism is implemented; a measured multi-run reduction in backlog and starvation is not yet qualified.

This handoff is necessary for correctness: simply starting several current `run_resident_event.py` processes would race the singleton plan, pending command, native rest controller and state writes.

### Implemented saved state and ownership

The actual first-slice schema uses derived reservations rather than separate actor/place tables:

| Record | Minimum fields | Owner and invariant |
| --- | --- | --- |
| `activity_jobs[job_id]` | Actor/reference identity, `source_plan`, session, epoch, slot, target, policy snapshot, saved phase, receipt/hash and release/ack flags | Service owns checkpoint writes. Saved phases are prepared, running, complete and held; detailed travel/rest/release phases come from native telemetry. |
| Derived actor/seat/slot leases | Unacknowledged saved jobs and current native jobs/receipts | One owner per actor, seat and slot. Terminal or held work remains reserved until release and durable acknowledgement. |
| `activity_orphans[identity_hash]` | Original native identity, held receipt/hash, release proof, acknowledgement, `recovery_applied=false` | Reconcile native work absent from an older saved lineage without importing future fatigue, memory or intention. |
| Existing plan list | Latest foreground-compatible plan, with delegated source plans retained by ID | `agency_busy` excludes delegated plans. Completion updates the original `source_plan`, preserving newer plans; no new foreground-pointer field was introduced. |
| Job receipt plus `rests` and memory records | Receipt hash, before/after fatigue, source identity and clocks | At most one recovery application per saved job. Arrival or elapsed wall time alone cannot grant recovery. |

The later source extension adds `independent_reviews`, `independent_review_waves` and `independent_plans` without replacing that foreground list. Exact event/claim/plan hashes authorize disjoint rest or owner-work delegation; source lookup spans both plan stores and rejects ambiguous IDs. One shared background worker and call budget schedule goal/review waves, while native effects still settle through the single writer. This new [independent follow-through contract](independent-followthrough.md) is distinct from the historical C2 rest/voice evidence above.

Admission atomically reserves the actor, native rest slot and seat at one checkpoint. A conflict rejects or defers the whole reservation; it must not acquire half the resources. Foreground social/economic selection, personal-goal claims and other background admission consult the same actor-lease registry. Multi-person encounters acquire their participant set atomically and revalidate availability at the relevant decision boundary. They must not select an actor already resting or working.

Expiry is a request to release and reconcile, not proof that a native task stopped. A held job with unverified release retains a visible quarantined actor/seat lease. Unrelated residents can continue if no shared resource or unresolved inventory effect conflicts. Do not clear a reservation merely because its worker exited or a timer elapsed.

### Native transport and execution contract

`WhiterunActivities.esp` adds two independent furniture-routing slots with distinct offsets, quests/mailboxes and controller state. Existing plugin identities were preserved. BX restored 17/17 compared fields with the append allowed; settled-job save BY restored 18/18 including activity history. These checks do not prove active-job save/load recovery. Capability telemetry advertises availability and capacity; the stored rest policy is versioned.

Implemented transport commands are **`activity_start_rest`** and **`activity_ack_receipt`**, carrying the immutable assignment identity, bounded rest duration and admission checkpoint. Acknowledging an old-session receipt carries current command session plus original `job_session`. Cancellation is internal to the native controller on session/assignment/freshness loss; a public `activity_cancel` command and arbitrary activity kinds are not implemented.

- `activity_start_rest` validates the saved reservation and native capabilities, installs a finite task and promptly acknowledges **accepted**, without holding the command channel for the full rest. Exact furniture arrival and 30 minutes of qualified attendance remain later milestones.
- A per-slot native controller ticks every frame independently of whichever foreground command is active. It verifies owned package, exact furniture reference, seated state, native time, session, slot and lease. It never accumulates rest during travel, pause, unloaded time, a clock jump or lost attendance.
- Each heartbeat reports `activity_jobs.jobs` progress and `activity_jobs.receipts`. Completed/held receipts remain available until the service acknowledges durable settlement. One chat acknowledgement cannot overwrite a rest completion, and one rest completion cannot replace another's receipt. The public saved projection retains leased jobs plus up to 32 acknowledged history rows.
- Cancellation releases only the job's own native slot. The terminal receipt distinguishes stopped activity, verified release, earned attendance and any unresolved native ownership. Repeated starts or cancellations with the same immutable identity are idempotent; conflicting reuse is rejected.

Checkpoint equality is required when admitting a new start/effect. An already admitted, non-mutating attendance job must continue through unrelated checkpoint changes in the same valid session and lease epoch; otherwise every conversation memory write would interrupt rest. Session changes and explicit cancellation invalidate it. Native heartbeat freshness remains bounded, with a stop/release response when the supervising service disappears.

### Serialize commits, not attendance or inference waits

Keep one authoritative checkpoint writer and one native inventory-mutation lane. Long physical attendance and provider waiting happen outside those critical sections. The service collects terminal activity receipts, validates them, and commits each fatigue/memory result against the latest state in a short checkpoint transition. Other native jobs keep their already validated leases during that transition.

For rest, reuse the existing exact-furniture, released-package, seated-sample and elapsed-game-time checks. Compute fatigue evolution/recovery using the current person's clocks and the receipt's qualified interval, then append one settlement/memory. If another state change makes reconciliation unsafe, hold that job with evidence instead of overwriting newer state. Do not store a many-minute rest in `active['pending']`.

The same lifecycle is now implemented in source for **independent stationary owner-work attendance**, with native qualification still pending. Work time can progress concurrently, but production starts its inventory effect only after fresh input/account validation and mutation-lane admission. Reserve inputs or revalidate them before use; a model's earlier stock observation is not a reservation. Serialize input/output effects through the receipt protocol. Neither added work slots nor generic recipe definitions permit parallel inventory writers or duplicate the historical single-owner recipe effect. [Owner-work contract](independent-owner-work.md) · [Catalog identity and quantities](economy-catalog.md).

### Failure, save and restart behaviour

The first slice should choose conservative, explicit recovery over inferred progress. Loading another save follows its saved marker, discards future-session progress/receipts and releases obsolete native slots. Reloading or restarting during an active rest may hold it with **no unverified recovery**, then verify release; automatic resumption of the remaining duration is a later feature unless native save-bound elapsed progress can be independently reconciled.

A terminal receipt received before a checkpoint finishes stays in the inbox. If the service restarts after committing recovery but before acknowledging the native receipt, the settlement ID/receipt hash prevents a second recovery. Preserve unresolved receipts and leases until reconciliation is visible. Stop/deadline controls stop new admissions immediately, then settle or explicitly cancel the already accepted jobs under their bounded lifecycle; report which jobs remain active or held.

### Implemented modules and remaining test gates

| Work package | Likely modules | Minimum gate before integration |
| --- | --- | --- |
| Saved job lifecycle and reservations | `activity_jobs.py`, `activity_leases.py`, `rest.py`, `agency.py`, `lineage.py` | Atomic actor/seat/slot ownership, delegated foreground detachment, legacy-save defaults and idempotent settlement |
| Native parallel attendance | `bridge/rest.js`, `bridge/papyrus-router.js`, bridge command dispatch and plugin builder | Two independent slots; start acknowledgement separate from completion; per-slot release; receipt retention and epoch checks |
| Scheduling and inference | `tools/run_daily_life.py`, resident worker, goal scheduler and admission endpoints | Delegated events remain started; fair admission continues without blocking on attendance; all model claims retain shared budget accounting |
| Observation and UI | Dashboard/observer metrics and activity inspector | Running physical jobs, queued reviews, actively inferring actors, settlement waits, reservations and held releases shown separately |
| Native qualification | Isolated lab fixtures and evidence exporter | Two rests plus one disjoint foreground event overlap, exact recovery once, unchanged unrelated accounts, and save/reload/replay failures retained |

Required regression cases include two actors choosing the same bench; a speaker also proposed for rest; native occupancy changing after reservation; stale or replaced actor identity; one job timing out while the other succeeds; two terminal receipts arriving during one checkpoint; duplicate/lost acknowledgements; old-session receipts; pause/unload/clock jumps; provider failure before admission; and stop/budget exhaustion with accepted jobs still running. Add mutation tests proving that a rejected or incomplete rest grants zero fatigue recovery and that a replayed completion cannot grant it twice.

The first native acceptance case used four disjoint residents: two on two benches plus two speakers. C2 passed ten cumulative seconds of simultaneous verified seated attendance and subsequently completed voice playback. It did not pass or claim ten continuous seconds. A separate native case must still overlap rest with a meal or consented trade and verify exact inventories. Count resting residents as active self-care even though their displacement is near zero.

Before claiming the queue bottleneck is repaired, compare a controlled backlog with the previous serialized protocol: record admission-to-start time, maximum/median pending age, overdue resident count, active physical job count, purpose-to-effect completion, per-actor starvation and all failures. The target is that unrelated eligible work can start and finish during the long break—not that all residents move constantly or that a faster chart hides missing outcomes. Repeated unforced runs and larger-capacity qualification follow the small native slice; they are not yet implemented or proven.


## Integrated evidence update

The first lease and acknowledgement failures are retained alongside their repairs. The repaired three-event native run completed a meal and a four-line conversation with up to 15 residents moving during playback; 44 personal decisions yielded 41 accepted journey arrivals. A rejected time-of-day greeting released cleanly, and three unavailable-resident results were not applied. See [full denominators, chart, receipts and 17-field save verification](personal-goals.md). This qualifies a bounded integration slice; it does not close the remaining programme milestones.
