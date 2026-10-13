import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def case_data():
    return json.loads((ROOT / "datasets/golden/retention.jsonl").read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path, case_data):
    root = tmp_path / "project"
    (root / "configs").mkdir(parents=True)
    (root / "datasets/golden").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    (root / "configs/demo.yaml").write_text((ROOT / "configs/demo.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "datasets/golden/retention.jsonl").write_text(json.dumps(case_data, ensure_ascii=False) + "\n", encoding="utf-8")
    return root
