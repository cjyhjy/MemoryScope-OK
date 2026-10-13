"""Command-line entry points for the Phase 1–2 offline foundation."""

import json
from pathlib import Path

import typer

from memoryscope import __version__
from memoryscope.io import InputError, load_dataset
from memoryscope.runner import run_benchmark

app = typer.Typer(no_args_is_help=True, invoke_without_command=True, help="MemoryScope-OK: auditable long-term memory benchmark for AI agents.")


@app.callback()
def main(version: bool = typer.Option(False, "--version", is_eager=True, help="Show package version.")) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def validate(path: Path = typer.Argument(..., help="UTF-8 JSONL file or directory containing JSONL files.")) -> None:
    """Validate dataset schema and uniqueness; never execute an agent."""
    try:
        dataset = load_dataset(path)
    except (OSError, InputError) as error:
        typer.echo(f"Validation failed: {error}", err=True)
        raise typer.Exit(2) from error
    typer.echo(f"Valid: {len(dataset.cases)} case(s), {len(dataset.sources)} file(s).")


@app.command("list-agents")
def list_agents() -> None:
    """List available adapters and their provenance."""
    typer.echo("demo\tsynthetic=true\tDeterministic toy memory fixture; NOT a real AI Agent.")
    typer.echo("codex\tsynthetic=false\tCodex CLI (codex exec) with a DeepSeek model; needs DEEPSEEK_API_KEY.")


@app.command()
def run(config: Path = typer.Argument(..., help="YAML configuration inside the project.")) -> None:
    """Run a benchmark configuration and write auditable JSON artifacts."""
    try:
        run_dir, results = run_benchmark(config)
    except (OSError, InputError) as error:
        typer.echo(f"Run rejected: {error}", err=True)
        raise typer.Exit(2) from error
    if results["synthetic"]:
        typer.echo(f"SYNTHETIC pipeline {results['status']}: {run_dir}")
        typer.echo("This is not a real Agent benchmark score. See results.json and events.jsonl.")
    else:
        typer.echo(f"Run {results['status']}: {run_dir}")
    if results["status"] != "completed":
        raise typer.Exit(1)


@app.command()
def report(run_dir: Path = typer.Argument(..., help="Existing run directory.")) -> None:
    """Print a JSON summary. CSV/Markdown/radar generation is planned for Phase 6."""
    try:
        result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
        if result["schema_version"] != "1.1":
            raise ValueError("unsupported result schema_version")
        summary = {
            "run_id": result["run_id"], "status": result["status"],
            "synthetic": result["synthetic"],
            "agents": [{"agent_id": item["agent_id"], "dimensions": item["dimensions"],
                        "overall_score": item["overall_score"], "synthetic": item["synthetic"]}
                       for item in result["agent_results"]],
            "note": "JSON summary only. CSV, Markdown and radar reports are not implemented yet.",
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Report failed: {error}", err=True)
        raise typer.Exit(2) from error
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
