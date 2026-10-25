# Optional livelihood backgrounds and observed identity

This slice adds an explicit way to author starting recipe knowledge for a scenario without assigning occupations by NPC name. It also distinguishes saved population records from residents whose current observed identity is qualified. **The contracts below are implemented in source; they are not installed or qualified in Skyrim.** Focused automated evidence is distinct from integrated release validation and native gameplay.

![Conceptual startup flow: observed identity, optional authored knowledge, resident choices and verified consequences](images/livelihood-startup.png)

Generated architecture illustration of the source contract; it is not gameplay or native qualification evidence.

## Separate the starting conditions from later choices

Census records observed eligible adults and creates reproducible initial personal state. It does not provide resources, start a business or teach recipes. An optional livelihood background is a separately authorized scenario prior: it can describe what a resident is assumed to know at the start, with explicit provenance. This is authored knowledge, not evidence that the resident performed work, attended training or learned from a successful production receipt.

Resources remain governed by the finite founding-resource program and observed inventories. Business registration remains a separate charter decision. A person who knows a recipe may decline to open a business, lack materials, choose another priority or be unable to reach appropriate work. Recipe knowledge is not proof of tools, workstation access, market demand, profitability or a completed output.

The intended dependency chain is therefore: observed identity → explicit census → optional authored recipe prior → feasible resident choices → charter, procurement and work admission where appropriate → observed attendance and inventory receipt → recorded consequences. Refusal, waiting and changed plans remain valid outcomes; no background is an order to produce or trade.

## Identity and prior provenance

Starting knowledge must bind the actor reference and base identity, the scenario definition and the exact recipe definition. A matching display name cannot establish identity. A stale, conflicting or historically unbound population row must not silently qualify a replacement actor or transfer another resident's biography. Preserve legacy history while exposing uncertainty and requiring explicit reconciliation.

New census people can receive matching saved actor/base bindings. Existing unbound history is not automatically bound by another census. Current qualification is recomputed from observations; missing observations, changed bases, duplicate rows, stale identity evidence, explicit child/dead/unloaded flags and invalid classification cannot qualify a prior. Preserving both the actor and base identifiers through a replacement is outside what this identity check can detect. Qualification is not a claim of path reachability or native task ownership.

Identity checks also cover ongoing execution. The resident-control projection publishes only currently qualified assignments, pins `actor_base_id` and places uncertain or changed identities in `identity_holds`. It preserves their original saved slots and assignment history; exclusion is not a release receipt or permission to reuse the slot. Holds expose `release_verified: false` until release is actually established. The native continuity controller rechecks observed/native base identity during tick and renewal, while parallel journeys retain their admitted base pins. Old parallel jobs without a trustworthy base pin are held without replay, and a cold parallel controller cannot adopt an already running native lane. A social receipt cannot grant encounter or heard-identity credit after participant identity becomes unqualified. Unbound legacy saves require explicit reconciliation; another census is not that reconciliation. These are source protections, with no new native qualification claim.

Keep authored assignments distinguishable from verified production learning in saved state, model context and reporting. Neither source should fabricate a heard conversation, friendship, income, material transfer or completed work event. Catalog registration alone is not personal recipe knowledge, and public supplier listings do not disclose private stock.

## Explicit scenario contract

The reviewed [livelihood manifest](../config/livelihood-backgrounds.json) currently defines `founding-livelihoods-v1`. Its `ranked_initial_cohort_v1` rule selects **one** member of an explicitly supplied cohort for the exact registered bread recipe. This is a small authored starting condition, not an occupation census or a claim that the selected resident is a canonical baker. The manifest pins the catalog and recipe hashes and records its provenance. No named character, wealthy resident or engine-assigned profession receives special treatment.

`preview_livelihood_background` validates the requested event ID, seed, scenario ID/hash and distinct bounded actor list without mutating state. Every cohort member must already be managed and match a currently qualified actor/base binding. For each rule, deterministic hash ranking uses scenario hash, seed, rule ID and actor/base identity; roster order and display names do not control the result. A requested recipient count larger than the qualified cohort is rejected rather than silently reduced.

