# Paid employment v2: labour, output and wages

Paid employment needs evidence of both a completed production job and payment to its worker. Work attendance, input consumption, output creation, wage transfer and release are separate outcomes. A model agreeing to a shift, an actor standing nearby or inventories resembling a final state cannot substitute for those observations.

**This replacement is implemented in source. It is not installed or qualified in Skyrim.** The [legacy execution gate](paid-employment-protocol.md) remains a separate compatibility boundary; historical completed jobs do not qualify the replacement, and unfinished old effects cannot be replayed under a new protocol label. Focused offline evidence below does not substitute for final integrated/hosted validation or a native acceptance trial.

## What must be agreed and observed

The worker and employer must agree to the same explicit recipe, configured batch quantities, duration and wage. Resident consent is distinct from an operator-authored fixture. A contract pins the participants' actor/base identities, business revision, recipe/catalog definition and the provenance of offer and acceptance. A generic recipe identifier is not permission for a language model to supply native form IDs or arbitrary inventory deltas. Generic selection still uses the current one-input/one-output catalog schema; it does not enable new commodities or recipes by itself.

The opportunity builder requires an observed protocol-2 paid-employment capability, current catalog proof and qualified worker/employer identities. It derives jobs from an active business's registered recipe capabilities, the employer's own valid recipe knowledge, complete observed inventories and its authored production policy. Required inputs, wage funding, worker currency capacity and the output target bound each option. A funded opportunity is not consent or a reserved job. The worker need not already know the recipe merely to be offered supervised work; verified learning remains a later consequence.

`validate_paid_consent` requires one exact employer `offer_shift` decision followed by one distinct worker `take_shift` decision, both from saved claims with the same current session and terms hash. Voiced employment also requires separate delivered offer and acceptance turns in that order, the exact speaker/listener pair and terms hash, ended playback and `nearbyThroughout: true`. A generated sentence or a claimed action missing its option/claim provenance cannot replace these witnesses. Final consent is hashed separately from the terms.

Attendance must belong to that exact contract and physical lease. Qualified time excludes travel, pause, unloaded intervals, clock discontinuities and loss of required attendance. Neither a standing worker nor elapsed wall time proves labour. Attendance also does not establish access to an oven, forge or smelter; station-dependent work needs its own verified capability.

Production and payment must be serialized through the effect pipeline. Input removal, output addition and employer-to-worker wage transfer each need their own issued-before-call evidence and exact observed deltas. Currency payment must be observed on both purses. Keep unrelated catalog balances intact. The complete contract outcome must distinguish created output from paid wages, including partial or unresolved effects.

The native source uses four ordered effect legs for the current recipe schema: employer input removal, employer output addition, employer wage debit, then worker wage credit. Each call is marked issued before crossing the native boundary; the complete two-account stage must be observed before issuing the next leg. This permits visible intermediate states, including output with no wages and a wage debit awaiting credit. It is not an atomic inventory operation. The controller does not resend an issued leg after an error or ambiguous observation.

Hired-worker attendance owns an exact existing Citizens slot, package, request/acknowledgement serial, self-target, anchor and cell. Both participants' native base identities remain bound. Qualified worker samples use game time under that lease, not a claim that the employer also performed labour. Output, wage debit, completed wages, effect completion and release have distinct native flags. A working animation or valid workstation is not established by this stationary protocol.

## Native command and receipt contract

The source controller has separate `paid_work_start`, `inventory_paid_work_commit` and `paid_work_ack_receipt` commands. The immutable identity includes protocol/job, worker/employer references and bases, slot, session/epoch, business/revision, recipe/catalog hashes, terms/consent hashes, work duration, wage/currency, package, anchor/cell and complete before/after accounts. A start acknowledgement accepts the assignment; it does not certify attendance or production.

After qualified attendance, the controller provides a bounded live attendance token for a single settlement command. The service must persist that permit before inventory effects. Each effect leg contains its item, role, amount, issued/observed witnesses and complete expected before/after accounts. A leg is observed only when the whole current stage matches; unchanged accounts can wait within the bounded observation interval, while drift or expiry holds execution.

Receipts distinguish `output_verified`, `wage_debit_verified`, `wages_verified`, `effects_verified`, `release_verified` and `effects_issued`. `effects_issued: null` means the controller lacks adequate surviving evidence; it is not equivalent to no effects. `no_effects_issued` can only be true from a live record that knows no call was issued. Output alone does not establish wages, and a wage debit alone does not establish worker receipt. The final native acknowledgement removes retained controller state only under the receipt/release checks; unrelated acknowledgement IDs cannot release this job.

