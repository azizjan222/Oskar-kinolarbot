import asyncio
import re
import time
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject

# Bot tokeni va ID'lar
TOKEN = "8398806896:AAH33LHZDY22nTfajwXp1eVTWygnDisGxCc"
BAZA_KANAL_ID = -1002496334857 
ADMIN_ID = 5660204735 

bot = Bot(token=TOKEN)
dp = Dispatcher()

kinolar_xotirasi = {}
vip_kinolar = set() 
foydalanuvchilar = set() 
majburiy_kanallar = set() 

referallar = {} 
vip_foydalanuvchilar = {} 
VIP_MUDDATI = 30 * 24 * 60 * 60 # 30 kun

# ==========================================
# ASOSIY MENYU TUGMALARI (Soddalashtirildi)
# ==========================================
asosiy_menyu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Shaxsiy kabinet"), KeyboardButton(text="🎲 Tasodifiy kino")]
    ],
    resize_keyboard=True
)

def obuna_klaviaturasi():
    tugmalar = []
    for kanal in majburiy_kanallar:
        url = f"https://t.me/{kanal.replace('@', '')}"
        tugmalar.append([InlineKeyboardButton(text=f"📢 {kanal} ga o'tish", url=url)])
    tugmalar.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="tekshirish")])
    return InlineKeyboardMarkup(inline_keyboard=tugmalar)

async def obunani_tekshirish(user_id):
    if not majburiy_kanallar: return True 
    for kanal in majburiy_kanallar:
        if kanal.lower().endswith('bot'): continue
        try:
            azo = await bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if azo.status in ['left', 'kicked']: return False
        except Exception: pass 
    return True

def check_vip(user_id):
    if user_id == ADMIN_ID: return True
    if user_id in vip_foydalanuvchilar:
        if time.time() < vip_foydalanuvchilar[user_id]: return True
        else: del vip_foydalanuvchilar[user_id]
    return False

# ==========================================
# 1. KANALDAN KINO SAQLASH
# ==========================================
@dp.channel_post(F.chat.id == BAZA_KANAL_ID)
async def kanaldan_kino_saqlash(message: Message):
    sarlavha = message.caption or message.text or ""
    qidiruv = re.search(r'\((\d+)\)', sarlavha)
    if qidiruv:
        kino_kodi = qidiruv.group(1)
        kinolar_xotirasi[kino_kodi] = message.message_id
        if "vip" in sarlavha.lower():
            vip_kinolar.add(kino_kodi)
            print(f"💎 Yangi VIP kino saqlandi! Kodi: {kino_kodi}")
        else:
            print(f"✅ Yangi kino saqlandi! Kodi: {kino_kodi}")

