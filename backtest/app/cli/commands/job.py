from __future__ import annotations

from typing import Any

import click

from ..cache import JobCache
from ..client import BackQuantClient
from ..config import CliSettings
from ..errors import CliError, EXIT_LOCAL
from ..output import json_error, json_ok


def _run_with_json_error(handler: Any) -> None:
    try:
        handler()
    except CliError as exc:
        click.echo(json_error(exc.code, exc.message, exc.details))
        raise click.exceptions.Exit(exc.exit_code) from exc


def _cached_entry(cache: JobCache, job_id: str) -> tuple[str | None, str | None]:
    try:
        entry = cache.lookup(job_id)
    except OSError as exc:
        raise CliError(
            code="LOCAL_FILE_ERROR",
            message="cannot read local job cache",
            exit_code=EXIT_LOCAL,
            details={"job_id": job_id, "error": str(exc)},
        ) from exc
    if not isinstance(entry, dict):
        return None, None
    file_path = entry.get("file")
    strategy_id = entry.get("strategy_id")
    return (
        str(file_path) if isinstance(file_path, str) else None,
        str(strategy_id) if isinstance(strategy_id, str) else None,
    )


def register_job_commands(root: click.Group) -> None:
    @root.group(name="job")
    def job_group() -> None:
        """Job command group."""

    @job_group.command(name="show")
    @click.option("--job-id", required=True)
    @click.pass_context
    def show_command(ctx: click.Context, job_id: str) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            cache = JobCache(settings.jobs_cache_path)

            file_path, strategy_id = _cached_entry(cache, job_id)
            remote = client.get_job(job_id)
            click.echo(
                json_ok(
                    {
                        "job_id": job_id,
                        "file": file_path,
                        "strategy_id": strategy_id,
                        "remote": remote,
                    }
                )
            )

        _run_with_json_error(_impl)

    @job_group.command(name="result")
    @click.option("--job-id", required=True)
    @click.pass_context
    def result_command(ctx: click.Context, job_id: str) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            cache = JobCache(settings.jobs_cache_path)

            file_path, strategy_id = _cached_entry(cache, job_id)
            remote = client.get_job_result(job_id)
            click.echo(
                json_ok(
                    {
                        "job_id": job_id,
                        "file": file_path,
                        "strategy_id": strategy_id,
                        "remote": remote,
                    }
                )
            )

        _run_with_json_error(_impl)

    @job_group.command(name="log")
    @click.option("--job-id", required=True)
    @click.option("--offset", type=click.IntRange(min=0))
    @click.option("--tail", type=click.IntRange(min=1))
    @click.pass_context
    def log_command(ctx: click.Context, job_id: str, offset: int | None, tail: int | None) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            cache = JobCache(settings.jobs_cache_path)

            file_path, strategy_id = _cached_entry(cache, job_id)
            remote = client.get_job_log(job_id, offset=offset, tail=tail)
            click.echo(
                json_ok(
                    {
                        "job_id": job_id,
                        "file": file_path,
                        "strategy_id": strategy_id,
                        "remote": remote,
                    }
                )
            )

        _run_with_json_error(_impl)
