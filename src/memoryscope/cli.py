"""Human and versioned machine interfaces over the same benchmark core."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import typer

from memoryscope import __version__
from memoryscope.adapters import adapter_catalog
from memoryscope.io import InputError, load_config, load_dataset
from memoryscope.reporting import build_report, load_results, summary
from memoryscope.runner import run_benchmark

CLI_SCHEMA_VERSION = "1.0"
app = typer.Typer(no_args_is_help=True, invoke_without_command=True,
                  help="MemoryScope-OK: auditable long-term memory benchmark for AI agents.")


def _json(value: dict[str, Any]) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _result(command: str, data: Any = None, *, error: Exception | None = None,
            jsonl: bool = False) -> None:
    item = {"schema_version": CLI_SCHEMA_VERSION, "command": command, "ok": error is None,
            "data": data, "error": None if error is None else {"type": type(error).__name__, "message": str(error)}}
    if jsonl:
        item["type"] = "result"
    _json(item)


def _reject(command: str, error: Exception, machine: bool, *, jsonl: bool = False,
            code: int = 2, data: Any = None) -> None:
    if machine:
        _result(command, data, error=error, jsonl=jsonl)
    else:
        typer.echo(f"{command} failed: {error}", err=True)
    raise typer.Exit(code)


def _dataset_info(dataset) -> dict[str, Any]:
    return {"case_count": len(dataset.cases), "file_count": len(dataset.sources),
            "categories": dict(Counter(case.category.value for case in dataset.cases)),
            "sources": dataset.sources}


@app.callback()
def main(version: bool = typer.Option(False, "--version", is_eager=True, help="Show package version.")) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def validate(path: Path = typer.Argument(..., help="UTF-8 JSONL file or directory."),
             json_output: bool = typer.Option(False, "--json", help="Emit a versioned JSON result.")) -> None:
    """Validate dataset schema and uniqueness; never execute an agent."""
    try:
        dataset = load_dataset(path)
    except (OSError, ValueError, TypeError) as error:
        _reject("validate", error, json_output)
    if json_output:
        _result("validate", _dataset_info(dataset))
    else:
        typer.echo(f"Valid: {len(dataset.cases)} case(s), {len(dataset.sources)} file(s).")


@app.command("list-agents")
def list_agents(json_output: bool = typer.Option(False, "--json", help="Describe registered adapter types as JSON.")) -> None:
    """List adapter types without creating agents or making network calls."""
    catalog = adapter_catalog()
    if json_output:
        _result("list-agents", {"agents": catalog})
    else:
        for item in catalog:
            typer.echo(f"{item['id']}\tsynthetic={str(item['synthetic']).lower()}\t{item['name']}")
        typer.echo("Demo is synthetic; it is NOT a real AI Agent. Real adapters require their configured credentials.")


@app.command("check-config")
def check_config(config: Path = typer.Argument(..., help="YAML configuration inside the project."),
                 json_output: bool = typer.Option(False, "--json", help="Emit resolved configuration and dataset counts.")) -> None:
    """Check config, paths and data offline; creates no output or agent."""
    try:
        loaded = load_config(config)
        dataset = load_dataset(loaded.dataset, loaded.root)
    except (OSError, ValueError, TypeError) as error:
        _reject("check-config", error, json_output)
    data = {"config_path": str(loaded.path), "dataset": str(loaded.dataset),
            "output_dir": str(loaded.output_dir), "config": loaded.config.model_dump(mode="json"),
            "dataset_info": _dataset_info(dataset)}
    if json_output:
        _result("check-config", data)
    else:
        typer.echo(f"Config valid: {loaded.path}; {len(dataset.cases)} case(s), {len(loaded.config.agents)} agent(s).")
        typer.echo(f"Output parent: {loaded.output_dir}")


@app.command()
def run(config: Path = typer.Argument(..., help="YAML configuration inside the project."),
        json_output: bool = typer.Option(False, "--json", help="Emit one JSON result after completion."),
        jsonl: bool = typer.Option(False, "--jsonl", help="Stream safe lifecycle progress then a final JSON result.")) -> None:
    """Run a benchmark and write evidence; completed does not imply all cases pass."""
    if json_output and jsonl:
        _reject("run", InputError("--json and --jsonl are mutually exclusive"), True)
    latest: dict[str, Any] = {}

    def progress(event: dict[str, Any]) -> None:
        latest.update(event)
        if jsonl:
            _json({"schema_version": CLI_SCHEMA_VERSION, "type": "progress", "command": "run", "data": event})

    try:
        run_dir, results = run_benchmark(config, progress=progress)
    except KeyboardInterrupt:
        _reject("run", RuntimeError("interrupted; existing evidence is incomplete and has not been resumed"),
                json_output or jsonl, jsonl=jsonl, code=130,
                data={"status": "interrupted", "run_dir": latest.get("run_dir")})
    except (OSError, ValueError, KeyError, TypeError) as error:
        _reject("run", error, json_output or jsonl, jsonl=jsonl,
                data={"run_dir": latest.get("run_dir")})
    data = {**summary(results), "run_dir": str(run_dir),
            "results_path": str(run_dir / "results.json"), "events_path": str(run_dir / "events.jsonl"),
            "metadata_path": str(run_dir / "metadata.json")}
    if json_output or jsonl:
        _result("run", data, jsonl=jsonl,
                error=None if results["status"] == "completed" else RuntimeError("benchmark execution failed; inspect saved evidence"))
    elif results["synthetic"]:
        typer.echo(f"SYNTHETIC pipeline {results['status']}: {run_dir}")
        typer.echo("This is not a real Agent benchmark score. See results.json and events.jsonl.")
    else:
        typer.echo(f"Run {results['status']}: {run_dir}")
    if results["status"] != "completed":
        raise typer.Exit(1)


@app.command("run-paired")
def run_paired_command(config: Path = typer.Argument(..., help="Config with an explicit paired declaration."),
                       json_output: bool = typer.Option(False, "--json", help="Emit a versioned JSON result.")) -> None:
    """Audit memory-on/off offline; P0 executes only the controlled synthetic adapter."""
    from memoryscope.paired import run_paired
    try:
        run_dir, result = run_paired(config)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _reject("run-paired", error, json_output)
    data = {"run_dir": str(run_dir), "status": result["status"], "executed_real_agents": 0,
            "pair_status_counts": result["pair_status_counts"],
            "pairs": [{"agent_id": pair["agent_id"], "case_id": pair["case_id"],
                       "status": pair["status"], "comparison": pair["comparison"]} for pair in result["pairs"]]}
    if json_output:
        _result("run-paired", data, error=None if result["status"] == "completed" else
                RuntimeError("paired execution failed; inspect saved evidence"))
    else:
        typer.echo(f"P0 paired protocol {result['status']}: {run_dir}")
        typer.echo("Only controlled synthetic execution is supported. Inspect results.json and paired-report.md.")
    if result["status"] != "completed":
        raise typer.Exit(1)


@app.command()
def report(run_dir: Path = typer.Argument(..., help="Existing run directory."),
           json_output: bool = typer.Option(False, "--json", help="Emit a versioned JSON result."),
           reuse: bool = typer.Option(False, "--reuse", help="Read an existing complete report matching results.")) -> None:
    """Build JSON/CSV/Markdown/radar reports offline; never calls an agent."""
    try:
        result = load_results(run_dir)
        out = build_report(run_dir, reuse=reuse)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _reject("report", error, json_output)
    if json_output:
        _result("report", {**summary(result), "report_dir": str(out.resolve())})
    else:
        typer.echo(json.dumps(summary(result), ensure_ascii=False, indent=2, allow_nan=False))
        typer.echo(f"Report files: {out}", err=True)


@app.command()
def rescore(run_dir: Path = typer.Argument(..., help="Existing run directory."),
            json_output: bool = typer.Option(False, "--json", help="Emit a versioned JSON result.")) -> None:
    """Re-grade saved evidence with the current evaluator; never calls an agent."""
    from memoryscope.rescore import rescore_run
    try:
        out, result = rescore_run(run_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _reject("rescore", error, json_output)
    if json_output:
        _result("rescore", {**summary(result), "run_dir": str(out.resolve()),
                            "source_run_dir": str(run_dir.resolve()), "status_changes": result["status_changes"]})
    else:
        typer.echo(f"Rescored into {out}; {len(result['status_changes'])} status change(s).")
        for change in result["status_changes"]:
            typer.echo(f"  {change['agent_id']}/{change['case_id']}/{change['check_id']}: {change['old']} -> {change['new']}")


@app.command()
def view(run_dir: Path = typer.Argument(..., help="Existing run directory."),
         open_page: bool = typer.Option(False, "--open", help="Open the page in the desktop browser."),
         json_output: bool = typer.Option(False, "--json", help="Emit a versioned JSON result.")) -> None:
    """Write a self-contained HTML page (radar, scores, per-check reasons); never calls an agent."""
    from memoryscope.htmlview import build_view
    try:
        page = build_view(run_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _reject("view", error, json_output)
    if json_output:
        _result("view", {"run_dir": str(run_dir.resolve()), "view_path": str(page.resolve())})
    else:
        typer.echo(f"View: {page}")
    if open_page:
        import webbrowser
        webbrowser.open(page.resolve().as_uri())
