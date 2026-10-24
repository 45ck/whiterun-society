# Resident-chosen seated rest

Idolaf chose an available bench, travelled under our owned package, sat at that exact furniture reference for 30 game minutes, and released the task. Only after the release receipt did his simulated fatigue fall from 1.00 to 0.65. This is an authored short-break rule, not sleep or a measured physiological effect.

![Idolaf physically seated at the selected Whiterun bench](images/rest-seated-live.png)

## Observed trial

The experimental plugin loaded and the previous managed society save restored in 42.53 seconds. The original rest package bytes were reused; the earlier cold-launch hang remains unexplained. A successful retry establishes this launch, not a root-cause fix or general stability.

The normal game-clock queue offered Idolaf a need review after his social cooldown. Jev selected `rest_at_bench` with one call, reporting US$0.00008715. Native package ownership and Papyrus alias binding were confirmed. The route began 4,129 game units from the bench and arrived about 51 units away. The bridge then observed the exact furniture reference, native sitting state, owned package and continuous game time: 30.002 game minutes across 5,401 samples. Paused time, clock jumps, combat, interrupted sitting and failed release do not qualify recovery.

The whole event took 120.359 seconds, including decision, travel, attendance and settlement. All 29 native accounting inventories were unchanged. No bread, grain or money was created. The resident remembers the completed break. Adrianne's separate need review selected defer; no rest or recovery was fabricated for her. [Compact evidence](evidence/seated-rest.json).

## Save verification and retained failures

Save AD at checkpoint 526 restored every compared field, including the rest journal and fatigue recovery. Save AF at checkpoint 530 also restored all compared fields after Adrianne's deferral. The latter proof additionally binds the enabled plugin order and SHA-256 of our generated plugins. The restore helper refuses to load it with a changed plugin order or changed generated plugin bytes. Older proofs without that manifest retain their original, narrower qualification.

Two save attempts were rejected and left untouched. AC changed during saving without a detailed diagnostic. The new diagnostics showed that AE differed only because guard 225390 left the loaded scene; all native accounting balances matched. Comparisons now retain the same expected resident IDs and use fresh native inventory observations when an actor unloads. They never fill missing observations from expected balances. Missing observations and actual balance changes still fail. All accounting inventories remain separately compared.

## Scheduling and visibility

High hunger with no carried food and no affordable seller route previously prevented considering other needs. The scheduler now offers a review when a qualified break or livelihood is available. Hunger stays unmet unless food is actually consumed. The resident remains free to defer; the fallback does not compel work or rest.

The browser inspector shows observed seated minutes and fatigue. The native inspector now puts rest progress before personality details, and distinguishes a previous speech intention from the current activity. The roster uses the active task phase instead of leaving a resting resident labelled as deciding.

## Launch and limits

Rest remains an explicit experimental opt-in. Stage the original `WhiterunRest.esp` built by this repository, then launch the isolated lab with:

```powershell
python tools/launch_demo.py --root D:\WhiterunLab --audio-diagnostic --experimental-rest --save WS-Rest-20261024-AF
```

The default profile configuration disables an existing rest entry when the opt-in is absent. Enabling it without the staged plugin is rejected. Do not attempt to restore a rest-enabled save under a different plugin configuration. The installed original game and campaign saves remain separate.

Native audio remains disabled for diagnosis. One bench-rest trial is not proof of overnight sleep, every NPC's rest routine, long-term stability or a sustainable economy. Carlotta was unloaded when follow-on work eligibility was checked, so no production shift or wage is claimed. Food supply, indoor destinations, business opening times and simultaneous actor task ownership remain development work.

Verification: 138 Python tests passed in the full suite, plus five new save-identity/observation tests; all 78 JavaScript tests passed. Hosted checks are attached to the published revision.
