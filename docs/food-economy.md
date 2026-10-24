# Resident reserves and food consumption

## What happened in Skyrim

Carlotta independently selected `reserve_all` during a stock review, then
`eat_bread` during a separate meal-time event. The service persisted each choice
before issuing an effect. Skyrim's native food-use command consumed one carried
loaf: bread changed from 3 to 2 and gold stayed at 5. Only after the observed
inventory matched did the simulation reduce hunger from 0.75 to 0.15 and record
a consumption memory. The eating animation was not verified.

| Event | Model choice | Inference time | Reported cost (USD) |
| --- | --- | --- | --- |
| stock-20261024-001 | Reserve all carried bread | 0.828 s | 0.000060228 |
| meal-carlotta-20261024-001 | Eat one carried loaf | 0.766 s | 0.000066066 |

These are TypeSafe Jev decisions through OpenRouter. Sixteen calls across the
experiments so far reported US$0.000722652 in total. They are discrete events;
the game does not run an inference loop. Repeating the completed meal returned
`duplicate: true`, `model_calls: 0`, with no second consumption.

[Allocation evidence](evidence/food-allocation-live.json) ·
[Consumption evidence](evidence/food-consumption-live.json) ·
[Duplicate follow-up state](evidence/food-duplicate-followup.json)

![Actual Skyrim observer after restoring the food save](images/food-consumption-restored.jpg)

## Rules and boundaries

An allocation partitions observed carried bread into household reserves and
surplus available for sale. It creates no additional goods. The resident chooses
between reserving all, one or two loaves. A fixed reserve is capped by actual
stock; an all-stock reserve follows the remaining stock. A direct purchase
request that would spend Carlotta's reserve was rejected with unchanged state
and inventory. [Reserve guard evidence](evidence/household-reserve-guard.json).

This is a first household-versus-sale distinction, not a complete household or
business accounting system. Residents without an allocation retain the earlier
unallocated-stock behaviour. Buyers are not given sellers' private reserve
policies. Production, wages, restocking, debts and time-based metabolism have not
been connected to the physical NPC economy.

The bridge uses `equipItem` with the existing bread form and checks actual counts.
It issues food use once, tolerates an asynchronous observed effect and holds on
unexpected inventory or timeout. A matching acknowledgement alone cannot reduce
hunger. The immutable save checkpoint records intent before the native command;
the committed checkpoint records the effect, needs and memory together. Tests
cover restored pending consumption, but an interrupted physical consumption has
not been qualified through a live save/load.

The meal event adds 0.35 simulated hunger; a loaf removes 0.60. These are authored
prototype parameters, not empirical human nutrition or vanilla Skyrim hunger.
The model chooses from supplied actions; this run does not prove spontaneous
planning, inferred motives, psychological validity or human believability.

## Actual save restoration

After saving `WS-Food-20261024-C` at checkpoint 55, the game loaded the prior
negotiation save B at checkpoint 45, then C again. Fresh sessions matched the
saved plans, people, memories, world journal and observed inventory. C additionally
matched its consumption history. The earlier B restored with no consumption
records. ESS and SKSE cosave hashes were checked.

[Earlier-state restore](evidence/food-restore-before.json) ·
[Food save and restore](evidence/food-save-C.json).

No new audio crash occurred in these two restores. Earlier audio-thread crashes
remain unresolved; this short experiment does not establish sustained stability.

## Development and execution corrections

The resident worker now accepts `--actor` and `--kind stock_review`, and permits
at most five model calls for a meal including a post-purchase food choice. A
completed purchase followed by eating is tested, but a model-approved physical
purchase still has not occurred in the live Jev runs.

The local server now binds exclusively on Windows before publishing its bridge
configuration. A replacement publishes its new port/token atomically; an updated
previous instance exits itself when superseded. The subprocess test checks both
port collision and retirement. The actual 17845 instance retired on replacement
by 17846. Older legacy services without this behaviour remain idle.

A bridge regression was also corrected: generic acknowledgements could overwrite
the asynchronous `release_routine` result before the package disappeared. A
controlled bridge test now verifies that release is acknowledged only after the
owned package disappears. Earlier live travel and arrival evidence remains valid,
but that generic acknowledgement alone was insufficient evidence of release.
The corrected release path still needs a new live qualification.

Current local validation: 54 Python and 36 JavaScript tests passed. Hosted CI for
this revision remains unverified.
