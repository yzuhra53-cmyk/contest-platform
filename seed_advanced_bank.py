"""Seed advanced output-prediction quizzes and sequential coding problems."""

import contextlib
import io
import random
import sys

from app import app
from models import Question, db


SNIPPETS = [
    ("juft indekslardagi sonlar yig‘indisi", "a=list(map(int,input().split())); print(sum(x for i,x in enumerate(a) if i%2==0))", ["4 8 2 7", "9 -3 5 1 6", "0 0 0", "11 2 -4 9 3"]),
    ("takrorlanmaydigan qiymatlar soni", "a=list(map(int,input().split())); print(len(set(a)))", ["1 2 1 3 2 4", "5 5 5 5", "-1 0 1 0", "7 8 9"]),
    ("eng katta va ikkinchi eng katta turli son", "a=sorted(set(map(int,input().split()))); print(a[-2])", ["4 9 2 9 7", "10 1 8 3", "-5 -2 -9", "20 20 4 11"]),
    ("sonlar orasidagi eng katta qo‘shni farq", "a=list(map(int,input().split())); print(max(abs(a[i]-a[i-1]) for i in range(1,len(a))))", ["2 9 1 7", "5 5 5", "-4 8 -2", "100 1 50"]),
    ("eng uzun so‘z uzunligi", "print(max(map(len,input().split())))", ["algoritm kod test", "python dasturlash tili", "a bb ccc", "massiv va satr"]),
    ("satrda nechta unli harf bor", "s=input().lower(); print(sum(c in 'aeiou' for c in s))", ["Olimpiada", "algorithm", "PYTHON", "aeiouxyz"]),
    ("raqamlar yig‘indisi", "n=input().strip(); print(sum(map(int,n)))", ["908172", "11111", "50009", "2026"]),
    ("son raqamlarini teskari yozish", "n=input().strip(); print(str(int(n[::-1])))", ["12030", "9876", "1000", "54321"]),
    ("sonlarning EKUB qiymati", "import math; a=list(map(int,input().split())); from functools import reduce; print(reduce(math.gcd,a))", ["48 18 30", "81 27 9", "7 13 19", "100 80 60"]),
    ("berilgan oraliqdagi juft sonlar yig‘indisi", "a,b=map(int,input().split()); print(sum(x for x in range(a,b+1) if x%2==0))", ["1 10", "4 9", "-3 3", "12 12"]),
    ("saralangan ro‘yxatning medianasi (toq uzunlik)", "a=sorted(map(int,input().split())); print(a[len(a)//2])", ["9 1 5 3 7", "10 2 8", "-4 5 0", "11 1 9 3 7"]),
    ("ro‘yxat prefiks yig‘indilari", "a=list(map(int,input().split())); s=0; r=[]\nfor x in a:\n s+=x; r.append(s)\nprint(*r)", ["2 3 5", "1 -2 4 0", "10 10 -5", "7"]),
    ("sonlar ro‘yxatidagi musbat qiymatlar soni", "a=list(map(int,input().split())); print(sum(x>0 for x in a))", ["-2 0 7 3 -1 5", "1 2 3", "-4 -2 0", "9 -9"]),
    ("belgilangan K dan katta sonlar yig‘indisi", "a=list(map(int,input().split())); k=a[0]; print(sum(x for x in a[1:] if x>k))", ["4 2 9 4 7 1", "0 -1 0 2", "5 5 6 7", "-3 -2 -4"]),
    ("eng uzun bir xil belgilar ketma-ketligi", "s=input().strip(); best=run=0; prev=None\nfor c in s:\n run=run+1 if c==prev else 1; best=max(best,run); prev=c\nprint(best)", ["aaabbccccd", "abcd", "1111222", "zzzz"]),
    ("so‘zlarni alifbo tartibida chiqarish", "print(*sorted(input().split()))", ["nok olma anor", "z a m b", "kitob daftar ruchka", "beta alfa"]),
    ("n ta sonning kvadratlari yig‘indisi", "a=list(map(int,input().split())); print(sum(x*x for x in a))", ["1 2 3 4", "-2 3", "5 0 -5", "10"]),
    ("sonlarni aylana bo‘yicha bir qadam o‘ngga surish", "a=input().split(); print(a[-1],*a[:-1])", ["1 2 3 4", "olma nok", "8", "a b c"]),
    ("ro‘yxatdagi nol bo‘lmagan sonlar ko‘paytmasi", "import math; a=list(map(int,input().split())); print(math.prod(x for x in a if x!=0))", ["2 0 3 4", "-2 5", "0 7 0", "1 2 3"]),
    ("berilgan satr palindromligini aniqlash", "s=''.join(input().lower().split()); print('YES' if s==s[::-1] else 'NO')", ["level", "A man a plan a canal Panama", "python", "abba"]),
    ("X dan katta sonlar soni", "a=list(map(int,input().split())); x=a[0]; print(sum(v>x for v in a[1:]))", ["5 1 8 6 2 9", "0 -1 0 2", "7 8 9 10", "-3 -2 -4"]),
    ("3 ga bo‘linadigan sonlar ko‘paytmasi", "import math; a=list(map(int,input().split())); print(math.prod(x for x in a if x%3==0))", ["2 3 6 7 9", "1 2 4", "3 5 12", "6"]),
    ("massivdagi minimum va maksimum orasidagi farq", "a=list(map(int,input().split())); print(max(a)-min(a))", ["-10 5 21 3", "7 7 7", "0 100 -20", "2 9"]),
    ("satrda katta harflar soni", "s=input(); print(sum(c.isupper() for c in s))", ["PyTHon", "ABCdef", "lower", "X Y Z"]),
    ("Fibonachchi ketma-ketligining N- hadi (F0=0)", "n=int(input()); a,b=0,1\nfor _ in range(n): a,b=b,a+b\nprint(a)", ["8", "0", "10", "12"]),
]


