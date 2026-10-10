# Continuous integration

FazTestBot uses one central workflow, `.github/workflows/ci.yml`. Module isolation is
implemented with a generated job matrix rather than duplicated workflow files.

## Triggers

The workflow runs on:

- pushes to `feature/**`, `develop`, and `master`;
- pull requests targeting `develop` or `master`;
- manual dispatch;
- a weekly scheduled compatibility/security run.

Concurrent runs for the same ref cancel older runs. Workflow permissions are
read-only, and every external GitHub Action is pinned to a full commit SHA.

## Blocking stages

| Stage | Responsibility |
| --- | --- |
| `discover` | Produces the module matrix from explicit packages under `modules/`. |
| `repository` | Enforces test ownership, secret/artifact policy, clean merges, and pinned Actions. |
| `quality` | Lints maintained code, checks formatting, compiles all Python, and performs an offline application smoke. |
| `tests` | Runs the complete suite with branch coverage on Python 3.10 and 3.13. |
| `modules` | Imports and validates every module independently, then runs its owned lint, format, and test gates. |
| `security` | Resolves and audits runtime dependencies with `pip-audit`. |
| `CI / required` | Fails unless every preceding stage succeeds. Use this as the branch-protection check. |

Coverage is uploaded from Python 3.13 for inspection. A global percentage is not yet
used as a merge gate because the legacy modules predate automated tests. New modules
are gated by the presence and success of their own suite and by Ruff lint/format
checks scoped to the module and its tests. The legacy allowlist temporarily defers
both owned tests and module-scoped Ruff checks; removing an entry enables both gates.

## Recommended GitHub branch protection

For `develop`:

- require pull requests;
- require `CI / required`;
- require the branch to be current before merge;
- block force pushes and deletion;
- dismiss stale approvals after new commits.

For `master`, use the same rules and require an explicit maintainer approval. This
repository intentionally has no deployment job: merging code and operating the
long-polling Telegram process remain separate until a deployment target, health
check, secret store, and rollback procedure exist.

## Failure ownership

The module matrix makes failures attributable to a module. A failure in `quality` or
`repository` is cross-cutting and must not be bypassed from a module PR. Dependency
audit failures require upgrading, replacing, or explicitly reviewing the affected
package; temporary exceptions should include a reason and expiry date rather than a
blanket ignore.
