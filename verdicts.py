"""Tekshiruv (judge) natijalarini ko'rsatishda tarjima qilish.

Natija bazaga o'zbekcha matn sifatida yoziladi (eski yozuvlar ham shunday). Sahifada
ko'rsatishda matn ma'lum shablonlarga solishtiriladi va tanlangan tilga o'giriladi;
tanilmagan qism (kompilyator xabari, stderr) o'zgarishsiz qoladi.
"""
import re

from i18n import N_, gettext as _

# Aniq mos keladigan natijalar (judge.py dagi JudgeError xabarlari ham N_ bilan belgilangan).
EXACT = (
    N_("Yechim navbatda, tekshirilmoqda…"),
    N_("Masala testlari JSON formati noto‘g‘ri."),
    N_("Tekshiruv serverida ichki xatolik yuz berdi."),
)

_DETAILS = (
    (re.compile(r"^Dastur (?P<name>\w+) signali bilan to‘xtadi\.$"), N_("Dastur %(name)s signali bilan to‘xtadi.")),
    (re.compile(r"^Dastur (?P<code>-?\d+) kodi bilan tugadi\.$"), N_("Dastur %(code)s kodi bilan tugadi.")),
)

_PATTERNS = (
    (re.compile(r"^Compilation Error\.\s?(?P<rest>.*)$", re.S), N_("Kompilyatsiya xatosi.")),
    (re.compile(r"^(?P<n>\d+)-test: Time Limit Exceeded \((?P<sec>[\d.]+) soniya\)\.$"),
     N_("%(n)s-test: Time Limit Exceeded (%(sec)s soniya).")),
    (re.compile(r"^(?P<n>\d+)-test: Output Limit Exceeded\.$"), N_("%(n)s-test: Output Limit Exceeded.")),
    (re.compile(r"^(?P<n>\d+)-test: Runtime Error\.\s?(?P<rest>.*)$", re.S), N_("%(n)s-test: Runtime Error.")),
    (re.compile(r"^(?P<n>\d+)-test: javob noto‘g‘ri\.$"), N_("%(n)s-test: javob noto‘g‘ri.")),
    (re.compile(r"^Barcha (?P<total>\d+) ta testdan o‘tdi\.$"), N_("Barcha %(total)s ta testdan o‘tdi.")),
)

STATUS_LABELS = {
    "pending": N_("Tekshirilmoqda"),
    "accepted": N_("Qabul qilindi"),
    "rejected": N_("Rad etildi"),
    "error": N_("Tekshiruv xatosi"),
}


def _detail(text):
    for pattern, template in _DETAILS:
        match = pattern.match(text)
        if match:
            return _(template, **match.groupdict())
    return text


def translate_verdict(text):
    if not text:
        return text
    stripped = text.strip()
    translated = _(stripped)
    if translated != stripped:
        return translated
    for pattern, template in _PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        values = match.groupdict()
        rest = values.pop("rest", None)
        if "Compilation" in pattern.pattern:
            head = "Compilation Error." if _("Kompilyatsiya xatosi.") == "Kompilyatsiya xatosi." else _(template)
        else:
            head = _(template, **values)
        return f"{head} {_detail(rest)}".strip() if rest else head
    return text


_SHORT = (
    (re.compile(r"^(?P<n>\d+)-test: javob noto‘g‘ri\.$"), N_("Noto‘g‘ri javob (test %(n)s)"), "wrong"),
    (re.compile(r"^(?P<n>\d+)-test: Time Limit Exceeded"), N_("Vaqt chegarasi (test %(n)s)"), "wrong"),
    (re.compile(r"^(?P<n>\d+)-test: Runtime Error"), N_("Bajarilish xatosi (test %(n)s)"), "wrong"),
    (re.compile(r"^(?P<n>\d+)-test: Output Limit Exceeded"), N_("Chiqish chegarasi (test %(n)s)"), "wrong"),
    (re.compile(r"^Compilation Error"), N_("Kompilyatsiya xatosi"), "wrong"),
)


def short_verdict(status, text):
    """Urinishlar jadvali uchun qisqa natija: (matn, turi). Turi: ok / wrong / pending / error."""
    if status == "pending":
        return _("Kutilmoqda"), "pending"
    if status == "accepted":
        return _("Qabul qilindi"), "ok"
    if status == "error":
        return _("Tizim xatosi"), "error"
    stripped = (text or "").strip()
    for pattern, template, kind in _SHORT:
        match = pattern.match(stripped)
        if match:
            return _(template, **match.groupdict()), kind
    return _("Rad etildi"), "wrong"


def status_label(status):
    return _(STATUS_LABELS[status]) if status in STATUS_LABELS else status
