# RTS camera synchronization and input qualification

The native RTS view now adopts the observed camera pose before a gesture. Previously, its UI controller retained an independent default: a drag could change distance from 1200 to 1800, height from 900 to 2200 and heading from 225 to 180 degrees even without meaningful movement. Empty drags now produce no command.

Each local movement carries a request ID. Older observations cannot undo newer unacknowledged gestures, and late acknowledgements of previous local movements are rejected. A new remote command can explicitly take over. Invalid observations cannot partially change the local camera state. Changing camera mode releases the pending gesture.

The focused browser now sends an explicit F8 release command, because its native input handler can consume the key before Skyrim Platform receives it. The existing native F8 handler restores focus when available. Pointer capture is requested during a drag; a move reporting neither left nor middle button held cancels the drag even if its release event was missed.

## What the game actually showed

One native drag preserved distance 1200 and elevation 900; heading 225 became its equivalent normalized value of −135 degrees. Its pan target moved from `(24500, −7100)` to approximately `(24669.71, −7269.71)`, and the bridge echoed the UI request ID. This verifies that a delivered gesture used the current pose rather than the unrelated defaults.

**Native input is still unqualified.** That drag reported pointer coordinates at the screen edges instead of the intended Windows positions. A later repeat produced zero browser input events despite document focus, visibility and requested native focus all reporting ready. The instrumented keyboard trial also produced no browser keydown. The earlier drag is one successful delivery, not reliable roster selection or panning accuracy.

The F8 relay and missed-release guard have regression coverage but still lack native end-to-end acceptance. We have not established whether ordinary physical mouse/keyboard input has the same failure as injected Computer Use input.

[Bounded native telemetry and trial scope](rts-input-evidence.json)

## Diagnostics and verification

The local bridge observation includes browser event counts, last event time, focus/visibility, last permitted control key and native event counts. It does not retain text typed into inputs. Native “wanted focus” describes the wrapper's requested state; document focus is separately reported. Neither proves that a key or click arrived.

All **161 JavaScript tests passed** in 2.483 seconds, including observed-pose gestures, stale and out-of-order acknowledgements, invalid input, F8 release/recovery, typed-text exclusion and missed pointer release. Python was unchanged; the preceding economy commit passed 329 Python tests. Hosted CI remains unverified. The changes are deployed to the isolated lab; the society director remains paused.

Next acceptance requires stable pointer coordinates, delivered down/up pairs, actual resident selection, keyboard pan/zoom and focus recovery in Skyrim. API camera operation and screenshots cannot substitute for that acceptance. Connected economics, personal routines, speech pacing and the wider society goal remain active work.
