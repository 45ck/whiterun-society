# Agents own routines

Calvin clarified that the society agents must choose residents' locations and
routines themselves. A language model commenting on otherwise unchanged vanilla
routines does not satisfy the project.

For a managed resident, the society planner must own the current goal, destination,
activity, counterpart and interruption rules. Skyrim supplies navmesh traversal,
animation, collision and low-level execution. Ordinary work and travel need not
call a model continuously. Events or meaningful changes request replanning.

## First complete behaviour loop

1. A resident's needs, resources, personality and memories produce a shopping goal
   or an explicit alternative such as postponing the purchase.
2. The resident selects an available seller and receives an owned travel routine.
3. Arrival is measured from actual positions. A timeout, unloaded actor or
   interrupted route is a failure/replanning event, never a completed journey.
4. Buyer and seller agree to terms or refuse. Only then may the finite-inventory
   trade run through the prepared/committed checkpoint protocol.
5. Confirmed outcomes update memories, trust and needs. The resident chooses their
   next activity. Loading either save restores the corresponding social state.

The observer must show the resident's goal, destination, current phase and outcome.
A passing demo requires an actual agent-selected route and action. Teleportation,
an externally selected route, nearby vanilla wandering or a proposed sentence is
not equivalent evidence.

## Movement probes, 24 October 2026

The first direct PathToReference request from Ysolda to Carlotta returned without
reaching interaction range (about 523 to 522 game units). An approach-controller
probe reached the proximity threshold (313 to 221 units), but that alone does not
isolate the effect from ordinary NPC movement.

A longer approach request from Ysolda to Adrianne stalled for 45 seconds, remaining
around 3,900 units away. It was marked held and the temporary approach setting
was cleared. Reliable agent-owned routing is **not accepted**. The next transport
implementation should establish explicit AI-package ownership and destination
references, rather than assume these simple calls supersede existing routines.

These probes were externally requested. Neither the destination selection nor the
routine was selected autonomously by the local model.

## First package ownership proof

The original `WhiterunAgents.esp` builder now creates six travel tasks between
Ysolda, Carlotta and Adrianne. Each task has a priority-95 quest, forced actor and
destination aliases, and a travel package referencing the owned game's standard
Travel template. It overrides the assigned actor's normal package stack while
active. No vanilla record is replaced and no game asset is redistributed.

Live test `40b45c4877bf802d`: Ysolda travelled to Adrianne, from 4,116.88 to
247.98 game units in about 47 seconds. The observed active package was our
`0x06000803` during the journey. After arrival, the quest stopped and the observed
package returned to vanilla `0x0002C3B9`. This proves execution of one externally
selected task, not an autonomous choice or a complete daily routine.
[Structured evidence](evidence/agent-package-forge.json).

A subsequent trip to Carlotta under the interruption-aware controller also passed:
698.91 to 248.93 units in about 7 seconds, using package `0x06000801`, then releasing
to `0x0002C3B9`. [Market evidence](evidence/agent-package-market.json).

