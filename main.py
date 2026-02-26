import asyncio
import re
import time
import random
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject

# Bot tokeni va ID'lar
TOKEN = "8398806896:AAH33LHZDY22nTfajwXp1eVTWygnDisGxCc"
BAZA_KANAL_ID = -1002496334857 
ADMIN_ID = 5660204735 

bot = Bot(token=TOKEN)
dp = Dispatcher()

VIP_MUDDATI = 30 * 24 * 60 * 60 # 30 kun

# ==========================================
# MA'LUMOTLAR BAZASINI YARATISH (SQLITE)
# ==========================================
conn = sqlite3.connect("baza.db", check_same_thread=False)
cursor = conn.cursor()

# Jadvallarni yaratamiz
cursor.execute('CREATE TABLE IF NOT EXISTS kinolar (kod TEXT PRIMARY KEY, xabar_id INTEGER, toza_matn TEXT, vip INTEGER)')
cursor.execute('CREATE TABLE IF NOT EXISTS foydalanuvchilar (id INTEGER PRIMARY KEY)')
cursor.execute('CREATE TABLE IF NOT EXISTS kanallar (kanal TEXT PRIMARY KEY)')
cursor.execute('CREATE TABLE IF NOT EXISTS referallar (id INTEGER PRIMARY KEY, soni INTEGER)')
cursor.execute('CREATE TABLE IF NOT EXISTS viplar (id INTEGER PRIMARY KEY, vaqt REAL)')
conn.commit()

# ==========================================
# BAZA BILAN ISHLASH FUNKSIYALARI
# ==========================================
def get_majburiy_kanallar():
    cursor.execute('SELECT kanal FROM kanallar')
    return [row[0] for row in cursor.fetchall()]

def get_referal_soni(user_id):
    cursor.execute('SELECT soni FROM referallar WHERE id=?', (user_id,))
    res = cursor.fetchone()
    return res[0] if res else 0

def add_referal(user_id):
    soni = get_referal_soni(user_id) + 1
    cursor.execute('REPLACE INTO referallar (id, soni) VALUES (?, ?)', (user_id, soni))
    conn.commit()
    return soni

def reset_referal(user_id):
    cursor.execute('REPLACE INTO referallar (id, soni) VALUES (?, ?)', (user_id, 0))
    conn.commit()

def check_vip(user_id):
    if user_id == ADMIN_ID: return True
    cursor.execute('SELECT vaqt FROM viplar WHERE id=?', (user_id,))
    res = cursor.fetchone()
    if res:
        if time.time() < res[0]: 
            return True
        else:
            cursor.execute('DELETE FROM viplar WHERE id=?', (user_id,))
            conn.commit()
    return False

# ==========================================
# ASOSIY MENYU VA OBUNA TUGMALARI
# ==========================================
asosiy_menyu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Shaxsiy kabinet"), KeyboardButton(text="🎲 Tasodifiy kino")]
    ], resize_keyboard=True
)

def obuna_klaviaturasi():
    tugmalar = []
    for kanal in get_majburiy_kanallar():
        url = f"https://t.me/{kanal.replace('@', '')}"
        tugmalar.append([InlineKeyboardButton(text=f"📢 {kanal} ga o'tish", url=url)])
    tugmalar.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="tekshirish")])
    return InlineKeyboardMarkup(inline_keyboard=tugmalar)

async def obunani_tekshirish(user_id):
    kanallar = get_majburiy_kanallar()
    if not kanallar: return True 
    for kanal in kanallar:
        if kanal.lower().endswith('bot'): continue
        try:
            azo = await bot.get_chat_member(chat_id=kanal, user_id=user_id)
            if azo.status in ['left', 'kicked']: return False
        except Exception: pass 
    return True

