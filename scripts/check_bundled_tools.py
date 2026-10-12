#!/usr/bin/env python3
"""Fail a distribution build when the bundled compression tools are missing.

``src/imslim/bin/<platform>/`` is gitignored and produced by
``scripts/build_tools.sh``, but the build backend packages whatever sits in the
module directory: without this guard a fresh checkout builds a wheel whose
tools are all absent, which installs happily and only fails at runtime.

Run from the repository root:
  python3 scripts/check_bundled_tools.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from imslim.binary_resolver import BIN_DIR, KNOWN_TOOLS, _platform_dir

# svgo is a shell wrapper that execs node directly, so node is required at
# runtime even though resolve_tool() is never asked for it by name.
EXTRA_TOOLS = ("node",)


def main() -> int:
    bin_dir = BIN_DIR / _platform_dir()
    expected = (*KNOWN_TOOLS, *EXTRA_TOOLS)
    missing = [name for name in expected if not (bin_dir / name).is_file()]
    if missing:
        print(
            f"missing bundled tools in {bin_dir}: {', '.join(missing)}\n"
            "run ./scripts/build_tools.sh before building a distribution",
            file=sys.stderr,
        )
        return 1
    print(f"bundled tools present ({len(expected)}): {bin_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
