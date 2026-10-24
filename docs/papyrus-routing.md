# Resident routing through Papyrus

The isolated Skyrim installation now runs our original `WhiterunRouter.esp` and `WSSocietyRouter.pex`. A loaded adult outside the original three can receive a travel package. The planner can select that route; the engine must confirm binding, ownership and arrival before the simulation accepts it.

## Native evidence

Idolaf Battle-Born travelled toward guard 225366 from **3,839.78 to 246.83 Skyrim units** in **21.831 seconds** from request initialization to release request. Papyrus confirmed both aliases, the actor held our package `117442561`, and the final observation showed vanilla package `837714`. This was an explicit destination probe, not a model-selected journey. [Native samples and acknowledgements](evidence/papyrus-route-dd713154ac3ad667.json).

The preceding Idolaf-to-Adrianne probe confirmed binding and package ownership but started only 154.95 units away. Its distance-based test correctly failed; proximity is not evidence of a journey. [Retained result](evidence/papyrus-route-41a51c971bddb76e.json).

Two bounded Jev decision trials used initialized residents and authored meal-time events:

| Resident | Decision | Native result | Reported inference cost |
| --- | --- | --- | --- |
| Idolaf | Visit Adrianne, probability 0.52 versus defer 0.48 | Bound route, owned arrival, release and a `visited_only` memory. He was already 128.76 units away, so this proves the decision handoff rather than a long walk. | US$0.000041748 |
| Guard 1048823 | Defer | Recorded own decision; no travel, purchase or conversation | US$0.000041622 |

Each trial made one call to `typesafe/jev-1.14-20261014`. Neither generated dialogue or transferred resources. [Idolaf decision](evidence/router-decision-idolaf.json) · [Guard decision](evidence/router-decision-guard.json).

The next game-clock review reached checkpoint 190 with 29 residents and six currently observed residents able to use the routing interface. No meal event was eligible and no model was called. Availability describes the installed executor and current observations, not qualification of every possible route. [Review](evidence/router-daily-review.json).

## Save and resource limits

Save P at checkpoint 190 restored the decisions, memories, town, prior economy records and compared inventories exactly. Save N at checkpoint 179 restored society fields but failed its inventory comparison: gold differed for guards 225366 and 1048823, Idolaf and Olfrid. The cause remains unresolved; this extends the earlier guard-only finding. Do not claim a closed, persistent whole-town economy from these results. [N including failure](evidence/router-save-N.json) · [P](evidence/router-save-P.json).

The tests retain both failures and successes. Native audio remains disabled for the separate crash investigation. No new screenshot or manual interface qualification accompanies this experiment.

## Protocol

1. Stop our own quest and wait for it to stop. Never edit a vanilla quest.
2. Write resident and destination into separate one-entry FormLists; read both back.
3. Increment a positive exact-float request serial, then start the quest.
4. Papyrus obtains aliases internally, forces both references, checks them and writes the matching acknowledgement and status. JavaScript never receives an alias object.
5. Require matching acknowledgement, mailbox contents and owned package. Recheck proximity on the game side and simulation side.
6. Stop the quest and observe the package leaving the actor. A retained route can support the existing consent sequence. Loads and bridge reloads release owned tasks; a native 120-second lease limits abandoned ownership.

Only numeric IDs persist across JavaScript update callbacks. The plugin is additive: one quest, one travel package, two lists and three globals. VMAD properties link only to our records. The travel package references the owned game's standard Travel template; no game asset is redistributed.

Food planning now offers `seek_bread` to other observed, initialized adults when the router, seller and affordable offer are available. The bounded daily queue uses the same capability check. Missing sellers, unavailable routing and unsupported needs remain unmet. Independent work contracts are still limited to the existing Ysolda/Carlotta prototype.

## Reproduce

Build with .NET 10 and the locked Mutagen dependency, and compile with the pinned Caprica release documented in [daily life](daily-life.md):

```powershell
dotnet run --project tools/AgentPluginBuilder -- work/WhiterunRouter.esp
python tools/build_router_script.py --compiler D:\WhiterunLab\vendor\caprica-v0.3.0\Caprica.exe --output work
# Save and close the isolated game first. The installer rejects running Skyrim.
python tools/install_router.py --root D:\WhiterunLab --stage work
python tools/launch_demo.py --root D:\WhiterunLab --audio-diagnostic
python tools/verify_plan_save.py --root D:\WhiterunLab --name YOUR_EXISTING_WS_SAVE --restore
python tools/probe_movement.py --root D:\WhiterunLab --method package --dynamic --actor 108169 --target 225366
```

Both residents must currently be loaded and initialized; NPCs naturally entering buildings can make these particular IDs unavailable. The installer copies only our ESP and PEX; it never installs the compile-only base-class declarations. Profile configuration preserves existing load order and appends the new plugin. The save verifier now permits restoring a managed save from the launcher's uninitialized world.

Local verification: **97 Python and 60 JavaScript tests**, binary readback of both plugins, Papyrus compilation, the native probes and two real decisions. These are separate kinds of evidence; tests do not prove the entire town behaves naturally.
