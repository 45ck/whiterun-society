# Agent instructions

Read [README.md](README.md) and preserve the source, runtime and evidence boundaries it describes.

## CI cost and delivery

- Batch a coherent implementation candidate after focused local checks; avoid repeated cosmetic pushes or unchanged full reruns.
- Use one integration owner for shared CI, dependency and lockfile changes; reconcile concurrent work before publishing.
- Read failed logs, reproduce the smallest failure, then retry only the necessary failed job and its dependents with a stated reason.
- Keep required QA, security, coverage and release gates. Never bypass hooks, use skip markers or weaken checks to reduce cost.
- Request previews or manual heavy checks only for a concrete review or acceptance need under the existing delivery policy.
- Record the commit, actual commands/results, run links and retry reason; mark unavailable checks NOT_RUN. Runner minutes and deployment counts are not invoices.
- Keep Linux/Windows, plugin/compiler and live-game evidence distinct. Manual native builds require a concrete review or validation need.
- Use the [CI cost guide](docs/ci-costs.md) for this repository's commands and warnings.
