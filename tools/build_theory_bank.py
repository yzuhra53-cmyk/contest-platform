"""Nazariy test savollarini Word (.docx) fayllardan theory_bank.json ga o'giradi.

Fayl tuzilishi: har bir blokda jadval — № | Savol | A. To'g'ri javob | B | C | D.
Jadvaldan oldingi sarlavha (masalan, "1-blok: Kompyuter qurilmasi...") savol blokiga,
jadvallar orasidagi qisqa sarlavhalar mavzuga aylanadi.

Manbada to'g'ri javob doim A ustunida, shuning uchun variantlar har bir savol uchun
aralashtiriladi (tasodif savol kalitidan olinadi — har safar bir xil natija).

Ishga tushirish (loyiha papkasida):
    uv run python tools/build_theory_bank.py "C:/yo'l/1-blok.docx" "C:/yo'l/2-blok.docx" ...
"""

import json
import os
import random
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "theory_bank.json")
BLOCK_RE = re.compile(r"^\s*(\d+)\s*-\s*blok\b[\s:]*(.*)$", re.IGNORECASE)


def text_of(element):
    parts = []
    for node in element.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append(" ")
    return " ".join("".join(parts).split())


def read_docx(path):
    """(blok, mavzu, [qatorlar]) ro'yxatini qaytaradi."""
    with zipfile.ZipFile(path) as archive:
        body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
    block, topic, items = None, None, []
    for child in body:
        if child.tag == W + "p":
            line = text_of(child)
            if not line:
                continue
            match = BLOCK_RE.match(line)
            if match:
                block = f"{match.group(1)}-blok: {match.group(2).strip()}".rstrip(": ")
                topic = None
            else:
                topic = line
        elif child.tag == W + "tbl":
            for row in child.iter(W + "tr"):
                cells = [text_of(cell) for cell in row.iter(W + "tc")]
                if len(cells) < 6 or not cells[0].isdigit():
                    continue  # sarlavha qatori
                items.append((block, topic, cells[:6]))
    return items


def build(paths):
    bank = []
    for path in paths:
        for block, topic, cells in read_docx(path):
            number, prompt, correct, *wrong = cells
            if not block:
                raise SystemExit(f"{path}: blok sarlavhasi topilmadi")
            if not prompt or not correct or not all(wrong):
                raise SystemExit(f"{path}: {number}-savol to'liq emas: {cells}")
            key = f"NB-{int(number):03d}"
            options = [correct, *wrong]
            random.Random(key).shuffle(options)
            letter = "ABCD"[options.index(correct)]
            bank.append({
                "key": key,
                "category": block,
                "topic": topic if topic and topic != block else None,
                "prompt": f"[{key}] {prompt}",
                "options": options,
                "correct": letter,
            })
    bank.sort(key=lambda item: item["key"])
    keys = [item["key"] for item in bank]
    if len(keys) != len(set(keys)):
        raise SystemExit("Savol raqamlari takrorlangan")
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(bank, handle, ensure_ascii=False, indent=1)
    by_block = {}
    for item in bank:
        by_block[item["category"]] = by_block.get(item["category"], 0) + 1
    for name, count in by_block.items():
        print(f"{count:4d}  {name}")
    print(f"Jami {len(bank)} ta savol -> {OUTPUT}")
    print("To'g'ri javob harflari:", {letter: sum(i["correct"] == letter for i in bank) for letter in "ABCD"})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    build(sys.argv[1:])
