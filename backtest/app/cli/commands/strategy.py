from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from ..cache import JobCache
from ..client import BackQuantClient
from ..config import CliSettings
from ..errors import CliError, EXIT_LOCAL, EXIT_REMOTE
from ..output import json_error, json_ok

_DEFAULT_STRATEGY_TEMPLATE = """from rqalpha.api import *


def init(context):
    pass


def handle_bar(context, bar_dict):
    pass
"""


def _read_strategy_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(
            code="LOCAL_FILE_ERROR",
            message="cannot read local strategy file",
            exit_code=EXIT_LOCAL,
            details={"file": str(file_path), "error": str(exc)},
        ) from exc


def _strategy_id_from_path(file_path: Path) -> str:
    return file_path.stem


def _write_strategy_file(file_path: Path, code: str) -> None:
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")
    except OSError as exc:
        raise CliError(
            code="LOCAL_FILE_ERROR",
            message="cannot write local strategy file",
            exit_code=EXIT_LOCAL,
            details={"file": str(file_path), "error": str(exc)},
        ) from exc


def _run_with_json_error(handler: Any) -> None:
    try:
        handler()
    except CliError as exc:
        click.echo(json_error(exc.code, exc.message, exc.details))
        raise click.exceptions.Exit(exc.exit_code) from exc


def _record_run_warning(cache: JobCache, job_id: str, file_path: Path, strategy_id: str) -> dict[str, Any] | None:
    try:
        cache.record_run(job_id, file_path.resolve(), strategy_id)
    except OSError as exc:
        return {
            "code": "LOCAL_CACHE_WRITE_ERROR",
            "message": "remote job queued but local job cache was not updated",
            "details": {
                "job_id": job_id,
                "file": str(file_path),
                "strategy_id": strategy_id,
                "error": str(exc),
            },
        }
    return None


def _create_strategy_file(file_path: Path) -> None:
    if file_path.exists():
        raise CliError(
            code="LOCAL_FILE_ERROR",
            message="local strategy file already exists",
            exit_code=EXIT_LOCAL,
            details={"file": str(file_path)},
        )
    _write_strategy_file(file_path, _DEFAULT_STRATEGY_TEMPLATE)


def register_strategy_commands(root: click.Group) -> None:
    @root.group(name="strategy")
    def strategy_group() -> None:
        """Strategy command group."""

    @strategy_group.command(name="create")
    @click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, dir_okay=False))
    @click.pass_context
    def create_command(ctx: click.Context, file_path: Path) -> None:
        def _impl() -> None:
            _create_strategy_file(file_path)
            click.echo(
                json_ok(
                    {
                        "file": str(file_path),
                        "strategy_id": _strategy_id_from_path(file_path),
                        "created": True,
                    }
                )
            )

        _run_with_json_error(_impl)

    @strategy_group.command(name="list")
    @click.option("--q")
    @click.option("--limit", type=click.IntRange(min=1, max=500))
    @click.option("--offset", type=click.IntRange(min=0))
    @click.pass_context
    def list_command(ctx: click.Context, q: str | None, limit: int | None, offset: int | None) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            remote = client.list_strategies(q=q, limit=limit, offset=offset)
            click.echo(json_ok({"remote": remote}))

        _run_with_json_error(_impl)

    @strategy_group.command(name="compile")
    @click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, dir_okay=False))
    @click.pass_context
    def compile_command(ctx: click.Context, file_path: Path) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)

            code = _read_strategy_file(file_path)
            strategy_id = _strategy_id_from_path(file_path)
            remote = client.compile_strategy(strategy_id, code)

            if isinstance(remote, dict) and remote.get("ok") is False:
                raise CliError(
                    code="COMPILE_ERROR",
                    message=str(remote.get("stderr") or "compile failed"),
                    exit_code=EXIT_REMOTE,
                    details=remote,
                )

            click.echo(
                json_ok(
                    {
                        "file": str(file_path),
                        "strategy_id": strategy_id,
                        "compile": remote,
                    }
                )
            )

        _run_with_json_error(_impl)

    @strategy_group.command(name="delete")
    @click.option("--strategy-id", required=True)
    @click.option("--cascade", is_flag=True)
    @click.pass_context
    def delete_command(ctx: click.Context, strategy_id: str, cascade: bool) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            remote = client.delete_strategy(strategy_id, cascade=cascade)
            click.echo(json_ok({"strategy_id": strategy_id, "remote": remote}))

        _run_with_json_error(_impl)

    @strategy_group.command(name="run")
    @click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, dir_okay=False))
    @click.option("--start", "start_date", required=True)
    @click.option("--end", "end_date", required=True)
    @click.option("--cash", default=1000000, type=float, show_default=True)
    @click.option("--benchmark", default="000300.XSHG", show_default=True)
    @click.option("--frequency", default="1d", show_default=True)
    @click.pass_context
    def run_command(
        ctx: click.Context,
        file_path: Path,
        start_date: str,
        end_date: str,
        cash: float,
        benchmark: str,
        frequency: str,
    ) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            cache = JobCache(settings.jobs_cache_path)

            code = _read_strategy_file(file_path)
            strategy_id = _strategy_id_from_path(file_path)
            client.save_strategy(strategy_id, code)
            remote = client.run_strategy(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date,
                cash=cash,
                benchmark=benchmark,
                frequency=frequency,
            )
            job_id = str(remote["job_id"])
            payload: dict[str, Any] = {
                "job_id": job_id,
                "file": str(file_path),
                "strategy_id": strategy_id,
                "status": "QUEUED",
            }
            warning = _record_run_warning(cache, job_id, file_path, strategy_id)
            if warning is not None:
                payload["warning"] = warning

            click.echo(
                json_ok(payload)
            )

        _run_with_json_error(_impl)

    @strategy_group.command(name="pull")
    @click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, dir_okay=False))
    @click.pass_context
    def pull_command(ctx: click.Context, file_path: Path) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)

            strategy_id = _strategy_id_from_path(file_path)
            payload = client.get_strategy(strategy_id)
            data = payload["data"]
            code = data["code"]
            _write_strategy_file(file_path, code)

            click.echo(
                json_ok(
                    {
                        "file": str(file_path),
                        "strategy_id": strategy_id,
                    }
                )
            )

        _run_with_json_error(_impl)
