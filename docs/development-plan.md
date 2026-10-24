# Living society development plan

Updated 25 October 2026 from Calvin's explicit direction. This plan preserves the full objective: a playable and watchable Whiterun economy and society, with autonomous residents, grounded speech, persistent consequences and an RTS-style observer. Items below are requirements and work in progress, not claims of completion.

## Accepted direction

- Use cloud models through OpenRouter. Local inference is optional future comparison, not a prerequisite. Mercury 2.5 is the leading dialogue candidate, subject to actual adapter, grounding, latency and voice checks. Keep Jev for bounded decisions and deterministic code for rules, accounting and native execution.
- Ordinary simulation must not depend on Ysolda, Carlotta, Adrianne or any fixed named resident. NPCs can enter, leave or change. Select partners, sellers, employers and destinations from current population, capabilities, observations and commitments. Keep named demonstrations explicitly labelled as fixtures.
- Each resident has a changing personal view of the world. Global simulation knowledge must not leak into their decisions. Meeting a stranger does not reveal their name, wealth, motives, personality or private memories. Names and other information require a recorded source. Rumours and speech remain claims until independently verified. Familiarity, affinity and trust are separate.
- Model-driven choices should have meaningful variety: trade and production, employment, meals and rest, courtesy, refusal, quiet passage, introductions, ordinary conversation, disagreement and relationship development. Generate feasible options from state; keep effect validation deterministic. Do not claim a large number of meaningful behaviours merely by multiplying cosmetic variants.
- Build full RTS observer mode in Skyrim: elevated overview, pan, zoom, rotate, select and highlight residents, follow them, jump between events, and inspect needs, activity, relationships, resources and businesses. Preserve first-person play as another mode. Simulation-speed controls must respect native game execution and persistence.
- Show the society visually and audibly: nearby speakers facing one another, clearly attributed speech, visible interaction state, informative overlays, and eventually recorded example videos explaining conversations, economy and consequences.
- Keep README, the Pages journal, system diagrams and evidence current as implementation progresses.

## Delivery sequence and evidence

| Workstream | Required implementation | Evidence needed |
| --- | --- | --- |
| Cloud dialogue | Explicit reasoning budget; fixed provider qualification; bounded calls; failure cost telemetry; grounded short responses; warm voice pipeline | Same-scene model receipts, failure counts, actual billed usage where available, time to usable line and audible speech; in-game playback |
| Dynamic population | Stable actor identity separate from displayed name; discover and initialize newcomers; suspend unavailable actors without fabricating death; explicit departures; no named actor requirement in normal scheduling | Scenarios with changed IDs/names, added and missing residents, interrupted commitments, and save/load |
| Personal knowledge | Save-bound acquaintance records; source-labelled names and claims; own observations/memories only in prompts; introductions update only participants who actually hear them | Stranger cannot name/read another resident; delivered introduction updates knowledge; failed audio and old saves do not inherit future knowledge |
| Dynamic economy | Capability-based sellers/employers; finite resource accounts; connected production; prices, wages and inventories that influence choices | Multiple production/trade cycles, conservation and provenance, unavailable supplier handling, persistence |
| Natural social life | Dynamic partner choice, consent, introductions, context-sensitive dialogue, subjective appraisal and memory; no forced interaction every time | Different pairings and quiet outcomes; believable economic and non-economic exchanges; consequences visible in observer |
| RTS observer | Free overview camera, pan/zoom/rotate, picking/highlighting, follow/event navigation, useful inspection panels and overlays, safe return to first person | Actual in-game visual capture of controls and resident selection; camera mode and plan/action distinction visibly correct |
| Demonstration | A self-running, bounded society session that does not require Calvin to manually play; save/resume; narrated system examples | Recorded runtime evidence, verified persistence and a video showing native movement, voices and economic/social consequences |

## Current boundaries

The current population and social scheduler already use observed resident IDs for many interactions, but fixed legacy trading/production participants and authored demo defaults still exist. Social prompts currently expose a nearby person's global profile name; personal identity knowledge needs implementation. The existing observer has selection/follow tools; full RTS camera control is not yet qualified. These are tracked gaps, not accepted final architecture.

See [system guide](system-guide.md), [model qualification](model-routing.md), [town progress](town-progress.md) and [video plan](demo-videos.md). Passing unit tests is not proof of a working in-game interaction, realistic psychology, or a complete economy.
