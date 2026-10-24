# Whiterun Society

An experimental, open-source society simulation for Skyrim Special Edition: a city economy you can live inside.

Residents should work, trade with one another, consume goods, remember events and form different opinions. The player can participate as a resident or influence policy. Skyrim supplies the physical world; our simulation owns economic rules, decisions and evidence.

**Development prototype, not a complete society mod.** The isolated game starts directly in Whiterun with an observer camera. Actual inventory transfers, paid production, food consumption and generated voiced encounters have been demonstrated. Full daily routines, lip sync and sustained audio stability remain unfinished. The autonomous farm–bakery–household model still runs separately.

**Voiced encounters:** Ysolda and Carlotta discussed their bread disagreement using generated voices. A language model proposed intentions, Jev chose, and deterministic code delivered speech and recorded heard claims only after playback. Those memories reached Carlotta's next stock decision. The latest two-turn encounter took 47.098 seconds, including local synthesis and playback, with US$0.001638432 in reported model cost. Voices currently use the overlay audio channel; native audio is disabled for crash diagnosis. [Voiced encounters and evidence](docs/voiced-encounters.md) · [Finite market day](docs/market-day.md) · [Paid work](docs/paid-work.md) · [Human behaviour design](docs/human-behaviour.md).

![Generated speech and speaker close-up in the actual Skyrim observer overlay](docs/images/conversation-closeup.jpg)

Save-linked trade history, factual memories, trust and settled decision plans restored correctly from actual before/after Skyrim saves. Earlier audio-thread crashes still prevent accepting sustained save/load stability; active-plan recovery needs live qualification. The current planner owns one errand at a time; ordinary Skyrim routines resume after it releases the task. [Evidence and limitations](docs/acceptance.md) · [Agent control](docs/agent-control.md).

**Population milestone:** 26 loaded adult NPCs now have persistent starting needs, traits and household records, with two business charters referencing real inventories. Actual before/after Skyrim saves restored the population correctly. This does not yet extend native routine ownership to all of them. [Population state, visual overview and evidence](docs/population.md).

**Daily-life milestone:** the roster has expanded to 29 residents. Game-clock reviews advance needs, preserve quiet periods and queue feasible decisions without constant model calls. Live reviews and the later save restored correctly; an earlier restore exposed differing guard purses, so whole-town inventory persistence remains unresolved. The Papyrus router is now deployed and connected to decisions; see the newer routing experiment below. [Daily life, limitations and evidence](docs/daily-life.md).

**Routing experiment:** Idolaf took an owned task outside the original three-resident system, travelled from 3,840 to 247 units and returned to a vanilla package. Separate Jev trials selected a nearby visit and a deferral. The daily planner can now offer supported food errands to other loaded adults. Save P restored all compared fields; save N exposed gold differences in named residents as well as guards. [Routing, decisions and retained failures](docs/papyrus-routing.md).

**Resource milestone:** all 29 initialized residents received finite, once-per-lineage native grants: 660 gold, 58 bread and 20 grain in total, with 340 gold, 42 bread and 80 grain left in the explicit external pool. A cold restart restored all 29 funded inventories exactly. A subsequent game-clock review led a guard, Amren and Adrianne to choose and consume one loaf each; the post-meal save also restored correctly. Earlier unfunded guard-purse failures remain documented. [Resources, scheduled meals and evidence](docs/founding-resources.md).

**Latest employment experiment:** the planner now supports eligible workers beyond Ysolda, business stock reviews, bilateral job consent and save-bound contracts. Live trials completed 25 further meals, a stock review and two employer refusals across 28 decisions. Carlotta retained her reserve policy and did not hire; no new worker's completed shift is claimed. The final state restored correctly. [Employment, economic bottlenecks and evidence](docs/resident-employment.md).

**Live observer:** select any initialized resident, inspect needs, personality, memories and existing relationships, and control Skyrim's camera with follow, zoom, orbit and pan. Browser controls were exercised against the game; a tour-control conflict was found and fixed. The seated-rest plugin remains excluded after a failed cold launch. [Control room, screenshot and exact limits](docs/live-observer.md).

**Resident-chosen social encounters:** Amren chose Saffir; Adrianne chose Idolaf. Both pairs approached under owned tasks, accepted, completed generated voiced exchanges and separately appraised what they heard. Amren and Saffir felt supported; Adrianne and Idolaf stayed neutral. Both settled saves restored correctly. [Social decisions, actual game screenshot, costs and limits](docs/resident-social.md).

## Run the tests

Python 3.12+, no third-party Python dependencies:

```sh
python -m unittest discover -s tests -v
python town.py --days 30
node --test tests/bridge.test.cjs tests/inventory-transfers.test.cjs tests/movement.test.cjs tests/agent-routines.test.cjs tests/papyrus-router.test.cjs tests/endowments.test.cjs tests/production.test.cjs tests/speech.test.cjs tests/rest.test.cjs tests/observer-camera.test.cjs
```

The tests exercise conservation of currency and stock, insufficient resources, duplicate delivery, persistence and separate simulation checkpoints. A passing unit test is not proof that an NPC acted inside Skyrim.

## Architecture

1. A local simulation service holds balances, inventory, events and beliefs in SQLite.
2. A Skyrim Platform plugin reports observed game state and performs bounded commands on the game thread.
3. Event-triggered planners propose decisions. Validated economic rules decide whether they can happen.
4. Separate language and decision adapters propose and select intentions; local Kokoro generates speech. A completed utterance becomes a source-tagged memory, not proof that its words are true.

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

The helper starts the local service, deploys the bridge, and launches the isolated profile. It waits up to three minutes for a new game session to report a loaded player, cell and actor. A stale heartbeat cannot prove a new launch succeeded. Progress and timings appear in the console; `runtime/last-launch.json` records readiness evidence. By default the profile starts a fresh Whiterun observation scenario automatically, bypassing character creation and Helgen. Add `--save WS-YOUR-SAVE` to restore an existing managed scenario and verify its recorded local proof. This does not import a campaign save.

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

**Verified in the live game:** camera repositioning and close-ups, changing actor counts, actual gold/bread inventory, and the completed trade receipt. **Browser controls now verified:** resident selection, follow, zoom and orbit. The local `/observer` control room also exposes map panning, needs, memories and relationships. Native overlay mouse delivery remains separately unqualified. Camera collision avoidance is not implemented, so moving NPCs can occasionally cause occlusion. The standalone production simulation does not yet autonomously drive these NPCs.

The deployer hashes the UI into the bridge revision so HTML changes trigger hot reload. No game restart is needed for this development loop. The browser UI never receives the local service bearer token.
