"""Birinchi ishga tushirishda .env faylini terminal orqali yaratish.

`python main.py` — .env yo‘q yoki BOT_TOKEN to‘ldirilmagan bo‘lsa, savollar beradi.
`python main.py --setup` — sozlamalarni qaytadan kiritish (eski qiymatlar standart sifatida taklif qilinadi).

Muhim: bu modul `config` ni import qilmaydi — u .env yaratilgandan keyin o‘qiladi.
"""
from __future__ import annotations

import asyncio
import getpass
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
PLACEHOLDER_TOKENS = {"", "123456789:AAAA-your-bot-token"}


class SetupCancelled(Exception):
    pass


# ---------------------------------------------------------------- .env o‘qish / yozish
def read_env_file(path: Path = ENV_PATH) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _quote(value: str) -> str:
    if value == "" or re.match(r"^[A-Za-z0-9_\-.:/@+?=&,%]+$", value):
        return value
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def write_env_file(values: Dict[str, str], path: Path = ENV_PATH) -> None:
    sections = [
        ("Telegram bot tokeni (@BotFather)", ["BOT_TOKEN"]),
        ("Admin Telegram ID lari (vergul bilan). Bo'sh bo'lsa - birinchi /start bosgan odam egasi bo'ladi", ["ADMIN_IDS"]),
        ("Ma'lumotlar bazasi", ["DATABASE_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]),
        ("Vaqt zonasi va standart vaqtlar", ["TIMEZONE", "DEFAULT_REPORT_TIME", "DEFAULT_COUNTDOWN_TIME"]),
        ("Log darajasi: DEBUG / INFO / WARNING", ["LOG_LEVEL"]),
    ]
    lines = ["# IELTS Controller sozlamalari (python main.py --setup orqali qayta yaratiladi)", ""]
    used = set()
    for title, keys in sections:
        present = [k for k in keys if k in values]
        if not present:
            continue
        lines.append("# " + title)
        for key in present:
            lines.append("%s=%s" % (key, _quote(values[key])))
            used.add(key)
        lines.append("")
    extra = [k for k in values if k not in used]
    if extra:
        lines.append("# Boshqa")
        lines += ["%s=%s" % (k, _quote(values[k])) for k in extra]
        lines.append("")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(str(tmp), str(path))
    try:
        os.chmod(str(path), 0o600)  # token maxfiy
    except OSError:
        pass


# ---------------------------------------------------------------- terminal yordamchilari
def _ask(prompt: str, default: Optional[str] = None, secret: bool = False) -> str:
    suffix = " [%s]" % ("****" if secret and default else default) if default else ""
    try:
        if secret:
            raw = getpass.getpass("  %s%s: " % (prompt, suffix))
        else:
            raw = input("  %s%s: " % (prompt, suffix))
    except EOFError:
        raise SetupCancelled()
    raw = raw.strip()
    return raw if raw else (default or "")


def _ask_valid(prompt: str, check: Callable[[str], Optional[str]], default: Optional[str] = None,
               secret: bool = False) -> str:
    """check(value) xato matnini qaytaradi yoki None (to‘g‘ri)."""
    while True:
        value = _ask(prompt, default, secret)
        error = check(value)
        if error is None:
            return value
        print("  ! " + error)


def _yes(prompt: str, default: bool = True) -> bool:
    hint = "H/y" if default else "h/Y"
    while True:
        raw = _ask("%s (%s)" % (prompt, hint)).lower()
        if not raw:
            return default
        if raw in ("h", "ha", "yes", "ok"):
            return True
        if raw in ("y", "yo'q", "yoq", "n", "no"):
            return False


def _title(text: str) -> None:
    print("\n" + text)
    print("-" * len(text))


# ---------------------------------------------------------------- tekshiruvlar
def check_token(value: str) -> Optional[str]:
    if not TOKEN_RE.match(value):
        return "Token formati noto'g'ri. Masalan: 123456789:AAH...xyz (BotFather bergan to'liq token)"
    return None


def verify_token_online(token: str) -> Tuple[Optional[bool], str]:
    """Telegram getMe. (True, username) / (False, xato) / (None, tarmoq xatosi)."""
    url = "https://api.telegram.org/bot%s/getMe" % token
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("ok"):
            return True, data["result"].get("username", "")
        return False, data.get("description", "noma'lum xato")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 404):
            return False, "token noto'g'ri yoki bekor qilingan"
        return None, "HTTP %s" % exc.code
    except Exception as exc:  # tarmoq yo‘q, proxy va h.k.
        return None, str(exc)


def check_admin_ids(value: str) -> Optional[str]:
    for part in value.replace(";", ",").replace(" ", ",").split(","):
        if part.strip() and not part.strip().isdigit():
            return "Faqat raqamli Telegram ID lar, vergul bilan. Masalan: 123456789,987654321"
    return None


def normalize_ids(value: str) -> str:
    return ",".join(p.strip() for p in value.replace(";", ",").replace(" ", ",").split(",") if p.strip())


def check_timezone(value: str) -> Optional[str]:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(value)
        return None
    except Exception:
        return "Bunday vaqt zonasi topilmadi. Masalan: Asia/Tashkent, Europe/Moscow, UTC"


def check_time(value: str) -> Optional[str]:
    return None if TIME_RE.match(value) else "Vaqt HH:MM formatida bo'lishi kerak. Masalan: 21:00"


def normalize_time(value: str) -> str:
    hour, minute = value.split(":")
    return "%02d:%02d" % (int(hour), int(minute))


async def _probe_db(url: str) -> Optional[str]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=10)
        return None
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)
    finally:
        await engine.dispose()


