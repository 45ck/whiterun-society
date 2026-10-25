# Ordinary conversations and authored scenarios

An ordinary social opportunity belongs to the observed, save-bound population; an authored encounter requires an explicit scenario. Neither route silently substitutes named residents. The admission and worker contracts below are implemented in source. This is not a claim of live installation, audible delivery, natural conversation quality or native acceptance for the migration.

## What an ordinary conversation means

A new ordinary conversation requires a nonempty established census. An offered social opportunity is permission to consider talking, not an instruction to deliver a fixed scene. The initiator considers eligible nearby residents or continues quietly. An approached resident may accept or give a brief refusal. During an accepted exchange, a resident may reply, close politely or leave quietly within the configured turn bound. A greeting does not guarantee friendship, a sale, employment or a longer conversation.

`POST /conversation/start` accepts `id`, optional `actor`, `max_turns`, `opportunity_batch` and `reply_policy`. Supplying `scenario`, `participants` or other unknown request fields fails. Without `actor`, it offers an opportunity to an eligible resident prioritized by least recent social attempt, with actor ID as a deterministic tie-break. With `actor`, the request must match that resident's pending scheduled `social_review` event. It does not force an arbitrary resident into a new social event. A default six-turn bound caps the exchange rather than obliging six turns.

Candidates come from current classified census residents, route eligibility, spatial proximity and activity reservations. A valid recent proximity notice can extend that candidate context, but it is not qualified vision, an invitation or consent. The candidate view uses the resident's own known identity and relationship information; a roster entry does not automatically reveal another person's name, memories, inventory or intentions.

The decision layer chooses bounded feasible actions. The language layer proposes situated intentions and wording. Deterministic code validates them, coordinates native approach and speech, and records verified outcomes. Hearing a claim is not evidence that the claim is true. Speaking about goods does not mutate inventory: an accepted economic action still needs its separate account checks and native receipt.

## A user-facing example without named participants

1. Bootstrap a new isolated timeline, then census the adults currently observed by the bridge. This supplies resident identities; it creates no money, relationships, enterprise or recipe knowledge by itself.
2. Offer a nearby social opportunity, or run an existing scheduled social-review event for its explicit resident. If there is no eligible pair, the request cannot invent one.
3. A resident chooses someone currently eligible to approach, or continues quietly. Their choice is checked against the current scene and reservations.
4. Skyrim walks the initiator toward that person. Speech waits for the matching route contract, actual attendance and proximity evidence.
5. The approached resident chooses whether to talk. They might discuss the weather, politely refuse, ask about a concern, or refer to something they actually know. Generated wording must remain within the available context.
6. Only confirmed delivered turns enter heard-speech memory. Subjective appraisal may affect the simulated relationship; it does not prove human psychology. A later need/work review can follow when an eligible reason exists. No forced sale or drama quota is required.

This is a description of possible flow, not a captured native conversation or a promise that every branch has been observed. A refusal or quiet continuation can be a correct outcome.

## Authored encounters remain a separate tool

An authored scenario explicitly selects two participants, a bounded turn limit and the provenance of that selection. It is useful for repeatable tests, recording and comparing the same setup. It must be labelled authored: model-generated wording within such an encounter does not make the participant selection autonomous.

`POST /conversation/scenario` accepts `id`, `scenario` and optional `reply_policy`. The scenario requires exactly these fields:

| Field | Contract |
| --- | --- |
| `version` | Integer `1` |
| `id` | Scenario definition identity: 1–64 ASCII letters, digits, underscores or hyphens |
| `participants` | Two ordered, distinct integer native actor IDs, each in `1..4294967295`; first actor approaches second |
| `max_turns` | Integer from 2 to 6 |
| `provenance` | 1–500 characters of explicit authorship/setup description, with no surrounding whitespace, control characters or surrogate code points |

The request's encounter `id` is separate from the scenario definition ID and is limited to 1–40 letters, digits, underscores or hyphens. Participants must already exist in saved people and be currently observed, eligible for routing and free of conflicting activity reservations. The scenario starts the selected pair's meeting directly; it does **not** run ordinary partner selection and social consent. That distinction must remain visible in analysis of autonomous versus authored encounters. Historical initialized profiles can support an explicit scenario without making a new ordinary no-census conversation legal.

