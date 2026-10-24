# Dynamic choices, personal knowledge and RTS observation

25 October 2026. This slice joins current-population choices, a personal identity ledger, Mercury cloud dialogue and RTS observation in the same Skyrim save.

![Actual Skyrim RTS overview with native resident projections](images/rts-live-overview.jpg)

The game renders an elevated overview, moving resident markers and a camera panel. The browser control room changed the native camera and inspected personal knowledge and relationships. Injected clicks and F7 did not activate the in-game controls during this run, despite pointer hover and confirmed script loading. Their end-to-end input path remains unqualified. The screenshot proves rendering, not successful button use.

## What changed

- Each resident's `known_people` ledger distinguishes strangers, familiar unnamed people and learned self-reported names. A name is learned only after confirmed nearby playback of a supported self-introduction. Old saves remove later knowledge. The initial recognizer supports the literal `My name is <speaker profile name>.` convention; aliases, third-party introductions and general linguistic extraction are unfinished. Existing historical speech memories are preserved, not retrospectively interpreted as identity records.
- Social and economic contexts use that resident's personal view of other people. Seller choices come from current public business capabilities and current routing availability, without exposing another person's private inventory. A seller changing during a decision invalidates that destination. Public enterprise charters remain authored scenario information.
- An operator-requested conversation in an initialized town now selects an eligible current resident, who chooses a partner or declines. The partner independently consents. The fixed two-person encounter remains only a pre-census compatibility fixture. Scheduled social opportunities remain supported.
- RTS camera code provides bounded pan, zoom, rotation and drag, with projected resident selection and an inspector. Browser control-room selection, knowledge and relationship tabs work against the live save. The in-game controls still need input qualification; first-person return is unfinished.

## Live cloud encounter

The operator offered one opportunity. Carlotta chose Ysolda from the current nearby candidates, approached using an owned native task, and Ysolda accepted. Mercury 2.5 through Inception proposed two alternatives per turn; Jev selected the line; Kokoro synthesized it. Both nearby audio deliveries completed, the movement task released, and the residents appraised what they heard.

Carlotta said: “I'm glad we agree that waiting for steadier supplies is the safest path forward.”

Ysolda replied: “I'm glad we see it the same way. When the market calms, I'll be happy to help you out.”

These lines continue their earlier remembered supply discussion. They do not establish a new market fact or execute a promise. Carlotta appraised the exchange neutrally; Ysolda chose `felt_supported`. Both recorded familiarity. Neither introduced herself, so the new identity ledgers recorded a familiar unnamed person rather than inventing a learned name.

| Measurement | Observed result |
| --- | --- |
| Complete encounter, including approach, synthesis, playback and persistence | 58.811 seconds |
| Model requests | 2 Mercury language requests and 6 Jev decisions |
| Mercury request times | 1.750 and 1.610 seconds |
| Local synthesis workers | 5.735 and 3.828 seconds |
| Spoken audio | 4.839 and 4.660 seconds |
| Reported language cost | US$0.00022348 |
| Reported cost across all eight model requests | US$0.000718912 |
| Saved and restored checkpoint | 648 |
| Save restoration comparisons | All 14 fields matched, including people, conversation, town and native inventories |

[Context, selections, provider usage, delivery receipts and save comparison](evidence/dynamic-society-live.json). These are provider-reported costs, not a billing reconciliation. Overlay audio remains the demonstrated voice channel; native audio is disabled for diagnosis, and lip sync is unfinished.

Mercury is now the experimental language default in this lab, pinned to Inception with fallback disabled and a 1,000-token output ceiling. `reasoning.effort: none` does not prevent this route from reporting reasoning tokens. An earlier four-call identity probe produced three valid responses and one output-limit failure that spent 485 reported tokens on reasoning. It also exposed an invented obligation and disposition. The prompt now explicitly forbids those excuses and unsupported personal habits; one successful live exchange does not establish broad grounding reliability. [Retained probe including failures](evidence/dialogue-identity-probe.json)

## Remaining programme

The final local regression passed **185 Python tests and 88 JavaScript tests**. These include changed populations and business owners, unknown/private state, failed playback, old saves and bounded camera motion. Native save restoration is separately reported above; hosted CI is not implied by local results.

Current business charters, unit prices and the bread recipe remain authored. Sustainable connected production, dynamic business formation, richer beliefs and drama, larger conversations, political intervention, full RTS input, first-person participation and a recorded video remain required by the [active development plan](development-plan.md). This is a verified implementation slice, not completion of that goal.
