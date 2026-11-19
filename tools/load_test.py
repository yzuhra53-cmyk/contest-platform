"""Yuklama sinovi: ko'p "virtual talaba" bir vaqtda kontest topshiradi.

Faqat Python standart kutubxonasi kerak (kamera/ekran rasmlari uchun OpenCV bo'lsa,
haqiqiyroq JPEG yasaladi). Har bir virtual talaba alohida oqimda:

  * kiradi (F.I.Sh. + guruh + HEMIS ID) va kontestni ochadi;
  * har 10 soniyada kamera kadri va ekran rasmi yuboradi (kuzatuv yoqilgan kontestda);
  * test kontestida javoblarni avtomatik saqlaydi;
  * kod kontestida ▶ Run bosadi va yechim yuboradi (avval xato, keyin to'g'ri),
    natija chiqquncha kutadi — tekshiruv navbati shu yerda o'lchanadi.

Ishga tushirish (loyiha papkasida, ustoz login/paroli muhit o'zgaruvchisida):

    (login va parol so‘raladi; yoki LOADTEST_ADMIN_USER / LOADTEST_ADMIN_PASSWORD bering)
    python tools/load_test.py --url https://<sayt>.onrender.com --students 50 --scenario coding --minutes 3

Sinov o'zi LT-001... talabalarini va «Yuklama sinovi» kontestini yaratadi, oxirida o'chiradi
(--keep bilan qoldiriladi). Haqiqiy kontest paytida ishga tushirmang.
"""

import argparse
import http.cookiejar
import io
import json
import getpass
import os
import random
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WRONG_SOLUTION = "print(0)"
FRAME_INTERVAL = 10


# ---------------------------------------------------------------- HTTP mijoz
class Client:
    def __init__(self, base_url, timeout=60):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None

    def request(self, method, path, data=None, headers=None, kind=None):
        """(status, matn, javob URL) qaytaradi va vaqtni statistikaga yozadi."""
        url = path if path.startswith("http") else self.base + path
        request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        started = time.perf_counter()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
                status, final = response.status, response.geturl()
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            status, final = error.code, url
        except Exception as error:  # noqa: BLE001 — tarmoq xatolari ham statistikaga tushsin
            STATS.record(kind or path, time.perf_counter() - started, f"ERR {type(error).__name__}")
            return 0, "", url
        STATS.record(kind or path, time.perf_counter() - started, status)
        match = re.search(r'name="csrf-token" content="([^"]+)"', body)
        if match:
            self.csrf = match.group(1)
        return status, body, final

    def get(self, path, kind=None):
        return self.request("GET", path, kind=kind)

    def post_form(self, path, fields, kind=None):
        fields = dict(fields, csrf_token=self.csrf or "")
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        return self.request("POST", path, data, {"Content-Type": "application/x-www-form-urlencoded"}, kind)

    def post_json(self, path, payload, kind=None):
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "X-CSRF-Token": self.csrf or ""}
        return self.request("POST", path, data, headers, kind)

    def post_multipart(self, path, fields, files, kind=None):
        boundary = uuid.uuid4().hex
        buffer = io.BytesIO()
        for name, value in fields.items():
            buffer.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, (filename, content) in files.items():
            buffer.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                         f"Content-Type: image/jpeg\r\n\r\n".encode())
            buffer.write(content + b"\r\n")
        buffer.write(f"--{boundary}--\r\n".encode())
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "X-CSRF-Token": self.csrf or ""}
        return self.request("POST", path, buffer.getvalue(), headers, kind)


