import asyncio
import os
import re
import sqlite3
from datetime import date
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "8695463059:AAH44oCa8nbnDGsGMyU6FH1TTQuQjcEdUss"

USERS = {
    7559048140: "Murod",
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

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id not in USERS:
        await message.answer("Kechirasiz, bu bot faqat kassa egalari uchun.")
        return
    name = USERS[message.from_user.id]
    await message.answer(
        f"Assalomu alaykum, {name}!\n\n"
        f"Kassaga pul solganingizda summani yozing (Masalan: 200.000 yoki 200000).\n"
        f"Umumiy hisobotni ko'rish uchun: /xisobot"
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

    text += f"🔒 **Seyfdagi jami jamg'arma:** {format_money(total_seyf)} so'm"
    await message.answer(text, parse_mode="Markdown")

@dp.message()
async def money_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in USERS:
        return

    cleaned_text = re.sub(r"[^\d]", "", message.text)
    if not cleaned_text:
        await message.answer("Iltimos, summani faqat raqamlarda yozing.")
        return

    amount = int(cleaned_text)
    if amount <= 0:
        await message.answer("Summa 0 dan katta bo'lishi kerak.")
        return

    today = date.today().isoformat()
    name = USERS[uid]

    cursor.execute("INSERT INTO transactions (user_id, amount, date) VALUES (?, ?, ?)", (uid, amount, today))
    conn.commit()

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND date = ?", (uid, today))
    today_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ?", (uid,))
    user_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions")
    seyf_total = cursor.fetchone()[0] or 0

    javob = (
        f"✅ **Seyfga qo'shildi:** +{format_money(amount)} so'm\n\n"
        f"👤 **{name}:**\n"
        f"• Bugun tashlaganingiz: {format_money(today_total)} so'm\n"
        f"• Shu paytgacha jami: {format_money(user_total)} so'm\n\n"
        f"🔒 **Seyfdagi umumiy summa:** {format_money(seyf_total)} so'm"
    )
    await message.answer(javob, parse_mode="Markdown")

async def handle_ping(request):
    return web.Response(text="Seyf bot 24/7 ishlayapti!")

async def main():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
