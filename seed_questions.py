"""Add 50 beginner programming and algorithm multiple-choice questions."""

from models import Question, db
from app import app


QUESTIONS = [
    ("A = 2 va B = 3. A + B qiymati nechaga teng?", "1", "5", "6", "23", "B"),
    ("A va B bitta qatorda, probel bilan berilsa, ularni Python'da qanday o‘qiymiz?", "a, b = map(int, input().split())", "a, b = int(input())", "a = input().split(int)", "a, b = input(int).map()", "A"),
    ("N natural sonining oxirgi raqamini topish uchun qaysi ifoda ishlatiladi?", "N // 10", "N * 10", "N % 10", "N / 10", "C"),
    ("N = 753 bo‘lsa, uning oxirgi raqami nechaga teng?", "7", "5", "53", "3", "D"),
    ("A = 34 va B = 43. Taqqoslash masalasi qanday belgi chiqaradi?", ">", "<", "=", "!=", "B"),
    ("12, 36 va -98 sonlarining eng kattasi qaysi?", "12", "36", "-98", "0", "B"),
    ("1, 2, 3, 4, 5 sonlaridan bittasini tashlab, qolgan to‘rttasining eng kichik yig‘indisi nechaga teng?", "10", "11", "14", "15", "A"),
    ("1, 2, 3, 4, 5 sonlaridan bittasini tashlab, qolgan to‘rttasining eng katta yig‘indisi nechaga teng?", "10", "12", "14", "15", "C"),
    ("A = -34 va B = -43 bo‘lsa, A va B ni taqqoslash natijasi qaysi?", "A > B, natija >", "A < B, natija <", "A = B, natija =", "Taqqoslab bo‘lmaydi", "A"),
    ("N = 1209 bo‘lsa, N % 10 natijasi nechaga teng?", "0", "9", "12", "120", "B"),
    ("A = 7 va B = -2 bo‘lsa, A + B nechaga teng?", "9", "5", "-5", "-9", "B"),
    ("-8, -3 va -12 sonlarining eng kattasi qaysi?", "-12", "-8", "-3", "12", "C"),
    ("2, 8, 4, 6, 10 sonlaridan bittasini tashlab, qolganlar yig‘indisining eng kichik qiymati qaysi?", "18", "20", "22", "28", "B"),
    ("A, B, C sonlarining eng kattasini Python'da qaysi ifoda topadi?", "max(A, B, C)", "min(A, B, C)", "sum(A, B, C)", "abs(A, B, C)", "A"),
    ("Ikki son tengligini tekshirish uchun qaysi operator ishlatiladi?", "=", "==", "!=", "=>", "B"),
    ("Python'da qoldiqni hisoblaydigan operator qaysi?", "/", "//", "%", "**", "C"),
    ("input() funksiyasi kiritilgan qiymatni dastlab qaysi turda qaytaradi?", "int", "float", "str", "bool", "C"),
    ("input().split() ifodasi odatda nima qaytaradi?", "Butun son", "Satrlar ro‘yxati", "Bitta mantiqiy qiymat", "Lug‘at", "B"),
    ("map(int, input().split()) nima vazifani bajaradi?", "Kiritilgan qiymatlarni butun songa aylantiradi", "Sonlarni matnga aylantiradi", "Faqat birinchi belgini oladi", "Sonlarni kamayish tartibida saralaydi", "A"),
    ("Alohida ikki qatorda berilgan A va B sonlarini o‘qishning to‘g‘ri usuli qaysi?", "a, b = map(int, input().split())", "a = int(input()); b = int(input())", "a, b = int(input())", "a = input(int, int)", "B"),
    ("abs(-17) qiymati nechaga teng?", "-17", "17", "0", "1", "B"),
    ("Python'da bir nechta qiymatning eng kichigini topish uchun qaysi funksiya ishlatiladi?", "max()", "sum()", "min()", "abs()", "C"),
    ("Python'da 2 ning 5-darajasini qaysi ifoda hisoblaydi?", "2 * 5", "2 ** 5", "2 // 5", "2 % 5", "B"),
    ("5 // 2 ifodasining qiymati nechaga teng?", "2", "2.5", "3", "1", "A"),
    ("A > B sharti rost yoki yolg‘onligini Python'da qaysi turdagi qiymat ifodalaydi?", "str", "list", "bool", "dict", "C"),
    ("Python'da o‘zgaruvchiga qiymat berish uchun qaysi belgi ishlatiladi?", "==", "=", "!=", "<=", "B"),
    ("A soni B dan katta bo‘lsa, > belgisini chiqarish sharti qanday yoziladi?", "if A > B:", "if A = B:", "if A < B:", "if A != B:", "A"),
    ("A va B tengligini tekshirishning to‘g‘ri sharti qaysi?", "if A = B:", "if A == B:", "if A => B:", "if A equals B:", "B"),
    ("A > B, aks holda A < B yoki A = B ekanini tekshirish uchun eng mos tuzilma qaysi?", "if / elif / else", "for / while", "try / import", "def / return", "A"),
    ("Python'da 'va' mantiqiy bog‘lovchisi qaysi?", "or", "not", "and", "in", "C"),
    ("for i in range(5) sikli necha marta bajariladi?", "4", "5", "6", "Cheksiz", "B"),
    ("1 dan 5 gacha bo‘lgan sonlar yig‘indisi nechaga teng?", "10", "12", "15", "20", "C"),
    ("Uchta sonning eng kichigini topish uchun qaysi ifoda to‘g‘ri?", "min(a, b, c)", "max(a, b, c)", "sum(a, b, c)", "abs(a, b, c)", "A"),
    ("[12, 36, -98] ro‘yxatidagi eng katta qiymatni qaysi ifoda qaytaradi?", "min([12, 36, -98])", "max([12, 36, -98])", "sum([12, 36, -98])", "len([12, 36, -98])", "B"),
    ("Sonlar ro‘yxatining eng katta va eng kichik qiymatlari ayirmasi qaysi ifoda bilan topiladi?", "max(nums) + min(nums)", "max(nums) - min(nums)", "sum(nums) - len(nums)", "abs(nums)", "B"),
    ("Beshta son yig‘indisidan ularning eng kattasini ayirsak nima hosil bo‘ladi?", "Eng kichik to‘rtta son yig‘indisi", "Faqat eng katta son", "Barcha sonlar ko‘paytmasi", "Eng katta va kichik son ayirmasi", "A"),
    ("Beshta son yig‘indisidan ularning eng kichigini ayirsak nima hosil bo‘ladi?", "Eng kichik to‘rtta son yig‘indisi", "Eng katta to‘rtta son yig‘indisi", "Barcha sonlar ko‘paytmasi", "Eng katta son", "B"),
    ("Taqqoslash masalasida A = B bo‘lsa, qanday belgi chiqariladi?", ">", "<", "=", "!", "C"),
    ("A = 9 va B = 4 bo‘lganda taqqoslash masalasi qanday belgi chiqaradi?", "<", "=", ">", "<=", "C"),
    ("A = -2 va B = 5 bo‘lsa, A va B ni odatiy son qiymatlari bo‘yicha taqqoslash natijasi qaysi?", ">", "<", "=", "Taqqoslab bo‘lmaydi", "B"),
    ("N = 10⁹ bo‘lsa, N % 10 qiymati nechaga teng?", "1", "9", "10", "0", "D"),
    ("N = 0 bo‘lsa, N % 10 qiymati nechaga teng?", "0", "1", "10", "Aniqlanmaydi", "A"),
    ("N = 905 bo‘lsa, oxirgi raqamni topuvchi N % 10 ifodasi nima qaytaradi?", "9", "0", "5", "95", "C"),
    ("Python'da ekranga qiymat chiqarish uchun qaysi funksiya ishlatiladi?", "input()", "print()", "output()", "write_int()", "B"),
    ("Python'da [5, 1, 4] ro‘yxatidagi eng kichik son qaysi?", "5", "1", "4", "0", "B"),
    ("[1, 2, 3, 4, 5] ro‘yxatining elementlari yig‘indisini qaytaradigan ifoda qaysi?", "len([1, 2, 3, 4, 5])", "max([1, 2, 3, 4, 5])", "sum([1, 2, 3, 4, 5])", "min([1, 2, 3, 4, 5])", "C"),
    ("N natural sonining oxirgi raqamini topishda N % 10 amalining natijasi qaysi oraliqda bo‘ladi?", "0 dan 9 gacha", "1 dan 10 gacha", "0 dan N gacha", "-N dan N gacha", "A"),
    ("Beshta qiymatni kichikdan kattaga tartiblash uchun qaysi Python ifodasi mos?", "sorted(nums)", "sum(nums)", "abs(nums)", "input(nums)", "A"),
    ("A va B ni taqqoslab >, < yoki = chiqarishda barcha holatlarni to‘g‘ri qamrab oladigan yondashuv qaysi?", "Faqat A > B ni tekshirish", "A > B, A < B va tenglik holatlarini tekshirish", "Faqat A < B ni tekshirish", "A va B ni qo‘shib, natijaga qarash", "B"),
    ("A = 1000000000 va B = 999999999 bo‘lsa, A + B nechaga teng?", "1999999999", "1999999989", "1000000001", "999999999", "A"),
]


def seed_questions():
    if len(QUESTIONS) != 50:
        raise RuntimeError(f"50 ta test kutilgan, {len(QUESTIONS)} ta topildi.")
    prompts = [item[0] for item in QUESTIONS]
    if len(set(prompts)) != len(prompts):
        raise RuntimeError("Test savollari ichida takroriy matn bor.")

    with app.app_context():
        existing_prompts = set(
            db.session.execute(
                db.select(Question.prompt).where(Question.question_type == "test")
            ).scalars()
        )
        added = 0
        for prompt, option_a, option_b, option_c, option_d, correct_option in QUESTIONS:
            if prompt in existing_prompts:
                continue
            db.session.add(
                Question(
                    question_type="test",
                    prompt=prompt,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_option=correct_option,
                )
            )
            added += 1
        db.session.commit()
        print(f"{added} ta yangi test qo‘shildi; jami {Question.query.filter_by(question_type='test').count()} ta test mavjud.")


if __name__ == "__main__":
    seed_questions()
