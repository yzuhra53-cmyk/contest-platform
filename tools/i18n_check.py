"""Tarjimalarni tekshirish: kod va shablonlardagi barcha `_()` / `N_()` matnlari
translations/ru.json va translations/en.json fayllarida bormi.

    python tools/i18n_check.py            # yetishmayotgan va ortiqcha kalitlar
    python tools/i18n_check.py --stubs    # yetishmayotganlarni bo'sh qiymat bilan qo'shadi
    python tools/i18n_check.py --prune    # endi ishlatilmaydigan kalitlarni o'chiradi

Xatolik bo'lsa 1 bilan chiqadi (testlarda ishlatiladi).
"""
import ast
import json
import os
import re
import sys

from jinja2 import Environment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ("ru", "en")
FUNCS = {"_", "N_", "gettext"}
PY_FILES = [name for name in os.listdir(ROOT) if name.endswith(".py")]


def python_messages(path):
    with open(path, encoding="utf-8") as file:
        tree = ast.parse(file.read(), path)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FUNCS
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            yield node.lineno, node.args[0].value


def template_messages(env, path):
    with open(path, encoding="utf-8") as file:
        source = file.read()
    for lineno, func, message in env.extract_translations(source, gettext_functions=("_", "gettext", "N_")):
        if isinstance(message, str):
            yield lineno, message


def collect():
    env = Environment(extensions=["jinja2.ext.i18n"])
    found = {}
    for name in PY_FILES:
        for lineno, message in python_messages(os.path.join(ROOT, name)):
            found.setdefault(message, f"{name}:{lineno}")
    templates = os.path.join(ROOT, "templates")
    for name in sorted(os.listdir(templates)):
        if name.endswith(".html"):
            for lineno, message in template_messages(env, os.path.join(templates, name)):
                found.setdefault(message, f"templates/{name}:{lineno}")
    return found


def load(lang):
    path = os.path.join(ROOT, "translations", f"{lang}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def save(lang, data):
    path = os.path.join(ROOT, "translations", f"{lang}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(dict(sorted(data.items())), file, ensure_ascii=False, indent=1)
        file.write("\n")


def placeholders(text):
    return sorted(re.findall(r"%\((\w+)\)s", text))


def main():
    found = collect()
    problems = 0
    for lang in LANGS:
        data = load(lang)
        missing = [key for key in found if not data.get(key)]
        unused = [key for key in data if key not in found]
        broken = [key for key, value in data.items() if value and key in found and placeholders(key) != placeholders(value)]
        if "--stubs" in sys.argv:
            for key in missing:
                data.setdefault(key, "")
        if "--prune" in sys.argv:
            for key in unused:
                data.pop(key)
        if "--stubs" in sys.argv or "--prune" in sys.argv:
            save(lang, data)
        print(f"[{lang}] matnlar: {len(found)}, tarjima yo'q: {len(missing)}, ortiqcha: {len(unused)}, "
              f"o'rinbosar xatosi: {len(broken)}")
        for key in missing[:40]:
            print(f"   - {found[key]}: {key[:90]!r}")
        for key in broken:
            print(f"   ! {found[key]}: {key[:90]!r}")
        problems += len(missing) + len(broken)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
