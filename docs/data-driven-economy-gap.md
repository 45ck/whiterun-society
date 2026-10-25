# Data-driven economy: implemented catalog and remaining gaps

**Implemented in source; deployment and native qualification remain unclaimed.** The versioned catalog, Python/bridge validation, owner-recipe parameterization, catalog-bound inventory intents and recipe-aware charter/knowledge paths now exist. The default catalog still contains exactly **gold, bread and wheat-labelled grain, with one authored bread recipe**. This closes a definition/execution gap without establishing a broader industrial economy. [Architecture and implementation contract](economy-catalog.md).

## Built, unqualified and still limited

| Area | Implemented source behavior | Remaining boundary |
| --- | --- | --- |
| Catalog authority | `config/economy-catalog.json`, `economy_catalog.py`, `bridge/economy-catalog.js` validate definitions and canonical hashes; packaging embeds the validated manifest | Not a live hot-edit interface; the running service and bridge must be updated coherently and qualified |
| Native observation | Configured commodities resolve by plugin/local ID and class/type evidence; unknown counts remain unavailable; duplicate resolved forms fail | Offline master verification does not prove the installed runtime binding or load-order overrides |
| Owner production | One data-defined input and one distinct output, quantities 1–1,000; complete account checks and unchanged currency; single-use attendance token and serialized commit witness | No multi-input crafting, station-use proof or native generic-recipe acceptance yet |
| Enterprise policy | Executable recipe capabilities come from the catalog; recipe policies are keyed by registered ID and generic output targets | Existing bread policy fields remain compatibility fields; registration creates no stock, building or tools |
| Knowledge and decisions | Recipe-specific verified learning, exact definition matching, offered business/recipe action IDs and explicit historical bread aliases | A catalog entry does not teach a recipe. Authored operator charters are not proof of resident learning |
| Trade and procurement | Bread/grain paths carry catalog proof and preserve the full configured account | New catalog materials do not automatically acquire sellers, buyer demand, price negotiation or procurement routes |
| Consumption and finite grants | Existing supported actions now carry catalog proof and preserve unrelated configured balances | Consumption is still bread; grants retain original commodity support |
| Paid work | New bread-production terms pin catalog/recipe hashes and derive quantities from the catalog | Paid-work menus and labour contracts remain bread-oriented, not generic industrial employment |
| Reporting | Configured mechanisms and deduplicated committed owner transformations are separate; input/output quantities retain their commodity identity | Configuration is not throughput, zero owner wage is not profit, and no new realism or OKR score is claimed |

A synthetic **two-grain to three-bread** recipe exercises generic quantities in tests only. It is not in the checked-in runtime catalog. The verified iron conversion below is also not activated. `metalwork_planned` remains a planning label, not an executable charter capability.

## Remaining NPC-specific execution paths

The town economy is not restricted to the original three residents: census accepts observed adult NPCs, sellers come from active business charters, and owner work uses discovered actor/business/recipe identities. The remaining named-actor exceptions below prevent an absolute “nothing is hardcoded” claim. This source audit excludes tests and isolated authored demonstration sequences; it does not establish deployed behavior.

