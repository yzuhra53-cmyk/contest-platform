"""Ichki (local) kod tekshiruvchi.

Talaba yuborgan Python 3 yoki C++17 kodini shu serverning o'zida, vaqtinchalik
papkada ishga tushiradi va yashirin testlar bilan solishtiradi.

Himoya choralari:
  * har bir test uchun vaqt cheklovi (standart 2 soniya, JUDGE_TIME_LIMIT);
  * xotira, fayl hajmi va jarayonlar soni cheklovi (Linux'da `prlimit` orqali);
  * talaba kodi tozalangan muhit (environment) bilan ishlaydi — SECRET_KEY,
    DATABASE_URL kabi o'zgaruvchilar unga berilmaydi;
  * server root sifatida ishlasa (Dockerfile'dagi kabi), kod alohida, huquqsiz
    foydalanuvchi nomidan ishga tushadi; parallel tekshiruvlarning har biri o'z
    UID'siga ega (runner UID + navbat raqami), shuning uchun bir talabaning kodi
    boshqasining tekshiruviga xalaqit bera olmaydi;
  * ish tugagach vaqtinchalik papka o'chiriladi, qolgan jarayonlar to'xtatiladi.
"""

import math
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

try:
    import pwd
except ImportError:  # Windows (faqat lokal ishlab chiqish uchun)
    pwd = None


class JudgeError(Exception):
    """Tekshiruv tizimining o'z xatosi (talaba kodining xatosi emas)."""


LANGUAGES = {"python", "cpp"}

TIME_LIMIT = float(os.environ.get("JUDGE_TIME_LIMIT", "2"))  # har bir test, soniya
COMPILE_TIMEOUT = float(os.environ.get("JUDGE_COMPILE_TIMEOUT", "30"))
MEMORY_LIMIT_MB = int(os.environ.get("JUDGE_MEMORY_MB", "256"))
MAX_PARALLEL = max(1, int(os.environ.get("JUDGE_MAX_PARALLEL", "2")))
QUEUE_TIMEOUT = 90  # navbat kutish, soniya
RUN_USER = os.environ.get("JUDGE_RUN_USER", "runner")
PYTHON_BIN = os.environ.get("JUDGE_PYTHON") or sys.executable

MAX_TESTS = 20
MAX_SOURCE_CHARS = 20000
MAX_CASE_CHARS = 100_000  # bitta test kirishi/chiqishi, belgi
MAX_OUTPUT_BYTES = 1024 * 1024  # dastur chiqishi, 1 MB
MAX_PROCESSES = 32
# Dockerfile'dagi oldindan kompilyatsiya qilingan sarlavha (PCH) aynan shu
# bayroqlar bilan yaratilgan. Bayroqlarni o'zgartirsangiz, Dockerfile'ni ham moslang.
CXX_FLAGS = ["-std=c++17", "-O2"]

_PRLIMIT = shutil.which("prlimit")
_free_slots = queue.Queue()
for _slot in range(MAX_PARALLEL):
    _free_slots.put(_slot)
_state_lock = threading.Lock()
_base_dir = None


def _sandbox_identity(slot):
    """Server root bo'lsa, (uid, gid) — talaba kodi shu foydalanuvchi nomidan ishlaydi."""
    if pwd is None or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return None
    try:
        entry = pwd.getpwnam(RUN_USER)
    except KeyError:
        return None
    return entry.pw_uid + slot, entry.pw_gid


def _get_base_dir():
    """Ro'yxatini ko'rib bo'lmaydigan (0711) umumiy papka: ichida ish papkalari yaratiladi."""
    global _base_dir
    with _state_lock:
        if _base_dir is None or not os.path.isdir(_base_dir):
            _base_dir = tempfile.mkdtemp(prefix="judge-")
            os.chmod(_base_dir, 0o711)
        return _base_dir


