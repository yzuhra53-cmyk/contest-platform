"""Interfeys tili: o'zbekcha (asosiy), ruscha, inglizcha.

Matnlar kodda o'zbekcha yoziladi va `_()` bilan o'raladi; tarjimalar
translations/ru.json va translations/en.json fayllarida (kalit — o'zbekcha matn).
Tarjima topilmasa, o'zbekcha matn ko'rsatiladi.

    _("Kontest yaratildi.")
    _("Fayldan %(count)s ta savol qo‘shildi.", count=added)

Modul darajasidagi lug'atlar (masalan, hodisa nomlari) `N_()` bilan belgilanadi —
u matnni o'zgartirmaydi, faqat tarjima ro'yxatiga tushishi uchun; ko'rsatishda `_()`.
"""
import json
import os

from flask import g, has_request_context, redirect, request, session, url_for

LANGUAGES = {"uz": "O‘zbekcha", "ru": "Русский", "en": "English"}
SHORT_NAMES = {"uz": "UZ", "ru": "RU", "en": "EN"}
DEFAULT_LANGUAGE = "uz"
COOKIE_NAME = "lang"

_catalogs = {}


def load_catalogs(root):
    for lang in LANGUAGES:
        if lang == DEFAULT_LANGUAGE:
            continue
        path = os.path.join(root, "translations", f"{lang}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                _catalogs[lang] = {key: value for key, value in json.load(file).items() if value}


def current_language():
    if has_request_context():
        return getattr(g, "lang", DEFAULT_LANGUAGE)
    return DEFAULT_LANGUAGE


def gettext(text, **values):
    if not text:
        return text
    translated = _catalogs.get(current_language(), {}).get(text, text)
    if values:
        try:
            return translated % values
        except (KeyError, ValueError, TypeError):
            return text % values
    return translated


def N_(text):  # noqa: N802 — tarjima uchun belgi
    return text


_ = gettext

# static/js fayllaridagi matnlar: sahifaga window.I18N sifatida beriladi, JS'da t('...') bilan o'qiladi.
JS_MESSAGES = [
    # static/js/ide.js
    N_("Bajarildi"),
    N_("Kompilyatsiya xatosi"),
    N_("Runtime Error"),
    N_("Vaqt limiti oshdi"),
    N_("Chiqish juda katta"),
    N_("Qator %(line)s, ustun %(col)s"),
    N_("Joriy kod shablon bilan almashtirilsinmi?"),
    N_("Avval kod yozing."),
    N_("Ishlamoqda…"),
    N_("Dastur ishga tushirilmoqda…"),
    N_("Server xatosi (%(status)s)."),
    N_("chiqish qisqartirildi"),
    N_("(dastur hech narsa chiqarmadi)"),
    N_("Namuna javobiga mos keldi"),
    N_("Namuna javobidan farq qiladi"),
    N_("Server bilan aloqa uzildi. Qayta urinib ko‘ring."),
    N_("Ishga tushirish"),
    # static/js/task.js va templates/public/task.html
    N_("Kutilmoqda"),
    N_("Server xatosi"),
    N_("Nusxa"),
]


def js_translations():
    if current_language() == DEFAULT_LANGUAGE:
        return {}
    return {text: gettext(text) for text in JS_MESSAGES}


def _pick_language():
    chosen = request.args.get("lang")
    if chosen in LANGUAGES:
        session["lang"] = chosen
        return chosen
    for candidate in (session.get("lang"), request.cookies.get(COOKIE_NAME)):
        if candidate in LANGUAGES:
            return candidate
    # Til tanlanmagan bo'lsa — o'zbekcha (lotin). Brauzer tiliga qarab avtomatik almashtirilmaydi.
    return DEFAULT_LANGUAGE


def init_app(application):
    load_catalogs(application.root_path)

    @application.before_request
    def select_language():
        g.lang = _pick_language()

    @application.after_request
    def remember_language(response):
        lang = getattr(g, "lang", None)
        if lang and request.cookies.get(COOKIE_NAME) != lang:
            response.set_cookie(COOKIE_NAME, lang, max_age=365 * 24 * 3600, samesite="Lax",
                                secure=request.is_secure, httponly=True)
        return response

    @application.route("/lang/<code>")
    def set_language(code):
        if code in LANGUAGES:
            session["lang"] = code
            g.lang = code
        target = request.referrer or ""
        host = request.host_url
        if not target.startswith(host):
            target = url_for("index")
        return redirect(target)

    application.jinja_env.globals.update(
        _=gettext, gettext=gettext, current_language=current_language,
        LANGUAGES=LANGUAGES, LANGUAGE_SHORT=SHORT_NAMES, js_translations=js_translations,
    )