# ---------------------------------------------------------------- statistika
class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.calls = {}
        self.verdicts = []
        self.notes = {}

    def record(self, kind, seconds, status):
        with self.lock:
            self.calls.setdefault(kind, []).append((seconds, status))

    def verdict(self, seconds, result):
        with self.lock:
            self.verdicts.append((seconds, result))

    def note(self, key):
        with self.lock:
            self.notes[key] = self.notes.get(key, 0) + 1

    def report(self):
        def pct(values, q):
            values = sorted(values)
            return values[min(len(values) - 1, int(q * len(values)))] if values else 0

        lines = [f"{'So‘rov':28} {'soni':>6} {'xato':>5} {'o‘rtacha':>9} {'p95':>8} {'max':>8}"]
        for kind, rows in sorted(self.calls.items()):
            times = [seconds for seconds, _ in rows]
            errors = sum(1 for _, status in rows if not (isinstance(status, int) and status < 400))
            lines.append(f"{kind:28} {len(rows):6d} {errors:5d} {statistics.mean(times):8.2f}s "
                         f"{pct(times, .95):7.2f}s {max(times):7.2f}s")
        if self.verdicts:
            times = [seconds for seconds, _ in self.verdicts]
            lines.append("")
            lines.append(f"Kod tekshiruvi (yuborishdan natijagacha): {len(times)} ta, o‘rtacha {statistics.mean(times):.1f}s, "
                         f"p95 {pct(times, .95):.1f}s, max {max(times):.1f}s")
            results = {}
            for _, result in self.verdicts:
                results[result] = results.get(result, 0) + 1
            lines.append("Natijalar: " + ", ".join(f"{name}: {count}" for name, count in sorted(results.items())))
        if self.notes:
            lines.append("Izohlar: " + ", ".join(f"{name}: {count}" for name, count in sorted(self.notes.items())))
        return "\n".join(lines)


STATS = Stats()


# ---------------------------------------------------------------- rasmlar
def make_jpegs():
    """(kamera kadri ~15 KB, ekran rasmi ~100 KB) — OpenCV bo'lsa haqiqiy JPEG."""
    try:
        import cv2
        import numpy as np

        rng = np.random.default_rng(1)
        camera = (rng.random((240, 320, 3)) * 60 + 90).astype("uint8")
        screen = np.full((576, 1024, 3), 245, dtype="uint8")
        for row in range(20, 560, 18):
            width = int(rng.integers(200, 980))
            screen[row:row + 9, 20:20 + width] = rng.integers(0, 120)
        screen = cv2.GaussianBlur(screen, (3, 3), 0)
        return (cv2.imencode(".jpg", camera, [cv2.IMWRITE_JPEG_QUALITY, 60])[1].tobytes(),
                cv2.imencode(".jpg", screen, [cv2.IMWRITE_JPEG_QUALITY, 45])[1].tobytes())
    except ImportError:
        header = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00"
        return header + os.urandom(15000), header + os.urandom(100000)


# ---------------------------------------------------------------- tayyorlash
def admin_client(args):
    user = os.environ.get("LOADTEST_ADMIN_USER") or input("Ustoz logini: ").strip()
    password = os.environ.get("LOADTEST_ADMIN_PASSWORD") or getpass.getpass("Ustoz paroli (ko‘rinmaydi): ")
    if not user or not password:
        raise SystemExit("Ustoz logini va paroli kerak.")
    admin = Client(args.url)
    admin.get("/admin/login", kind="setup")
    status, body, final = admin.post_form("/admin/login", {"username": user, "password": password}, kind="setup")
    if "/admin/login" in final:
        raise SystemExit("Ustoz sifatida kirib bo‘lmadi: login yoki parol noto‘g‘ri.")
    return admin


