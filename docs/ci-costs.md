# CI cost and delivery

Keep necessary verification and ship useful changes. Reduce redundant candidates
and repeated work; a smaller bill is not evidence of adequate QA.

## Repository workflow

Use a focused branch and a coherent candidate. Keep source tests separate from in-game evidence; no repository check proves an NPC performed an action inside Skyrim.

## Choose checks by the changed risk

| Change | First check | Required follow-through |
| --- | --- | --- |
| Simulation change | `python -m unittest discover -s tests -v` | During diagnosis, use unittest's `-p` option for the affected existing test file, then run the applicable suite. |
| Observer/UI change | `npm ci` then `npm test` | Keep the Node tests and relevant simulation checks; test actual game behavior separately when claimed. |
| Plugin/compiler change | Follow `.github/workflows/tests.yml` | Preserve Linux/Windows, generated-plugin readback and Windows Papyrus compiler evidence. |

Focused checks shorten diagnosis. They do not replace existing merge, release,
security, compatibility, coverage or acceptance requirements. Shared runtime,
dependency, test-runner or workflow changes need the broader applicable gates.

## Publish a coherent candidate

1. Inspect current branches and open PRs. Assign one integrating writer for shared
   CI, configuration and lockfiles; preserve other agents' work.
2. Finish one reviewable increment, run its focused checks and required local gate,
   then publish together. Keep ownership claims timely where the repository requires them.
3. Read the actual remote result for that commit. On failure, capture the first
   relevant error, diagnose locally where possible, and retry the smallest failed
   job set only when a fix or transient-failure explanation warrants it.
4. Request a preview or manual heavy run when someone needs that result. Reuse
   valid evidence for an unchanged candidate; do not poll by dispatching workflows.
5. Record commit/PR, check scope, commands, outcomes, run links and retry reason in
   the existing handoff or change record. Keep blocked and unrun checks explicit.

## CI/CD warnings

> [!WARNING]
> Simulation tests run on pushes and PRs across Linux and Windows. Batch intermediate fixups before publishing. The separate native UI build is manual and may run for up to 90 minutes; dispatch only for the reviewed native candidate or a required baseline.

GitHub can repeat dependent jobs when a failed job is rerun. A cancelled or
previously green run is not proof about a changed candidate. Do not add `[skip ci]`,
disable required jobs, lower thresholds or use forced green results as a cost control.
Path-filter changes require coverage proof and compatible required-check behaviour.

Keep licensed game files, mod binaries, model weights, saves, credentials and runtime databases out of commits. Native build output remains unqualified until its existing acceptance requirements are met.

## Measure the outcome

Use the existing run/deployment records: accepted change, commit, run attempt, job
duration, outcome and retry reason. Compare runner minutes, elapsed delivery time
and failed/repeated work per accepted change. Keep provider CPU usage, credits and
actual invoices separate; job counts and elapsed wall time alone are not billed cost.
This guidance adds no schedule, workflow, dependency or paid service.

References: [GitHub job reruns](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)
and [skipped workflow checks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs).
