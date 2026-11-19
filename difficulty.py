"""Savollar qiyinlik darajasi: oson / o'rta / qiyin.

Daraja savol yaratilganda yoki fayldan yuklanganda beriladi. Darajasi yo'q eski
savollar ishga tushishda bir marta avtomatik baholanadi:
  * masala shartida "Daraja: Oson/O‘rta/Qiyin" yozilgan bo'lsa — o'sha;
  * nazariy bank (NB-xxx) — qo'lda belgilangan ro'yxat;
  * kod savollari — kodning murakkabligi (sikllar, ichma-ich sikl, funksiya, rekursiya...);
  * masalalar — mavzusi (dinamik dasturlash, graflar va h.k.).
Ustoz istalgan savol darajasini bankda o'zgartira oladi.
"""
import re

from i18n import N_

LEVELS = ("easy", "medium", "hard")
LEVEL_LABELS = {"easy": N_("Oson"), "medium": N_("O‘rta"), "hard": N_("Qiyin")}

_LABEL_WORDS = {
    "oson": "easy", "easy": "easy", "легкий": "easy", "лёгкий": "easy", "легко": "easy",
    "o'rta": "medium", "orta": "medium", "medium": "medium", "средний": "medium",
    "qiyin": "hard", "hard": "hard", "сложный": "hard",
}

# Nazariy bank: qo'lda baholangan. Qolganlari — oson.
_THEORY_HARD = {
    4, 5, 7, 16, 17, 25, 42, 54, 55, 60, 66, 81, 82, 83, 86, 87, 88, 89, 90, 97, 104, 105, 108, 109, 110,
    126, 140, 145, 146, 150, 162, 163, 164, 165, 183, 187, 189, 190, 196, 197,
}
_THEORY_MEDIUM = {
    3, 6, 9, 10, 11, 13, 14, 15, 19, 21, 22, 24, 27, 28, 29, 31, 32, 35, 36, 37, 38, 43, 44, 48, 52, 56, 57,
    59, 64, 67, 68, 70, 73, 74, 79, 84, 85, 92, 93, 94, 95, 96, 98, 99, 100, 101, 102, 103, 106, 107, 113,
    116, 117, 118, 121, 122, 123, 124, 125, 127, 128, 131, 134, 135, 136, 137, 138, 139, 143, 147, 149,
    151, 152, 153, 154, 159, 160, 166, 167, 168, 169, 170, 171, 173, 174, 175, 176, 177, 179, 180, 182,
    186, 188, 192, 193, 194, 198, 200,
}

_HARD_TOPICS = (
    "o‘suvchi qism", "o'suvchi qism", "inversiya", "permutatsiya", "tangalar", "yig‘indisi x", "yig'indisi x",
    "k xil belgili", "labirint", "orollar", "ryukzak", "eng qisqa yo", "graf", "dinamik", "rekursiya",
    "umumiy qism ketma", "vazifalar tartibi", "zinapoya", "shaharlar guruh",
)
_MEDIUM_TOPICS = (
    "tub", "ekub", "ekuk", "mukammal", "armstrong", "ko‘paytuvchi", "ko'paytuvchi", "qism massiv", "oraliq",
    "fibonachchi", "palindrom", "saralash", "sort", "matritsa", "satr", "massiv", "ro‘yxat", "ro'yxat",
    "ikkining darajasi", "bo‘luvchi", "bo'luvchi",
)


def normalize(value):
    """Formadagi yoki fayldagi qiymatni easy/medium/hard ga keltiradi (bo'lmasa None)."""
    if not value:
        return None
    text = str(value).strip().lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'")
    if text in LEVELS:
        return text
    return _LABEL_WORDS.get(text) or _LABEL_WORDS.get(text.replace("'", ""))


def _from_label(prompt):
    match = re.search(r"Daraja:\s*([^\n·]+)", prompt or "")
    return normalize(match.group(1)) if match else None


def _code_score(code):
    code = code or ""
    lines = [line for line in code.splitlines() if line.strip() and not line.strip().startswith("#")]
    score = len(lines)
    loops = len(re.findall(r"^\s*(for|while)\b", code, re.M))
    score += 2 * loops
    indents = [len(line) - len(line.lstrip()) for line in lines if re.match(r"\s*(for|while)\b", line)]
    if len(indents) >= 2 and max(indents) > min(indents):
        score += 4  # ichma-ich sikl
    functions = re.findall(r"^\s*def\s+(\w+)", code, re.M)
    score += 3 * len(functions)
    for name in functions:
        body = code.split(f"def {name}", 1)[1]
        if re.search(rf"\b{name}\s*\(", body):
            score += 5  # rekursiya
    score += 2 * len(re.findall(r"\bfor\b.+\bin\b.+[\]\)]", code))
    score += 2 * len(re.findall(r"lambda|\bdict\b|\{.*:.*\}|\bset\(|\bzip\(|\benumerate\(|\bsorted\(.+key=", code))
    score += len(re.findall(r"\[[^\]]*:[^\]]*\]", code))  # kesmalar
    return score


def classify(question):
    """Savol obyekti (yoki shunga o'xshash) uchun easy/medium/hard."""
    prompt = getattr(question, "prompt", "") or ""
    label = _from_label(prompt)
    if label:
        return label
    kind = getattr(question, "question_type", "test")
    match = re.match(r"\[NB-(\d{3})\]", prompt)
    if match:
        number = int(match.group(1))
        if number in _THEORY_HARD:
            return "hard"
        return "medium" if number in _THEORY_MEDIUM else "easy"
    lowered = prompt.lower()
    if kind == "code_output":
        score = _code_score(getattr(question, "code_snippet", ""))
        return "easy" if score <= 2 else "medium" if score <= 4 else "hard"
    if kind == "code_problem":
        head = lowered.split("\n", 1)[0] + " " + lowered[:400]
        if any(word in head for word in _HARD_TOPICS):
            return "hard"
        if any(word in head for word in _MEDIUM_TOPICS):
            return "medium"
        number = re.match(r"(\d+)-masala", lowered)
        if number:
            return "easy" if int(number.group(1)) <= 30 else "medium"
        return "medium"
    # Test savollari: kod/ifoda bilan bog'liq yoki uzun savollar — o'rta, qolganlari — oson.
    if re.search(r"map\(|split\(|range\(|elif|sorted|\bfor\b", prompt) or len(prompt) > 140:
        return "medium"
    return "easy"
