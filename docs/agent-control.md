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
the override, and cancels prototype tasks on bridge reload or game load. Saved
planner intent and automatic resumption are not yet implemented. The model still
only proposes decisions. Combat, interiors, unloaded actors, concurrent residents
and all six route variants are not qualified by the first trip.

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
