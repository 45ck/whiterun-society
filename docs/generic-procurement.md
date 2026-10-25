# Configured procurement and witnessed exchange

This slice separates what exists in the catalog, what a business publicly offers, what a resident knows how to use, what two residents agree to exchange, and what actually moves in Skyrim. These are different authorities. Adding a catalog row does not create supply, demand, recipe knowledge, a seller or a completed sale.

The policy/listing, demand, dialogue and transfer contracts below are implemented in source and have focused automated coverage. **This slice is not installed or native-qualified.** The default catalog remains gold, bread and wheat-labelled grain. A fourth commodity is only a synthetic fixture for exercising generality, not an activated industrial chain.

## Market policy and public listings

[config/market-policy.json](../config/market-policy.json) defines `resident-market-v1`, bound to the exact economy catalog. It enables bread and grain, with authored quantity choices **1, 2, 5 and 10** and a bounded unit-price ladder inside **1–100 gold**. The execution safety ceilings remain **10 units per exchange** and **100 gold per unit**. These are experimental option bounds, not discovered willingness, market equilibrium or a claim that every combination is available.

The policy validates unique registered noncurrency goods, sorted distinct integer choice lists, quantity/price bounds, compatibility capability names and reserve modes. `existing_food_policy` applies only to bread; `seller_choice` supplies the non-food reserve mode. A canonical policy digest pins the whole reviewed definition to each new trade. An in-flight transaction cannot silently adopt a changed catalog or market policy.

A business advertises through explicit `sale_commodities` and an appropriate retail capability. `retail_goods` supports reviewed declared goods; the old `retail_food` and `retail_grain` aliases are read through their policy mappings. Historical charters without an explicit list can be projected through those mappings without rewriting the saved charter. A producer is not automatically a retailer. Registration and a public listing create no inventory or knowledge of private stock; a seller can lack goods, retain them or refuse an offer.

## Demand comes from the resident's state

`input_procurement` considers an active enterprise only when the resident is both its owner and custodian, holds the executable recipe capability and personally knows the exact recipe. It uses that resident's complete observed inventory and the enterprise's configured output target. For the current one-input/one-output recipe schema, required batches are the ceiling of the remaining output target divided by output per batch; input shortfall subtracts inputs already held. A satisfied target or sufficient input stock creates no new procurement demand.

Quantity candidates come from the reviewed goods menu, cannot exceed that input shortfall, and must be affordable from the resident's own gold at the policy's minimum unit price. This is an initial opportunity filter, not a promise that a seller accepts that price. Later bargaining and physical execution recheck the actual quantity, total cost and stock.

Each purchase option pins supplier, producing business/revision, known recipe/hash, catalog/market-policy hashes, commodity, quantity, purpose `production_input`, and the supplier listing/revision. An opaque choice ID binds those fields. Selection is revalidated from current state; distance can change while walking, but an obsolete recipe, listing, enterprise revision or demand cannot silently become the same valid offer. The old `grain_procurement` helper is a compatibility filter over this mechanism.

Multiple enterprises sharing an owner's purse produce **alternative choices**, not simultaneous input reservations. Their shortfalls are not added together as guaranteed demand, and listing candidate options neither spends money nor allocates the shared inventory. Public suppliers are found from explicit listings and current resident/route eligibility. The buyer sees the public capability and its own known identity view, not the supplier's stock or private willingness. Catalog registration alone teaches no recipe and grants no private knowledge.

## Bounded attention without dropping purchase alternatives

A larger supplier set previously overflowed the 12,000-byte serialized decision-context bound. The source repair uses a staged `purchase_select` view, configured by [purchase-attention.json](../config/purchase-attention.json): at most six full alternatives per leaf, up to eight branches per group and a separate maximum of 16 navigation/selection decisions, including the final leaf selection. The initial decision to inspect the menu and subsequent negotiation retain the six-decision economic allowance. Both lanes remain bounded and counted; worker run-budget projections conservatively include the 16-call navigation ceiling per event.

When more than six eligible alternatives exist, the ordinary review offers inspection of the purchase menu. Entering it freezes the full choice list, its canonical identity hash and the attention policy. Groups summarize goods, the resident's projects, public supplier identities and observed distances. A leaf exposes the original complete purchase proofs; group navigation, going back or cancelling creates no purchase, reservation or inventory effect. Supplier motion alone does not change a choice's contractual identity. Changed listings or demand are rechecked, with unavailable saved choices shown explicitly rather than replaced by another supplier. Invalid menu ranges, hashes or policy state are rejected.