def probe_db(url: str) -> Optional[str]:
    try:
        return asyncio.run(asyncio.wait_for(_probe_db(url), timeout=15))
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)


# ---------------------------------------------------------------- bo‘limlar
def _ask_token(old: Dict[str, str]) -> str:
    _title("1. Bot tokeni")
    print("  @BotFather -> /newbot (yoki /mybots -> API Token) dan olingan tokenni kiriting.")
    default = old.get("BOT_TOKEN") if old.get("BOT_TOKEN") not in PLACEHOLDER_TOKENS else None
    while True:
        token = _ask_valid("BOT_TOKEN", check_token, default)
        print("  Tekshirilmoqda...")
        ok, info = verify_token_online(token)
        if ok:
            print("  OK: bot @%s" % info)
            return token
        if ok is False:
            print("  ! Telegram tokenni rad etdi: %s" % info)
            default = None
            continue
        print("  ! Telegram bilan bog'lanib bo'lmadi (%s)." % info)
        if _yes("Token shu holicha saqlansinmi?"):
            return token


def _ask_admins(old: Dict[str, str]) -> str:
    _title("2. Admin")
    print("  O'z Telegram ID ingiz (@userinfobot dan bilish mumkin). Bir nechta bo'lsa - vergul bilan.")
    print("  Enter bosib o'tkazsangiz: botga birinchi /start bosgan odam egasi bo'ladi.")
    return normalize_ids(_ask_valid("ADMIN_IDS", check_admin_ids, old.get("ADMIN_IDS") or None))


def _sqlite_available() -> bool:
    try:
        import aiosqlite  # noqa: F401

        return True
    except ImportError:
        return False


def is_termux() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "") or "TERMUX_VERSION" in os.environ


def _ask_database(old: Dict[str, str]) -> Dict[str, str]:
    _title("3. Ma'lumotlar bazasi")
    old_url = old.get("DATABASE_URL", "")
    if is_termux():
        print("  1) PostgreSQL - alohida server kerak")
        print("  2) SQLite - bitta fayl, server kerak emas (telefon/Termux uchun tavsiya)")
        default_choice = "1" if old_url.startswith("postgres") else "2"
    else:
        print("  1) PostgreSQL (tavsiya)")
        print("  2) SQLite - bitta fayl, server kerak emas (sinov uchun qulay)")
        default_choice = "2" if old_url.startswith("sqlite") else "1"
    choice = _ask_valid("Tanlang (1/2)", lambda v: None if v in ("1", "2") else "1 yoki 2 ni kiriting", default_choice)

    while True:
        if choice == "2":
            if not _sqlite_available():
                print("  ! SQLite uchun 'aiosqlite' paketi kerak. O'rnating:")
                print("      %s -m pip install aiosqlite" % (Path(sys.executable).name or "python"))
                if _yes("PostgreSQL ga o'tamizmi?"):
                    choice = "1"
                    continue
            name = _ask("Fayl nomi", "ielts.db")
            path = Path(name).expanduser()
            if path.is_absolute():
                try:  # loyiha ichida bo‘lsa — nisbiy yozamiz (.env boshqa qurilmaga ko‘chsa ham ishlaydi)
                    path = path.relative_to(ROOT)
                except ValueError:
                    pass
            # nisbiy yo‘lni config.py loyiha papkasiga bog‘laydi
            return {"DATABASE_URL": "sqlite+aiosqlite:///%s" % path.as_posix()}

        try:
            import asyncpg  # noqa: F401
        except ImportError:
            print("  ! PostgreSQL uchun 'asyncpg' paketi o'rnatilmagan:  python -m pip install asyncpg")
            if _yes("SQLite ga o'tamizmi?"):
                choice = "2"
                continue
        host = _ask("Host", old.get("_PG_HOST", "localhost"))
        port = _ask_valid("Port", lambda v: None if v.isdigit() else "Port raqam bo'lishi kerak",
                          old.get("_PG_PORT", "5432"))
        user = _ask("Foydalanuvchi", old.get("POSTGRES_USER", "ielts"))
        password = _ask("Parol", old.get("POSTGRES_PASSWORD", "ielts"), secret=True)
        dbname = _ask("Baza nomi", old.get("POSTGRES_DB", "ielts"))
        url = "postgresql+asyncpg://%s:%s@%s:%s/%s" % (
            quote(user, safe=""), quote(password, safe=""), host, port, quote(dbname, safe="")
        )
        result = {"DATABASE_URL": url, "POSTGRES_USER": user, "POSTGRES_PASSWORD": password, "POSTGRES_DB": dbname}

        if host in ("db", "postgres"):  # docker compose ichidagi host — bu yerdan ulanib bo‘lmaydi
            return result
        print("  Ulanish tekshirilmoqda...")
        error = probe_db(url)
        if error is None:
            print("  OK: bazaga ulanildi.")
            return result
        print("  ! Bazaga ulanib bo'lmadi: %s" % error[:300])
        print("    (PostgreSQL ishlayotganini va baza/foydalanuvchi yaratilganini tekshiring.)")
        if not _yes("Qayta kiritasizmi?"):
            return result
        old = dict(old, _PG_HOST=host, _PG_PORT=port, POSTGRES_USER=user, POSTGRES_PASSWORD=password,
                   POSTGRES_DB=dbname)


