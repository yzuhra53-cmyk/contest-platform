"""Olimpiada masalalar bankini (problem_bank.json) yaratadi.

Har bir masala uchun: shart, generator (deterministik, seed bilan) va etalon yechim.
Testlarning to'g'ri javoblari etalon yechimni haqiqatan ishga tushirib olinadi;
ba'zi masalalarda kichik testlar sodda (brute-force) yechim bilan ham solishtiriladi.

Ishga tushirish (loyiha papkasida):
    uv run python tools/build_problem_bank.py
"""

import json
import os
import random
import string
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "problem_bank.json")
MAX_CASE_CHARS = 100_000
BRUTE_MAX_INPUT = 3_000

PROBLEMS = []


def problem(key, title, level, statement, input_fmt, output_fmt, limits, ref, gen, brute=None, brute_if=None):
    PROBLEMS.append(dict(key=key, title=title, level=level, statement=statement, input_fmt=input_fmt,
                         output_fmt=output_fmt, limits=limits, ref=ref, gen=gen, brute=brute,
                         brute_if=brute_if or (lambda text: len(text) <= BRUTE_MAX_INPUT)))


def arr(values):
    return " ".join(map(str, values))


def arr_case(values):
    return f"{len(values)}\n{arr(values)}"


def words(rnd, count, min_len=1, max_len=8, alphabet=string.ascii_lowercase):
    return ["".join(rnd.choice(alphabet) for _ in range(rnd.randint(min_len, max_len))) for _ in range(count)]


# ---------------------------------------------------------------- 1
problem(
    "OB-01", "Juftlar va toqlar farqi", "Oson",
    "n ta butun son berilgan. Juft sonlar yig‘indisidan toq sonlar yig‘indisini ayiring. "
    "Manfiy sonlarning juft-toqligi ham odatdagidek aniqlanadi (masalan, −3 toq, −4 juft).",
    "Birinchi qatorda n, ikkinchi qatorda n ta butun son.",
    "Bitta son — juftlar yig‘indisi minus toqlar yig‘indisi.",
    "1 ≤ n ≤ 10^5, |a_i| ≤ 10^4",
    """import sys
d = sys.stdin.read().split()
a = list(map(int, d[1:1 + int(d[0])]))
print(sum(x for x in a if x % 2 == 0) - sum(x for x in a if x % 2 != 0))
""",
    lambda r: ["5\n1 2 3 4 5", "1\n-3", "1\n0", "4\n-4 -3 -2 -1"]
    + [arr_case([r.randint(-10**4, 10**4) for _ in range(r.randint(2, 50))]) for _ in range(5)]
    + [arr_case([r.randint(-10**4, 10**4) for _ in range(11000)]), arr_case([-9999] * 11000)],
)

# ---------------------------------------------------------------- 2
problem(
    "OB-02", "Eng uzun o‘suvchi bo‘lak", "Oson",
    "n ta sondan iborat massiv berilgan. Ketma-ket joylashgan va qat’iy o‘suvchi bo‘lgan "
    "eng uzun bo‘lakning (qism massivning) uzunligini toping.",
    "Birinchi qatorda n, ikkinchi qatorda a_1 … a_n.",
    "Bitta son — eng uzun qat’iy o‘suvchi bo‘lak uzunligi.",
    "1 ≤ n ≤ 10^5, 0 ≤ a_i ≤ 10^6",
    """import sys
d = sys.stdin.read().split()
n = int(d[0]); a = list(map(int, d[1:1 + n]))
best = cur = 1
for i in range(1, n):
    cur = cur + 1 if a[i] > a[i - 1] else 1
    best = max(best, cur)
print(best)
""",
    lambda r: ["8\n1 2 2 3 4 5 1 9", "1\n7", "5\n5 4 3 2 1", "6\n1 2 3 4 5 6"]
    + [arr_case([r.randint(0, 10) for _ in range(r.randint(2, 60))]) for _ in range(5)]
    + [arr_case(list(range(1, 11001))), arr_case([r.randint(0, 10**6) for _ in range(11000)])],
    brute="""import sys
d = sys.stdin.read().split()
n = int(d[0]); a = list(map(int, d[1:1 + n]))
best = 1
for i in range(n):
    j = i
    while j + 1 < n and a[j + 1] > a[j]:
        j += 1
    best = max(best, j - i + 1)
print(best)
""",
)

# ---------------------------------------------------------------- 3
problem(
    "OB-03", "Turli sonlar", "Oson",
    "n ta butun son berilgan. Ular orasida nechta turli qiymat borligini aniqlang.",
    "Birinchi qatorda n, ikkinchi qatorda n ta butun son.",
    "Bitta son — turli qiymatlar soni.",
    "1 ≤ n ≤ 10^4, |a_i| ≤ 10^9",
    """import sys
d = sys.stdin.read().split()
print(len(set(map(int, d[1:1 + int(d[0])]))))
""",
    lambda r: ["7\n3 1 3 -2 1 3 5", "1\n0", "5\n7 7 7 7 7", "4\n-1000000000 1000000000 0 -1000000000"]
    + [arr_case([r.randint(-5, 5) for _ in range(r.randint(1, 40))]) for _ in range(5)]
    + [arr_case([r.randint(-10**9, 10**9) for _ in range(8000)]), arr_case([r.randint(1, 100) for _ in range(10**4)])],
)

# ---------------------------------------------------------------- 4
def gen_longest_word(r):
    tests = ["olma anor uzum shaftoli nok", "a", "bir ikki uch tort", "qalam daftar kitob"]
    for size in (5, 20, 100, 400):
        tests.append(" ".join(words(r, size, 1, 12)))
    tests.append(" ".join(words(r, 6000, 1, 9)))
    tests.append(" ".join(["abc"] * 3000 + ["abcd"] + ["abcde"] * 2))
    return tests


problem(
    "OB-04", "Eng uzun so‘z", "Oson",
    "Bitta qatorda kichik lotin harflaridan iborat so‘zlar bitta bo‘sh joy bilan ajratib yozilgan. "
    "Eng uzun so‘zni chiqaring. Bunday so‘zlar bir nechta bo‘lsa, ulardan birinchi uchraganini chiqaring.",
    "Bitta qator — so‘zlar.",
    "Eng uzun so‘z.",
    "Qator uzunligi 1 dan 60 000 gacha.",
    """import sys
w = sys.stdin.read().split()
best = w[0]
for x in w:
    if len(x) > len(best):
        best = x
print(best)
""",
    gen_longest_word,
)