`establish_livelihood_background` saves the frozen definition, cohort, assignments and checkpoint/session provenance through the normal checkpoint writer. The assignment lives separately in `person.authored_recipe_priors`, with source `authored_livelihood_background`, and must match its exact entry in `town.livelihood_backgrounds`. It does not append a fictitious production receipt or learning event. Only one initial cohort can be frozen per timeline. Repeating the same event and request returns the saved result; changing its request, starting another initial-cohort event or overwriting an existing authored prior is rejected. Later census arrivals and configuration edits do not enroll newcomers or reseed the town.

Using a prior requires its saved journal, current actor/base identity, catalog hash, recipe hash and full recipe definition to match. A changed recipe or unqualified actor makes that prior unusable rather than guessing an equivalent skill. The saved definition preserves provenance; it is not permission to execute an obsolete recipe. Recipe knowledge and physical capability still pass their separate admission checks.

The source API exposes `POST /town/livelihood-background/preview` and `POST /town/livelihood-background`. Their exact request fields are `id`, `seed`, `scenario_id`, `scenario_hash`, `actor_ids` and `expected_checkpoint`, with optional `expected_session`. The same observer routes under `/observer/` require the current session as well as checkpoint, and the existing same-origin observer token. Use the actual reviewed hash and currently observed actor IDs; there is no implicit cohort or recipient name. Preview is read-only. Applying requires the director to be paused, a fresh bridge, no pending bridge command and normal checkpoint/admission guards. A stale preview must be refreshed before applying. No request or native activation was performed for this documentation.

## Preview and apply tool

`tools/apply_livelihood_background.py` requires an explicit root, event ID, seed, scenario file and actor list. It defaults to a read-only preview. The file must match the server's reviewed scenario definition; a client cannot introduce an unreviewed recipe by passing another file. The tool checks the returned manifest, request, cohort and hash before allowing application.

In these PowerShell examples, `$ObservedActorIds` must already contain the integer reference IDs of the deliberately selected, currently observed cohort. It is not a default cast or an instruction to reuse an ID from historical evidence.

```powershell
python tools/apply_livelihood_background.py --root D:\WhiterunLab --id initial-livelihood-001 --seed town-livelihood-v1 --scenario config/livelihood-backgrounds.json --actors $ObservedActorIds
python tools/apply_livelihood_background.py --root D:\WhiterunLab --id initial-livelihood-001 --seed town-livelihood-v1 --scenario config/livelihood-backgrounds.json --actors $ObservedActorIds --apply
```

The apply path rechecks the session, checkpoint and exact cohort before posting, then waits for the acknowledged checkpoint and verifies the saved background. A timeout or mismatch is not confirmation. The tool writes compact local startup evidence; this is not an automatic Skyrim save or an end-to-end native trial. Census and charter tools likewise require their own explicit `--apply`; invoking a preview grants no knowledge, assets or business.

## Acceptance measures

These are measurement contracts for qualification, not current scores or invented realism targets. Record the exact build, catalog/scenario hashes, session, observation window and source mode. Publish numerator and denominator, including zero denominators as unavailable rather than 100%. Retain rejection and held cases.

The current source exposes raw startup counts for initialized residents, currently qualified identities and rejection reasons, authored background records, charters and committed production/sales. Population status separately reports qualified, unqualified, unbound and conflicting bindings. These counts do not yet implement every linked denominator below or prove that a sale or production event arose from a particular background.

