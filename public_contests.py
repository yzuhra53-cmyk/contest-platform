"""Ochiq musobaqalar: ro'yxat, ro'yxatdan o'tish, masalalar, ICPC natijalar jadvali.

Qoidalar (ICPC):
  * o'rin yechilgan masalalar soni (ko'p — yuqori), so'ng jarima (kam — yuqori) bo'yicha;
  * jarima = har bir yechilgan masala uchun: musobaqa boshidan qabul qilingungacha
    o'tgan daqiqalar + shu masaladagi har bir oldingi xato urinish uchun 20 daqiqa;
  * kompilyatsiya xatosi va tizim xatosi jarima hisoblanmaydi;
  * musobaqa tugagach masalalar arxivga qaytadi va ular ustida mashq qilish mumkin.
"""
import re
from datetime import datetime, timedelta

from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.orm import contains_eager

from i18n import _
from public import parse_code, problem_code, problem_title
from rating import ensure_ratings, rebuild_ratings
from models import (
    ContestRegistration,
    PublicContest,
    PublicContestProblem,
    Question,
    RatingChange,
    Submission,
    User,
    db,
    utcnow,
)

WRONG_PENALTY_MINUTES = 20
MAX_PROBLEMS = 26
MAX_DURATION_MINUTES = 7 * 24 * 60
EPOCH = datetime(1970, 1, 1)


def epoch_ms(value):
    return int((value - EPOCH).total_seconds() * 1000) if value is not None else None


def format_duration(minutes):
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return _("%(h)s soat %(m)s daqiqa", h=hours, m=mins)
    if hours:
        return _("%(h)s soat", h=hours)
    return _("%(m)s daqiqa", m=mins)


