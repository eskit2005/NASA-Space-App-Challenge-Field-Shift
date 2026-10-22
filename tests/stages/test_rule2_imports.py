"""Test enforcing architectural Rule 2:
Stages import ONLY from cropseq.contracts and their own folder. Never from other stages.
"""

import ast
from pathlib import Path

STAGES_DIR = Path(__file__).resolve().parents[2] / "src" / "cropseq" / "stages"


def test_rule2_no_cross_stage_imports() -> None:
    stage_names = {p.name for p in STAGES_DIR.iterdir() if p.is_dir() and not p.name.startswith("__")}

    for stage_name in stage_names:
        stage_path = STAGES_DIR / stage_name
        other_stages = stage_names - {stage_name}

        for py_file in stage_path.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for other in other_stages:
                            assert other not in alias.name, (
                                f"{py_file.name} violates Rule 2 by importing {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for other in other_stages:
                        assert other not in mod, (
                            f"{py_file.name} violates Rule 2 by importing from {mod}"
                        )
