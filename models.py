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
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    questions = db.relationship(
        "Question",
        secondary=contest_questions,
        back_populates="contests",
        order_by="Question.id",
    )
    attempts = db.relationship("Attempt", back_populates="contest")


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(40), db.ForeignKey("students.hemis_id"), nullable=False)
    contest_id = db.Column(db.Integer, db.ForeignKey("contests.id"), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)
    answers_json = db.Column(db.Text, nullable=False, default="{}")
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
