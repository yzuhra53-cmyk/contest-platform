"""Proktoring yordamchilari: OpenCV bilan yuz aniqlash."""

import os
import threading

from i18n import N_

try:
    import cv2
    import numpy as np
except ImportError:  # OpenCV o'rnatilmagan bo'lsa ham ilova ishlayveradi
    cv2 = None
    np = None

MAX_FRAME_BYTES = 300 * 1024
# Ekran rasmi kattaroq (matn o'qilishi uchun).
MAX_SCREEN_BYTES = 600 * 1024
FRAME_INTERVAL_SECONDS = 10
# Shuncha vaqt kadr kelmasa, kamera o'chgan hisoblanadi va kod yuborish to'xtatiladi.
FRAME_STALE_SECONDS = 60
# Bir xil turdagi ogohlantirish shu oraliqda faqat bir marta yoziladi.
EVENT_COOLDOWN_SECONDS = 30

# Ko'rsatishda _() bilan tarjima qilinadi (app.py, admin_proctor_attempt).
EVENT_LABELS = {
    "no_face": N_("Kadrda yuz yo‘q"),
    "multiple_faces": N_("Kadrda bir nechta yuz"),
    "tab_hidden": N_("Boshqa tab/dasturga o‘tdi"),
    "window_blur": N_("Oynadan chiqdi"),
    "paste": N_("Kod joylashtirishga urindi (paste)"),
    "camera_denied": N_("Kameraga ruxsat bermadi"),
    "camera_lost": N_("Kamera uzildi"),
    "camera_missing": N_("Kompyuterda kamera yo‘q — faqat ekran orqali kuzatildi"),
    "screen_denied": N_("Ekranni ulashishga ruxsat bermadi"),
    "screen_lost": N_("Ekran ulashish to‘xtatildi"),
    "fullscreen_exit": N_("To‘liq ekran rejimidan chiqdi"),
    "seb_missing": N_("Safe Exam Browser'siz kirishga urindi"),
    "new_device_login": N_("Boshqa qurilma/brauzerdan kirdi"),
    "auto_finished": N_("Qoidabuzarlik limiti: urinish avtomatik yakunlandi"),
}
# Limitga hisoblanadigan qoidabuzarliklar. tab_hidden hisoblanmaydi: tab almashganda
# window_blur ham keladi, ikki marta sanalmasin. camera_denied — kontest boshlanmasdan oldin.
VIOLATION_KINDS = (
    "no_face",
    "multiple_faces",
    "window_blur",
    "paste",
    "camera_lost",
    "screen_lost",
    "fullscreen_exit",
    "new_device_login",
)
CLIENT_EVENT_KINDS = {
    "tab_hidden", "window_blur", "paste", "camera_denied", "camera_lost", "camera_missing", "screen_denied",
    "screen_lost",
    "fullscreen_exit",
}

_cascade = None
_cascade_lock = threading.Lock()


def _get_cascade():
    global _cascade
    with _cascade_lock:
        if _cascade is None and cv2 is not None:
            path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            classifier = cv2.CascadeClassifier(path)
            _cascade = classifier if not classifier.empty() else False
        return _cascade or None


def detect_faces(image_bytes):
    """JPEG/PNG kadrdagi yuzlar sonini qaytaradi.

    None — rasmni o'qib bo'lmadi yoki OpenCV mavjud emas.
    """
    cascade = _get_cascade()
    if cascade is None or not image_bytes:
        return None
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    height, width = image.shape[:2]
    if width > 640:
        scale = 640 / width
        image = cv2.resize(image, (640, int(height * scale)))
    image = cv2.equalizeHist(image)
    faces = cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=6, minSize=(40, 40))
    return len(faces)


def is_jpeg(data):
    return data[:3] == b"\xff\xd8\xff"