| Exact source | Classification and current consequence | Next bounded change |
| --- | --- | --- |
| [routing.py:20](../routing.py#L20), [agent-routines.js:10](../bridge/agent-routines.js#L10), [agent-routines.js:44](../bridge/agent-routines.js#L44) | **Executable routing exception:** pairs among IDs `108149`, `108186`, `108156` select the fixed `WhiterunAgents.esp` route table. `route_available` accepts these pairs before checking the dynamic mailbox capability; other residents require that capability and adult classification. Arbitrary residents work when the mailbox is available, but routing eligibility is not uniform. | Prioritize one observed-capability route policy for all residents, retaining explicit cleanup of any already-owned legacy packages. Verify a newly discovered pair and the original pair fail equally when the executor is unavailable. |
| [server.py:264](../server.py#L264), [agency.py:77](../agency.py#L77) | **General API default:** omitting `actor` from `/agency/event` selects `108186`. This is not an actor whitelist; the resident worker already sends an explicit actor ([run_resident_event.py:116](../tools/run_resident_event.py#L116)). | Require the caller's explicit resident or an exact saved event identity; do not silently select a named resident. |
| [population.py:40](../population.py#L40), [population.py:134](../population.py#L134), [daily_life.py:69](../daily_life.py#L69) | **Initial reporting default:** `native_route_supported` initially depends on the same three IDs. A later daily review replaces it with observed route/market availability. This can temporarily underreport newly discovered residents; it does not stop their census admission. | Initialize this field from current executor evidence or mark it unmeasured until reviewed. |
| [endowments.py:44](../endowments.py#L44), [endowments.js:11](../bridge/endowments.js#L11) | **Authored scenario policy:** the finite founding program grants `108149` 100 gold/2 bread/20 grain; other initialized residents receive 20 gold/2 bread/0 grain. It affects starting wealth and input distribution, not ordinary production eligibility or earned revenue. | Move recipient allocations into a versioned, explicit scenario specification if generalizing the founding program; never infer occupation or wealth from an NPC name. |

Pre-census Adrianne visits, the original Ysolda/Carlotta encounter, shortage-rumour profiles and market-day scripts remain authored compatibility/demo paths, not evidence that the populated-town dispatcher is restricted to those names. The higher-priority gap is the live routing exception, followed by the implicit general-API actor default; moving authored scenario data alone would not resolve either.

## Migration is conservative

New inventory intents require a matching resolved/type-verified native catalog and carry its digest. Owner/paid-production terms also pin recipe identity. Missing or changed catalog proof on an unsettled legacy intent causes a hold; the dispatcher does not stamp it with a new hash or replay it. Old owner jobs without supported proof require explicit reconciliation. Historical receipts and narrowly defined legacy bread knowledge remain readable without claiming modern native evidence.

Catalog changes invalidate recipe hashes because each recipe digest includes the full catalog digest. A configuration edit cannot reinterpret already accepted work. Full configured accounts are required: missing commodity observations are not zero balances. The service loads its catalog at process import and deployment packaging embeds the bridge manifest; editing one JSON file does not update running processes. No blanket live-save migration or native rollout has been qualified by this implementation.

## Verified owned-master metadata

The local owned `Skyrim.esm` is **249,753,412 bytes**, SHA-256 `2bbc77fdec35a70ef96b710f8c525e50a1db9e63e11a391a0eb9ee8f56d36107`. Its TES4 record version is **44** and HEDR version decodes to **1.7100000381469727**. Record traversal, compressed-record decoding and subrecord parsing produced the following metadata; game assets were not copied into the repository. [Compact provenance and records](evidence/native-economy-items.json).

| Logical use | Plugin-local form ID | Native record / editor ID | Activation boundary |
| --- | --- | --- | --- |
| Septims | `Skyrim.esm:0000000F` | MISC / `Gold001` | Existing currency mapping |
| Bread | `Skyrim.esm:00065C97` | ALCH / `FoodBread01A` | Existing food mapping |
| Grain label | `Skyrim.esm:0004B0BA` | INGR / `Wheat` | Existing simulation label maps specifically to wheat |
| Candidate iron ore | `Skyrim.esm:00071CF3` | MISC / `OreIron` | Verified metadata only; not added as executable material |
| Candidate iron ingot | `Skyrim.esm:0005ACE4` | MISC / `IngotIron` | Verified metadata only; not added as executable material |

The master contains **COBJ `000A30C3`, `RecipeIngotIron`**, record version 40: one `OreIron` input, one `IngotIron` output, one declared input entry, and zero CTDA condition subrecords. Its workbench keyword is **`000A5CCE`, `CraftingSmelter`**. Zero condition subrecords does not remove that workstation requirement. Current stationary owner attendance does **not** prove access to, operation of, or animation at a smelter. The candidate remains disabled until a station-access gate, an explicit simulation labour policy and appropriate actor recipe knowledge exist and are tested. Native recipe metadata supplies no economic demand, price, profit or autonomous production evidence.

Local SKSE source declares native `Form.GetType()` and enum values **MISC 32**, **INGR 30**, **Potion/ALCH 46** and **ConstructibleObject 49**. Source hashes are retained in the metadata receipt. No installed SkyrimPlatform SDK declaration was located, and its exact typed casts/getType binding was not invoked. Runtime feature checks must require available, consistent class/type evidence; static enum knowledge is not proof that the installed bridge exposes the method. Load-order overrides remain outside this base-master inspection.

## Native acceptance and remaining economic work

Focused automated work covers schema rejection, canonical identity, complete-account arithmetic, changed catalog/charter handling, recipe-specific knowledge and synthetic nondefault quantities. Native-controller tests retain single-use permits, input/output witnesses, partial-effect holds, duplicate acknowledgements and release/quarantine behavior. These are source-level tests; final aggregate results belong in the verified build/run record, not an invented total here.

Before qualifying native generic production, show the installed catalog resolving with matching hashes and types, then two eligible owners accruing overlapping attendance while a disjoint foreground encounter proceeds. Serialize the final commits and retain exact per-owner before/input-only/after inventories, tokens, receipt hashes, source plans and release acknowledgements. Test changed catalog, missing inputs, partial effects, expired permits, cold restart and old-save restoration without replay. An authored recipe fixture demonstrates mechanics; later unforced choices need separate denominators and evidence.

To make a material supply chain, the next work must connect acquisition, seller discovery, private stock allocation, agreed-price exchange, recipe knowledge, accessible workstations, production and demand. Generalize `opportunities.py`, `world_economy.py`, `procurement.py`, `bridge/inventory-transfers.js` and decision/consent paths deliberately. A new commodity mapping does not provide those mechanisms. Multi-input crafting needs a reviewed multi-leg effect journal; business profit needs costs, revenue and account boundaries rather than a turnover label.

Keep the [independent owner-work acceptance plan](independent-owner-work.md) and [quantitative roadmap](simulation-roadmap.md) as the next gates. Catalog capacity, generated speech, a local test, and a static master recipe must remain distinct from deployed behavior, actual sales, native station use and a sustained autonomous economy.