def _clean_env(workdir):
    env = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
    }
    for name in ("SYSTEMROOT", "SystemRoot"):  # Windows'da Python ishga tushishi uchun
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _with_limits(command, cpu_seconds, memory_mb, file_bytes, limit_processes):
    if not _PRLIMIT:
        return command
    limits = [
        _PRLIMIT,
        f"--cpu={int(cpu_seconds)}",
        f"--fsize={int(file_bytes)}",
        "--core=0",
    ]
    if memory_mb:
        limits.append(f"--as={int(memory_mb) * 1024 * 1024}")
    if limit_processes:
        limits.append(f"--nproc={MAX_PROCESSES}")
    return limits + command


def _kill_group(process):
    if hasattr(os, "killpg"):
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def _read_limited(handle):
    handle.seek(0)
    data = handle.read(MAX_OUTPUT_BYTES + 1)
    return data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"), len(data) > MAX_OUTPUT_BYTES


def _run(command, workdir, stdin_text, timeout, memory_mb, file_bytes, identity):
    """Buyruqni cheklovlar bilan ishga tushiradi.

    Qaytaradi: (returncode, timed_out, stdout, stderr, output_too_big)

    Kirish/chiqish fayllari ish papkasidan tashqarida, nomsiz vaqtinchalik
    fayllarda turadi: talaba kodi ularni almashtirib (masalan, symlink bilan)
    serverdagi boshqa fayllarni o'qita olmaydi.
    """
    base = os.path.dirname(workdir)
    extra = {}
    if identity:
        extra.update(user=identity[0], group=identity[1], extra_groups=[])
    if os.name == "posix":
        extra["start_new_session"] = True
    full_command = _with_limits(
        command,
        cpu_seconds=math.ceil(timeout) + 1,
        memory_mb=memory_mb,
        file_bytes=file_bytes,
        limit_processes=bool(identity),
    )
    with tempfile.TemporaryFile(dir=base) as stdin_file, \
            tempfile.TemporaryFile(dir=base) as stdout_file, \
            tempfile.TemporaryFile(dir=base) as stderr_file:
        stdin_file.write(stdin_text.encode("utf-8"))
        stdin_file.seek(0)
        try:
            process = subprocess.Popen(
                full_command,
                cwd=workdir,
                env=_clean_env(workdir),
                stdin=stdin_file,
                stdout=stdout_file,
                stderr=stderr_file,
                close_fds=True,
                **extra,
            )
        except OSError as error:
            raise JudgeError("Tekshiruv jarayonini ishga tushirib bo‘lmadi.") from error
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            _kill_group(process)  # orqada qolgan bola jarayonlarni ham to'xtatadi
            process.wait()
        stdout, too_big = _read_limited(stdout_file)
        stderr, _ = _read_limited(stderr_file)
    return process.returncode, timed_out, stdout, stderr, too_big


