# A persistent starting population

## Fresh timelines now start without a cast

Fresh bootstrap binds the observed zero-marker timeline and saves a deep copy of its inventory observation with session/checkpoint provenance. **`people` starts empty**, even when adults are visible. The snapshot is historical observation, not a spendable wallet, endowment or census. There is no import of the original named-character profiles into a new timeline.

An explicit census with its event ID and seed then initializes every eligible observed adult through the same `person_seed` policy. Names come from observations; authored needs, tendencies, skills and household placeholders use the reproducible seed. The original cast is not required to exist or be loaded. Census creates no gold, goods, friendship, private identity knowledge, recipe knowledge or enterprise. A later census can add newly observed residents without resetting established people, and a living population cannot be silently reseeded.

This is a fresh-timeline change, not an old-save reset. Existing profiles, memories, trust and hunger remain when historical managed people enter a census; prior saved checkpoints retain their data. Bootstrap is restricted to a fresh zero-marker world and cannot be used to overwrite an already bound timeline. Tests that explicitly prepare a historical cast are compatibility fixtures, not the production initialization path.

New ordinary conversations require that nonempty census. Explicit authored scenarios can select already initialized participants through a separate frozen definition; neither path silently supplies the original two speakers. See [ordinary conversations and authored scenarios](conversation-scenarios.md) for admission, knowledge and recovery boundaries.

Focused verification reported **8 new fresh-timeline tests** and **34 existing base/fixture tests**, all passing. This tests source behavior and saved-state preservation; the new bootstrap/census/conversation migration has not been installed or qualified in Skyrim by this work.

## Current identity and optional livelihood backgrounds

The current source adds actor/base continuity to new census records. A newly created person with a valid observed base identity receives an `identity_binding` containing schema version, actor reference, base ID, census event, source checkpoint and observed session; the same binding is retained on the town resident. This is observed identity evidence, not a canonical biography. Census does not attach an unbound legacy history to whichever actor currently occupies that reference, nor repair a conflicting binding automatically. Existing profiles and history remain preserved. A new resident without usable base evidence remains unqualified.

`population_status(observation)` recomputes each resident's `identity_status` from the supplied current observation. It reports qualified/unqualified counts, unbound histories and conflicts separately. Missing observations cannot return a qualified identity, and an old cached success is not authority. Changed bases, duplicate observations, stale row session/checkpoint fields, absent or unloaded actors, explicit children/dead actors and missing adult classification are rejected or shown unqualified according to the source contract. Census records skipped-classification reasons and requires complete bounded inventory for the current catalog. An actor replacement that preserves both native identifiers cannot be detected by this binding alone.

This qualification is independent of the route-support flag: matching identity does not prove path reachability, ownership of a routine, available work slots or completed activity. For coverage, divide currently observed qualified managed adults by all currently eligible observed adults in the same sample; do not divide by historical roster size or report absent observations as success. Raw projection counts are not a validated end-to-end autonomy score.

Ongoing resident control now projects only qualified assignments with an `actor_base_id` pin. Unknown or changed assignments move into `identity_holds`, retaining saved slots and history with `release_verified: false`; they are not counted as released or silently reassigned. Native continuity tick/renew and parallel journeys recheck their base identities. Old unpinned parallel jobs hold without replay, and a cold parallel controller cannot adopt an existing native lane. Conversation receipts are also blocked from granting social/identity knowledge to unqualified participants. Legacy unbound saves require explicit reconciliation instead of automatic census rebinding. These source checks do not establish native recovery or completed release.

An **opt-in livelihood background** can separately assign authored recipe knowledge using an explicit frozen cohort, seed and reviewed definition. The default manifest chooses one ranked cohort member for the registered bread recipe, without naming a Skyrim character. Census itself still grants no recipe knowledge. The prior creates no inventory, charter, production receipt, work memory or friendship. A resident must later choose among feasible actions; business registration, input purchasing, attendance and production remain separate admissions and consequences. Authored prior knowledge stays distinguishable from knowledge learned through verified production. [Scenario contract, identity limits and measurement plan](livelihood-backgrounds.md).

These source changes have not been installed or qualified in Skyrim. The historical census and save evidence below are retained as recorded and do not prove the new identity or background protocol.

The identity implementation owner reported **48 focused tests passing**: 24 new identity/census tests and 24 existing population, fresh-population and route tests. They cover new bindings, preserved unbound legacy history, current-observation qualification, skipped classifications and conflict handling without rewriting history, charters or leases. This is source evidence; it is not a native acceptance count or the final integrated release suite.

