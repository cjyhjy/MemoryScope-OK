"""Command-line entry points for the Phase 1–2 offline foundation."""

import json
from pathlib import Path

import typer

from memoryscope import __version__
from memoryscope.io import InputError, load_dataset
from memoryscope.reporting import build_report, load_results, summary
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
    typer.echo("dsh\tsynthetic=false\tDeepSeek Harness CLI (dsh --profile headless); needs DEEPSEEK_API_KEY.")


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
    """Rebuild JSON/CSV/Markdown/radar reports from saved results; never calls an agent."""
    try:
        result = load_results(run_dir)
        out = build_report(run_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Report failed: {error}", err=True)
        raise typer.Exit(2) from error
    typer.echo(json.dumps(summary(result), ensure_ascii=False, indent=2, allow_nan=False))
    typer.echo(f"Report files: {out}", err=True)


@app.command()
def rescore(run_dir: Path = typer.Argument(..., help="Existing run directory.")) -> None:
    """Re-grade saved evidence with the current evaluator; never calls an agent."""
    from memoryscope.rescore import rescore_run
    try:
        out, result = rescore_run(run_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Rescore failed: {error}", err=True)
        raise typer.Exit(2) from error
    typer.echo(f"Rescored into {out}; {len(result['status_changes'])} status change(s).")
    for change in result["status_changes"]:
        typer.echo(f"  {change['agent_id']}/{change['case_id']}/{change['check_id']}: {change['old']} -> {change['new']}")
