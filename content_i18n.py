"""Savol va masala matnlarining tarjimasi.

Bank savollari (masalalar, output testlari, nazariy testlar) uchun tarjimalar
translations/content/ru.json va en.json fayllarida; kalit — o'zbekcha matnning o'zi
("[NB-001] " kabi bank belgisi olib tashlangan holda). Tarjima topilmasa — asl matn.
Ustoz qo'shgan yangi savollar o'zi yozilgan tilda ko'rsatiladi.
"""
import json
import os
import re

from i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language

_PREFIX = re.compile(r"^(\[(?:NB|OB)-\d+\]\s*)")
_catalogs = {}


def load(root):
    for lang in LANGUAGES:
        if lang == DEFAULT_LANGUAGE:
            continue
        path = os.path.join(root, "translations", "content", f"{lang}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                _catalogs[lang] = json.load(file)


def translate(text, keep_prefix=True):
    """Savol matnini joriy tilga o'giradi; bank belgisi ([NB-001]) saqlanadi."""
    if not text:
        return text
    match = _PREFIX.match(text)
    prefix, body = (match.group(1), text[match.end():]) if match else ("", text)
    translated = _catalogs.get(current_language(), {}).get(body.strip()) or body
    return (prefix if keep_prefix else "") + translated


def init_app(application):
    load(application.root_path)
    application.jinja_env.filters["content"] = translate
