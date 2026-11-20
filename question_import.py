"""Test savollarini Word (.docx) yoki Excel (.xlsx) fayldan o'qish.

Qo'llab-quvvatlanadigan jadval ko'rinishi (Word jadvali yoki Excel varag'i):

    № | Savol | A. To'g'ri javob | B. javob | C. javob | D. javob

* To'g'ri javob — birinchi javob ustuni (A). Variantlar bazaga qo'shilganda
  aralashtiriladi, talabalarga to'g'ri javob har xil harfda chiqadi.
* Agar jadvalda "To'g'ri" / "Javob" nomli alohida ustun bo'lsa (ichida A, B, C yoki D),
  to'g'ri javob o'sha harfdan olinadi va variantlar tartibi saqlanadi.
* Word'da jadvaldan oldingi "N-blok: Nomi" sarlavhasi savollar blokiga aylanadi.
  Excel'da ixtiyoriy "Blok" ustuni bo'lishi mumkin, aks holda varaq nomi ishlatiladi.
"""

import io
import random

from difficulty import normalize as normalize_level
from i18n import _
import re
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BLOCK_RE = re.compile(r"^\s*(\d+)\s*-\s*blok\b[\s:]*(.*)$", re.IGNORECASE)
LETTERS = "ABCD"


class ImportFormatError(ValueError):
    """Fayl tuzilishi tushunarsiz."""


def _clean(value):
    return " ".join(str(value if value is not None else "").split())


def _text_of(element):
    parts = []
    for node in element.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append(" ")
    return _clean("".join(parts))


def _header_layout(cells):
    """Sarlavha qatoridan ustunlar joylashuvini aniqlaydi (topilmasa None)."""
    lowered = [cell.lower().replace("ʻ", "'").replace("‘", "'").replace("’", "'") for cell in cells]
    try:
        prompt_index = next(i for i, cell in enumerate(lowered) if cell.startswith("savol") or cell == "question")
    except StopIteration:
        return None
    answer_index = next(
        (i for i, cell in enumerate(lowered) if i > prompt_index + 4 and ("to'g'ri" in cell or "javob" == cell or "correct" in cell)),
        None,
    )
    block_index = next((i for i, cell in enumerate(lowered) if cell in {"blok", "block", "mavzu"}), None)
    level_index = next(
        (i for i, cell in enumerate(lowered) if cell in {"daraja", "qiyinlik", "difficulty", "level", "сложность"}),
        None,
    )
    return {"prompt": prompt_index, "answer": answer_index, "block": block_index, "level": level_index}


def _row_to_question(cells, layout, category):
    start = layout["prompt"]
    if len(cells) < start + 5:
        return None
    prompt = _clean(cells[start])
    options = [_clean(cell) for cell in cells[start + 1:start + 5]]
    if not prompt or not all(options):
        return None
    letter = None
    if layout["answer"] is not None and layout["answer"] < len(cells):
        letter = _clean(cells[layout["answer"]]).upper()[:1]
        if letter not in LETTERS:
            return None
    block = category
    if layout["block"] is not None and layout["block"] < len(cells) and _clean(cells[layout["block"]]):
        block = _clean(cells[layout["block"]])
    level = None
    if layout.get("level") is not None and layout["level"] < len(cells):
        level = normalize_level(_clean(cells[layout["level"]]))
    return {"prompt": prompt, "options": options, "correct": letter, "category": block, "difficulty": level}


def _finalize(items):
    """To'g'ri javobi birinchi ustunda bo'lganlarning variantlarini aralashtiradi."""
    result = []
    for item in items:
        options = list(item["options"])
        if item["correct"] is None:
            correct = options[0]
            random.Random(item["prompt"]).shuffle(options)
            letter = LETTERS[options.index(correct)]
        else:
            letter = item["correct"]
        result.append({"prompt": item["prompt"], "options": options, "correct": letter, "category": item["category"],
                       "difficulty": item.get("difficulty")})
    return result


def parse_docx(data, default_category=None):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as error:
        raise ImportFormatError(_("Word faylini o‘qib bo‘lmadi (.docx bo‘lishi kerak).")) from error
    category, items = default_category, []
    for child in body:
        if child.tag == W + "p":
            match = BLOCK_RE.match(_text_of(child))
            if match:
                category = f"{match.group(1)}-blok: {match.group(2).strip()}".rstrip(": ")
        elif child.tag == W + "tbl":
            layout = None
            for row in child.iter(W + "tr"):
                cells = [_text_of(cell) for cell in row.iter(W + "tc")]
                header = _header_layout(cells)
                if header:
                    layout = header
                    continue
                # Sarlavhasiz jadval: № | Savol | A | B | C | D deb qabul qilinadi.
                question = _row_to_question(cells, layout or {"prompt": 1, "answer": None, "block": None}, category)
                if question:
                    items.append(question)
    return _finalize(items)


def parse_xlsx(data, default_category=None):
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as error:  # noqa: BLE001 — openpyxl turli xatolar beradi
        raise ImportFormatError(_("Excel faylini o‘qib bo‘lmadi (.xlsx bo‘lishi kerak).")) from error
    items = []
    for sheet in workbook.worksheets:
        layout = None
        for row in sheet.iter_rows(values_only=True):
            cells = [_clean(value) for value in row]
            if not any(cells):
                continue
            header = _header_layout(cells)
            if header:
                layout = header
                continue
            if layout is None:
                # Sarlavhasiz: birinchi ustun raqam bo'lsa № | Savol | A..D, aks holda Savol | A..D.
                layout = {"prompt": 1 if cells[0].isdigit() else 0, "answer": None, "block": None}
            question = _row_to_question(cells, layout, default_category or sheet.title)
            if question:
                items.append(question)
    return _finalize(items)


def parse_file(filename, data, default_category=None):
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return parse_docx(data, default_category)
    if name.endswith(".xlsx"):
        return parse_xlsx(data, default_category)
    raise ImportFormatError(_("Faqat .docx (Word) yoki .xlsx (Excel) fayl yuklang."))
