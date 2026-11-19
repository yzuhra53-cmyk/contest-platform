from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


contest_questions = db.Table(
    "contest_questions",
    db.Column("contest_id", db.Integer, db.ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True),
    db.Column("question_id", db.Integer, db.ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True),
)


class Student(db.Model):
    __tablename__ = "students"

    hemis_id = db.Column(db.String(40), primary_key=True)
    full_name = db.Column(db.String(180), nullable=False)
    group_name = db.Column(db.String(100), nullable=False)
    # Shaxsiy kirish kodi xeshi (ochiq kod bazada saqlanmaydi).
    access_code_hash = db.Column(db.String(255))
    # Oxirgi kirish tokeni: yangi qurilmadan kirilsa, eski sessiya bekor bo'ladi.
    session_token = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    attempts = db.relationship("Attempt", back_populates="student")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    question_type = db.Column(db.String(20), nullable=False, default="test")
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)
    correct_option = db.Column(db.String(1))
    code_snippet = db.Column(db.Text)
    input_data = db.Column(db.Text)
    expected_output = db.Column(db.Text)
    test_cases_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    contests = db.relationship("Contest", secondary=contest_questions, back_populates="questions")
    code_submissions = db.relationship("CodeSubmission", back_populates="question")


class Contest(db.Model):
    __tablename__ = "contests"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    contest_type = db.Column(db.String(20), nullable=False, default="quiz")
    # Ixtiyoriy vaqt oynasi (UTC). start_at gacha boshlab bo'lmaydi; end_at da
    # barcha urinishlar yakunlanadi (shaxsiy taymer qolgan bo'lsa ham).
    start_at = db.Column(db.DateTime)
    end_at = db.Column(db.DateTime)
    public_leaderboard = db.Column(db.Boolean, nullable=False, default=False)
    # Kamera snapshotlari + kod kuzatuvi + oyna/tab nazorati.
    proctoring = db.Column(db.Boolean, nullable=False, default=False)
    # Faqat Safe Exam Browser orqali kirishga ruxsat.
    require_seb = db.Column(db.Boolean, nullable=False, default=False)
    # Ekran kuzatuvi: talaba butun ekranini ulashadi, ustoz ekran rasmlarini ko'radi.
    screen_capture = db.Column(db.Boolean, nullable=False, default=False)
    # Qulflangan rejim: to'liq ekran majburiy, sahifadan chiqish va ko'p tugmalar bloklanadi.
    lockdown = db.Column(db.Boolean, nullable=False, default=False)
    # Shuncha qoidabuzarlikdan keyin urinish avtomatik yakunlanadi (0 — o'chiq).
    max_violations = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    questions = db.relationship(
        "Question",
        secondary=contest_questions,
        back_populates="contests",
        order_by="Question.id",
    )
    attempts = db.relationship("Attempt", back_populates="contest")

    @property
    def has_coding(self):
        return self.contest_type in ("coding", "mixed")

    @property
    def has_quiz(self):
        return self.contest_type in ("quiz", "mixed")

    @property
    def coding_questions(self):
        return [question for question in self.questions if question.question_type == "code_problem"]

    @property
    def quiz_questions(self):
        return [question for question in self.questions if question.question_type != "code_problem"]

    @property
    def type_label(self):
        return {"coding": "Kod yozish", "mixed": "Kod + test"}.get(self.contest_type, "Output testi")

    @property
    def monitored(self):
        """Kamera yoki ekran kuzatuvi yoqilgan."""
        return bool(self.proctoring or self.screen_capture)


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(40), db.ForeignKey("students.hemis_id"), nullable=False)
    contest_id = db.Column(db.Integer, db.ForeignKey("contests.id"), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)
    answers_json = db.Column(db.Text, nullable=False, default="{}")
    # Talabaga ko'rsatiladigan savollar tartibi (aralashtirilgan id ro'yxati, JSON).
    question_order = db.Column(db.Text)
    # Aralash kontest: kod bo'limi yakunlangan vaqt (shundan keyin test bloki ochiladi).
    coding_done_at = db.Column(db.DateTime)
    correct_count = db.Column(db.Integer)
    total_questions = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float)

    student = db.relationship("Student", back_populates="attempts")
    contest = db.relationship("Contest", back_populates="attempts")
    code_submissions = db.relationship("CodeSubmission", back_populates="attempt")

    __table_args__ = (
        db.UniqueConstraint("student_id", "contest_id", name="uq_attempt_student_contest"),
    )


class CodeSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    language = db.Column(db.String(10), nullable=False, default="python")
    source_code = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    judge_result = db.Column(db.String(500))
    submitted_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewer_note = db.Column(db.String(500))

    attempt = db.relationship("Attempt", back_populates="code_submissions")
    question = db.relationship("Question", back_populates="code_submissions")
    history = db.relationship(
        "SubmissionLog",
        back_populates="submission",
        order_by="SubmissionLog.id.desc()",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("attempt_id", "question_id", name="uq_submission_attempt_question"),
    )


class ProctorState(db.Model):
    """Urinishning joriy kuzatuv holati: oxirgi kadr, oxirgi kod va hisoblagichlar.

    Joy tejash uchun har bir urinishda faqat oxirgi kadr saqlanadi; shubhali
    kadrlar alohida ProctorEvent sifatida qoladi.
    """

    __tablename__ = "proctor_state"

    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id", ondelete="CASCADE"), primary_key=True)
    last_seen_at = db.Column(db.DateTime)
    last_image = db.Column(db.LargeBinary)
    last_faces = db.Column(db.Integer)
    last_screen = db.Column(db.LargeBinary)
    last_screen_at = db.Column(db.DateTime)
    last_code = db.Column(db.Text)
    last_language = db.Column(db.String(10))
    last_question_id = db.Column(db.Integer)
    focus_lost_count = db.Column(db.Integer, nullable=False, default=0)
    paste_count = db.Column(db.Integer, nullable=False, default=0)
    face_alert_count = db.Column(db.Integer, nullable=False, default=0)

    attempt = db.relationship("Attempt")


class ProctorEvent(db.Model):
    __tablename__ = "proctor_event"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    # no_face, multiple_faces, tab_hidden, window_blur, paste, camera_denied, camera_lost, seb_missing
    kind = db.Column(db.String(30), nullable=False)
    detail = db.Column(db.String(300))
    image = db.Column(db.LargeBinary)

    attempt = db.relationship("Attempt")


class BankImport(db.Model):
    """problem_bank.json dan qaysi masalalar bir marta qo'shilganini eslab qoladi.

    Ustoz bank masalasini o'chirsa, keyingi ishga tushishda u qayta qo'shilmaydi.
    """

    __tablename__ = "bank_import"

    key = db.Column(db.String(20), primary_key=True)
    imported_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class SubmissionLog(db.Model):
    """Har bir yuborilgan yechimning o'zgarmas nusxasi (yechimlar tarixi)."""

    __tablename__ = "submission_log"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer, db.ForeignKey("code_submission.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language = db.Column(db.String(10), nullable=False)
    source_code = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    judge_result = db.Column(db.String(500))
    submitted_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    judged_at = db.Column(db.DateTime)

    submission = db.relationship("CodeSubmission", back_populates="history")
