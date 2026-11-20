"""Ochiq platforma: ro'yxatdan o'tish, masalalar arxivi va masala sahifasi.

Ustoz/talaba (HEMIS) qismidan alohida ishlaydi: foydalanuvchi o'zi ro'yxatdan
o'tadi, arxivdagi masalalarni istalgan vaqtda yechadi. Yechimlar `Submission`
jadvaliga yoziladi va mavjud ichki judge orqali fon oqimida tekshiriladi.
"""
import json
import math
import re
import threading
import time
from datetime import timedelta
from functools import wraps

from flask import abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import case, distinct, func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

import content_i18n
from i18n import _
from judge import MEMORY_LIMIT_MB, TIME_LIMIT, JudgeError, judge_solution, run_program
from models import Question, Submission, User, db, utcnow
from verdicts import short_verdict

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
PASSWORD_MIN = 8
SIGNIN_MAX_FAILURES = 10
REGISTER_MAX_PER_WINDOW = 10
TASKS_PER_PAGE = 50
MAX_SOURCE_CHARS = 20000
PENDING_STALE_SECONDS = 180
LANGUAGE_NAMES = {"python": "Python 3", "cpp": "C++17"}

# Masala matnini bo'limlarga ajratish (o'zbek, rus va ingliz tarjimalari uchun).
_TITLE_PREFIX = re.compile(r"^(?:\[(?:NB|OB)-\d+\]\s*)?(?:(?:Masala|Задача|Problem)\s+\d+\s*:\s*)?")
_LEVEL_SUFFIX = re.compile(r"\s*·\s*(?:Daraja|Уровень|Level)\s*:.*$")
_SAMPLE_MARK = re.compile(r"\n\s*(?:Namuna Input|Пример ввода|Sample Input)\s*:", re.I)
_SECTION_LABELS = (
    ("statement", ("Sharti", "Условие", "Statement")),
    ("input", ("Kirish", "Входные данные", "Input")),
    ("output", ("Chiqish", "Выходные данные", "Output")),
    ("constraints", ("Cheklovlar", "Ограничения", "Constraints")),
)
_SECTION_RE = re.compile(
    r"^(?P<label>" + "|".join(re.escape(label) for _, labels in _SECTION_LABELS for label in labels) + r")\s*:\s*(?P<rest>.*)$"
)
_LABEL_KEY = {label: key for key, labels in _SECTION_LABELS for label in labels}


def problem_code(question):
    return f"A{question.id:04d}"


def parse_code(code):
    match = re.fullmatch(r"[Aa](\d{1,9})", code or "")
    return int(match.group(1)) if match else None


def problem_title(question):
    text = content_i18n.translate(question.prompt or "", keep_prefix=False).strip()
    first = text.split("\n", 1)[0]
    title = _LEVEL_SUFFIX.sub("", _TITLE_PREFIX.sub("", first)).strip()
    return title or problem_code(question)


def problem_sections(question):
    """Masala matni: [(kalit, matn)] ro'yxati. Kalit: statement / input / output / constraints."""
    text = content_i18n.translate(question.prompt or "", keep_prefix=False).replace("\r\n", "\n").strip()
    body = text.split("\n", 1)[1] if "\n" in text else ""
    body = _SAMPLE_MARK.split("\n" + body, 1)[0].strip()
    sections = []
    for line in body.split("\n"):
        match = _SECTION_RE.match(line.strip())
        if match:
            sections.append([_LABEL_KEY[match.group("label")], match.group("rest")])
        elif sections:
            sections[-1][1] += "\n" + line
        else:
            sections.append(["statement", line])
    merged = []
    for key, value in sections:
        value = value.strip()
        if not value:
            continue
        if merged and merged[-1][0] == key:
            merged[-1][1] += "\n" + value
        else:
            merged.append([key, value])
    return [tuple(item) for item in merged]


def problem_samples(question):
    """Ko'rinadigan misollar: masala namunasi (yashirin testlar ko'rsatilmaydi)."""
    if question.input_data is None and question.expected_output is None:
        return []
    return [{"input": (question.input_data or "").strip(), "output": (question.expected_output or "").strip()}]


def archive_problems():
    return (
        Question.query.filter(Question.question_type == "code_problem", Question.archived.is_(False))
        .order_by(Question.id)
        .all()
    )


