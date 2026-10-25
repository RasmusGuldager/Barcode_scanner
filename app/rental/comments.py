"""Short notes on an item, e.g. "Lens cap missing"."""

from flask import flash, g, redirect, render_template, request, url_for

from ..auth import admin_required, login_required
from ..extensions import db
from ..models import Comment
from . import bp
from .items import get_item_by_code_or_404

MAX_LENGTH = 500


@bp.post("/i/<code>/comments")
@login_required
def comment_add(code: str):
    item = get_item_by_code_or_404(code)
    text = request.form.get("text", "").strip()
    if not text:
        error = "Write a note first."
    elif len(text) > MAX_LENGTH:
        error = f"Keep the note under {MAX_LENGTH} characters."
    else:
        error = None
        db.session.add(Comment(item=item, user=g.user, text=text))
        db.session.commit()

    if request.headers.get("HX-Request"):
        # Sent from the return page: replace the note form with the result.
        return render_template("rental/_comment_result.html", item=item, error=error)
    flash(error or "Note added.", "error" if error else "success")
    return redirect(url_for("rental.item_page", code=item.code))


@bp.post("/comments/<int:comment_id>/delete")
@admin_required
def comment_delete(comment_id: int):
    comment = db.get_or_404(Comment, comment_id)
    code = comment.item.code
    db.session.delete(comment)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect(url_for("rental.item_page", code=code))