# ---------------------------------------------------------------- 5
def gen_phrase_pal(r):
    tests = ["A man, a plan, a canal: Panama", "Salom dunyo", "No lemon, no melon", "x", "12321", "ab"]
    alphabet = string.ascii_letters + string.digits
    for size in (10, 50, 300, 3000):
        core = [r.choice(alphabet) for _ in range(size)]
        if r.random() < 0.6:
            core = core + core[::-1]
        noisy = []
        for ch in core:
            noisy.append(ch.upper() if r.random() < 0.3 else ch.lower() if ch.isalpha() else ch)
            if r.random() < 0.2:
                noisy.append(r.choice(" ,.!?-:;"))
        tests.append("".join(noisy).strip(" ") or "a")
    return tests


problem(
    "OB-05", "Gap-palindrom", "Oson",
    "Bitta qatorda matn berilgan. Faqat lotin harflari va raqamlarni hisobga olib, katta-kichik harf farqiga "
    "qaramasdan, matn palindrom (chapdan o‘ngga va o‘ngdan chapga bir xil o‘qiladi) bo‘lsa YES, aks holda NO chiqaring.",
    "Bitta qator — matn (kamida bitta harf yoki raqam bor).",
    "YES yoki NO.",
    "Matn uzunligi ≤ 20 000.",
    """import sys
s = [c.lower() for c in sys.stdin.read() if c.isascii() and c.isalnum()]
print("YES" if s == s[::-1] else "NO")
""",
    gen_phrase_pal,
)

# ---------------------------------------------------------------- 6
problem(
    "OB-06", "Ikkinchi o‘rin", "Oson",
    "Musobaqada n ta ishtirokchi ball oldi. Ikkinchi o‘rindagi ball — eng katta balldan qat’iy kichik bo‘lgan "
    "eng katta ball. Uni toping. Barcha ballar bir xil bo‘lsa, NO chiqaring.",
    "Birinchi qatorda n, ikkinchi qatorda n ta butun son.",
    "Ikkinchi o‘rin bali yoki NO.",
    "1 ≤ n ≤ 10^5, |a_i| ≤ 10^4",
    """import sys
d = sys.stdin.read().split()
a = set(map(int, d[1:1 + int(d[0])]))
if len(a) < 2:
    print("NO")
else:
    m = max(a); a.discard(m); print(max(a))
""",
    lambda r: ["6\n5 9 2 9 7 1", "1\n4", "3\n-5 -5 -5", "2\n-1 -2", "4\n10000 -10000 10000 9999"]
    + [arr_case([r.randint(-20, 20) for _ in range(r.randint(2, 30))]) for _ in range(4)]
    + [arr_case([r.randint(-10**4, 10**4) for _ in range(11000)]), arr_case([7] * 11000)],
)

# ---------------------------------------------------------------- 7
problem(
    "OB-07", "Raqamli ildiz", "Oson",
    "Manfiy bo‘lmagan butun N son berilgan. Uning raqamlari yig‘indisini topamiz, natija bir xonali bo‘lmaguncha "
    "shu amalni takrorlaymiz. Hosil bo‘lgan bir xonali sonni (raqamli ildizni) chiqaring. N juda katta bo‘lishi mumkin.",
    "Bitta qatorda N (boshida ortiqcha nollar yo‘q).",
    "Bitta raqam.",
    "N ning uzunligi 1 dan 50 000 raqamgacha.",
    """import sys
s = sys.stdin.read().strip()
t = sum(map(int, s))
while t >= 10:
    t = sum(map(int, str(t)))
print(t)
""",
    lambda r: ["9875", "0", "9", "10", "999999999999999999"]
    + [str(r.randint(1, 9)) + "".join(r.choice(string.digits) for _ in range(r.randint(1, 300))) for _ in range(5)]
    + ["9" * 50000, "1" + "0" * 49999, str(r.randint(1, 9)) + "".join(r.choice(string.digits) for _ in range(49999))],
)

# ---------------------------------------------------------------- 8
def gen_brackets(r):
    pairs = {"(": ")", "[": "]", "{": "}"}

    def balanced(n):
        out, stack = [], []
        while len(out) + len(stack) < n or stack:
            if stack and (len(out) + len(stack) >= n or r.random() < 0.45):
                out.append(pairs[stack.pop()])
            else:
                ch = r.choice("([{")
                stack.append(ch)
                out.append(ch)
        return "".join(out)

    tests = ["([]{})", "([)]", "(", "}", "{[()()]}", "(()"]
    for n in (10, 50, 400):
        tests.append(balanced(n))
    for n in (10, 60, 500):
        s = list(balanced(n))
        i = r.randrange(len(s))
        s[i] = r.choice("()[]{}".replace(s[i], ""))
        tests.append("".join(s))
    tests.append(balanced(40000))
    tests.append("(" * 25000 + ")" * 24999 + "]")
    return tests


problem(
    "OB-08", "Qavslar muvozanati", "O‘rta",
    "Faqat ( ) [ ] { } belgilaridan iborat satr berilgan. Satr to‘g‘ri qavslar ketma-ketligi bo‘lsa YES, aks holda NO "
    "chiqaring. To‘g‘ri ketma-ketlikda har bir ochilgan qavs o‘z turidagi qavs bilan, to‘g‘ri tartibda yopiladi.",
    "Bitta qator — qavslar satri.",
    "YES yoki NO.",
    "Satr uzunligi 1 dan 50 000 gacha.",
    """import sys
s = sys.stdin.read().strip()
match = {")": "(", "]": "[", "}": "{"}
st = []
ok = True
for c in s:
    if c in "([{":
        st.append(c)
    elif not st or st.pop() != match[c]:
        ok = False
        break
print("YES" if ok and not st else "NO")
""",
    gen_brackets,
)

# ---------------------------------------------------------------- 9
def gen_matrix(r):
    def case(n, lo, hi):
        rows = [" ".join(str(r.randint(lo, hi)) for _ in range(n)) for _ in range(n)]
        return f"{n}\n" + "\n".join(rows)

    return ["3\n1 2 3\n4 5 6\n9 8 9", "1\n-7", "2\n1 2\n3 4"] + [case(r.randint(2, 8), -9, 9) for _ in range(5)] + [
        case(120, -1000, 1000), case(120, 1000, 1000)]


problem(
    "OB-09", "Diagonallar farqi", "Oson",
    "n×n o‘lchamli butun sonli matritsa berilgan. Bosh diagonal (chap yuqoridan o‘ng pastga) elementlari yig‘indisi "
    "bilan yordamchi diagonal (o‘ng yuqoridan chap pastga) elementlari yig‘indisi orasidagi farqning modulini toping.",
    "Birinchi qatorda n, keyingi n qatorda matritsaning qatorlari.",
    "Bitta son.",
    "1 ≤ n ≤ 120, |a_ij| ≤ 1000",
    """import sys
d = sys.stdin.read().split()
n = int(d[0]); v = list(map(int, d[1:]))
print(abs(sum(v[i * n + i] for i in range(n)) - sum(v[i * n + n - 1 - i] for i in range(n))))
""",
    gen_matrix,
)