## Saved jobs and settlement order

The service persists `paid_work_jobs` with the source plan, exact consent/terms, recipe definition, current accounts and native assignment identity. Delegation requires verified release of the preceding travel task and reserves both participants, their accounts, the business and the worker's slot. The source plan becomes delegated so unrelated residents can progress while this worker attends; one worker's long shift is not a foreground model call.

An attendance receipt is checkpointed before settlement preparation. The service then rechecks current consent, charter, identities, catalog, attendance token and reserved stock, and writes `inventory_paid_work_commit` into the single pending effect lane. Preparation waits for an available command/checkpoint lane; attendance alone never writes output or wages. A new inference or an earlier stock snapshot is not authority to bypass those checks.

The effect observer compares the frozen command, exact ordered leg witnesses and independently observed complete accounts. A valid all-leg result records committed physical production and payment separately from final contract completion. Full completion additionally needs a valid terminal receipt and verified native release. Only then does the service finish the source plan, record the participants' paid-employment memories and teach the worker the exact recipe through verified production provenance. Retained authored priors remain separate.

Account/activity reservations remain until the terminal receipt is acknowledged, release is verified and no unresolved effect remains. This excludes the **employer as well as the worker** from competing activity/account use until acknowledgement; the employer is not free merely because the worker has finished attendance. A known no-effect rejection can follow its bounded cleanup path only with the exact live attestation and unchanged accounts. Unknown or partial effects keep their reconciliation hold. Service checkpoints preserve the evidence and cannot recreate a lost native issued-call journal.

## Recovery and historical evidence

An uncertain effect holds the relevant accounts and activity reservations until explicit reconciliation establishes what occurred and what was released. A partially completed job must not be labelled paid, completed or cancelled without the required evidence. Do not infer an issued native call from matching balances or infer no effect merely from a missing acknowledgement.

Cold controller loss is not permission to resend effects, compensate automatically or adopt an unknown existing native task. Persisted service intent and receipts are different from a crash-durable native effect journal. Without that stronger journal, no exactly-once-across-crashes claim is justified. Historical records remain readable with their original protocol and evidence scope.

Recipe learning must preserve its source. An authored livelihood prior remains an authored prior; verified production participation needs the qualified completed protocol result. Neither an offer nor a partial output observation creates a completed-work memory or silently upgrades a starting skill to verified learning.

## Quantitative acceptance

These measurement definitions specify the evidence to collect. They are not current passing values, economic realism ratings or a requirement that residents accept every job. Use a fixed observation window and include build/configuration hashes, protocol, session and source mode. Report numerator and denominator, with no denominator represented as unavailable. Retain rejected, held and incomplete cases.

The current read-only projection, `paid-employment-metrics-v2`, reports offered, accepted, qualified-attendance, output, wages, completed, released and held stages separately. Each stage has `success`, assessed sample count `n`, `unknown` and `percent`; `n` excludes unknown proof. This is a retained-job sample, not the denominator of all offered opportunities or all residents. Conversion rates use a separate `eligible` count and remain null when any eligible outcome lacks evidence. Opportunity eligibility is not yet journalled and remains null. There is no overall progress or realism score.

The projection keeps partial observed output, wage debit without verified credit, and verified wages without a committed production record separate from committed goods and wages. It excludes duplicate/conflicting job lineages from credit and exposes invalid/legacy records. Latency distributions report game minutes and wall-clock seconds independently, with missing/reversed clocks unknown; those elapsed intervals can include queues and pauses. Saved retained evidence is not lifetime town throughput or a fresh native capability observation.

In particular, saved `accepted_at`/`accepted_day` timestamps denote **native job admission**, not the earlier worker's agreement. The projection labels these intervals `native_admission_to_attendance` and `native_admission_to_completion`; its other intervals are attendance-to-output, output-to-wages and wages-to-release. Do not interpret them as consent latency, reply latency or uninterrupted productive time. Authored controller fixtures remain labelled as fixtures even when every stage verifies.

