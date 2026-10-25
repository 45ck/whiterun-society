# Watching a conversation in Movie view

Movie view now uses subject-relative framing instead of inheriting the wide RTS camera distance and heading. It follows a travelling resident at close range, frames a nearby pair together, preserves the shot across speaker changes, and freezes the final composition when the encounter ends. Manual RTS controls still take priority. Native telemetry reports the framing profile, subjects and follow/hold status.

![Both residents visible during a controlled voiced negotiation](images/movie-pair-speaking-fixture.jpg)

Captured in Skyrim on 25 October 2026. This is a controlled protocol test with authored decisions, not spontaneous conversation. Both residents are visible and the counteroffer subtitle accompanies overlay speech. Lighting remains dark.

## Native qualification

Jon Battle-Born approached Carlotta Valentia, offered four septims, heard a seven-septim counteroffer, accepted and acknowledged receipt. All four utterances recorded completed overlay playback. One loaf moved to Jon and seven septims moved to Carlotta; their combined 136 septims remained conserved. These identities came from runtime state, not camera constants.

The sampled encounter took 73.156 seconds, including travel, synthesis, playback and a deliberate 15-second fixture capture window. It is not a natural dialogue latency score. Camera telemetry moved from resident follow to a pair shot at distance 250 and elevation 150, then reported `holding_last_shot`. Speaker changes retained the same composition. [Camera samples, speech receipts and inventories](movie-camera-evidence.json).

![Controlled trade completed with the pair still visible](images/movie-pair-receipt-fixture.jpg)

Two preceding real Jev reviews deferred work and produced no conversation. Their choices were not overridden or counted as camera trials. Restoring `WS-Camera-20261025-BK` matched all 17 compared saved-state fields, rolling back the reviews and fixture sale. The director is paused after restoration.

## Verification and limits

All 171 JavaScript tests pass, including speaker-swap stability, moving pair composition, distant-pair fallback, invalid coordinates, idle holding and manual override. The bridge is deployed to the isolated lab.

Composition does not establish geometry clearance: there is no verified camera collision raycast. Other positions may still be obstructed. Screenshots qualify one encounter, not every street or interior. Speech uses the CEF overlay; lip sync and physical audibility were not qualified in this camera trial. Native pointer-control reliability remains tracked in [RTS input](rts-input.md).

Next: qualify occlusion detection with positive and blocked controls, improve low-light readability, and record uninterrupted native videos showing conversation, receipts and economic consequences.