# ---------------------------------------------------------------- 10
def gen_caesar(r):
    tests = ["3\nSalom, Dunyo!", "0\nabc XYZ", "26\nZebra", "1000000000\nHello World 2026", "25\nab yz AB YZ"]
    alphabet = string.ascii_letters + string.digits + " ,.!?-"
    for size in (20, 100, 1000, 30000):
        text = "".join(r.choice(alphabet) for _ in range(size)).strip() or "a"
        text = " ".join(text.split())
        tests.append(f"{r.randint(0, 10**9)}\n{text}")
    return tests


problem(
    "OB-10", "Sezar shifri", "Oson",
    "k soni va matn berilgan. Matndagi har bir lotin harfini alifboda k pozitsiya oldinga suring (z dan keyin yana a "
    "keladi). Katta harflar katta, kichiklari kichik bo‘lib qoladi; boshqa belgilar o‘zgarmaydi.",
    "Birinchi qatorda k, ikkinchi qatorda matn.",
    "Shifrlangan matn.",
    "0 ≤ k ≤ 10^9, matn uzunligi ≤ 30 000.",
    """import sys
lines = sys.stdin.read().split("\\n", 1)
k = int(lines[0]) % 26
text = lines[1].rstrip("\\n") if len(lines) > 1 else ""
out = []
for c in text:
    if "a" <= c <= "z":
        out.append(chr((ord(c) - 97 + k) % 26 + 97))
    elif "A" <= c <= "Z":
        out.append(chr((ord(c) - 65 + k) % 26 + 65))
    else:
        out.append(c)
print("".join(out))
""",
    gen_caesar,
)

# ---------------------------------------------------------------- 11
def gen_prefix(r):
    def case(n, q, hi):
        a = [r.randint(-hi, hi) for _ in range(n)]
        qs = []
        for _ in range(q):
            left = r.randint(1, n)
            qs.append(f"{left} {r.randint(left, n)}")
        return f"{n} {q}\n{arr(a)}\n" + "\n".join(qs)

    return ["5 3\n1 2 3 4 5\n1 5\n2 4\n3 3", "1 1\n-7\n1 1"] + [case(r.randint(2, 20), r.randint(1, 10), 50) for _ in range(5)] + [
        case(6000, 6000, 10**4), case(10000, 4000, 10**4)]


problem(
    "OB-11", "Oraliq yig‘indilari", "O‘rta",
    "n ta sondan iborat massiv va q ta so‘rov berilgan. Har bir so‘rovda l va r beriladi: a_l + a_(l+1) + … + a_r "
    "yig‘indisini chiqaring. So‘rovlar ko‘p — har biriga massivni qayta aylanib chiqish juda sekin bo‘ladi.",
    "Birinchi qatorda n va q. Ikkinchi qatorda a_1 … a_n. Keyingi q qatorda l r (1 ≤ l ≤ r ≤ n).",
    "Har bir so‘rov javobi alohida qatorda.",
    "1 ≤ n, q ≤ 10^4, |a_i| ≤ 10^4",
    """import sys
d = sys.stdin.buffer.read().split()
n, q = int(d[0]), int(d[1])
p = [0] * (n + 1)
for i in range(n):
    p[i + 1] = p[i] + int(d[2 + i])
out = []
pos = 2 + n
for _ in range(q):
    l, r = int(d[pos]), int(d[pos + 1]); pos += 2
    out.append(p[r] - p[l - 1])
print("\\n".join(map(str, out)))
""",
    gen_prefix,
    brute="""import sys
d = sys.stdin.read().split()
n, q = int(d[0]), int(d[1])
a = list(map(int, d[2:2 + n]))
pos = 2 + n
for _ in range(q):
    l, r = int(d[pos]), int(d[pos + 1]); pos += 2
    print(sum(a[l - 1:r]))
""",
)

# ---------------------------------------------------------------- 12
def gen_pairs(r):
    def case(n, hi, target=None):
        a = [r.randint(-hi, hi) for _ in range(n)]
        s = target if target is not None else a[0] + a[-1]
        return f"{n} {s}\n{arr(a)}"

    return ["5 6\n1 5 3 3 2", "1 2\n1", "4 0\n0 0 0 0", "3 100\n1 2 3"] + [case(r.randint(2, 40), 10) for _ in range(5)] + [
        case(11000, 1000), case(11000, 3, 0)]


problem(
    "OB-12", "Juftliklar yig‘indisi", "O‘rta",
    "n ta butun son va S berilgan. i < j bo‘lib, a_i + a_j = S shartini qanoatlantiradigan (i, j) juftliklar sonini toping.",
    "Birinchi qatorda n va S, ikkinchi qatorda a_1 … a_n.",
    "Bitta son — juftliklar soni.",
    "1 ≤ n ≤ 10^5, |a_i| ≤ 10^4, |S| ≤ 2·10^4",
    """import sys
d = sys.stdin.read().split()
n, s = int(d[0]), int(d[1])
seen = {}
total = 0
for x in map(int, d[2:2 + n]):
    total += seen.get(s - x, 0)
    seen[x] = seen.get(x, 0) + 1
print(total)
""",
    gen_pairs,
    brute="""import sys
d = sys.stdin.read().split()
n, s = int(d[0]), int(d[1])
a = list(map(int, d[2:2 + n]))
print(sum(1 for i in range(n) for j in range(i + 1, n) if a[i] + a[j] == s))
""",
)

# ---------------------------------------------------------------- 13
problem(
    "OB-13", "Eng foydali davr", "O‘rta",
    "Do‘konning n kunlik foydasi (manfiy bo‘lishi mumkin) berilgan. Ketma-ket kunlardan iborat, kamida bir kunlik "
    "davr tanlab, foydalar yig‘indisini maksimal qiling. Shu maksimal yig‘indini chiqaring.",
    "Birinchi qatorda n, ikkinchi qatorda n ta butun son.",
    "Bitta son — maksimal yig‘indi.",
    "1 ≤ n ≤ 10^5, |a_i| ≤ 10^4",
    """import sys
d = sys.stdin.read().split()
a = list(map(int, d[1:1 + int(d[0])]))
best = cur = a[0]
for x in a[1:]:
    cur = max(x, cur + x)
    best = max(best, cur)
print(best)
""",
    lambda r: ["8\n-2 1 -3 4 -1 2 1 -5", "1\n-5", "3\n-3 -1 -2", "4\n1 2 3 4"]
    + [arr_case([r.randint(-20, 20) for _ in range(r.randint(1, 60))]) for _ in range(5)]
    + [arr_case([r.randint(-10**4, 10**4) for _ in range(11000)]), arr_case([-10**4] * 5000 + [1] + [-10**4] * 5000)],
    brute="""import sys
d = sys.stdin.read().split()
a = list(map(int, d[1:1 + int(d[0])]))
n = len(a)
best = a[0]
for i in range(n):
    s = 0
    for j in range(i, n):
        s += a[j]
        best = max(best, s)
print(best)
""",
)

