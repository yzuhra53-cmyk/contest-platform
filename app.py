import hmac
import io
import json
import os
import secrets
import csv
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile

from dotenv import load_dotenv

load_dotenv()

from models import (
    Attempt,
    BankImport,
    CodeSubmission,
    Contest,
    ProctorEvent,
    ProctorState,
    Question,
    Student,
    SubmissionLog,
    db,
    utcnow,
)
from judge import MAX_PARALLEL, JudgeError, judge_solution, run_program
import proctoring

# Kirish kodi: chalkash belgilarsiz (0/O, 1/I/L yo'q), 8 belgi = ~40 bit.
ACCESS_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ACCESS_CODE_LENGTH = 8
ACCESS_CODE_HASH_METHOD = "pbkdf2:sha256:60000"

LOGIN_WINDOW_SECONDS = 15 * 60
ADMIN_MAX_FAILURES = 5
STUDENT_MAX_FAILURES = 10
PENDING_RESUBMIT_SECONDS = 180
DEFAULT_MAX_VIOLATIONS = 5
ICPC_WRONG_PENALTY_MINUTES = 20

# Bazada vaqt UTC'da saqlanadi; ekranda va formalarda mahalliy vaqt (Toshkent: UTC+5).
UTC_OFFSET = timedelta(hours=float(os.environ.get("APP_UTC_OFFSET_HOURS", "5")))
LOCAL_INPUT_FORMAT = "%Y-%m-%dT%H:%M"


def to_local(value):
    return value + UTC_OFFSET if value is not None else None


def format_local(value, fmt="%d.%m.%Y %H:%M"):
    return to_local(value).strftime(fmt) if value is not None else ""


def parse_local(value):
    """<input type="datetime-local"> qiymatini UTC'ga o'tkazadi. Bo'sh bo'lsa None."""
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value[:16], LOCAL_INPUT_FORMAT) - UTC_OFFSET


def contest_state(contest, now=None):
    """closed — ustoz yopgan; upcoming — hali boshlanmagan; finished — vaqti tugagan; open."""
    now = now or utcnow()
    if not contest.is_active:
        return "closed"
    if contest.start_at is not None and now < contest.start_at:
        return "upcoming"
    if contest.end_at is not None and now >= contest.end_at:
        return "finished"
    return "open"


APOSTROPHES = str.maketrans({ch: "'" for ch in "\u2018\u2019\u02bb\u02bc\u0060\u00b4"})