The first dynamic alias implementation failed: both `GetAlias` and `GetNthAlias`
returned null through the installed bridge even though `GetNumAliases` returned
two. Waiting for quest startup and adding alias script bindings did not resolve
it. The upstream [native conversion code](https://github.com/skyrim-multiplayer/skymp/blob/main/skyrim-platform/src/platform_se/skyrim_platform/CallNative.cpp)
only searches ordinary form types when converting returned objects, a likely
explanation for losing alias objects. Prebound quest aliases avoid that conversion.
A future Papyrus or native adapter can support arbitrary destination assignment.

The prototype runs one task at a time. It holds interrupted/stalled tasks, releases
the override, and cancels native tasks on bridge reload or game load. The later
resident planner below persists intent and can reissue a saved travelling stage;
that restoration needs live qualification. Combat, interiors, unloaded actors,
concurrent residents and all six route variants are not qualified by these trips.

### Build and install the original task plugin

Requires .NET 10 SDK. Mutagen.Bethesda.Skyrim is pinned to official release 0.54.4
with a NuGet lockfile. The builder needs no game assets to generate its own records.

```powershell
dotnet restore tools/AgentPluginBuilder/AgentPluginBuilder.csproj --locked-mode
dotnet run --no-restore --project tools/AgentPluginBuilder/AgentPluginBuilder.csproj -- work/WhiterunAgents.esp
```

With the isolated game closed, copy that generated ESP to the lab's `game/Data`.
The observer profile helper enables it on the next cold launch. Do not replace a
plugin while the game has it loaded. The lab uses a portable, hash-verified SDK
10.0.402 rather than modifying the workstation's global SDK installation.

```powershell
python tools/probe_movement.py --method package --target 108156
```

This bounded probe selects Ysolda and a destination explicitly. Its report requires
observed ownership and arrival. The observer follows the traveller and displays
the destination, execution phase and distance; the camera tour resumes afterward.

## Resident-selected errand and consent

The meal-time worker now connects a resident's needs, authored Big Five profile,
own inventory and retrieved memories to choices. It persists a model-call claim
before inference, validates the result, requests owned travel, waits for observed
arrival, and asks the seller independently whether to sell. An acceptance enters
the existing inventory-verified trade protocol. A refusal moves no inventory and
creates factual memories for both people without automatically lowering trust.
The retained travel package is explicitly released after the outcome.

Actual experiments on 24 October 2026:

| Event | Provider | Observed outcome |
| --- | --- | --- |
| meal-001 | Local Qwen | Deferred, one call, 8.86 seconds; explanation repeated instructions |
| meal-002 | Jev | Chose Carlotta, travelled 762.52 to 249.63 game units under our package, seller declined; two calls, 2.734 and 0.515 seconds |
| meal-003 | Jev | Received the previous refusal memory, again chose Carlotta and was refused; already within 200.98 units, so no new journey proved; two calls, 0.797 and 0.875 seconds |

Evidence: [local event](evidence/resident-local-001.json),
[first Jev event](evidence/resident-jev-002.json),
[repeat Jev event](evidence/resident-jev-003.json),
[four-case comparison](evidence/jev-comparison.json).
The actual IDs use the `meal-20261024-` prefix. Initial stock was an explicit
three-loaf fixture. Gold and bread were unchanged by the refusals. The first
refusal's memory recording was added after its run, then derived from its saved
outcome before the second Jev event; that later context contains the memory.
The evidence is not rewritten to imply the first worker recorded it immediately.

Jev's action descriptions are authored labels, not generated dialogue or inferred
inner thoughts. No emotion is invented for its typed choice. Eight hosted calls
(four comparison, four in-game decisions) reported a total US$0.000300342.
The key stays outside source control; the worker accepts a named environment
variable. It never makes a model call from the Skyrim update loop.

To run one explicitly triggered event after a fresh world's explicit bootstrap, replace `OBSERVED_ACTOR_ID` with the decimal ID of the intended initialized resident from the current observation. `--actor` is required; the worker does not select a default named resident:

```powershell
python tools/run_resident_event.py --runtime D:\WhiterunLab\runtime --event-id meal-unique-id --actor OBSERVED_ACTOR_ID --model-config PATH_TO_PRIVATE_CONFIG
```

For Jev, config fields are `provider: openrouter_decisions`,
`url: https://openrouter.ai/api/alpha/decisions`, `model: typesafe/jev-1.14`,
and `key_env` naming an existing environment variable. The revised negotiation
protocol permits at most four inference calls per errand and no automatic retries. Replaying the
same event does not increase hunger or repeat decisions. A crashed inference
claim is held for review instead of silently charging another request.

The initial experiments above do not prove adaptive replanning after refusal,
negotiated prices, alternative suppliers, consumption, continuous schedules or humanlike judgement.
The local prompt was generalized after the recorded run; its quality improvement
has not been measured. [Broader design and evaluation](human-behaviour.md).

## Revised offer and actual plan restoration

Experiment `meal-20261024-005` exercised the revised protocol in the actual game:

1. Jev selected seeking bread. Ysolda travelled from 1,697.96 to 249.79 game units
   under custom package `0x06000801`.
2. Carlotta declined the initial three-gold offer. Both received a factual memory
   before the next model request; the buyer did not learn a fabricated motive.
3. Given leaving, visiting Adrianne or raising the offer, Jev selected five gold.
4. Carlotta independently refused again. The protocol ended, released the task
   and left actual gold/bread unchanged. No third unchanged request was allowed.

The four inference calls took 0.484, 0.469, 0.531 and 0.531 seconds and reported
US$0.000204792 total. The plan reached completion at about 57.8 seconds, including
walking and checkpoint synchronization. [Full live evidence](evidence/negotiation-live.json).
This demonstrates a choice among revised options. The maximum of two offers is
an authored execution constraint, not spontaneous model learning or unrestricted
bargaining. A model-approved purchase remains unproved in the live game.

The preceding `meal-004` run reached reconsideration but its claim response timed
out before the third inference. The claim had persisted. The worker stopped;
an explicit hold then released the task. No claim or paid call was replayed.
The local HTTP timeout is now 30 seconds. [Failure](evidence/reconsideration-timeout.json)
and [observed recovery](evidence/reconsideration-timeout-recovery.json) are retained.
That run's two decisions cost US$0.000091224. Across all fourteen Jev calls so far,
the provider reported US$0.000596358.

### Real game-save comparison

| Saved state | Checkpoint | Plan | Ysolda / Carlotta memories |
| --- | --- | --- | --- |
| WS-Agency-20261024-A | 23 | meal-003, refused at 3 gold | 2 / 2 |
| WS-Agency-20261024-B | 45 | meal-005, refused at 3 then 5 gold | 5 / 5 |
| Load A | 23 | Exact earlier plan | Exact earlier memories |
| Load B | 45 | Exact later plan | Exact later memories |

Both actual loads started fresh bridge sessions and matched complete plan, people,
inventory and trade-journal snapshots. Each ESS and SKSE cosave hash was checked.
The fifth memories include the intermediate failed run's real seller refusal;
they are not all from the successful negotiation run. [Save A proof](evidence/agency-save-A.json),
[save B proof](evidence/agency-save-B.json). No new audio crash occurred during
these two restores; earlier crashes remain unresolved and this is not a soak test.
Restoring a settled plan does not qualify a model call or trade interrupted by a load.

```powershell
python tools/verify_plan_save.py --root D:\WhiterunLab --name WS-unique-name
python tools/verify_plan_save.py --root D:\WhiterunLab --name WS-unique-name --restore
```

The launcher now reads the current port from the runtime configuration. After
switching development to port 17843, attaching to the running game and observing a
fresh bridge session took 1.2 seconds. The earlier service on 17841 remains idle
with no connected bridge; no worker or model loop is running there.

![Revised offer in the actual game](images/negotiation-reconsideration.jpg)
![Later plan restored from an actual save](images/negotiation-restored.jpg)

## Food decisions and release correction

Managed residents can now review carried food allocations and choose to consume
a loaf. The worker accepts `--actor` and `--kind stock_review`; a meal has a maximum
of five model calls including an optional post-purchase food choice. See
[actual consumption, save restoration and development lifecycle evidence](food-economy.md).

The generic bridge acknowledgement previously could overwrite a pending
`release_routine` result. It now waits for confirmed removal of the owned package,
with a regression test. Earlier acknowledgements alone should not be treated as
release proof. A new live qualification of the corrected release is still open.

The subsequent [paid-work experiment](paid-work.md) now qualifies that corrected
release: the bridge observed package removal and returned `released: true` before
the plan cleared its release requirement. It also demonstrates a separate
employer offer, worker consent, owned attendance and physical production/payment.