def setup(args, admin):
    print(f"Tayyorlanmoqda: {args.students} ta talaba va «Yuklama sinovi» kontesti…")
    admin.get("/admin/students", kind="setup")
    for index in range(1, args.students + 1):
        admin.post_form("/admin/students", {
            "hemis_id": f"LT-{index:03d}", "full_name": f"Yuklama Talaba {index:03d}", "group_name": "LOAD-TEST",
        }, kind="setup")
    _, page, _ = admin.get("/admin/contests", kind="setup")

    def column(block):
        match = re.search(rf'data-block="{block}".*?</section>', page, re.S)
        return match.group(0) if match else ""

    code_ids = {key: int(qid) for qid, key in
                re.findall(r'value="(\d+)"><span class="small">\[(OB-0[1-3])\]', column("code"))}
    output_ids = re.findall(r'name="question_ids" value="(\d+)"', column("output"))[:10]
    theory_ids = re.findall(r'name="question_ids" value="(\d+)"', column("theory"))[:20]
    if args.scenario == "coding":
        chosen = [str(qid) for qid in code_ids.values()]
    else:
        chosen = output_ids + theory_ids
    if not chosen:
        raise SystemExit("Kontest uchun savollar topilmadi (bank masalalari bazada bormi?).")
    title = f"Yuklama sinovi {time.strftime('%H:%M:%S')}"
    fields = {"title": title, "duration_minutes": "120", "question_ids": chosen, "is_active": "on", "max_violations": "0"}
    if args.camera:
        fields["proctoring"] = "on"
    if args.screen:
        fields["screen_capture"] = "on"
    admin.post_form("/admin/contests", fields, kind="setup")
    _, page, _ = admin.get("/admin/contests", kind="setup")
    position = page.find(title)
    match = re.search(r"/admin/contests/(\d+)/", page[position:])
    if position < 0 or not match:
        raise SystemExit("Sinov kontesti yaratilmadi.")
    contest_id = int(match.group(1))
    print(f"Kontest #{contest_id}: {len(chosen)} ta savol ({args.scenario}); kamera={args.camera}, ekran={args.screen}")
    return contest_id, code_ids


def cleanup(args, admin, contest_id):
    print("Tozalanmoqda…")
    admin.get("/admin/contests", kind="setup")
    if contest_id:
        admin.post_form(f"/admin/contests/{contest_id}/delete", {}, kind="setup")
    for index in range(1, args.students + 1):
        admin.post_form(f"/admin/students/LT-{index:03d}/delete", {}, kind="setup")


# ---------------------------------------------------------------- virtual talaba
def student(index, args, contest_id, solutions, images, stop_at):
    camera, screen = images
    client = Client(args.url)
    client.get("/login", kind="login page")
    status, _, final = client.post_form("/login", {
        "hemis_id": f"LT-{index:03d}", "full_name": f"Yuklama Talaba {index:03d}", "group_name": "LOAD-TEST",
    }, kind="login")
    if "/student" not in final:
        STATS.note("kirish muvaffaqiyatsiz")
        return
    _, page, _ = client.get(f"/contest/{contest_id}", kind="contest page")
    rng = random.Random(index)
    next_frame = time.time() + rng.uniform(0, FRAME_INTERVAL)
    next_action = time.time() + rng.uniform(2, 8)
    submits = 0

    def send_frames():
        code = solutions[0][1] if solutions else ""
        if args.camera:
            client.post_multipart(f"/contest/{contest_id}/proctor/frame",
                                  {"code": code, "language": "python"}, {"frame": ("f.jpg", camera)}, kind="camera frame")
        if args.screen:
            client.post_multipart(f"/contest/{contest_id}/proctor/screen", {}, {"screen": ("s.jpg", screen)},
                                  kind="screen frame")

    send_frames()
    while time.time() < stop_at:
        now = time.time()
        if now >= next_frame:
            send_frames()
            next_frame = now + FRAME_INTERVAL
        if now >= next_action:
            if args.scenario == "coding":
                question = re.search(r'data-question-id="(\d+)"', page)
                if not question:
                    _, page, _ = client.get(f"/contest/{contest_id}", kind="contest page")
                    if "/result/" in page or not re.search(r'data-question-id="(\d+)"', page):
                        STATS.note("barcha masalalar yechildi")
                        return
                    continue
                qid = int(question.group(1))
                solution = dict(solutions).get(qid, WRONG_SOLUTION)
                if rng.random() < 0.6:
                    client.post_json(f"/contest/{contest_id}/run/{qid}",
                                     {"language": "python", "source_code": solution, "stdin": "1 2"}, kind="run")
                    next_action = now + rng.uniform(5, 10)
                else:
                    submits += 1
                    code = WRONG_SOLUTION if submits % 3 else solution
                    started = time.perf_counter()
                    client.post_form(f"/contest/{contest_id}/code/{qid}",
                                     {"language": "python", "source_code": code}, kind="submit")
                    result = "kutish vaqti tugadi"
                    while time.perf_counter() - started < 240 and time.time() < stop_at + 240:
                        time.sleep(2)
                        if time.time() >= next_frame:
                            send_frames()
                            next_frame = time.time() + FRAME_INTERVAL
                        _, page, final = client.get(f"/contest/{contest_id}", kind="verdict poll")
                        current = re.search(r'data-question-id="(\d+)"', page)
                        if "/result/" in final or not current or int(current.group(1)) != qid:
                            result = "qabul"  # keyingi masala ochildi yoki kontest tugadi
                            break
                        if '"pending": true' in page:
                            continue
                        result = "navbat band" if "navbati band" in page else "rad etildi"
                        break
                    STATS.verdict(time.perf_counter() - started, result)
                    next_action = time.time() + rng.uniform(20, 30)  # SUBMIT_COOLDOWN_SECONDS=20
            else:
                question_ids = re.findall(r'name="(\d+)" value="[A-D]"', page)
                if question_ids:
                    client.post_json(f"/contest/{contest_id}/save",
                                     {"question_id": rng.choice(question_ids), "answer": rng.choice("ABCD")}, kind="save answer")
                next_action = now + rng.uniform(4, 12)
        time.sleep(0.2)


