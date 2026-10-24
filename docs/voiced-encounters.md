# Voiced encounters: three cooperating layers

Ysolda and Carlotta now meet, exchange generated speech and remember what was
said in the actual isolated Skyrim game. Their conversation follows the refusal
of Ysolda's bread offers. Subsequent economic planning receives these memories.
This is a finite two-person encounter, not a general autonomous town calendar.

![Actual Skyrim conversation and speaker caption](images/conversation-closeup.jpg)

## What each layer owns

| Layer | Responsibility | Boundary |
| --- | --- | --- |
| Language model | Proposes two different intentions and short spoken lines using the resident's own experiences and heard speech | Cannot see another resident's private inventory or execute game commands |
| Jev decision model | Chooses among those intentions using needs, authored Big Five traits, priorities and memories | Choice probabilities are model outputs, not validated human probabilities |
| Deterministic simulation | Owns the meeting route, schemas, inference claims, audio delivery, range checks, save checkpoints and memory writes | Speech cannot mint food, spend gold, create consent or establish the truth of a claim |
| Skyrim and local speech | Execute walking, look requests, standing-body turn requests, camera and overlay audio | Native lips and spatial sound remain unfinished |

The tested language provider is `openai/gpt-4.1-mini` through OpenRouter; selection
uses `typesafe/jev-1.14`. Kokoro ONNX generates two distinct stock voices locally
(`bf_emma` and `bf_alice`). No actor's voice has been cloned. The language adapter
also accepts the local llama.cpp endpoint. A local Qwen 2B trial invented events;
an early hosted trial confused buyer and seller. These were failed grounding
tests, not evidence that the local model is ready. First-person factual summaries
now explicitly identify who offered money, refused a sale, worked and paid.
Schema validation cannot guarantee that every future sentence will be truthful.

## Delivery and memory

The encounter temporarily owns Ysolda's route to Carlotta. It retains that route
through dialogue and verifies release afterward. A nearby listener is required
throughout playback. Native head looks are requested for both residents; body
turns are requested only when the engine reports a standing actor. Furniture and
animations may constrain the final pose; requests are not a full pose-quality
measurement.

Each inference is claimed in the save-bound timeline before it runs. The worker
makes at most two language calls and two Jev calls, with no automatic retry.
The generated WAV is hash-addressed and checked against its actual PCM format
and duration before delivery. The in-game browser reports playback completion,
played seconds, mute and volume state. Native callbacks are processed on a game
update, not on the browser-message callback. An interrupted or incomplete
delivery is held rather than credited as hearing.

Only completed playback creates `said` and `heard_speech` memories. Quotes are
explicitly **claims, not verified facts**. The responding resident receives the
previously heard line. Later stock planning receives these same memories; in the
observed follow-up Carlotta still chose `reserve_all`. That demonstrates context
flow, not a causal experiment proving that dialogue changed her preference.

Completed event IDs make zero new model calls. Loading the pre-conversation save
and then the completed voice save restored the correct inventories, people,
dialogue and memories without replaying speech. Mid-speech recovery is covered
by a unit test and holds on a new session; it is not yet a live mid-speech save
qualification.

## Visual experience and timing

An encounter card displays progress, transcript, model timings and the generated
voice's duration. The camera follows the current speaker. Projected nameplates
and frames highlight the participants or selected resident, using actual engine
positions. These are approximate screen markers, not mesh outlines or qualified
occlusion sensing. Guided close-ups open a profile inspector with hunger,
authored trait bars, a generated character intention and recent memories.
These intentions are roleplay output, not access to model chain-of-thought.
Traits are authored game parameters, not psychological test results.

The direct keyboard selection route is implemented but did not pass the current
live input check. Mouse controls remain disabled. Guided inspection is the
verified usable path; do not advertise manual selection as working yet.
Native activation is wired to the inspector but still needs playable-mode proof.

During encounters the bridge polls at 350 ms instead of its idle two seconds,
reducing repeated checkpoint delays. Language and Jev latency, synthesis wall
time, playback length, stage transitions and total encounter time are recorded
by the worker. The 350 ms bridge cadence is not an LLM polling cadence: walking,
waiting and rendering do not call a model. Finite simulations should schedule
meaningful opportunities and quiet periods, not repeatedly manufacture speech
just to fill silence. An autonomous event director remains unfinished.

## Run in an existing isolated lab

Create `voice-venv` under the lab with Python 3.12 and install
`voice-requirements.txt`. The tested workstation environment reused existing
NumPy/ONNX packages through `--system-site-packages`; a fresh standalone install
still needs separate qualification. Download the pinned, hash-checked assets:

```powershell
python tools/prepare_voice.py --root D:\WhiterunLab
```

Prepare private model config files, containing model IDs and **environment
variable names**, never keys. For language, use `provider: openrouter_chat`,
`model: openai/gpt-4.1-mini`, and `key_env: YOUR_KEY_VARIABLE`. For Jev, use the
existing typed decisions config. Then run:

```powershell
python tools/run_conversation.py --root D:\WhiterunLab --id unique-encounter --language-config D:\WhiterunLab\runtime\language-config.json --decision-config D:\WhiterunLab\runtime\jev-config.json
```

The game and managed society must already be connected. No microphone or player
reply is required. Loading a completed voice save shows the stored conversation;
it does not replay audio or resume inference automatically.

## Evidence and limits

- [Conversation runs, costs and playback metadata](evidence/voice-summary.json)
- [First completed exchange](evidence/voice-003-live.json)
- [Corrected close-up and callback run](evidence/voice-004-live.json)
- [Completed voice save and restoration](evidence/WS-Voice-20261024-G.json)
- [Economic decision after hearing dialogue](evidence/voice-followup-stock.json)

Playback was verified through the embedded browser's media completion events and
game acknowledgments. Independent acoustic capture of the physical output device
was not performed. **Skyrim's native audio mixer remains disabled in the current
diagnostic process** after earlier audio-stack crashes. These voices use the
separate CEF overlay channel. This does not prove native sound stability, spatial
voice or lip synchronization. Quests, full political institutions, continuous
daily planning and player-directed encounters are still development work.

Kokoro wrapper: [official project](https://github.com/thewh1teagle/kokoro-onnx)
(MIT); model licensing is Apache 2.0 as documented upstream. Model assets remain
outside this repository. The source project does not redistribute Skyrim assets.