def normalize_person_text(value):
    """F.I.Sh. va guruhni solishtirish uchun: katta-kichik harf, bo'shliqlar va
    apostrof turlari (o‘, oʻ, o') farqi hisobga olinmaydi."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(APOSTROPHES)
    return " ".join(text.casefold().split())


def generate_access_code():
    return "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(ACCESS_CODE_LENGTH))


def format_access_code(code):
    return f"{code[:4]}-{code[4:]}"


def normalize_access_code(value):
    return "".join(char for char in (value or "").upper() if char.isalnum())


def hash_access_code(code):
    return generate_password_hash(normalize_access_code(code), method=ACCESS_CODE_HASH_METHOD)


class LoginThrottle:
    """Muvaffaqiyatsiz kirishlarni xotirada sanaydi (bitta gunicorn worker uchun yetarli)."""

    def __init__(self):
        self._failures = {}
        self._lock = threading.Lock()

    def _recent(self, key, now):
        stamps = [stamp for stamp in self._failures.get(key, ()) if now - stamp < LOGIN_WINDOW_SECONDS]
        if stamps:
            self._failures[key] = stamps
        else:
            self._failures.pop(key, None)
        return stamps

    def blocked(self, key, limit):
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= limit

    def fail(self, key):
        now = time.monotonic()
        with self._lock:
            if len(self._failures) > 10000:
                for stale_key in list(self._failures):
                    self._recent(stale_key, now)
            self._failures.setdefault(key, []).append(now)

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)


def create_app(test_config=None):
    application = Flask(__name__)
    if os.environ.get("RENDER"):
        # Render proksi ortida: haqiqiy mijoz IP manzili X-Forwarded-For'da keladi.
        application.wsgi_app = ProxyFix(application.wsgi_app, x_for=1, x_proto=1)
    database_url = os.environ.get("DATABASE_URL", "sqlite:///contest.db")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    secret_key = os.environ.get("SECRET_KEY")
    if os.environ.get("RENDER") and not secret_key:
        raise RuntimeError("Render deploy uchun SECRET_KEY environment variable belgilang.")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password:
        if os.environ.get("RENDER"):
            raise RuntimeError("Render deploy uchun ADMIN_PASSWORD environment variable belgilang.")
        # Lokal ishga tushirishda standart parol yo'q: har safar tasodifiy parol yaratiladi.
        admin_password = secrets.token_urlsafe(12)
        print(
            "\n[Bilim.Arena] ADMIN_PASSWORD .env faylida belgilanmagan.\n"
            f"[Bilim.Arena] Bu safar uchun vaqtinchalik ustoz paroli: {admin_password}\n",
            flush=True,
        )
    application.config.update(
        SECRET_KEY=secret_key or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "Zuhra"),
        ADMIN_PASSWORD=admin_password,
        DEBUG=not bool(os.environ.get("RENDER")) and os.environ.get("FLASK_DEBUG", "").lower() == "true",
        TRUSTED_HOSTS=[os.environ["RENDER_EXTERNAL_HOSTNAME"]]
        if os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        else None,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),
        # True bo'lsa yechim so'rov ichida tekshiriladi (testlar uchun qulay).
        JUDGE_SYNC=False,
        # Bitta talabaning ketma-ket yechim yuborishlari orasidagi minimal oraliq.
        SUBMIT_COOLDOWN_SECONDS=int(os.environ.get("SUBMIT_COOLDOWN_SECONDS", "20")),
        RUN_COOLDOWN_SECONDS=int(os.environ.get("RUN_COOLDOWN_SECONDS", "3")),
    )
    if test_config:
        application.config.update(test_config)
    db.init_app(application)
    application.jinja_env.filters["local"] = format_local
    application.jinja_env.globals["contest_state"] = contest_state
    throttle = LoginThrottle()
    judge_pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL, thread_name_prefix="judge")

    @application.before_request
    def protect_post_requests():
        if request.method == "POST":
            supplied_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            expected_token = session.get("csrf_token")
            if not isinstance(expected_token, str) or not isinstance(supplied_token, str):
                abort(400, description="So‘rov xavfsizlik tekshiruvidan o‘tmadi. Sahifani yangilang.")
            if not hmac.compare_digest(supplied_token, expected_token):
                abort(400, description="So‘rov xavfsizlik tekshiruvidan o‘tmadi. Sahifani yangilang.")

    @application.context_processor
    def inject_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"csrf_token": session["csrf_token"]}

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("is_admin"):
                return redirect(url_for("admin_login"))
            return view(*args, **kwargs)

        return wrapped

    def student_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("student_id"):
                return redirect(url_for("student_login"))
            student = db.session.get(Student, session["student_id"])
            if student is None:
                session.clear()
                flash("Talaba hisobi topilmadi. Qayta kiring.", "warning")
                return redirect(url_for("student_login"))
            if student.session_token and not hmac.compare_digest(
                str(session.get("student_token", "")), student.session_token
            ):
                # Bir vaqtda faqat bitta qurilma/brauzer: yangi kirish eskisini chiqaradi.
                session.clear()
                flash(
                    "Hisobingizga boshqa qurilma yoki brauzerdan kirildi. Bir vaqtda faqat bitta joyda ishlash mumkin.",
                    "warning",
                )
                return redirect(url_for("student_login"))
            return view(*args, **kwargs)

        return wrapped

    def normalize_output(value):
        return "\n".join(line.rstrip() for line in (value or "").replace("\r\n", "\n").split("\n")).strip()

    def attempt_deadline(attempt):
        deadline = attempt.started_at + timedelta(minutes=attempt.contest.duration_minutes)
        if attempt.contest.end_at is not None:
            deadline = min(deadline, attempt.contest.end_at)
        return deadline

    def score_attempt(attempt, answers, commit=True):
        questions = attempt.contest.questions
        correct = 0
        for question in questions:
            answer = str(answers.get(str(question.id), "")).strip()
            if question.question_type in {"test", "code_output"}:
                if answer.upper() == question.correct_option:
                    correct += 1
            elif question.question_type == "code_problem":
                submission = CodeSubmission.query.filter_by(
                    attempt_id=attempt.id, question_id=question.id, status="accepted"
                ).first()
                if submission:
                    correct += 1
            elif normalize_output(answer) == normalize_output(question.expected_output):
                correct += 1
        total = len(questions)
        attempt.answers_json = json.dumps(answers, ensure_ascii=False)
        attempt.correct_count = correct
        attempt.total_questions = total
        attempt.score = round(correct * 100 / total, 2) if total else 0
        # Vaqt tugagach yakunlangan urinish uchun yakun vaqti — muddat oxiri.
        attempt.completed_at = min(utcnow(), attempt_deadline(attempt))
        if commit:
            db.session.commit()

    def finalize_expired_attempts(student_id=None):
        """Vaqti tugagan, lekin talaba qaytib kelmagan urinishlarni baholaydi.

        Aks holda brauzerni yopib ketgan talabalar natijalar ro'yxatiga tushmaydi.
        """
        query = Attempt.query.filter(Attempt.completed_at.is_(None))
        if student_id is not None:
            query = query.filter(Attempt.student_id == student_id)
        now = utcnow()
        finalized = False
        for attempt in query.all():
            if now >= attempt_deadline(attempt):
                score_attempt(attempt, json.loads(attempt.answers_json or "{}"), commit=False)
                finalized = True
        if finalized:
            db.session.commit()

    def get_attempt(student_id, contest_id):
        return Attempt.query.filter_by(student_id=student_id, contest_id=contest_id).first()

    def client_ip():
        return request.remote_addr or "unknown"

    @application.route("/")
    def index():
        if session.get("is_admin"):
            return redirect(url_for("admin_dashboard"))
        if session.get("student_id"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_login"))

    @application.route("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok"})

    @application.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            throttle_key = ("admin", client_ip())
            if throttle.blocked(throttle_key, ADMIN_MAX_FAILURES):
                flash("Juda ko‘p noto‘g‘ri urinish. 15 daqiqadan so‘ng qayta urinib ko‘ring.", "danger")
                return render_template("admin_login.html"), 429
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            valid_user = hmac.compare_digest(username.encode(), application.config["ADMIN_USERNAME"].encode())
            valid_password = hmac.compare_digest(password.encode(), application.config["ADMIN_PASSWORD"].encode())
            if valid_user and valid_password:
                throttle.reset(throttle_key)
                session.clear()
                session["is_admin"] = True
                return redirect(url_for("admin_dashboard"))
            throttle.fail(throttle_key)
            flash("Login yoki parol noto‘g‘ri.", "danger")
        return render_template("admin_login.html")

    @application.route("/login", methods=["GET", "POST"])
    def student_login():
        if request.method == "POST":
            hemis_id = request.form.get("hemis_id", "").strip()
            full_name = " ".join(request.form.get("full_name", "").split())
            group_name = " ".join(request.form.get("group_name", "").split())
            if not hemis_id or not full_name or not group_name:
                flash("HEMIS ID, F.I.Sh. va guruhni to‘liq kiriting.", "danger")
                return render_template("student_login.html", form=request.form), 400
            # Bazada yo'q HEMIS ID larni ketma-ket sinash IP bo'yicha sekinlashtiriladi.
            ip_key = ("student-ip", client_ip())
            if throttle.blocked(ip_key, STUDENT_MAX_FAILURES * 5):
                flash("Juda ko‘p noto‘g‘ri urinish. 15 daqiqadan so‘ng qayta urinib ko‘ring.", "danger")
                return render_template("student_login.html", form=request.form), 429
            student = db.session.get(Student, hemis_id)
            if (
                student
                and normalize_person_text(student.full_name) == normalize_person_text(full_name)
                and normalize_person_text(student.group_name) == normalize_person_text(group_name)
            ):
                had_session = bool(student.session_token)
                student.session_token = secrets.token_hex(24)
                if had_session:
                    open_attempts = Attempt.query.filter(
                        Attempt.student_id == student.hemis_id, Attempt.completed_at.is_(None)
                    ).all()
                    for open_attempt in open_attempts:
                        if utcnow() < attempt_deadline(open_attempt):
                            record_proctor_event(open_attempt, "new_device_login", request.headers.get("User-Agent", ""))
                            enforce_violation_limit(open_attempt)
                db.session.commit()
                session.clear()
                session["student_id"] = student.hemis_id
                session["student_token"] = student.session_token
                return redirect(url_for("student_dashboard"))
            throttle.fail(ip_key)
            flash(
                "HEMIS ID, F.I.Sh. yoki guruh ro‘yxatdagi ma’lumotga mos kelmadi. "
                "Ismingizni ro‘yxatdan tanlang va HEMIS ID’ni tekshiring.",
                "danger",
            )
            return render_template("student_login.html", form=request.form)
        return render_template("student_login.html", form={})

    @application.route("/login/lookup")
    def student_login_lookup():
        """F.I.Sh. va guruh ro'yxatdagi bitta talabaga to'liq mos kelsa, uning HEMIS ID'sini qaytaradi."""
        name = normalize_person_text(request.args.get("name", ""))
        group = normalize_person_text(request.args.get("group", ""))
        if not name or not group:
            return jsonify({})
        ip_key = ("lookup-ip", client_ip())
        if throttle.blocked(ip_key, 300):
            return jsonify({}), 429
        throttle.fail(ip_key)  # oddiy hisoblagich: 15 daqiqada 300 so'rovdan oshmasin
        found = [
            hemis_id
            for hemis_id, full_name, group_name in db.session.execute(
                db.select(Student.hemis_id, Student.full_name, Student.group_name)
            )
            if normalize_person_text(full_name) == name and normalize_person_text(group_name) == group
        ]
        return jsonify({"hemis_id": found[0]} if len(found) == 1 else {})

    @application.route("/login/suggest")
    def student_login_suggest():
        """Kirish sahifasi uchun: ism bo'yicha F.I.Sh. va guruh takliflari (HEMIS ID berilmaydi)."""
        query = normalize_person_text(request.args.get("q", ""))[:80]
        if len(query) < 3:
            return jsonify([])
        ip_key = ("suggest-ip", client_ip())
        if throttle.blocked(ip_key, 600):
            return jsonify([]), 429
        throttle.fail(ip_key)  # oddiy hisoblagich: 15 daqiqada 600 so'rovdan oshmasin
        words = query.split()
        matches = []
        for full_name, group_name in db.session.execute(
            db.select(Student.full_name, Student.group_name).order_by(Student.full_name)
        ):
            name = normalize_person_text(full_name)
            if all(word in name for word in words):
                matches.append({"name": full_name, "group": group_name, "starts": name.startswith(query)})
        matches.sort(key=lambda item: (not item["starts"], item["name"]))
        return jsonify([{"name": item["name"], "group": item["group"]} for item in matches[:8]])

    @application.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("student_login"))

    @application.route("/admin/logout", methods=["POST"])
    @admin_required
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    @application.route("/admin")
    @admin_required
    def admin_dashboard():
        finalize_expired_attempts()
        return render_template(
            "admin_dashboard.html",
            student_count=Student.query.count(),
            question_count=Question.query.count(),
            contest_count=Contest.query.count(),
            attempt_count=Attempt.query.filter(Attempt.completed_at.is_not(None)).count(),
            active_contests=Contest.query.filter_by(is_active=True).all(),
        )

    @application.route("/admin/students", methods=["GET", "POST"])
    @admin_required
    def admin_students():
        if request.method == "POST":
            hemis_id = request.form.get("hemis_id", "").strip()
            full_name = request.form.get("full_name", "").strip()
            group_name = request.form.get("group_name", "").strip()
            if not all((hemis_id, full_name, group_name)):
                flash("Barcha maydonlarni to‘ldiring.", "danger")
            elif db.session.get(Student, hemis_id):
                flash("Bu HEMIS ID avval ro‘yxatga qo‘shilgan.", "warning")
            else:
                db.session.add(Student(hemis_id=hemis_id, full_name=full_name, group_name=group_name))
                db.session.commit()
                flash("Talaba qo‘shildi. U HEMIS ID, F.I.Sh. va guruhini yozib kira oladi.", "success")
            return redirect(url_for("admin_students"))
        students = Student.query.order_by(Student.full_name).all()
        return render_template(
            "students.html",
            students=students,
            missing_code_count=sum(1 for student in students if not student.access_code_hash),
        )

    @application.route("/admin/students/codes.xlsx", methods=["POST"])
    @admin_required
    def export_access_codes():
        """Kirish kodlarini yaratadi va Excel fayl sifatida beradi.

        Bazada faqat xesh saqlanadi, shuning uchun kodlar faqat shu faylda ko'rinadi.
        scope=missing — faqat kodi yo'q talabalar; scope=all — barchasiga yangi kod.
        """
        scope = request.form.get("scope", "missing")
        if scope not in {"missing", "all"}:
            abort(400)
        query = Student.query.order_by(Student.group_name, Student.full_name)
        if scope == "missing":
            query = query.filter(Student.access_code_hash.is_(None))
        students = query.all()
        if not students:
            flash("Kirish kodi kerak bo‘lgan talaba topilmadi.", "info")
            return redirect(url_for("admin_students"))
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Kirish kodlari"
        sheet.append(["HEMIS ID", "F.I.O", "Guruh", "Kirish kodi"])
        for student in students:
            code = generate_access_code()
            student.access_code_hash = hash_access_code(code)
            sheet.append([student.hemis_id, student.full_name, student.group_name, format_access_code(code)])
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        db.session.commit()
        return send_file(
            output,
            as_attachment=True,
            download_name=f"kirish_kodlari_{utcnow():%Y%m%d_%H%M}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @application.route("/admin/students/<hemis_id>/reset-code", methods=["POST"])
    @admin_required
    def reset_access_code(hemis_id):
        student = db.session.get(Student, hemis_id)
        if student is None:
            abort(404)
        code = generate_access_code()
        student.access_code_hash = hash_access_code(code)
        db.session.commit()
        flash(
            f"{student.full_name} uchun yangi kirish kodi: {format_access_code(code)} "
            "(eski kod endi ishlamaydi).",
            "success",
        )
        return redirect(url_for("admin_students"))

    @application.route("/admin/students/import", methods=["POST"])
    @admin_required
    def import_students():
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            flash("Yuklash uchun .xlsx yoki .csv faylni tanlang.", "danger")
            return redirect(url_for("admin_students"))
        file_extension = os.path.splitext(uploaded.filename)[1].lower()
        if file_extension not in {".xlsx", ".csv"}:
            flash("Faqat .xlsx yoki .csv formatidagi fayl qabul qilinadi.", "danger")
            return redirect(url_for("admin_students"))
        workbook = None
        try:
            if file_extension == ".xlsx":
                workbook = load_workbook(uploaded.stream, read_only=True, data_only=True)
                sheet = workbook.worksheets[0] if workbook.worksheets else None
                if sheet is None:
                    raise ValueError("Excel faylida faol varaq topilmadi.")
                rows = sheet.iter_rows(values_only=True)
            else:
                raw_csv = uploaded.stream.read()
                try:
                    csv_text = raw_csv.decode("utf-8-sig")
                except UnicodeDecodeError:
                    try:
                        csv_text = raw_csv.decode("cp1251")
                    except UnicodeDecodeError as error:
                        raise ValueError("CSV fayli UTF-8 yoki Windows-1251 kodlashida bo‘lishi kerak.") from error
                sample = csv_text[:4096]
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
                rows = csv.reader(io.StringIO(csv_text), dialect)
            def normalize_header(value):
                text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
                return "".join(char for char in text if not unicodedata.combining(char)).replace(".", "")

            def column(*names):
                aliases = {normalize_header(name) for name in names}
                for name in names:
                    normalized_names = [
                        normalize_header(value) if value is not None else ""
                        for value in header_row
                    ]
                    if normalize_header(name) in normalized_names:
                        return normalized_names.index(normalize_header(name))
                for position, normalized_name in enumerate(normalized_names):
                    if normalized_name in aliases:
                        return position
                raise ValueError("Ustunlar: HEMIS ID, F.I.O va Guruh bo‘lishi kerak.")

            header_row = None
            data_rows = iter(rows)
            for candidate in data_rows:
                if candidate and any(value is not None and str(value).strip() for value in candidate):
                    candidate_names = {normalize_header(value) for value in candidate if value is not None}
                    has_id = bool(candidate_names & {"hemis id", "hemis_id", "id"})
                    has_name = bool(candidate_names & {"fio", "full name", "ism"})
                    has_group = bool(candidate_names & {"guruh", "group", "group_name"})
                    if has_id and has_name and has_group:
                        header_row = candidate
                        break
            if header_row is None:
                raise ValueError("Faylda HEMIS ID, F.I.O va Guruh sarlavhalari topilmadi.")

            id_col = column("hemis id", "hemis_id", "id")
            name_col = column("f.i.o", "fio", "full name", "ism")
            group_col = column("guruh", "group", "group_name")
            added = 0
            skipped = 0
            for row in data_rows:
                values = [row[position] if position < len(row) else None for position in (id_col, name_col, group_col)]
                hemis_id, full_name, group_name = [str(value).strip() if value is not None else "" for value in values]
                if not all((hemis_id, full_name, group_name)) or db.session.get(Student, hemis_id):
                    skipped += 1
                    continue
                db.session.add(Student(hemis_id=hemis_id, full_name=full_name, group_name=group_name))
                added += 1
            db.session.commit()
            flash(f"{added} ta talaba qo‘shildi, {skipped} ta qator o‘tkazib yuborildi. "
                "Yangi talabalar uchun «Kodlarni yaratish» tugmasi orqali kirish kodlarini oling.", "success")
        except (ValueError, KeyError) as error:
            db.session.rollback()
            flash(str(error), "danger")
        except (InvalidFileException, BadZipFile, OSError, TypeError):
            db.session.rollback()
            application.logger.exception("Excel faylni o‘qishda xatolik")
            flash("Faylni o‘qib bo‘lmadi. Fayl buzilmaganini va kodlashini tekshiring.", "danger")
        finally:
            if workbook is not None:
                workbook.close()
        return redirect(url_for("admin_students"))

    @application.route("/admin/students/<hemis_id>/delete", methods=["POST"])
    @admin_required
    def delete_student(hemis_id):
        student = db.session.get(Student, hemis_id)
        if student is None:
            abort(404)
        if student.attempts:
            flash("Natijalari mavjud talabani o‘chirib bo‘lmaydi.", "warning")
        else:
            db.session.delete(student)
            db.session.commit()
            flash("Talaba o‘chirildi.", "success")
        return redirect(url_for("admin_students"))

    @application.route("/admin/questions", methods=["GET", "POST"])
    @admin_required
    def admin_questions():
        if request.method == "POST":
            question_type = request.form.get("question_type", "test")
            prompt = request.form.get("prompt", "").strip()
            question = Question(question_type=question_type, prompt=prompt)
            if question_type == "test":
                question.option_a = request.form.get("option_a", "").strip()
                question.option_b = request.form.get("option_b", "").strip()
                question.option_c = request.form.get("option_c", "").strip()
                question.option_d = request.form.get("option_d", "").strip()
                question.correct_option = request.form.get("correct_option", "").upper()
                if not prompt or not all((question.option_a, question.option_b, question.option_c, question.option_d)):
                    flash("Savol va to‘rtta javob variantini kiriting.", "danger")
                    return redirect(url_for("admin_questions"))
                if question.correct_option not in {"A", "B", "C", "D"}:
                    flash("To‘g‘ri javobni A, B, C yoki D sifatida tanlang.", "danger")
                    return redirect(url_for("admin_questions"))
            elif question_type == "code_output":
                question.code_snippet = request.form.get("code_snippet", "").strip()
                question.input_data = request.form.get("code_input_data", "").strip()
                question.option_a = request.form.get("option_a", "").strip()
                question.option_b = request.form.get("option_b", "").strip()
                question.option_c = request.form.get("option_c", "").strip()
                question.option_d = request.form.get("option_d", "").strip()
                question.correct_option = request.form.get("correct_option", "").upper()
                if not prompt or not question.code_snippet or not all(
                    (question.option_a, question.option_b, question.option_c, question.option_d)
                ):
                    flash("Savol, Python kodi va to‘rtta chiqish variantini kiriting.", "danger")
                    return redirect(url_for("admin_questions"))
                if question.correct_option not in {"A", "B", "C", "D"}:
                    flash("To‘g‘ri chiqishni A, B, C yoki D sifatida belgilang.", "danger")
                    return redirect(url_for("admin_questions"))
            elif question_type == "code":
                question.input_data = request.form.get("input_data", "").strip()
                question.expected_output = request.form.get("expected_output", "").strip()
                if not prompt or not question.expected_output:
                    flash("Masala sharti va kutilgan chiqish ma’lumotini kiriting.", "danger")
                    return redirect(url_for("admin_questions"))
            elif question_type == "code_problem":
                question.input_data = request.form.get("input_data", "").strip()
                question.expected_output = request.form.get("expected_output", "").strip()
                raw_test_cases = request.form.get("test_cases_json", "").strip()
                if not prompt or not question.input_data or not question.expected_output:
                    flash("Masala sharti, namunaviy Input va Outputni kiriting.", "danger")
                    return redirect(url_for("admin_questions"))
                try:
                    test_cases = json.loads(raw_test_cases)
                    if not isinstance(test_cases, list) or not test_cases:
                        raise ValueError
                    if any(
                        not isinstance(case, dict)
                        or not isinstance(case.get("input"), str)
                        or not isinstance(case.get("output"), str)
                        for case in test_cases
                    ):
                        raise ValueError
                except (ValueError, json.JSONDecodeError):
                    flash("Yashirin testlar JSON ro‘yxati bo‘lishi, har birida input va output satrlari bo‘lishi kerak.", "danger")
                    return redirect(url_for("admin_questions"))
                question.test_cases_json = json.dumps(test_cases, ensure_ascii=False)
            else:
                abort(400)
            db.session.add(question)
            db.session.commit()
            flash("Savol bazaga qo‘shildi.", "success")
            return redirect(url_for("admin_questions"))
        return render_template("questions.html", questions=Question.query.order_by(Question.id.desc()).all())

    @application.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
    @admin_required
    def delete_question(question_id):
        question = db.session.get(Question, question_id)
        if question is None:
            abort(404)
        if question.contests:
            flash("Kontestga biriktirilgan savolni o‘chirib bo‘lmaydi.", "warning")
        else:
            db.session.delete(question)
            db.session.commit()
            flash("Savol o‘chirildi.", "success")
        return redirect(url_for("admin_questions"))

    @application.route("/admin/contests", methods=["GET", "POST"])
    @admin_required
    def admin_contests():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            try:
                duration = int(request.form.get("duration_minutes", ""))
            except ValueError:
                duration = 0
            contest_type = request.form.get("contest_type", "quiz")
            start_as_teacher = request.form.get("start_as_teacher") == "on"
            allowed_types = {
                "quiz": ("code_output",), "coding": ("code_problem",), "mixed": ("code_problem", "code_output"),
            }.get(contest_type, ())
            selected_ids = request.form.getlist("question_ids")
            selected = [int(value) for value in selected_ids if value.isdigit()]
            questions = (
                Question.query.filter(
                    Question.id.in_(selected),
                    Question.question_type.in_(allowed_types),
                ).order_by(Question.id.asc()).all()
                if selected
                else []
            )
            window_error = None
            try:
                start_at, end_at = read_contest_window(request.form)
            except ValueError as error:
                start_at = end_at = None
                window_error = str(error)
            mixed_incomplete = contest_type == "mixed" and {
                question.question_type for question in questions
            } != {"code_problem", "code_output"}
            if contest_type not in {"quiz", "coding", "mixed"} or not title or not 1 <= duration <= 600 or not questions:
                flash("Kontest turi, nomi, 1–600 daqiqalik vaqt va shu turga mos kamida bitta masala kerak.", "danger")
            elif mixed_incomplete:
                flash("Aralash kontestga kamida bitta kod yozish masalasi va bitta test savoli tanlang.", "danger")
            elif window_error:
                flash(window_error, "danger")
            else:
                contest = Contest(
                    title=title,
                    duration_minutes=duration,
                    is_active=False if start_as_teacher else request.form.get("is_active") == "on",
                    contest_type=contest_type,
                    questions=questions,
                    start_at=start_at,
                    end_at=end_at,
                    public_leaderboard=request.form.get("public_leaderboard") == "on",
                    proctoring=request.form.get("proctoring") == "on",
                    screen_capture=request.form.get("screen_capture") == "on",
                    lockdown=request.form.get("lockdown") == "on",
                    require_seb=request.form.get("require_seb") == "on",
                    max_violations=read_max_violations(request.form),
                )
                db.session.add(contest)
                db.session.commit()
                if start_as_teacher:
                    flash("Kontest yaratildi. Ustoz ko‘rigi ochildi; talabalar uchun alohida faollashtiring.", "success")
                    return redirect(url_for("admin_preview_contest", contest_id=contest.id))
                flash("Kontest yaratildi.", "success")
            return redirect(url_for("admin_contests"))
        return render_template(
            "contests.html",
            seb_configured=bool(proctoring.seb_config_keys()),
            default_max_violations=DEFAULT_MAX_VIOLATIONS,
            contests=Contest.query.order_by(Contest.id.desc()).all(),
            quiz_questions=Question.query.filter_by(question_type="code_output").order_by(Question.id.desc()).all(),
            coding_questions=Question.query.filter_by(question_type="code_problem").order_by(Question.id.desc()).all(),
        )

    def read_max_violations(form):
        try:
            return max(0, min(50, int(form.get("max_violations", "0") or 0)))
        except ValueError:
            return 0

    def read_contest_window(form):
        try:
            start_at = parse_local(form.get("start_at"))
            end_at = parse_local(form.get("end_at"))
        except ValueError:
            raise ValueError("Boshlanish yoki tugash vaqti noto‘g‘ri formatda.") from None
        if start_at and end_at and end_at <= start_at:
            raise ValueError("Tugash vaqti boshlanish vaqtidan keyin bo‘lishi kerak.")
        return start_at, end_at

    @application.route("/admin/contests/<int:contest_id>/settings", methods=["POST"])
    @admin_required
    def update_contest_settings(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        try:
            contest.start_at, contest.end_at = read_contest_window(request.form)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("admin_contests"))
        contest.public_leaderboard = request.form.get("public_leaderboard") == "on"
        contest.proctoring = request.form.get("proctoring") == "on"
        contest.screen_capture = request.form.get("screen_capture") == "on"
        contest.lockdown = request.form.get("lockdown") == "on"
        contest.require_seb = request.form.get("require_seb") == "on"
        contest.max_violations = read_max_violations(request.form)
        db.session.commit()
        flash(f"“{contest.title}” sozlamalari saqlandi.", "success")
        return redirect(url_for("admin_contests"))

    @application.route("/admin/contests/<int:contest_id>/preview", methods=["GET", "POST"])
    @admin_required
    def admin_preview_contest(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        score = None
        if request.method == "POST":
            if not contest.has_quiz:
                abort(400)
            correct = sum(
                request.form.get(str(question.id), "").upper() == question.correct_option
                for question in contest.quiz_questions
            )
            total = len(contest.quiz_questions)
            score = {
                "correct": correct,
                "total": total,
                "percentage": round(correct * 100 / total, 2) if total else 0,
            }
        return render_template("admin_preview.html", contest=contest, score=score)

    @application.route("/admin/submissions")
    @admin_required
    def admin_submissions():
        submissions = (
            CodeSubmission.query.join(CodeSubmission.attempt)
            .join(Attempt.student)
            .join(Attempt.contest)
            .order_by(CodeSubmission.submitted_at.desc())
            .all()
        )
        return render_template("submissions.html", submissions=submissions)

    @application.route("/admin/submissions/<int:submission_id>/review", methods=["POST"])
    @admin_required
    def review_submission(submission_id):
        submission = db.session.get(CodeSubmission, submission_id)
        if submission is None:
            abort(404)
        status = request.form.get("status")
        if status not in {"accepted", "rejected"}:
            abort(400)
        submission.status = status
        submission.reviewer_note = request.form.get("reviewer_note", "").strip()[:500]
        submission.reviewed_at = utcnow()
        db.session.commit()
        flash("Yechim qabul qilindi; keyingi masala ochildi." if status == "accepted" else "Yechim qaytarildi; talaba kodni tuzatib qayta yuborishi mumkin.", "success" if status == "accepted" else "warning")
        return redirect(url_for("admin_submissions"))

    @application.route("/admin/contests/<int:contest_id>/toggle", methods=["POST"])
    @admin_required
    def toggle_contest(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        contest.is_active = not contest.is_active
        db.session.commit()
        flash("Kontest holati yangilandi.", "success")
        return redirect(url_for("admin_contests"))

    @application.route("/admin/contests/<int:contest_id>/delete", methods=["POST"])
    @admin_required
    def delete_contest(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        attempt_ids = db.session.execute(
            db.select(Attempt.id).where(Attempt.contest_id == contest.id)
        ).scalars().all()
        if attempt_ids:
            submission_ids = db.select(CodeSubmission.id).where(CodeSubmission.attempt_id.in_(attempt_ids))
            SubmissionLog.query.filter(SubmissionLog.submission_id.in_(submission_ids)).delete(
                synchronize_session=False
            )
            CodeSubmission.query.filter(CodeSubmission.attempt_id.in_(attempt_ids)).delete(
                synchronize_session=False
            )
            ProctorEvent.query.filter(ProctorEvent.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
            ProctorState.query.filter(ProctorState.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
            Attempt.query.filter(Attempt.id.in_(attempt_ids)).delete(synchronize_session=False)
        db.session.delete(contest)
        db.session.commit()
        flash("Kontest, urinishlari va yuborilgan kodlari butunlay o‘chirildi. Savollar bazada saqlandi.", "success")
        return redirect(url_for("admin_contests"))

    def build_leaderboard(contest):
        """Kontest reytingi.

        Kod yozish (ICPC uslubi): yechilgan masalalar soni bo'yicha, teng bo'lsa
        jarima bo'yicha. Jarima = har bir yechilgan masala uchun urinish boshidan
        qabul qilingungacha o'tgan daqiqalar + har bir noto'g'ri urinish uchun 20 daqiqa
        (kompilyatsiya va tizim xatolari hisobga olinmaydi).
        Output testi: to'g'ri javoblar soni, teng bo'lsa sarflangan vaqt bo'yicha.
        """
        now = utcnow()
        questions = contest.questions
        attempts = Attempt.query.filter_by(contest_id=contest.id).join(Attempt.student).all()
        rows = []
        if contest.contest_type == "coding":
            attempt_ids = [attempt.id for attempt in attempts]
            submissions = (
                CodeSubmission.query.filter(CodeSubmission.attempt_id.in_(attempt_ids)).all() if attempt_ids else []
            )
            logs_by_submission = {}
            if submissions:
                for log in SubmissionLog.query.filter(
                    SubmissionLog.submission_id.in_([item.id for item in submissions])
                ).order_by(SubmissionLog.submitted_at, SubmissionLog.id):
                    logs_by_submission.setdefault(log.submission_id, []).append(log)
            by_attempt = {}
            for item in submissions:
                by_attempt.setdefault(item.attempt_id, {})[item.question_id] = item
            for attempt in attempts:
                cells, solved, penalty, last_accept = [], 0, 0, None
                for question in questions:
                    submission = by_attempt.get(attempt.id, {}).get(question.id)
                    logs = logs_by_submission.get(submission.id, []) if submission else []
                    accepted_at = next((log.submitted_at for log in logs if log.status == "accepted"), None)
                    if accepted_at is None and submission is not None and submission.status == "accepted":
                        # Ustoz qo'lda qabul qilgan yoki tarixdan oldingi yechim.
                        accepted_at = submission.reviewed_at or submission.submitted_at
                    wrong = sum(
                        1
                        for log in logs
                        if log.status == "rejected"
                        and not (log.judge_result or "").startswith("Compilation Error")
                        and (accepted_at is None or log.submitted_at < accepted_at)
                    )
                    pending = any(log.status == "pending" for log in logs)
                    cell = {"solved": accepted_at is not None, "wrong": wrong, "pending": pending, "minutes": None}
                    if accepted_at is not None:
                        minutes = max(0, int((accepted_at - attempt.started_at).total_seconds() // 60))
                        cell["minutes"] = minutes
                        solved += 1
                        penalty += minutes + ICPC_WRONG_PENALTY_MINUTES * wrong
                        last_accept = max(last_accept or accepted_at, accepted_at)
                    cells.append(cell)
                rows.append({
                    "attempt": attempt,
                    "student": attempt.student,
                    "cells": cells,
                    "solved": solved,
                    "penalty": penalty,
                    "finished": attempt.completed_at is not None or now >= attempt_deadline(attempt),
                    "sort_key": (-solved, penalty, last_accept or datetime.max),
                })
        else:
            for attempt in attempts:
                finished = attempt.completed_at is not None
                used = (
                    int((attempt.completed_at - attempt.started_at).total_seconds() // 60) if finished else None
                )
                rows.append({
                    "attempt": attempt,
                    "student": attempt.student,
                    "cells": [],
                    "solved": attempt.correct_count if finished else None,
                    "penalty": used,
                    "finished": finished,
                    # Davom etayotganlar ro'yxat oxirida.
                    "sort_key": (0, -(attempt.correct_count or 0), used) if finished else (1, 0, 0),
                })
        rows.sort(key=lambda row: (row["sort_key"], row["student"].full_name))
        previous_key, rank = None, 0
        for position, row in enumerate(rows, start=1):
            ranked = row["solved"] is not None
            if ranked and row["sort_key"] != previous_key:
                rank, previous_key = position, row["sort_key"]
            row["rank"] = rank if ranked else None
        return rows

    def render_leaderboard(contest, viewer_student_id=None):
        return render_template(
            "leaderboard.html",
            contest=contest,
            rows=build_leaderboard(contest),
            state=contest_state(contest),
            viewer_student_id=viewer_student_id,
            wrong_penalty=ICPC_WRONG_PENALTY_MINUTES,
        )

    @application.route("/admin/contests/<int:contest_id>/leaderboard")
    @admin_required
    def admin_leaderboard(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        finalize_expired_attempts()
        return render_leaderboard(contest)

    @application.route("/admin/contests/<int:contest_id>/leaderboard.xlsx")
    @admin_required
    def export_leaderboard(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        finalize_expired_attempts()
        rows = build_leaderboard(contest)
        coding = contest.contest_type == "coding"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Reyting"
        header = ["O‘rin", "HEMIS ID", "F.I.O", "Guruh"]
        if coding:
            header += [f"Masala {index}" for index in range(1, len(contest.questions) + 1)]
            header += ["Yechilgan", "Jarima (daqiqa)"]
        else:
            header += ["To‘g‘ri javob", "Jami savol", "Sarflangan vaqt (daqiqa)"]
        header.append("Holat")
        sheet.append(header)
        for row in rows:
            line = [row["rank"] or "—", row["student"].hemis_id, row["student"].full_name, row["student"].group_name]
            if coding:
                for cell in row["cells"]:
                    if cell["solved"]:
                        line.append(f"+{cell['wrong'] or ''} ({cell['minutes']})")
                    else:
                        line.append(f"-{cell['wrong']}" if cell["wrong"] else "")
                line += [row["solved"], row["penalty"]]
            else:
                line += [
                    row["solved"] if row["solved"] is not None else "",
                    row["attempt"].total_questions,
                    row["penalty"] if row["penalty"] is not None else "",
                ]
            line.append("Yakunlangan" if row["finished"] else "Davom etmoqda")
            sheet.append(line)
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"reyting_kontest_{contest.id}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @application.route("/contest/<int:contest_id>/leaderboard")
    @student_required
    def student_leaderboard(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None or not contest.public_leaderboard:
            abort(404)
        student_id = session["student_id"]
        if not contest.is_active and get_attempt(student_id, contest_id) is None:
            abort(404)
        finalize_expired_attempts()
        return render_leaderboard(contest, viewer_student_id=student_id)

    @application.route("/admin/results")
    @admin_required
    def admin_results():
        finalize_expired_attempts()
        attempts = (
            Attempt.query.filter(Attempt.completed_at.is_not(None))
            .join(Attempt.student)
            .join(Attempt.contest)
            .order_by(Attempt.completed_at.desc())
            .all()
        )
        return render_template("results.html", attempts=attempts)

    @application.route("/admin/results.xlsx")
    @admin_required
    def export_results():
        finalize_expired_attempts()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Natijalar"
        sheet.append(["HEMIS ID", "F.I.O", "Guruh", "Kontest", "To‘g‘ri javob", "Jami savol", "Ball (%)", "Yakunlagan vaqt"])
        attempts = (
            Attempt.query.filter(Attempt.completed_at.is_not(None))
            .join(Attempt.student)
            .join(Attempt.contest)
            .order_by(Attempt.completed_at.desc())
            .all()
        )
        for attempt in attempts:
            sheet.append(
                [
                    attempt.student.hemis_id,
                    attempt.student.full_name,
                    attempt.student.group_name,
                    attempt.contest.title,
                    attempt.correct_count,
                    attempt.total_questions,
                    attempt.score,
                    format_local(attempt.completed_at, "%Y-%m-%d %H:%M:%S"),
                ]
            )
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="olimpiada_natijalari.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @application.route("/student")
    @student_required
    def student_dashboard():
        student_id = session["student_id"]
        finalize_expired_attempts(student_id)
        attempts = {attempt.contest_id: attempt for attempt in Attempt.query.filter_by(student_id=student_id).all()}
        all_contests = Contest.query.order_by(Contest.id.desc()).all()
        contests = [contest for contest in all_contests if contest.is_active or contest.id in attempts]
        return render_template("student_dashboard.html", student=db.session.get(Student, student_id), contests=contests, attempts=attempts)

    def seb_ok(contest, allow_session=False):
        """Kontest SEB talab qilsa, so'rov SEB'dan kelganini tekshiradi.

        Sahifa so'rovlarida SEB sarlavhasi tekshiriladi va sessiyaga belgi qo'yiladi;
        fon (fetch) so'rovlarida esa shu belgi yetarli (allow_session=True).
        """
        if not contest.require_seb:
            return True
        flag = f"seb_ok_{contest.id}"
        if proctoring.verify_seb_request(request.url, request.headers):
            session[flag] = True
            return True
        return allow_session and session.get(flag) is True

    def seb_required_response(contest, attempt=None):
        if attempt is not None and attempt.completed_at is None:
            record_proctor_event(attempt, "seb_missing", request.headers.get("User-Agent", "")[:300])
            enforce_violation_limit(attempt)
            db.session.commit()
        return render_template(
            "seb_required.html",
            contest=contest,
            seb_link=os.environ.get("SEB_START_LINK", ""),
        ), 403

    def proctor_state(attempt, create=True):
        state = db.session.get(ProctorState, attempt.id)
        if state is None and create:
            state = ProctorState(attempt_id=attempt.id, focus_lost_count=0, paste_count=0, face_alert_count=0)
            db.session.add(state)
        return state

    def record_proctor_event(attempt, kind, detail=None, image=None):
        """Hodisani yozadi; bir xil hodisa EVENT_COOLDOWN_SECONDS ichida takrorlanmaydi."""
        since = utcnow() - timedelta(seconds=proctoring.EVENT_COOLDOWN_SECONDS)
        recent = ProctorEvent.query.filter(
            ProctorEvent.attempt_id == attempt.id,
            ProctorEvent.kind == kind,
            ProctorEvent.created_at >= since,
        ).first()
        if recent is not None:
            return None
        event = ProctorEvent(attempt_id=attempt.id, kind=kind, detail=(detail or "")[:300] or None, image=image)
        db.session.add(event)
        return event

    def violation_count(attempt):
        return ProctorEvent.query.filter(
            ProctorEvent.attempt_id == attempt.id,
            ProctorEvent.kind.in_(proctoring.VIOLATION_KINDS),
        ).count()

    def enforce_violation_limit(attempt):
        """Limitdan oshsa urinishni yakunlaydi (javoblar/qabul qilingan yechimlar baholanadi)."""
        limit = attempt.contest.max_violations or 0
        if not limit or attempt.completed_at is not None:
            return False
        count = violation_count(attempt)
        if count < limit:
            return False
        db.session.add(
            ProctorEvent(attempt_id=attempt.id, kind="auto_finished", detail=f"{count} ta qoidabuzarlik (limit {limit})")
        )
        score_attempt(attempt, json.loads(attempt.answers_json or "{}"), commit=False)
        return True

    def violation_payload(attempt, finished):
        return {
            "violations": violation_count(attempt),
            "max_violations": attempt.contest.max_violations or 0,
            "finished": finished,
        }

    def camera_is_live(attempt):
        state = proctor_state(attempt, create=False)
        return (
            state is not None
            and state.last_seen_at is not None
            and (utcnow() - state.last_seen_at).total_seconds() <= proctoring.FRAME_STALE_SECONDS
        )

    def screen_is_live(attempt):
        state = proctor_state(attempt, create=False)
        return (
            state is not None
            and state.last_screen_at is not None
            and (utcnow() - state.last_screen_at).total_seconds() <= proctoring.FRAME_STALE_SECONDS
        )

    def monitoring_problem(contest, attempt):
        """Kuzatuv talablari bajarilmasa, talabaga ko'rsatiladigan sabab (aks holda None)."""
        if contest.proctoring and not camera_is_live(attempt):
            return "Kamera ishlamayapti: kamerani yoqing va sahifani yangilang."
        if contest.screen_capture and not screen_is_live(attempt):
            return "Ekran ulashilmayapti: butun ekraningizni ulashing va sahifani yangilang."
        return None

    def store_live_code(contest, state):
        if not contest.has_coding:
            return
        code = request.form.get("code")
        if code is not None:
            state.last_code = code[:20000]
            state.last_language = request.form.get("language", "")[:10] or None
            question_id = request.form.get("question_id", "")
            state.last_question_id = int(question_id) if question_id.isdigit() else None

    def open_proctored_attempt(contest_id, allow_lockdown=False):
        """Proktoring endpointlari uchun: faol, SEB tekshiruvidan o'tgan urinish."""
        contest = db.session.get(Contest, contest_id)
        if contest is None or not (contest.monitored or (allow_lockdown and contest.lockdown)):
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if attempt is None or attempt.completed_at is not None or utcnow() >= attempt_deadline(attempt):
            abort(409)
        if not seb_ok(contest, allow_session=True):
            abort(403)
        return contest, attempt

    def shuffled_question_order(contest):
        """Output testida har bir talabaga savollar boshqa tartibda (yonidagidan ko'chirish qiyinlashadi)."""
        if not contest.has_quiz:
            return None
        ids = [question.id for question in contest.quiz_questions]
        secrets.SystemRandom().shuffle(ids)
        return json.dumps(ids)

    def ordered_questions(contest, attempt):
        questions = list(contest.questions)
        try:
            order = json.loads(attempt.question_order or "[]")
        except json.JSONDecodeError:
            order = []
        position = {question_id: index for index, question_id in enumerate(order)}
        return sorted(questions, key=lambda question: position.get(question.id, len(position) + question.id))

    @application.route("/contest/<int:contest_id>/proctor/frame", methods=["POST"])
    @student_required
    def proctor_frame(contest_id):
        contest, attempt = open_proctored_attempt(contest_id)
        if not contest.proctoring:
            abort(404)
        uploaded = request.files.get("frame")
        image = uploaded.read(proctoring.MAX_FRAME_BYTES + 1) if uploaded else b""
        if not image or len(image) > proctoring.MAX_FRAME_BYTES or not proctoring.is_jpeg(image):
            abort(400)
        faces = proctoring.detect_faces(image)
        state = proctor_state(attempt)
        state.last_seen_at = utcnow()
        state.last_image = image
        state.last_faces = faces
        store_live_code(contest, state)
        alert = None
        if faces == 0:
            alert = "no_face"
        elif faces is not None and faces > 1:
            alert = "multiple_faces"
        if alert and record_proctor_event(attempt, alert, f"Yuzlar soni: {faces}", image) is not None:
            state.face_alert_count = (state.face_alert_count or 0) + 1
        finished = enforce_violation_limit(attempt)
        payload = violation_payload(attempt, finished)
        db.session.commit()
        return jsonify({"ok": True, "faces": faces, "interval": proctoring.FRAME_INTERVAL_SECONDS, **payload})

    @application.route("/contest/<int:contest_id>/proctor/screen", methods=["POST"])
    @student_required
    def proctor_screen(contest_id):
        contest, attempt = open_proctored_attempt(contest_id)
        if not contest.screen_capture:
            abort(404)
        uploaded = request.files.get("screen")
        image = uploaded.read(proctoring.MAX_SCREEN_BYTES + 1) if uploaded else b""
        if not image or len(image) > proctoring.MAX_SCREEN_BYTES or not proctoring.is_jpeg(image):
            abort(400)
        state = proctor_state(attempt)
        state.last_screen = image
        state.last_screen_at = utcnow()
        store_live_code(contest, state)
        if request.form.get("reason") in {"window_blur", "tab_hidden"}:
            # Talaba oynadan chiqqanda olingan ekran rasmi shu hodisaga dalil sifatida biriktiriladi.
            event = (
                ProctorEvent.query.filter(
                    ProctorEvent.attempt_id == attempt.id,
                    ProctorEvent.kind.in_(("window_blur", "tab_hidden")),
                    ProctorEvent.image.is_(None),
                    ProctorEvent.created_at >= utcnow() - timedelta(seconds=60),
                )
                .order_by(ProctorEvent.id.desc())
                .first()
            )
            if event is not None:
                event.image = image
        finished = enforce_violation_limit(attempt)
        payload = violation_payload(attempt, finished)
        db.session.commit()
        return jsonify({"ok": True, "interval": proctoring.FRAME_INTERVAL_SECONDS, **payload})

    @application.route("/contest/<int:contest_id>/proctor/event", methods=["POST"])
    @student_required
    def proctor_client_event(contest_id):
        _, attempt = open_proctored_attempt(contest_id, allow_lockdown=True)
        payload = request.get_json(silent=True) or {}
        kind = payload.get("kind")
        if kind not in proctoring.CLIENT_EVENT_KINDS:
            abort(400)
        state = proctor_state(attempt)
        if kind in {"tab_hidden", "window_blur", "fullscreen_exit"}:
            state.focus_lost_count = (state.focus_lost_count or 0) + 1
        elif kind == "paste":
            state.paste_count = (state.paste_count or 0) + 1
        record_proctor_event(attempt, kind, str(payload.get("detail", ""))[:300])
        finished = enforce_violation_limit(attempt)
        result = violation_payload(attempt, finished)
        db.session.commit()
        return jsonify({"ok": True, **result})

    def purge_old_proctor_data():
        days = int(os.environ.get("PROCTOR_RETENTION_DAYS", "30"))
        cutoff = utcnow() - timedelta(days=days)
        ProctorEvent.query.filter(ProctorEvent.created_at < cutoff).delete(synchronize_session=False)
        ProctorState.query.filter(ProctorState.last_seen_at < cutoff).delete(synchronize_session=False)
        db.session.commit()

    def proctor_rows(contest):
        attempts = Attempt.query.filter_by(contest_id=contest.id).join(Attempt.student).all()
        states = {
            state.attempt_id: state
            for state in ProctorState.query.filter(
                ProctorState.attempt_id.in_([attempt.id for attempt in attempts] or [0])
            )
        }
        event_counts = dict(
            db.session.query(ProctorEvent.attempt_id, db.func.count(ProctorEvent.id))
            .filter(ProctorEvent.attempt_id.in_([attempt.id for attempt in attempts] or [0]))
            .group_by(ProctorEvent.attempt_id)
            .all()
        )
        violation_counts = dict(
            db.session.query(ProctorEvent.attempt_id, db.func.count(ProctorEvent.id))
            .filter(
                ProctorEvent.attempt_id.in_([attempt.id for attempt in attempts] or [0]),
                ProctorEvent.kind.in_(proctoring.VIOLATION_KINDS),
            )
            .group_by(ProctorEvent.attempt_id)
            .all()
        )
        now = utcnow()
        rows = []
        for attempt in sorted(attempts, key=lambda item: item.student.full_name):
            state = states.get(attempt.id)
            seen = state.last_seen_at if state else None
            active = attempt.completed_at is None and now < attempt_deadline(attempt)
            camera_live = bool(seen and (now - seen).total_seconds() <= proctoring.FRAME_STALE_SECONDS)
            screen_seen = state.last_screen_at if state else None
            screen_live = bool(screen_seen and (now - screen_seen).total_seconds() <= proctoring.FRAME_STALE_SECONDS)
            live = (camera_live or not contest.proctoring) and (screen_live or not contest.screen_capture)
            rows.append({
                "attempt_id": attempt.id,
                "name": attempt.student.full_name,
                "hemis_id": attempt.student.hemis_id,
                "group": attempt.student.group_name,
                "active": active,
                "live": live,
                "seen_ago": int((now - seen).total_seconds()) if seen else None,
                "faces": state.last_faces if state else None,
                "has_image": bool(state and state.last_image),
                "camera_live": camera_live,
                "screen_live": screen_live,
                "has_screen": bool(state and state.last_screen),
                "screen_version": int(screen_seen.timestamp()) if screen_seen else 0,
                "screen_ago": int((now - screen_seen).total_seconds()) if screen_seen else None,
                "frame_version": int(seen.timestamp()) if seen else 0,
                "code": (state.last_code or "") if state else "",
                "language": (state.last_language or "") if state else "",
                "focus_lost": state.focus_lost_count if state else 0,
                "paste": state.paste_count if state else 0,
                "face_alerts": state.face_alert_count if state else 0,
                "events": event_counts.get(attempt.id, 0),
                "violations": violation_counts.get(attempt.id, 0),
                "max_violations": contest.max_violations or 0,
                # Ustoz e'tibori kerak bo'lganlar yuqorida.
                "alert": active and (not live or (state is not None and state.last_faces not in (1, None))),
            })
        rows.sort(key=lambda row: (not row["alert"], not row["active"], row["name"]))
        return rows

    @application.route("/admin/contests/<int:contest_id>/proctor")
    @admin_required
    def admin_proctor(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        purge_old_proctor_data()
        return render_template(
            "proctor.html",
            contest=contest,
            rows=proctor_rows(contest),
            stale_seconds=proctoring.FRAME_STALE_SECONDS,
        )

    @application.route("/admin/contests/<int:contest_id>/proctor.json")
    @admin_required
    def admin_proctor_json(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        return jsonify({"rows": proctor_rows(contest)})

    @application.route("/admin/proctor/<int:attempt_id>/frame.jpg")
    @admin_required
    def admin_proctor_frame(attempt_id):
        state = db.session.get(ProctorState, attempt_id)
        if state is None or not state.last_image:
            abort(404)
        response = send_file(io.BytesIO(state.last_image), mimetype="image/jpeg")
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.route("/admin/proctor/<int:attempt_id>/screen.jpg")
    @admin_required
    def admin_proctor_screen(attempt_id):
        state = db.session.get(ProctorState, attempt_id)
        if state is None or not state.last_screen:
            abort(404)
        response = send_file(io.BytesIO(state.last_screen), mimetype="image/jpeg")
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.route("/admin/proctor/event/<int:event_id>.jpg")
    @admin_required
    def admin_proctor_event_image(event_id):
        event = db.session.get(ProctorEvent, event_id)
        if event is None or not event.image:
            abort(404)
        return send_file(io.BytesIO(event.image), mimetype="image/jpeg")

    @application.route("/admin/proctor/<int:attempt_id>")
    @admin_required
    def admin_proctor_attempt(attempt_id):
        attempt = db.session.get(Attempt, attempt_id)
        if attempt is None:
            abort(404)
        events = (
            ProctorEvent.query.filter_by(attempt_id=attempt.id).order_by(ProctorEvent.created_at.desc()).limit(300).all()
        )
        return render_template(
            "proctor_attempt.html",
            attempt=attempt,
            state=db.session.get(ProctorState, attempt.id),
            events=events,
            labels=proctoring.EVENT_LABELS,
        )

    @application.route("/admin/contests/<int:contest_id>/proctor/clear", methods=["POST"])
    @admin_required
    def clear_proctor_data(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        attempt_ids = db.select(Attempt.id).where(Attempt.contest_id == contest.id)
        ProctorEvent.query.filter(ProctorEvent.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        ProctorState.query.filter(ProctorState.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        db.session.commit()
        flash("Kontestning barcha kamera kadrlari va kuzatuv hodisalari o‘chirildi.", "success")
        return redirect(url_for("admin_proctor", contest_id=contest.id))

    @application.route("/contest/<int:contest_id>", methods=["GET", "POST"])
    @student_required
    def take_contest(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        student_id = session["student_id"]
        attempt = get_attempt(student_id, contest_id)
        if not (attempt and attempt.completed_at) and not seb_ok(contest):
            return seb_required_response(contest, attempt)
        if attempt and attempt.completed_at:
            return redirect(url_for("student_result", attempt_id=attempt.id))
        if not attempt:
            state = contest_state(contest)
            if state != "open":
                messages = {
                    "closed": "Bu kontest hozir faol emas.",
                    "upcoming": f"Kontest {format_local(contest.start_at)} da boshlanadi.",
                    "finished": "Kontest vaqti tugagan.",
                }
                flash(messages[state], "warning")
                return redirect(url_for("student_dashboard"))
            attempt = Attempt(
                student_id=student_id,
                contest_id=contest.id,
                total_questions=len(contest.questions),
                answers_json="{}",
                question_order=shuffled_question_order(contest),
            )
            db.session.add(attempt)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                attempt = get_attempt(student_id, contest_id)
                if attempt is None:
                    raise
        deadline = attempt_deadline(attempt)
        now = utcnow()
        saved_answers = json.loads(attempt.answers_json or "{}")
        if contest.contest_type == "mixed" and attempt.coding_done_at is None:
            # Aralash kontest: avval kod bo'limi. Hammasi qabul qilinsa, test bloki o'zi ochiladi.
            accepted = {
                submission.question_id
                for submission in CodeSubmission.query.filter_by(attempt_id=attempt.id, status="accepted")
            }
            if all(question.id in accepted for question in contest.coding_questions):
                attempt.coding_done_at = now
                db.session.commit()
                flash("Barcha kod masalalari qabul qilindi. Endi test bloki ochildi.", "success")
        if contest.contest_type == "coding" or (contest.contest_type == "mixed" and attempt.coding_done_at is None):
            questions = contest.coding_questions
            submissions = {
                submission.question_id: submission
                for submission in CodeSubmission.query.filter_by(attempt_id=attempt.id).all()
            }
            current_question = next(
                (question for question in questions
                 if question.id not in submissions or submissions[question.id].status != "accepted"),
                None,
            )
            if current_question is None and contest.contest_type == "coding":
                score_attempt(attempt, saved_answers)
                return redirect(url_for("student_result", attempt_id=attempt.id))
            remaining_seconds = max(0, int((deadline - now).total_seconds()))
            if remaining_seconds == 0:
                flash("Kontest vaqti tugadi. Qabul qilingan masalalaringiz natijaga qo‘shildi.", "warning")
                score_attempt(attempt, saved_answers)
                return redirect(url_for("student_result", attempt_id=attempt.id))
            return render_template(
                "take_coding.html",
                contest=contest,
                attempt=attempt,
                question=current_question,
                question_number=questions.index(current_question) + 1,
                total_questions=len(questions),
                submission=submissions.get(current_question.id),
                history=submissions[current_question.id].history[:10] if current_question.id in submissions else [],
                remaining_seconds=remaining_seconds,
            )
        if request.method == "POST":
            if now < deadline:
                submitted = {}
                for question in contest.quiz_questions:
                    key = str(question.id)
                    submitted[key] = request.form.get(key, "").strip()
                saved_answers.update(submitted)
            score_attempt(attempt, saved_answers)
            return redirect(url_for("student_result", attempt_id=attempt.id))
        remaining_seconds = max(0, int((deadline - now).total_seconds()))
        if remaining_seconds == 0:
            score_attempt(attempt, saved_answers)
            return redirect(url_for("student_result", attempt_id=attempt.id))
        return render_template(
            "take_contest.html",
            contest=contest,
            attempt=attempt,
            questions=[question for question in ordered_questions(contest, attempt)
                       if question.question_type != "code_problem"],
            answers=saved_answers,
            remaining_seconds=remaining_seconds,
        )

    @application.route("/contest/<int:contest_id>/finish-coding", methods=["POST"])
    @student_required
    def finish_coding(contest_id):
        """Aralash kontest: talaba kod bo'limini yakunlab, test blokiga o'tadi (qaytib bo'lmaydi)."""
        contest = db.session.get(Contest, contest_id)
        if contest is None or contest.contest_type != "mixed":
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if not attempt or attempt.completed_at:
            abort(409)
        if attempt.coding_done_at is None:
            attempt.coding_done_at = utcnow()
            db.session.commit()
            flash("Kod bo‘limi yakunlandi. Qabul qilingan masalalaringiz natijaga qo‘shiladi. Endi test bloki.", "info")
        return redirect(url_for("take_contest", contest_id=contest_id))

    run_times = {}
    run_lock = threading.Lock()

    @application.route("/contest/<int:contest_id>/run/<int:question_id>", methods=["POST"])
    @student_required
    def run_code(contest_id, question_id):
        """Konsol: kodni talaba kiritgan input bilan ishga tushiradi. Baholanmaydi."""
        contest = db.session.get(Contest, contest_id)
        question = db.session.get(Question, question_id)
        if (
            contest is None or question is None or not contest.has_coding
            or question.question_type != "code_problem" or question not in contest.questions
        ):
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if not attempt or attempt.completed_at or utcnow() >= attempt_deadline(attempt):
            return jsonify(error="Kontest vaqti tugagan.", finished=True), 409
        if attempt.coding_done_at is not None:
            return jsonify(error="Kod bo‘limi yakunlangan.", finished=True), 409
        if not seb_ok(contest):
            return jsonify(error="Kontest faqat Safe Exam Browser orqali ishlaydi."), 403
        data = request.get_json(silent=True) or {}
        language = data.get("language")
        source_code = data.get("source_code") or ""
        stdin_text = data.get("stdin") or ""
        if language not in {"python", "cpp"} or not isinstance(source_code, str) or not isinstance(stdin_text, str):
            abort(400)
        if not source_code.strip():
            return jsonify(error="Avval kod yozing."), 400
        cooldown = application.config["RUN_COOLDOWN_SECONDS"]
        now = time.monotonic()
        with run_lock:
            last = run_times.get(attempt.id)
            if cooldown and last and now - last < cooldown:
                return jsonify(error=f"Juda tez. {cooldown - (now - last):.0f} soniyadan so‘ng qayta ishga tushiring."), 429
            run_times[attempt.id] = now
        attempt_id = attempt.id
        db.session.remove()  # dastur ishlayotganda baza ulanishini band qilib turmaymiz
        try:
            result = run_program(language, source_code, stdin_text.replace("\r\n", "\n"))
        except JudgeError as error:
            with run_lock:
                run_times.pop(attempt_id, None)
            return jsonify(error=str(error)), 503
        return jsonify(result)

    @application.route("/contest/<int:contest_id>/code/<int:question_id>", methods=["POST"])
    @student_required
    def submit_code(contest_id, question_id):
        contest = db.session.get(Contest, contest_id)
        question = db.session.get(Question, question_id)
        if (
            contest is None or question is None or not contest.has_coding
            or question.question_type != "code_problem" or question not in contest.questions
        ):
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if not attempt or attempt.completed_at:
            abort(409)
        if attempt.coding_done_at is not None:
            flash("Kod bo‘limi yakunlangan, endi test bloki ochiq.", "warning")
            return redirect(url_for("take_contest", contest_id=contest_id))
        if utcnow() >= attempt_deadline(attempt):
            flash("Kontest vaqti tugagan.", "warning")
            return redirect(url_for("take_contest", contest_id=contest_id))
        if not seb_ok(contest):
            return seb_required_response(contest, attempt)
        problem = monitoring_problem(contest, attempt)
        if problem:
            flash(problem, "danger")
            return redirect(url_for("take_contest", contest_id=contest_id))
        submissions = {
            submission.question_id: submission
            for submission in CodeSubmission.query.filter_by(attempt_id=attempt.id).all()
        }
        current_question = next(
            (item for item in contest.coding_questions
             if item.id not in submissions or submissions[item.id].status != "accepted"),
            None,
        )
        if current_question is None or current_question.id != question.id:
            abort(409)
        source_code = request.form.get("source_code", "").strip()
        language = request.form.get("language", "")
        if language not in {"python", "cpp"}:
            abort(400)
        if not source_code or len(source_code) > 20000:
            flash("Kodingizni kiriting (ko‘pi bilan 20 000 belgi).", "danger")
            return redirect(url_for("take_contest", contest_id=contest_id))
        cooldown = application.config["SUBMIT_COOLDOWN_SECONDS"]
        last_submitted = db.session.execute(
            db.select(db.func.max(SubmissionLog.submitted_at))
            .join(CodeSubmission, SubmissionLog.submission_id == CodeSubmission.id)
            .where(CodeSubmission.attempt_id == attempt.id)
        ).scalar()
        if cooldown and last_submitted and (utcnow() - last_submitted).total_seconds() < cooldown:
            wait = int(cooldown - (utcnow() - last_submitted).total_seconds()) + 1
            flash(f"Yechimlar orasida kamida {cooldown} soniya bo‘lishi kerak. {wait} soniyadan so‘ng yuboring.", "warning")
            return redirect(url_for("take_contest", contest_id=contest_id))
        submission = submissions.get(question.id)
        if (
            submission
            and submission.status == "pending"
            and submission.submitted_at is not None
            and (utcnow() - submission.submitted_at).total_seconds() < PENDING_RESUBMIT_SECONDS
        ):
            # Tekshiruv hali ketmoqda. 3 daqiqadan eski "pending" — uzilib qolgan
            # tekshiruv deb hisoblanadi va talaba qayta yuborishi mumkin.
            flash("Oldingi yechimingiz hali tekshirilmoqda. Biroz kuting.", "warning")
            return redirect(url_for("take_contest", contest_id=contest_id))
        now = utcnow()
        if submission is None:
            submission = CodeSubmission(attempt_id=attempt.id, question_id=question.id)
            db.session.add(submission)
        submission.language = language
        submission.source_code = source_code
        submission.status = "pending"
        submission.submitted_at = now
        submission.reviewed_at = None
        submission.reviewer_note = None
        submission.judge_result = "Yechim navbatda, tekshirilmoqda…"
        log_entry = SubmissionLog(
            submission=submission,
            language=language,
            source_code=source_code,
            status="pending",
            judge_result=submission.judge_result,
            submitted_at=now,
        )
        db.session.add(log_entry)
        db.session.commit()
        job = (submission.id, log_entry.id, language, source_code, question.test_cases_json)
        if application.config["JUDGE_SYNC"]:
            run_judge_job(*job)
        else:
            # Tekshiruv fon oqimida: veb-so'rov darhol qaytadi, sahifa natijani o'zi yangilaydi.
            judge_pool.submit(run_judge_job, *job)
        flash("Yechim qabul qilindi va tekshiruv navbatiga qo‘yildi.", "info")
        return redirect(url_for("take_contest", contest_id=contest_id))

    def run_judge_job(submission_id, log_id, language, source_code, test_cases_json):
        """Yechimni tekshiradi va natijani tarixga hamda joriy holatga yozadi."""
        with application.app_context():
            try:
                try:
                    test_cases = json.loads(test_cases_json or "[]")
                    accepted, result_message = judge_solution(language, source_code, test_cases)
                    status = "accepted" if accepted else "rejected"
                except JudgeError as error:
                    result_message, status = str(error), "error"
                except json.JSONDecodeError:
                    result_message, status = "Masala testlari JSON formati noto‘g‘ri.", "error"
                except Exception:
                    application.logger.exception("Ichki judge kutilmagan xatolik berdi")
                    result_message, status = "Tekshiruv serverida ichki xatolik yuz berdi.", "error"
                result_message = result_message[:500]
                now = utcnow()
                log_entry = db.session.get(SubmissionLog, log_id)
                if log_entry is not None:
                    log_entry.status = status
                    log_entry.judge_result = result_message
                    log_entry.judged_at = now
                latest_log_id = db.session.execute(
                    db.select(db.func.max(SubmissionLog.id)).where(SubmissionLog.submission_id == submission_id)
                ).scalar()
                submission = db.session.get(CodeSubmission, submission_id)
                # Joriy holatni faqat eng so'nggi yuborilgan yechim natijasi yangilaydi.
                if submission is not None and latest_log_id == log_id and submission.status != "accepted":
                    submission.status = status
                    submission.judge_result = result_message
                    submission.reviewed_at = now
                db.session.commit()
            except Exception:
                db.session.rollback()
                application.logger.exception("Tekshiruv natijasini saqlab bo‘lmadi")
            finally:
                db.session.remove()

    @application.route("/contest/<int:contest_id>/save", methods=["POST"])
    @student_required
    def save_answer(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if not attempt or attempt.completed_at:
            abort(409)
        if utcnow() >= attempt_deadline(attempt):
            return jsonify({"saved": False, "expired": True}), 409
        if not seb_ok(contest, allow_session=True):
            return jsonify({"saved": False, "seb": False}), 403
        if monitoring_problem(contest, attempt):
            return jsonify({"saved": False, "camera": False}), 409
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        question_id = payload.get("question_id")
        valid_question_ids = {str(question.id) for question in contest.questions}
        if not isinstance(question_id, (int, str)) or str(question_id) not in valid_question_ids:
            abort(400)
        answers = json.loads(attempt.answers_json or "{}")
        answer = payload.get("answer", "")
        answers[str(question_id)] = str(answer).strip()
        attempt.answers_json = json.dumps(answers, ensure_ascii=False)
        db.session.commit()
        return jsonify({"saved": True})

    @application.route("/result/<int:attempt_id>")
    @student_required
    def student_result(attempt_id):
        attempt = db.session.get(Attempt, attempt_id)
        if attempt is None or attempt.student_id != session["student_id"]:
            abort(404)
        if attempt.completed_at is None:
            return redirect(url_for("take_contest", contest_id=attempt.contest_id))
        percentage = round(attempt.correct_count * 100 / attempt.total_questions, 2) if attempt.total_questions else 0
        return render_template("result.html", attempt=attempt, percentage=percentage)

    with application.app_context():
        db.create_all()
        question_columns = {
            column["name"] for column in db.inspect(db.engine).get_columns("questions")
        }
        if "code_snippet" not in question_columns:
            db.session.execute(db.text("ALTER TABLE questions ADD COLUMN code_snippet TEXT"))
            db.session.commit()
        if "test_cases_json" not in question_columns:
            db.session.execute(db.text("ALTER TABLE questions ADD COLUMN test_cases_json TEXT"))
            db.session.commit()
        contest_columns = {column["name"] for column in db.inspect(db.engine).get_columns("contests")}
        if "contest_type" not in contest_columns:
            db.session.execute(
                db.text("ALTER TABLE contests ADD COLUMN contest_type VARCHAR(20) NOT NULL DEFAULT 'quiz'")
            )
            db.session.commit()
        submission_columns = {
            column["name"] for column in db.inspect(db.engine).get_columns("code_submission")
        }
        if "language" not in submission_columns:
            db.session.execute(
                db.text("ALTER TABLE code_submission ADD COLUMN language VARCHAR(10) NOT NULL DEFAULT 'python'")
            )
            db.session.commit()
        if "judge_result" not in submission_columns:
            db.session.execute(db.text("ALTER TABLE code_submission ADD COLUMN judge_result VARCHAR(500)"))
            db.session.commit()
        student_columns = {column["name"] for column in db.inspect(db.engine).get_columns("students")}
        for name, ddl in (
            ("start_at", "TIMESTAMP"),
            ("end_at", "TIMESTAMP"),
            ("public_leaderboard", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("proctoring", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("require_seb", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("screen_capture", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("lockdown", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("max_violations", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in contest_columns:
                db.session.execute(db.text(f"ALTER TABLE contests ADD COLUMN {name} {ddl}"))
                db.session.commit()
        if "session_token" not in student_columns:
            db.session.execute(db.text("ALTER TABLE students ADD COLUMN session_token VARCHAR(64)"))
            db.session.commit()
        attempt_columns = {column["name"] for column in db.inspect(db.engine).get_columns("attempts")}
        if "coding_done_at" not in attempt_columns:
            db.session.execute(db.text("ALTER TABLE attempts ADD COLUMN coding_done_at TIMESTAMP"))
            db.session.commit()
        if "question_order" not in attempt_columns:
            db.session.execute(db.text("ALTER TABLE attempts ADD COLUMN question_order TEXT"))
            db.session.commit()
        if db.inspect(db.engine).has_table("proctor_state"):
            state_columns = {column["name"] for column in db.inspect(db.engine).get_columns("proctor_state")}
            blob = "BYTEA" if db.engine.dialect.name == "postgresql" else "BLOB"
            for name, ddl in (("last_screen", blob), ("last_screen_at", "TIMESTAMP")):
                if name not in state_columns:
                    db.session.execute(db.text(f"ALTER TABLE proctor_state ADD COLUMN {name} {ddl}"))
                    db.session.commit()
        if "access_code_hash" not in student_columns:
            db.session.execute(db.text("ALTER TABLE students ADD COLUMN access_code_hash VARCHAR(255)"))
            db.session.commit()

        if Question.query.count() == 0:
            questions_file = os.path.join(application.root_path, "questions_data.json")
            with open(questions_file, encoding="utf-8") as file:
                questions_data = json.load(file)
            if not isinstance(questions_data, list) or not questions_data:
                raise RuntimeError("questions_data.json bo‘sh yoki ro‘yxat formatida emas.")
            if any(not isinstance(question, dict) for question in questions_data):
                raise RuntimeError("questions_data.json ichida noto‘g‘ri savol ma’lumoti bor.")
            db.session.add_all(Question(**question) for question in questions_data)
            db.session.commit()

        import_problem_bank(application)

    return application


def import_problem_bank(application):
    """problem_bank.json dagi olimpiada masalalarini bazaga bir marta qo'shadi."""
    bank_file = os.path.join(application.root_path, "problem_bank.json")
    if not os.path.exists(bank_file):
        return
    with open(bank_file, encoding="utf-8") as file:
        bank = json.load(file)
    done = set(db.session.execute(db.select(BankImport.key)).scalars())
    added = 0
    for item in bank:
        if item["key"] in done:
            continue
        db.session.add(Question(
            question_type="code_problem",
            prompt=item["prompt"],
            input_data=item["input_data"],
            expected_output=item["expected_output"],
            test_cases_json=json.dumps(item["test_cases"], ensure_ascii=False),
        ))
        db.session.add(BankImport(key=item["key"]))
        added += 1
    if added:
        try:
            db.session.commit()
            application.logger.info("Olimpiada bankidan %s ta masala qo'shildi.", added)
        except IntegrityError:
            # Bir nechta jarayon bir vaqtda ishga tushsa, boshqasi allaqachon qo'shgan.
            db.session.rollback()


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