The final offline fixture has 18 residents and 17 suppliers. Its exhaustive traversal reached all **68 quantity/supplier alternatives across 44 menu nodes plus the overview**, with zero context errors and a largest context of **8,186 bytes**, including public supplier-name and distance hints. Any leaf required at most three navigation/selection calls after the initial inspection decision. These are compact JSON byte counts below the unchanged 12,000-byte bound, not model tokens or measured inference latency. Exhaustively visiting the test graph does not mean one resident browsed all 44 nodes within its 16-call navigation allowance. This fixture demonstrates source reachability at that size, not unlimited market scale, a successful model choice or native economic activity.

## Decision and effect loop

```mermaid
flowchart LR
    K[Own state and known recipe] --> D[Derive eligible input demand]
    L[Explicit public seller listing] --> O[Offer feasible supplier and quantity choices]
    D --> O
    O --> C[Resident choices and exact negotiated terms]
    C --> V[Grounded spoken offer and response]
    V --> R[Persist consent and reserve both accounts]
    R --> A[Native arm: zero effects]
    A --> P[Persist permit checkpoint]
    P --> G[Issue goods transfer; witness both accounts]
    G --> M[Issue payment; witness both accounts]
    M --> E[Matching terminal receipt and final balances]
    E --> H[Commit trade history and personal memory]
    G -->|Uncertain effect or identity| Q[Hold both accounts; no blind replay]
    M -->|Uncertain effect or identity| Q
```

This diagram describes the intended integrated resident path. Operator-authored trade fixtures have a separately labelled consent source and cannot be counted as autonomous negotiation. Generated speech alone authorizes no inventory change. Refusal and continued quiet are valid outcomes; an authored policy does not require a sale.

## Spoken terms cannot drift from the agreed trade

Trade speech freezes the commodity's reviewed label, quantity, unit price, total cost and currency. An offer, counteroffer, acceptance, refusal and post-transfer receipt use those exact terms. For example, a five-unit offer at three gold per unit states **five units, three each, fifteen total**; this arithmetic example is not a recorded transaction. The receipt line is queued only after physical settlement, rather than making its claim true by speaking it.

The language model can propose bounded courtesy wording around one protected terms marker. Validation keeps the canonical terms unchanged and rejects extra numeric/economic claims, unsupported explanations or repeated greetings. Invalid wrappers are recorded and can be replaced with direct unchanged terms. This tight wording boundary improves contract clarity but is not evidence of natural sales dialogue or humanlike negotiation. Local voice synthesis and delivered playback still need separate timing, audibility and attendance evidence.

## Two accounts, two witnessed transfer legs

New native trades use `inventory_trade`, protocol 2, with `arm` and `deliver` phases. The immutable contract binds the trade ID, catalog and market-policy hashes, buyer/seller references and base identities, commodity, currency, quantity, unit price, total cost, originating session, executor epoch, complete before/after accounts and consent identity/hash.

Both participants must be classified adults, loaded, in the same verified native parent cell and within 500 native coordinate units. Missing or invalid positions/cell identity cannot satisfy proximity. The arm validates the exact starting accounts and returns a permit **without inventory effects**. The service checkpoints that permit before authorizing delivery.

Delivery first issues the goods transfer from seller to buyer, then payment from buyer to seller. Each native call is marked issued before invocation. A transfer can be observed asynchronously: unchanged, debit-only, credit-only or both changed are allowed only after that specific leg was issued. The controller waits for **both** the sending debit and receiving credit before proceeding. A previously observed side regressing, an unrelated commodity changing, a five-second observation timeout or a native-call error holds the trade without resending it. The arm permit has a 120-second pre-delivery deadline.

The complete receipt carries separate goods/payment witnesses, each with exactly `leg`, `item`, `amount`, `issued`, `observed`, `debit_observed` and `credit_observed`, plus exact final accounts. All four witness flags must be true. The service validates the complete receipt and fresh observed balances before recording a sale. A coincidental final inventory is insufficient; one party losing goods does not establish the other received them, and goods arrival alone is not payment.

The actor/account reservations cover both purses while armed, delivering or held. A native completed receipt can release its live reservation, while pending service settlement still protects those accounts. Only one authoritative effect/checkpoint pipeline commits inventory consequences; this is not parallel uncontrolled trading.

## Consent, history and recovery boundaries

