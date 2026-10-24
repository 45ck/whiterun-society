# A persistent starting population

The live census initialized **26 loaded adult NPCs** at checkpoint 174. Each has persistent authored needs, Big Five tendencies, social style, skills, goals and a household reference. Existing personalities, memories and hunger for previously managed characters were preserved. The engine classified the cow as non-person, so it received no human profile.

This is a census of loaded actors, not every Whiterun resident or interior. Ysolda was outside the census at initialization; her earlier saved profile and memories remain. A subsequent census can add newly observed residents without resetting existing ones. The native `IsGuard` flag is engine evidence, not a verified biography or job assignment.

## Resources and businesses

Initialization creates no gold, food or materials. Household and business resources refer to actual actor inventories rather than duplicate spendable balances. All observed inventories were unchanged after initialization. Initial inventory values are historical evidence, not authoritative current balances.

The 26 household records currently represent single-adult placeholders. Family membership, obligations and relationship histories still need deliberate modelling. Empty relationships and memories are not invented historical events. Skills and personality scores are reproducible scenario inputs, not psychological measurements.

| Business | Implemented capability | Remaining work |
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

## Next implementation

Most new residents await their first daily plan. Native owned travel still supports only Ysolda, Carlotta and Adrianne; only the latter two were in this census. Connect elapsed game time, needs and commitments to bounded reconsideration, expand native travel beyond fixed actor pairs, and attach productive roles with conserved inputs and outputs. Unloaded or unsupported actors must never be described as physically walking, working or speaking without native evidence.

The target remains three cooperating layers: deterministic state and economic constraints; Jev selecting among feasible actions; language models proposing intentions and speaking when an event warrants it. Quiet intervals and walking past are valid choices. A population record alone is not that complete simulation.
