"""Print a Markdown review table of a dataset directory (default: datasets/golden).

    python scripts/dataset_table.py [datasets/golden] > table.md
"""

import sys
from pathlib import Path

from memoryscope.io import load_dataset
from memoryscope.models import CheckFileStep, CheckMemoryStep, NewSessionStep, ProbeStep


def describe_check(step) -> str:
    if isinstance(step, ProbeStep):
        label = f"probe:{step.id}"
    elif isinstance(step, CheckMemoryStep):
        label = f"memory:{step.id}"
    else:
        label = f"file:{step.path}"
    terms = [f"+{term}" for term in step.expected.include] + [f"−{term}" for term in step.expected.exclude]
    return f"{label} " + " ".join(f"`{term}`" for term in terms)


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "datasets/golden")
    cases = load_dataset(root).cases
    print("| ID | 维度/子类 | 难度 | 描述 | 会话数 | 检查（+必须出现 −不得出现） |")
    print("| --- | --- | --- | --- | --- | --- |")
    for case in sorted(cases, key=lambda item: (item.category.value, item.id)):
        sessions = 1 + sum(isinstance(step, NewSessionStep) for step in case.steps)
        checks = "<br>".join(cell(describe_check(step)) for step in case.steps
                             if isinstance(step, (ProbeStep, CheckMemoryStep, CheckFileStep)))
        kind = case.category.value + (f" / {case.metadata.subcategory}" if case.metadata.subcategory else "")
        print(f"| `{case.id}` | {kind} | {case.metadata.difficulty} | {cell(case.description)} | {sessions} | {checks} |")
    print(f"\n共 {len(cases)} 条。")


if __name__ == "__main__":
    main()
