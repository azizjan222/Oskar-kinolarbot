"""Ma'lumotlar bazasi (aiosqlite — asinxron).

Nega o'zgardi: oldin `sqlite3` ishlatilgan edi. U sinxron ishlaydi va har bir
so'rov paytida butun bot "muzlab" turadi. 10 000 odamga reklama tarqatganda bu
sezilarli — bot boshqa hech kimga javob bermaydi. `aiosqlite` esa so'rovni
alohida ip (thread) da bajaradi, bot esa ishlashda davom etadi.

Mavjud `baza.db` buzilmaydi: jadvallar o'sha-o'sha, faqat yangi ustunlar
qo'shiladi (migratsiya avtomatik).
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import List, Optional, Tuple

import aiosqlite

import config

log = logging.getLogger("db")

_conn: Optional[aiosqlite.Connection] = None


def _c() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Baza ulanmagan — avval db.ulanish() ni chaqiring")
    return _conn


def kun_boshi() -> int:
    """Bugungi kun boshining unix vaqti (statistika uchun)."""
    return int(time.mktime(date.today().timetuple()))


# ==========================================
# ULANISH VA JADVALLAR
# ==========================================

async def ulanish() -> None:
    global _conn
    _conn = await aiosqlite.connect(config.DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _yaratish()
    await _migratsiya()
    await _conn.commit()
    log.info("Baza ulandi: %s", config.DB_PATH)


async def yopish() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def _yaratish() -> None:
    c = _c()
    await c.execute(
        """CREATE TABLE IF NOT EXISTS kinolar (
               kod TEXT PRIMARY KEY,
               xabar_id INTEGER,
               toza_matn TEXT,
               vip INTEGER DEFAULT 0
           )"""
    )
    await c.execute(
        """CREATE TABLE IF NOT EXISTS foydalanuvchilar (
               id INTEGER PRIMARY KEY
           )"""
    )
    await c.execute("CREATE TABLE IF NOT EXISTS kanallar (kanal TEXT PRIMARY KEY)")
    await c.execute(
        "CREATE TABLE IF NOT EXISTS referallar (id INTEGER PRIMARY KEY, soni INTEGER DEFAULT 0)"
    )
    await c.execute("CREATE TABLE IF NOT EXISTS viplar (id INTEGER PRIMARY KEY, vaqt REAL)")


async def _migratsiya() -> None:
    """Eski bazaga yangi ustunlarni qo'shadi (ma'lumot yo'qolmaydi)."""
    c = _c()
    async with c.execute("PRAGMA table_info(foydalanuvchilar)") as cur:
        mavjud = {row["name"] for row in await cur.fetchall()}

    yangilar = {
        "username": "TEXT",
        "ism": "TEXT",
        "qoshilgan": "INTEGER DEFAULT 0",
        "oxirgi_faollik": "INTEGER DEFAULT 0",
        "bloklangan": "INTEGER DEFAULT 0",
        "taklif_qilgan": "INTEGER",
    }
    for ustun, turi in yangilar.items():
        if ustun not in mavjud:
            await c.execute(f"ALTER TABLE foydalanuvchilar ADD COLUMN {ustun} {turi}")
            log.info("Migratsiya: foydalanuvchilar.%s qo'shildi", ustun)

    await c.execute(
        "CREATE INDEX IF NOT EXISTS ix_foyd_bloklangan ON foydalanuvchilar (bloklangan)"
    )


# ==========================================
# FOYDALANUVCHILAR
# ==========================================

async def foydalanuvchi_bormi(user_id: int) -> bool:
    c = _c()
    async with c.execute("SELECT 1 FROM foydalanuvchilar WHERE id=?", (user_id,)) as cur:
        return await cur.fetchone() is not None


