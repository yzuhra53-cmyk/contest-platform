import hmac
import io
import json
import os
import re
import secrets
import csv
import unicodedata
from itertools import chain
from datetime import datetime
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
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile

from dotenv import load_dotenv

load_dotenv()

from models import Attempt, CodeSubmission, Contest, Question, Student, db, utcnow
from judge import JudgeError, judge_solution


def create_app(test_config=None):
    application = Flask(__name__)
    database_url = os.environ.get("DATABASE_URL", "sqlite:///contest.db")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    secret_key = os.environ.get("SECRET_KEY")
    if os.environ.get("RENDER") and not secret_key:
        raise RuntimeError("Render deploy uchun SECRET_KEY environment variable belgilang.")
    application.config.update(
        SECRET_KEY=secret_key or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "Zuhra"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "1211"),
        DEBUG=not bool(os.environ.get("RENDER")) and os.environ.get("FLASK_DEBUG", "").lower() == "true",
        TRUSTED_HOSTS=[os.environ["RENDER_EXTERNAL_HOSTNAME"]]
        if os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        else None,
    )
    if test_config:
        application.config.update(test_config)
    db.init_app(application)

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
            if db.session.get(Student, session["student_id"]) is None:
                session.clear()
                flash("Talaba hisobi topilmadi. Qayta kiring.", "warning")
                return redirect(url_for("student_login"))
            return view(*args, **kwargs)

        return wrapped

    def normalize_output(value):
        return "\n".join(line.rstrip() for line in (value or "").replace("\r\n", "\n").split("\n")).strip()

    def score_attempt(attempt, answers):
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
        attempt.completed_at = utcnow()
        db.session.commit()

    def get_attempt(student_id, contest_id):
        return Attempt.query.filter_by(student_id=student_id, contest_id=contest_id).first()

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
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            valid_user = hmac.compare_digest(username, application.config["ADMIN_USERNAME"])
            valid_password = hmac.compare_digest(password, application.config["ADMIN_PASSWORD"])
            if valid_user and valid_password:
                session.clear()
                session["is_admin"] = True
                return redirect(url_for("admin_dashboard"))
            flash("Login yoki parol noto‘g‘ri.", "danger")
        return render_template("admin_login.html")

    @application.route("/login", methods=["GET", "POST"])
    def student_login():
        if request.method == "POST":
            hemis_id = request.form.get("hemis_id", "").strip()
            full_name = " ".join(request.form.get("full_name", "").split())
            group_name = " ".join(request.form.get("group_name", "").split())
            student = db.session.get(Student, hemis_id)

            def normalize_name(value):
                value = unicodedata.normalize("NFKC", value).casefold()
                value = value.translate(str.maketrans({
                    "\u2018": "'", "\u2019": "'", "\u02bb": "'", "\u02bc": "'",
                    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
                    "\u2014": "-", "\u2212": "-",
                }))
                return " ".join(value.replace(".", "").split())

            def normalize_group(value):
                value = unicodedata.normalize("NFKC", value).casefold()
                value = value.translate(str.maketrans({
                    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
                    "\u2014": "-", "\u2212": "-",
                }))
                return re.sub(r"\s*-\s*", "-", " ".join(value.split()))

            if (
                student
                and normalize_name(student.full_name) == normalize_name(full_name)
                and normalize_group(student.group_name) == normalize_group(group_name)
            ):
                session.clear()
                session["student_id"] = student.hemis_id
                return redirect(url_for("student_dashboard"))
            flash("Ma’lumotlar bazadagi talaba ma’lumotlariga mos kelmadi. Ustoz bilan bog‘laning.", "danger")
        return render_template("student_login.html")

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
                flash("Talaba muvaffaqiyatli qo‘shildi.", "success")
            return redirect(url_for("admin_students"))
        students = Student.query.order_by(Student.full_name).all()
        return render_template("students.html", students=students)

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
            for row in chain(data_rows):
                values = [row[position] if position < len(row) else None for position in (id_col, name_col, group_col)]
                hemis_id, full_name, group_name = [str(value).strip() if value is not None else "" for value in values]
                if not all((hemis_id, full_name, group_name)) or db.session.get(Student, hemis_id):
                    skipped += 1
                    continue
                db.session.add(Student(hemis_id=hemis_id, full_name=full_name, group_name=group_name))
                added += 1
            db.session.commit()
            flash(f"{added} ta talaba qo‘shildi, {skipped} ta qator o‘tkazib yuborildi.", "success")
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
            allowed_type = "code_output" if contest_type == "quiz" else "code_problem"
            selected_ids = request.form.getlist("question_ids")
            selected = [int(value) for value in selected_ids if value.isdigit()]
            questions = (
                Question.query.filter(
                    Question.id.in_(selected),
                    Question.question_type == allowed_type,
                ).order_by(Question.id.asc()).all()
                if selected
                else []
            )
            if contest_type not in {"quiz", "coding"} or not title or not 1 <= duration <= 600 or not questions:
                flash("Kontest turi, nomi, 1–600 daqiqalik vaqt va shu turga mos kamida bitta masala kerak.", "danger")
            else:
                contest = Contest(
                    title=title,
                    duration_minutes=duration,
                    is_active=False if start_as_teacher else request.form.get("is_active") == "on",
                    contest_type=contest_type,
                    questions=questions,
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
            contests=Contest.query.order_by(Contest.id.desc()).all(),
            quiz_questions=Question.query.filter_by(question_type="code_output").order_by(Question.id.desc()).all(),
            coding_questions=Question.query.filter_by(question_type="code_problem").order_by(Question.id.desc()).all(),
        )

    @application.route("/admin/contests/<int:contest_id>/preview", methods=["GET", "POST"])
    @admin_required
    def admin_preview_contest(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        score = None
        if request.method == "POST":
            if contest.contest_type != "quiz":
                abort(400)
            correct = sum(
                request.form.get(str(question.id), "").upper() == question.correct_option
                for question in contest.questions
            )
            total = len(contest.questions)
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
            CodeSubmission.query.filter(CodeSubmission.attempt_id.in_(attempt_ids)).delete(
                synchronize_session=False
            )
            Attempt.query.filter(Attempt.id.in_(attempt_ids)).delete(synchronize_session=False)
        db.session.delete(contest)
        db.session.commit()
        flash("Kontest, urinishlari va yuborilgan kodlari butunlay o‘chirildi. Savollar bazada saqlandi.", "success")
        return redirect(url_for("admin_contests"))

    @application.route("/admin/results")
    @admin_required
    def admin_results():
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
                    attempt.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
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
        attempts = {attempt.contest_id: attempt for attempt in Attempt.query.filter_by(student_id=student_id).all()}
        all_contests = Contest.query.order_by(Contest.id.desc()).all()
        contests = [contest for contest in all_contests if contest.is_active or contest.id in attempts]
        return render_template("student_dashboard.html", student=db.session.get(Student, student_id), contests=contests, attempts=attempts)

    @application.route("/contest/<int:contest_id>", methods=["GET", "POST"])
    @student_required
    def take_contest(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        student_id = session["student_id"]
        attempt = get_attempt(student_id, contest_id)
        if attempt and attempt.completed_at:
            return redirect(url_for("student_result", attempt_id=attempt.id))
        if not attempt:
            if not contest.is_active:
                flash("Bu kontest hozir faol emas.", "warning")
                return redirect(url_for("student_dashboard"))
            attempt = Attempt(
                student_id=student_id,
                contest_id=contest.id,
                total_questions=len(contest.questions),
                answers_json="{}",
            )
            db.session.add(attempt)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                attempt = get_attempt(student_id, contest_id)
                if attempt is None:
                    raise
        deadline = (attempt.started_at - datetime(1970, 1, 1)).total_seconds() + contest.duration_minutes * 60
        now_epoch = (utcnow() - datetime(1970, 1, 1)).total_seconds()
        saved_answers = json.loads(attempt.answers_json or "{}")
        if contest.contest_type == "coding":
            questions = contest.questions
            submissions = {
                submission.question_id: submission
                for submission in CodeSubmission.query.filter_by(attempt_id=attempt.id).all()
            }
            current_question = next(
                (question for question in questions
                 if question.id not in submissions or submissions[question.id].status != "accepted"),
                None,
            )
            if current_question is None:
                score_attempt(attempt, saved_answers)
                return redirect(url_for("student_result", attempt_id=attempt.id))
            remaining_seconds = max(0, int(deadline - now_epoch))
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
                remaining_seconds=remaining_seconds,
            )
        if request.method == "POST":
            if now_epoch < deadline:
                submitted = {}
                for question in contest.questions:
                    key = str(question.id)
                    submitted[key] = request.form.get(key, "").strip()
                saved_answers.update(submitted)
            score_attempt(attempt, saved_answers)
            return redirect(url_for("student_result", attempt_id=attempt.id))
        remaining_seconds = max(0, int(deadline - now_epoch))
        if remaining_seconds == 0:
            score_attempt(attempt, saved_answers)
            return redirect(url_for("student_result", attempt_id=attempt.id))
        return render_template(
            "take_contest.html",
            contest=contest,
            attempt=attempt,
            answers=saved_answers,
            remaining_seconds=remaining_seconds,
        )

    @application.route("/contest/<int:contest_id>/code/<int:question_id>", methods=["POST"])
    @student_required
    def submit_code(contest_id, question_id):
        contest = db.session.get(Contest, contest_id)
        question = db.session.get(Question, question_id)
        if contest is None or question is None or contest.contest_type != "coding" or question not in contest.questions:
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if not attempt or attempt.completed_at:
            abort(409)
        seconds = (utcnow() - attempt.started_at).total_seconds()
        if seconds >= contest.duration_minutes * 60:
            flash("Kontest vaqti tugagan.", "warning")
            return redirect(url_for("take_contest", contest_id=contest_id))
        submissions = {
            submission.question_id: submission
            for submission in CodeSubmission.query.filter_by(attempt_id=attempt.id).all()
        }
        current_question = next(
            (item for item in contest.questions
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
        submission = submissions.get(question.id)
        if (
            submission
            and submission.status == "pending"
            and submission.submitted_at is not None
            and (utcnow() - submission.submitted_at).total_seconds() < 180
        ):
            # Tekshiruv hali ketmoqda. 3 daqiqadan eski "pending" — uzilib qolgan
            # tekshiruv deb hisoblanadi va talaba qayta yuborishi mumkin.
            flash("Oldingi yechimingiz hali tekshirilmoqda. Biroz kuting.", "warning")
            return redirect(url_for("take_contest", contest_id=contest_id))
        if submission is None:
            submission = CodeSubmission(
                attempt_id=attempt.id,
                question_id=question.id,
                language=language,
                source_code=source_code,
                status="pending",
                judge_result="Avtomatik tekshiruv boshlandi.",
            )
            db.session.add(submission)
        else:
            submission.language = language
            submission.source_code = source_code
            submission.status = "pending"
            submission.submitted_at = utcnow()
            submission.reviewed_at = None
            submission.reviewer_note = None
            submission.judge_result = "Avtomatik tekshiruv boshlandi."
        db.session.commit()
        try:
            test_cases = json.loads(question.test_cases_json or "[]")
            # Ichki (local) judge: kod shu serverda, vaqtinchalik papkada ishlaydi.
            accepted, result_message = judge_solution(language, source_code, test_cases)
        except JudgeError as error:
            result_message = str(error)
            submission.status = "error"
        except json.JSONDecodeError:
            result_message = "Masala testlari JSON formati noto‘g‘ri."
            submission.status = "error"
        except Exception:
            application.logger.exception("Ichki judge kutilmagan xatolik berdi")
            result_message = "Tekshiruv serverida ichki xatolik yuz berdi."
            submission.status = "error"
        else:
            submission.status = "accepted" if accepted else "rejected"
        submission.judge_result = result_message[:500]
        submission.reviewed_at = utcnow()
        db.session.commit()
        if submission.status == "accepted":
            flash("Yechim barcha yashirin testlardan o‘tdi. Keyingi masala ochildi.", "success")
        elif submission.status == "error":
            flash(f"Avtomatik tekshiruv ishlamadi: {result_message}", "danger")
        else:
            flash(f"Yechim testdan o‘tmadi: {result_message}", "warning")
        return redirect(url_for("take_contest", contest_id=contest_id))

    @application.route("/contest/<int:contest_id>/save", methods=["POST"])
    @student_required
    def save_answer(contest_id):
        contest = db.session.get(Contest, contest_id)
        if contest is None:
            abort(404)
        attempt = get_attempt(session["student_id"], contest_id)
        if not attempt or attempt.completed_at:
            abort(409)
        seconds = (utcnow() - attempt.started_at).total_seconds()
        if seconds >= contest.duration_minutes * 60:
            return jsonify({"saved": False, "expired": True}), 409
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

    return application


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
