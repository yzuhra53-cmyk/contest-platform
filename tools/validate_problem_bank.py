"""problem_bank.json ni haqiqiy judge orqali tekshiradi.

1. Har bir etalon yechim barcha testlardan vaqt limiti (JUDGE_TIME_LIMIT) ichida o'tishi kerak.
2. Faqat namuna javobini chiqaradigan "aldamchi" yechim qabul qilinmasligi kerak
   (testlar yetarlicha farqlovchi ekanini tekshiradi).

Ishga tushirish (loyiha papkasida):
    uv run python tools/validate_problem_bank.py
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_problem_bank import PROBLEMS  # noqa: E402
from judge import TIME_LIMIT, judge_solution  # noqa: E402


def main():
    with open(os.path.join(ROOT, "problem_bank.json"), encoding="utf-8") as handle:
        bank = {item["key"]: item for item in json.load(handle)}
    failures = 0
    for spec in PROBLEMS:
        item = bank[spec["key"]]
        started = time.perf_counter()
        accepted, message = judge_solution("python", spec["ref"], item["test_cases"])
        elapsed = time.perf_counter() - started
        cheat = f"print({item['expected_output']!r})"
        cheat_accepted, _ = judge_solution("python", cheat, item["test_cases"])
        ok = accepted and not cheat_accepted
        failures += not ok
        print(f"{'OK ' if ok else 'XATO'} {spec['key']} {spec['title']}: etalon — {message} ({elapsed:.1f} s); "
              f"namunani chiqaruvchi yechim {'QABUL QILINDI!' if cheat_accepted else 'rad etildi'}")
    print(f"\nVaqt limiti: {TIME_LIMIT:g} s har bir test uchun. Xatolar: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