# ==========================================
# 1. KANALDAN KINO SAQLASH (Endi Bazaga yoziladi)
# ==========================================
@dp.channel_post(F.chat.id == BAZA_KANAL_ID)
async def kanaldan_kino_saqlash(message: Message):
    sarlavha = message.caption or message.text or ""
    barcha_kodlar = re.findall(r'\((\d+)\)', sarlavha)
    
    if barcha_kodlar:
        kino_kodi = barcha_kodlar[-1]
        toza_matn = sarlavha.replace(f"({kino_kodi})", "")
        toza_matn = re.sub(r'(?i)vip', '', toza_matn).strip()
        is_vip = 1 if "vip" in sarlavha.lower() else 0
        
        cursor.execute('REPLACE INTO kinolar (kod, xabar_id, toza_matn, vip) VALUES (?, ?, ?, ?)', 
                       (kino_kodi, message.message_id, toza_matn, is_vip))
        conn.commit()
        print(f"✅ BAZAGA SAQLANDI! Kodi: {kino_kodi}")

# ==========================================
# 2. START TUGMASI 
# ==========================================
@dp.message(CommandStart())
async def start_xabar(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    # Yangi odamni bazaga qo'shish
    cursor.execute('SELECT id FROM foydalanuvchilar WHERE id=?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO foydalanuvchilar (id) VALUES (?)', (user_id,))
        conn.commit()
        
        # Referal tizimi
        taklif_qilgan_id = command.args
        if taklif_qilgan_id and taklif_qilgan_id.isdigit():
            taklif_qilgan_id = int(taklif_qilgan_id)
            if taklif_qilgan_id != user_id:
                cursor.execute('SELECT id FROM foydalanuvchilar WHERE id=?', (taklif_qilgan_id,))
                if cursor.fetchone():
                    yangi_soni = add_referal(taklif_qilgan_id)
                    if yangi_soni >= 10:
                        reset_referal(taklif_qilgan_id)
                        cursor.execute('REPLACE INTO viplar (id, vaqt) VALUES (?, ?)', (taklif_qilgan_id, time.time() + VIP_MUDDATI))
                        conn.commit()
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
    takliflar = get_referal_soni(user_id)
    silka = f"https://t.me/{bot_info.username}?start={user_id}"
    
    if check_vip(user_id):
        if user_id == ADMIN_ID:
            status = "Admin"
        else:
            cursor.execute('SELECT vaqt FROM viplar WHERE id=?', (user_id,))
            qolgan_sekundlar = cursor.fetchone()[0] - time.time()
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
        
    cursor.execute('SELECT kod, xabar_id, toza_matn, vip FROM kinolar')
    barcha_kinolar = cursor.fetchall()
    
    if not barcha_kinolar:
        await message.answer("❌ Hozircha bazada kinolar yo'q.")
        return

    ruxsat_etilganlar = []
    is_vip = check_vip(message.from_user.id)
    
    for k in barcha_kinolar:
        if k[3] == 1 and not is_vip: continue
        ruxsat_etilganlar.append(k)
        
    if not ruxsat_etilganlar:
        await message.answer("❌ Hozircha siz uchun ochiq kinolar topilmadi.")
        return
        
    tasodifiy_kod = random.choice(ruxsat_etilganlar)
    xabar_id, toza_matn = tasodifiy_kod[1], tasodifiy_kod[2]
    
    bot_info = await bot.get_me()
    yakuniy_matn = f"{toza_matn}\n\n🤖 Bizning bot: @{bot_info.username}" if toza_matn else f"🤖 Bizning bot: @{bot_info.username}"
    
    await message.answer("🎲 <b>Siz uchun tasodifiy kino tanlandi!</b>", parse_mode="HTML")
    try:
        await bot.copy_message(chat_id=message.from_user.id, from_chat_id=BAZA_KANAL_ID, message_id=xabar_id, caption=yakuniy_matn)
    except Exception:
        await message.answer("❌ Kinoni yuklashda xatolik yuz berdi.")

# ==========================================
# 4. ADMIN FUNKSIYALARI
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
            cursor.execute('REPLACE INTO kanallar (kanal) VALUES (?)', (kanal,))
            conn.commit()
            await message.answer(f"✅ {kanal} bazaga qo'shildi!")

@dp.message(Command("delkanal"))
async def kanal_ochirish(message: Message):
    if message.from_user.id == ADMIN_ID:
        matn = message.text.split()
        if len(matn) > 1:
            kanal = matn[1]
            if not kanal.startswith("@"): kanal = "@" + kanal
            cursor.execute('DELETE FROM kanallar WHERE kanal=?', (kanal,))
            conn.commit()
            await message.answer(f"🗑 {kanal} bazadan o'chirildi!")

@dp.message(Command("tarqat"))
async def reklama_tarqatish(message: Message):
    if message.from_user.id == ADMIN_ID and message.reply_to_message:
        cursor.execute('SELECT id FROM foydalanuvchilar')
        foydalanuvchilar = cursor.fetchall()
        yuborildi = 0
        kutish = await message.answer("⏳ Tarqatilmoqda...")
        for user in foydalanuvchilar:
            try:
                await bot.copy_message(chat_id=user[0], from_chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
                yuborildi += 1
                await asyncio.sleep(0.05) 
            except Exception: pass
        await kutish.delete()
        await message.answer(f"✅ {yuborildi} ta foydalanuvchiga tarqatildi!")

@dp.message(Command("stat"))
async def statistika_korish(message: Message):
    if message.from_user.id == ADMIN_ID:
        # Bazadan statistikani sanash
        cursor.execute('SELECT COUNT(*) FROM foydalanuvchilar')
        jami_odamlar = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM kinolar')
        jami_kinolar = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM kinolar WHERE vip=1')
        vip_kinolar = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM viplar')
        vip_odamlar = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM kanallar')
        jami_kanallar = cursor.fetchone()[0]
        
        await message.answer(
            f"📊 <b>BOT STATISTIKASI (BAZA)</b>\n\n"
            f"👥 Jami: {jami_odamlar} ta\n"
            f"🎬 Kinolar: {jami_kinolar} ta\n"
            f"💎 VIP Kinolar: {vip_kinolar} ta\n"
            f"👑 VIP Odamlar: {vip_odamlar} ta\n"
            f"📢 Majburiy obunalar: {jami_kanallar} ta", 
            parse_mode="HTML"
        )

# ==========================================
# 5. KINONI YUBORISH 
# ==========================================
@dp.message(F.text)
async def kino_yuborish(message: Message):
    kod = message.text
    
    if not await obunani_tekshirish(message.from_user.id):
        await message.answer("Botdan to'liq foydalanish uchun kanallarga obuna bo'ling!✅", reply_markup=obuna_klaviaturasi())
        return

    if kod.isdigit():
        cursor.execute('SELECT xabar_id, toza_matn, vip FROM kinolar WHERE kod=?', (kod,))
        kino = cursor.fetchone()
        
        if kino:
            xabar_id, toza_matn, is_vip = kino
            
            if is_vip and not check_vip(message.from_user.id):
                bot_info = await bot.get_me()
                silka = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
                takliflar = get_referal_soni(message.from_user.id)
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

            bot_info = await bot.get_me()
            yakuniy_matn = f"{toza_matn}\n\n🤖 Bizning bot: @{bot_info.username}" if toza_matn else f"🤖 Bizning bot: @{bot_info.username}"
            
            try:
                 await bot.copy_message(chat_id=message.from_user.id, from_chat_id=BAZA_KANAL_ID, message_id=xabar_id, caption=yakuniy_matn)
            except Exception:
                await message.answer("❌ Kinoni yuklashda xatolik yuz berdi.")
        else:
            await message.answer("❌ Kechirasiz, bunday kodli kino topilmadi.")

async def main():
    print("Bot muvaffaqiyatli ishga tushdi va BAZA ulandi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
