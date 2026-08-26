"""Bot sozlamalari.

Barcha maxfiy qiymatlar `.env` faylidan o'qiladi — kod ichida token saqlamaymiz.
`.env.example` dan nusxa olib to'ldiring: cp .env.example .env
"""
from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int = 0) -> int:
    try:
        return int((os.getenv(name) or "").strip() or default)
    except ValueError:
        return default


# ===== majburiy =====
TOKEN: str = (os.getenv("BOT_TOKEN") or "").strip()

# Kinolar saqlanadigan baza kanal ID (manfiy son, -100... bilan boshlanadi)
BAZA_KANAL_ID: int = _int("BAZA_KANAL_ID")

# Adminlar (bir nechta bo'lsa vergul bilan: 111,222)
ADMIN_IDS: List[int] = [
    int(x)
    for x in (os.getenv("ADMIN_IDS") or "").replace(" ", "").split(",")
    if x.lstrip("-").isdigit()
]

# ===== ixtiyoriy =====
DB_PATH: str = (os.getenv("DB_PATH") or "baza.db").strip()

# VIP status necha kun beriladi
VIP_KUNLAR: int = _int("VIP_KUNLAR", 30)
VIP_MUDDATI: int = VIP_KUNLAR * 24 * 60 * 60

# VIP olish uchun nechta do'st taklif qilish kerak
REFERAL_KERAK: int = _int("REFERAL_KERAK", 10)

# Reklama tarqatish tezligi (sekundda xabar). Telegram limiti ~30.
TARQATISH_TEZLIGI: int = max(1, min(_int("TARQATISH_TEZLIGI", 20), 25))


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def tekshir() -> List[str]:
    """Ishga tushirishdan oldin sozlamalarni tekshiradi."""
    xatolar: List[str] = []
    if not TOKEN:
        xatolar.append("BOT_TOKEN ko'rsatilmagan (.env)")
    if not BAZA_KANAL_ID:
        xatolar.append("BAZA_KANAL_ID ko'rsatilmagan (.env)")
    if not ADMIN_IDS:
        xatolar.append("ADMIN_IDS ko'rsatilmagan (.env)")
    return xatolar
