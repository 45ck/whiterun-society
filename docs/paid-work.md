# Paid production in Whiterun

**Historical evidence:** current source disables this legacy executor. Its receipt protocol lacks sufficient attendance and payment witnesses for safe replay and ongoing qualification. The observations below remain part of the experiment's history, but do not qualify the replacement protocol or authorize current execution. [Audit and required replacement](paid-employment-protocol.md).

This page records the original fixed-term experiment. [Dynamic enterprises](enterprises.md) now support changing custodians, wages, shift durations, stock targets and business closure; existing saves retain their original terms until edited.

**Recorded in the historical live trial:** Carlotta offered the contract and Ysolda accepted.
Thirty game minutes of qualified attendance produced two loaves and paid two gold.
Both before/after Skyrim saves restored the corresponding economic state.

![Completed paid work in the actual observer](images/paid-work-complete.jpg)

The prototype contract is explicit: Carlotta can offer Ysolda two gold for
30 game minutes of simulated bread-making attendance. Ysolda can refuse or walk
to the job. One observed grain becomes two bread; Carlotta pays the wage from
her own purse. No model is called while walking or working.

## Economic rules

- Employer and worker make separate decisions using their own inventories,
  authored profiles, needs and memories. The worker receives the offer, not the
  employer's private balances.
- The offer is unavailable without grain and wage funds. Conditions are checked
  again before issuing the physical command.
- Attendance requires the owned travel package, both loaded adult actors and a
  distance no greater than 300 game units. Game time advances work; paused time
  adds nothing. Clock jumps and interrupted attendance hold the operation.
- Native effects consume one Wheat item, create two bread and transfer two gold.
  Each intermediate inventory state is checked. Duplicate commands do not repeat
  the effects; unexpected state or a delayed-effect timeout holds for review.
- Only observed completed effects commit production and wage memories. Production
  is a separate journal from purchases, consumption and scenario imports.

This is an authored conversion recipe at the employer's location. The actor does
not yet use an oven or a qualified crafting animation. It does not account for
water, fuel, tools, skill, fatigue or a firm's separate bank account. It is a real
inventory-backed economic effect, not proof that Skyrim performed its vanilla
baking recipe. The Wheat form 0x4b0ba was verified from the owned Skyrim.esm record.

## Reproduce the bounded scenario

Use the isolated lab and a synchronized society. Both residents must be loaded.
The initial two grain are an explicit demo import with its own journal, not
production. This helper cannot replenish an already imported timeline or create
gold. Replace `OBSERVED_ACTOR_ID` below with the decimal ID of the intended initialized, currently observed worker. `--actor` is required; an omitted actor does not select a named resident:

```powershell
python tools/prepare_production.py --root D:\WhiterunLab
python tools/run_resident_event.py --runtime D:\WhiterunLab\runtime --event-id work-unique-id --actor OBSERVED_ACTOR_ID --kind work_shift --model-config D:\WhiterunLab\runtime\jev-config.json
```

Supply the provider key through the environment variable named in the local model
configuration. Never put it in a command argument or the repository. The worker
persists an inference claim before each call, stops on uncertainty and does not
automatically retry a claimed call. A refusal is a valid outcome.

The isolated launcher starts in Whiterun without character creation or a
playthrough. These setup and event commands still require the developer; there is
not yet an autonomous daily job market or a complete one-click player scenario.

## Validation scope

| Observed resident stock | Before | After |
| --- | --- | --- |
| Carlotta gold | 6 | 4 |
| Ysolda gold | 5 | 7 |
| Carlotta grain | 2 | 1 |
| Carlotta bread | 3 | 5 |

The two Jev calls selected `offer_shift` (reported probability 0.60) and
`take_shift` (0.87), taking 0.766 and 0.500 seconds. Their reported total cost was
US$0.000082194. Across eighteen calls so far, the reported total is US$0.000804846.
The plan reached completion about 118.5 seconds after starting, including
checkpoint synchronization and labour. It began within 218 units of Carlotta:
this run demonstrates owned attendance, not a new long-distance journey.

[Full live evidence](evidence/paid-work-live.json) ·
[Explicit initial import](evidence/paid-work-setup.json) ·
[Actual package release](evidence/paid-work-release.json).

Actual saves D (checkpoint 58, imported inputs before work) and E (checkpoint 68,
completed work) both restored matching plan, people, memories, trades,
consumptions, imports, production and observed inventories. File hashes and fresh
bridge sessions were checked. The two restores succeeded in the restarted game;
they do not erase the earlier crash described below.
[Save D](evidence/paid-work-save-D.json) · [Save E](evidence/paid-work-save-E.json).

Repeating the completed event returned zero model calls. Repeating setup returned
zero imported grain. [Observed state after those checks](evidence/paid-work-duplicate.json).
The release acknowledgement now reports `released: true` after the native
package check, and the final movement status has `ownedPackage: false`. This
qualifies the release fix previously covered only by a controlled test.

**59 Python and 43 JavaScript tests passed locally.** The actual UI was inspected;
hosted CI for this revision is not yet verified.

Local checks cover consent, absent inputs, actual-inventory confirmation,
conserved wages, finite imports, duplicate delivery, intermediate-state recovery,
paused time, clock jumps and interrupted attendance. Restored pending work
restarts uncompleted attendance; partial recipe effects reconcile from inventory.
That recovery path is tested, but live interruption midway through production is
not yet qualified.

The attempt to reload the earlier food save before this experiment crashed the
game after about 41 minutes of process uptime. CrashLogger reported integer
division by zero in SkyrimSE.exe+0CC2080 on an audio manager stack. This is observed
diagnostic evidence, not a proven root cause. The lab restarted successfully;
the original installation was not modified. Sustained save/load stability remains
an explicit acceptance gap.
