# A finite market day

This scenario connects four existing resident events: a paid-work opportunity,
Carlotta's household stock review, Ysolda's meal and Carlotta's meal. The sequence
offers opportunities; it does not prescribe acceptance, sale or consumption.
Refusals remain valid outcomes. It is an authored demonstration, not a continuous
daily calendar or a labour-market model.

## Run without an opening playthrough

From a prepared isolated installation, with the model's configured key available
in its named environment variable:

```powershell
python tools/run_market_day.py --root D:\WhiterunLab --id market-unique-id --model-config D:\WhiterunLab\runtime\jev-config.json
```

The runner attaches to a fresh connected lab bridge or invokes the existing
observer launcher. A new world gets explicitly prepared bread and a single
two-grain import, then its society is bootstrapped. Existing managed saves keep
their resources. No campaign save is overwritten. The game starts in Whiterun;
character creation and the opening quests are not required.

The four stages have at most nine model calls in total. Walking, work attendance,
inventory confirmation and checkpoint binding do not call a model. Each claim
is saved before inference. An unsettled existing stage stops the runner instead
of automatically repeating inference. The current save owns the scenario cursor,
results and baseline; a local progress file never overrides a loaded older save.
Completed stage advances and completed day IDs are idempotent, including after a
later day begins. A completed stage can be recorded after a runner interruption
without paying for a new decision.

The observer shows the stage sequence, actual stocks, choices and final metrics.
The gold metric covers the two participating residents, not all Whiterun. Trade,
production and meal counts refer to committed records during this scenario.
This is still an observer demonstration; direct player intervention, daily
schedule choice, voiced conversation and lips remain unfinished.

## Audio diagnostic mode

Repeated lab crashes were observed on audio-manager/XAudio2 stacks, including one
after approximately five minutes of process uptime. This has not been diagnosed
to a root cause. A separate, explicit diagnostic option disables audio only in
the isolated profile on a fresh process:

```powershell
python tools/run_market_day.py --root D:\WhiterunLab --id diagnostic-unique-id --model-config D:\WhiterunLab\runtime\jev-config.json --audio-diagnostic
```

The UI labels this mode and launch evidence records it. It is not an audio fix,
does not qualify voice, and cannot establish stability with sound enabled. A
normal fresh launch without the option restores the normal profile defaults.
Attaching to a running diagnostic process preserves its current audio mode.
The original installation and its INIs are untouched.

The `bEnableAudio` setting is listed in the [Skyrim SE INI settings project](https://github.com/Pickysaurus/skyrimse-ini-settings/blob/master/settings.json).
The native readback uses the matching installed SKSE Utility script's
`GetINIBool` interface. Readback may report unavailable if a binding is absent;
configuration intent and actual engine readback must remain distinguishable.

## Checks

Tests cover stage ownership, settled-stage requirements, refusal outcomes,
duplicate advancement, restoring an older queue, completed-day reuse and stopping
after a held decision. A separate profile test verifies that diagnostic audio is
opt-in and normal configuration restores defaults without changing the source INI.
Employer deferral now records the employer's own decision, rather than falsely
attributing it to the worker.