def format_clock(seconds):
    """Musobaqa boshidan o'tgan vaqt: 14:54 yoki 1:01:03."""
    seconds = max(int(seconds), 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def is_compile_error(submission):
    return (submission.verdict or "").startswith("Compilation Error")


def compute_standings(contest):
    """ICPC natijalar jadvali.

    Qaytaradi: (rows, first_solves). rows — ro'yxat, har birida: place, user, solved,
    penalty, attempted (kamida bitta yechim yuborganmi),
    cells {question_id: {"solved", "tries", "time", "pending", "first"}}.
    """
    problem_ids = [item.question_id for item in contest.problems]
    users = {reg.user_id: reg.user for reg in contest.registrations}
    submissions = (
        Submission.query.filter(Submission.contest_id == contest.id, Submission.created_at < contest.end_at)
        .order_by(Submission.id)
        .all()
    )
    cells = {}
    submitted = set()
    for sub in submissions:
        if sub.question_id not in problem_ids:
            continue
        users.setdefault(sub.user_id, sub.user)
        submitted.add(sub.user_id)
        cell = cells.setdefault((sub.user_id, sub.question_id), {"solved": False, "tries": 0, "time": None, "pending": 0})
        if cell["solved"]:
            continue
        if sub.status == "accepted":
            cell["solved"] = True
            cell["time"] = (sub.created_at - contest.start_at).total_seconds()
        elif sub.status == "pending":
            cell["pending"] += 1
        elif sub.status == "rejected" and not is_compile_error(sub):
            cell["tries"] += 1
    first_solves = {}
    for (user_id, question_id), cell in cells.items():
        if cell["solved"] and (question_id not in first_solves or cell["time"] < first_solves[question_id][1]):
            first_solves[question_id] = (user_id, cell["time"])
    rows = []
    for user_id, user in users.items():
        row_cells, solved, penalty, last_ac = {}, 0, 0, 0
        for question_id in problem_ids:
            cell = cells.get((user_id, question_id), {"solved": False, "tries": 0, "time": None, "pending": 0})
            cell = dict(cell, first=first_solves.get(question_id, (None,))[0] == user_id and cell["solved"])
            if cell["solved"]:
                solved += 1
                penalty += int(cell["time"] // 60) + WRONG_PENALTY_MINUTES * cell["tries"]
                last_ac = max(last_ac, cell["time"])
            row_cells[question_id] = cell
        rows.append({"user": user, "solved": solved, "penalty": penalty, "last_ac": last_ac, "cells": row_cells,
                     "attempted": user_id in submitted})
    rows.sort(key=lambda row: (-row["solved"], row["penalty"], row["user"].full_name.casefold()))
    # Bir xil natija (yechilgan + jarima) — bir xil o'rin: "1-2".
    index = 0
    while index < len(rows):
        end = index
        while (end + 1 < len(rows) and rows[end + 1]["solved"] == rows[index]["solved"]
               and rows[end + 1]["penalty"] == rows[index]["penalty"]):
            end += 1
        place = str(index + 1) if end == index else f"{index + 1}-{end + 1}"
        for position in range(index, end + 1):
            rows[position]["place"] = place
        index = end + 1
    return rows, first_solves


def register_contests(application, helpers):
    current_user = helpers["current_user"]
    login_required = helpers["login_required"]
    admin_required = helpers["admin_required"]
    render_problem = helpers["render_problem"]
    handle_submit = helpers["handle_submit"]
    handle_run = helpers["handle_run"]
    parse_local = helpers["parse_local"]
    to_local = helpers["to_local"]

    application.jinja_env.filters["epoch_ms"] = epoch_ms
    application.jinja_env.filters["duration"] = format_duration
    application.jinja_env.filters["clock"] = format_clock

    def visible_contest(contest_id):
        contest = db.session.get(PublicContest, contest_id)
        if contest is None or (not contest.is_published and not session.get("is_admin")):
            abort(404)
        return contest

    def is_registered(contest, user):
        return user is not None and db.session.get(ContestRegistration, (contest.id, user.id)) is not None

    def contest_problem(contest, label):
        for item in contest.problems:
            if item.label == label.upper():
                return item
        abort(404)

    def problems_open(contest):
        return contest.state() != "upcoming" or bool(session.get("is_admin"))

    # ---------------- Ro'yxat ----------------

    @application.route("/contests")
    def contests():
        ensure_ratings()
        query = PublicContest.query
        if not session.get("is_admin"):
            query = query.filter(PublicContest.is_published.is_(True))
        items = query.order_by(PublicContest.start_at.desc()).all()
        now = utcnow()
        groups = {"running": [], "upcoming": [], "finished": []}
        for contest in items:
            groups[contest.state(now)].append(contest)
        groups["upcoming"].sort(key=lambda contest: contest.start_at)
        counts = dict(
            db.session.execute(
                db.select(ContestRegistration.contest_id, db.func.count()).group_by(ContestRegistration.contest_id)
            ).all()
        )
        user = current_user()
        mine = set()
        if user:
            mine = set(db.session.execute(
                db.select(ContestRegistration.contest_id).where(ContestRegistration.user_id == user.id)
            ).scalars())
        return render_template("public/contests.html", groups=groups, counts=counts, mine=mine)

    # ---------------- Musobaqa sahifasi ----------------

    @application.route("/contests/<int:contest_id>")
    def contest_page(contest_id):
        contest = visible_contest(contest_id)
        user = current_user()
        tab = request.args.get("tab", "overview")
        state = contest.state()
        opened = problems_open(contest)
        if tab not in ("overview", "problems", "standings", "attempts") or (tab != "overview" and not opened):
            tab = "overview"
        context = dict(
            contest=contest,
            state=state,
            tab=tab,
            opened=opened,
            registered=is_registered(contest, user),
            participants=len(contest.registrations),
        )
        if tab in ("problems", "overview") and opened:
            stats = {}
            for question_id, solvers in db.session.execute(
                db.select(Submission.question_id, db.func.count(db.distinct(Submission.user_id)))
                .where(Submission.contest_id == contest.id, Submission.status == "accepted",
                       Submission.created_at < contest.end_at)
                .group_by(Submission.question_id)
            ):
                stats[question_id] = solvers
            marks = {}
            if user:
                for question_id, status in db.session.execute(
                    db.select(Submission.question_id, Submission.status)
                    .where(Submission.contest_id == contest.id, Submission.user_id == user.id)
                ):
                    if marks.get(question_id) != "solved":
                        marks[question_id] = "solved" if status == "accepted" else "tried"
            context.update(problem_solvers=stats, problem_marks=marks)
        if tab == "standings":
            rows, _first = compute_standings(contest)
            context.update(rows=rows)
        if tab == "attempts":
            only_mine = request.args.get("mine") == "1" and user is not None
            query = (
                db.select(Submission)
                .join(User, Submission.user_id == User.id)
                .options(contains_eager(Submission.user))
                .where(Submission.contest_id == contest.id)
            )
            if only_mine:
                query = query.where(Submission.user_id == user.id)
            context.update(
                attempts=db.session.execute(query.order_by(Submission.id.desc()).limit(200)).scalars().all(),
                labels={item.question_id: item.label for item in contest.problems},
                only_mine=only_mine,
            )
        return render_template("public/contest.html", **context)

    @application.route("/contests/<int:contest_id>/register", methods=["POST"])
    @login_required
    def contest_register(contest_id):
        contest = visible_contest(contest_id)
        if contest.state() == "finished":
            flash(_("Musobaqa tugagan, ro‘yxatdan o‘tib bo‘lmaydi."), "warning")
        elif not is_registered(contest, current_user()):
            db.session.add(ContestRegistration(contest_id=contest.id, user_id=current_user().id))
            db.session.commit()
            flash(_("Siz musobaqaga ro‘yxatdan o‘tdingiz."), "success")
        return redirect(request.form.get("next") or url_for("contest_page", contest_id=contest.id))

    @application.route("/contests/<int:contest_id>/unregister", methods=["POST"])
    @login_required
    def contest_unregister(contest_id):
        contest = visible_contest(contest_id)
        registration = db.session.get(ContestRegistration, (contest.id, current_user().id))
        if contest.state() != "upcoming":
            flash(_("Musobaqa boshlangandan keyin ro‘yxatdan chiqib bo‘lmaydi."), "warning")
        elif registration is not None:
            db.session.delete(registration)
            db.session.commit()
            flash(_("Ro‘yxatdan chiqdingiz."), "info")
        return redirect(url_for("contest_page", contest_id=contest.id))

    # ---------------- Musobaqa masalasi ----------------

    @application.route("/contests/<int:contest_id>/<label>")
    def contest_task(contest_id, label):
        contest = visible_contest(contest_id)
        if not problems_open(contest):
            flash(_("Masalalar musobaqa boshlanganda ochiladi."), "info")
            return redirect(url_for("contest_page", contest_id=contest.id))
        item = contest_problem(contest, label)
        if contest.state() == "finished" and not session.get("is_admin"):
            # Musobaqa tugadi: masala arxivda, yechimlar endi mashq sifatida hisoblanadi.
            return redirect(url_for("task", code=problem_code(item.question)))
        can_submit = contest.state() == "running" and is_registered(contest, current_user())
        return render_problem(
            item.question,
            url_for("contest_submit", contest_id=contest.id, label=item.label),
            url_for("contest_run", contest_id=contest.id, label=item.label),
            contest=contest,
            label=item.label,
            can_submit=can_submit,
        )

    def guard_running(contest):
        if contest.state() != "running":
            abort(409, description=_("Musobaqa hozir davom etmayapti."))
        if not is_registered(contest, current_user()):
            abort(403, description=_("Avval musobaqaga ro‘yxatdan o‘ting."))

    @application.route("/contests/<int:contest_id>/<label>/submit", methods=["POST"])
    @login_required
    def contest_submit(contest_id, label):
        contest = visible_contest(contest_id)
        item = contest_problem(contest, label)
        guard_running(contest)
        return handle_submit(
            item.question,
            url_for("contest_task", contest_id=contest.id, label=item.label),
            contest_id=contest.id,
        )

    @application.route("/contests/<int:contest_id>/<label>/run", methods=["POST"])
    @login_required
    def contest_run(contest_id, label):
        contest = visible_contest(contest_id)
        contest_problem(contest, label)
        guard_running(contest)
        return handle_run()

    # ---------------- Ustoz: ochiq musobaqalarni boshqarish ----------------

    def archive_choices():
        problems = (
            Question.query.filter(Question.question_type == "code_problem", Question.archived.is_(False))
            .order_by(Question.id)
            .all()
        )
        return [{"code": problem_code(q), "title": problem_title(q), "difficulty": q.difficulty} for q in problems]

    def parse_problem_codes(text):
        codes = [code.upper() for code in re.findall(r"[Aa]\d{1,9}", text or "")]
        questions, seen, errors = [], set(), []
        for code in codes:
            question_id = parse_code(code)
            if question_id in seen:
                continue
            question = db.session.get(Question, question_id)
            if question is None or question.question_type != "code_problem" or question.archived:
                errors.append(code)
                continue
            seen.add(question_id)
            questions.append(question)
        return questions, errors

    def save_contest(contest, form):
        """Formadagi ma'lumotlarni tekshiradi va saqlaydi. Xato bo'lsa, ro'yxat qaytaradi."""
        errors = []
        title = " ".join(form.get("title", "").split())[:180]
        if not title:
            errors.append(_("Musobaqa nomini kiriting."))
        try:
            start_at = parse_local(form.get("start_at"))
        except ValueError:
            start_at = None
        if start_at is None:
            errors.append(_("Boshlanish vaqtini kiriting."))
        try:
            duration = int(form.get("duration_minutes", ""))
        except ValueError:
            duration = 0
        if not 1 <= duration <= MAX_DURATION_MINUTES:
            errors.append(_("Davomiylik 1 daqiqadan 7 kungacha bo‘lishi kerak."))
        questions, bad_codes = parse_problem_codes(form.get("problem_codes"))
        if bad_codes:
            errors.append(_("Bunday masalalar topilmadi: %(codes)s", codes=", ".join(bad_codes)))
        if not questions:
            errors.append(_("Kamida bitta masala qo‘shing."))
        if len(questions) > MAX_PROBLEMS:
            errors.append(_("Ko‘pi bilan %(n)s ta masala qo‘shish mumkin.", n=MAX_PROBLEMS))
        started = contest.id is not None and contest.state() != "upcoming"
        if started and [item.question_id for item in contest.problems] != [q.id for q in questions]:
            errors.append(_("Musobaqa boshlangan: masalalar ro‘yxatini o‘zgartirib bo‘lmaydi."))
        if errors:
            return errors
        contest.title = title
        contest.description = (form.get("description") or "").strip()[:5000] or None
        contest.start_at = start_at
        contest.duration_minutes = duration
        contest.is_rated = bool(form.get("is_rated"))
        contest.is_published = bool(form.get("is_published"))
        if not started:
            contest.problems.clear()
            db.session.flush()
            for position, question in enumerate(questions):
                contest.problems.append(PublicContestProblem(question_id=question.id, position=position))
        if contest.id is None:
            db.session.add(contest)
        db.session.commit()
        # Tugagan musobaqa tahrirlansa (reytingli/e'lon belgisi, vaqt), reyting qayta quriladi.
        if contest.end_at <= utcnow() or RatingChange.query.filter_by(contest_id=contest.id).first():
            rebuild_ratings()
        return []

    def contest_form_values(contest):
        if contest is None:
            start = to_local(utcnow() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
            return {"title": "", "description": "", "start_at": start.strftime("%Y-%m-%dT%H:%M"),
                    "duration_minutes": 120, "is_rated": True, "is_published": False, "problem_codes": ""}
        return {
            "title": contest.title,
            "description": contest.description or "",
            "start_at": to_local(contest.start_at).strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": contest.duration_minutes,
            "is_rated": contest.is_rated,
            "is_published": contest.is_published,
            "problem_codes": " ".join(problem_code(item.question) for item in contest.problems),
        }

    @application.route("/admin/public-contests", methods=["GET", "POST"])
    @admin_required
    def admin_public_contests():
        form = contest_form_values(None)
        status = 200
        if request.method == "POST":
            contest = PublicContest()
            errors = save_contest(contest, request.form)
            if not errors:
                flash(_("Musobaqa yaratildi."), "success")
                return redirect(url_for("admin_public_contests"))
            db.session.rollback()
            for error in errors:
                flash(error, "danger")
            form, status = request.form, 400
        items = PublicContest.query.order_by(PublicContest.start_at.desc()).all()
        counts = dict(db.session.execute(
            db.select(ContestRegistration.contest_id, db.func.count()).group_by(ContestRegistration.contest_id)
        ).all())
        return render_template(
            "admin_public_contests.html", items=items, counts=counts, form=form, contest=None,
            choices=archive_choices(),
        ), status

    @application.route("/admin/public-contests/<int:contest_id>", methods=["GET", "POST"])
    @admin_required
    def admin_public_contest_edit(contest_id):
        contest = db.session.get(PublicContest, contest_id)
        if contest is None:
            abort(404)
        form = contest_form_values(contest)
        status = 200
        if request.method == "POST":
            errors = save_contest(contest, request.form)
            if not errors:
                flash(_("O‘zgarishlar saqlandi."), "success")
                return redirect(url_for("admin_public_contest_edit", contest_id=contest.id))
            db.session.rollback()
            for error in errors:
                flash(error, "danger")
            form, status = request.form, 400
        return render_template(
            "admin_public_contests.html", items=None, counts={}, form=form, contest=contest,
            choices=archive_choices(),
        ), status

    @application.route("/admin/public-contests/<int:contest_id>/delete", methods=["POST"])
    @admin_required
    def admin_public_contest_delete(contest_id):
        contest = db.session.get(PublicContest, contest_id)
        if contest is None:
            abort(404)
        # Yechimlar o'chirilmaydi: ular arxiv yechimlari bo'lib qoladi.
        Submission.query.filter_by(contest_id=contest.id).update({"contest_id": None})
        had_rating = RatingChange.query.filter_by(contest_id=contest.id).delete()
        db.session.delete(contest)
        db.session.commit()
        if had_rating:
            rebuild_ratings()
        flash(_("Musobaqa o‘chirildi."), "success")
        return redirect(url_for("admin_public_contests"))
