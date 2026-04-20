from __future__ import annotations

import os
from typing import Sequence

import click

from .commands.strategy import register_strategy_commands
from .config import CliSettings
from .errors import CliError, EXIT_ARGUMENT, EXIT_OK
from .output import json_error


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["settings"] = CliSettings.from_env(os.environ)


register_strategy_commands(cli)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        cli.main(args=list(argv) if argv is not None else None, prog_name="bq", standalone_mode=False, obj={})
        return EXIT_OK
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except CliError as exc:
        click.echo(json_error(exc.code, exc.message, exc.details))
        return exc.exit_code
    except click.ClickException as exc:
        click.echo(json_error("CLI_ARGUMENT_ERROR", exc.format_message()))
        return EXIT_ARGUMENT
