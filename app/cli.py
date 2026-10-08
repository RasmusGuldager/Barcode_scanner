import json
import sys
from pathlib import Path

import click
from flask import Flask, current_app

from .extensions import db
from .models import User
from .services.backup import write_backup
from .services.transfer import TransferError, export_data, import_data, summary


def register(app: Flask) -> None:
    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin(email: str) -> None:
        """Promote the registered user with EMAIL to admin."""
        user = db.session.execute(
            db.select(User).filter_by(email=email.strip().lower())
        ).scalar_one_or_none()
        if user is None:
            raise click.ClickException(
                f"No user with email {email}. They must register by scanning their card first."
            )
        user.is_admin = True
        db.session.commit()
        click.echo(f"{user.email} is now an admin.")

    @app.cli.command("export")
    @click.argument("path", type=click.Path(dir_okay=False, writable=True, allow_dash=True))
    def export(path: str) -> None:
        """Write the whole database to PATH as JSON ("-" for stdout)."""
        text = json.dumps(export_data(), indent=2, ensure_ascii=False)
        if path == "-":
            sys.stdout.write(text + "\n")
        else:
            Path(path).write_text(text)
            click.echo(f"Exported to {path}.", err=True)

    @app.cli.command("import")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--mode", type=click.Choice(["replace", "merge"]), required=True,
                  help="replace: delete everything first. merge: add and update only.")
    @click.option("--yes", is_flag=True, help="Don't ask before replacing.")
    def import_(path: str, mode: str, yes: bool) -> None:
        """Load an export file into the database."""
        if mode == "replace" and not yes:
            click.confirm("This deletes everything in the database first. Continue?",
                          abort=True)
        try:
            data = json.loads(Path(path).read_text())
            counts = import_data(data, mode)
        except json.JSONDecodeError as error:
            raise click.ClickException(f"{path} is not valid JSON: {error}")
        except TransferError as error:
            raise click.ClickException(str(error))
        click.echo(f"Imported {summary(counts)}.")

    @app.cli.command("backup")
    def backup() -> None:
        """Write a dated backup to data/backups/ and delete the oldest ones."""
        path = write_backup(Path(current_app.config["BACKUP_DIR"]))
        click.echo(f"Backup written to {path}.")
