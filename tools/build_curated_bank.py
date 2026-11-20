"""Savollar bazasini saralash: har bir blokdan takrorlanmaydigan eng yaxshi savollar,
har bir darajadan ko'pi bilan 40 ta (Oson / O‘rta / Qiyin).

Natija — curated_bank.json: qoldiriladigan savollar matni (bloklar bo'yicha).
Ilova ishga tushganda (app.curate_bank) bank savollaridan shu ro'yxatda yo'qlari o'chiriladi.

    python tools/build_curated_bank.py
"""
import json
import os
import re
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from difficulty import classify  # noqa: E402

PER_LEVEL = 40
LEVELS = ("easy", "medium", "hard")


def norm(text):
    return " ".join((text or "").split())


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as file:
        return json.load(file)


def level_of(**fields):
    return classify(types.SimpleNamespace(**fields))


def problem_title(prompt):
    head = prompt.split("\n", 1)[0]
    head = re.sub(r"^(\[OB-\d+\]\s*|Masala \d+:\s*|\d+-masala:\s*)", "", head)
    return head.split(" · ")[0].strip().casefold()


def pick(candidates):
    """candidates: [(level, key, prompt)] tartib bo'yicha; har darajadan PER_LEVEL ta."""
    chosen = {level: [] for level in LEVELS}
    for level, _key, prompt in candidates:
        if len(chosen[level]) < PER_LEVEL:
            chosen[level].append(prompt)
    return chosen


def balanced(items, per_group_key):
    """Mavzular bo'yicha navbatma-navbat (round-robin) tartiblaydi."""
    groups = {}
    for item in items:
        groups.setdefault(per_group_key(item), []).append(item)
    ordered, queues = [], [list(group) for group in groups.values()]
    while any(queues):
        for queue in queues:
            if queue:
                ordered.append(queue.pop(0))
    return ordered


def main():
    qd = load("questions_data.json")
    problem_bank = load("problem_bank.json")
    theory_bank = load("theory_bank.json")

    # ---- Kod yozish: avval olimpiada banki (to'liq shart, ko'p test), keyin qolganlari; nom bo'yicha takrorlanmas.
    seen, coding = set(), []
    sources = [item["prompt"] for item in problem_bank] + [q["prompt"] for q in qd if q["question_type"] == "code_problem"]
    for prompt in sources:
        title = problem_title(prompt)
        if title in seen:
            continue
        seen.add(title)
        coding.append((level_of(prompt=prompt, question_type="code_problem"), title, prompt))

    # ---- Output testi: bir xil kod faqat bir marta.
    seen, output = set(), []
    for q in qd:
        if q["question_type"] != "code_output":
            continue
        snippet = norm(q["code_snippet"])
        if snippet in seen:
            continue
        seen.add(snippet)
        output.append((level_of(prompt=q["prompt"], question_type="code_output", code_snippet=q["code_snippet"]),
                       snippet, q["prompt"]))

    # ---- Nazariy bilimlar: 5 blokdan teng taqsimlab.
    theory = []
    for level in LEVELS:
        items = [t for t in theory_bank if level_of(prompt=t["prompt"], question_type="test") == level]
        for t in balanced(items, lambda item: item["category"]):
            theory.append((level, t["key"], t["prompt"]))

    result = {}
    for block, candidates in (("code_problem", coding), ("code_output", output), ("test", theory)):
        chosen = pick(candidates)
        result[block] = {level: [norm(p) for p in prompts] for level, prompts in chosen.items()}
        print(block, {level: len(prompts) for level, prompts in chosen.items()})

    seeded = sorted({norm(q["prompt"]) for q in qd} | {norm(p["prompt"]) for p in problem_bank}
                    | {norm(t["prompt"]) for t in theory_bank})
    with open(os.path.join(ROOT, "curated_bank.json"), "w", encoding="utf-8", newline="\n") as file:
        json.dump({"version": 1, "keep": result, "seeded": seeded}, file, ensure_ascii=False, indent=1)
        file.write("\n")


if __name__ == "__main__":
    main()