def _split_pg_url(url: str) -> Dict[str, str]:
    match = re.match(r"^postgres\w*(?:\+\w+)?://(?:[^:@/]*(?::[^@/]*)?@)?([^:/?]+)(?::(\d+))?/", url or "")
    if not match:
        return {}
    return {"_PG_HOST": match.group(1), "_PG_PORT": match.group(2) or "5432"}


def _ask_schedule(old: Dict[str, str]) -> Dict[str, str]:
    _title("4. Vaqt sozlamalari")
    tz = _ask_valid("Vaqt zonasi", check_timezone, old.get("TIMEZONE") or "Asia/Tashkent")
    report = _ask_valid("Daily Report vaqti (HH:MM)", check_time, old.get("DEFAULT_REPORT_TIME") or "21:00")
    countdown = _ask_valid("Countdown posti vaqti (HH:MM)", check_time, old.get("DEFAULT_COUNTDOWN_TIME") or "09:00")
    return {
        "TIMEZONE": tz,
        "DEFAULT_REPORT_TIME": normalize_time(report),
        "DEFAULT_COUNTDOWN_TIME": normalize_time(countdown),
    }


# ---------------------------------------------------------------- asosiy
def needs_setup() -> bool:
    if os.environ.get("BOT_TOKEN", "").strip() not in PLACEHOLDER_TOKENS:
        return False  # token muhitdan keldi (masalan Docker env_file)
    return read_env_file().get("BOT_TOKEN", "").strip() in PLACEHOLDER_TOKENS


def run_wizard() -> Dict[str, str]:
    old = read_env_file()
    old.update({k: v for k, v in _split_pg_url(old.get("DATABASE_URL", "")).items()})

    print("=" * 52)
    print("  IELTS CONTROLLER - birinchi sozlash")
    print("=" * 52)
    print("Savollarga javob bering. [qavsdagi] qiymat - Enter bosilsa olinadigan standart.")
    print("Bekor qilish: Ctrl+C")

    values: Dict[str, str] = {k: v for k, v in old.items() if not k.startswith("_")}
    values["BOT_TOKEN"] = _ask_token(old)
    values["ADMIN_IDS"] = _ask_admins(old)
    db = _ask_database(old)
    if not db["DATABASE_URL"].startswith("postgres"):
        for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
            values.pop(key, None)
    values.update(db)
    values.update(_ask_schedule(old))
    values.setdefault("LOG_LEVEL", "INFO")

    write_env_file(values)
    print("\nSaqlandi: %s" % ENV_PATH)
    print("Keyinroq o'zgartirish: python main.py --setup  (yoki .env faylini tahrirlang)\n")
    return values


def ensure_env(force: bool = False) -> None:
    """Kerak bo‘lsa sozlash ustasini ishga tushiradi va qiymatlarni os.environ ga yuklaydi."""
    if not force and not needs_setup():
        return
    if not sys.stdin or not sys.stdin.isatty():
        sys.exit(
            "BOT_TOKEN topilmadi va terminal interaktiv emas.\n"
            "Botni terminalda 'python main.py' bilan ishga tushiring yoki .env faylini qo'lda to'ldiring "
            "(namuna: .env.example)."
        )
    try:
        values = run_wizard()
    except (KeyboardInterrupt, SetupCancelled):
        print("\n\nSozlash bekor qilindi. .env o'zgartirilmadi.")
        sys.exit(1)
    for key, value in values.items():
        os.environ[key] = value  # dotenv mavjud muhit qiymatini ustidan yozmaydi — shuning uchun o‘zimiz
