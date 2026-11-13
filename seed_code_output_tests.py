"""Seed 50 code-tracing questions with explicit Python snippets and input data."""

from app import app
from models import Question, db


QUESTIONS = [
    ("A va B berilgan. Dastur nimani chiqaradi?", "a, b = map(int, input().split())\nprint(a * 2 + b)", "3 5", "8", "11", "13", "16", "B"),
    ("N ning oxirgi raqami va yuzlik xonasini qo‘shish natijasini toping.", "n = int(input())\nprint(n % 10 + n // 100)", "753", "10", "37", "60", "357", "A"),
    ("Uchta sonning eng katta va eng kichik qiymatlari ayirmasi nima?", "a = list(map(int, input().split()))\nprint(max(a) - min(a))", "12 36 -98", "62", "122", "134", "146", "C"),
    ("Beshta son yig‘indisidan eng katta va eng kichik son ayirilsa, nima chiqadi?", "a = list(map(int, input().split()))\nprint(sum(a) - max(a) - min(a))", "1 2 3 4 5", "8", "9", "10", "11", "B"),
    ("Kod A va B ni taqqoslaydi. Natija qanday?", "a, b = map(int, input().split())\nif a > b:\n    print('>')\nelif a < b:\n    print('<')\nelse:\n    print('=')", "34 43", ">", "<", "=", "34", "B"),
    ("Uchta sondan eng kattasi chiqariladi. Natijani toping.", "a, b, c = map(int, input().split())\nprint(max(a, b, c))", "1000 1 3665", "1000", "1", "3665", "4666", "C"),
    ("Sikl yig‘indiga 1 dan 4 gacha bo‘lgan sonlarni qo‘shadi. Natija?", "s = 0\nfor i in range(1, 5):\n    s += i\nprint(s)", "—", "6", "10", "15", "4", "B"),
    ("Kod ro‘yxatdagi juft sonlar yig‘indisini chiqaradi. Natija?", "a = list(map(int, input().split()))\nprint(sum(x for x in a if x % 2 == 0))", "3 8 11 6 2", "8", "14", "16", "19", "C"),
    ("Sikl necha marta bajariladi? Dastur sanagichni chiqaradi.", "n = int(input())\nc = 0\nwhile n > 1:\n    c += 1\n    n -= 2\nprint(c)", "7", "2", "3", "4", "7", "B"),
    ("Satrning teskari ko‘rinishi nima bo‘ladi?", "s = input().strip()\nprint(s[::-1])", "olimpiada", "adaipmilo", "olimpiada", "adapmilo", "OLIMPIADA", "A"),
    ("A = 5, B = 2. Butun bo‘lish va qoldiq yig‘indisi nima?", "a, b = map(int, input().split())\nprint(a // b + a % b)", "5 2", "2", "3", "4", "5", "B"),
    ("Son raqamlarining yig‘indisi chiqariladi. Natija?", "n = int(input())\ns = 0\nwhile n:\n    s += n % 10\n    n //= 10\nprint(s)", "5082", "10", "15", "16", "582", "B"),
    ("Ro‘yxatning ikkinchi va oxirgi elementlari yig‘indisi nima?", "a = list(map(int, input().split()))\nprint(a[1] + a[-1])", "10 20 30 40", "40", "50", "60", "70", "C"),
    ("Kod faqat musbat sonlarni sanaydi. Natija?", "a = list(map(int, input().split()))\nprint(sum(1 for x in a if x > 0))", "-2 0 7 3 -1 5", "2", "3", "4", "6", "B"),
    ("Shart rost bo‘lsa, qaysi son chiqariladi?", "a, b = map(int, input().split())\nprint(a + b if a % 2 == 0 else a - b)", "8 3", "5", "8", "11", "24", "C"),
    ("Kod A dan B gacha bo‘lgan sonlar yig‘indisini chiqaradi. Natija?", "a, b = map(int, input().split())\nprint(sum(range(a, b + 1)))", "3 6", "15", "18", "21", "24", "B"),
    ("Kodni bajarganda ro‘yxat elementlari qanday tartibda chiqadi?", "a = list(map(int, input().split()))\na.sort()\nprint(*a)", "9 1 5 3", "9 5 3 1", "1 3 5 9", "1 5 3 9", "3 1 5 9", "B"),
    ("Dastur eng katta sonning indeksini (0 dan boshlab) chiqaradi.", "a = list(map(int, input().split()))\nprint(a.index(max(a)))", "4 9 2 9", "0", "1", "2", "3", "B"),
    ("Ushbu kod nimani chiqaradi?", "a, b = map(int, input().split())\nprint((a + b) // 2)", "7 12", "9", "9.5", "10", "19", "A"),
    ("Kod 3 ga bo‘linadigan sonlarni chiqaradi. Chiqish qaysi?", "a = list(map(int, input().split()))\nprint(*[x for x in a if x % 3 == 0])", "2 3 6 7 9", "2 7", "3 6 9", "3 6 7 9", "2 3 6 9", "B"),
    ("Satrda nechta 'a' harfi bor?", "s = input().strip()\nprint(s.count('a'))", "ananas", "2", "3", "4", "6", "B"),
    ("Uchta son o‘sish tartibida chiqarilsa, natija qanday?", "a = list(map(int, input().split()))\nprint(*sorted(a))", "7 -2 4", "-2 4 7", "7 4 -2", "-2 7 4", "4 -2 7", "A"),
    ("Kodning natijasini toping.", "n = int(input())\nprint(n // 10 % 10)", "4827", "4", "8", "2", "7", "C"),
    ("Quyidagi sikl yakunida x ning qiymati nima?", "x = 0\nfor i in range(5):\n    if i % 2 == 0:\n        x += i\nprint(x)", "—", "4", "5", "6", "10", "C"),
    ("Ikki satr yonma-yon birlashtirilib, uzunligi chiqariladi.", "a = input().strip()\nb = input().strip()\nprint(len(a + b))", "kitob\nolam", "8", "9", "10", "11", "B"),
    ("A va B orasidagi barcha toq sonlar nechta? Chegaralar kiritilgan.", "a, b = map(int, input().split())\nprint(sum(1 for x in range(a, b + 1) if x % 2))", "2 9", "3", "4", "5", "6", "B"),
    ("Kod 0 kiritilguncha sonlarni qo‘shadi. Natija?", "s = 0\nwhile True:\n    n = int(input())\n    if n == 0:\n        break\n    s += n\nprint(s)", "4\n-1\n7\n0", "9", "10", "11", "12", "B"),
    ("Ro‘yxatdagi takrorlanmaydigan qiymatlar soni nechta?", "a = list(map(int, input().split()))\nprint(len(set(a)))", "1 2 1 3 2 4", "3", "4", "5", "6", "B"),
    ("Kodning ekrandagi natijasi nima?", "a, b, c = map(int, input().split())\nprint(max(a + b, b + c))", "4 7 2", "9", "11", "13", "14", "B"),
    ("Berilgan N uchun 1² + 2² + ... + N² qiymatini toping.", "n = int(input())\nprint(sum(i * i for i in range(1, n + 1)))", "4", "14", "20", "30", "36", "C"),
    ("Kod raqamlarni ko‘paytiradi. Natijani toping.", "n = int(input())\np = 1\nwhile n:\n    p *= n % 10\n    n //= 10\nprint(p)", "234", "9", "20", "24", "36", "C"),
    ("Quyidagi kod nechani chiqaradi?", "a, b = map(int, input().split())\nwhile b:\n    a, b = b, a % b\nprint(a)", "48 18", "3", "6", "12", "18", "B"),
    ("Kod ro‘yxatni bir pozitsiyaga chapga aylantiradi. Natija?", "a = input().split()\na = a[1:] + a[:1]\nprint(*a)", "qizil yashil ko‘k", "qizil yashil ko‘k", "yashil ko‘k qizil", "ko‘k qizil yashil", "yashil qizil ko‘k", "B"),
    ("Koddagi shartdan keyin qaysi qiymat chiqadi?", "x = int(input())\nprint('YES' if x % 2 == 0 and x % 3 == 0 else 'NO')", "18", "NO", "YES", "6", "True", "B"),
    ("Ro‘yxatdagi eng kichik musbat son chiqariladi.", "a = list(map(int, input().split()))\nprint(min(x for x in a if x > 0))", "-5 8 3 0 11", "0", "3", "5", "8", "B"),
    ("Koddagi print natijasini toping.", "a, b, c = map(int, input().split())\nprint(a * b + c * c)", "2 3 4", "14", "20", "22", "26", "C"),
    ("Satrning katta harflarga o‘tkazilgan ko‘rinishi nima?", "s = input().strip()\nprint(s.upper())", "PyThOn", "python", "Python", "PYTHON", "pYtHoN", "C"),
    ("Kod nechta raqamni sanaydi?", "s = input().strip()\nprint(sum(ch.isdigit() for ch in s))", "a1b23c", "2", "3", "4", "6", "B"),
    ("Kod ro‘yxatdagi qo‘shni elementlar farqlarining modulini qo‘shadi.", "a = list(map(int, input().split()))\nprint(sum(abs(a[i] - a[i - 1]) for i in range(1, len(a))))", "2 7 3", "7", "9", "10", "12", "B"),
    ("Ro‘yxatning oxirgi va birinchi elementi ayirmasi nimaga teng?", "a = list(map(int, input().split()))\nprint(a[-1] - a[0])", "5 12 20 8", "3", "7", "12", "15", "A"),
    ("Kod berilgan sonning ikkilik yozuvidagi 1 lar sonini chiqaradi.", "n = int(input())\nprint(bin(n).count('1'))", "13", "2", "3", "4", "13", "B"),
    ("Quyidagi kod A+B ni qoldiq bilan chiqaradi.", "a, b, m = map(int, input().split())\nprint((a + b) % m)", "17 9 7", "2", "4", "5", "26", "C"),
    ("Kod ro‘yxatdagi ikkinchi eng katta turli qiymatni topadi.", "a = sorted(set(map(int, input().split())))\nprint(a[-2])", "4 9 2 9 7", "4", "7", "9", "2", "B"),
    ("Quyidagi kodning chiqishi nima?", "n = int(input())\nfor i in range(1, n + 1):\n    if n % i == 0:\n        print(i, end=' ')", "12", "1 2 3 4 6 12", "1 2 4 6 12", "2 3 4 6", "12", "A"),
    ("Koddagi if shartlari natijasida qaysi so‘z chiqadi?", "a, b = map(int, input().split())\nif a > b and a % 2 == 0:\n    print('A')\nelif b % 2:\n    print('B')\nelse:\n    print('C')", "8 5", "A", "B", "C", "8", "A"),
    ("Ro‘yxat elementlari indekslari bilan ko‘paytirilib yig‘iladi.", "a = list(map(int, input().split()))\nprint(sum(i * x for i, x in enumerate(a)))", "3 5 2 4", "17", "19", "21", "23", "C"),
    ("Satr palindrom bo‘lsa YES, aks holda NO chiqariladi.", "s = input().strip()\nprint('YES' if s == s[::-1] else 'NO')", "level", "NO", "YES", "level", "True", "B"),
    ("Kod sonning raqamlari ichidagi eng kattasini topadi.", "n = input().strip()\nprint(max(n))", "50729", "5", "7", "9", "29", "C"),
    ("A, B, C uchburchak tomonlari. Kod eng uzun tomon va qolganlari yig‘indisini tekshiradi.", "a = sorted(map(int, input().split()))\nprint('YES' if a[0] + a[1] > a[2] else 'NO')", "3 4 8", "YES", "NO", "15", "4", "B"),
    ("Kod 1 dan N gacha 5 ga bo‘linadigan, ammo 3 ga bo‘linmaydigan sonlarni sanaydi.", "n = int(input())\nprint(sum(1 for x in range(1, n + 1) if x % 5 == 0 and x % 3 != 0))", "30", "3", "4", "5", "6", "B"),
]


def seed_questions():
    if len(QUESTIONS) != 50:
        raise RuntimeError(f"50 ta kod testi kutilgan, {len(QUESTIONS)} ta topildi.")
    prompts = [item[0] for item in QUESTIONS]
    if len(set(prompts)) != len(prompts):
        raise RuntimeError("Kod testlari ichida takroriy savol matni bor.")

    with app.app_context():
        existing_prompts = set(
            db.session.execute(
                db.select(Question.prompt).where(Question.question_type == "code_output")
            ).scalars()
        )
        added = 0
        for prompt, code, input_data, option_a, option_b, option_c, option_d, correct in QUESTIONS:
            if prompt in existing_prompts:
                continue
            db.session.add(
                Question(
                    question_type="code_output",
                    prompt=prompt,
                    code_snippet=code,
                    input_data="" if input_data == "—" else input_data,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_option=correct,
                )
            )
            added += 1
        db.session.commit()
        total = Question.query.filter_by(question_type="code_output").count()
        print(f"{added} ta yangi kod natijasi testi qo‘shildi; jami {total} ta mavjud.")


if __name__ == "__main__":
    seed_questions()