def _snippet_output(code, data):
    source = io.StringIO(data)
    output = io.StringIO()
    old_stdin = sys.stdin
    with contextlib.redirect_stdout(output):
        sys.stdin = source
        try:
            exec(compile(code, "<trusted-seed-snippet>", "exec"), {})
        finally:
            sys.stdin = old_stdin
    return output.getvalue().strip()


def _choices(answer, variant):
    try:
        value = int(answer)
        candidates = [str(value + 1), str(value - 1), str(value * 2), str(value + 3)]
    except ValueError:
        candidates = ["0", "-1", "YES" if answer != "YES" else "NO", "NONE"]
    options = [answer]
    for candidate in candidates:
        if candidate not in options:
            options.append(candidate)
        if len(options) == 4:
            break
    rotation = variant % 4
    options = options[rotation:] + options[:rotation]
    return options, "ABCD"[options.index(answer)]


def _make_quiz_rows():
    rows = []
    for snippet_index, (title, code, inputs) in enumerate(SNIPPETS):
        for variant, input_data in enumerate(inputs):
            output = _snippet_output(code, input_data)
            options, correct = _choices(output, snippet_index * len(inputs) + variant)
            rows.append(
                {
                    "prompt": f"Python kodi natijasini aniqlang: {title}. Variant {len(rows) + 1}.",
                    "code": code,
                    "input": input_data,
                    "options": options,
                    "correct": correct,
                }
            )
    return rows


def _max_bounded_subarray(data, k):
    best = None
    for start in range(len(data)):
        total = 0
        for end in range(start, min(len(data), start + k)):
            total += data[end]
            best = total if best is None else max(best, total)
    return best if best is not None else 0


def _count_target_subarrays(data, target):
    counts = {0: 1}
    prefix = result = 0
    for value in data:
        prefix += value
        result += counts.get(prefix - target, 0)
        counts[prefix] = counts.get(prefix, 0) + 1
    return result


def _longest_k_distinct(text, k):
    counts = {}
    left = best = 0
    for right, char in enumerate(text):
        counts[char] = counts.get(char, 0) + 1
        while len(counts) > k:
            old = text[left]
            counts[old] -= 1
            if counts[old] == 0:
                del counts[old]
            left += 1
        best = max(best, right - left + 1)
    return best


def _lis_length(values):
    tails = []
    for value in values:
        low, high = 0, len(tails)
        while low < high:
            mid = (low + high) // 2
            if tails[mid] < value:
                low = mid + 1
            else:
                high = mid
        if low == len(tails):
            tails.append(value)
        else:
            tails[low] = value
    return len(tails)


def _inversions(values):
    result = 0
    for i in range(len(values)):
        result += sum(values[i] > value for value in values[i + 1:])
    return result


def _max_subarray(values):
    best = current = values[0]
    for value in values[1:]:
        current = max(value, current + value)
        best = max(best, current)
    return best


def _minimum_coins(coins, target):
    dp = [0] + [target + 1] * target
    for amount in range(1, target + 1):
        for coin in coins:
            if coin <= amount:
                dp[amount] = min(dp[amount], dp[amount - coin] + 1)
    return dp[target] if dp[target] <= target else -1


def _merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return len(merged)


def _prime_count(low, high):
    def is_prime(number):
        return number >= 2 and all(number % divisor for divisor in range(2, int(number**0.5) + 1))
    return sum(is_prime(number) for number in range(low, high + 1))


def _distinct_permutations(text):
    from collections import Counter

    counts = Counter(text)
    result = 1
    for value in range(2, len(text) + 1):
        result *= value
    for count in counts.values():
        for value in range(2, count + 1):
            result //= value
    return result