# ---------------------------------------------------------------- 14
def gen_anagram(r):
    def case(groups, per, length):
        bases = set()
        while len(bases) < groups:
            bases.add("".join(r.choice("abcdefgh") for _ in range(length)))
        items = []
        for base in bases:
            for _ in range(r.randint(1, per)):
                w = list(base)
                r.shuffle(w)
                items.append("".join(w))
        r.shuffle(items)
        return f"{len(items)}\n" + "\n".join(items)

    return ["6\nolma\nmola\nanor\nnora\nuzum\nalom", "1\nx", "3\nab\nba\nab"] + [case(r.randint(1, 6), 4, r.randint(1, 4)) for _ in range(5)] + [
        case(1500, 6, 6), case(3000, 2, 10)]


problem(
    "OB-14", "Anagramma guruhlari", "O‘rta",
    "n ta so‘z berilgan. Ikki so‘z bir xil harflardan (har bir harf bir xil miqdorda) tuzilgan bo‘lsa, ular bitta "
    "guruhga kiradi. So‘zlar nechta guruhga bo‘linishini toping.",
    "Birinchi qatorda n, keyingi n qatorda kichik lotin harflaridan iborat so‘zlar.",
    "Bitta son — guruhlar soni.",
    "1 ≤ n ≤ 10^4, so‘z uzunligi ≤ 10",
    """import sys
d = sys.stdin.read().split()
print(len({"".join(sorted(w)) for w in d[1:1 + int(d[0])]}))
""",
    gen_anagram,
)

# ---------------------------------------------------------------- 15
problem(
    "OB-15", "Eng ommabop qiymat", "O‘rta",
    "n ta butun son berilgan. Eng ko‘p uchragan qiymatni va u necha marta uchraganini chiqaring. "
    "Bunday qiymatlar bir nechta bo‘lsa, eng kichigini chiqaring.",
    "Birinchi qatorda n, ikkinchi qatorda n ta butun son.",
    "Ikki son: qiymat va uchrashlar soni.",
    "1 ≤ n ≤ 10^5, |a_i| ≤ 10^4",
    """import sys
from collections import Counter
d = sys.stdin.read().split()
c = Counter(map(int, d[1:1 + int(d[0])]))
best = max(c.values())
print(min(k for k, v in c.items() if v == best), best)
""",
    lambda r: ["7\n4 1 4 2 1 3 5", "1\n-8", "4\n3 2 1 0", "6\n-1 -1 -2 -2 5 5"]
    + [arr_case([r.randint(-5, 5) for _ in range(r.randint(1, 50))]) for _ in range(5)]
    + [arr_case([r.randint(-10**4, 10**4) for _ in range(11000)]), arr_case([r.randint(-3, 3) for _ in range(11000)])],
)

# ---------------------------------------------------------------- 16
def gen_intervals(r):
    def case(n, hi):
        lines = []
        for _ in range(n):
            a = r.randint(0, hi)
            lines.append(f"{a} {r.randint(a, min(hi, a + hi // 5 + 1))}")
        return f"{n}\n" + "\n".join(lines)

    return ["4\n1 3\n2 6\n8 10\n10 12", "1\n5 5", "3\n0 1\n2 3\n4 5", "3\n1 10\n2 3\n4 5"] + [case(r.randint(2, 15), 50) for _ in range(5)] + [
        case(6000, 10**6), case(6000, 2000)]


problem(
    "OB-16", "Bandlik jadvali", "O‘rta",
    "Auditoriya n marta band qilingan, har bir bandlik [l, r] yopiq oraliq bilan berilgan. Bir-biri bilan kesishgan "
    "yoki tegib turgan (birining oxiri ikkinchisining boshiga teng) oraliqlar birlashtiriladi. Birlashtirilgandan "
    "keyin nechta oraliq qolishini va ularning umumiy uzunligini (har bir oraliq uchun r − l yig‘indisi) chiqaring.",
    "Birinchi qatorda n, keyingi n qatorda l r.",
    "Ikki son: oraliqlar soni va umumiy uzunlik.",
    "1 ≤ n ≤ 10^4, 0 ≤ l ≤ r ≤ 10^6",
    """import sys
d = sys.stdin.read().split()
n = int(d[0])
iv = sorted((int(d[1 + 2 * i]), int(d[2 + 2 * i])) for i in range(n))
merged = []
for l, r in iv:
    if merged and l <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], r)
    else:
        merged.append([l, r])
print(len(merged), sum(r - l for l, r in merged))
""",
    gen_intervals,
)

# ---------------------------------------------------------------- 17
def gen_count_le(r):
    def case(n, q, hi):
        a = sorted(r.randint(-hi, hi) for _ in range(n))
        xs = [r.randint(-hi - 2, hi + 2) for _ in range(q)]
        return f"{n}\n{arr(a)}\n{q}\n{arr(xs)}"

    return ["5\n1 3 3 7 9\n4\n3 0 10 7", "1\n5\n2\n4 5"] + [case(r.randint(1, 20), r.randint(1, 10), 20) for _ in range(5)] + [
        case(6000, 6000, 10**4), case(9000, 5000, 50)]


problem(
    "OB-17", "Nechta kichik yoki teng?", "O‘rta",
    "O‘sish tartibida saralangan n ta son va q ta so‘rov berilgan. Har bir so‘rovda x beriladi: massivda x dan "
    "kichik yoki unga teng elementlar sonini chiqaring.",
    "Birinchi qatorda n, ikkinchi qatorda saralangan massiv, uchinchi qatorda q, to‘rtinchi qatorda q ta x.",
    "q ta javob, bitta qatorda bo‘sh joy bilan.",
    "1 ≤ n, q ≤ 10^4, |a_i|, |x| ≤ 10^4",
    """import sys
from bisect import bisect_right
d = sys.stdin.read().split()
n = int(d[0]); a = list(map(int, d[1:1 + n]))
q = int(d[1 + n])
print(" ".join(str(bisect_right(a, int(x))) for x in d[2 + n:2 + n + q]))
""",
    gen_count_le,
    brute="""import sys
d = sys.stdin.read().split()
n = int(d[0]); a = list(map(int, d[1:1 + n]))
q = int(d[1 + n])
print(" ".join(str(sum(1 for v in a if v <= int(x))) for x in d[2 + n:2 + n + q]))
""",
)

# ---------------------------------------------------------------- 18
def gen_window(r):
    def case(n, k, hi):
        return f"{n} {k}\n{arr([r.randint(-hi, hi) for _ in range(n)])}"

    return ["6 3\n2 1 5 1 3 2", "1 1\n-4", "5 5\n1 -2 3 -4 5"] + [case(n, r.randint(1, n), 30) for n in (r.randint(2, 30) for _ in range(5))] + [
        case(11000, 7000, 10**4), case(11000, 1, 10**4)]


