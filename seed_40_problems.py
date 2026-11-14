"""Seed the 40 beginner programming problems with private judge tests."""

import json

from app import app
from models import Question, db


PROBLEMS = [
    ("Ikki son yig‘indisi", "A va B butun sonlari berilgan. A + B ni chiqaring.", [("5 7", "12"), ("-10 3", "-7"), ("1000000000 -1000000000", "0")]),
    ("Katta yoki kichik", "A va B sonlarini taqqoslab, mos ravishda >, < yoki = belgisini chiqaring.", [("10 20", "<"), ("5 5", "="), ("-2 -9", ">")]),
    ("To‘rtburchak perimetri va yuzi", "Tomonlari a va b bo‘lgan to‘g‘ri to‘rtburchak yuzini va perimetrini shu tartibda chiqaring.", [("4 5", "20 18"), ("1 1", "1 4"), ("10000 2", "20000 20004")]),
    ("Direktor tashrifi", "N ta partaning har birida P tadan o‘quvchi bor. Jami o‘quvchilar sonini toping.", [("15 2", "30"), ("1 1", "1"), ("1000000000 1000000000", "1000000000000000000")]),
    ("Olma taqsimoti", "N o‘quvchi K ta olmani teng bo‘lishdi. Har biriga tekkan olma soni va qoldiqni chiqaring.", [("3 14", "4 2"), ("5 23", "4 3"), ("7 7", "1 0")]),
    ("Oxirgi raqam", "Natural N sonining oxirgi raqamini toping.", [("12345", "5"), ("9", "9"), ("100", "0"), ("1000000000000000000", "0")]),
    ("O‘nliklar xonasidagi raqam", "Ikki xonali N sonining o‘nliklar xonasidagi raqamini toping.", [("74", "7"), ("10", "1"), ("99", "9")]),
    ("Uch xonali son raqamlari yig‘indisi", "Uch xonali N sonining raqamlari yig‘indisini hisoblang.", [("482", "14"), ("100", "1"), ("999", "27")]),
    ("Vaqtni soniyalarga o‘tkazish", "Kun boshidan beri o‘tgan H soat, M daqiqa va S soniyani jami soniyaga o‘tkazing.", [("1 2 30", "3750"), ("0 0 0", "0"), ("23 59 59", "86399")]),
    ("Keyingi juft son", "N dan katta bo‘lgan eng kichik juft sonni chiqaring.", [("7", "8"), ("8", "10"), ("1", "2")]),
    ("Juft yoki toq", "N juft bo‘lsa Juft, aks holda Toq so‘zini chiqaring.", [("15", "Toq"), ("-8", "Juft"), ("0", "Juft")]),
    ("Uchta sondan eng kattasi", "A, B, C sonlari orasidan eng kattasini toping.", [("12 45 23", "45"), ("-5 -2 -9", "-2"), ("7 7 3", "7")]),
    ("Kabisa yili", "Yil 400 ga bo‘linsa yoki 4 ga bo‘linib 100 ga bo‘linmasa Kabisa yili, aks holda Kabisa yili emas deb chiqaring.", [("2024", "Kabisa yili"), ("1900", "Kabisa yili emas"), ("2000", "Kabisa yili")]),
    ("Uchburchak mavjudligi", "a, b, c kesmalardan uchburchak yasash mumkin bo‘lsa YES, aks holda NO chiqaring.", [("3 4 5", "YES"), ("1 2 3", "NO"), ("5 5 9", "YES")]),
    ("Fasllar", "1–12 oralig‘idagi oy raqamiga mos faslni chiqaring: qish (12,1,2), bahor (3,4,5), yoz (6,7,8), kuz (9,10,11).", [("4", "Bahor"), ("12", "Qish"), ("8", "Yoz"), ("10", "Kuz")]),
    ("Shaxmat doskasi katagi rangi", "(1,1) katak qora bo‘lsa, x va y koordinatali katak rangini Qora yoki Oq deb chiqaring.", [("1 2", "Oq"), ("1 1", "Qora"), ("8 8", "Qora"), ("3 6", "Oq")]),
    ("Poyezd chiptasi", "6 yoshgacha bepul, 7–18 yosh 5000 so‘m, 18 dan kattalar 10000 so‘m to‘laydi. Narxni chiqaring.", [("12", "5000"), ("6", "0"), ("18", "5000"), ("19", "10000")]),
    ("Kvadrat tenglama ildizlari soni", "a ≠ 0 bo‘lgan ax²+bx+c=0 tenglama nechta haqiqiy ildizga ega ekanini (0, 1 yoki 2) toping.", [("1 -3 2", "2"), ("1 2 1", "1"), ("1 0 1", "0"), ("-1 0 4", "2")]),
    ("Palindrom to‘rt xonali son", "To‘rt xonali N soni palindrom bo‘lsa YES, aks holda NO chiqaring.", [("1221", "YES"), ("1234", "NO"), ("9009", "YES")]),
    ("Harorat holati", "T ≤ 0 bo‘lsa Muz, 0 < T < 100 bo‘lsa Suyuq, T ≥ 100 bo‘lsa Bug' chiqaring.", [("105", "Bug'"), ("0", "Muz"), ("25", "Suyuq"), ("100", "Bug'")]),
    ("1 dan N gacha sonlar yig‘indisi", "1+2+...+N yig‘indisini toping.", [("5", "15"), ("1", "1"), ("1000000", "500000500000")]),
    ("Faktorial hisoblash", "N! ni hisoblang (0! = 1).", [("5", "120"), ("0", "1"), ("20", "2432902008176640000")]),
    ("Juft sonlar yig‘indisi", "A dan B gacha (chegaralar bilan) bo‘lgan juft sonlar yig‘indisini toping.", [("2 8", "20"), ("1 1", "0"), ("4 9", "18")]),
    ("Sonning raqamlari soni", "Natural N sonining raqamlari sonini aniqlang.", [("45890", "5"), ("1", "1"), ("1000000000000000000", "19")]),
    ("Sonning raqamlari yig‘indisi", "Natural N sonining barcha raqamlari yig‘indisini toping.", [("12345", "15"), ("9", "9"), ("1000000000000000000", "1")]),
    ("Teskari son", "Natural N raqamlarini teskari yozib hosil bo‘lgan sonni chiqaring; boshidagi nollar tushib qolsin.", [("1200", "21"), ("7", "7"), ("1001", "1001"), ("987654321", "123456789")]),
    ("Darajaga ko‘tarish", "A ning B-darajasini sikl yordamida hisoblang.", [("2 10", "1024"), ("20 0", "1"), ("3 5", "243"), ("20 15", "32768000000000000000")]),
    ("Fibonachchi soni", "F1=1, F2=1, Fn=Fn-1+Fn-2 ketma-ketligining N-hadini toping.", [("7", "13"), ("1", "1"), ("2", "1"), ("45", "1134903170")]),
    ("Nol kiritilguncha yig‘indi", "0 kiritilguncha berilgan butun sonlar yig‘indisini toping. 0 yig‘indiga qo‘shilmaydi.", [("5 10 -3 0", "12"), ("0", "0"), ("-5 -2 7 0", "0")]),
    ("Karra jadvali", "N sonining 1 dan 10 gacha ko‘paytmalarini bir qatorda chiqaring.", [("3", "3 6 9 12 15 18 21 24 27 30"), ("1", "1 2 3 4 5 6 7 8 9 10"), ("10", "10 20 30 40 50 60 70 80 90 100")]),
    ("Natural bo‘luvchilar soni", "N natural sonining musbat bo‘luvchilari sonini toping.", [("12", "6"), ("1", "1"), ("36", "9"), ("97", "2")]),
    ("Tub sonni aniqlash", "N tub bo‘lsa Tub, aks holda Murakkab deb chiqaring. N ≥ 2.", [("17", "Tub"), ("2", "Tub"), ("49", "Murakkab"), ("1000000000", "Murakkab")]),
    ("EKUB", "A va B natural sonlarining eng katta umumiy bo‘luvchisini toping.", [("24 36", "12"), ("7 13", "1"), ("1000000000 250000000", "250000000")]),
    ("EKUK", "A va B natural sonlarining eng kichik umumiy karralisini toping.", [("12 18", "36"), ("7 13", "91"), ("1000000 999999", "999999000000")]),
    ("Mukammal son", "O‘zidan boshqa musbat bo‘luvchilari yig‘indisi o‘ziga teng bo‘lsa YES, aks holda NO chiqaring.", [("28", "YES"), ("1", "NO"), ("12", "NO"), ("496", "YES")]),
    ("Ikkining darajasimi?", "N soni 2 ning butun darajasi bo‘lsa YES, aks holda NO chiqaring.", [("64", "YES"), ("1", "YES"), ("0", "NO"), ("1000000000000000000", "NO")]),
    ("Eng katta raqam", "Natural N raqamlari orasidagi eng katta raqamni toping.", [("39472", "9"), ("111", "1"), ("908070", "9")]),
    ("Armstrong soni", "Uch xonali N raqamlarining kublari yig‘indisi N ga teng bo‘lsa YES, aks holda NO chiqaring.", [("153", "YES"), ("370", "YES"), ("100", "NO"), ("407", "YES")]),
    ("Oraliqdagi tub sonlar soni", "A dan B gacha (chegaralar bilan) tub sonlar sonini hisoblang.", [("10 20", "4"), ("1 1", "0"), ("2 2", "1"), ("1 10", "4")]),
    ("Tub ko‘paytuvchilarga ajratish", "N murakkab sonini o‘sish tartibida tub ko‘paytuvchilariga ajratib chiqaring.", [("60", "2 2 3 5"), ("2", "2"), ("13", "13"), ("100", "2 2 5 5")]),
]


