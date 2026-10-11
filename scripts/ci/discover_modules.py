"""Print the module matrix consumed by GitHub Actions."""

import argparse
import json
from pathlib import Path

from scripts.ci.contract import discover_modules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    matrix = {"module": discover_modules(Path.cwd())}
    encoded = json.dumps(matrix, separators=(",", ":"))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"matrix={encoded}\n")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
