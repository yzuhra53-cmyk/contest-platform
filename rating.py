"""Musobaqa reytingi (Elo uslubidagi, Codeforces hisobining soddalashtirilgan varianti).

Har bir tugagan, e'lon qilingan, reytingli musobaqadan keyin:
  1. Ishtirokchilar — kamida bitta yechim yuborganlar (faqat ro'yxatdan o'tganlar hisobga olinmaydi).
     Yangi ishtirokchining boshlang'ich reytingi INITIAL_RATING.
  2. Har bir ishtirokchi uchun kutilgan o'rin (seed) hisoblanadi:
     seed_i = 1 + Σ_j P(j i dan yuqori), P = 1 / (1 + 10^((r_i - r_j) / 400)).
  3. Haqiqiy o'rin (teng natijalarda o'rtacha o'rin) bilan seed'ning geometrik o'rtachasi —
     "maqsad o'rin". Shu o'ringa mos reyting R ikkilik qidiruv bilan topiladi.
  4. O'zgarish = (R - r_i) / 2, so'ng barcha o'zgarishlar yig'indisi taxminan nolga keltiriladi
     (reyting inflyatsiyasi bo'lmasin).

Reyting har doim noldan, xronologik tartibda qayta quriladi: musobaqa tahrirlansa yoki
o'chirilsa ham natija izchil bo'ladi. Foydalanuvchilar soni kichik bo'lgani uchun bu tez.
"""
import math

from sqlalchemy.exc import IntegrityError

from i18n import N_, _
from models import PublicContest, RatingChange, User, db, utcnow

INITIAL_RATING = 1500

# (quyi chegara, kalit, nom) — reyting darajalari (unvonlar).
TIERS = (
    (2400, "legend", N_("Grossmeyster")),
    (2100, "master", N_("Usta")),
    (1900, "candidate", N_("Ustalikka nomzod")),
    (1600, "expert", N_("Ekspert")),
    (1400, "specialist", N_("Mutaxassis")),
    (1200, "pupil", N_("Havaskor")),
    (-10**9, "newbie", N_("Yangi boshlovchi")),
)


def tier(rating):
    """(kalit, tarjima qilingan nom) yoki reyting yo'q bo'lsa (None, None)."""
    if rating is None:
        return None, None
    for floor, key, name in TIERS:
        if rating >= floor:
            return key, _(name)
    return None, None


def _win_probability(rating_a, rating_b):
    """a ning b dan yuqori o'rin olish ehtimoli."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def calculate_deltas(entries):
    """entries: [(key, joriy reyting, o'rin (float))]. Qaytaradi: {key: o'zgarish (int)}."""
    count = len(entries)
    if count < 2:
        return {key: 0 for key, _rating, _place in entries}
    ratings = [rating for _key, rating, _place in entries]

    def seed(rating, skip):
        return 1.0 + sum(_win_probability(other, rating) for index, other in enumerate(ratings) if index != skip)

    deltas = []
    for index, (_key, rating, place) in enumerate(entries):
        target = math.sqrt(seed(rating, index) * place)
        low, high = 1.0, 8000.0
        for _step in range(60):  # seed(R) R oshgani sari kamayadi
            middle = (low + high) / 2
            if seed(middle, index) < target:
                high = middle
            else:
                low = middle
        deltas.append((low - rating) / 2)
    correction = -sum(deltas) / count - 1
    return {key: int(round(delta + correction)) for (key, _r, _p), delta in zip(entries, deltas)}


def _place_value(place):
    """'3' -> 3.0, '1-2' -> 1.5 (teng natijalar uchun o'rtacha o'rin)."""
    if "-" in place:
        first, last = place.split("-", 1)
        return (int(first) + int(last)) / 2
    return float(place)


def rebuild_ratings():
    """Barcha reytingni tugagan reytingli musobaqalardan noldan qayta quradi."""
    from public_contests import compute_standings

    now = utcnow()
    contests = [
        contest
        for contest in PublicContest.query.filter(
            PublicContest.is_rated.is_(True), PublicContest.is_published.is_(True)
        ).all()
        if contest.end_at <= now
    ]
    contests.sort(key=lambda contest: (contest.end_at, contest.id))
    RatingChange.query.delete()
    User.query.update({"rating": None, "max_rating": None})
    db.session.flush()
    ratings, best = {}, {}
    for contest in contests:
        rows, _first = compute_standings(contest)
        rows = [row for row in rows if row["attempted"]]
        # Faqat qatnashganlar orasida o'rinlarni qayta sanaymiz (bo'sh qatorlar o'rinni egallamasin).
        entries = []
        position = 0
        while position < len(rows):
            end = position
            while (end + 1 < len(rows) and rows[end + 1]["solved"] == rows[position]["solved"]
                   and rows[end + 1]["penalty"] == rows[position]["penalty"]):
                end += 1
            label = str(position + 1) if end == position else f"{position + 1}-{end + 1}"
            for index in range(position, end + 1):
                rows[index]["rated_place"] = label
                user_id = rows[index]["user"].id
                entries.append((user_id, ratings.get(user_id, INITIAL_RATING), _place_value(label)))
            position = end + 1
        deltas = calculate_deltas(entries)
        for row in rows:
            user_id = row["user"].id
            old = ratings.get(user_id, INITIAL_RATING)
            new = max(1, old + deltas.get(user_id, 0))
            ratings[user_id] = new
            best[user_id] = max(best.get(user_id, new), new)
            db.session.add(RatingChange(
                user_id=user_id, contest_id=contest.id, place=row["rated_place"],
                solved=row["solved"], old_rating=old, new_rating=new,
            ))
        contest.rating_applied = True
    for user_id, rating in ratings.items():
        user = db.session.get(User, user_id)
        if user is not None:
            user.rating = rating
            user.max_rating = best[user_id]
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def ensure_ratings():
    """Yaqinda tugagan reytingli musobaqa hali hisoblanmagan bo'lsa — reytingni qayta quradi."""
    now = utcnow()
    pending = PublicContest.query.filter(
        PublicContest.is_rated.is_(True),
        PublicContest.is_published.is_(True),
        PublicContest.rating_applied.is_(False),
        PublicContest.start_at <= now,
    ).all()
    if any(contest.end_at <= now for contest in pending):
        rebuild_ratings()