problem(
    "OB-18", "Sirpanuvchi oyna", "O‘rta",
    "n ta son va k berilgan. Ketma-ket joylashgan aynan k ta elementning yig‘indisi eng katta bo‘lishi uchun qaysi "
    "bo‘lakni tanlash kerak? Shu maksimal yig‘indini chiqaring.",
    "Birinchi qatorda n va k, ikkinchi qatorda n ta son.",
    "Bitta son.",
    "1 ≤ k ≤ n ≤ 10^5, |a_i| ≤ 10^4",
    """import sys
d = sys.stdin.read().split()
n, k = int(d[0]), int(d[1])
a = list(map(int, d[2:2 + n]))
s = sum(a[:k]); best = s
for i in range(k, n):
    s += a[i] - a[i - k]
    best = max(best, s)
print(best)
""",
    gen_window,
    brute="""import sys
d = sys.stdin.read().split()
n, k = int(d[0]), int(d[1])
a = list(map(int, d[2:2 + n]))
print(max(sum(a[i:i + k]) for i in range(n - k + 1)))
""",
)

# ---------------------------------------------------------------- 19
problem(
    "OB-19", "Tub sonlar soni", "O‘rta",
    "N berilgan. 1 dan N gacha (N ham kiradi) nechta tub son borligini toping. N katta — har bir sonni alohida "
    "tekshirish vaqt limitiga sig‘maydi, Eratosfen g‘alviridan foydalaning.",
    "Bitta son N.",
    "Bitta son — tub sonlar soni.",
    "1 ≤ N ≤ 3·10^6",
    """import sys
n = int(sys.stdin.read())
if n < 2:
    print(0)
else:
    sieve = bytearray([1]) * (n + 1)
    sieve[0] = sieve[1] = 0
    i = 2
    while i * i <= n:
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(range(i * i, n + 1, i)))
        i += 1
    print(sum(sieve))
""",
    lambda r: ["20", "1", "2", "3", "100", "1000", str(r.randint(10**4, 10**5)), str(r.randint(10**5, 10**6)),
               "999983", "3000000", str(r.randint(2 * 10**6, 3 * 10**6))],
    brute="""import sys
n = int(sys.stdin.read())
c = 0
for x in range(2, n + 1):
    if all(x % p for p in range(2, int(x ** 0.5) + 1)):
        c += 1
print(c)
""",
    brute_if=lambda text: int(text) <= 200_000,
)

# ---------------------------------------------------------------- 20
def gen_bigadd(r):
    def num(length):
        return str(r.randint(1, 9)) + "".join(r.choice(string.digits) for _ in range(length - 1))

    return ["123456789123456789 987654321987654321", "0 0", "9999 1", "5 0"] + [f"{num(r.randint(1, 40))} {num(r.randint(1, 40))}" for _ in range(5)] + [
        f"{num(40000)} {num(40000)}", f"{'9' * 45000} 1", f"{num(30000)} {num(5)}"]


problem(
    "OB-20", "Katta sonlarni qo‘shish", "O‘rta",
    "Ikki manfiy bo‘lmagan butun A va B son berilgan. Ular juda uzun — standart butun turlariga sig‘maydi. "
    "A + B ni chiqaring.",
    "Bitta qatorda A va B (boshida ortiqcha nollar yo‘q).",
    "A + B.",
    "A va B uzunligi 1 dan 45 000 raqamgacha.",
    """import sys
a, b = sys.stdin.read().split()
a, b = a[::-1], b[::-1]
out = []
carry = 0
for i in range(max(len(a), len(b))):
    s = carry + (ord(a[i]) - 48 if i < len(a) else 0) + (ord(b[i]) - 48 if i < len(b) else 0)
    out.append(chr(s % 10 + 48))
    carry = s // 10
if carry:
    out.append(chr(carry + 48))
print("".join(reversed(out)))
""",
    gen_bigadd,
)

# ---------------------------------------------------------------- 21
def gen_coins(r):
    def case(n, s, hi):
        coins = set(r.randint(2, hi) for _ in range(n))
        if r.random() < 0.6:
            coins.add(1)  # aks holda tasodifiy testlarning ko'pida javob -1 bo'lib qoladi
        coins = sorted(coins)
        return f"{len(coins)} {s}\n{arr(coins)}"

    return ["3 11\n1 2 5", "1 3\n2", "2 0\n3 7", "3 30\n4 9 25", "2 7\n2 4"] + [case(r.randint(1, 5), r.randint(1, 200), 30) for _ in range(4)] + [
        case(10, 5 * 10**4, 1000), case(3, 49999, 7)]


problem(
    "OB-21", "Tangalar", "Qiyin",
    "Bankomatda n xil nominaldagi tangalar bor, har biridan cheksiz ko‘p. S summani eng kam sonli tanga bilan "
    "berish kerak. Tangalarning eng kam sonini chiqaring, agar S ni aniq berib bo‘lmasa −1 chiqaring.",
    "Birinchi qatorda n va S, ikkinchi qatorda n ta turli nominal.",
    "Bitta son.",
    "1 ≤ n ≤ 10, 0 ≤ S ≤ 5·10^4, 1 ≤ nominal ≤ 1000",
    """import sys
d = sys.stdin.read().split()
n, s = int(d[0]), int(d[1])
coins = list(map(int, d[2:2 + n]))
INF = float("inf")
dp = [0] + [INF] * s
for c in coins:
    for v in range(c, s + 1):
        if dp[v - c] + 1 < dp[v]:
            dp[v] = dp[v - c] + 1
print(dp[s] if dp[s] != INF else -1)
""",
    gen_coins,
)

# ---------------------------------------------------------------- 22
problem(
    "OB-22", "Zinapoya", "Qiyin",
    "Zinapoya n ta pog‘onadan iborat. Bir qadamda 1, 2 yoki 3 pog‘ona ko‘tarilish mumkin. Pastdan (0-pog‘ona) "
    "n-pog‘onaga necha xil usulda chiqish mumkin? Javob katta bo‘lishi mumkin, uni 10^9 + 7 ga bo‘lgandagi qoldiqni chiqaring.",
    "Bitta son n.",
    "Bitta son.",
    "1 ≤ n ≤ 10^6",
    """import sys
n = int(sys.stdin.read())
M = 10**9 + 7
a, b, c = 1, 0, 0  # f(0), f(-1), f(-2)
for _ in range(n):
    a, b, c = (a + b + c) % M, a, b
print(a)
""",
    lambda r: ["4", "1", "2", "3", "10", "50", str(r.randint(100, 1000)), str(r.randint(10**4, 10**5)), "1000000", str(r.randint(5 * 10**5, 10**6))],
    brute="""import sys
from functools import lru_cache
sys.setrecursionlimit(10000)
n = int(sys.stdin.read())
@lru_cache(None)
def f(k):
    if k < 0: return 0
    if k == 0: return 1
    return f(k - 1) + f(k - 2) + f(k - 3)
print(f(n) % (10**9 + 7))
""",
    brute_if=lambda text: int(text) <= 3_000,
)

