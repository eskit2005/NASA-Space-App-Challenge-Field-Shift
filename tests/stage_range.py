"""Run a range of pipeline stages and print each result type.

Usage:
    uv run python tests/stage_range.py s3 s6
"""

import sys
from typing import Any

from cropseq.stages.s1_intake import service as s1
from cropseq.stages.s2_environment import service as s2
from cropseq.stages.s3_normalization import service as s3
from cropseq.stages.s4_filtering import service as s4
from cropseq.stages.s5_sequences import service as s5
from cropseq.stages.s6_optimization import service as s6
from cropseq.stages.s7_explanation import service as s7
from cropseq.stages.s8_audit import service as s8

STAGES = ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8")


def run_range(start: str, end: str) -> dict[str, Any]:
    """Run stages from `start` to `end` and return each stage output."""
    if start not in STAGES or end not in STAGES:
        raise ValueError(f"Unknown stage. Use one of: {', '.join(STAGES)}")
    first = STAGES.index(start)
    last = STAGES.index(end)
    if first > last:
        raise ValueError("start must come before end")

    out: dict[str, Any] = {}
    for name in STAGES[first : last + 1]:
        if name == "s1":
            result = s1.run(out.get("s1"))
        elif name == "s2":
            result = s2.run()
        elif name == "s3":
            result = s3.run(out.get("s1"), out.get("s2"))
        elif name == "s4":
            result = s4.run(out.get("s3"))
        elif name == "s5":
            result = s5.run(out.get("s4"))
        elif name == "s6":
            result = s6.run(out.get("s5"), out.get("s3"), out.get("s1"))
        elif name == "s7":
            result = s7.run(out.get("s6"))
        else:
            result = s8.run(out.get("s7"), out.get("s6"))
        out[name] = result
        print(f"{name} -> {type(result).__name__}")

    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: uv run python tests/stage_range.py <start> <end>")
    run_range(sys.argv[1], sys.argv[2])
