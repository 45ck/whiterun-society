# Independent resident journeys

This page preserves the initial two-person experiment. The [later bounded director run](town-progress.md) verified seven simultaneous journeys, plus save/load persistence and follow-up scheduling fixes.

Amren and Adrianne independently chose to check the market. Skyrim ran two different owned travel packages at the same time, delivered both residents to the destination, and released each package independently. Both recorded that Carlotta was not within interaction range at their respective arrivals.

![Amren under independent control while Adrianne travels in another slot](images/parallel-native.png)

| Live measurement | Result |
|---|---|
| Cohort | `parallel-food-20261024-A` |
| Decisions | Two Jev calls; both chose `check_market` over `defer` |
| Model | `typesafe/jev-1.14-20261014` |
| Inference | 0.812 seconds per call, issued concurrently |
| Reported cost | US$0.000138894 total |
| Total observed cycle | 74.62 seconds |
| Concurrent package ownership | Two packages; 3,538 overlapping frame samples |
| Amren | 3,374.42 → 247.41 game units; package 150996993 |
| Adrianne | 4,178.59 → 247.61 game units; package 150997009 |
| Release | Both confirmed; finishing Amren's route did not stop Adrianne's |
| Resources and needs | All 29 native inventories unchanged; neither resident received hunger relief |
| Save/load | `WS-Parallel-20261024-AI`, checkpoint 540; all recorded comparisons matched after a fresh load |

[Compact evidence](evidence/parallel-routines.json) contains each result, probability distribution, movement receipt, inventory comparison and save/load checks. These were developer-selected pending opportunities; each model selected its own action. The eight-slot capacity is built and checked structurally, but this live test qualified **two**, not eight, simultaneous journeys.

## How it works

`WhiterunLanes.esp` adds eight separate quests, packages and mailbox sets. Each uses the existing original Papyrus router script with its own aliases and serial acknowledgement. A slot cannot be assigned twice, nor can one resident occupy multiple slots in a cohort. Starting, finishing or failing one route does not stop another slot. Native handles remain within individual update callbacks.

The service persists all inference claims before any model request. Each resident receives only their own profile, needs, inventory, memories and relationship state, plus authored public-place knowledge. The worker issues at most four model requests concurrently and no more than eight total per cohort. There are no automatic retries. Choices are validated again before the native command is prepared and bound to the save checkpoint.

During travel, Skyrim executes every active slot each frame. The server records completion only from matching actor, slot, destination, ownership, proximity and release evidence. A missing or interrupted resident can fail independently. An unverified native release leaves the reconciliation guard active. Loading an unfinished cohort holds it rather than replaying model calls or journeys.

The current cohort vocabulary is deliberately explicit: `check_market` or `defer`. Reaching the market is not a sale. Seller presence is sampled at each resident's completion; resources and needs remain unchanged. Separate normal events still own negotiation, purchase, production, rest and conversations.

![Observer with independent resident activities and camera controls](images/parallel-observer.jpg)

## Running a bounded session

Build `WhiterunLanes.esp` with `tools/AgentPluginBuilder`, stage it alongside the existing compiled `WSSocietyRouter.pex`, and use `tools/install_router.py --lanes` while the isolated game is stopped. Launch with both `--experimental-rest` and `--experimental-routines` if the selected save uses them. The current lab still requires the explicit `--audio-diagnostic` mode.

An older managed save may be migrated with `--allow-added-plugin WhiterunLanes.esp`. That option accepts only an appended plugin; every earlier enabled plugin, order and recorded generated-file hash must remain identical. New saves record the additional plugin hash normally. The first launch took 131.7 seconds; it was allowed to finish rather than being duplicated during loading.

The daily director now accepts:

```powershell
python tools/run_daily_life.py --root D:\WhiterunLab --model-config D:\WhiterunLab\runtime\jev-config.json --max-events 8 --parallel-journeys
```

Provide the authorized model key through the configured environment variable. The director groups two to eight eligible food-search events within the remaining event budget, then falls back to normal event handling for others. Selection, capacity and budget behaviour are unit tested; the live run above invoked the cohort worker directly. This flag does not start a permanent background service.

## Validation and limits

The full local suite passed 159 Python and 86 JavaScript tests; the added director-selection test also passed, bringing the Python coverage to 160 distinct tests. Focused tests cover independent release, missing actors, duplicate slots, deferral, stale claims, load interruption, guarded plugin migration and no resource/need effects.

This is concurrent **travel**, not a completed concurrent society. Trades and speech remain serialized. Eight-way native movement, indoor destinations, broad production chains, family households, politics, continuous scheduling and long-term stability remain unqualified. Psychology and needs remain authored gameplay models. The observer exposes these distinctions rather than presenting intentions as completed economic activity.