async def foydalanuvchi_qoshish(
    user_id: int,
    username: Optional[str] = None,
    ism: Optional[str] = None,
    taklif_qilgan: Optional[int] = None,
) -> bool:
    """Yangi foydalanuvchini qo'shadi. True — haqiqatan yangi bo'lsa."""
    c = _c()
    hozir = int(time.time())
    cur = await c.execute(
        """INSERT OR IGNORE INTO foydalanuvchilar
           (id, username, ism, qoshilgan, oxirgi_faollik, bloklangan, taklif_qilgan)
           VALUES (?, ?, ?, ?, ?, 0, ?)""",
        (user_id, username, ism, hozir, hozir, taklif_qilgan),
    )
    await c.commit()
    return cur.rowcount > 0


async def faollik_belgilash(
    user_id: int, username: Optional[str] = None, ism: Optional[str] = None
) -> None:
    """Mavjud foydalanuvchining faolligini yangilaydi (yangi qo'shmaydi)."""
    c = _c()
    await c.execute(
        """UPDATE foydalanuvchilar
              SET oxirgi_faollik=?,
                  username=COALESCE(?, username),
                  ism=COALESCE(?, ism),
                  bloklangan=0
            WHERE id=?""",
        (int(time.time()), username, ism, user_id),
    )
    await c.commit()


async def bloklangan_belgilash(user_id: int, holat: bool = True) -> None:
    c = _c()
    await c.execute(
        "UPDATE foydalanuvchilar SET bloklangan=? WHERE id=?", (1 if holat else 0, user_id)
    )
    await c.commit()


async def faol_foydalanuvchilar() -> List[int]:
    """Reklama yuborish mumkin bo'lganlar (botni bloklamaganlar)."""
    c = _c()
    async with c.execute(
        "SELECT id FROM foydalanuvchilar WHERE bloklangan IS NULL OR bloklangan=0"
    ) as cur:
        return [row["id"] for row in await cur.fetchall()]


# ==========================================
# MAJBURIY KANALLAR
# ==========================================

async def kanallar() -> List[str]:
    c = _c()
    async with c.execute("SELECT kanal FROM kanallar") as cur:
        return [row["kanal"] for row in await cur.fetchall()]


async def kanal_qoshish(kanal: str) -> None:
    c = _c()
    await c.execute("REPLACE INTO kanallar (kanal) VALUES (?)", (kanal,))
    await c.commit()


async def kanal_ochirish(kanal: str) -> bool:
    c = _c()
    cur = await c.execute("DELETE FROM kanallar WHERE kanal=?", (kanal,))
    await c.commit()
    return cur.rowcount > 0


# ==========================================
# REFERALLAR
# ==========================================

async def referal_soni(user_id: int) -> int:
    c = _c()
    async with c.execute("SELECT soni FROM referallar WHERE id=?", (user_id,)) as cur:
        row = await cur.fetchone()
    return row["soni"] if row else 0


async def referal_qoshish(user_id: int) -> int:
    """Referal sonini 1 ga oshiradi va yangi sonni qaytaradi."""
    c = _c()
    await c.execute(
        """INSERT INTO referallar (id, soni) VALUES (?, 1)
           ON CONFLICT(id) DO UPDATE SET soni = soni + 1""",
        (user_id,),
    )
    await c.commit()
    return await referal_soni(user_id)


async def referal_tozalash(user_id: int) -> None:
    c = _c()
    await c.execute("REPLACE INTO referallar (id, soni) VALUES (?, 0)", (user_id,))
    await c.commit()


# ==========================================
# VIP
# ==========================================