| Measure | Numerator / denominator | Required distinction |
| --- | --- | --- |
| Feasible paid-work opportunity coverage | Eligible resident reviews exposing at least one valid paid-work option / all eligible resident reviews | Explain exclusions for identity, knowledge, stock, funds, access, reservations or unavailable executor. An option is not a job. |
| Explicit agreement | Contracts with matching offer and acceptance evidence / admitted contract attempts | Separate worker/employer refusal, changed terms and operator fixtures. No forced acceptance rate. |
| Qualified attendance | Jobs reaching their exact qualified attendance requirement / admitted work jobs | Publish qualified and excluded game-time intervals; wall time and nearby idle time are separate. |
| Witnessed input debit | Jobs with the complete expected issued-and-observed input debit / effect-admitted jobs | A debit can exist before output or payment; do not count it as successful production. |
| Witnessed output creation | Jobs with the complete expected issued-and-observed output credit / effect-admitted jobs | Report physical output even when wages later remain unresolved; incomplete contract status remains visible. |
| Bilateral wage payment | Jobs with witnessed employer debit and worker credit for the agreed wage / wage-leg admissions | Also report paid jobs / all accepted jobs so delayed or blocked wage admission cannot disappear from the denominator. |
| Qualified contract completion | Jobs with valid attendance, all required effect witnesses and accepted terminal settlement / admitted work jobs | Retain partial effects and held jobs. A coincidental final account is not a witness. |
| Verified release | Terminal jobs whose exact activity/lease release is verified / terminal jobs requiring release | Keep release unknown distinct from released. Completion of inventory effects alone does not free a native slot. |
| Duplicate consequence prevention | Duplicate or replay attempts causing no new output, wage or learning / all exercised duplicate/replay attempts | Include crash/reset ambiguity as held cases; passing same-process duplicates is not a crash durability guarantee. |

For each admitted job, retain one lineage from opportunity and consent through attendance, permit, each physical leg, terminal receipt, settlement, memory and release. Record latency per transition and time spent held. Avoid summing unrelated recipe quantities into one throughput score: report units by commodity and wages by currency. Production value, profit and GDP need separate valuation/costing definitions; a wage transfer is not itself new economic output.

## Source qualification

[Hosted run 40208269941](https://github.com/45ck/whiterun-society/actions/runs/40208269941) passed on Windows and Ubuntu at revision `d8361c4`. Each platform ran 1,236 Python tests (1,235 passed, one generated-file check initially skipped and subsequently passed), 488 JavaScript tests and six generated-plugin readback tests. Windows compiled both Papyrus scripts. [Exact revision, suite evidence and limitations](evidence/paid-employment-validation.json).

Six interoperability cases exercise the actual JavaScript paid/trade controllers and Python checkpoints with simulated native actor/form APIs: witnessed work and later spending of earned wages; partial unpaid output; reset after input debit; identity replacement; cold controller loss; and rejected admission without retry. Metrics are checked against those actual controller receipts. Five Agency tests separately exercise the real decision path, including refusal and privacy, with authored model choices. These suites are included in the full counts, not added to them. No live model, audible game speech, crafting animation or native economic outcome is proved by this run.

![Offers, consent, attendance, production, wages and consequences](images/paid-employment-cycle.png)

Generated system illustration, not gameplay. Its pictured goods are conceptual; [full prompt and limits](images/paid-employment-cycle.prompt.md).

The generic path remains limited to the reviewed **one-input/one-output recipe schema** and one configured batch per job. Renamed test commodities and a synthetic recipe exercise data generality; they do not activate another production chain in Skyrim. Station access, productive animation, multi-input/output recipes, negotiated wage policy and sustained unforced employment remain separate qualification or implementation work.

## Native qualification to perform

A controlled native fixture must prove the exact recipe and agreed wage with unchanged unrelated balances, independent attendance evidence, witnessed input/output effects, both sides of wage payment and verified release. Preserve the authored origin. A separate unforced resident encounter must show the feasible opportunity, genuine offer/acceptance or refusal, delivered exact terms and the resulting physical outcome.

Exercise session/base replacement, stale contracts, recipe/business revisions, lost and duplicate acknowledgements, delayed debit/credit observations, foreign inventory changes, exceptions after effects, partial output with unpaid wages, controller loss and old-save restoration. Every failure must preserve observable partial effects and avoid blind replay. Record source tests separately from these game trials; neither a fake native API nor a generated diagram is gameplay evidence.

Related: [legacy paid-work boundary](paid-employment-protocol.md), [independent owner work](independent-owner-work.md), [configured recipes](economy-catalog.md), [starting recipe knowledge](livelihood-backgrounds.md), [witnessed market exchange](generic-procurement.md).
