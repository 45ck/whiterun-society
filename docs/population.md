# A persistent starting population

## Fresh timelines now start without a cast

Fresh bootstrap binds the observed zero-marker timeline and saves a deep copy of its inventory observation with session/checkpoint provenance. **`people` starts empty**, even when adults are visible. The snapshot is historical observation, not a spendable wallet, endowment or census. There is no import of the original named-character profiles into a new timeline.

An explicit census with its event ID and seed then initializes every eligible observed adult through the same `person_seed` policy. Names come from observations; authored needs, tendencies, skills and household placeholders use the reproducible seed. The original cast is not required to exist or be loaded. Census creates no gold, goods, friendship, private identity knowledge, recipe knowledge or enterprise. A later census can add newly observed residents without resetting established people, and a living population cannot be silently reseeded.

This is a fresh-timeline change, not an old-save reset. Existing profiles, memories, trust and hunger remain when historical managed people enter a census; prior saved checkpoints retain their data. Bootstrap is restricted to a fresh zero-marker world and cannot be used to overwrite an already bound timeline. Tests that explicitly prepare a historical cast are compatibility fixtures, not the production initialization path.

New ordinary conversations require that nonempty census. Explicit authored scenarios can select already initialized participants through a separate frozen definition; neither path silently supplies the original two speakers. See [ordinary conversations and authored scenarios](conversation-scenarios.md) for admission, knowledge and recovery boundaries.

Focused verification reported **8 new fresh-timeline tests** and **34 existing base/fixture tests**, all passing. This tests source behavior and saved-state preservation; the new bootstrap/census/conversation migration has not been installed or qualified in Skyrim by this work.

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
python tools/initialize_population.py --root D:\WhiterunLab --id town-001 --seed whiterun-society-v1
python tools/render_population.py --input docs/evidence/population-live.json --output work/town-overview.html
```

The overview is a portable offline HTML snapshot with searchable resident cards, needs, traits, stocks, memories and route-support status. Its data is recorded, not live. The game bridge now observes the native game clock, current weather classification and interior/exterior status; these signals are not yet driving weather-sensitive decisions.

## Current capability and remaining qualification

New travel uses the observed mailbox executor for dynamically discovered residents; the original fixed actor-pair route table is no longer an admission path. Census and daily review record route eligibility as supported, unavailable or unknown from current executor/person evidence. Historical ID-derived flags without the current basis marker are unknown until refreshed. This eligibility snapshot is not a claim of destination reachability, free activity slots or native routine ownership. Unloaded or unsupported actors must never be described as physically walking, working or speaking without native evidence.

Needs, commitments, social opportunities and accepted independent jobs feed bounded daily reconsideration. A resident may decline, rest or remain quiet; activity is not required solely to keep the picture busy. Production needs observed inventories and verified receipts, and accessible workstation use remains separate from stationary attendance. See the [data-driven economy migration and qualification limits](data-driven-economy-gap.md).

The target remains three cooperating layers: deterministic state and economic constraints; Jev selecting among feasible actions; language models proposing intentions and speaking when an event warrants it. Quiet intervals and walking past are valid choices. A population record alone is not that complete simulation.
