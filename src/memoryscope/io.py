"""Input loading and filesystem containment checks."""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from memoryscope.models import BenchmarkCase, RunConfig, upgrade_case


class InputError(ValueError):
    """A configuration or dataset cannot be executed safely."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate object key: {key}")
        result[key] = value
    return result


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    loader.flatten_mapping(node)
    return unique_object([
        (loader.construct_object(key, deep=deep), loader.construct_object(value, deep=deep))
        for key, value in node.value
    ])


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contained_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise InputError(f"path escapes project root: {path}") from error
    return resolved


@dataclass(frozen=True)
class LoadedConfig:
    config: RunConfig
    path: Path
    root: Path
    dataset: Path
    output_dir: Path
    raw: bytes


def load_config(path: Path) -> LoadedConfig:
    config_path = path.resolve(strict=True)
    root = next((parent for parent in config_path.parents if (parent / "pyproject.toml").is_file()), None)
    if root is None:
        raise InputError("configuration must be inside a project containing pyproject.toml")
    raw = config_path.read_bytes()
    try:
        parsed = yaml.load(raw.decode("utf-8"), Loader=UniqueKeyLoader)
        config = RunConfig.model_validate(parsed)
    except (ValueError, TypeError, yaml.YAMLError) as error:
        raise InputError(f"invalid configuration {config_path}: {error}") from error
    dataset = contained_path(config_path.parent / config.dataset, root)
    output_dir = contained_path(config_path.parent / config.output_dir, root)
    if output_dir == root or output_dir == config_path.parent:
        raise InputError("output_dir must be a dedicated directory")
    dataset_dir = dataset if dataset.is_dir() else dataset.parent
    if output_dir.is_relative_to(dataset_dir) or dataset_dir.is_relative_to(output_dir):
        raise InputError("output_dir and the dataset directory must not overlap; use separate data and runs directories")
    return LoadedConfig(config, config_path, root, dataset, output_dir, raw)


@dataclass(frozen=True)
class LoadedDataset:
    cases: list[BenchmarkCase]
    sources: list[dict[str, str]]
    snapshot: bytes


def load_dataset(path: Path, root: Path | None = None) -> LoadedDataset:
    path = path.resolve(strict=True)
    if root:
        contained_path(path, root)
    if path.is_dir():
        files = [
            filename
            for filename in sorted(path.rglob("*.jsonl"))
            if not filename.name.startswith("._")
        ]
    else:
        files = [path]
    if not files:
        raise InputError(f"no JSONL files found: {path}")
    cases: list[BenchmarkCase] = []
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for filename in files:
        if filename.suffix != ".jsonl":
            raise InputError(f"dataset file must end in .jsonl: {filename}")
        if root:
            contained_path(filename, root)
        raw = filename.read_bytes()
        source_path = str(filename.relative_to(root)) if root else str(filename)
        sources.append({"path": source_path, "sha256": sha256_bytes(raw)})
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as error:
            raise InputError(f"dataset must be UTF-8: {filename}") from error
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line, object_pairs_hook=unique_object)
                case = BenchmarkCase.model_validate(upgrade_case(data))
            except (ValueError, TypeError) as error:
                raise InputError(f"{filename}:{number}: {error}") from error
            if case.id in seen:
                raise InputError(f"{filename}:{number}: duplicate case ID {case.id}")
            seen.add(case.id)
            cases.append(case)
    if not cases:
        raise InputError("dataset must contain at least one case")
    snapshot = "".join(json.dumps(case.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n" for case in cases).encode("utf-8")
    return LoadedDataset(cases, sources, snapshot)


ENV_FILE = ".env"


def load_env_file(root: Path) -> list[str]:
    """Load KEY=VALUE lines from ``<project>/.env`` into this process only.

    Existing environment variables win. Values are never returned or logged;
    only the names that were loaded are reported for the run manifest.
    """
    path = root / ENV_FILE
    if not path.is_file():
        return []
    loaded = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if not separator or not key.isidentifier():
            raise InputError(f"{ENV_FILE}:{number}: expected KEY=VALUE")
        if value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def write_json(path: Path, value: Any) -> None:
    # Run directories are new and private to one invocation; never overwrite an artifact.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
