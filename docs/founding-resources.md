# Finite starting resources and resident meals

The 29 initialized adult residents now have explicit starting resources in their actual Skyrim inventories. This is scenario initialization, not earned income. A finite external pool funds each grant once per resident in the saved lineage; household and business records do not create duplicate purses.

## Allocation

| Recipient | Gold | Bread | Grain |
| --- | ---: | ---: | ---: |
| Ordinary initialized adult, each | 20 | 2 | 0 |
| Carlotta, including food-enterprise capital | 100 | 2 | 20 |
| Total delivered to 29 residents | 660 | 58 | 20 |
| External pool remaining | 340 | 42 | 80 |

The authored pool began with 1,000 gold, 100 bread and 100 grain. It is not a resident wallet and does not replenish automatically. Family size, assets and wealth are not inferred from appearance. These are explicit prototype allocations, not a calibrated reconstruction of Whiterun's economy.

The service persists a prepared grant before authorizing native effects. Skyrim checks the bounded contract, adult classification and exact inventory at each delivery stage. Only a completed native observation debits the external pool and adds a receipt and factual memory. Drift, timeout and partial failure hold the operation rather than retrying blindly. Loading an older save selects its own grant history and remaining pool.

## Native results

Idolaf received 20 gold and two loaves; Saffir then received the same grant while her 3D was unloaded. The remaining 27 deliveries completed sequentially in 126.074 seconds. All 29 have committed receipts. Of those receipts, 22 explicitly report unloaded 3D, six report loaded 3D, and the first Idolaf receipt predates that flag. These are native inventory changes, not evidence that unloaded NPCs walked or acted physically. No model calls were required for distribution.

The bridge now reports a separate accounting inventory for initialized residents, including unloaded references. This does not add them to the visual/perceptual census. The service and visual overview distinguish native account observations from loaded actors.

The next bounded daily review made three actual Jev decisions: a Whiterun guard, Amren and Adrianne each chose to eat. Skyrim removed one carried loaf from each before simulated hunger fell from 1.0 to 0.4. Across the 29 observed accounts, bread fell from 62 to 59; gold stayed at 964 and grain at 21. These totals include pre-existing items as well as the grants. The three calls reported US$0.000140364 in aggregate cost. This trial did not demonstrate new sales, wages, dialogue or an eating animation.

## Save and restart evidence

| Save | Checkpoint | Result |
| --- | ---: | --- |
| WS-Resources-20261024-Q | 192 | Warm restore passed. After process restart, two unmodified guard purses differed; Idolaf's funded inventory remained exact. |
| WS-Resources-20261024-S | 248 | Cold launch and restore passed all compared fields, including native inventory for all 29 funded accounts. |
| WS-Resources-20261024-T | 267 | Post-meal warm restore passed all fields, including all 29 inventories and the three consumption records. |

Cold launch plus verified restore of S took 36.7 seconds. Explicit inventory modification may explain why these funded accounts persisted when earlier unmodified purses differed, but the engine-level cause is not established. The failed Q comparison remains in the evidence; this result does not establish indefinite persistence through respawns or every external engine change.

## Reproduce in the configured isolated lab

```powershell
python tools/endow_town.py --root D:\WhiterunLab --maximum 32
```

The batch uses initialized, natively observed accounts and skips committed grants. It stops on a delivery failure or session change. The first accounting heartbeat can require a service round trip; the single-resident helper waits read-only for that roster before requesting a grant.

To reopen an existing verified local scenario without a playthrough:

```powershell
python tools/launch_demo.py --root D:\WhiterunLab --audio-diagnostic --save WS-Resources-20261024-T
```

That named save and its local proof must already exist. Saves and game assets are not distributed in this repository. The diagnostic flag retains disabled native audio; overlay voices use their separate channel. This is not a fix for the earlier native-audio crashes.

## Verification and remaining scope

Local verification passed 106 Python tests and 68 JavaScript tests. New checks cover finite-pool exhaustion, duplicate grants, save lineage, partial delivery, hot reload, inventory drift, unloaded accounting and adult classification. The live results above are separate evidence from those tests.

The overview now shows current inventories, grant receipts and remaining external resources. Its new presentation has not been manually inspected in-game. The initialized roster is not every Whiterun inhabitant. Broad employment, sustained production chains, housing and kinship, endogenous prices, fuller social routines and consequential player actions remain unfinished; paid work still uses the earlier Ysolda/Carlotta prototype. Needs and personality parameters are authored simulation heuristics, not validated psychometrics.

Evidence: [resource grants](evidence/founding-resources.json), [three scheduled meals](evidence/founding-daily-life.json), [Q including the failed cold comparison](evidence/resources-save-Q.json), [S cold restore](evidence/resources-save-S.json), [T post-meal restore](evidence/resources-save-T.json). Related: [daily life](daily-life.md), [Papyrus routing](papyrus-routing.md), [paid work](paid-work.md).