| Question | Numerator / denominator | Evidence and interpretation |
| --- | --- | --- |
| How much of the currently eligible observed population is managed under a qualified identity? | Currently observed eligible adults with matching qualified saved actor/base bindings / all eligible adults in the same observation | Report absent saved residents, unbound legacy rows and conflicts separately. Saved roster size is not the numerator. Qualification does not prove path reachability or native control. |
| How many requested starting priors were actually assigned? | Accepted authored actor/recipe assignments / requested eligible actor/recipe assignments in the explicit scenario | Retain already-present, rejected, conflicting and unavailable outcomes separately. Count unique assignment identities, not retries. This is scenario setup coverage, not learning success. |
| How much recipe knowledge has verified production provenance? | Distinct actor/recipe knowledge records supported by a validated committed production receipt / all distinct actor/recipe knowledge records in scope | Show authored priors and other historical/unknown sources separately. Mixed provenance requires source counts as well as the distinct-record denominator. A catalog recipe is not evidence that any person knows it. |
| Do backgrounds expose feasible livelihood options? | Resident reviews containing at least one feasible charter or production opportunity / eligible reviews of qualified residents with applicable knowledge | Record stock, money, charter, access and reservation exclusions. An offered option is not a resident choice or a successful enterprise. |
| What do residents choose? | Reviews selecting each available action class / eligible completed decision reviews | Include refusal, rest, quiet and other priorities; report inference failure and budget holds separately from choices. Separate authored operator choices from model-selected choices. |
| Do input purchases settle? | Validated complete input-purchase receipts / admitted input-purchase attempts | Retain refusal before admission, held or partial transfers, and native observation coverage separately. Both goods and payment need bilateral witnesses. |
| Does accepted work become a consequence? | Committed production receipts / accepted work jobs; separately, jobs with verified attendance / accepted work jobs | Link exact job, charter, recipe, actor identity and account receipt. Attendance alone is not production; inventory coincidence alone is not a witnessed effect. |

Follow each opportunity through a stable lineage instead of dividing unrelated aggregate totals. For example, a chosen input purchase can settle while its later work is still waiting; that is one completed purchase and an unfinished production path, not an end-to-end success. Report elapsed time, model calls and every held transition alongside counts. A larger number of authored skills or menu choices is not a measure of human realism or economic complexity.

## Native qualification still required

[Full hosted validation](https://github.com/45ck/whiterun-society/actions/runs/40205604026) passed at revision `0b934c4` on Windows and Ubuntu. Per platform: 1,148 Python tests (1,147 passed, one generated-file check initially skipped and subsequently passed), 450 JavaScript tests, six generated plugins and six plugin readback checks. Windows also compiled both Papyrus scripts. Five fresh-livelihood integration tests use the actual JavaScript attendance and owner-effect controllers through simulated native APIs: a validated production receipt adds verified recipe learning while preserving the authored prior audit. Choices are authored test inputs, not live model decisions. [Machine-readable evidence, first failed run and repairs](evidence/livelihood-validation.json).

These are source and build results, not a Skyrim work trial or measured human realism. No new game deployment occurred. Historical learning aliases remain readable and do not become newly observed learning merely because they are projected.

Use a controlled arbitrary-resident fixture to verify that census, optional knowledge assignment, resources and business formation remain separate state changes. Confirm unchanged inventories and no invented work/voice history when the prior is applied. Reload the saved state and compare exact identities, hashes, assignments and provenance.

Then test removed, renamed and replaced residents; legacy rows without a trustworthy base binding; conflicting duplicate observations; changed recipe/scenario definitions; repeated requests; unknown recipes; and no-census admission. Ambiguous identity or effects must not create a usable prior or silently move history to a different actor.

A separate unforced run must show qualified residents considering the resulting feasible options and independently choosing or declining them. Follow selected economic paths through real meetings, exact spoken terms, input receipts, qualified attendance and production effects. Retain incomplete paths. This slice does not by itself qualify workstation access, generic paid work, multi-input recipes, upstream resource generation or the full movie-first RTS society.

Related: [population](population.md), [catalog](economy-catalog.md), [finite resources](founding-resources.md), [generic procurement](generic-procurement.md), [owner-work attendance](independent-owner-work.md).
