"""OSKAR KINOLAR — kino kodi orqali kino yuboruvchi bot.

Ishlash tartibi: baza kanalga kino tashlanadi, sarlavhasida qavs ichida kod
bo'ladi — masalan "Titanik (1997) (125)". Oxirgi qavsdagi son kino kodi bo'ladi.
Sarlavhada "vip" so'zi bo'lsa, kino faqat VIP foydalanuvchilarga ko'rinadi.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    TelegramObject,
)

import config
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-8s | %(message)s",
)
log = logging.getLogger("bot")

bot = Bot(
    token=config.TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


# ==========================================
# FILTRLAR VA MIDDLEWARE
# ==========================================

class Admin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and config.is_admin(event.from_user.id)


class Faollik(BaseMiddleware):
    """Har bir harakatda foydalanuvchining faolligini yangilaydi (statistika uchun).

    Diqqat: bu yerda YANGI foydalanuvchi qo'shilmaydi — faqat mavjudi
    yangilanadi. Aks holda /start dagi referal tizimi ishlamay qolardi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and not user.is_bot:
            try:
                await db.faollik_belgilash(user.id, user.username, user.full_name)
            except Exception:
                log.exception("Faollikni yozib bo'lmadi")
        return await handler(event, data)


dp.update.outer_middleware(Faollik())


# ==========================================
# KLAVIATURALAR
# ==========================================

asosiy_menyu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Shaxsiy kabinet"), KeyboardButton(text="🎲 Tasodifiy kino")]
    ],
    resize_keyboard=True,
)


async def obuna_klaviaturasi() -> InlineKeyboardMarkup:
    tugmalar = []
    for kanal in await db.kanallar():
        url = f"https://t.me/{kanal.replace('@', '')}"
        tugmalar.append([InlineKeyboardButton(text=f"📢 {kanal} ga o'tish", url=url)])
    tugmalar.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="tekshirish")])
    return InlineKeyboardMarkup(inline_keyboard=tugmalar)


# ==========================================
# OBUNANI TEKSHIRISH (natijasi 5 daqiqa saqlanadi)
# ==========================================

_obuna_kesh: Dict[int, Tuple[float, bool]] = {}
_KESH_MUDDATI = 300  # 5 daqiqa


async def obunani_tekshirish(user_id: int, keshdan: bool = True) -> bool:
    """Foydalanuvchi barcha majburiy kanallarga a'zomi?

    Har bir xabarda Telegram'ga so'rov yubormaslik uchun natija 5 daqiqa
    keshlanadi (faqat "a'zo" natijasi). Bu botni sezilarli tezlashtiradi.
    """
    if keshdan:
        kesh = _obuna_kesh.get(user_id)
        if kesh and time.time() - kesh[0] < _KESH_MUDDATI and kesh[1]:
            return True

    kanallar = await db.kanallar()
    if not kanallar:
        return True

    for kanal in kanallar:
        if kanal.lower().endswith("bot"):
            continue
        try:
            azo = await bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if azo.status in ("left", "kicked"):
                _obuna_kesh[user_id] = (time.time(), False)
                return False
        except Exception as e:
            # bot kanalda admin emas yoki kanal topilmadi — foydalanuvchini to'smaymiz
            log.info("A'zolikni tekshirib bo'lmadi (%s): %s", kanal, e)

    _obuna_kesh[user_id] = (time.time(), True)
    return True


async def obunaga_undash(message: Message) -> None:
    await message.answer(
        "Botdan to'liq foydalanish uchun kanallarga obuna bo'ling! ✅",
        reply_markup=await obuna_klaviaturasi(),
    )


# ==========================================
# 1. KANALDAN KINO SAQLASH
# ==========================================

@dp.channel_post(F.chat.id == config.BAZA_KANAL_ID)
async def kanaldan_kino_saqlash(message: Message) -> None:
    sarlavha = message.caption or message.text or ""
    barcha_kodlar = re.findall(r"\((\d+)\)", sarlavha)
    if not barcha_kodlar:
        return

    kino_kodi = barcha_kodlar[-1]
    toza_matn = sarlavha.replace(f"({kino_kodi})", "")
    toza_matn = re.sub(r"(?i)vip", "", toza_matn).strip()
    is_vip = "vip" in sarlavha.lower()

    await db.kino_saqlash(kino_kodi, message.message_id, toza_matn, is_vip)
    log.info("Kino saqlandi: kod=%s vip=%s", kino_kodi, is_vip)