def problem_stats():
    """{question_id: (yechganlar soni, urinishlar soni, qabul qilinganlar soni)}."""
    rows = db.session.execute(
        db.select(
            Submission.question_id,
            func.count(distinct(case((Submission.status == "accepted", Submission.user_id)))),
            func.count(Submission.id),
            func.sum(case((Submission.status == "accepted", 1), else_=0)),
        )
        .where(Submission.status != "error")
        .group_by(Submission.question_id)
    )
    return {qid: (solvers or 0, total or 0, accepted or 0) for qid, solvers, total, accepted in rows}


def register_public(application, judge_pool, throttle, client_ip):
    run_times = {}
    run_lock = threading.Lock()

    def current_user():
        if "current_user" not in g:
            user_id = session.get("user_id")
            g.current_user = db.session.get(User, user_id) if isinstance(user_id, int) else None
        return g.current_user

    @application.context_processor
    def inject_user():
        return {"current_user": current_user(), "problem_code": problem_code, "language_names": LANGUAGE_NAMES}

    application.jinja_env.globals["short_verdict"] = short_verdict

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                if request.is_json or request.headers.get("X-Requested-With") == "fetch":
                    return jsonify(error=_("Iltimos, avval tizimga kiring.")), 401
                return redirect(url_for("signin", next=request.full_path.rstrip("?")))
            return view(*args, **kwargs)

        return wrapped

    def safe_next(value):
        return value if isinstance(value, str) and value.startswith("/") and not value.startswith("//") else None

    def get_problem(code):
        question_id = parse_code(code)
        question = db.session.get(Question, question_id) if question_id else None
        if question is None or question.question_type != "code_problem" or question.archived:
            abort(404)
        return question

    # ---------------- Hisob ----------------

    @application.route("/register", methods=["GET", "POST"])
    def register():
        if current_user():
            return redirect(url_for("tasks"))
        form = request.form if request.method == "POST" else {}
        if request.method == "POST":
            username = form.get("username", "").strip()
            full_name = " ".join(form.get("full_name", "").split())
            organization = " ".join(form.get("organization", "").split())[:160] or None
            password = form.get("password", "")
            errors = []
            if not USERNAME_RE.match(username):
                errors.append(_("Login 3–32 belgidan iborat bo‘lsin: lotin harflari, raqamlar va _ belgisi."))
            if not 2 <= len(full_name) <= 120:
                errors.append(_("Ism-familiyani kiriting."))
            if len(password) < PASSWORD_MIN:
                errors.append(_("Parol kamida %(n)s belgidan iborat bo‘lsin.", n=PASSWORD_MIN))
            elif password != form.get("password2", ""):
                errors.append(_("Parollar bir xil emas."))
            if not errors and User.query.filter(func.lower(User.username) == username.lower()).first():
                errors.append(_("Bu login band. Boshqasini tanlang."))
            ip_key = ("register-ip", client_ip())
            if not errors and throttle.blocked(ip_key, REGISTER_MAX_PER_WINDOW):
                errors.append(_("Juda ko‘p urinish. 15 daqiqadan so‘ng qayta urinib ko‘ring."))
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("public/register.html", form=form), 400
            user = User(
                username=username,
                full_name=full_name,
                organization=organization,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(_("Bu login band. Boshqasini tanlang."), "danger")
                return render_template("public/register.html", form=form), 400
            throttle.fail(ip_key)  # ro'yxatdan o'tishlar sonini IP bo'yicha cheklash
            session.clear()
            session["user_id"] = user.id
            flash(_("Xush kelibsiz, %(name)s!", name=user.full_name), "success")
            return redirect(safe_next(request.args.get("next")) or url_for("tasks"))
        return render_template("public/register.html", form=form)

    @application.route("/signin", methods=["GET", "POST"])
    def signin():
        if current_user():
            return redirect(url_for("tasks"))
        if request.method == "POST":
            ip_key = ("signin-ip", client_ip())
            if throttle.blocked(ip_key, SIGNIN_MAX_FAILURES):
                flash(_("Juda ko‘p noto‘g‘ri urinish. 15 daqiqadan so‘ng qayta urinib ko‘ring."), "danger")
                return render_template("public/signin.html", form=request.form), 429
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter(func.lower(User.username) == username.lower()).first() if username else None
            if user and check_password_hash(user.password_hash, password):
                throttle.reset(ip_key)
                session.clear()
                session["user_id"] = user.id
                user.last_seen_at = utcnow()
                db.session.commit()
                return redirect(safe_next(request.args.get("next")) or url_for("tasks"))
            throttle.fail(ip_key)
            flash(_("Login yoki parol noto‘g‘ri."), "danger")
            return render_template("public/signin.html", form=request.form), 401
        return render_template("public/signin.html", form={})

    @application.route("/signout", methods=["POST"])
    def signout():
        session.clear()
        return redirect(url_for("tasks"))

    # ---------------- Masalalar arxivi ----------------

    @application.route("/tasks")
    def tasks():
        level = request.args.get("level", "")
        query = " ".join(request.args.get("q", "").split()).casefold()[:80]
        status_filter = request.args.get("status", "")
        user = current_user()
        stats = problem_stats()
        solved, tried = set(), set()
        if user:
            for question_id, status in db.session.execute(
                db.select(Submission.question_id, Submission.status).where(Submission.user_id == user.id).distinct()
            ):
                (solved if status == "accepted" else tried).add(question_id)
        rows = []
        for question in archive_problems():
            if level in ("easy", "medium", "hard") and question.difficulty != level:
                continue
            code = problem_code(question)
            title = problem_title(question)
            if query and query not in title.casefold() and query not in code.casefold():
                continue
            mark = "solved" if question.id in solved else ("tried" if question.id in tried else "")
            if status_filter == "solved" and mark != "solved":
                continue
            if status_filter == "unsolved" and mark == "solved":
                continue
            solvers, total, accepted = stats.get(question.id, (0, 0, 0))
            rows.append({
                "code": code,
                "title": title,
                "difficulty": question.difficulty,
                "solvers": solvers,
                "attempts": total,
                "success": round(accepted * 100 / total, 1) if total else None,
                "mark": mark,
            })
        sort = request.args.get("sort", "")
        if sort == "solvers":
            rows.sort(key=lambda row: -row["solvers"])
        elif sort == "success":
            rows.sort(key=lambda row: -(row["success"] or 0))
        pages = max(1, math.ceil(len(rows) / TASKS_PER_PAGE))
        page = min(max(request.args.get("page", 1, type=int), 1), pages)
        return render_template(
            "public/tasks.html",
            rows=rows[(page - 1) * TASKS_PER_PAGE: page * TASKS_PER_PAGE],
            total=len(rows),
            page=page,
            pages=pages,
            args={"q": request.args.get("q", ""), "level": level, "status": status_filter, "sort": sort},
            solved_count=len(solved),
        )

    @application.route("/tasks/<code>")
    def task(code):
        question = get_problem(code)
        user = current_user()
        submissions = []
        if user:
            submissions = (
                Submission.query.filter_by(user_id=user.id, question_id=question.id)
                .order_by(Submission.id.desc())
                .limit(30)
                .all()
            )
        solvers, total, accepted = problem_stats().get(question.id, (0, 0, 0))
        return render_template(
            "public/task.html",
            question=question,
            code=problem_code(question),
            title=problem_title(question),
            sections=problem_sections(question),
            samples=problem_samples(question),
            time_limit_ms=int(TIME_LIMIT * 1000),
            memory_limit_mb=MEMORY_LIMIT_MB,
            solvers=solvers,
            success=round(accepted * 100 / total, 1) if total else None,
            submissions=submissions,
            last_source=submissions[0].source_code if submissions else "",
            last_language=submissions[0].language if submissions else "python",
            pending=any(item.status == "pending" for item in submissions),
        )

    @application.route("/tasks/<code>/run", methods=["POST"])
    @login_required
    def task_run(code):
        get_problem(code)
        data = request.get_json(silent=True) or {}
        language = data.get("language")
        source_code = data.get("source_code") or ""
        stdin_text = data.get("stdin") or ""
        if language not in LANGUAGE_NAMES or not isinstance(source_code, str) or not isinstance(stdin_text, str):
            abort(400)
        if not source_code.strip():
            return jsonify(error=_("Avval kod yozing.")), 400
        user_id = current_user().id
        cooldown = application.config["RUN_COOLDOWN_SECONDS"]
        now = time.monotonic()
        with run_lock:
            last = run_times.get(user_id)
            if cooldown and last and now - last < cooldown:
                return jsonify(error=_("Juda tez. %(seconds)s soniyadan so‘ng qayta ishga tushiring.",
                                       seconds=f"{cooldown - (now - last):.0f}")), 429
            run_times[user_id] = now
        db.session.remove()  # dastur ishlayotganda baza ulanishini band qilib turmaymiz
        try:
            result = run_program(language, source_code, stdin_text.replace("\r\n", "\n"))
        except JudgeError as error:
            with run_lock:
                run_times.pop(user_id, None)
            return jsonify(error=_(str(error))), 503
        return jsonify(result)

    @application.route("/tasks/<code>/submit", methods=["POST"])
    @login_required
    def task_submit(code):
        question = get_problem(code)
        user = current_user()
        wants_json = request.headers.get("X-Requested-With") == "fetch"

        def reply(message, category, status=400, submission_id=None):
            if wants_json:
                return jsonify(error=message if category != "info" else None, message=message, id=submission_id), status
            flash(message, category)
            return redirect(url_for("task", code=problem_code(question)))

        source_code = request.form.get("source_code", "").strip()
        language = request.form.get("language", "")
        if language not in LANGUAGE_NAMES:
            abort(400)
        if not source_code or len(source_code) > MAX_SOURCE_CHARS:
            return reply(_("Kodingizni kiriting (ko‘pi bilan 20 000 belgi)."), "danger")
        now = utcnow()
        last = (
            Submission.query.filter_by(user_id=user.id).order_by(Submission.id.desc()).first()
        )
        cooldown = application.config["PUBLIC_SUBMIT_COOLDOWN_SECONDS"]
        if last and cooldown and (now - last.created_at).total_seconds() < cooldown:
            wait = int(cooldown - (now - last.created_at).total_seconds()) + 1
            return reply(_("Yechimlar orasida kamida %(cooldown)s soniya bo‘lishi kerak. %(wait)s soniyadan so‘ng yuboring.",
                           cooldown=cooldown, wait=wait), "warning", 429)
        stale_before = now - timedelta(seconds=PENDING_STALE_SECONDS)
        if Submission.query.filter(
            Submission.user_id == user.id, Submission.status == "pending", Submission.created_at > stale_before
        ).first():
            return reply(_("Oldingi yechimingiz hali tekshirilmoqda. Biroz kuting."), "warning", 429)
        submission = Submission(
            user_id=user.id,
            question_id=question.id,
            language=language,
            source_code=source_code,
            status="pending",
            created_at=now,
        )
        db.session.add(submission)
        user.last_seen_at = now
        db.session.commit()
        job = (submission.id, language, source_code, question.test_cases_json)
        if application.config["JUDGE_SYNC"]:
            run_public_judge(*job)
        else:
            judge_pool.submit(run_public_judge, *job)
        return reply(_("Yechim qabul qilindi va tekshiruv navbatiga qo‘yildi."), "info", 202, submission.id)

    def run_public_judge(submission_id, language, source_code, test_cases_json):
        with application.app_context():
            try:
                try:
                    accepted, message = judge_solution(language, source_code, json.loads(test_cases_json or "[]"))
                    status = "accepted" if accepted else "rejected"
                except JudgeError as error:
                    message, status = str(error), "error"
                except json.JSONDecodeError:
                    message, status = "Masala testlari JSON formati noto‘g‘ri.", "error"
                except Exception:
                    application.logger.exception("Ichki judge kutilmagan xatolik berdi")
                    message, status = "Tekshiruv serverida ichki xatolik yuz berdi.", "error"
                submission = db.session.get(Submission, submission_id)
                if submission is not None:
                    submission.status = status
                    submission.verdict = message[:500]
                    submission.judged_at = utcnow()
                    db.session.commit()
            except Exception:
                db.session.rollback()
                application.logger.exception("Tekshiruv natijasini saqlab bo‘lmadi")
            finally:
                db.session.remove()

    @application.route("/submissions/<int:submission_id>.json")
    @login_required
    def submission_status(submission_id):
        submission = db.session.get(Submission, submission_id)
        if submission is None or submission.user_id != current_user().id:
            abort(404)
        label, kind = short_verdict(submission.status, submission.verdict)
        return jsonify(id=submission.id, status=submission.status, label=label, kind=kind)