def seed_questions():
    if len(PROBLEMS) != 40:
        raise RuntimeError(f"40 ta masala kutilgan, {len(PROBLEMS)} ta topildi.")
    with app.app_context():
        existing = Question.query.filter_by(question_type="code_problem").all()
        added = updated = 0
        for index, (title, statement, cases) in enumerate(PROBLEMS, start=1):
            sample_input, sample_output = cases[0]
            input_note = "Sonlar 0 kiritilguncha o‘qiladi." if index == 29 else (
                "Qiymatlar standart kiritishdan namunadagi tartibda beriladi."
            )
            prompt = (
                f"{index}-masala: {title}\n\nSharti: {statement}\n\n"
                f"Input: {input_note}\n"
                "Output: Shartda so‘ralgan natijani standart chiqishga chiqaring.\n\n"
                f"Namuna Input:\n{sample_input}\nNamuna Output:\n{sample_output}"
            )
            question = next(
                (item for item in existing if item.prompt.startswith(f"{index}-masala: {title}\n\nSharti:")),
                None,
            )
            if question:
                question.prompt = prompt
                question.input_data = sample_input
                question.expected_output = sample_output
                question.test_cases_json = json.dumps(
                    [{"input": input_data, "output": output} for input_data, output in cases],
                    ensure_ascii=False,
                )
                updated += 1
                continue
            db.session.add(Question(
                question_type="code_problem",
                prompt=prompt,
                input_data=sample_input,
                expected_output=sample_output,
                test_cases_json=json.dumps(
                    [{"input": input_data, "output": output} for input_data, output in cases],
                    ensure_ascii=False,
                ),
            ))
            added += 1
        db.session.commit()
        print(
            f"{added} ta yangi masala qo‘shildi, {updated} tasi yangilandi; "
            f"kod yozish masalalari jami {Question.query.filter_by(question_type='code_problem').count()} ta."
        )


if __name__ == "__main__":
    seed_questions()