# ---------------------------------------------------------------- asosiy
def main():
    parser = argparse.ArgumentParser(description="Kontest platformasi uchun yuklama sinovi")
    parser.add_argument("--url", required=True, help="sayt manzili, masalan https://<sayt>.onrender.com")
    parser.add_argument("--students", type=int, default=50)
    parser.add_argument("--scenario", choices=["quiz", "coding"], default="coding")
    parser.add_argument("--minutes", type=float, default=3)
    parser.add_argument("--ramp", type=float, default=30, help="talabalar shuncha soniya ichida kiradi")
    parser.add_argument("--no-camera", dest="camera", action="store_false")
    parser.add_argument("--no-screen", dest="screen", action="store_false")
    parser.add_argument("--keep", action="store_true", help="sinov talabalari va kontestini o‘chirmaslik")
    args = parser.parse_args()

    solutions = []
    if args.scenario == "coding":
        from build_problem_bank import PROBLEMS
        references = {item["key"]: item["ref"] for item in PROBLEMS}
    admin = admin_client(args)
    contest_id, code_ids = setup(args, admin)
    if args.scenario == "coding":
        solutions = [(qid, references[key]) for key, qid in sorted(code_ids.items())]
    images = make_jpegs()
    started = time.time()
    stop_at = started + args.ramp + args.minutes * 60
    threads = []
    try:
        for index in range(1, args.students + 1):
            thread = threading.Thread(target=student, args=(index, args, contest_id, solutions, images, stop_at), daemon=True)
            thread.start()
            threads.append(thread)
            time.sleep(args.ramp / max(1, args.students))
        print(f"{args.students} ta virtual talaba ishlayapti, {args.minutes:g} daqiqa…")
        for thread in threads:
            thread.join(timeout=max(1, stop_at + 300 - time.time()))
    finally:
        print("\n=== Natija ===")
        print(f"Talabalar: {args.students}, davomiylik: {time.time() - started:.0f}s, ssenariy: {args.scenario}")
        print(STATS.report())
        if not args.keep:
            cleanup(args, admin, contest_id)


if __name__ == "__main__":
    main()
