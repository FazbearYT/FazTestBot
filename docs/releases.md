# Release process

FazTestBot uses strict semantic versions (`vX.Y.Z`) and does not use a dedicated
release branch. A release is a promotion of a proven `develop` state to `master`,
not a deployment to a production host.

## Version policy

- `core/version.py` is the only application version source.
- `CHANGELOG.md` contains concise technical release notes for maintainers.
- `history.txt` contains the user-visible development history exposed by the bot.
- A version changes because the scope and compatibility impact justify it, not
  because a fixed number of commits elapsed.
- Tags and GitHub Releases are immutable. Correct a bad release with a new patch
  version instead of moving or replacing an existing tag.

Use MAJOR for intentionally incompatible behavior or a major platform baseline,
MINOR for compatible capability changes, and PATCH for compatible fixes. Stabilizing
changes can accumulate on `develop` without changing the released version; update
the version and both changelogs together when preparing promotion.

## Promotion checklist

1. Stabilize general fixes directly on `develop`; use a `feature/*` branch for an
   isolated subsystem or privileged automation change.
2. Confirm the blocking `CI / required` check is green on `develop`.
3. Update `core/version.py`, `CHANGELOG.md`, and `history.txt` in one reviewed change.
4. Run `python -m scripts.ci.run_all --audit` locally when network access is available.
5. Open and merge a pull request from `develop` to `master` without squashing away
   the reviewed history, then require `CI / required` to pass on `master`.
6. Create an annotated tag at the exact `master` commit and push it:

   ```bash
   git tag -a vX.Y.Z -m "FazTestBot vX.Y.Z"
   git push origin vX.Y.Z
   ```

The tag starts the Release workflow. It proves the commit is in `origin/master`,
checks that the tag matches `core.version`, repeats the full audited CI suite, builds
a source ZIP from the tagged Git tree, emits its SHA-256 checksum, creates a build
provenance attestation, and publishes an immutable GitHub Release.

Run `python -m scripts.release verify --tag vX.Y.Z` to check metadata without
building, or `python -m scripts.release build --ref HEAD` to inspect local artifacts.
Generated files are written under ignored `dist/`.

## Failure and rollback

No application deployment is performed, so a failed workflow does not affect the
running bot. Do not recreate or force-move a public tag. Fix the problem on
`develop`, promote it through `master`, increment the patch version, and publish a
new tag. A GitHub Release can be marked non-latest if a later operational problem is
discovered, while the original artifacts remain available for audit.
