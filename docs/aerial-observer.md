# Aerial map, resident portraits and owned production

The RTS overlay and local control room now use an actual overhead Whiterun capture with live resident markers. Seven portraits are captured from the running game. Septim coin symbols identify money while the accounting key remains `gold`.

![Actual selected-resident inspector and calibrated aerial map](images/aerial-portrait-inspector.jpg)

The selected view was driven through the authenticated camera API. It demonstrates the rendered face, needs, traits, memories and map, **not successful physical mouse input**.

## What the map represents

The background is a static game capture, not a live aerial video stream or all of Skyrim. It covers the Whiterun city area; the far northern edge of Dragonsreach is outside this capture. Three native ground projections establish its coordinates. Resident elevation adjusts the projection around the camera centre. Only loaded residents in the captured exterior worldspace and image bounds receive markers. An unloaded resident remains in the roster but has no invented position.

The same renderer serves the in-game overlay and browser control room. The browser fades stale markers and disables their controls. Markers and in-game roster buttons retain DOM identity between updates so refreshes do not discard focus or an interaction. A previously received remote camera request cannot override a later local choice or replay after camera reset.

The screenshots were captured in temporary daylight in the isolated lab. The previous save was restored afterward; all 17 compared society/inventory fields matched. The game clock and lighting returned with the save. Original screenshots remain under `docs/images`; SVG viewports crop their display without changing the image files. The artwork shown is Skyrim gameplay, not original character art or a generated illustration.

## Portrait coverage and currency

Current captures: Amren, Saffir, Carlotta, Adrianne, Anoriath, Ysolda and Brenuin — **7 of 29 enrolled residents**. The asset manifest pairs a reference ID with its base ID. Missing, unloaded, replaced or unverified identities show initials; other characters never borrow a face because of their name. New captures can extend the manifest without adding NPC-specific simulation logic. Appearance changes within the same reference/base pair still require recapture.

The original coin UI symbol is a gold `S` medallion labelled **Septims**. It is a presentation symbol, not an extracted game icon or a new resource. Selected and loaded residents sort ahead of unloaded ones in the in-game roster. Audio settings can be expanded when needed; Realtek remains the selected voice output.

## Owner-operated production

An active business owner who is also its inventory custodian can now choose to work their own stock. Eligibility comes from the current charter, owned inventory, finite position and verified standing package. The offer binds the charter revision and policy; changed terms invalidate the decision.

The single-account native contract requires ten game minutes in this trial, the expected package and attendance within 100 game units. Paused time earns no labour credit; clock jumps and interrupted attendance hold the transaction. One grain becomes two bread, with no wage transfer. Completion requires an acknowledgement **and** matching physical inventory. Household reserve policy and hunger do not change merely because bread was made. Partial effects require reconciliation; input/output are not repeated blindly.

| Evidence | Observed result |
| --- | --- |
| Real Jev review, existing owner opportunity | Chose to eat, despite the available owned-production option |
| Decision latency and reported cost | 0.781 s; US$0.00021063 |
| Controlled native recipe fixture | 20 → 19 grain; 5 → 7 bread; 102 → 102 septims |
| Attendance receipt | 10 game minutes; expected package owned during work; zero-distance anchor |
| Fixture rollback | `WS-Owner-20261025-BG`, checkpoint 1904; all 17 fields matched |

![Actual native recipe qualification with aerial map and roster](images/owner-production-aerial-ui.jpg)

This screenshot is an explicit qualification fixture, **not a spontaneous model-chosen work event**. Its older “Bread & wages” heading has since been corrected to “Owned production.” There is still no oven interaction or productive animation; the owner stands under an owned package. There is one authored recipe, not a full upstream supply chain or market-discovered prices.

[Machine-readable, bounded evidence](owner-production-evidence.json)

## Validation and open work

319 Python and 151 JavaScript tests passed locally. Coverage includes changed owners and charter terms, zero-gold owner eligibility, exact conservation, interrupted work, input-only recovery, projection/elevation, identity mismatch, stale markers and remote-camera replay. Native inventory output and save rollback are separately evidenced above.

Injected Windows clicks were still not reliably delivered to the embedded browser during visual qualification. API camera control and native rendering worked. Full mouse/keyboard RTS acceptance remains open; do not treat unit tests or screenshots as proof that every control works for a player. The portrait set is partial. Lip sync, gaze, natural dialogue scoring and all-day routines remain incomplete.

### Cursor focus follow-up

The bridge now reapplies browser focus across two update frames after the UI heartbeat arrives. This avoids NirnLab's cached pre-load focus flag skipping native cursor initialization. The native Skyrim cursor became visible after deployment. Automated selection still failed: a click aimed at Adrianne's roster row produced a pointer event at `(1280, 0)` and no recorded click. This is partial focus recovery, not completed RTS input acceptance. The 152 JavaScript tests pass, including page-load timing, save-load reset and preserving F8 focus release. The previous 319 Python result belongs to the preceding economy/media revision; Python code did not change in this follow-up.

The bounded live session settled after six events, including Brenuin approaching Carlotta, delivering a voiced offer and receiving a refusal. It was paused before bridge deployment. Refusal is an outcome, not a completed sale.

## Toward a continuous broadcast

A 24/7 economy-and-drama stream is a product direction, not a running service. Before broadcasting: durable event history across restarts, bounded inference spending, audio recovery and silence metrics, save/crash recovery, a multihour soak, and a scene director that frames real activity without fabricating it. Public stream setup and publication have not been started. Existing Play sessions remain bounded to 96 events or 60 minutes.