# ---------------------------------------------------------------- 23
def gen_lcs(r):
    def s(n, alpha):
        return "".join(r.choice(alpha) for _ in range(n))

    return ["abcbdab\nbdcaba", "a\nb", "abc\nabc", "x\nxxxxx"] + [f"{s(r.randint(1, 15), 'abc')}\n{s(r.randint(1, 15), 'abc')}" for _ in range(5)] + [
        f"{s(1000, 'acgt')}\n{s(1000, 'acgt')}", f"{s(1000, string.ascii_lowercase)}\n{s(900, string.ascii_lowercase)}"]


problem(
    "OB-23", "Umumiy qism ketma-ketlik", "Qiyin",
    "Ikki satr berilgan. Ikkalasida ham qism ketma-ketlik sifatida uchraydigan eng uzun satr uzunligini toping. "
    "Qism ketma-ketlik — satrdan ba’zi belgilarni (ehtimol hech birini) o‘chirib, qolganlarining tartibini "
    "o‘zgartirmasdan hosil qilingan satr.",
    "Ikki qatorda kichik lotin harflaridan iborat ikki satr.",
    "Bitta son.",
    "Satrlar uzunligi 1 dan 1000 gacha.",
    """import sys
a, b = sys.stdin.read().split()
prev = [0] * (len(b) + 1)
for ch in a:
    cur = [0]
    for j, bj in enumerate(b):
        cur.append(prev[j] + 1 if ch == bj else (cur[j] if cur[j] > prev[j + 1] else prev[j + 1]))
    prev = cur
print(prev[-1])
""",
    gen_lcs,
    brute="""import sys
from functools import lru_cache
sys.setrecursionlimit(100000)
a, b = sys.stdin.read().split()
@lru_cache(None)
def f(i, j):
    if i == len(a) or j == len(b): return 0
    if a[i] == b[j]: return 1 + f(i + 1, j + 1)
    return max(f(i + 1, j), f(i, j + 1))
print(f(0, 0))
""",
    brute_if=lambda text: len(text) <= 200,
)

# ---------------------------------------------------------------- 24
def gen_maze(r):
    def case(n, m, wall):
        g = [["#" if r.random() < wall else "." for _ in range(m)] for _ in range(n)]
        cells = [(i, j) for i in range(n) for j in range(m)]
        (si, sj), (ei, ej) = r.sample(cells, 2)
        g[si][sj], g[ei][ej] = "S", "E"
        return f"{n} {m}\n" + "\n".join("".join(row) for row in g)

    snake = ["S" + "." * 199] + [("#" * 199 + ".") if i % 4 == 1 else ("." * 200) if i % 2 == 0 else ("." + "#" * 199) for i in range(1, 199)] + ["." * 199 + "E"]
    return ["3 4\nS..#\n.#..\n...E", "1 2\nSE", "2 2\nS#\n#E", "3 3\nS#.\n.#.\n.#E"] + [case(r.randint(2, 10), r.randint(2, 10), 0.3) for _ in range(5)] + [
        case(200, 200, 0.25), "200 200\n" + "\n".join(snake)]


problem(
    "OB-24", "Labirint", "Qiyin",
    "n×m o‘lchamli labirint berilgan: '.' — bo‘sh katak, '#' — devor, 'S' — boshlang‘ich, 'E' — chiqish katagi. "
    "Har qadamda yuqori, past, chap yoki o‘ng qo‘shni bo‘sh katakka o‘tish mumkin. S dan E gacha eng kam qadamlar "
    "sonini toping; yetib bo‘lmasa −1 chiqaring.",
    "Birinchi qatorda n va m, keyingi n qatorda labirint.",
    "Bitta son.",
    "1 ≤ n, m ≤ 200",
    """import sys
from collections import deque
d = sys.stdin.read().split()
n, m = int(d[0]), int(d[1])
g = d[2:2 + n]
for i in range(n):
    j = g[i].find("S")
    if j >= 0: s = (i, j)
    j = g[i].find("E")
    if j >= 0: e = (i, j)
dist = [[-1] * m for _ in range(n)]
dist[s[0]][s[1]] = 0
dq = deque([s])
while dq:
    x, y = dq.popleft()
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if 0 <= nx < n and 0 <= ny < m and g[nx][ny] != "#" and dist[nx][ny] < 0:
            dist[nx][ny] = dist[x][y] + 1
            dq.append((nx, ny))
print(dist[e[0]][e[1]])
""",
    gen_maze,
)

# ---------------------------------------------------------------- 25
def gen_islands(r):
    def case(n, m, p):
        return f"{n} {m}\n" + "\n".join("".join("1" if r.random() < p else "0" for _ in range(m)) for _ in range(n))

    return ["4 5\n11000\n11011\n00100\n00011", "1 1\n0", "1 1\n1", "3 3\n101\n010\n101"] + [case(r.randint(1, 10), r.randint(1, 10), 0.45) for _ in range(5)] + [
        case(250, 250, 0.4), case(250, 250, 0.6)]


problem(
    "OB-25", "Orollar", "Qiyin",
    "n×m xarita berilgan: '1' — quruqlik, '0' — suv. Yon tomonlari (yuqori, past, chap, o‘ng) bilan tutashgan "
    "quruqlik kataklari bitta orolni tashkil qiladi. Xaritada nechta orol borligini toping.",
    "Birinchi qatorda n va m, keyingi n qatorda 0 va 1 lardan iborat satrlar.",
    "Bitta son — orollar soni.",
    "1 ≤ n, m ≤ 250",
    """import sys
d = sys.stdin.read().split()
n, m = int(d[0]), int(d[1])
g = [list(row) for row in d[2:2 + n]]
count = 0
for i in range(n):
    for j in range(m):
        if g[i][j] == "1":
            count += 1
            g[i][j] = "0"
            stack = [(i, j)]
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < n and 0 <= ny < m and g[nx][ny] == "1":
                        g[nx][ny] = "0"
                        stack.append((nx, ny))
print(count)
""",
    gen_islands,
)

# ---------------------------------------------------------------- 26
def gen_knapsack(r):
    def case(n, cap, wmax, vmax):
        items = [f"{r.randint(1, wmax)} {r.randint(1, vmax)}" for _ in range(n)]
        return f"{n} {cap}\n" + "\n".join(items)

    return ["4 7\n1 1\n3 4\n4 5\n5 7", "1 5\n6 10", "1 5\n5 10", "3 0\n1 1\n2 2\n3 3"] + [case(r.randint(1, 12), r.randint(1, 40), 15, 50) for _ in range(5)] + [
        case(100, 10**4, 1000, 10**6), case(100, 5000, 100, 10**4)]


