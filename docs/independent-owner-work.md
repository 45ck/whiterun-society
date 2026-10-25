# Independent owner work: execution contract and native acceptance plan

The next slice lets separate business owners accumulate observed work attendance while a disjoint foreground conversation continues. Each owner then requests a serialized recipe transaction. The goal is to remove long attendance waits from the town's foreground queue without introducing concurrent inventory writers.

**Current evidence boundary:** the service, bridge, worker/director and observer UI are implemented. [Hosted Windows and Linux checks](https://github.com/45ck/whiterun-society/actions/runs/40186289204) passed at revision `e2e3962`: 668 Python tests with one initial build-dependent skip, followed by six generated-plugin readback checks, and 267 JavaScript tests. The separate local runs overlap with this coverage and must not be added together. The native acceptance case below is **not yet qualified**. This does not establish improved queue fairness or a new OKR score. The earlier single-owner fixture and [controlled concurrent-rest trial](concurrent-activities.md) remain separate evidence.

![Generated architecture illustration of independent owner work, rest and conversation with one inventory writer](images/independent-owner-work.png)

*Generated design illustration, not a game screenshot. The depicted workbench activity and animation are conceptual; independent owner work is not yet native-qualified. Stationary attendance and verified inventory effects require separate evidence. [Generation and correction prompts](images/independent-owner-work.prompt.md).*

## Capacity and meaning

| Quantity | Current contract | What it does not establish |
| --- | --- | --- |
| Independent owner-work capacity | Four configured concurrent jobs; the saved projection carries the resolved capacity | Four jobs have not yet been demonstrated together in Skyrim |
| Independent seated-rest capacity | Two separate `WhiterunActivities.esp` slots | Rest slots are not consumed by owner-work attendance |
| Resident mailbox address space | 128 `WhiterunCitizens.esp` mailboxes; each owner uses their existing resident slot | This is not 128 productive jobs, businesses, or verified simultaneous agents |
| Inventory mutation lane | One authoritative pending transaction and checkpoint writer | Independent attendance does not permit parallel ledger mutation |

**Attendance, animation, and production are different facts.** A native self-target package, matching mailbox and stable position can establish stationary attendance. They do not establish that the owner is hammering, baking, or using a workplace. The public projection explicitly reports `productive_animation_verified=false`. Bread is recorded only after the matching single-use native recipe receipt and observed physical inventory agree. No output is credited for admission, stationary appearance, elapsed wall time, dialogue, or an attendance token alone.

The current supported recipe uses **one grain to produce two bread, with zero gold paid**. This slice validates that recipe in code; arbitrary data-defined transformations remain future work. The owner works their own account, so this is not a wage transaction, validated productivity model, or claim of profit. The owner must currently own and steward an active enterprise with the recipe capability. Charter revision, policy, identity, available grain and account reservations are rechecked before the effect is admitted.

## Saved job and native execution

`owner_work_jobs.py` stores `work_jobs[job_id]` with the original `source_plan`, actor/base identity, existing Citizens slot, session/epoch, business ID and revision, recipe ID, policy snapshot/version, required game minutes, input reservation, attendance evidence, settlement state and release/acknowledgement flags. Its schema is `owner-work-jobs-v1`. Source-plan IDs remain attached after a newer foreground event starts; completing one owner's job must not complete or replace somebody else's plan.

Admission reserves the actor, their inventory account, enterprise and resident mailbox. The saved reservation for one grain is not a debit or production effect. A conflicting meal, trade, social encounter, rest or second business job must respect those reservations. An unrelated owner or disjoint pair remains eligible. The current projection exposes live jobs and a bounded acknowledged history of up to 32 records, with attendance and settlement shown separately.

The protocol is:

1. Persist the accepted intention and reservations, then bind the checkpoint. The source plan becomes `delegated`; its daily event remains unfinished.
2. Send `owner_work_start`. Its short acknowledgement means accepted, not worked or produced. The native controller acquires the owner's self-target Citizens hold and independently samples attendance.
3. Require matching actor/base identity, current mailbox serial/package, loaded and eligible actor, the same native cell and position within 100 game units of the anchor. Combat, scene, sleep, lost ownership, invalid clocks and changed identity hold the job. Elapsed game time accumulates only while qualified attendance continues; a clock step over one game minute or a reversed clock is rejected. The allowed work-duration contract is 5–120 game minutes, read from the production policy.
4. Issue a session-bound attendance token after the required samples and game minutes. The current token has a 120-second validity window. Persist the attendance receipt. This is still **zero credited production**.
5. When the foreground conversation/agency and inventory writer are free, recheck current stock, charter, policy and the same valid attendance token. Persist `inventory_self_produce_commit` with exact before/after inventories and bind its checkpoint.
6. Consume the token once in the native mutation path. Reconcile the exact commit ID, actor/business/session identity, token, receipt and observed inventory. Only then append one production record and memory. Both successful output and a partially applied failure must remain visible; an ambiguous effect must not be replayed.
7. Verify native release and the committed recipe identity before completing the source plan. Send `owner_work_ack_receipt` after durable settlement/release; retain reservations while effects or ownership remain unresolved.

Receipt persistence must not replace a pending inventory operation, active speech, conversation attendance command or travel command. Independent native attendance may continue through unrelated checkpoint writes. Recipe preparation currently waits for the foreground event to finish, not merely for a moment between its spoken turns. A long encounter can therefore exhaust a ready work token; that must appear as a held job, not invented production. Fairness and token-wait behavior require measurement.

## Interruption, restart and older saves

Work state is saved, but a saved record alone cannot reconstruct elapsed native attendance or prove whether an interrupted inventory call executed. A new session holds unfinished work without replaying attendance or the recipe. Prepared or uncertain inventory effects retain quarantine rather than inferring completion from an inventory that happens to match a before/after value.

Native receipts absent from an older saved lineage enter `work_orphans`. They may establish release without importing future labour, output or memories. If effects may have been issued and no valid commitment survives, the owner account remains quarantined. A worker exit, timer, cancelled intention or released package does not establish that an inventory mutation was undone. Active-job reset, interruption and cold recovery remain native qualification gaps.

## Exact automated regression obligations

The implementation has dedicated service tests in `tests/test_owner_work_jobs.py`, real checkpoint/SQLite integration tests in `tests/test_owner_work_integration.py`, and native-controller test code. The latest focused review reports **20 native-controller automated tests and seven Python integration tests passing**; these are code-level tests, not Skyrim execution. The full-suite run remains in progress, so no final aggregate is claimed here. Required cases include:

- Four independent mailbox reservations without consuming the two rest slots; rejection of duplicate actor, account, business or mailbox ownership.
- Admission leaves inventory unchanged and the source event unfinished. Qualified attendance persists without creating bread. Changed enterprise revision/policy, missing grain, expired token or changed actor identity rejects recipe preparation.
- Two ready owners obtain serialized commits with exact deltas per owner: grain −1, bread +2, gold 0. Repeated acknowledgements and receipts create neither a second production entry nor duplicate memory.
- Unrelated inventory operations and disjoint travel/attendance/speech retain their command IDs and checkpoints while background receipts arrive. A completed old job updates only its own `source_plan`.
- Wrong receipt identity/token, stale inventory checkpoint and partial inventory mutation hold the operation once without repeated checkpoint churn or automatic retry. A verified rejection before effects can clear the writer but must retain the lease until release is proved.
- Save/load during a prepared recipe does not replay or infer success. Older-save orphan receipts with uncertain effects retain account quarantine; proven no-effect release is durably recorded before acknowledgement.
- Native package loss, unsafe activity, movement away from the anchor, cell/clock changes, service freshness loss and cancelled assignments cannot accrue unverified work or issue a reusable token. Reset and cold reconstruction cannot manufacture attendance.

Passing an authored test proves the specified code path against its test observations. It does not substitute for native package behavior, physical inventories, audible output or a successful live recovery.

## Planned native acceptance: two owners and a separate conversation

Use an isolated managed save and dynamically identified eligible enterprises, owners and disjoint speakers. Record whether initial resources or decisions are authored fixture inputs. Do not silently credit authored choices as agent autonomy. Preserve the plugin manifest and baseline checkpoint, inventories, plans and leases.

The first controlled case admits **two disjoint owner jobs plus a foreground conversation**. Sample the native identities, mailbox serials/packages, attendance clocks, positions and conversation delivery state. Show both owners' qualified game-minute counters increasing over overlapping observed intervals while the separate encounter progresses. Report cumulative and longest continuous overlap separately; do not reuse the seated-rest success count or invent a new realism score.

After the conversation releases, verify both recipes through the single inventory writer. For **each** owner, require exactly **one grain consumed, two bread added and no gold change**, with a distinct attendance token, commit ID, native receipt and one saved production entry. Confirm unchanged unrelated accounts, completed source plans, verified release and acknowledged reservations. Stationary bodies and requested body/head facing are not animation, eye-contact or raycast proof.

Then qualify failure cases individually: interrupt one owner while the other continues; change occupancy/ownership or charter; exhaust a ready token behind an encounter; lose the service; load an older save; and restart while attendance, a prepared recipe or release acknowledgement is pending. Retain the resulting held/quarantined states and any unresolved effects. Native interruption, reset, lease release, and fairness outcomes are currently **unknown**.

Autonomous qualification follows the controlled protocol case. Let residents select or refuse work from their own current state, then retain every attempt and its reason, waiting time, admission, attendance, output and failure. Compare overdue queue age and per-actor opportunities with the serialized baseline. One successful controlled recipe cannot establish employment demand, profitability, sustained production chains, all-resident agency or starvation-free scheduling.