## Historical 26-resident census

The historical live census initialized **26 loaded adult NPCs** at checkpoint 174. Each had persistent authored needs, Big Five tendencies, social style, skills, goals and a household reference. Existing personalities, memories and hunger for previously managed characters were preserved. The engine classified the cow as non-person, so it received no human profile. These counts describe that recorded run, not the present loaded population.

This is a census of loaded actors, not every Whiterun resident or interior. Ysolda was outside the census at initialization; her earlier saved profile and memories remain. A subsequent census can add newly observed residents without resetting existing ones. The native `IsGuard` flag is engine evidence, not a verified biography or job assignment.

## Resources and businesses

Initialization creates no gold, food or materials. Household and business resources refer to actual actor inventories rather than duplicate spendable balances. All observed inventories were unchanged after initialization. Initial inventory values are historical evidence, not authoritative current balances.

The 26 recorded household records represent single-adult placeholders. Family membership, obligations and relationship histories still need deliberate modelling. Empty relationships and memories are not invented historical events. Skills and personality scores are reproducible scenario inputs, not psychological measurements.

The following enterprises belonged to the recorded scenario. Census now preserves existing charters and does not create a named business merely by discovering a resident.

| Historical scenario business | Recorded capability | Remaining qualification |
| --- | --- | --- |
| Carlotta's food enterprise | Existing paid recipe: one grain and 30 game minutes of labour produce two bread; wage two gold | Recurring employment, procurement, costing and consensual sales |
| Adrianne's workshop | Resource-custodian reference and charter | Metal inputs, recipes, labour, tool use and sales |

The charter itself runs no jobs. Workers and contract lists start empty. The existing paid-work experiment remains the proof of actual production; registering a workshop does not prove smithing occurred.

## Save proof

| Actual Skyrim save | Checkpoint | Population state | Restore result |
| --- | --- | --- | --- |
| WS-Population-20261024-I | 173 | Before census | All compared fields matched |
| WS-Population-20261024-J | 174 | 26 residents, 26 households, two businesses | All compared fields matched |

Both restores used fresh native game sessions and verified ESS/cosave hashes. Comparison included people, town, prior plans, conversations, production, consumption, imports, inventories and trade history. These settled restores do not qualify interruption recovery or long-term audio stability.

[Census and inventory checks](evidence/population-live.json) · [Earlier save](evidence/population-save-I.json) · [Later save](evidence/population-save-J.json)

## Reproduce and inspect

With the isolated game connected and no unsettled task:

```powershell
python tools/initialize_population.py --root D:\WhiterunLab --id town-001 --seed whiterun-society-v1 --apply
python tools/render_population.py --input docs/evidence/population-live.json --output work/town-overview.html
```

The census CLI now defaults to a read-only preview; omit `--apply` to inspect its current observed cohort and definition hash. Applying repeats the fresh session/checkpoint preflight and verifies the acknowledged saved state. An optional `--actors` list must match the entire observed adult cohort; it does not turn census into a partial named-character initializer. These are source usage examples, not evidence that the new tool has been run against Skyrim. Optional starting recipe knowledge has its own [preview/apply tool](livelihood-backgrounds.md#preview-and-apply-tool).

The overview is a portable offline HTML snapshot with searchable resident cards, needs, traits, stocks, memories and route-support status. Its data is recorded, not live. The game bridge now observes the native game clock, current weather classification and interior/exterior status; these signals are not yet driving weather-sensitive decisions.

## Current capability and remaining qualification

New travel uses the observed mailbox executor for dynamically discovered residents; the original fixed actor-pair route table is no longer an admission path. Census and daily review record route eligibility as supported, unavailable or unknown from current executor/person evidence. Historical ID-derived flags without the current basis marker are unknown until refreshed. This eligibility snapshot is not a claim of destination reachability, free activity slots or native routine ownership. Unloaded or unsupported actors must never be described as physically walking, working or speaking without native evidence.

Needs, commitments, social opportunities and accepted independent jobs feed bounded daily reconsideration. A resident may decline, rest or remain quiet; activity is not required solely to keep the picture busy. Production needs observed inventories and verified receipts, and accessible workstation use remains separate from stationary attendance. See the [data-driven economy migration and qualification limits](data-driven-economy-gap.md).

The target remains three cooperating layers: deterministic state and economic constraints; Jev selecting among feasible actions; language models proposing intentions and speaking when an event warrants it. Quiet intervals and walking past are valid choices. A population record alone is not that complete simulation.
