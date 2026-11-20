"""Foydalanuvchilar: reyting jadvali, profil sahifasi va hisob sozlamalari."""
import math

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import distinct, func
from werkzeug.security import check_password_hash, generate_password_hash

from i18n import _
from models import PublicContest, Question, RatingChange, Submission, User, db
from public import PASSWORD_MIN, problem_code, problem_title
from rating import TIERS, ensure_ratings, tier

USERS_PER_PAGE = 50
GRAPH_WIDTH, GRAPH_HEIGHT, GRAPH_PAD = 640, 220, 28


def solved_counts():
    """{user_id: yechilgan masalalar soni} (arxiv va musobaqa yechimlari birga)."""
    return dict(db.session.execute(
        db.select(Submission.user_id, func.count(distinct(Submission.question_id)))
        .where(Submission.status == "accepted")
        .group_by(Submission.user_id)
    ).all())


def contest_counts():
    return dict(db.session.execute(
        db.select(RatingChange.user_id, func.count()).group_by(RatingChange.user_id)
    ).all())


def rating_graph(changes):
    """Reyting grafigi uchun SVG nuqtalari. changes — xronologik tartibda."""
    if not changes:
        return None
    values = [changes[0].old_rating] + [change.new_rating for change in changes]
    low = min(values + [1200]) - 100
    high = max(values + [1600]) + 100
    span_x = GRAPH_WIDTH - 2 * GRAPH_PAD
    span_y = GRAPH_HEIGHT - 2 * GRAPH_PAD

    def y_of(value):
        return GRAPH_PAD + span_y * (high - value) / (high - low)

    points = []
    for index, value in enumerate(values):
        x = GRAPH_PAD + (span_x * index / (len(values) - 1) if len(values) > 1 else span_x / 2)
        change = changes[index - 1] if index else None
        points.append({"x": round(x, 1), "y": round(y_of(value), 1), "value": value, "change": change})
    bands = []
    previous = high
    for floor, key, _name in TIERS:
        top, bottom = min(previous, high), max(floor, low)
        if top > bottom:
            bands.append({"key": key, "y": round(y_of(top), 1), "height": round(y_of(bottom) - y_of(top), 1)})
        previous = floor
    step = 200
    grid = [value for value in range(int(math.ceil(low / step) * step), int(high) + 1, step)]
    return {
        "width": GRAPH_WIDTH,
        "height": GRAPH_HEIGHT,
        "points": points,
        "path": " ".join(f"{point['x']},{point['y']}" for point in points),
        "bands": bands,
        "grid": [{"value": value, "y": round(y_of(value), 1)} for value in grid],
    }


def register_users(application, helpers):
    current_user = helpers["current_user"]
    login_required = helpers["login_required"]
    hidden_question_ids = helpers["hidden_question_ids"]

    application.jinja_env.globals["rating_tier"] = tier

    @application.route("/users")
    def users():
        ensure_ratings()
        view = request.args.get("view", "rating")
        query_text = " ".join(request.args.get("q", "").split())[:60]
        solved = solved_counts()
        contests = contest_counts()
        query = User.query
        if query_text:
            like = f"%{query_text}%"
            query = query.filter(db.or_(User.full_name.ilike(like), User.username.ilike(like)))
        if view == "solved":
            people = query.all()
            people.sort(key=lambda user: (-solved.get(user.id, 0), user.full_name.casefold()))
            people = [user for user in people if solved.get(user.id, 0)]
        else:
            view = "rating"
            people = query.filter(User.rating.isnot(None)).order_by(User.rating.desc(), User.full_name).all()
        pages = max(1, math.ceil(len(people) / USERS_PER_PAGE))
        page = min(max(request.args.get("page", 1, type=int), 1), pages)
        offset = (page - 1) * USERS_PER_PAGE
        return render_template(
            "public/users.html",
            people=people[offset: offset + USERS_PER_PAGE],
            offset=offset,
            page=page,
            pages=pages,
            total=len(people),
            view=view,
            q=query_text,
            solved=solved,
            contests=contests,
        )

    @application.route("/users/<username>")
    def profile(username):
        ensure_ratings()
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if user is None:
            abort(404)
        changes = (
            RatingChange.query.filter_by(user_id=user.id)
            .join(PublicContest, RatingChange.contest_id == PublicContest.id)
            .all()
        )
        changes.sort(key=lambda change: (change.contest.end_at, change.contest_id))
        hidden = hidden_question_ids()
        solved_rows = db.session.execute(
            db.select(Submission.question_id).where(Submission.user_id == user.id, Submission.status == "accepted")
            .distinct()
        ).scalars().all()
        solved_problems = [
            question for question in Question.query.filter(Question.id.in_(solved_rows)).order_by(Question.id).all()
            if question.id not in hidden
        ]
        total, accepted = db.session.execute(
            db.select(func.count(Submission.id), func.sum(db.case((Submission.status == "accepted", 1), else_=0)))
            .where(Submission.user_id == user.id, Submission.status != "error")
        ).one()
        rank = None
        if user.rating is not None:
            rank = User.query.filter(User.rating > user.rating).count() + 1
        return render_template(
            "public/profile.html",
            person=user,
            changes=list(reversed(changes)),
            graph=rating_graph(changes),
            solved_problems=solved_problems,
            total_submissions=total or 0,
            accepted_submissions=accepted or 0,
            rank=rank,
            problem_code=problem_code,
            problem_title=problem_title,
        )

    @application.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        user = current_user()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "profile":
                full_name = " ".join(request.form.get("full_name", "").split())
                organization = " ".join(request.form.get("organization", "").split())[:160] or None
                if not 2 <= len(full_name) <= 120:
                    flash(_("Ism-familiyani kiriting."), "danger")
                else:
                    user.full_name = full_name
                    user.organization = organization
                    db.session.commit()
                    flash(_("Profil saqlandi."), "success")
            elif action == "password":
                current = request.form.get("current_password", "")
                new = request.form.get("new_password", "")
                if not check_password_hash(user.password_hash, current):
                    flash(_("Joriy parol noto‘g‘ri."), "danger")
                elif len(new) < PASSWORD_MIN:
                    flash(_("Parol kamida %(n)s belgidan iborat bo‘lsin.", n=PASSWORD_MIN), "danger")
                elif new != request.form.get("new_password2", ""):
                    flash(_("Parollar bir xil emas."), "danger")
                else:
                    user.password_hash = generate_password_hash(new)
                    db.session.commit()
                    flash(_("Parol o‘zgartirildi."), "success")
            return redirect(url_for("settings"))
        return render_template("public/settings.html")