problem(
    "OB-26", "Sayohat ryukzagi", "Qiyin",
    "Sayohatchida sig‘imi W bo‘lgan ryukzak va n ta buyum bor; i-buyumning og‘irligi w_i, qiymati v_i. Har bir "
    "buyumni ko‘pi bilan bir marta olish mumkin. Umumiy og‘irlik W dan oshmasligi sharti bilan olingan buyumlar "
    "qiymatlari yig‘indisini maksimal qiling.",
    "Birinchi qatorda n va W, keyingi n qatorda w_i v_i.",
    "Bitta son — maksimal qiymat.",
    "1 ≤ n ≤ 100, 0 ≤ W ≤ 10^4, 1 ≤ w_i ≤ 1000, 1 ≤ v_i ≤ 10^6",
    """import sys
d = sys.stdin.read().split()
n, cap = int(d[0]), int(d[1])
dp = [0] * (cap + 1)
for i in range(n):
    w, v = int(d[2 + 2 * i]), int(d[3 + 2 * i])
    if w > cap:
        continue
    # o'ngdan chapga: har bir buyum bir martadan
    for c in range(cap, w - 1, -1):
        cand = dp[c - w] + v
        if cand > dp[c]:
            dp[c] = cand
print(dp[cap])
""",
    gen_knapsack,
    brute="""import sys
d = sys.stdin.read().split()
n, cap = int(d[0]), int(d[1])
items = [(int(d[2 + 2 * i]), int(d[3 + 2 * i])) for i in range(n)]
best = 0
for mask in range(1 << n):
    w = v = 0
    for i in range(n):
        if mask >> i & 1:
            w += items[i][0]; v += items[i][1]
    if w <= cap:
        best = max(best, v)
print(best)
""",
    brute_if=lambda text: int(text.split()[0]) <= 15,
)

# ---------------------------------------------------------------- 27
def gen_components(r):
    def case(n, m):
        edges = [f"{r.randint(1, n)} {r.randint(1, n)}" for _ in range(m)]
        return f"{n} {m}\n" + "\n".join(edges) if m else f"{n} 0"

    return ["6 4\n1 2\n2 3\n4 5\n3 1", "1 0", "3 0", "2 1\n1 1"] + [case(r.randint(1, 15), r.randint(0, 10)) for _ in range(5)] + [
        case(10**4, 7000), case(5000, 7500)]


problem(
    "OB-27", "Shaharlar guruhlari", "Qiyin",
    "Mamlakatda n ta shahar (1 dan n gacha raqamlangan) va m ta ikki tomonlama yo‘l bor. Bir-biriga yo‘llar orqali "
    "(balki boshqa shaharlar orqali) yetib boriladigan shaharlar bitta guruhni tashkil qiladi. Guruhlar sonini toping. "
    "Yo‘l shaharni o‘zi bilan tutashtirishi yoki ikki shahar orasida bir nechta yo‘l bo‘lishi mumkin.",
    "Birinchi qatorda n va m, keyingi m qatorda yo‘l: u v.",
    "Bitta son — guruhlar soni.",
    "1 ≤ n ≤ 10^4, 0 ≤ m ≤ 10^4",
    """import sys
d = sys.stdin.read().split()
n, m = int(d[0]), int(d[1])
parent = list(range(n + 1))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
groups = n
for i in range(m):
    a, b = find(int(d[2 + 2 * i])), find(int(d[3 + 2 * i]))
    if a != b:
        parent[a] = b
        groups -= 1
print(groups)
""",
    gen_components,
)

# ---------------------------------------------------------------- 28
def gen_dijkstra(r):
    def case(n, m, wmax, connected=True):
        edges = []
        if connected:
            order = list(range(2, n + 1))
            r.shuffle(order)
            prev = 1
            for v in order:
                edges.append((prev, v, r.randint(1, wmax)))
                prev = v if r.random() < 0.5 else prev
        while len(edges) < m:
            edges.append((r.randint(1, n), r.randint(1, n), r.randint(1, wmax)))
        return f"{n} {len(edges)}\n" + "\n".join(f"{a} {b} {w}" for a, b, w in edges)

    return ["4 5\n1 2 4\n1 3 1\n3 2 2\n2 4 5\n3 4 10", "1 0", "2 0", "3 1\n1 2 5"] + [case(r.randint(2, 10), r.randint(1, 20), 20, r.random() < 0.7) for _ in range(5)] + [
        case(3000, 5000, 10**6), case(5000, 5500, 1000, False)]


problem(
    "OB-28", "Eng qisqa yo‘l", "Qiyin",
    "n ta shahar va m ta ikki tomonlama yo‘l berilgan, har bir yo‘lning uzunligi musbat butun son. 1-shahardan "
    "n-shaharga eng qisqa yo‘l uzunligini toping. Yetib bo‘lmasa −1 chiqaring.",
    "Birinchi qatorda n va m, keyingi m qatorda u v w (yo‘l u va v ni tutashtiradi, uzunligi w).",
    "Bitta son.",
    "1 ≤ n ≤ 5000, 0 ≤ m ≤ 10^4, 1 ≤ w ≤ 10^6",
    """import sys, heapq
d = sys.stdin.read().split()
n, m = int(d[0]), int(d[1])
adj = [[] for _ in range(n + 1)]
for i in range(m):
    a, b, w = int(d[2 + 3 * i]), int(d[3 + 3 * i]), int(d[4 + 3 * i])
    adj[a].append((b, w)); adj[b].append((a, w))
INF = float("inf")
dist = [INF] * (n + 1)
dist[1] = 0
pq = [(0, 1)]
while pq:
    du, u = heapq.heappop(pq)
    if du > dist[u]:
        continue
    for v, w in adj[u]:
        if du + w < dist[v]:
            dist[v] = du + w
            heapq.heappush(pq, (dist[v], v))
print(dist[n] if dist[n] < INF else -1)
""",
    gen_dijkstra,
    brute="""import sys
d = sys.stdin.read().split()
n, m = int(d[0]), int(d[1])
edges = [(int(d[2 + 3 * i]), int(d[3 + 3 * i]), int(d[4 + 3 * i])) for i in range(m)]
INF = float("inf")
dist = [INF] * (n + 1); dist[1] = 0
for _ in range(n):
    for a, b, w in edges:
        if dist[a] + w < dist[b]: dist[b] = dist[a] + w
        if dist[b] + w < dist[a]: dist[a] = dist[b] + w
print(dist[n] if dist[n] < INF else -1)
""",
)

