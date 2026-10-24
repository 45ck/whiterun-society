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
