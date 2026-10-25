# Data-driven economy: next-slice gap and proposal

**Status: proposed, not implemented.** This is a source-code audit of the next economy slice. The independent owner-work lifecycle has been implemented separately; native acceptance of that slice remains pending. This audit performed no game control, native inventory changes, or runtime catalogue discovery.

The present system has dynamic residents, enterprise ownership, leases and policy choices, but its executable commodities and recipes are still narrowly authored in code. A configurable bakery policy is not a general production economy.

## Current executable limits

| Area | Current limitation | Source |
| --- | --- | --- |
| Native observation | The observed commodity map contains only gold, bread and grain, with native form IDs embedded in JavaScript. | `bridge/whiterun-society.js`, `bridge/production.js`, `bridge/inventory-transfers.js` |
| Enterprise charter | Executable capabilities are `retail_food`, `bread_recipe`, and `retail_grain`. Policy uses `target_bread`, `grain_per_shift`, and `bread_per_shift`; the permitted recipe is exactly one grain into two bread. | `enterprises.py` |
| Independent owner work | Eligibility, inventory keys, input reservation, output delta, recipe ID, learning and memory all assume bread production. | `owner_production.py`, `owner_work_jobs.py` |
| Native work permit | Job identity admits `bread_recipe`; the serialized commit validates exactly the gold/bread/grain account and one-grain/two-bread conversion. | `bridge/owner-work-jobs.js`, `bridge/production.js` |
| Other paid work | The earlier employer/worker flow also implements the bread recipe and its wage transfer. | `production.py`, `labour.py` |
| Trade and procurement | Seller discovery, commodity snapshots and native trades support bread/grain; procurement specifically seeks grain for bakeries. | `opportunities.py`, `world_economy.py`, `procurement.py`, `bridge/inventory-transfers.js` |
| Knowledge and founding | Verified recipe learning and bakery registration explicitly reference bread. | `entrepreneurship.py` |
| Reporting | Several production and cash-flow checks assume bread/grain fields and recipe-specific memory records. | `agency_metrics.py`, `owner_work_metrics.py`, `metrics.py` |

`metalwork_planned` is a planning label, not an executable recipe or charter capability. Existing coverage deliberately preserves such planned businesses instead of silently converting them into bakeries (`tests/test_entrepreneurship.py`). Registration itself supplies no inputs, tools, money, buildings, or verified knowledge.

Two owner jobs do not require two different recipes: two legitimately configured and funded bakery owners can test concurrent attendance and serialized commits. That proof would establish concurrency, not industrial diversity. A planned workshop must not be relabelled merely to satisfy the test prerequisite.

## Smallest useful catalogue slice

Introduce **one versioned, validated economy catalogue**, shared by Python and the deployed native bridge. Start by representing the existing three commodities and bread recipe without changing their meaning. Then admit one additional, verified native material conversion. The initial generic engine should support exactly one input commodity and one distinct output commodity per recipe; multi-input crafting is a later extension to the effect journal.

Proposed files:

- `config/economy-catalog.json`: logical commodity IDs, display labels, native plugin/local-form references, classification and provenance; recipe IDs, input/output quantities, bounded labour policy and revision.
- `economy_catalog.py` and `bridge/economy-catalog.js`: equivalent validation, canonicalization, lookup and deterministic recipe-delta construction.
- `tools/deploy_bridge.py`: validate and bundle the same manifest and digest used by the Python service. A mismatch prevents admission.

The catalogue is reviewed game configuration. Models select currently offered recipe IDs; they do not supply native form IDs, executable code, inventory deltas, or new recipe definitions through an ordinary decision response.

Each new job must pin catalogue version/digest, recipe revision/digest, enterprise revision, accepted policy, actor/base identity and native attendance identity. A configuration edit must not reinterpret in-flight work. Historical receipts retain their pinned definitions. Legacy bread records need an explicit compatibility reader rather than an invented modern proof.

Enterprise policy should express the selected output's stock target rather than a universal `target_bread`. Recipe knowledge and production memories should reference a recipe ID and verified receipt, with an explicit adapter for existing bread memories. A new recipe must not become universally known merely because its catalogue entry exists.

## Preserve the authority and accounting boundaries