def _test_case(input_data, expected):
    return {"input": input_data, "output": str(expected)}


def _make_problem_rows():
    rows = []
    randomizer = random.Random(20261113)
    for variant in range(1, 11):
        numbers = [randomizer.randint(-20, 35) for _ in range(7 + variant % 4)]
        k = 1 + variant % len(numbers)
        cases = []
        for shift in range(4):
            values = numbers[shift:] + numbers[:shift]
            cases.append(_test_case(f"{len(values)} {k}\n" + " ".join(map(str, values)), _max_bounded_subarray(values, k)))
        rows.append((f"Masala {len(rows) + 1}: Uzunligi ko‘pi bilan K bo‘lgan eng katta yig‘indi",
                     "N ta butun son va K beriladi. Uzunligi 1 dan K gacha bo‘lgan ketma-ket qism massivlar ichidan yig‘indisi eng kattasini toping. N ≤ 2·10^5; yechim O(NK) dan samaraliroq bo‘lishi kerak.",
                     cases))

    for variant in range(1, 11):
        target = variant * 2 - 7
        numbers = [randomizer.randint(-9, 12) for _ in range(9)]
        cases = []
        for shift in range(4):
            values = numbers[shift:] + numbers[:shift]
            cases.append(_test_case(f"{len(values)} {target}\n" + " ".join(map(str, values)), _count_target_subarrays(values, target)))
        rows.append((f"Masala {len(rows) + 1}: Yig‘indisi X bo‘lgan qism massivlar",
                     "N ta son va X beriladi. Yig‘indisi aynan X ga teng bo‘lgan ketma-ket qism massivlar sonini toping. Sonlar manfiy ham bo‘lishi mumkin; O(N) prefix-yig‘indi usulidan foydalaning.",
                     cases))

    alphabet = "abcde"
    for variant in range(1, 11):
        text = "".join(randomizer.choice(alphabet[:2 + variant % 4]) for _ in range(18 + variant))
        k = 1 + variant % 4
        cases = []
        for shift in range(4):
            sample = text[shift:] + text[:shift]
            cases.append(_test_case(f"{sample} {k}", _longest_k_distinct(sample, k)))
        rows.append((f"Masala {len(rows) + 1}: K xil belgili eng uzun substring",
                     "S satr va K beriladi. Ko‘pi bilan K xil belgidan tashkil topgan eng uzun uzluksiz substring uzunligini chiqaring. S uzunligi 2·10^5 gacha.",
                     cases))

    for variant in range(1, 11):
        values = [randomizer.randint(-30, 30) for _ in range(10 + variant)]
        cases = []
        for shift in range(4):
            sample = values[shift:] + values[:shift]
            cases.append(_test_case(f"{len(sample)}\n" + " ".join(map(str, sample)), _lis_length(sample)))
        rows.append((f"Masala {len(rows) + 1}: Eng uzun o‘suvchi qism ketma-ketlik",
                     "N ta butun son berilgan. Elementlari qat’iy o‘suvchi bo‘lgan eng uzun qism ketma-ketlik uzunligini toping. Qism ketma-ketlik uzluksiz bo‘lishi shart emas. O(N log N) yechim kutiladi.",
                     cases))

    for variant in range(1, 11):
        values = [randomizer.randint(-25, 30) for _ in range(12 + variant)]
        cases = []
        for shift in range(4):
            sample = values[shift:] + values[:shift]
            cases.append(_test_case(f"{len(sample)}\n" + " ".join(map(str, sample)), _inversions(sample)))
        rows.append((f"Masala {len(rows) + 1}: Inversiyalar soni",
                     "N ta sondan iborat massiv beriladi. i < j va A[i] > A[j] shartini qanoatlantiruvchi juftliklar sonini toping. N ≤ 2·10^5, O(N log N) yechimdan foydalaning.",
                     cases))

    for variant in range(1, 11):
        values = [randomizer.randint(-40, 35) for _ in range(10 + variant)]
        cases = []
        for shift in range(4):
            sample = values[shift:] + values[:shift]
            cases.append(_test_case(f"{len(sample)}\n" + " ".join(map(str, sample)), _max_subarray(sample)))
        rows.append((f"Masala {len(rows) + 1}: Maksimal qism massiv yig‘indisi",
                     "N ta butun son beriladi. Kamida bitta elementli ketma-ket qism massiv yig‘indisining maksimal qiymatini toping. Barcha sonlar manfiy bo‘lishi ham mumkin. O(N) yechim ishlating.",
                     cases))

    for variant in range(1, 11):
        coins = sorted(set([1, 3 + variant % 3, 5 + variant % 5, 9 + variant % 4]))
        target = 20 + variant * 3
        cases = []
        for delta in (0, 1, 4, 7):
            amount = target + delta
            input_data = f"{len(coins)} {amount}\n" + " ".join(map(str, coins))
            cases.append(_test_case(input_data, _minimum_coins(coins, amount)))
        rows.append((f"Masala {len(rows) + 1}: Tangalarni eng kam sondagi tanlash",
                     "N turdagi tanga qiymatlari va S summa beriladi. Summani hosil qilish uchun kerak bo‘ladigan tangalarning eng kam sonini toping; summa hosil qilib bo‘lmasa -1 chiqaring. Har bir tangadan cheksiz foydalanish mumkin.",
                     cases))

    for variant in range(1, 11):
        base = variant * 3
        intervals = [(base, base + 3), (base + 2, base + 7), (base + 10, base + 12), (base + 11, base + 15), (base + 20, base + 21)]
        cases = []
        for shift in range(4):
            sample = intervals[shift:] + intervals[:shift]
            input_data = f"{len(sample)}\n" + "\n".join(f"{a} {b}" for a, b in sample)
            cases.append(_test_case(input_data, _merge_intervals(sample)))
        rows.append((f"Masala {len(rows) + 1}: Kesishuvchi oraliqlarni birlashtirish",
                     "N ta [L, R] butun sonli oraliq beriladi. Kesishuvchi yoki tutash oraliqlarni birlashtirgandan keyin nechta mustaqil oraliq qolishini toping. Kirishdagi tartib ixtiyoriy.",
                     cases))

    for variant in range(1, 11):
        low = 2 + variant
        high = low + 30 + variant
        cases = []
        for delta in (0, 3, 7, 11):
            left = low + delta
            right = high + delta
            cases.append(_test_case(f"{left} {right}", _prime_count(left, right)))
        rows.append((f"Masala {len(rows) + 1}: Oraliqdagi tub sonlar",
                     "L va R beriladi. [L, R] yopiq oraliqdagi tub sonlar sonini aniqlang. R ≤ 10^7 bo‘lishi mumkin; takroriy bo‘linishlarni kamaytiradigan usul tanlang.",
                     cases))

    for variant in range(1, 11):
        text = "".join(randomizer.choice("aabbccdde") for _ in range(8 + variant))
        cases = []
        for shift in range(4):
            sample = text[shift:] + text[:shift]
            cases.append(_test_case(sample, _distinct_permutations(sample)))
        rows.append((f"Masala {len(rows) + 1}: Takroriy belgili permutatsiyalar",
                     "Faqat kichik lotin harflaridan iborat S satr berilgan. Bir xil belgilarni o‘zaro almashtirish yangi permutatsiya hisoblanmaydi. Turli permutatsiyalar sonini hisoblang; javob katta bo‘lishi mumkin.",
                     cases))

    if len(rows) != 100:
        raise RuntimeError(f"100 ta kod masalasi kutilgan, {len(rows)} ta yaratildi.")
    return rows