# ==========================================
# 2. START
# ==========================================

@dp.message(CommandStart())
async def start_xabar(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id

    taklif_qilgan: Optional[int] = None
    arg = (command.args or "").strip()
    if arg.isdigit() and int(arg) != user_id:
        taklif_qilgan = int(arg)

    yangi = await db.foydalanuvchi_qoshish(
        user_id,
        username=message.from_user.username,
        ism=message.from_user.full_name,
        taklif_qilgan=taklif_qilgan,
    )

    # Referal faqat haqiqatan yangi foydalanuvchi uchun hisoblanadi
    if yangi and taklif_qilgan and await db.foydalanuvchi_bormi(taklif_qilgan):
        yangi_soni = await db.referal_qoshish(taklif_qilgan)
        if yangi_soni >= config.REFERAL_KERAK:
            await db.referal_tozalash(taklif_qilgan)
            await db.vip_berish(taklif_qilgan)
            try:
                await bot.send_message(
                    taklif_qilgan,
                    f"🎉 Tabriklaymiz! Siz botga {config.REFERAL_KERAK} ta do'stingizni "
                    f"taklif qildingiz va <b>{config.VIP_KUNLAR} KUNLIK 💎 VIP statusini</b> "
                    "qo'lga kiritdingiz! Endi barcha yopiq kinolarni ko'ra olasiz.",
                )
            except Exception:
                pass
        else:
            qoldi = config.REFERAL_KERAK - yangi_soni
            try:
                await bot.send_message(
                    taklif_qilgan,
                    f"👥 Yangi do'stingiz qo'shildi! Takliflaringiz: <b>{yangi_soni}</b> ta.\n"
                    f"💎 VIP uchun yana <b>{qoldi}</b> ta kerak.",
                )
            except Exception:
                pass

    if await obunani_tekshirish(user_id):
        await message.answer(
            "👋 Assalomu alaykum! <b>OSKAR KINOLAR</b> botiga xush kelibsiz.\n"
            "🎬 Kino ko'rish uchun uning <b>kodini</b> yuboring.",
            reply_markup=asosiy_menyu,
        )
    else:
        await obunaga_undash(message)


# ==========================================
# 3. KABINET VA TASODIFIY KINO
# ==========================================

@dp.message(F.text == "👤 Shaxsiy kabinet")
async def referal_menyu(message: Message) -> None:
    user_id = message.from_user.id
    bot_info = await bot.me()
    takliflar = await db.referal_soni(user_id)
    silka = f"https://t.me/{bot_info.username}?start={user_id}"

    if config.is_admin(user_id):
        holat = "Admin 👑"
    elif await db.vip_mi(user_id):
        holat = f"💎 VIP (yana {await db.vip_qolgan_kun(user_id)} kun qoldi)"
    else:
        holat = "Oddiy"

    await message.answer(
        f"👤 <b>Sizning shaxsiy kabinetingiz</b>\n\n"
        f"Holatingiz: {holat}\n"
        f"👥 Taklif qilgan do'stlaringiz: {takliflar} ta "
        f"(VIP uchun {config.REFERAL_KERAK} ta kerak)\n\n"
        f"🔗 <b>Sizning tarqatish silkangiz:</b>\n{silka}\n\n"
        f"<i>Shu silkani do'stlaringizga yuboring — ular botga kirsa sizga ball yoziladi.</i>"
    )


@dp.message(F.text == "🎲 Tasodifiy kino")
async def tasodifiy_kino_berish(message: Message) -> None:
    if not await obunani_tekshirish(message.from_user.id):
        await obunaga_undash(message)
        return

    vip_ruxsat = await db.vip_mi(message.from_user.id)
    kino = await db.tasodifiy_kino(vip_ruxsat)
    if kino is None:
        await message.answer("❌ Hozircha siz uchun ochiq kinolar topilmadi.")
        return

    xabar_id, toza_matn = kino
    await message.answer("🎲 <b>Siz uchun tasodifiy kino tanlandi!</b>")
    await kinoni_yuborish(message.from_user.id, xabar_id, toza_matn, message)


async def kinoni_yuborish(
    chat_id: int, xabar_id: int, toza_matn: str, message: Message
) -> None:
    bot_info = await bot.me()
    imzo = f"🤖 Bizning bot: @{bot_info.username}"
    yakuniy_matn = f"{toza_matn}\n\n{imzo}" if toza_matn else imzo
    try:
        # parse_mode=None — kino sarlavhasida < > belgilari bo'lsa xato bermasin
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=config.BAZA_KANAL_ID,
            message_id=xabar_id,
            caption=yakuniy_matn,
            parse_mode=None,
        )
    except Exception as e:
        log.warning("Kinoni yuborib bo'lmadi (xabar_id=%s): %s", xabar_id, e)
        await message.answer(
            "❌ Kinoni yuklashda xatolik. Kino kanaldan o'chirilgan bo'lishi mumkin."
        )


