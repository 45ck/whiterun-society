# Paid employment execution qualification

Paid execution is currently **unavailable** (`legacy_paid_execution_unqualified`). Existing completed records remain readable. New paid offers and production intents are blocked; saved unfinished `inventory_produce` intents stay held for reconciliation, with prior effects explicitly unknown. Matching balances, an old applied acknowledgement, or a historical no-effect claim cannot release those reservations or award output, wages, memories, or recipe learning.

This gate does not disable independent owner-work jobs, which use their own attendance and recipe-commit protocol. It does not certify old owner-work or authored supply helpers as equivalent to that newer protocol.

## Why the legacy path is gated

The previous paid controller in `bridge/production.js` accepted the expected final inventory without retained attendance or effect witnesses. It could reconstruct partial recipe stages from inventory after reset. Its live attendance state was keyed by command ID and a package ID, without binding both residents' base identities, session, epoch, exact stationary lease, and immutable contract. The service in `production.py` previously settled an applied receipt plus matching balances and then taught the recipe to both participants. Those observations cannot prove who issued the effects, whether labour occurred, or whether wages were transferred once.

The gate now operates at three boundaries: `labour.work_opportunities` advertises no executable paid jobs; `Production.plan_production` rejects new execution and `observe_production` quarantines pending legacy work before reading acknowledgements; the bridge rejects `inventory_produce` before its ID-only completion cache and before acquiring native handles. Native rejection reports `effects_issued: null` and `no_effects_issued: false`. It does not claim that an earlier process produced no effects.

## Required replacement protocol

1. Persist a frozen job contract binding worker and employer reference/base identity, business revision, catalog and recipe hashes, agreed wage and duration, and both offer and acceptance provenance. Generic commodity IDs come from the catalog; models must not supply form IDs or arbitrary inventory deltas.
2. Reserve the worker's activity and both accounts. Verify a stationary attendance lease with exact slot, serial, package, anchor, cell, session and bounded game-time samples. Owner-work's attendance machinery is a useful implementation pattern, but owner attendance does not prove a hired worker attended.
3. Persist a single-use same-session settlement permit before effects. Serialize employer input debit, employer output credit, and employer-to-worker currency transfer. Each leg needs an issued-before-call witness and exact observed account deltas; wages need both debit and credit witnesses. Unrelated catalog balances must remain unchanged. Never infer an issued leg from a coincidentally matching inventory.
4. Report physical output, wage payment, contract completion and activity release separately. If output exists but wages are unresolved, preserve that distinction and quarantine the accounts. Reset or missing witnesses must hold; neither replay nor automatic compensation is justified.
5. Award learning only from a qualified completed job with explicit provenance. Startup skills require a separate authored or observed source. Workstation-dependent recipes also require verified access and an authored labour policy; a stationary actor is not proof of a working forge or smelter.

This change is an offline safety gate, not a new paid-employment implementation or a native gameplay qualification. Tests exercise admission, old pending states, partial/final inventory appearances, cache replay, history preservation and isolation from independent owner production.
