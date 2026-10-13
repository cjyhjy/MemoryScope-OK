import json

import pytest
from pydantic import ValidationError

from memoryscope.io import InputError, load_config, load_dataset
from memoryscope.models import BenchmarkCase, Expected, upgrade_case


def test_seed_and_directory_loading(project):
    case = load_dataset(project / "datasets").cases[0]
    assert case.id == "retention-001"
    assert case.protocol.mode == "cross_session"
    assert [probe.id for probe in case.probes] == ["port"]


def probe_step(data):
    return next(step for step in data["steps"] if step["type"] == "probe")


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(schema_version="2.0"),
    lambda data: data.update(typo="ignored"),
    lambda data: data.update(id="../escape"),
    lambda data: probe_step(data)["expected"].update(include=[]),
    lambda data: probe_step(data)["expected"].update(include=[" "]),
    lambda data: probe_step(data)["expected"].update(exclude=[""]),
    lambda data: data.update(protocol={"mode": "context_truncation"}),
    lambda data: probe_step(data).update(evaluation={"type": "llm"}),
    lambda data: data["steps"].append({"type": "shell", "content": "rm -rf /"}),
    lambda data: data.update(steps=[step for step in data["steps"] if step["type"] != "new_session"]),
    lambda data: data.update(steps=[step for step in data["steps"] if step["type"] != "probe"]),
    lambda data: data["steps"].insert(0, {"type": "new_session"}),
    lambda data: data["steps"].append(dict(probe_step(data))),
    lambda data: data["metadata"].update(requires=["telepathy"]),
])
def test_invalid_case_is_not_silently_accepted(case_data, mutation):
    mutation(case_data)
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(case_data)


def test_legacy_schema_is_converted_explicitly():
    legacy = {"schema_version": "1.0", "id": "legacy-1", "category": "retention", "description": "d",
              "setup": [{"role": "user", "content": "以后用 uv。"}], "updates": [],
              "distractors": [{"role": "user", "content": "无关。"}],
              "probe": {"type": "question", "content": "用什么？"},
              "expected": {"include": ["uv"], "exclude": []}, "evaluation": {"type": "contains"},
              "protocol": {"mode": "cross_session"}, "metadata": {"difficulty": "easy", "tags": []}}
    case = BenchmarkCase.model_validate(upgrade_case(legacy))
    assert case.source_schema_version == "1.0"
    assert [step.type for step in case.steps] == ["message", "message", "new_session", "probe"]
    legacy["typo"] = 1
    with pytest.raises(ValidationError):
        upgrade_case(legacy)


def test_inconsistent_expected_rejected():
    with pytest.raises(ValidationError):
        Expected(include=["Poetry"], exclude=["poetry"])
    with pytest.raises(ValidationError):
        Expected(include=["uv", "UV"])
    with pytest.raises(ValidationError):
        Expected(include=["postgresql"], exclude=["sql"])


def test_duplicate_ids_across_files_rejected(project, case_data):
    (project / "datasets/golden/another.jsonl").write_text(json.dumps(case_data), encoding="utf-8")
    with pytest.raises(InputError, match="duplicate case ID"):
        load_dataset(project / "datasets")


def test_empty_and_invalid_json_rejected(tmp_path):
    source = tmp_path / "cases.jsonl"
    source.write_text("\n", encoding="utf-8")
    with pytest.raises(InputError, match="at least one"):
        load_dataset(source)
    source.write_text('{"schema_version":"1.0","schema_version":"2.0"}', encoding="utf-8")
    with pytest.raises(InputError, match="duplicate object key"):
        load_dataset(source)
    source.write_text("{bad}", encoding="utf-8")
    with pytest.raises(InputError, match=":1:"):
        load_dataset(source)


@pytest.mark.parametrize("suffix", ["unknown_field: ignored\n", "seed: 2\n", "agents: []\n"])
def test_unknown_duplicate_and_empty_config_rejected(project, suffix):
    config = project / "configs/demo.yaml"
    config.write_text(config.read_text(encoding="utf-8") + suffix, encoding="utf-8")
    with pytest.raises(InputError):
        load_config(config)


def test_config_path_is_relative_to_config_and_cannot_escape(project, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    loaded = load_config(project / "configs/demo.yaml")
    assert loaded.dataset == project / "datasets/golden/retention.jsonl"
    config = project / "configs/demo.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("../runs", "../../escape"), encoding="utf-8")
    with pytest.raises(InputError, match="escapes project root"):
        load_config(config)


def test_symlink_escape_rejected(project, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / "runs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(InputError, match="escapes project root"):
        load_config(project / "configs/demo.yaml")


@pytest.mark.parametrize("output", ["../datasets/golden/runs", "../datasets", "../datasets/golden"])
def test_output_and_dataset_directories_cannot_overlap(project, output):
    config = project / "configs/demo.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("../runs", output), encoding="utf-8")
    with pytest.raises(InputError, match="must not overlap"):
        load_config(config)


def test_env_file_loads_names_only_and_never_overrides(tmp_path, monkeypatch):
    import os

    from memoryscope.io import load_env_file
    (tmp_path / ".env").write_text("# key\nMS_TEST_KEY='abc'\nexport MS_TEST_OTHER=1\nMS_TEST_SET=new\n", encoding="utf-8")
    monkeypatch.delenv("MS_TEST_KEY", raising=False)
    monkeypatch.delenv("MS_TEST_OTHER", raising=False)
    monkeypatch.setenv("MS_TEST_SET", "old")
    assert load_env_file(tmp_path) == ["MS_TEST_KEY", "MS_TEST_OTHER"]
    assert os.environ["MS_TEST_KEY"] == "abc" and os.environ["MS_TEST_SET"] == "old"
    (tmp_path / ".env").write_text("not valid\n", encoding="utf-8")
    with pytest.raises(InputError):
        load_env_file(tmp_path)