@dp.callback_query(F.data == "tekshirish")
async def tasdiqlash_tugmasi(call: CallbackQuery) -> None:
    if await obunani_tekshirish(call.from_user.id, keshdan=False):
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(
            "✅ Obuna tasdiqlandi! Kino kodini yuborishingiz mumkin.",
            reply_markup=asosiy_menyu,
        )
    else:
        await call.answer("❌ Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)


# ==========================================
# 4. ADMIN BUYRUQLARI
# ==========================================

@dp.message(Command("help"), Admin())
async def yordam(message: Message) -> None:
    await message.answer(
        "🛠 <b>Admin buyruqlari</b>\n\n"
        "/stat — statistika\n"
        "/addkanal <code>@kanal</code> — majburiy kanal qo'shish\n"
        "/delkanal <code>@kanal</code> — kanalni olib tashlash\n"
        "/kanallar — majburiy kanallar ro'yxati\n"
        "/tarqat — <i>xabarga reply qilib</i> yuborsangiz hammaga tarqatiladi\n"
        "/vip <code>id [kun]</code> — VIP berish\n"
        "/delvip <code>id</code> — VIP ni olib tashlash\n"
        "/delkino <code>kod</code> — kinoni bazadan o'chirish\n\n"
        "<b>Kino qo'shish:</b> baza kanalga kinoni tashlaysiz, sarlavhaga qavs "
        "ichida kod yozasiz — <code>Titanik (1997) (125)</code>. "
        "VIP kino bo'lsa sarlavhaga <code>vip</code> so'zini qo'shing."
    )


@dp.message(Command("addkanal"), Admin())
async def kanal_qoshish(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Format: <code>/addkanal @kanal</code>")
        return
    kanal = command.args.split()[0]
    if not kanal.startswith("@"):
        kanal = "@" + kanal
    await db.kanal_qoshish(kanal)
    _obuna_kesh.clear()
    await message.answer(f"✅ {kanal} majburiy kanallar ro'yxatiga qo'shildi!")


@dp.message(Command("delkanal"), Admin())
async def kanal_ochirish(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Format: <code>/delkanal @kanal</code>")
        return
    kanal = command.args.split()[0]
    if not kanal.startswith("@"):
        kanal = "@" + kanal
    ochirildi = await db.kanal_ochirish(kanal)
    _obuna_kesh.clear()
    await message.answer(
        f"🗑 {kanal} o'chirildi!" if ochirildi else f"❌ {kanal} ro'yxatda yo'q."
    )


@dp.message(Command("kanallar"), Admin())
async def kanallar_royxati(message: Message) -> None:
    kanallar = await db.kanallar()
    if not kanallar:
        await message.answer("📢 Majburiy kanal yo'q — bot hammaga ochiq.")
        return
    await message.answer(
        "📢 <b>Majburiy kanallar</b>\n\n" + "\n".join(f"• {k}" for k in kanallar)
    )


@dp.message(Command("vip"), Admin())
async def vip_berish_buyruq(message: Message, command: CommandObject) -> None:
    qismlar = (command.args or "").split()
    if not qismlar or not qismlar[0].isdigit():
        await message.answer(
            "Format: <code>/vip 123456789 30</code>\n<i>(kun ko'rsatilmasa "
            f"{config.VIP_KUNLAR} kun beriladi)</i>"
        )
        return
    user_id = int(qismlar[0])
    kun = int(qismlar[1]) if len(qismlar) > 1 and qismlar[1].isdigit() else config.VIP_KUNLAR
    await db.vip_berish(user_id, kun * 86400)
    await message.answer(f"✅ <code>{user_id}</code> ga {kun} kunlik VIP berildi.")
    try:
        await bot.send_message(
            user_id,
            f"🎉 Sizga <b>{kun} kunlik 💎 VIP status</b> berildi! "
            "Endi barcha yopiq kinolarni ko'ra olasiz.",
        )
    except Exception:
        pass


@dp.message(Command("delvip"), Admin())
async def vip_ochirish_buyruq(message: Message, command: CommandObject) -> None:
    qismlar = (command.args or "").split()
    if not qismlar or not qismlar[0].isdigit():
        await message.answer("Format: <code>/delvip 123456789</code>")
        return
    user_id = int(qismlar[0])
    ochirildi = await db.vip_ochirish(user_id)
    await message.answer(
        f"🗑 <code>{user_id}</code> dan VIP olib tashlandi."
        if ochirildi
        else f"❌ <code>{user_id}</code> VIP emas edi."
    )


@dp.message(Command("delkino"), Admin())
async def kino_ochirish_buyruq(message: Message, command: CommandObject) -> None:
    kod = (command.args or "").strip()
    if not kod.isdigit():
        await message.answer("Format: <code>/delkino 125</code>")
        return
    ochirildi = await db.kino_ochirish(kod)
    await message.answer(
        f"🗑 {kod} kodli kino bazadan o'chirildi." if ochirildi else f"❌ {kod} kodli kino yo'q."
    )


# ==========================================
# 5. REKLAMA TARQATISH
# ==========================================

_tarqatish_ketmoqda = False


@dp.message(Command("tarqat"), Admin())
async def reklama_tarqatish(message: Message) -> None:
    global _tarqatish_ketmoqda

    if not message.reply_to_message:
        await message.answer(
            "📢 Tarqatmoqchi bo'lgan xabarga <b>reply</b> qilib <code>/tarqat</code> yozing."
        )
        return
    if _tarqatish_ketmoqda:
        await message.answer("⏳ Oldingi tarqatish hali tugamadi.")
        return

    foydalanuvchilar = await db.faol_foydalanuvchilar()
    jami = len(foydalanuvchilar)
    if jami == 0:
        await message.answer("❌ Yuborish uchun foydalanuvchi yo'q.")
        return

    _tarqatish_ketmoqda = True
    oraliq = 1.0 / config.TARQATISH_TEZLIGI
    daqiqa = round(jami * oraliq / 60, 1)
    holat = await message.answer(
        f"⏳ Tarqatilmoqda... 0/{jami}\n<i>Taxminan {daqiqa} daqiqa</i>"
    )

    yuborildi = bloklagan = xato = 0
    try:
        for i, user_id in enumerate(foydalanuvchilar, 1):
            natija = await _bitta_yuborish(user_id, message)
            if natija == "ok":
                yuborildi += 1
            elif natija == "blok":
                bloklagan += 1
            else:
                xato += 1

            if i % 25 == 0:
                foiz = round(i * 100 / jami)
                try:
                    await holat.edit_text(
                        f"⏳ Tarqatilmoqda... {foiz}%\n\n"
                        f"✅ Yuborildi: {yuborildi}\n"
                        f"🚫 Bloklagan: {bloklagan}\n"
                        f"⚠️ Xato: {xato}\n"
                        f"👥 Jami: {jami}"
                    )
                except Exception:
                    pass
            await asyncio.sleep(oraliq)
    finally:
        _tarqatish_ketmoqda = False

    try:
        await holat.edit_text(
            f"✅ <b>Tarqatish tugadi</b>\n\n"
            f"✅ Yuborildi: <b>{yuborildi}</b>\n"
            f"🚫 Botni bloklaganlar: {bloklagan}\n"
            f"⚠️ Boshqa xatolar: {xato}\n"
            f"👥 Jami urinish: {jami}\n\n"
            f"<i>Bloklaganlar belgilab qo'yildi — keyingi tarqatishda "
            f"ularga urinilmaydi, tarqatish tezlashadi.</i>"
        )
    except Exception:
        pass


async def _bitta_yuborish(user_id: int, message: Message) -> str:
    """Bitta foydalanuvchiga yuborish. Natija: ok | blok | xato"""
    for urinish in range(2):
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id,
            )
            return "ok"
        except TelegramRetryAfter as e:
            if urinish == 0:
                await asyncio.sleep(e.retry_after + 1)
                continue
            return "xato"
        except TelegramForbiddenError:
            await db.bloklangan_belgilash(user_id, True)
            return "blok"
        except Exception as e:
            matn = str(e).lower()
            if "chat not found" in matn or "user is deactivated" in matn:
                await db.bloklangan_belgilash(user_id, True)
                return "blok"
            return "xato"
    return "xato"


# ==========================================
# 6. STATISTIKA
# ==========================================

@dp.message(Command("stat"), Admin())
async def statistika_korish(message: Message) -> None:
    s = await db.statistika()
    await message.answer(
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Jami foydalanuvchi: <b>{s['odamlar']}</b>\n"
        f"🆕 Bugun qo'shilgan: <b>{s['bugun_yangi']}</b>\n"
        f"🔥 Bugun faol: <b>{s['bugun_faol']}</b>\n"
        f"🚫 Botni bloklaganlar: {s['bloklaganlar']}\n\n"
        f"🎬 Kinolar: <b>{s['kinolar']}</b> ta\n"
        f"💎 VIP kinolar: {s['vip_kinolar']} ta\n"
        f"👑 VIP odamlar: {s['vip_odamlar']} ta\n"
        f"📢 Majburiy kanallar: {s['kanallar']} ta"
    )


# ==========================================
# 7. KINO KODI BO'YICHA YUBORISH (oxirgi handler)
# ==========================================

@dp.message(F.text)
async def kino_yuborish(message: Message) -> None:
    kod = (message.text or "").strip()

    if not await obunani_tekshirish(message.from_user.id):
        await obunaga_undash(message)
        return

    if not kod.isdigit():
        await message.answer(
            "🎬 Kino <b>kodini</b> yuboring (masalan: <code>125</code>).\n\n"
            "Kodlarni kanalimizdan topasiz. Yoki «🎲 Tasodifiy kino» tugmasini bosing."
        )
        return

    kino = await db.kino_olish(kod)
    if kino is None:
        await message.answer("❌ Kechirasiz, bunday kodli kino topilmadi.")
        return

    xabar_id, toza_matn, is_vip = kino

    if is_vip and not await db.vip_mi(message.from_user.id):
        bot_info = await bot.me()
        silka = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
        takliflar = await db.referal_soni(message.from_user.id)
        qoldi = max(0, config.REFERAL_KERAK - takliflar)
        await message.answer(
            f"🔒 <b>Bu yopiq (VIP) kino!</b>\n\n"
            f"Ko'rish uchun sizda <b>VIP status</b> bo'lishi kerak. Buning uchun "
            f"pastdagi silkangizni do'stlaringizga yuboring va botga "
            f"<b>{config.REFERAL_KERAK} ta do'stingizni</b> taklif qiling.\n\n"
            f"📊 Hozirgi takliflaringiz: {takliflar} ta (yana {qoldi} ta kerak)\n\n"
            f"🔗 <b>Sizning tarqatish silkangiz:</b>\n{silka}"
        )
        return

    await kinoni_yuborish(message.from_user.id, xabar_id, toza_matn, message)


# ==========================================
# ISHGA TUSHIRISH
# ==========================================

BUYRUQLAR = [
    BotCommand(command="start", description="Botni ishga tushirish"),
]


async def main() -> None:
    xatolar = config.tekshir()
    if xatolar:
        for x in xatolar:
            log.error("Sozlama xatosi: %s", x)
        log.error(".env faylini to'ldiring (.env.example dan nusxa oling).")
        raise SystemExit(1)

    await db.ulanish()
    me = await bot.me()
    log.info("Bot ishga tushdi: @%s | adminlar: %s", me.username, config.ADMIN_IDS)

    try:
        await bot.set_my_commands(BUYRUQLAR)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.yopish()
        await bot.session.close()
        log.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
