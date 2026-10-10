# Contributing to FazTestBot

## Branch flow

Create feature branches from the current `develop` branch. Changes return through a
pull request to `develop`; release promotion from `develop` to `master` is a separate
decision. Direct pushes to protected branches should be disabled in GitHub settings.

## Definition of a module

A directory `modules/example/` is discovered only when it contains `__init__.py`.
It must export an object named `example_module` that inherits `BaseModule`, passes
`validate()`, and uses unique `module_id` and callback-prefix values.

Every new module must also provide:

```text
tests/example/
|-- __init__.py
`-- test_*.py
```

Tests should cover business rules, Telegram handler routing, invalid input, access
control, external-service failure, and persistence/recovery when applicable. Unit
tests must not call Telegram or another live external service. Use fakes or mocks and
keep optional live smoke tests outside the blocking CI path.

The entries in `.ci/legacy-modules-without-tests.txt` are temporary debt for modules
that existed before this policy. Do not add new modules to that file. Remove a legacy
entry in the same change that introduces its first test suite.

## Local validation

Install both runtime and development dependencies:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Run the blocking pipeline locally:

```bash
python -m scripts.ci.run_all
```

Run the dependency vulnerability query as well when network access is available:

```bash
python -m scripts.ci.run_all --audit
```

The repository contract rejects committed secrets, runtime databases, Graphify
output, unresolved merge markers, unpinned GitHub Actions, and new modules without
tests. Never weaken a check only to make a pull request green; document and fix the
underlying problem.