async def vip_mi(user_id: int) -> bool:
    if config.is_admin(user_id):
        return True
    c = _c()
    async with c.execute("SELECT vaqt FROM viplar WHERE id=?", (user_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return False
    if time.time() < row["vaqt"]:
        return True
    # muddati tugagan — o'chiramiz
    await c.execute("DELETE FROM viplar WHERE id=?", (user_id,))
    await c.commit()
    return False


async def vip_berish(user_id: int, sekund: Optional[int] = None) -> None:
    """VIP beradi. Agar allaqachon VIP bo'lsa — muddatni uzaytiradi."""
    c = _c()
    sekund = sekund if sekund is not None else config.VIP_MUDDATI
    async with c.execute("SELECT vaqt FROM viplar WHERE id=?", (user_id,)) as cur:
        row = await cur.fetchone()
    boshlanish = max(time.time(), row["vaqt"]) if row else time.time()
    await c.execute(
        "REPLACE INTO viplar (id, vaqt) VALUES (?, ?)", (user_id, boshlanish + sekund)
    )
    await c.commit()


async def vip_ochirish(user_id: int) -> bool:
    c = _c()
    cur = await c.execute("DELETE FROM viplar WHERE id=?", (user_id,))
    await c.commit()
    return cur.rowcount > 0


async def vip_qolgan_kun(user_id: int) -> int:
    c = _c()
    async with c.execute("SELECT vaqt FROM viplar WHERE id=?", (user_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return 0
    return max(0, int((row["vaqt"] - time.time()) / 86400))


# ==========================================
# KINOLAR
# ==========================================

async def kino_saqlash(kod: str, xabar_id: int, toza_matn: str, vip: bool) -> None:
    c = _c()
    await c.execute(
        "REPLACE INTO kinolar (kod, xabar_id, toza_matn, vip) VALUES (?, ?, ?, ?)",
        (kod, xabar_id, toza_matn, 1 if vip else 0),
    )
    await c.commit()


async def kino_olish(kod: str) -> Optional[Tuple[int, str, bool]]:
    c = _c()
    async with c.execute(
        "SELECT xabar_id, toza_matn, vip FROM kinolar WHERE kod=?", (kod,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return row["xabar_id"], row["toza_matn"] or "", bool(row["vip"])


async def tasodifiy_kino(vip_ruxsat: bool) -> Optional[Tuple[int, str]]:
    """Tasodifiy kino. Saralash bazada bajariladi — hamma kinoni xotiraga
    yuklash shart emas (oldin shunday qilinardi va baza kattalashsa sekinlashardi)."""
    c = _c()
    shart = "" if vip_ruxsat else "WHERE vip=0 OR vip IS NULL"
    async with c.execute(
        f"SELECT xabar_id, toza_matn FROM kinolar {shart} ORDER BY RANDOM() LIMIT 1"
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return row["xabar_id"], row["toza_matn"] or ""


async def kino_ochirish(kod: str) -> bool:
    c = _c()
    cur = await c.execute("DELETE FROM kinolar WHERE kod=?", (kod,))
    await c.commit()
    return cur.rowcount > 0


# ==========================================
# STATISTIKA
# ==========================================

async def _son(sql: str, params: tuple = ()) -> int:
    c = _c()
    async with c.execute(sql, params) as cur:
        row = await cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


async def statistika() -> dict:
    bugun = kun_boshi()
    return {
        "odamlar": await _son("SELECT COUNT(*) FROM foydalanuvchilar"),
        "bugun_yangi": await _son(
            "SELECT COUNT(*) FROM foydalanuvchilar WHERE qoshilgan >= ?", (bugun,)
        ),
        "bugun_faol": await _son(
            "SELECT COUNT(*) FROM foydalanuvchilar WHERE oxirgi_faollik >= ?", (bugun,)
        ),
        "bloklaganlar": await _son(
            "SELECT COUNT(*) FROM foydalanuvchilar WHERE bloklangan=1"
        ),
        "kinolar": await _son("SELECT COUNT(*) FROM kinolar"),
        "vip_kinolar": await _son("SELECT COUNT(*) FROM kinolar WHERE vip=1"),
        "vip_odamlar": await _son("SELECT COUNT(*) FROM viplar WHERE vaqt > ?", (time.time(),)),
        "kanallar": await _son("SELECT COUNT(*) FROM kanallar"),
    }
