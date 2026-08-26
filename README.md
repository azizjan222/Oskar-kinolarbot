# 🎬 OSKAR KINOLAR bot

Kino kodini yuborsa — kinoni jo'natadigan Telegram bot. Majburiy kanal obunasi,
referal orqali VIP status va admin panel bilan.

## Qanday ishlaydi

1. Kinoni **baza kanalga** tashlaysiz, sarlavhasiga qavs ichida kod yozasiz:
   `Titanik (1997) (125)` → bot avtomatik saqlaydi, kod = `125`
2. VIP kino qilish uchun sarlavhaga `vip` so'zini qo'shasiz
3. Foydalanuvchi botga `125` deb yozadi → kino keladi
4. VIP kinoni ko'rish uchun foydalanuvchi 10 ta do'st taklif qilishi kerak
   (yoki admin `/vip` bilan beradi)

Kinolarning o'zi kanalda qoladi — bot faqat `copy_message` bilan nusxa
jo'natadi. Shuning uchun bot fayllarni saqlamaydi va joy egallamaydi.

## O'rnatish

```bash
git clone https://github.com/azizjan222/Oskar-kinolarbot.git
cd Oskar-kinolarbot

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env          # BOT_TOKEN, BAZA_KANAL_ID, ADMIN_IDS ni to'ldiring

python main.py
```

Bot baza kanalda **admin** bo'lishi kerak — aks holda kinolarni ko'rmaydi va
nusxa jo'nata olmaydi.

## Admin buyruqlari

| Buyruq | Vazifasi |
|---|---|
| `/stat` | statistika: foydalanuvchilar, bugungi, faol, kinolar, VIP |
| `/addkanal @kanal` | majburiy kanal qo'shish |
| `/delkanal @kanal` | kanalni olib tashlash |
| `/kanallar` | majburiy kanallar ro'yxati |
| `/tarqat` | xabarga **reply** qilib yuborilsa — hammaga tarqatiladi |
| `/vip <id> [kun]` | qo'lda VIP berish |
| `/delvip <id>` | VIP ni olib tashlash |
| `/delkino <kod>` | kinoni bazadan o'chirish |
| `/help` | buyruqlar ro'yxati |

## Serverda 24/7 ishlatish

```ini
# /etc/systemd/system/oskarbot.service
[Unit]
Description=Oskar Kinolar Bot
After=network.target

[Service]
WorkingDirectory=/root/Oskar-kinolarbot
ExecStart=/root/Oskar-kinolarbot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now oskarbot
journalctl -u oskarbot -f     # loglarni ko'rish
```

## Fayllar

```
main.py    — bot va barcha handlerlar
config.py  — sozlamalar (.env dan o'qiladi)
db.py      — baza (aiosqlite): kinolar, foydalanuvchilar, VIP, referal, kanallar
```

## Xavfsizlik

Token, kanal ID va admin ID **`.env` faylida** turadi va git'ga tushmaydi.
Tokenni hech qachon kod ichiga yozmang — repo ochiq bo'lsa istagan odam
botingizni egallab oladi.
