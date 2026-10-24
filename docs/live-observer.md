# Live society control room

The observer is now a live local interface, rather than a recorded population snapshot. Open `/observer` on the running development service. In the current lab that is `http://127.0.0.1:17862/observer`.

![Live resident map and personality inspector](images/live-control-room.jpg)

Select a resident from the roster or map. **Follow selected** moves the Skyrim spectator camera. Zoom, orbit and height change its offset; east/west and north/south controls select a free overlook. The game stays in observer mode: there is no character setup or opening quest to complete.

The roster includes all 29 initialized adults, with live positions for loaded residents and retained records for unloaded residents. This is not every Whiterun inhabitant. The inspector shows five simulated needs, authored Big Five tendencies, commitments, remembered experiences and existing relationship/trust records. Empty relationships remain empty; there are no invented affection levels or family histories.

The activity panel separates the current plan, native travel, recorded conversation turns, queued opportunities and completed outcomes. Enterprises expose custodians and employment contract history. Inventories come from native observations; business accounts are not duplicated wallets. The UI does not expose the bridge bearer credential and cannot dispatch arbitrary native commands or spend on models. Local camera writes require the exact loopback Host, same Origin and a separate observer capability.

## Verified interaction

Chrome roster selection followed Amren (reference 108138), outside the original three demo residents. A matching request ID was reported by the game along with its actual free-camera position. Browser keyboard interaction with the sliders changed distance from 650 to 100, yaw from 225 to -360, and height from 300 to 40. The native camera followed those parameters. A game screenshot showed Amren selected, the projected marker, his live inventory and character inspector. Roof occlusion appeared at the initial offset: collision-aware camera positioning remains absent.

Testing found the old automatic tour could steal manual control. Manual camera requests now take precedence; the in-game tour pauses. Starting the tour explicitly releases manual control. The server clears a camera request once acknowledged so a later in-game choice is not overwritten by a stale web request.

The game loaded the previous verified checkpoint 432 in 40.3 seconds, including save restoration. All compared society and native inventory fields matched. Manual browser controls are verified; native CEF mouse delivery is enabled but still needs its own end-to-end input test.

![Selected Amren and live inspector in Skyrim](images/resident-follow-live.png)

A bounded director pass then completed six Jev choices: Bergritte, Ahlam, Idolaf, Saffir, Carlotta and Fralia each consumed a carried loaf. Across all 29 observed inventories, bread fell from 34 to 28, gold stayed at 964 and grain at 21. Six calls reported US$0.000355908. No new sale, wage, production or social interaction is claimed by this batch. Save Z at checkpoint 469 restored all compared society fields and native inventories, including the empty rest journal. [Compact evidence](evidence/live-observer.json).

Local verification: 124 Python tests and 78 JavaScript tests passed. Changed bridge and service-lifecycle checks were rerun after the camera-priority fix. The rebuilt original travel plugin retains its prior SHA-256, so the experimental builder extension did not change that artifact.

## Seated-rest experiment retained separately

Code now supports a bounded 30-game-minute bench break: a resident chooses rest; an owned SitTarget package targets an allowlisted unowned bench; exact furniture reference, native sitting state, proximity, package ownership and continuous game time must agree. Recovery is applied only after verified release. Occupancy, combat, interrupted attendance, unavailable sensors and clock jumps hold the event without recovery. The recovery amount is an authored gameplay rule.

The original `WhiterunRest.esp` builder passed binary readback, and deterministic bridge/backend tests passed. Its first cold launch hung during loading. The new plugin was removed from the active lab profile; the previous plugin set then loaded successfully. This correlation does not establish the hang's root cause. Rest is **not accepted in-game**, and the experimental plugin is not part of the current playable configuration. No seated recovery is claimed.

## Scope remaining

The current director executes one resident plan at a time in bounded runs. Whole-town concurrent action ownership, households with dependants, more production chains, prices responding to demand, politics and player interventions remain development work. Native audio is still disabled for crash diagnosis; previous generated voices use CEF playback, with lip sync unfinished.

Update: [resident-chosen social encounters](resident-social.md) now demonstrate partner choice, acceptance, nearby voiced speech and private appraisals in two live pairs. Concurrent independent economic work still needs actor-level ownership and is not claimed.