The scenario definition is validated and frozen into saved conversation state with an integrity digest. Changing the local file later must not rewrite the accepted encounter. Reusing an event ID with different participants, definition or conversation policy must fail rather than silently replacing the saved event. An identical duplicate should return saved state without spending another inference call or restarting speech.

The SHA-256 digest covers sorted-key compact UTF-8 JSON of the full validated definition, including provenance and participant order. Reusing a scenario ID with changed content also fails even under a new encounter ID; an unchanged definition can be intentionally reused for a separate test with a new encounter ID. Ordinary and authored encounter IDs cannot be crossed between the two admission paths. Exact saved duplicate lookup occurs before new-census admission; it returns history rather than starting a new encounter.

The worker loads a scenario only from an explicitly supplied `--scenario PATH_TO_SCENARIO_JSON`. Its UTF-8 JSON file is capped at 16 KiB, duplicate JSON keys are rejected, and unknown schema fields such as native commands are rejected. `--scenario` cannot combine with `--actor`, `--opportunity-batch` or `--max-turns`; the definition owns its participants and limit. No default scenario file is discovered. Admission and duplicate detection happen before provider-key resolution, inference or voice startup; a later setup failure is held rather than silently retried.

For reproducible policy comparisons, pass `--reply-policy` explicitly. The worker defaults to `combined_choice`, as does the ordinary HTTP entry point; the authored HTTP entry point and direct engine methods default to `separate_choice`. These are dialogue policies, not levels of proof. Never put provider keys in the scenario JSON or repository.

Scenario data cannot create missing resident profiles, mint resources, grant private knowledge or bypass route/activity checks. Ordinary requests cannot become authored scenarios merely because the census is absent. Historical saved profiles and settled records remain historical state, rather than being overwritten with newly seeded defaults.

## Physical attendance and recovery

New meetings pin `meeting_route` to the actor, target, `papyrus-mailbox-v1` adapter and game session. A missing, changed or old-session contract prevents movement dispatch and requires hold/release recovery. The arrival witness must match the movement ID, participants and mailbox adapter, confirm aliases and retained package ownership, and show nearby positions. A cached `applied` acknowledgement alone cannot establish attendance.

These checks apply to authored and ordinary social meetings. Old unversioned meetings do not silently become new trips. Cleanup checks the original route/initiator/scenario identities against the two speakers; speaking order may reverse after a refusal, but release must still belong to the original route owner. Unknown or contradictory participants and failed release leave `release_required` and `cleanup_review_required` set in a held state. The system does not guess an actor or accept a cached acknowledgement as sufficient recovery.

Native reload, interrupted approaches, participant disappearance, audio interruption and retained-package release still need game evidence. Source tests and a scenario hash do not prove lip sync, audible output, visibility or good conversational timing.

## Qualification required

[Full hosted validation](https://github.com/45ck/whiterun-society/actions/runs/40195842462) passed for source revision `9ef9476` on Windows and Ubuntu: **832 Python tests per platform (831 passed, one initial generated-file skip), 300 JavaScript tests, six generated plugins and six plugin-readback checks**. The initially skipped test passed in the later readback stage. Windows also compiled both Papyrus scripts. [Machine-readable validation evidence](evidence/population-scenario-validation.json). These results do not qualify installation or native execution.

Use fresh arbitrary participant IDs in tests; changing their names must not alter eligibility. Verify no-census rejection without a state change or provider call; uniform fresh profile seeding and old-save preservation; unknown/duplicate/stale participants; opportunity expiry; reservations; changed scenario digest or policy; exact duplicate handling; and saved-route holds before cached acknowledgements.

Focused source verification reported **12 new engine/cleanup tests**, **9 dedicated API/CLI entry-point tests** and **3 existing worker tests**, all passing. These are separately reported scopes, not a count of native encounters or a general realism score. Fresh population initialization has its own [test and historical-evidence boundaries](population.md).

For a native run, record the census and chosen source mode, explicit participants, route/attendance evidence, delivered turn IDs, playback duration, refusals and interruptions, memory changes and release outcome. Count authored scenarios separately from autonomous opportunities. Compare conversation completion and latency with their actual denominators; do not invent a realism score from merely hearing a voice.

See [population provenance](population.md), [remaining identity/economy gaps](data-driven-economy-gap.md) and [catalog choices versus physical effects](economy-catalog.md).