def _sweep_sandbox_processes(identity):
    """Sessiyadan "qochgan" jarayonlarni ham to'xtatadi.

    Sandbox UID nomidan kill(-1) chaqiriladi: yadro shu UID'ning barcha
    jarayonlarini bir yo'la o'ldiradi (fork-bomba ham ulgurmaydi).
    """
    try:
        subprocess.run(
            [PYTHON_BIN, "-I", "-c", "import os, signal; os.kill(-1, signal.SIGKILL)"],
            user=identity[0],
            group=identity[1],
            extra_groups=[],
            env={},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _tail(text, workdir, limit=300):
    text = text.replace(workdir + os.sep, "").replace(workdir, "").strip()
    return text[-limit:] if len(text) > limit else text


def _normalize(text):
    return " ".join((text or "").replace("\r\n", "\n").split())


def _validate(language, source_code, test_cases):
    if language not in LANGUAGES:
        raise JudgeError("Dasturlash tili qo‘llab-quvvatlanmaydi.")
    if not isinstance(test_cases, list) or not test_cases or len(test_cases) > MAX_TESTS:
        raise JudgeError("Masala testlari soni noto‘g‘ri.")
    if len(source_code) > MAX_SOURCE_CHARS or any(
        not isinstance(case, dict)
        or not isinstance(case.get("input"), str)
        or not isinstance(case.get("output"), str)
        or len(case["input"]) > MAX_CASE_CHARS
        or len(case["output"]) > MAX_CASE_CHARS
        for case in test_cases
    ):
        raise JudgeError("Kod yoki test ma’lumoti ruxsat etilgan hajmdan katta.")


def _judge(language, source_code, test_cases, workdir, identity):
    if language == "python":
        source_path = os.path.join(workdir, "main.py")
        # -I: izolyatsiya rejimi (muhit o'zgaruvchilari va joriy papka import yo'liga qo'shilmaydi)
        run_command = [PYTHON_BIN, "-I", "-X", "utf8", source_path]
    else:
        source_path = os.path.join(workdir, "main.cpp")
        run_command = [os.path.join(workdir, "main")]

    with open(source_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(source_code)

    if language == "cpp":
        compiler = shutil.which("g++")
        if not compiler:
            raise JudgeError("Serverda C++ kompilyatori (g++) o‘rnatilmagan.")
        returncode, timed_out, _, stderr, _ = _run(
            [compiler, *CXX_FLAGS, "-o", "main", "main.cpp"],
            workdir,
            "",
            timeout=COMPILE_TIMEOUT,
            memory_mb=None,  # kompilyator ko'p virtual xotira talab qiladi
            file_bytes=64 * 1024 * 1024,
            identity=identity,
        )
        if timed_out:
            return False, "Compilation Error. Kompilyatsiya vaqti tugadi."
        if returncode != 0:
            return False, f"Compilation Error. {_tail(stderr, workdir)}"

    for index, case in enumerate(test_cases, start=1):
        returncode, timed_out, stdout, stderr, too_big = _run(
            run_command,
            workdir,
            case["input"],
            timeout=TIME_LIMIT,
            memory_mb=MEMORY_LIMIT_MB,
            file_bytes=MAX_OUTPUT_BYTES * 2,
            identity=identity,
        )
        if timed_out or returncode == -getattr(signal, "SIGXCPU", 24):
            return False, f"{index}-test: Time Limit Exceeded ({TIME_LIMIT:g} soniya)."
        if too_big or returncode == -getattr(signal, "SIGXFSZ", 25):
            return False, f"{index}-test: Output Limit Exceeded."
        if returncode != 0:
            details = _tail(stderr, workdir)
            if not details and returncode < 0:
                try:
                    details = f"Dastur {signal.Signals(-returncode).name} signali bilan to‘xtadi."
                except ValueError:
                    details = ""
            details = details or f"Dastur {returncode} kodi bilan tugadi."
            return False, f"{index}-test: Runtime Error. {details}"
        if _normalize(stdout) != _normalize(case["output"]):
            return False, f"{index}-test: javob noto‘g‘ri."
    return True, f"Barcha {len(test_cases)} ta testdan o‘tdi."


def judge_solution(language, source_code, test_cases):
    """Kodni barcha testlarda tekshiradi. Qaytaradi: (accepted: bool, xabar: str).

    Birinchi muvaffaqiyatsiz testda to'xtaydi. Faqat barcha testlar o'tsa True.
    """
    _validate(language, source_code, test_cases)
    try:
        slot = _free_slots.get(timeout=QUEUE_TIMEOUT)
    except queue.Empty:
        raise JudgeError("Tekshiruv navbati band. Birozdan so‘ng qayta yuboring.") from None
    identity = _sandbox_identity(slot)
    workdir = None
    try:
        workdir = tempfile.mkdtemp(prefix="job-", dir=_get_base_dir())
        if identity:
            os.chown(workdir, identity[0], identity[1])
        return _judge(language, source_code, test_cases, workdir, identity)
    except JudgeError:
        raise
    except OSError as error:
        raise JudgeError("Tekshiruv serverida ichki xatolik yuz berdi.") from error
    finally:
        if identity:
            _sweep_sandbox_processes(identity)
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        _free_slots.put(slot)