# ==========================================
# 2. START TUGMASI 
# ==========================================
@dp.message(CommandStart())
async def start_xabar(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    if user_id not in foydalanuvchilar:
        foydalanuvchilar.add(user_id)
        referallar[user_id] = 0
        
        taklif_qilgan_id = command.args
        if taklif_qilgan_id and taklif_qilgan_id.isdigit():
            taklif_qilgan_id = int(taklif_qilgan_id)
            if taklif_qilgan_id != user_id and taklif_qilgan_id in foydalanuvchilar:
                referallar[taklif_qilgan_id] += 1
                if referallar[taklif_qilgan_id] >= 10:
                    referallar[taklif_qilgan_id] -= 10 
                    vip_foydalanuvchilar[taklif_qilgan_id] = time.time() + VIP_MUDDATI
                    try:
                        await bot.send_message(taklif_qilgan_id, "🎉 Tabriklaymiz! Siz botga 10 ta do'stingizni taklif qildingiz va <b>1 OYLIK 💎 VIP Statusini</b> qo'lga kiritdingiz! Endi barcha yopiq kinolarni ko'ra olasiz.", parse_mode="HTML")
                    except Exception: pass

    if await obunani_tekshirish(user_id):
        await message.answer(
            "👋 Assalomu alaykum! OSKAR KINOLAR botiga xush kelibsiz.\n"
            "🎬 Kino ko'rish uchun uning kodini yuboring.", reply_markup=asosiy_menyu
        )
    else:
        await message.answer("Botdan to'liq foydalanish uchun kanallarga obuna bo'ling!✅", reply_markup=obuna_klaviaturasi())

# ==========================================
# 3. KABINET VA TASODIFIY KINO
# ==========================================
@dp.message(F.text == "👤 Shaxsiy kabinet")
async def referal_menyu(message: Message):
    bot_info = await bot.get_me()
    user_id = message.from_user.id
    takliflar = referallar.get(user_id, 0)
    silka = f"https://t.me/{bot_info.username}?start={user_id}"
    
    if check_vip(user_id):
        if user_id == ADMIN_ID:
            status = "Admin"
        else:
            qolgan_sekundlar = vip_foydalanuvchilar[user_id] - time.time()
            qolgan_kunlar = int(qolgan_sekundlar / (24 * 3600))
            status = f"Faol (Yana {qolgan_kunlar} kun qoldi)"
    else:
        status = "Oddiy"
    
    matn = (
        f"👤 <b>Sizning shaxsiy kabinetingiz</b>\n\n"
        f"Holatingiz: {status}\n"
        f"👥 Taklif qilgan do'stlaringiz: {takliflar} ta\n\n"
        f"🔗 <b>Sizning tarqatish silkangiz:</b>\n{silka}\n\n"
        f"<i>(Shu silkani do'stlaringizga yuboring, ular botga kirsa sizga ball yoziladi)</i>"
    )
    
    await message.answer(matn, parse_mode="HTML")

@dp.message(F.text == "🎲 Tasodifiy kino")
async def tasodifiy_kino_berish(message: Message):
    if not await obunani_tekshirish(message.from_user.id):
        await message.answer("Botdan to'liq foydalanish uchun kanallarga obuna bo'ling!✅", reply_markup=obuna_klaviaturasi())
        return
        
    if not kinolar_xotirasi:
        await message.answer("❌ Hozircha bazada kinolar yo'q.")
        return

    ruxsat_etilganlar = []
    is_vip = check_vip(message.from_user.id)
    
    for kod in kinolar_xotirasi.keys():
        if kod in vip_kinolar and not is_vip: continue
        ruxsat_etilganlar.append(kod)
        
    if not ruxsat_etilganlar:
        await message.answer("❌ Hozircha siz uchun ochiq kinolar topilmadi.")
        return
        
    tasodifiy_kod = random.choice(ruxsat_etilganlar)
    xabar_id = kinolar_xotirasi[tasodifiy_kod]
    
    await message.answer("🎲 <b>Siz uchun tasodifiy kino tanlandi!</b>", parse_mode="HTML")
    try:
        await bot.copy_message(chat_id=message.from_user.id, from_chat_id=BAZA_KANAL_ID, message_id=xabar_id)
    except Exception:
        await message.answer("❌ Kinoni yuklashda xatolik yuz berdi.")

# ==========================================
# 4. ADMIN FUNKSIYALARI (Qisqartirilgan)
# ==========================================
@dp.callback_query(F.data == "tekshirish")
async def tasdiqlash_tugmasi(call: CallbackQuery):
    if await obunani_tekshirish(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Obuna tasdiqlandi! Kino kodini yuborishingiz mumkin.", reply_markup=asosiy_menyu)
    else:
        await call.answer("❌ Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

@dp.message(Command("addkanal"))
async def kanal_qoshish(message: Message):
    if message.from_user.id == ADMIN_ID:
        matn = message.text.split()
        if len(matn) > 1:
            kanal = matn[1]
            if not kanal.startswith("@"): kanal = "@" + kanal
            majburiy_kanallar.add(kanal)
            await message.answer(f"✅ {kanal} ro'yxatga qo'shildi!")

@dp.message(Command("delkanal"))
async def kanal_ochirish(message: Message):
    if message.from_user.id == ADMIN_ID:
        matn = message.text.split()
        if len(matn) > 1:
            kanal = matn[1]
            if not kanal.startswith("@"): kanal = "@" + kanal
            if kanal in majburiy_kanallar:
                majburiy_kanallar.remove(kanal)
                await message.answer(f"🗑 {kanal} o'chirildi!")

@dp.message(Command("tarqat"))
async def reklama_tarqatish(message: Message):
    if message.from_user.id == ADMIN_ID and message.reply_to_message:
        yuborildi = 0
        kutish = await message.answer("⏳ Tarqatilmoqda...")
        for user in foydalanuvchilar:
            try:
                await bot.copy_message(chat_id=user, from_chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
                yuborildi += 1
                await asyncio.sleep(0.05) 
            except Exception: pass
        await kutish.delete()
        await message.answer(f"✅ {yuborildi} ta foydalanuvchiga tarqatildi!")

@dp.message(Command("stat"))
async def statistika_korish(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"📊 <b>BOT STATISTIKASI</b>\n\n"
            f"👥 Jami: {len(foydalanuvchilar)} ta\n"
            f"🎬 Kinolar: {len(kinolar_xotirasi)} ta\n"
            f"💎 VIP Kinolar: {len(vip_kinolar)} ta\n"
            f"👑 VIP Odamlar: {len(vip_foydalanuvchilar)} ta\n"
            f"📢 Majburiy obunalar: {len(majburiy_kanallar)} ta", 
            parse_mode="HTML"
        )

# ==========================================
# 5. KINONI YUBORISH (Shu joyda VIP xabar chiqadi)
# ==========================================
@dp.message(F.text)
async def kino_yuborish(message: Message):
    kod = message.text
    
    if not await obunani_tekshirish(message.from_user.id):
        await message.answer("Botdan to'liq foydalanish uchun kanallarga obuna bo'ling!✅", reply_markup=obuna_klaviaturasi())
        return

    if kod in kinolar_xotirasi:
        
        # QACHONKI VIP KINONI SO'RASA SHU XABAR CHIQADI
        if kod in vip_kinolar and not check_vip(message.from_user.id):
            bot_info = await bot.get_me()
            silka = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
            takliflar = referallar.get(message.from_user.id, 0)
            qoldi = 10 - takliflar if takliflar < 10 else 0
            
            await message.answer(
                f"🔒 <b>Bu yopiq (VIP) kino!</b>\n\n"
                f"Siz tanlagan kinoni ko'rish uchun sizda <b>VIP status</b> bo'lishi kerak.\n"
                f"Buning uchun pastdagi shaxsiy silkangizni do'stlaringizga yuboring va botga <b>10 ta do'stingizni</b> taklif qiling.\n\n"
                f"📊 Hozirda sizning takliflaringiz: {takliflar} ta (Yana {qoldi} ta kerak)\n\n"
                f"🔗 <b>Sizning tarqatish silkangiz:</b>\n{silka}", 
                parse_mode="HTML"
            )
            return

        xabar_id = kinolar_xotirasi[kod]
        try:
             await bot.copy_message(chat_id=message.from_user.id, from_chat_id=BAZA_KANAL_ID, message_id=xabar_id)
        except Exception:
            await message.answer("❌ Kinoni yuklashda xatolik yuz berdi.")
    else:
        if kod.isdigit():
            await message.answer("❌ Kechirasiz, bunday kodli kino topilmadi.")

async def main():
    print("Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
