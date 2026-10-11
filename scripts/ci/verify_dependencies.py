"""Verify that installed direct dependencies match exact repository pins."""

from __future__ import annotations

import argparse
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

EXACT_REQUIREMENT = re.compile(
    r"^\s*([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s;]+)\s*(?:;.*)?$"
)


class DependencyVerificationError(RuntimeError):
    """A manifest or installed distribution does not match the exact-pin contract."""


def read_exact_pins(path: Path) -> dict[str, str]:
    """Read one simple requirements file and reject non-exact declarations."""

    pins: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = EXACT_REQUIREMENT.fullmatch(line)
        if match is None:
            raise DependencyVerificationError(
                f"{path}:{line_number}: dependency must use one exact == pin"
            )
        name, expected = match.groups()
        normalized = name.lower().replace("_", "-")
        if normalized in pins:
            raise DependencyVerificationError(f"{path}:{line_number}: duplicate pin for {name}")
        pins[normalized] = expected
    if not pins:
        raise DependencyVerificationError(f"{path}: no dependency pins found")
    return pins


def verify_installed(paths: list[Path]) -> list[str]:
    """Return every missing or mismatched direct distribution."""

    errors: list[str] = []
    expected: dict[str, str] = {}
    for path in paths:
        try:
            pins = read_exact_pins(path)
        except (OSError, DependencyVerificationError) as error:
            errors.append(str(error))
            continue
        for name, pinned_version in pins.items():
            previous = expected.get(name)
            if previous is not None and previous != pinned_version:
                errors.append(f"conflicting pins for {name}: {previous} and {pinned_version}")
            expected[name] = pinned_version

    for name, expected_version in sorted(expected.items()):
        try:
            actual_version = version(name)
        except PackageNotFoundError:
            errors.append(f"{name} is not installed (expected {expected_version})")
            continue
        if actual_version != expected_version:
            errors.append(f"{name}=={actual_version} is installed; expected {expected_version}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", nargs="+", type=Path)
    args = parser.parse_args()
    errors = verify_installed(args.requirements)
    if errors:
        print("Dependency verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Direct dependency pins: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
