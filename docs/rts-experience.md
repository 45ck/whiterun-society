# RTS experience and audio diagnosis

The active product is an RTS city economy/social simulation. First-person play and direct player dialogue are deferred. Skyrim executes movement and animation; the simulation chooses bounded resident tasks. Native routines still run when our tasks release. This is not full-time agent ownership of every resident.

## Controls and visual information

- Free RTS overview is the default. Pan, rotate and zoom; select an on-screen resident to inspect, or use the roster to follow. Movie view follows the active resident/speaker only when requested. Automatic tours are removed.
- Play starts a session of up to **96 events or 60 minutes**, with at most 16 model calls per event. Pause lets the current event settle. This is not an always-running background service, and no models run just to animate the interface.
- Native player movement, fighting and activation are disabled. Menus remain available.
- The control-share donut separates confirmed current agent packages, native scenes, other native routines, unknown activity and unloaded residents. It does not equate model calls or intended tasks with native control.
- Resource cards show separate gold, bread and grain totals with account coverage. Missing values stay unknown; overlapping business/household custodians are not counted twice. Need bars show authored simulation state. Economic totals are verified cumulative save events, including earlier qualification experiments.
- The resident roster now labels current speaking/listening, plans, journeys and native activity. Paused status takes precedence over an old completed encounter.

## Why the town looked idle and silent

The director was idle at the start. A connected overlay alone does not schedule new resident decisions. Agent task release also returns residents to native Skyrim packages. The new Play/Pause state and control-share chart make both visible.

Windows output routing changed during diagnosis. Realtek was initially the default at 1% volume and was raised to 20%; later the default became the Yeti microphone's headphone output. The game voice process was observed on that output. Raising one device does not fix another device's route. The UI now shows the browser-reported output, permits selection of available speaker devices, and provides an explicit saved-sample audio check. It never requests microphone access or changes Windows' global defaults. Output selection uses the browser's [permitted speaker-device API](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/setSinkId); unavailable/denied outputs report failure.

The audio check is labelled as a saved sample. It creates no conversation, resident memory or economic event. CEF playback completion, a Windows audio signal and a person hearing the speakers are separate observations. A 2.74-second saved-sample check completed on the Yeti output: the CEF process meter peaked at 0.270 and its endpoint at 0.431, with application volume 1 and mute false. Eight compared society fields stayed unchanged. Realtek showed no signal during that check. This confirms the output route, not that a person heard it.

Skyrim ambience is still disabled in this diagnostic lab; NPC voices use the independent CEF overlay channel. Lip sync is still pending.

## Native qualification

[Compact evidence](evidence/rts-experience.json) preserves two completed runs with **12 event entries**, including a voiced night-time refusal, bread consumption, quiet passes and five simultaneous agent-owned journeys. Four members of the travel cohort reached a market without an observed seller; one journey failed. Cleanup was verified before other residents continued. There was no successful sale in these runs. These failures are retained, not counted as realistic economic success.

The native bridge confirmed RTS free mode and movement/fighting/activation disabled. A later explicit movie request was acknowledged and followed the active speaker. The new dashboard is served in both the in-game overlay and local control room. Its counts are sensor-based operator information and are never added to residents' private knowledge.

Local checks: **300 Python tests and 128 JavaScript tests**, including actual HTML execution in jsdom, output-routing failure, diagnostic audio separation, play/pause messages, no automatic camera tours, accounting coverage, ownership classification, service controls and game-load reset. This is not a new rendered screenshot or native mouse-input acceptance test.

Checkpoint acknowledgements now use a short polling interval, and consent/thinking phases keep the active cadence. Workers no longer add a fixed pause after every mutation. Claim binding, save/session checks and one outstanding request remain required. A matched before/after live negotiation timing comparison is still outstanding.

## Remaining work

Persistent agent-owned daily routines, broader production chains, seller availability/opening hours, realistic market prices, political controls, sustained conversation quality, lip sync and native interaction/UI acceptance remain unfinished. Counts of possibilities or completed model calls do not establish human realism.

Save `WS-RTS-20261025-BA` was recorded at checkpoint 1403 and restored with all 17 compared society/inventory fields matching.
