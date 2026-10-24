# Residents can seek a known place

Idolaf selected `check_market` while Carlotta was not loaded. Skyrim walked him to its public marketplace reference, acknowledged the owned travel package and released it after arrival. Carlotta was still not within interaction range. He remembered the unsuccessful visit; no money, food or hunger recovery was invented.

![Idolaf walking toward the market with the resident inspector open](images/market-travel-live.png)

This image captures the actual trip. Its right-hand destination label displayed `undefined`; the final UI now resolves public-place names in that card too. The left inspector already showed the correct destination.

## Measured result

| Observation | Result |
|---|---|
| Event | `daily-16-108169` |
| Choice | `check_market`, selected by `typesafe/jev-1.14-20261014` |
| Model usage | One call, 0.765 seconds, reported US$0.000089712 |
| Time to complete stage | 73.25 seconds, including decision and walking |
| Distance | 4,171.93 → 249.59 game units |
| Ownership | Papyrus aliases acknowledged; owned package witnessed; release observed |
| Consequence | Seller not observed nearby; unsuccessful-visit memory |
| Conservation | All 29 observed native inventories unchanged |
| Hunger | 0.922521 before and after |
| Persistence | Checkpoint 537, `WS-Market-20261024-AG`; fresh-load comparison passed for all recorded fields |

[Compact native receipts](evidence/known-market.json) include the offered choices, movement acknowledgement, inventory comparison and save/load checks. The developer selected a pending resident event; the model chose the action. This is not a fully autonomous town scheduler demonstration.

## Knowledge and execution

The authored shared starting knowledge is that Whiterun has a public market. Its location uses the owned game's `WhiterunMarketplaceMarker`, Skyrim.esm reference `0x2BE1B`. No game assets are redistributed. A public map location is different from knowing a merchant's current whereabouts or private stock.

The bridge accepts this allowlisted landmark only when the loaded adult is in its exterior worldspace and the reference is enabled. Invisible markers do not need a rendered mesh. Interior coordinates, unknown references, missing spatial APIs and other worldspaces are rejected. Native ownership and freshly observed proximity are required for arrival.

If Carlotta is observed in the same market space and within interaction range on arrival, the existing consent flow begins. Her stock is considered on her own decision turn. Otherwise the resident records only that she was not observed nearby, not that the shop was certainly closed. That memory suppresses another identical market search for four game hours. Inventory and need relief still require their existing verified commands.

![Observer map, camera controls and the remembered visit after reload](images/market-observer.jpg)

The observer marks known places with gold squares and active destination intentions with dashed lines; these are not navmesh path predictions. Select a resident, follow them in Skyrim, and inspect the destination, result and memory. The in-game inspector also reports remaining distance.

## Validation and remaining work

150 Python tests and 82 JavaScript tests passed locally. Coverage includes absent sellers, newly encountered sellers requiring consent, wrong spatial identity, missing package ownership, stale decisions, four-hour revisit suppression and invisible-reference routing.

This qualifies one outdoor landmark. Indoor shop/home navigation, discovery of opening hours, all-town initialization, simultaneous native routines, sustainable production and deeper social consequences remain unfinished. Native audio remains disabled for the existing diagnostic; generated overlay speech is separate, and lip sync is not implemented.
