# Resident employment

Paid bread-making is no longer restricted to Ysolda. Initialized adult residents can consider work at an executable food enterprise when the employer has inputs, a wage budget, a stock gap and an observed route. The worker and employer must both be loaded for physical execution.

## Decision and settlement path

1. A game-clock review prioritizes food needs. A resident without urgent hunger or high fatigue can receive a livelihood opportunity when an enterprise has capacity.
2. The resident may explore work, eat, visit a supported destination or defer. An opportunity is not consent.
3. The employer decides whether to offer the shift, considering their own resources, household reserve, needs and memories. Private employer inventory is not supplied to the worker.
4. The worker accepts or declines. Acceptance records a contract, but produces no wage or goods.
5. Skyrim executes the worker's owned travel. Observed arrival, correct Papyrus binding and package ownership qualify attendance.
6. After 30 game minutes of qualified attendance, the existing native executor consumes one employer grain, creates two employer loaves and transfers two employer gold to the worker.
7. Exact inventory observations settle the contract, add production and wage records, and update both residents' memories. Travel control is released. Interrupted travel ends the contract without claiming work.

The first business policy targets eight loaves. Its wage, stock target and recipe are authored scenario rules, not inferred market equilibria. Employer context explains that two loaves could yield six gold at the initial asking price, but neither sales nor profit is guaranteed, and grain has an opportunity cost. The prototype does not yet negotiate wages or value the grain input financially.

Existing guard duty and explicit commitments are not displaced by side jobs; their leave and scheduling mechanisms are unfinished. The scheduler marks unsupported rest needs rather than pretending to restore fatigue. The original standalone Ysolda/Carlotta scenario remains usable before town initialization.

Food retailers also receive stock-policy reviews when their policy has no recorded review time, four game hours pass, or stock changes by at least two loaves. Urgent food and rest take priority, and the normal one-game-hour resident cooldown still applies. The owner can retain all food or release surplus through the existing reserve choices. A scheduled stock review must match its queued kind; it cannot be repurposed as another activity.

## State and execution boundaries

Business resources remain the custodian's native inventory. A contract cannot create another wallet. The service allows one active resident plan, so jobs are serialized; simultaneous contracts and reservation arbitration remain future work. Stock and wage availability are checked again before production. A failed effect holds for reconciliation, not automatic retry.

The Papyrus lease now lasts at most 300 real seconds, allowing travel plus a 30-game-minute shift at the lab's timescale of 20. Travel itself still has a 120-second timeout. The lease expires if the controller disconnects; very slow game time can cause work to stop instead of paying an unverified wage. Only the original script was recompiled; no game scripts or assets are distributed.

Model decisions are not spoken job conversations. Baking animation, oven use and native spatial voice remain unfinished. The overlay uses actual worker/employer names, and the recorded overview separates accepted contracts, completed shifts and residents with work history.

## Verification

Local verification passed 116 Python tests and 68 JavaScript tests. New coverage exercises capacity limits, existing obligations, guard exclusions, three-stage scheduled consent, a nonlegacy worker, exact wage/input/output effects, interrupted travel, held production, stock-review timing, event-kind validation and save-lineage rollback. These tests establish code behavior, not that every resident performed work in the game.

The bounded director accepts up to 24 resident events per invocation, at most five model calls per event and a review window up to 600 seconds. The window controls when another review begins; an already-selected event batch finishes its bounded workers afterward. No model runs while the director is absent. Each worker retains the existing persisted claim and no-automatic-retry rule.

Live results are recorded separately below; a refusal is retained as a valid outcome, not retried until the model agrees.

## Live trial, 24 October 2026

Carlotta first declined to offer Amren a shift while holding six loaves. A bounded director then completed 24 scheduled meal events across two game-clock reviews. Observed bread across the 29 accounts fell from 59 to 35; gold remained 964 and grain remained 21. No wage, sale or new production occurred in that cycle. Anoriath's livelihood opportunity resulted in eating rather than seeking work.

The updated scheduler generated Carlotta's stock review. In a focused execution of that queued event, she chose to reserve all five remaining loaves. Brenuin's already-queued livelihood review also resulted in eating. A final focused hiring event for Brenuin, after those state changes, again ended with Carlotta declining to offer a shift. The hiring events were test-triggered; their decisions were model-selected. The large meal batch was selected and executed by the director; the two focused queued reviews were selected for inspection.

Across these 28 events, there were 25 observed meals, one stock allocation and two employer deferrals. The 28 Jev calls reported US$0.001633716 in aggregate cost. No new actor completed paid work, so generalized native employment remains unqualified despite passing integration tests. The earlier Ysolda paid-work demonstration is separate evidence. There was no new job conversation, animation or manually inspected game recording.

The employer's conservative reserve policy is now reconsidered rather than permanent by omission, but the model retained it. More work is needed on demand, household planning, rest and viable offers before claiming a self-sustaining economy. These are observations of the prototype, not validation of psychological or economic theory.

Save V at checkpoint 267 restored all compared fields after a process restart, including all 29 funded inventories. Save W at checkpoint 417 restored the 24-meal cycle, and final save X at checkpoint 432 restored subsequent decisions and inventories. The initial U save attempt was rejected because the pre/post snapshots changed during saving; it has no accepted proof and was not overwritten. The precise changed field was not retained by that attempt.

The native router was recompiled and installed only in the isolated lab (3,328 bytes; SHA-256 `36133af79b988bad509482bff5943daee351f95390c596e787dcbe1e6ec862dc`). Its longer lease has not yet been exercised by a new worker's live shift. Native audio remains disabled for crash diagnosis.

Evidence: [decision and native-effect records](evidence/resident-employment.json), [V cold restore](evidence/employment-save-V.json), [W post-cycle restore](evidence/employment-save-W.json), [X final restore](evidence/employment-save-X.json). The generated town overview includes the recorded activity history and contract states.
