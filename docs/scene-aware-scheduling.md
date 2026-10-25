# Residents can be occupied, without stopping the town

**Update:** explicit agent-priority mode can now request a verified handoff from a native scene. The passive occupancy checks described below remain active before and after that handoff. [Current scene-control protocol](native-scene-handoff.md)

An agent's intention is not ownership of an NPC's body. Skyrim may already have that resident in a scene, combat or a sleep transition. The scheduler now observes those conditions before offering new travel or social opportunities, and checks again before accepting a travel decision and while acquiring/executing its native package.

The bridge reads `ObjectReference.GetCurrentScene`, `Actor.IsInCombat`, `Actor.GetSleepState` and the current package. The owned SKSE source files document the first three APIs; the live lab also returned all four fields. Scene ID zero means no current scene. A failed or missing native API returns unknown, never a fabricated zero. Current bridge observations always include the activity object; legacy observations without the entire object retain the older protocol behavior.

## What happens to the resident

1. A scene, combat or sleep transition makes a new activity temporarily unavailable. The pending need remains unmet; no inference, invented purchase or friendship gain follows from waiting.
2. A later observation can make the same pending opportunity available again. This does not require an LLM to poll the scene every frame.
3. If occupancy changes during inference, the proposed trip is held before departure. If it changes during routing, our route releases without stopping the vanilla scene.
4. After alias binding, a package that has never been acquired gets a **15-second acquisition limit**. A successfully acquired walk keeps the existing 120-second journey limit. Engine package identity and a finite failure reason remain in the receipt and the resident's failed-journey memory.

The observer exposes current occupancy alongside the resident's intention. These are separate: a desire to find food does not prove the engine let the resident leave.

## What happens to everyone else

The bounded director can continue after a held travel cohort only when the committed state proves all members settled, every issued route released, the daily queue agrees with the receipts, and no checkpoint, inventory effect, command or active conversation remains unresolved. An overlapping conversation must have completed. A worker error, session change or uncertain release still stops the run.

The failed member stays held and gets `continued_other_residents: true` in the director receipt. Its event is removed from that run's cached pending list, so it is not replayed. This is failure isolation, not a conversion of failure into success or an automatic retry.

## Evidence and limits

Live activity sensing identified **Heimskr (108162)** in **scene 237915**, with **package 237916**. The earlier overlap report incorrectly called that actor Ahlam; the README and compact evidence have been corrected. The simulation's native census already had the correct names. Ahlam is a separate resident, 108197.

The initial four-event director qualification exposed a separate startup bug: a transient social opportunity has no stored daily status, but the travel selector attempted to read it. That run stopped before any model inference. The selector now filters event kinds before examining travel fields; the failed receipt remains retained.

Tests exercise scene entry/exit, unknown sensing, changed occupancy during inference, package acquisition timeout, unchanged normal travel, and the full director sequence in which a held released cohort is followed by a third resident's decision. They also verify that an unverified release prevents that next worker. These controlled tests do not establish how often real scenes interrupt city-wide plans, human dialogue realism, gaze accuracy or the capacity of a complete autonomous city.

The corrected four-event director run completed **Olfina–Nazeem small talk (three delivered turns), Olfina's meal, Bergritte–Brenuin small talk (four delivered turns), and Ria's meal**. Both encounters released their native attendance. Across 29 compared accounts, bread changed from 25 to 23, gold remained 964 and grain remained 20. The only inventory changes were the two consumed loaves. Twenty-nine model calls reported **US$0.002905604**; this is retained response usage, not an account billing audit. Save `WS-SceneAware-20261025-AW`, checkpoint 1093, restored all 16 compared fields. [Compact native evidence and transcripts](evidence/scene-aware-director.json)

Reply dispatch gaps remained **9.995–12.578 seconds**. The live run had no new held travel cohort, so it does not qualify native continuation after failure, nor the new acquisition timeout. Its contribution is a complete bounded scheduler run through two conversations and two inventory-backed meals while busy-scene sensing was active.
