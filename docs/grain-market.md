# Grain procurement and a connected food chain

**Historical implementation and native trial:** the results on this page describe the earlier grain-specific protocol. The later [configured procurement and witnessed-exchange implementation](generic-procurement.md) generalizes listings, demand and quantities in source, but is not native-qualified. Its arm/deliver protocol holds after native witness loss instead of reconstructing a transaction from matching inventories; the earlier restart behavior below is not permission to replay a new trade.

An initialized bakery can now buy grain from a currently available public supplier. The buyer considers its own stock and production target; it does not know the supplier's inventory or willingness. Both residents can negotiate or refuse. A successful native purchase enables a later production choice, followed by an independently consented bread sale and consumption.

![Illustrated grain procurement and production loop](images/grain-market-loop.png)

Generated explanatory illustration, not gameplay. [Generation prompt](grain-market-image-prompt.md).

## What changed

Enterprise charters support `retail_grain` alongside bread retail and production. The observer can configure grain suppliers, food suppliers or mixed bakeries using current resident identities. The scheduler offers procurement when an enterprise's existing inputs cannot meet its authored bread target. It creates an opportunity, never an automatic purchase or a forced work decision.

Jev selects among feasible bids, counteroffers, acceptance and refusal. The language layer remains available for social dialogue; economic wording states exact terms deterministically, and local Kokoro speaks them. Skyrim owns navigation and animation. The bridge transfers existing wheat and septims, verifies the resulting inventories, and records commodity-specific personal memories. Grain purchases do not reduce hunger or release household bread reserves. Bread and grain price series are shown separately.

Native commands now reject unsupported goods, malformed quantities, insufficient stock and unconserved effects before mutation. Deferred operations are awaited; a restart after the goods leg resumes payment without repeating the goods transfer. Drift in even the untraded bread balance holds a grain transaction for reconciliation.

## Native qualification on 25 October 2026

The controlled chain used Jon Battle-Born, Carlotta Valentia and Fralia Gray-Mane, selected from current observed residents and queued reviews. These names are trial observations, not planner constants. The operator registered supplier and bakery capabilities; no new stock or money was granted.

| Stage | Native result | Decision provenance |
| --- | --- | --- |
| Input negotiation | Jon bid 2; Carlotta asked 4; Jon accepted. One grain moved from Carlotta to Jon; 4 septims moved back. Four spoken lines completed. | Controlled integration choices |
| Production | At Jon's next scheduled review, five qualified game minutes converted his purchased grain into two loaves. His purse stayed at 30 septims. | Controlled integration choice |
| Retail and meal | Fralia bought one of Jon's loaves for 3 septims, then consumed it. Three spoken lines completed; her simulated hunger fell from 1.0 to 0.4. | Controlled integration choices |

Across the three participants, money remained **170 septims**. Carlotta ended with 106 septims and 19 grain; Jon with 33 septims and one remaining loaf; Fralia with 31 septims and no carried bread after eating. Grain decreased only through the documented recipe. The sampled worker intervals were 46.074 seconds for procurement, 19.848 for production and 37.715 for retail/consumption; these exclude charter setup and the wait for the next scheduled review. The seven delivered lines demonstrate the protocol, not natural conversational quality or autonomous profitable enterprise.

![Jon receiving grain after a controlled native negotiation](images/grain-trade-native-fixture.jpg)

The screenshot shows the older static encounter heading; the current heading is commodity-neutral. The camera angle was set through the observer API. [Listen to the generated utterances](https://45ck.github.io/whiterun-society/#voice-example) · [Native receipts, timings, transcripts and balances](grain-market-evidence.json).

The preceding real Jev trial chose to seek **bread**, not grain, and offered 2 septims. Its first line played, then the seller's request exceeded the 16,000-byte local guard because action descriptions were duplicated. It held with unchanged inventories. The adapter now sends those descriptions once, retaining the resident state and the same bound. A separate live provider check of that captured context returned `decline` in 4.0 seconds, reporting US$0.000212478; that proposal was not applied to Skyrim. This is not an unforced completed grain cycle.

Save `WS-Grain-20261025-BJ` restored all **17 compared state fields**, including inventories, people, town charters, work and consumption. The controlled trial is preserved in evidence, not retained as ordinary live economic success. The director remains paused.

## Verification and remaining gaps

The full Python suite passed **339 tests** in 419.682 seconds. After the small provider fix, all four provider tests—including the new context-deduplication regression—and all eight procurement tests passed. The final JavaScript suite passed **167 tests** in 2.384 seconds, including all seven supported enterprise-capability combinations. Hosted CI remains unverified.

This is a connected finite-input prototype: two traded goods, one recipe and one production transformation. Farming, replenishment, autonomous business formation, separate business treasuries, negotiated wages, rent, credit and taxes remain unfinished. The next economic acceptance target is an unforced repeated purchase → work → sale → meal cycle with measured margins and stockout recovery.

The automatic movie camera still sometimes intersects buildings, as [this captured failure](images/grain-chain-camera-obstruction.jpg) shows. Manual camera positioning can recover the view. Native in-game input remains intermittent; productive animations, eating animations, eye gaze, raycast accuracy, lip sync and physical-speaker audibility are not established by the inventory and overlay playback receipts.