1. Require a valid current enterprise, known/offered recipe and actually observed input stock. Charter registration and catalogue loading create no resources.
2. Reserve the actor, native inventory account, enterprise revision and required input quantity as **intent**. Do not debit inputs before labour or create a second spendable business wallet.
3. Count qualified native attendance independently. It establishes stationary labour time; productive animation remains unverified unless separately measured.
4. Persist the attendance receipt and its single-use native permit. Recheck current charter, identity, catalogue agreement and fresh inventory at the existing exclusive writer boundary.
5. Derive `before`, input-only intermediate state and `after` from the trusted recipe. Native code independently derives and checks the same states. Preserve the existing issued/observed witness for each inventory leg.
6. Consume the exact permit for one commit ID before the first native effect. Only a matching commit receipt plus observed final inventory records production. `actual == after` alone remains insufficient.
7. Keep leases through verified release and durable receipt acknowledgement. Unknown/partial effects, cold controller state, changed sessions and unresolved old-save jobs remain quarantined; they never replay labour or mint a replacement output.

The initial catalogue validator should reject duplicate logical IDs, duplicate native commodity mappings, unresolved recipe references, nonpositive/fractional/overflowing quantities, empty-input recipes, identical input/output commodities and currency creation or consumption by this owner-production primitive. Gold remains unchanged. Approved transformations are authored recipes, not claims of real-world mass conservation or economic calibration.

## Native form verification is a prerequisite

Do not guess a new material's form ID or treat a display name as identity. Resolve the declared plugin/local-form reference in the isolated installation, verify the actual form class and identity, and confirm that the intended native inventory APIs can observe it. Duplicate resolved forms must not masquerade as distinct commodities, especially as an alias for currency.

Missing plugins, unresolved forms, unknown counts or incomplete observations mean **unavailable**, never an observed quantity of zero. No new recipe becomes executable until both service and native bridge agree on the verified catalogue. Any finite demonstration inputs must use the existing explicit, accounted resource-authoring path; ordinary production must not replenish itself.

No such new form verification was performed in this audit.

## Code changes needed for the vertical slice

| Change | Modules |
| --- | --- |
| Observe the configured commodity set and report catalogue compatibility | `bridge/whiterun-society.js`, new catalogue loaders, `tools/deploy_bridge.py` |
| Advertise recipes and compute owner opportunities from charter, knowledge and own stock | `enterprises.py`, `owner_production.py`, `entrepreneurship.py`, `goal_opportunities.py`, relevant `agency.py` context |
| Pin recipe/catalogue identity and derive saved effects | `owner_work_jobs.py` |
| Verify pinned identity and parameterize the existing two-leg recipe witness | `bridge/owner-work-jobs.js`, `bridge/production.js` |
| Record and display verified commodity inputs/outputs without counting admission as production | `agency_metrics.py`, `owner_work_metrics.py`, `metrics.py`, observer/dashboard projection |

The owner-only production slice does **not** automatically add trading, procurement, consumption or paid contracts for every new commodity. A following integration must generalize `opportunities.py`, `world_economy.py`, `procurement.py`, `bridge/inventory-transfers.js` and their decision/consent paths. Retain private-stock boundaries and agreed-price/wage checks. Do not label a new material a functioning supply chain until those exchanges have receipts.

## Required tests and acceptance evidence

- Python/JavaScript catalogue validation and canonical digests agree; unknown recipes, duplicate IDs/forms, currency aliases and invalid quantities fail closed.
- Existing bread charters, saved jobs, receipts and native behaviour remain compatible without being reseeded.
- Two different eligible owners select data-defined recipes; both attend independently while final inventory commits remain serialized.
- Adding a valid test recipe changes offered opportunities and derived deltas without adding an NPC-name branch or recipe-specific execution branch.
- Insufficient inputs, unavailable forms, incomplete commodity observations, changed ownership/revision and mismatched catalogue hashes cause no effects.
- Changing configuration during attendance cannot alter the accepted recipe or reuse its token for another recipe.
- The model cannot inject form IDs, choose an unoffered recipe, change quantities, or turn an input reservation into spendable stock.
- Duplicate commit, input-call timeout, output-call timeout, inventory drift, cold controller restart and old-save restoration preserve the current no-replay and quarantine guarantees.
- Production records link catalogue/recipe hashes, exact input/output deltas, native witness, commit ID and source job. No output is counted at admission or attendance completion.
- Report per-commodity quantities and chain edges; do not add unlike goods as a single physical total or call turnover profit/GDP.
- Native acceptance must verify the added forms and actual before/input-only/after inventory receipts. Mocked tests alone do not establish this.

This proposal closes a concrete data-model gap. It does not claim that generic recipes, metalworking, new resource sales, or a broader simulated industrial economy already work.
