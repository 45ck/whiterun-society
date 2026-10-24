# Whiterun Society

An experimental, open-source society simulation for Skyrim Special Edition: a city economy you can live inside.

Residents should work, trade with one another, consume goods, remember events and form different opinions. The player can participate as a resident or influence policy. Skyrim supplies the physical world; our simulation owns economic rules, decisions and evidence.

**Development prototype, not a complete society mod.** The isolated game starts directly in Whiterun with an observer camera. Actual inventory transfers and save-linked trade memories have been demonstrated. The autonomous farm–bakery–household model still runs separately; full daily routines, generated dialogue, lip sync and stable save/load remain under development.

**Latest experiment:** event-triggered Jev decisions now select an actual destination and seller response. Ysolda chose to seek bread, our travel package took her to Carlotta, and Carlotta declined. No goods or money moved. Both remembered the refusal; the next event received those memories but repeated the same choices. This is real, bounded agency, not accepted human believability. [Live evidence](docs/agent-control.md#resident-selected-errand-and-consent) · [Human behaviour design and research](docs/human-behaviour.md).

![Jev choices and refusal memories in the actual Skyrim observer overlay](docs/images/jev-resident-decisions.jpg)

Save-linked trade history, factual memories and trust restored correctly from actual before/after Skyrim saves. A recurring audio-thread crash still prevents accepting save/load stability. Saved decision-plan restoration has unit coverage but still needs a real save/load experiment. The current planner owns one errand at a time; ordinary Skyrim routines resume after it releases the task. [Evidence and limitations](docs/acceptance.md) · [Agent control](docs/agent-control.md).

## Run the tests

Python 3.12+, no third-party Python dependencies:

```sh
python -m unittest discover -s tests -v
python town.py --days 30
node --test tests/bridge.test.cjs tests/inventory-transfers.test.cjs tests/movement.test.cjs tests/agent-routines.test.cjs
```

The tests exercise conservation of currency and stock, insufficient resources, duplicate delivery, persistence and separate simulation checkpoints. A passing unit test is not proof that an NPC acted inside Skyrim.

## Architecture

1. A local simulation service holds balances, inventory, events and beliefs in SQLite.
2. A Skyrim Platform plugin reports observed game state and performs bounded commands on the game thread.
3. Event-triggered planners propose decisions. Validated economic rules decide whether they can happen.
4. Speech and language providers will be replaceable, so local and hosted models can be compared on the same scenarios.

An unloaded citizen can participate in abstract simulation, but we must not claim they physically walked or spoke unless the game reports it. Pausing or closing the game should pause progression by default.

## Development setup

Use a legitimately owned copy of Skyrim Special Edition. The initial experiment targets runtime 1.6.1170 with SKSE 2.2.6 and the locally installed Skyrim Platform 2.9 build using NirnLab UI. The live connection has been demonstrated on that setup; compatibility with other distributions is untested.

`tools/prepare_runtime.py --source "YOUR_GAME_DIRECTORY" --root "SEPARATE_LAB_DIRECTORY"` copies selected local game assets and existing bridge dependencies into an independent experiment directory and downloads the official Mod Organizer 2.5.2 portable archive. It does not modify the source game or copy saves. Profile and save isolation must be verified before launching. This script is an experimental development helper, not a general mod installer.

Do not commit game files, mod binaries, model weights, saves, credentials or runtime databases. This repository distributes only our source code and documentation. Skyrim and other dependencies retain their respective ownership and licenses.

## Observer launch

After completing the portable Mod Organizer setup with profile-specific saves and INIs and an executable named `SKSE` pointing at the isolated loader:

```powershell
python tools/launch_demo.py --root D:\WhiterunLab
```

The helper starts the local service, deploys the bridge, and launches the isolated profile. It waits up to three minutes for a new game session to report a loaded player, cell and actor. A stale heartbeat cannot prove a new launch succeeded. Progress and timings appear in the console; `runtime/last-launch.json` records readiness evidence. The profile starts a fresh Whiterun observation scenario automatically, bypassing character creation and Helgen. It does not load a campaign save.

Observer mode protects the player from combat and uses a raised free camera. The game runs while unfocused so development does not stop NPC routines. Nearby actors are read from the engine, filtered for loaded 3D, and reported every two seconds. Only numeric form IDs survive between frames; native handles are reacquired before commands. The separate economic simulation is not yet driving those actors. A prepared playable character and a return-to-player control are future work.

## Physical trade journal

The authenticated local /world/trade endpoint quotes against observed bread and gold. It writes an immutable prepared checkpoint in timeline.sqlite, asks Skyrim to bind that checkpoint, and only then transfers goods and payment. The next committed checkpoint includes the confirmed trade, factual memories and trust changes. Loading a save selects its checkpoint rather than the latest database state. Retries with the same event ID return the original record.

A changed save/session, unexpected inventory or incomplete operation places the command on hold. Further physical trades stop until it is reconciled. Before/after save restoration now passes for inventories, trade history, memories and trust; recurring audio crashes and in-game mid-trade restore still require qualification. The older `/scenario/trade` endpoint and `society.sqlite` remain standalone test simulation; their balances are not game inventory.

## First playable acceptance criteria

- A real in-game handshake and observed NPC action.
- NPC-to-NPC buying and selling with finite stocks and budgets.
- Production, wages and consumption recorded with explicit causes.
- One shortage with competing interests and a consequential player intervention.
- Duplicate-safe commands and correct reconciliation after loading an older save.
- Evidence from a real play session, including response latency and player feedback.

## License

MIT for the original code in this repository. No affiliation with Bethesda or the creators of Skyrim, Cities: Skylines, SKSE or Skyrim Platform is implied.


### In-game spectator demo

![Actual in-game spectator overlay and resident camera](docs/images/spectator-ui.jpg)

Captured in the running isolated Skyrim installation; this is not a mockup.

The isolated game now displays a transparent society panel over Whiterun: observed resident inventories, actor positions, and a receipt for the verified physical bread trade. A guided camera tour changes every 12 seconds between the market, Carlotta, Ysolda, the trade pair, and the approach. It starts without player input.

**Verified in the live game:** camera repositioning and close-ups, changing actor counts, actual gold/bread inventory, and the completed trade receipt. **Still being qualified:** native mouse delivery. Manual camera controls are deliberately disabled in this preview; the automatic tour remains usable. Camera collision avoidance is not implemented, so moving NPCs can occasionally cause occlusion. The standalone production simulation does not yet autonomously drive these NPCs.

The deployer hashes the UI into the bridge revision so HTML changes trigger hot reload. No game restart is needed for this development loop. The browser UI never receives the local service bearer token.
