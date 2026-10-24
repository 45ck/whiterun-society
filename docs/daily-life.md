# Game-clock needs and scheduled opportunities

The population now contains **29 observed residents** after a second census added Ysolda and two more guards. A bounded director updates their simulated needs using Skyrim's observed game clock. It can queue meal decisions and pass them to the existing Jev worker without repeatedly prompting every resident.

## Rules implemented

- Review at most once per 15 game minutes; unchanged game time causes no growth or new queue entries.
- Advance hunger by 0.055 and fatigue by 0.025 per game hour. Social pressure grows by 0.018 plus 0.025 times authored extraversion per hour. Values cap at one. These are tunable gameplay parameters, not validated human physiology or psychometrics.
- Review a resident's opportunities at most once per game hour. Hunger at least 0.6 permits a meal review when the resident has carried bread or a currently qualified, affordable seller route.
- Unsupported food, rest and social actions remain unmet. Unloaded people progress abstractly; no walking, sleeping, speaking or working is inferred.
- Keep at most one outstanding opportunity per resident. A saved claim precedes each model call. Queue status follows observed completion or a held outcome.
- Scheduled meals do not apply the old demonstration event's extra 0.35 hunger. Food use accounts for elapsed game time before the verified reduction, then subsequent reviews age only the post-meal period.
- Observe current weather/outdoor status without inventing past exposure or reducing needs merely because a plan was proposed.

The director is explicitly bounded to three resident events, five inference calls per event, and up to 600 seconds of watching. No worker is left running indefinitely. Closing, loading or losing the game connection stops the worker. This is not yet a complete autonomous town calendar.

```powershell
# Review only; no model configuration or paid calls needed.
python tools/run_daily_life.py --root D:\WhiterunLab --watch-seconds 50

# Execute up to three eligible opportunities using the configured environment key.
python tools/run_daily_life.py --root D:\WhiterunLab --max-events 3 --model-config D:\WhiterunLab\runtime\jev-config.json
```

## Live evidence and limits

The first review reached checkpoint 176. A subsequent bounded watch completed two reviews and reached checkpoint 179. The final population state contained eight quiet intervals, twelve unloaded residents, seven unmet food needs and two unmet social needs. No executable event was eligible, so these live runs made **zero model calls** and no economic transfers. Eligible queued consumption is covered by a deterministic integration test, not yet a live scheduled-consumption demonstration.

An intervening watch stopped with a changed-session error when the development bridge was reloaded. It made no calls and did not continue against the new session. [Successful and interrupted runs](evidence/daily-life-live.json).

Actual save M at checkpoint 179 restored town state, people, prior plans and all compared inventories exactly. Earlier save K at checkpoint 175 restored society fields, but guards 225408 and 225392 had different carried gold after loading (5 → 9 and 7 → 4). The cause is unresolved. Native actor inventories therefore cannot yet support a claim of whole-town asset persistence or closed-economy conservation. [K, including its failed inventory comparison](evidence/daily-save-K.json) · [M](evidence/daily-save-M.json).

The game overlay now has a town-needs card. The offline population overview can be regenerated from the latest director evidence. The revised overlay has been deployed but its rendering and manual interactions have not been visually qualified.

## Arbitrary resident movement

Two explicit Sigurd-to-Carlotta probes failed because the installed JavaScript bridge returned no usable reference aliases, including after the quest started. Neither is accepted as movement. [First probe](evidence/dynamic-alias-b0be2a0649f7d7bb.json) · [Startup-aware probe](evidence/dynamic-alias-f517e5cc66ab35a1.json). These probes used the old JavaScript alias path. The replacement Papyrus path is now demonstrated in the [new routing experiment](papyrus-routing.md).

This matches the earlier finding in [agent control](agent-control.md). The upstream [native object conversion](https://github.com/skyrim-multiplayer/skymp/blob/main/skyrim-platform/src/platform_se/skyrim_platform/CallNative.cpp) searches ordinary form types when resolving returned objects; an alias conversion limitation remains the working hypothesis. Existing fixed routes continue to be the qualified movement path. Completion now also waits for the owned package to leave the actor, even after the quest stops.

An original Papyrus adapter, `papyrus/WSSocietyRouter.psc`, keeps alias operations inside Papyrus. It reads actor and destination references from a form-list mailbox, verifies assignment, acknowledges a request serial and expires abandoned routes. It compiles successfully with [Caprica v0.3.0](https://github.com/Orvid/Caprica/releases/tag/v0.3.0) using our compile-only interface declarations. The release archive SHA-256 is `0037e54cf3a1021e976278d9a637e8ae541aaf9ebeb8d274b6c2cfe32f4ee559`.

```powershell
python tools/build_router_script.py --compiler D:\WhiterunLab\vendor\caprica-v0.3.0\Caprica.exe --output work\papyrus-stage
```

At the end of this earlier experiment the adapter was staged only. The subsequent [Papyrus routing experiment](papyrus-routing.md) built and installed its original quest, optional aliases, two reference mailboxes and bridge integration, then demonstrated native travel. Compile-only base declarations must never be installed into the game. No runtime plugin or game asset was replaced for the earlier failed JavaScript probes.

Next: expand qualification of that adapter, address resident inventory persistence, give production and household endowments explicit sources, and connect supported social/rest/business actions to the daily queue. These are required for the requested whole-town society.
