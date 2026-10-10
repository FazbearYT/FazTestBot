"""CLI entry point for repository contract validation."""

from pathlib import Path

from scripts.ci.contract import ContractError, assert_repository_contract


def main() -> int:
    try:
        assert_repository_contract(Path.cwd())
    except ContractError as exc:
        print(exc)
        return 1
    print("Repository contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
