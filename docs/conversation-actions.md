# Conversations that can lead to actions

NPCs can now choose a food, rest or livelihood review after hearing an exchange. Jev sees only their own needs, inventory, commitments, memories and the lines they heard. It can choose a follow-up, a subjective relationship response, or no new errand.

```mermaid
flowchart LR
  A[Confirmed nearby speech] --> B[Resident appraises heard words]
  B --> C[Continue without an errand]
  B --> D[Choose food / rest / work review]
  D --> E[Save a source-linked queue entry]
  E --> F[Recheck resources and duties]
  F --> G[Resident chooses current action]
  G --> H[Native execution and verification]
  G --> I[Defer or change plan]
```

A follow-up records the source encounter, actor, focus, delivery IDs and heard claims. An existing pending need review receives that source instead of creating a duplicate errand. The next decision retains the source and rechecks current options. Resident-chosen follow-ups take precedence over demo social alternation and new operator-offered encounters. Unrelated journey cohorts cannot consume their event budget first. Speech never creates money, inventory, completed work or recovery. Choosing a review is not a promise, and finishing a review can legitimately end in deferral.

The observer shows the conversation source beside the current plan. Metrics distinguish chosen follow-ups, pending reviews, completed/held plans and actual outcomes. These are implementation traces, not a causal experiment proving why a model chose an action.

## Restrictions removed

Guards and residents with recorded duties are no longer categorically excluded from conversation, market visits, job opportunities or seated breaks. Their own commitments remain decision context. Social partners, sellers and advertised employers are no longer truncated to the nearest six. A seated break no longer requires crossing a hard fatigue threshold before it can appear in a resident's available choices.

Current native occupancy still matters. Actors already owned by another simulation activity cannot be assigned twice. Combat, sleep transitions and running Skyrim scenes currently defer new routing because those engine activities own the actor. There is no permanent quest-character blacklist in this path. Disabling every Skyrim quest or forcibly stopping native scenes has not been implemented; simply deleting these occupancy checks would produce competing packages and failed movement. A dedicated society-priority scene takeover remains required if the lab should replace those behaviors.

Model calls and native workers retain execution budgets. This implementation has three follow-up domains, one food commodity and one production recipe; it is not unrestricted planning or a complete organic economy. Spontaneous dialogue still needs stronger factual grounding and lower latency. Generating a departure excuse does not create a real work obligation.

## Verification

Controlled tests exercise heard dialogue → chosen review → native consumption acknowledgement → one loaf removed, along with no duplicate consumption. They also cover no follow-up from unheard words, merging an existing review, removal of future intentions on an older save, and more than six nearby guard candidates with duties. These tests use authored choices; live model selection of the new follow-up actions must be measured separately.


## Native qualification

A Whiterun guard and Idolaf completed six voiced turns while three other residents travelled. The native cohort observed three simultaneous owned travel packages and 664 speech-overlap frames; these are correlated frame samples. Both speakers then selected food reviews. The first four-event budget ended with those reviews pending. A second two-event run, after prioritizing resident follow-ups, executed both intentions: the guard chose and consumed one carried loaf; Idolaf chose a market visit, found no seller and gained no food. No participant outcome was forced.

The two runs made 19 and 2 model calls, reporting $0.002052118 and $0.000329448 respectively. Reply dispatch gaps were 9.076–16.118 seconds (five samples), worse than the earlier combined-choice encounters. The guard's city and patrol claims are unsupported, and the exchange was ordinary city small talk rather than a food request. The trace establishes that heard dialogue can feed a subsequent resident choice, not that these words logically required a meal or fulfilled a promise.

The save `WS-FollowThrough-20261025-AY`, checkpoint 1299, restored all 16 compared fields, including source-linked plans and inventory observations. [Native trace and limitations](evidence/conversation-actions.json) · [Six guard–Idolaf voice assets](https://45ck.github.io/whiterun-society/#voice-example). They are synthesized assets used by confirmed overlay playback, not game-audio recordings. No new gameplay screenshot was taken.

The implementation passed hosted validation on Windows and Ubuntu: 283 Python tests, 111 JavaScript tests, plugin builds and Windows Papyrus compilation. The subsequent scheduler-priority change passed six director tests and six failure-isolation tests locally; its hosted validation is tracked separately. One old local test enforced the removed duty exclusion and was corrected to retain the spatial and private-knowledge checks.