def seed_questions():
    quizzes = _make_quiz_rows()
    problems = _make_problem_rows()
    if len(quizzes) != 100 or len(problems) != 100:
        raise RuntimeError("Bankda 100 ta test va 100 ta kod masalasi bo‘lishi shart.")
    with app.app_context():
        existing_quizzes = set(db.session.execute(
            db.select(Question.prompt).where(Question.question_type == "code_output")
        ).scalars())
        existing_problems = set(db.session.execute(
            db.select(Question.prompt).where(Question.question_type == "code_problem")
        ).scalars())
        added_quizzes = added_problems = 0
        for quiz in quizzes:
            if quiz["prompt"] in existing_quizzes:
                continue
            options = quiz["options"]
            db.session.add(Question(
                question_type="code_output",
                prompt=quiz["prompt"],
                code_snippet=quiz["code"],
                input_data=quiz["input"],
                option_a=options[0],
                option_b=options[1],
                option_c=options[2],
                option_d=options[3],
                correct_option=quiz["correct"],
            ))
            added_quizzes += 1
        for prompt, statement, cases in problems:
            full_prompt = f"{prompt}\n\n{statement}"
            if full_prompt in existing_problems:
                continue
            db.session.add(Question(
                question_type="code_problem",
                prompt=full_prompt,
                input_data=cases[0]["input"],
                expected_output=cases[0]["output"],
                test_cases_json=__import__("json").dumps(cases, ensure_ascii=False),
            ))
            added_problems += 1
        db.session.commit()
        print(
            f"{added_quizzes} ta yangi output testi, {added_problems} ta kod masalasi qo‘shildi. "
            f"Bankda jami {Question.query.filter_by(question_type='code_output').count()} ta output testi va "
            f"{Question.query.filter_by(question_type='code_problem').count()} ta kod masalasi mavjud."
        )


if __name__ == "__main__":
    seed_questions()