# ---------------------------------------------------------------- 29
problem(
    "OB-29", "Eng uzun o‘suvchi qism ketma-ketlik", "Qiyin",
    "n ta sondan iborat ketma-ketlik berilgan. Undan ba’zi elementlarni o‘chirib (tartibni saqlagan holda) qat’iy "
    "o‘suvchi ketma-ketlik hosil qilish kerak. Hosil bo‘ladigan eng uzun ketma-ketlik uzunligini toping. "
    "n katta: O(n²) yechim vaqt limitiga sig‘maydi.",
    "Birinchi qatorda n, ikkinchi qatorda n ta son.",
    "Bitta son.",
    "1 ≤ n ≤ 10^5, |a_i| ≤ 10^4",
    """import sys
from bisect import bisect_left
d = sys.stdin.read().split()
tails = []
for x in map(int, d[1:1 + int(d[0])]):
    i = bisect_left(tails, x)
    if i == len(tails):
        tails.append(x)
    else:
        tails[i] = x
print(len(tails))
""",
    lambda r: ["8\n10 9 2 5 3 7 101 18", "1\n5", "5\n3 3 3 3 3", "6\n1 2 3 4 5 6", "6\n6 5 4 3 2 1"]
    + [arr_case([r.randint(-10, 10) for _ in range(r.randint(1, 60))]) for _ in range(4)]
    + [arr_case([r.randint(-10**4, 10**4) for _ in range(11000)]), arr_case(list(range(-5000, 6000)))],
    brute="""import sys
d = sys.stdin.read().split()
a = list(map(int, d[1:1 + int(d[0])]))
f = [1] * len(a)
for i in range(len(a)):
    for j in range(i):
        if a[j] < a[i] and f[j] + 1 > f[i]:
            f[i] = f[j] + 1
print(max(f))
""",
)

# ---------------------------------------------------------------- 30
def gen_topo(r):
    def case(n, m, acyclic=True):
        perm = list(range(1, n + 1))
        r.shuffle(perm)
        pos = {v: i for i, v in enumerate(perm)}
        edges = set()
        tries = 0
        while len(edges) < m and tries < m * 20:
            tries += 1
            a, b = r.sample(range(1, n + 1), 2) if n > 1 else (1, 1)
            if a == b:
                continue
            if acyclic and pos[a] > pos[b]:
                a, b = b, a
            edges.add((a, b))
        edges = list(edges)
        if not acyclic and n > 2:
            a, b = r.sample(range(1, n + 1), 2)
            edges += [(a, b), (b, a)]
        return f"{n} {len(edges)}\n" + "\n".join(f"{a} {b}" for a, b in edges) if edges else f"{n} 0"

    return ["5 4\n1 2\n1 3\n3 4\n2 5", "1 0", "3 3\n1 2\n2 3\n3 1", "4 0", "3 1\n3 1"] + [case(r.randint(2, 10), r.randint(0, 12), r.random() < 0.7) for _ in range(4)] + [
        case(5000, 7000), case(3000, 6000, False)]


problem(
    "OB-30", "Vazifalar tartibi", "Qiyin",
    "n ta vazifa (1 dan n gacha) va m ta shart berilgan: «a b» — a vazifa b dan oldin bajarilishi kerak. Barcha "
    "shartlarni qanoatlantiradigan bajarish tartibini chiqaring. Bunday tartiblar bir nechta bo‘lsa, leksikografik "
    "eng kichigini chiqaring (har qadamda bajarish mumkin bo‘lganlarning eng kichik raqamlisi tanlanadi). "
    "Tartib mavjud bo‘lmasa (shartlar zid bo‘lsa), −1 chiqaring.",
    "Birinchi qatorda n va m, keyingi m qatorda a b.",
    "n ta son bo‘sh joy bilan, yoki −1.",
    "1 ≤ n ≤ 10^4, 0 ≤ m ≤ 10^4",
    """import sys, heapq
d = sys.stdin.read().split()
n, m = int(d[0]), int(d[1])
adj = [[] for _ in range(n + 1)]
indeg = [0] * (n + 1)
for i in range(m):
    a, b = int(d[2 + 2 * i]), int(d[3 + 2 * i])
    adj[a].append(b); indeg[b] += 1
pq = [v for v in range(1, n + 1) if indeg[v] == 0]
heapq.heapify(pq)
order = []
while pq:
    u = heapq.heappop(pq)
    order.append(u)
    for v in adj[u]:
        indeg[v] -= 1
        if indeg[v] == 0:
            heapq.heappush(pq, v)
print(" ".join(map(str, order)) if len(order) == n else -1)
""",
    gen_topo,
)


# ================================================================ build
def run(source, stdin_text, timeout=20):
    result = subprocess.run([sys.executable, "-I", "-c", source], input=stdin_text, capture_output=True,
                            text=True, encoding="utf-8", timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout.strip()


def build_prompt(index, spec, sample_in, sample_out):
    return (
        f"[{spec['key']}] {spec['title']} · Daraja: {spec['level']}\n\n"
        f"Sharti: {spec['statement']}\n\n"
        f"Kirish: {spec['input_fmt']}\n"
        f"Chiqish: {spec['output_fmt']}\n"
        f"Cheklovlar: {spec['limits']}\n\n"
        f"Namuna Input:\n{sample_in}\nNamuna Output:\n{sample_out}"
    )


def main():
    bank = []
    for index, spec in enumerate(PROBLEMS, start=1):
        rnd = random.Random(f"bilim-arena-{spec['key']}")
        inputs = spec["gen"](rnd)
        assert 8 <= len(inputs) <= 20, (spec["key"], len(inputs))
        cases = []
        for text in inputs:
            assert len(text) <= MAX_CASE_CHARS, (spec["key"], len(text))
            output = run(spec["ref"], text + "\n")
            assert output != "", (spec["key"], text[:80])
            assert len(output) <= MAX_CASE_CHARS, (spec["key"], len(output))
            if spec["brute"] and spec["brute_if"](text):
                brute = run(spec["brute"], text + "\n")
                assert brute == output, (spec["key"], text[:200], output, brute)
            cases.append({"input": text, "output": output})
        bank.append({
            "key": spec["key"],
            "prompt": build_prompt(index, spec, cases[0]["input"], cases[0]["output"]),
            "input_data": cases[0]["input"],
            "expected_output": cases[0]["output"],
            "test_cases": cases,
        })
        size = sum(len(c["input"]) + len(c["output"]) for c in cases)
        print(f"{spec['key']} {spec['title']}: {len(cases)} test, {size // 1024} KB"
              + (" (brute-force bilan solishtirildi)" if spec["brute"] else ""))
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(bank, handle, ensure_ascii=False, indent=1)
    print(f"\n{len(bank)} ta masala -> {OUTPUT} ({os.path.getsize(OUTPUT) // 1024} KB)")


if __name__ == "__main__":
    main()
