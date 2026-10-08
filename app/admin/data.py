"""Export, import and backups in the browser. The same as the flask CLI commands."""

import json
from datetime import UTC, datetime
from pathlib import Path

from flask import (
    Response,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from ..auth import log_in, log_out
from ..extensions import db
from ..models import User
from ..services.backup import backup_files, write_backup
from ..services.transfer import TransferError, export_data, import_data, summary
from . import bp


def backup_dir() -> Path:
    return Path(current_app.config["BACKUP_DIR"])


@bp.get("/data")
def data():
    backups = backup_files(backup_dir()) if backup_dir().exists() else []
    return render_template("admin/data.html", backups=backups)


@bp.get("/data/export.json")
def data_export():
    text = json.dumps(export_data(), indent=2, ensure_ascii=False)
    filename = f"rental-export-{datetime.now(UTC):%Y-%m-%d}.json"
    return Response(text, mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@bp.post("/data/import")
def data_import():
    mode = request.form.get("mode")
    upload = request.files.get("file")
    if mode not in ("replace", "merge"):
        flash("Choose replace or merge.", "error")
    elif upload is None or not upload.filename:
        flash("Choose a file to import.", "error")
    elif mode == "replace" and request.form.get("confirm") != "yes":
        flash("Tick the box to confirm that everything will be replaced.", "error")
    else:
        my_card = g.user.card_number
        try:
            counts = import_data(json.load(upload.stream), mode)
        except (json.JSONDecodeError, UnicodeDecodeError):
            flash("That file is not a JSON export.", "error")
        except TransferError as error:
            flash(str(error), "error")
        else:
            # Database ids may have changed: sign in again as the same person.
            me = db.session.execute(
                db.select(User).filter_by(card_number=my_card)
            ).scalar_one_or_none()
            if me is None or not me.is_admin:
                log_out()
                flash("Imported. You are not an admin in the imported data, so you "
                      "have been signed out.", "success")
                return redirect(url_for("rental.index"))
            log_in(me)
            flash(f"Imported {summary(counts)}.", "success")
    return redirect(url_for(".data"))


@bp.post("/data/backups")
def backup_now():
    path = write_backup(backup_dir())
    flash(f"Backup {path.name} written.", "success")
    return redirect(url_for(".data"))


@bp.get("/data/backups/<name>")
def backup_download(name: str):
    # Only serve files that are listed as backups; never build a path from input.
    for path in backup_files(backup_dir()) if backup_dir().exists() else []:
        if path.name == name:
            return send_file(path.resolve(), as_attachment=True)
    abort(404)
