import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

TOKEN = "9080559382:AAHetIj4JeMCJLt2lEFdgZXsnsEGMp2oy4A"
CHANNEL_USERNAME = "@somsapos"

# --- ADMINLAR ---
ADMIN_IDS = [7995649103, 6342803772]  # Asilbek va @Xomidjonov_a ning ID raqamlari
ADMIN_USERNAMES = ["Asilbek6008", "Xomidjonov_a"]
APK_PATH = Path(__file__).parent / "app-release.apk"


# Admin ekanligini tekshiruvchi yordamchi funksiya
def is_admin(user_id: int, username: str) -> bool:
    if user_id in ADMIN_IDS:
        return True
    if username and username.lower() in [u.lower() for u in ADMIN_USERNAMES]:
        return True
    return False


# Bazani sozlash (faqat foydalanuvchilarni saqlash uchun)
def init_db():
    conn = sqlite3.connect("bot_base.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    conn.commit()
    conn.close()


init_db()


def get_db():
    return sqlite3.connect("bot_base.db")


bot = Bot(token=TOKEN)
dp = Dispatcher()


async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


async def show_main_menu(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 APK yuklash", callback_data="get_apk")]
    ])
    
    # Agar foydalanuvchi admin bo'lsa, Admin Panel tugmasi qo'shiladi
    if is_admin(user_id, username):
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")]
        )
        
    await message.answer(
        "Assalomu alaykum! Xush kelibsiz. Kerakli bo'limni tanlang:",
        reply_markup=keyboard
    )


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username or ""

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, full_name, username, status) VALUES (?, ?, ?, ?)",
            (user_id, full_name, username, "active")
        )
    else:
        cursor.execute("UPDATE users SET status = 'active', username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()

    if not await check_subscription(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish",
                                   url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
        ])
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanalimizga obuna bo'lishingiz kerak:",
            reply_markup=keyboard
        )
        return

    await show_main_menu(message)


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await show_main_menu(callback.message)
    else:
        await callback.answer("Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)


# APK yuborish
@dp.callback_query(F.data == "get_apk")
async def get_apk(callback: CallbackQuery):
    user_id = callback.from_user.id

    if not await check_subscription(user_id):
        await callback.answer("Avval kanalga obuna bo'ling!", show_alert=True)
        return

    if not APK_PATH.exists():
        await callback.answer("Fayl topilmadi, admin bilan bog'laning.", show_alert=True)
        return

    await callback.answer()
    await bot.send_document(
        chat_id=callback.message.chat.id,
        document=FSInputFile(APK_PATH),
        caption="📱 Somsa pos dasturini.\nO'rnatish uchun faylni oching.",
    )


@dp.callback_query(F.data == "back_home")
async def back_home(callback: CallbackQuery):
    await callback.message.delete()
    await show_main_menu(callback.message)


# --- ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
    active_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'blocked'")
    blocked_users = cursor.fetchone()[0]
    conn.close()

    text = (
        f"👑 **Admin Panel**\n\n"
        f"📊 **Statistika:**\n"
        f"👥 Jami kirganlar: {total_users}\n"
        f"✅ Hozirda faollar: {active_users}\n"
        f"❌ Botni tark etganlar/bloklaganlar: {blocked_users}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="back_home")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


# --- RENDER UCHUN PORT OCHUVCHI WEB SERVER ---
async def handle(request):
    return web.Response(text="Bot ishlayapti!")


async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()


async def main():
    await web_server()
    print("Bot va veb-server muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
