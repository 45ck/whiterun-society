# Resident-chosen social encounters

A scheduled social need can now lead to a resident choosing someone nearby, approaching under an owned Skyrim task, and letting the other person accept or decline. This extends the earlier authored Ysolda–Carlotta encounter to eligible initialized residents. Guards and residents with explicit commitments are excluded. Native proximity supplies candidates; this is not yet qualified vision or hearing perception.

![Actual Skyrim encounter: Adrianne and Idolaf, with generated speech and live inspector](images/resident-social-live.png)

## Three layers

1. Deterministic game-clock reviews age needs and queue feasible opportunities. Quiet periods and unavailable partners require no model request.
2. Jev chooses approach/defer and accept/decline. A language model proposes two brief utterances using the speaker's own traits, needs, memories and observed weather; Jev chooses one. Neither model receives the other resident's private state.
3. Code validates the choice, owns the approach, delivers a stock Kokoro voice, and waits for complete nearby playback. Only then does speech become a remembered claim. After verified route release, each resident privately appraises what they heard.

The appraisals can be neutral, supported or annoyed. The authored consequences are +0.05 familiarity per heard turn, affinity +0.05/0/-0.05, and 0.2 social-need recovery after an accepted completed exchange. They are gameplay rules, not measured psychological effects. Courtesy does not automatically imply friendship. Refusals do not automatically create hostility or satisfy social need. Relationship records feed later social and economic decision contexts.

## Live results

| Scheduled initiator | Resident-chosen partner | Outcome | Private appraisal | Elapsed | Reported model cost |
|---|---|---|---|---:|---:|
| Amren | Saffir | Two delivered turns about tiredness and company | Both supported; affinity +0.05 each | 53.976 s | US$0.001468246 |
| Adrianne | Idolaf | Two delivered turns about weather, work and tiredness | Both neutral; affinity unchanged | 66.090 s | US$0.001533266 |

Each encounter used two GPT-4.1-mini calls and six `typesafe/jev-1.14-20261014` decisions, plus local Kokoro synthesis. The developer selected existing queued initiators for these focused trials; the partner and responses were model choices. No refusal or drama is claimed from these two trials. Decline, defer, interrupted audio, failed release and old-save rollback are covered by deterministic tests.

The native approach receipts placed the pairs 134 and 133 game units apart with the owned package active. Both route releases were verified. The observer screenshot shows Adrianne and Idolaf facing one another nearby, though the camera angle partially occludes Adrianne behind a post. Collision-aware framing remains unfinished.

Save AA at checkpoint 493 and save AB at checkpoint 516 were loaded into fresh game sessions. All compared people, conversations, town records, economic journals and native inventories matched. That proves settled encounters for those saves, not interrupted-conversation recovery or long-term stability. Fralia's trial was refused before any model call because no qualified nearby partner remained. [Compact receipts](evidence/resident-social.json).

The second trial also verified that participating as a partner closes that person's queued social opportunity. The director now refreshes eligibility after each completed event, so a satisfied or unloaded partner is skipped instead of being dispatched from a stale queue.

## Watching and running

Open `/observer` on the live development service, select a roster entry, choose **Relationships** or **Memory**, and use **Follow selected**, zoom and orbit to frame them in Skyrim. The control room reads live state; it cannot spend on models. The in-game inspector shows the selected resident and delivered utterances. Completed outcomes and quiet choices have distinct labels.

![Live control room with Adrianne’s neutral appraisal](images/social-control-room.jpg)

With the model keys supplied via the configured environment variables, enable social opportunities in a bounded director run:

```powershell
python tools/run_daily_life.py --root D:\WhiterunLab --max-events 4 --watch-seconds 60 --model-config D:\WhiterunLab\runtime\jev-config.json --language-config D:\WhiterunLab\runtime\language-config.json
```

The allowance is at most eight inference calls per social event. Speech is currently a two-turn protocol, or a single polite refusal. Workers persist each inference claim before calling the provider; uncertain results are held without automatic repetition. Omitting the language configuration leaves social execution disabled.

## Remaining scope

This is a serialized prototype across an initialized roster of 29, not simultaneous full-town agency. Ordinary Skyrim routines resume after release. Sustained rest, multiple production chains, viable food supply, family relationships, social plans with more than two turns, emergent conflict, player intervention, concurrent task ownership and lip sync remain unfinished. Native audio stays disabled for crash diagnosis; generated voice uses CEF playback. The language can mention sitting, but no seated action is claimed or executed by this social protocol.

Verification: 135 Python tests passed in the full suite, plus two new director eligibility tests; all 78 JavaScript tests passed. Hosted checks are recorded on the published commit.
