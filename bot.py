import asyncio
import os
import re
import sqlite3
from datetime import date
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8695463059:AAHQeb0w4OBLc3h8Xezk9IkFMYPPzqRHorY"

# Katta maqsad: 350 million so'm
TARGET_GOAL = 350_000_000

ADMIN_ID = 7559048140
USERS = {
    7559048140: "Murod",
    692189214: "Muhammadali",
}

conn = sqlite3.connect("seyf.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    date TEXT
)
""")
conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")

def generate_progress_bar(current: int, target: int, length: int = 10) -> str:
    percent = (current / target) * 100 if target > 0 else 0
    filled_length = int(length * current // target) if target > 0 else 0
    filled_length = min(max(filled_length, 0), length)
    bar = "▓" * filled_length + "░" * (length - filled_length)
    remaining = max(target - current, 0)
    
    return (
        f"🎯 **Maqsad:** {format_money(target)} so'm\n"
        f"`[{bar}]` **{percent:.1f}%**\n"
        f"🔒 **Seyfda:** {format_money(current)} so'm\n"
        f"⏳ **Qolgan summa:** {format_money(remaining)} so'm"
    )

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id not in USERS:
        await message.answer("Kechirasiz, bu bot faqat kassa egalari uchun.")
        return
    name = USERS[message.from_user.id]
    await message.answer(
        f"Assalomu alaykum, {name}!\n\n"
        f"Kassaga pul solganingizda faqat summani yozing (Masalan: 200.000 yoki 200000).\n\n"
        f"📊 Umumiy hisobot: /xisobot\n"
        f"🔄 Kassani 0 qilish: /tozalash"
    )

@dp.message(Command("xisobot"))
async def report_handler(message: types.Message):
    if message.from_user.id not in USERS:
        return

    today = date.today().isoformat()
    text = "📊 **Seyfdagi umumiy holat:**\n\n"
    total_seyf = 0

    for uid, name in USERS.items():
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (uid,))
        total_user = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND date = ?", (uid, today))
        today_user = cursor.fetchone()[0] or 0

        total_seyf += total_user
        text += f"👤 **{name}:**\n"
        text += f"   • Bugun: {format_money(today_user)} so'm\n"
        text += f"   • Jami: {format_money(total_user)} so'm\n\n"

    progress_text = generate_progress_bar(total_seyf, TARGET_GOAL)
    text += f"{progress_text}"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("tozalash"))
async def reset_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in USERS:
        return

    if uid != ADMIN_ID:
        await message.answer("❌ Kassani 0 qilish huquqi faqat Murodga berilgan.")
        return

    cursor.execute("DELETE FROM transactions")
    conn.commit()

    tozalash_xabari = "🔄 **Seyf Murod tomonidan tozalandi!**\nBarcha hisoblar 0 ga tenglashtirildi."
    for user_id in USERS:
        try:
            await bot.send_message(user_id, tozalash_xabari, parse_mode="Markdown")
        except Exception:
            pass

@dp.callback_query(F.data.startswith("bekor_"))
async def cancel_transaction(callback: types.CallbackQuery):
    tx_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT user_id, amount FROM transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()

    if not row:
        await callback.answer("Bu amal allaqachon bekor qilingan yoki topilmadi.", show_alert=True)
        return

    tx_user_id, amount = row
    if callback.from_user.id != tx_user_id and callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat o'zingiz kiritgan summani bekor qila olasiz!", show_alert=True)
        return

    cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()

    cursor.execute("SELECT SUM(amount) FROM transactions")
    seyf_total = cursor.fetchone()[0] or 0
    progress_text = generate_progress_bar(seyf_total, TARGET_GOAL)

    sender_name = USERS[tx_user_id]
    await callback.message.edit_text(
        f"❌ **Xato summa bekor qilindi:** -{format_money(amount)} so'm\n\n"
        f"{progress_text}",
        parse_mode="Markdown"
    )

    for other_id in USERS:
        if other_id != callback.from_user.id:
            try:
                await bot.send_message(
                    other_id,
                    f"⚠️ **{sender_name} adashib kiritgan summani bekor qildi:** -{format_money(amount)} so'm\n\n"
                    f"{progress_text}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    await callback.answer("Summa muvaffaqiyatli bekor qilindi!")

@dp.message()
async def money_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in USERS:
        return

    raw_text = message.text.strip() if message.text else ""
    cleaned_digits = re.sub(r"[^\d]", "", raw_text)
    allowed_format = bool(re.match(r"^[\d\s.,]+$", raw_text))

    if not cleaned_digits or not allowed_format:
        await message.answer("⚠️ **Bu botga faqat summa yozing!**\n(Masalan: 200000 yoki 50.000)", parse_mode="Markdown")
        return

    amount = int(cleaned_digits)
    if amount <= 0:
        await message.answer("⚠️ Summa 0 dan katta bo'lishi kerak.")
        return

    today = date.today().isoformat()
    sender_name = USERS[uid]

    cursor.execute("INSERT INTO transactions (user_id, amount, date) VALUES (?, ?, ?)", (uid, amount, today))
    conn.commit()
    tx_id = cursor.lastrowid

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND date = ?", (uid, today))
    today_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (uid,))
    user_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions")
    seyf_total = cursor.fetchone()[0] or 0

    progress_text = generate_progress_bar(seyf_total, TARGET_GOAL)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Adashdim (Bekor qilish)", callback_data=f"bekor_{tx_id}")]
    ])

    javob_egasi = (
        f"✅ **Seyfga qo'shildi:** +{format_money(amount)} so'm\n\n"
        f"👤 **{sender_name}:**\n"
        f"• Bugun tashlaganingiz: {format_money(today_total)} so'm\n"
        f"• Shu paytgacha jami: {format_money(user_total)} so'm\n\n"
        f"{progress_text}"
    )
    await message.answer(javob_egasi, reply_markup=keyboard, parse_mode="Markdown")

    sherik_xabari = (
        f"🔔 **{sender_name} seyfga pul qo'shdi:** +{format_money(amount)} so'm\n\n"
        f"👤 **{sender_name} hisobi:**\n"
        f"• Bugun: {format_money(today_total)} so'm\n"
        f"• Jami: {format_money(user_total)} so'm\n\n"
        f"{progress_text}"
    )
    for other_id in USERS:
        if other_id != uid:
            try:
                await bot.send_message(other_id, sherik_xabari, parse_mode="Markdown")
            except Exception:
                pass

# Serverni uyg'oq saqlash uchun oddiy ping manzili
async def handle_ping(request):
    return web.Response(text="Bot faol ishlamoqda!")

# Cron-job orqali ertalab 09:00 da chaqiriladigan manzil
async def handle_morning_reminder(request):
    for uid, name in USERS.items():
        msg = f"🌅 **Salom {name}, yangi do'konga pul yig'ish kerak bugun seyfga pul tashlang!**"
        try:
            await bot.send_message(uid, msg, parse_mode="Markdown")
        except Exception:
            pass
    return web.Response(text="Eslatmalar yuborildi!")

async def main():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/morning-reminder", handle_morning_reminder)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
