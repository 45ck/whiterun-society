# Spatial telemetry and urban-system evidence

The spatial recorder measures **observed positions over time**, separately from an NPC's intention to walk. A route package, model choice, animation or destination marker alone does not establish movement. The recorder does not modify the simulation, call a model or invent activity between observations.

## Measurement contract

`SpatialTelemetry.observe(observation, society)` accepts at most one frame per five seconds. The rolling window holds at most 720 frames and one hour of observations; the UI receives the last 60 chart points. Configuration and six engineering targets live in [`config/spatial-metrics.json`](../config/spatial-metrics.json). Runtime configuration is loaded at service startup, so a configuration change needs a controlled restart.

Each frame records the native session, checkpoint, game day, loaded managed resident IDs, finite native 3D positions, space identity and narrowly selected goal/package evidence. No names, dialogue, private memories, prompts or credentials are logged. Optional local JSONL persistence rotates at 8 MiB and retains one previous file. It is an operational trace, **not a durable lifetime archive**. Persistence failures are counted and do not stop the simulation. A restarted recorder begins a new in-memory observation window; it does not silently treat old trace files as current activity.

Different native sessions, a reversed game clock, a reversed save checkpoint or a reversed wall clock start a new measurement segment. This prevents movements before a save rollback from becoming activity in the restored world. Save-derived outcomes and rolling operational telemetry have different lifetimes and should remain visibly labelled.

## What the figures mean

| Measurement | Evidence and denominator | What it does not prove |
| --- | --- | --- |
| Observed moving / stationary residents | Consecutive loaded native positions, advancing game clock, same native space and an interval no longer than 15 seconds | Animation quality, path correctness or purpose |
| Travel intentions | Current owned standing package, matching observed package ID, `go_to` and `travelling` phase | The actor actually moved |
| Movement duty cycle | Moving actor-seconds divided by usable paired actor-seconds | A target to make everyone perpetually walk |
| Sampled distance | Sum of straight-line 3D displacement between accepted samples | Actual navmesh path length; turns between samples are missed |
| Speed | Accepted displacement divided by wall-clock sample interval, in game units/second | Metres per second or a validated human locomotion model |
| Stationary duration | Consecutive usable intervals below the configured displacement threshold; resets after movement or missing evidence | Inactivity or failure: conversation, work and rest may be stationary |
| Goal coverage | Resident samples with a travelling, arrived or quiet personal goal, divided by loaded managed resident samples | Continuous reasoning, useful work or a completed outcome |
| Destination concentration | Current personal-goal target assignments and the largest target's share | Completed visits, demand, market share or distinct behavioural mechanisms |
| Close pairs | Observed resident pairs within a configured 3D radius, among same-space comparable pairs | Crowd density, congestion, collision or social consent |
| Supplier/work proximity | Nearest observed public enterprise custodian with the relevant capability, excluding the subject itself | Fixed premises, a stocked shop, affordable food, an open job or a reachable route |

Movement currently uses a ten-game-unit jitter threshold and excludes apparent speeds above 1,500 game units/second as discontinuities or possible teleports. Both thresholds are **authored measurement settings**, not facts about human motion. Exterior positions are comparable when the observed worldspace matches; interiors require the same observed cell. Missing space identity cannot support a distance measurement. Vertical distance is included.

`candidate_actor_seconds` includes the union of managed residents seen at either endpoint multiplied by elapsed time. `usable_actor_seconds` includes only accepted paired intervals. Unloaded actors, invalid geometry, changed spaces, clock pauses, observation gaps and possible teleports are reported as excluded intervals; they are never called stationary. A long observation gap lowers usable coverage instead of creating an apparently motionless town. The first frame has no preceding interval and contributes no actor-seconds.

The latest displayed counters have a freshness flag and last-sample timestamp. Older rolling measurements can remain available while the native bridge is disconnected, but they cannot be described as current motion. Rates remain `null` without a valid denominator.

## Configured spatial OKRs

All thresholds are proposed engineering objectives, not validated psychological or city-planning norms. A missing measure is `unmeasured`; an undersized sample is `insufficient_sample` and cannot pass.

| ID | Key result | Current instrumentation |
| --- | --- | --- |
| SPA-01 | ≥90% usable tracked actor-time over ≥300 candidate actor-seconds | Implemented from paired observations |
| SPA-02 | ≥95% sampled personal-goal coverage over ≥300 loaded resident samples | Implemented; existing goals are not proof of purposeful completion |
| SPA-03 | ≥95% verified reachable food destinations over ≥100 probes | Unmeasured: requires paths, stock, opening hours, prices and affordability |
| SPA-04 | Five qualified route-disruption and recovery scenarios | Unmeasured: requires interventions, replanning and recovery evidence |
| SPA-05 | Neighbourhood food-access p90/p10 ratio ≤2 over ≥100 observations | Unmeasured: requires neighbourhood/household geography and usable travel-time access measures |
| SPA-06 | Queue and throughput measurements for ≥90% of businesses over ≥30 observations | Unmeasured: requires service capacities and request/completion timing |

The next urban-system instrumentation should establish actual premises and public opening hours, path probes and route failures, queue/service capacity, household access costs, production-input deliveries and geographically identifiable supply disruptions. An agent can choose where to travel now; that does not yet provide a city planning model with land use, transport networks, rent, housing capacity or infrastructure investment.

## Integration and tests

Create one recorder in the bridge service, call `observe` after native observation and society projection, and attach `status(current_native_session)` to `dashboard.spatial`. The class exposes `current`, `coverage`, `movement`, `destinations`, `proximity`, `chart` and `quality_goals`. It caches summaries between new frames so frequent UI requests do not repeatedly aggregate the full window.

The focused suite covers actual movement versus intent, paused time and gaps, unloaded actors, invalid positions, apparent teleportation, different native spaces, save/session reversal, sampling and window bounds, dynamic enterprise proximity, unknown-target handling, privacy of the trace, log rotation and write failure, and stationary timer reset. Passing these tests verifies the measurement code; live native recordings are still needed for runtime qualification.
