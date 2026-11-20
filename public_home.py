"""Bosh sahifa (statistika, yaqin musobaqalar, top ishtirokchilar) va yangiliklar."""
import math
from datetime import timedelta

from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from i18n import _
from models import ContestRegistration, NewsPost, PublicContest, Submission, User, db, utcnow
from public import archive_problems
from public_users import solved_counts
from rating import ensure_ratings

ONLINE_MINUTES = 15
SEEN_UPDATE_SECONDS = 300
NEWS_PER_PAGE = 10


def register_home(application, helpers):
    current_user = helpers["current_user"]
    admin_required = helpers["admin_required"]
    hidden_question_ids = helpers["hidden_question_ids"]
    to_local = helpers["to_local"]

    @application.before_request
    def track_last_seen():
        """«Onlayn» statistikasi uchun: foydalanuvchi faolligini 5 daqiqada bir marta yozamiz."""
        if not isinstance(session.get("user_id"), int) or request.endpoint in (None, "static"):
            return
        user = current_user()
        now = utcnow()
        if user is not None and (user.last_seen_at is None
                                 or (now - user.last_seen_at).total_seconds() > SEEN_UPDATE_SECONDS):
            user.last_seen_at = now
            db.session.commit()

    def community_stats():
        now = utcnow()
        # Mahalliy (Toshkent) kun boshi — UTC'da.
        local_now = to_local(now)
        day_start = now - (local_now - local_now.replace(hour=0, minute=0, second=0, microsecond=0))
        hidden = hidden_question_ids()
        return {
            "users": User.query.count(),
            "users_week": User.query.filter(User.created_at >= now - timedelta(days=7)).count(),
            "problems": sum(1 for question in archive_problems() if question.id not in hidden),
            "attempts_day": Submission.query.filter(Submission.created_at >= now - timedelta(hours=24)).count(),
            "solved_today": db.session.execute(
                db.select(func.count()).select_from(
                    db.select(Submission.user_id, Submission.question_id)
                    .where(Submission.status == "accepted", Submission.created_at >= day_start)
                    .distinct()
                    .subquery()
                )
            ).scalar() or 0,
            "contests": sum(
                1 for contest in PublicContest.query.filter(PublicContest.is_published.is_(True)).all()
                if contest.end_at <= now
            ),
            "online": User.query.filter(User.last_seen_at >= now - timedelta(minutes=ONLINE_MINUTES)).count(),
        }

    @application.route("/")
    def index():
        if session.get("is_admin"):
            return redirect(url_for("admin_dashboard"))
        if session.get("student_id"):
            return redirect(url_for("student_dashboard"))
        ensure_ratings()
        now = utcnow()
        soon = [
            contest
            for contest in PublicContest.query.filter(PublicContest.is_published.is_(True))
            .order_by(PublicContest.start_at).all()
            if contest.end_at > now
        ][:3]
        counts = dict(db.session.execute(
            db.select(ContestRegistration.contest_id, func.count()).group_by(ContestRegistration.contest_id)
        ).all())
        top = User.query.filter(User.rating.isnot(None)).order_by(User.rating.desc(), User.full_name).limit(5).all()
        top_by = "rating"
        if not top:
            solved = solved_counts()
            top = sorted((user for user in User.query.all() if solved.get(user.id)),
                         key=lambda user: -solved[user.id])[:5]
            top_by = "solved"
        else:
            solved = {}
        news = (
            NewsPost.query.filter(NewsPost.is_published.is_(True))
            .order_by(NewsPost.created_at.desc()).limit(4).all()
        )
        return render_template(
            "public/home.html",
            stats=community_stats(),
            soon=soon,
            counts=counts,
            top=top,
            top_by=top_by,
            solved=solved,
            news=news,
        )

    # ---------------- Yangiliklar ----------------

    @application.route("/news")
    def news_list():
        query = NewsPost.query.filter(NewsPost.is_published.is_(True))
        tag = request.args.get("tag", "").strip().lstrip("#")[:40]
        if tag:
            query = query.filter(NewsPost.tags.ilike(f"%{tag}%"))
        posts = query.order_by(NewsPost.created_at.desc()).all()
        if tag:
            posts = [post for post in posts if tag.casefold() in (item.casefold() for item in post.tag_list)]
        pages = max(1, math.ceil(len(posts) / NEWS_PER_PAGE))
        page = min(max(request.args.get("page", 1, type=int), 1), pages)
        return render_template(
            "public/news.html",
            posts=posts[(page - 1) * NEWS_PER_PAGE: page * NEWS_PER_PAGE],
            page=page,
            pages=pages,
            tag=tag,
        )

    @application.route("/news/<int:post_id>")
    def news_post(post_id):
        post = db.session.get(NewsPost, post_id)
        if post is None or (not post.is_published and not session.get("is_admin")):
            abort(404)
        return render_template("public/news_post.html", post=post)

    def save_post(post, form):
        title = " ".join(form.get("title", "").split())[:200]
        body = (form.get("body") or "").strip()[:20000]
        if not title or not body:
            return [_("Sarlavha va matnni kiriting.")]
        post.title = title
        post.body = body
        post.tags = ", ".join(
            tag.strip().lstrip("#") for tag in (form.get("tags") or "").split(",") if tag.strip().lstrip("#")
        )[:200] or None
        post.is_published = bool(form.get("is_published"))
        post.author = " ".join(form.get("author", "").split())[:120] or None
        if post.id is None:
            db.session.add(post)
        db.session.commit()
        return []

    @application.route("/admin/news", methods=["GET", "POST"])
    @admin_required
    def admin_news():
        form = {"is_published": True}
        status = 200
        if request.method == "POST":
            errors = save_post(NewsPost(), request.form)
            if not errors:
                flash(_("Yangilik e’lon qilindi."), "success")
                return redirect(url_for("admin_news"))
            for error in errors:
                flash(error, "danger")
            form, status = request.form, 400
        posts = NewsPost.query.order_by(NewsPost.created_at.desc()).all()
        return render_template("admin_news.html", posts=posts, post=None, form=form), status

    @application.route("/admin/news/<int:post_id>", methods=["GET", "POST"])
    @admin_required
    def admin_news_edit(post_id):
        post = db.session.get(NewsPost, post_id)
        if post is None:
            abort(404)
        form = {"title": post.title, "body": post.body, "tags": post.tags or "", "author": post.author or "",
                "is_published": post.is_published}
        status = 200
        if request.method == "POST":
            errors = save_post(post, request.form)
            if not errors:
                flash(_("O‘zgarishlar saqlandi."), "success")
                return redirect(url_for("admin_news_edit", post_id=post.id))
            for error in errors:
                flash(error, "danger")
            form, status = request.form, 400
        return render_template("admin_news.html", posts=None, post=post, form=form), status

    @application.route("/admin/news/<int:post_id>/delete", methods=["POST"])
    @admin_required
    def admin_news_delete(post_id):
        post = db.session.get(NewsPost, post_id)
        if post is None:
            abort(404)
        db.session.delete(post)
        db.session.commit()
        flash(_("Yangilik o‘chirildi."), "success")
        return redirect(url_for("admin_news"))
