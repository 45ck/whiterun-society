# Whiterun Society

An experimental, open-source society simulation for Skyrim Special Edition: a city economy you can live inside.

Residents should work, trade with one another, consume goods, remember events and form different opinions. The player can participate as a resident or influence policy. Skyrim supplies the physical world; our simulation owns economic rules, decisions and evidence.

**Development has started. This is not a playable release.** The current code implements a small standalone transaction ledger and scenario beliefs. In-game integration, autonomous production and consumption, generated dialogue, lip sync and game-save synchronization remain under development. Scenario beliefs currently use explicit rules, not a language model.

## Run the tests

Python 3.12+, no third-party Python dependencies:

```sh
python -m unittest discover -s tests -v
```

The tests exercise conservation of currency and stock, insufficient resources, duplicate delivery, persistence and separate simulation checkpoints. A passing unit test is not proof that an NPC acted inside Skyrim.

## Architecture

1. A local simulation service holds balances, inventory, events and beliefs in SQLite.
2. A Skyrim Platform plugin reports observed game state and performs bounded commands on the game thread.
3. Event-triggered planners propose decisions. Validated economic rules decide whether they can happen.
4. Speech and language providers will be replaceable, so local and hosted models can be compared on the same scenarios.

An unloaded citizen can participate in abstract simulation, but we must not claim they physically walked or spoke unless the game reports it. Pausing or closing the game should pause progression by default.

## Development setup

Use a legitimately owned copy of Skyrim Special Edition. The initial experiment targets runtime 1.6.1170 with SKSE 2.2.6 and an installed Skyrim Platform distribution. Compatibility is not yet demonstrated.

`tools/prepare_runtime.py --source "YOUR_GAME_DIRECTORY" --root "SEPARATE_LAB_DIRECTORY"` copies selected local game assets and existing bridge dependencies into an independent experiment directory and downloads the official Mod Organizer 2.5.2 portable archive. It does not modify the source game or copy saves. Profile and save isolation must be verified before launching. This script is an experimental development helper, not a general mod installer.

Do not commit game files, mod binaries, model weights, saves, credentials or runtime databases. This repository distributes only our source code and documentation. Skyrim and other dependencies retain their respective ownership and licenses.

## First playable acceptance criteria

- A real in-game handshake and observed NPC action.
- NPC-to-NPC buying and selling with finite stocks and budgets.
- Production, wages and consumption recorded with explicit causes.
- One shortage with competing interests and a consequential player intervention.
- Duplicate-safe commands and correct reconciliation after loading an older save.
- Evidence from a real play session, including response latency and player feedback.

## License

MIT for the original code in this repository. No affiliation with Bethesda or the creators of Skyrim, Cities: Skylines, SKSE or Skyrim Platform is implied.