Resident trade provenance must bind the selected buyer/seller, quantity, commodity, unit price, total cost, policy/catalog identities and purpose. A changed offer requires a new matching response; a statement about buying does not prove consent to different terms. An operator fixture cannot masquerade as a resident-selected trade, and operator trade cannot spend a protected household bread reserve.

Procurement consent also carries the producing enterprise, public listing, recipe identities/revisions and original selected-choice claim. Admission rechecks demand before effects; settlement checks the accepted structural terms rather than demanding that the original shortage remain after its goods arrived. A production-input purchase records that purpose, exact quantity and paid total; it does not automatically eat the goods or lower hunger. Only a bread purchase for the food purpose proceeds to the separate food-use path. Verified purchase may make later production feasible, but it does not complete production or teach an unknown recipe.

Service intents, arm permits and committed receipts are saved. Native issued/effect witnesses remain **live-controller-only**. Reset, hot reload, session/epoch change or an unknown permit does not reconstruct progress from inventory. Unresolved work holds both accounts without replay; partial transfers can exist without a completed sale. This is not an atomic rollback or an exactly-once guarantee across crashes. Historical completed trade evidence remains historical; old unfinished transfer contracts require reconciliation, not silent promotion to the new protocol.

Food consumption retains its separate existing protocol. The market policy does not make every commodity edible, teach an unknown recipe, create another currency, supply equipment, establish station access or implement multi-input production. Catalog capacity is distinct from economic throughput, autonomous behavior and human realism. Held or possibly partial exchanges must remain separate from verified sales in the observer; unknown commodity identifiers must not fall back to bread.

## Source evidence, not game evidence

The complete [hosted run 40201564112](https://github.com/45ck/whiterun-society/actions/runs/40201564112) passed at revision `20269b420664e9f52681789ab9efb5958baf93af`. Windows and Ubuntu each ran 1,039 Python tests (1,038 passed, one generated-file test initially skipped and subsequently passed), 420 JavaScript tests, six generated-plugin builds and six plugin readback checks. Windows also compiled both Papyrus scripts. [Exact evidence, including the earlier failed fixture migration](evidence/generic-market-validation.json). These are source and build results, not installation or native gameplay acceptance.

The integrated synthetic case uses real charter/knowledge/choice/service logic and the JavaScript trade controller with **fake native actor/form APIs**. It exchanges **15 gold for five units of fixture-only ore**, checks conservation and private-information boundaries, records one purchase memory, leaves hunger unchanged and makes a later production opportunity feasible. It does not execute Skyrim, enable ore in the installed catalog or complete metal production. Two companion cases reject changed listings and unknown recipes.

The implementing owners reported three generic-cycle tests, 60 lineage/service-fault tests, eight consent tests, four Python/Node interoperability cases, 75 focused JavaScript controller tests, and 50 speech/language/memory Python plus 40 UI tests passing. These suites overlap and are not summed into a unique total or a claim about hosted validation. The policy/schema/listing suite separately reported 14 checks. The staged-menu owner reported seven purchase-attention tests and three worker tests passing, including real SQLite claim persistence to the final leaf, unchanged selection proof, Back/Exit, stale listings, malformed menu state and independent budget limits. Keep final integrated/hosted results tied to their exact revision in the release evidence.

## Qualification to perform

Before native activation, test policy/catalog changes, renamed/replaced residents, listing removal, unknown recipes, unaffordable quantities, private-stock leakage, changed consent, exact numeric spoken terms, and both sides of every asynchronous transfer. Include debit-only and credit-only delays, regressions, foreign inventory drift, duplicate/lost acknowledgements, side effects before a thrown native exception, cold controller loss and older-save restoration. Retain failed and held cases.

A first controlled native case should exchange an enabled good at quantity greater than one, record the effect-free arm and persisted permit, witness both goods accounts and both payment accounts, and verify the final ledger and memories. A separate unforced model-driven case must show the actual demand/known recipe, public supplier selection, agreed voiced quantity/price, physical meeting, receipt and later use. Neither a fixture commodity nor an authored successful exchange proves a richer autonomous economy.

Measure offered opportunities, chosen quantities, refusals, completed/held transfers, both-leg observation delays, reply dispatch and audible onset separately, with build/configuration and source-mode labels. Do not combine missing observations with zero delay or treat a transfer count as a realism score.

Related: [catalog definitions](economy-catalog.md), [remaining economy gaps](data-driven-economy-gap.md), [historical grain chain](grain-market.md), [finite external imports](founding-resources.md).
