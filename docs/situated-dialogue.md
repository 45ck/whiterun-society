# Conversations inside an established town

The target is an ongoing town where people recognize neighbours, act on needs and commitments, and sometimes exchange only a greeting. A conversation should follow the situation and the previous line rather than generate isolated speeches. This implementation is a step toward that target; simultaneous town-wide social activity remains unfinished.

## Context and choice

Each speech proposal receives the observed game clock, the latest line actually heard, whether the speaker has already spoken, their own commitments, relationship band, known identity and recorded experiences. The language layer proposes two intentions and lines. Jev chooses the intention. Deterministic code verifies the output and arranges local voice playback. After hearing a line, the listener may reply, close politely or leave quietly. The turn budget is an execution ceiling, not a conversational goal.

One-word acknowledgements are valid. The old 8–30-word prompt encouraged padded greetings and farewells; it now allows 1–30 words. Closing turns must acknowledge or answer what was said without introducing a new question. A person can say goodbye without inventing an urgent job or appointment. Suggestions to sit are excluded while the social executor cannot perform them.

Time-of-day bands are authored rules: morning 05:00–11:59, afternoon 12:00–16:59, evening 17:00–21:59, night otherwise. Unknown clock readings require neutral wording. Literal mismatched time greetings and question marks on a closing line are rejected. These narrow checks cannot establish semantic relevance, factual grounding or naturalness; quotation, indirect language and nuanced endings need a richer evaluator.

## Established neighbours and genuine new acquaintances

An explicit, save-bound `POST /town/social-background` accepts an event ID and a cohort of existing resident IDs. It establishes knowledge of names and a minimum familiarity of 0.1 for that cohort. It does not assign friendship, change affinity, create heard turns, invent shared memories, transfer inventory or overwrite a name already personally learned. The source is `authored_shared_town_background`, visibly distinguished in the inspector from a delivered introduction.

The current lab cohort contains **20 civilian residents**. Applying this scenario prior introduced **379 directed name records** and preserved every existing memory. This is initial world state, not evidence that 379 conversations happened. Guards and future arrivals are not silently included. A repeated event is idempotent; changing its cohort is rejected. Restoring a save restores its knowledge state. [Initial-state receipt](evidence/established-town-background.json)

The speech prompt treats established neighbours as already acquainted: no repeated name exchange or “nice to meet you.” Familiarity does not grant access to private needs, stock, motives or invented shared events. Actual heard speech and later subjective appraisal continue to accumulate independently.

## Measure interaction rather than just successful audio

The observer separates delivered lines, repeated greetings, exact within-scene repetitions, line length, clock-known coverage, time-checked greetings and questions introduced at closing. Unknown historic clock context is excluded from the time-check denominator. Word cues for smalltalk, courtesy, weather, business and conflict overlap; they are not semantic classifications.

Human review should cover whether the opening fits the relationship, whether a response addresses the prior line, whether claims have support, whether the topic changes naturally, and whether the ending fits the exchange. Semantic relevance and human ratings remain unmeasured. The existing reply-dispatch metric includes model calls, checkpointing and voice synthesis; it is not measured acoustic onset. The prior two reply gaps were 10.630 and 10.256 seconds, which miss the natural-conversation target.

## What still limits the living-town experience

Two live attempts after the initial-state change are retained in [the dialogue receipt](evidence/situated-dialogue-live.json). Heimskr's route to Ahlam lost native package ownership, so no line was delivered. Olfrid then approached Carlotta; she declined, spoke one line, and the encounter released. The refusal still invented household duties, and its unselected alternative claimed they had been chatting. That exposed an incorrect `closing` label on a declined approach. Refusal now has a dedicated context stage, with regression checks for those two observed phrases. This subsequent correction has unit coverage but no fresh live qualification. One refusal does not test multi-turn relevance or reply latency.

The 236-test Python suite passed before the final refusal/fairness changes; afterward, all six dialogue-context, eight identity and twelve social tests passed. All 101 JavaScript tests passed. The native save `WS-EstablishedTown-20261025-AS`, checkpoint 953, restored all 16 compared fields, including people, town, conversation and inventories. Initial acquaintances therefore persist through Skyrim saves.

The bridge supports up to eight exclusive travel tasks, or six background tasks leaving two slots for one disjoint conversation. The [new allocation and checkpoint rules](concurrent-society.md) are integration tested; the first live background trial completed one journey but found no eligible pair, so simultaneous native travel and speech remain unqualified. Transactions remain serialized. Not every NPC is under full agent routine control; released actors can resume vanilla schedules. Six speech turns and bounded model calls prevent an encounter from running indefinitely. Removing those numbers alone would not create meaningful autonomy.

Next architecture work is persistent per-resident plans, multiple local encounters, resumable routines and per-encounter speech channels. The initial travel/conversation participant reservations are implemented; broader overlapping work, economic effects and multiple conversations remain requirements. The observer distinguishes the active conversation from background journeys and exposes their overlap counters.

Opportunity selection now tracks the last attempted encounter separately from social need relief. A failed encounter rotates behind residents who have not had an opportunity; it does not satisfy social needs. Existing settled social events supply the ordering for older saves without invented backfilled memories.
