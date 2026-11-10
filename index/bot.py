import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "9190538462:AAGp-TxR7fm4TDOdoACl5iNJSaV1N5Je4TU"  # Токен от @BotFather
ADMIN_ID = 8967507182                # Ваш Telegram ID (число)
DB_NAME = "subscribers.db"

# Приветственное сообщение с HTML-разметкой для гиперссылок
WELCOME_MESSAGE = """Greetings and welcome. The following is an overview of my projects:

1. <a href="https://github.com/cofiles/">My GitHub profile</a>

2. <a href="https://cofiles.github.io/cof/">Collection of files</a> — A comprehensive repository of essential files for contemporary use. It includes Python packages, links to prominent GitHub repositories, and widely used Windows applications.

The catalog comprises 109,109 entries, organized into 109 topic groups, with 1,001 entries per group.

The content covers software, programming languages, Python packages, and GitHub repositories. No registration or advertising is required.

3. <a href="https://cofiles.github.io/toolbox/">Toolbox</a> — A suite of utilities for encrypting and decrypting text, extracting hashes, testing network connection speeds, and retrieving IP address information."""

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def add_subscriber(user_id: int):
    """Автоматически подписывает пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,))
        conn.commit()
    finally:
        conn.close()

def get_all_subscribers():
    """Возвращает список ID всех подписчиков."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM subscribers")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

# ================= СОСТОЯНИЯ (FSM) =================
class BroadcastState(StatesGroup):
    waiting_for_message = State()

# ================= ИНИЦИАЛИЗАЦИЯ =================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= КЛАВИАТУРА АДМИНИСТРАТОРА =================
def get_admin_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Сделать рассылку")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ================= ОБРАБОТЧИКИ КОМАНД И КНОПОК =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Автоматическая подписка пользователя
    add_subscriber(message.from_user.id)
    
    # Отправка приветствия с HTML-разметкой
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            WELCOME_MESSAGE,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            WELCOME_MESSAGE,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=ReplyKeyboardRemove()
        )

@dp.message(F.text == "Сделать рассылку")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    
    await state.set_state(BroadcastState.waiting_for_message)
    await message.answer(
        "Отправьте сообщение (текст, фото или документ), которое хотите разослать всем подписчикам.\n\n"
        "Для отмены напишите /cancel."
    )

@dp.message(Command("cancel"))
async def cancel_broadcast(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else ReplyKeyboardRemove()
    await message.answer("Рассылка отменена.", reply_markup=kb)

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()
    subscribers = get_all_subscribers()
    
    if not subscribers:
        await message.answer("В базе пока нет подписчиков.", reply_markup=get_admin_keyboard())
        return

    await message.answer(f"Начинаю рассылку для {len(subscribers)} пользователей...")

    success_count = 0
    fail_count = 0

    for sub_id in subscribers:
        try:
            await message.copy_to(chat_id=sub_id)
            success_count += 1
            await asyncio.sleep(0.05)
        except (TelegramForbiddenError, TelegramBadRequest):
            fail_count += 1
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю {sub_id}: {e}")
            fail_count += 1

    await message.answer(
        f"Рассылка завершена!\n\n"
        f"Успешно доставлено: {success_count}\n"
        f"Ошибок: {fail_count}",
        reply_markup=get_admin_keyboard()
    )

# ================= ЗАПУСК =================
async def main():
    init_db()
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())