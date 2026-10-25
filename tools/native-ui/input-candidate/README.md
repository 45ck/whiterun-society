# Reviewed native input candidate (unqualified)

This source patch targets NirnLabUIPlatform commit `c9514ac16434e2edc2bbfb348be2fcdc47e1d6e2`. It is a candidate, not proof that Skyrim input works. No DLL is installed or executed by preparation tests.

## Build and artifact separation

The manual Native UI reviewed build workflow defaults to `upstream-unchanged`. Choosing `input-candidate` first runs pure C++ policy checks immediately after hosted compiler discovery, then compiles the unchanged upstream DLL/PDB and preserves them in `evidence/artifacts/`, then applies the exact reviewed source diff, compiles the candidate into `evidence/candidate/artifacts/`. Both are runtime-unqualified. The original baseline CMake cache is retained separately; all artifact hashes, compiler evidence, licenses and the candidate source-patch receipt are retained. There is no automatic deployment.

`candidate.json` pins original/result source checksums and every added source. `changes.patch` is the complete review diff. Preparation validates all files and the reconstructed diff before writing any file. CRLF checkout differences in the checked-in templates/diff are normalized; downloaded original upstream files retain their verified bytes. The dependency registry, engine and helper repairs remain pinned by the existing build manifest.

## Scope

- Add the source-level `kAllowSaving` menu flag needed by the existing lab. Never apply an old DLL binary-offset patch to a new build.
- Correct cached focus: a request before browser readiness is deferred and applied once when ready. Repeating an already-settled request remains idempotent. A recreated browser preserves requested focus and reapplies it after its own page load.
- Add bounded mouse/input diagnostics and a separately selected Win32 mouse route. Keyboard events remain on the upstream native route.
- Drop browser/render references under the route mutex in `onBeforeBrowserClose`; wrapper destruction detaches before requesting close. Hook callbacks capture the shared route, not a raw browser-wrapper pointer.

## Modes

Set `WHITERUN_UI_INPUT_MODE` in the future game process environment before launch. The mode is read once when each browser route is constructed. This document does not launch or alter the running game.

| Value | Behavior |
| --- | --- |
| unset, `native`, or any unknown value | Existing native mouse delivery; no route diagnostic rows. The source saving/focus changes still apply. |
| `diagnostics` | Existing native mouse delivery plus bounded `WSINPUT` rows. No input rerouting. |
| `win32-mouse` | Visible, focused, foreground owner receives WinProc mouse motion, clicks and wheel events; all still-focused Win32 routes suppress duplicate native mouse delivery. Keyboard remains native. |

Message coordinates are mapped once from client dimensions into the CEF render view. Wheel screen coordinates are converted to client coordinates. Out-of-bounds new clicks are rejected; existing held gestures clamp to the view edge. No additional guessed DPI multiplier is applied. Current message positions are used for clicks, including a first click with no prior movement.

The candidate never acquires/releases HWND capture or posts a cancellation message. It respects Skyrim's existing capture. While an active owner holds a gesture, the render tick polls only the three physical mouse buttons to reconcile missing releases, once per tracked button, accounting for Windows swapped-button settings. Outside-client drag motion is sampled on that tick; it is not a guarantee of lossless input delivery. Focus/capture loss cancels tracked CEF buttons. Closed routes clear state without calling CEF. A later window or render callback cannot use the cleared CEF references.

`WSINPUT` logs contain counters, mode, foreground/owner flags, dimensions, cursor coordinates, DPI and held mouse bits. At most one row per second, 600 rows per route lifetime. They do not record typed text, key codes, URLs or window titles. These rows measure event routing, not gameplay success or user intent.

## Evidence required before qualification

1. Hosted candidate compilation and C++ policy suite pass; DLL/PDB identities and matching debug signature are verified. The unchanged baseline remains independently identifiable.
2. Separately authorized isolated-lab installation preserves the currently working DLL and rollback hashes. No live installation has been performed by this change.
3. In `diagnostics`, compare message/native counters and client/render mapping with observed pointer behavior, including browser-ready focus. Counts alone do not establish correct controls.
4. In `win32-mouse`, visibly verify first click, all three buttons, double click, wheel, drag, release outside the window, focus loss/reacquisition, hidden browser, competing focused browser, close/reopen, and client/render scaling. Verify no duplicate action or stuck gesture.
5. Verify menu saving/loading, RTS selection/pan/zoom, movie-view controls and the native keyboard route separately. Keyboard repair is not claimed here.

Changing the mode to `native` on a later launch reverses the mouse rerouting, not the saving/focus source changes. A full rollback restores the exact preserved lab DLL and original environment. Restarts, in-game control and deployment require their own authorized runtime step. This candidate is not a claim that existing input failures share a single cause.
