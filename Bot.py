
import asyncio
import random
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.enums import ChatMemberStatus
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

giveaways = {}
user_states = {}

# ========= UI =========

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Создать розыгрыш", callback_data="create")],
        [InlineKeyboardButton(text="📊 Активные розыгрыши", callback_data="list")]
    ])

def participate_kb(g_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Участвовать", callback_data=f"join_{g_id}")]
    ])

def manage_kb(g_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Завершить", callback_data=f"finish_{g_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

# ========= START =========

@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return

    await message.answer("👋 Панель управления ботом:", reply_markup=main_menu())

# ========= NAV =========

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    await callback.message.edit_text("👋 Панель управления:", reply_markup=main_menu())

# ========= CREATE =========

@dp.callback_query(F.data == "create")
async def create_start(callback: CallbackQuery):
    user_states[callback.from_user.id] = {"step": "text"}
    await callback.message.answer("✏️ Введи текст розыгрыша:")

@dp.message()
async def process(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    state = user_states.get(message.from_user.id)
    if not state:
        return

    step = state["step"]

    if step == "text":
        state["text"] = message.text
        state["step"] = "conditions"
        await message.answer("📋 Условия участия:")

    elif step == "conditions":
        state["conditions"] = message.text
        state["step"] = "subs"
        await message.answer("🔗 Каналы (@channel1 @channel2):")

    elif step == "subs":
        state["subs"] = message.text.split()
        state["step"] = "winners"
        await message.answer("🏆 Кол-во победителей:")

    elif step == "winners":
        state["winners"] = int(message.text)

        g_id = str(len(giveaways) + 1)
        giveaways[g_id] = {
            "text": state["text"],
            "conditions": state["conditions"],
            "subs": state["subs"],
            "winners": state["winners"],
            "participants": set(),
            "active": True
        }

        text = (
            f"🎁 {state['text']}\n\n"
            f"📋 {state['conditions']}\n\n"
            f"🔔 Подписки:\n" + "\n".join(state["subs"])
        )

        msg = await bot.send_message(
            CHANNEL_ID,
            text,
            reply_markup=participate_kb(g_id)
        )

        giveaways[g_id]["message_id"] = msg.message_id

        await message.answer(
            f"✅ Розыгрыш #{g_id} создан",
            reply_markup=manage_kb(g_id)
        )

        user_states.pop(message.from_user.id)

# ========= LIST =========

@dp.callback_query(F.data == "list")
async def list_g(callback: CallbackQuery):
    text = "📊 Активные розыгрыши:\n\n"

    for g_id, g in giveaways.items():
        if g["active"]:
            text += f"🎁 #{g_id} | участников: {len(g['participants'])}\n"

    await callback.message.edit_text(text, reply_markup=main_menu())

# ========= CHECK SUB =========

async def check_subs(user_id, subs):
    for channel in subs:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in [
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER
            ]:
                return False
        except:
            return False
    return True

# ========= JOIN =========

@dp.callback_query(F.data.startswith("join_"))
async def join(callback: CallbackQuery):
    g_id = callback.data.split("_")[1]
    g = giveaways.get(g_id)

    if not g or not g["active"]:
        await callback.answer("❌ Завершён", show_alert=True)
        return

    ok = await check_subs(callback.from_user.id, g["subs"])

    if not ok:
        await callback.answer("❌ Подпишись на все каналы!", show_alert=True)
        return

    g["participants"].add(callback.from_user.id)
    await callback.answer("✅ Ты участвуешь")

# ========= FINISH =========

@dp.callback_query(F.data.startswith("finish_"))
async def finish(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    g_id = callback.data.split("_")[1]
    g = giveaways.get(g_id)

    if not g or not g["active"]:
        return

    g["active"] = False
    participants = list(g["participants"])

    winners = random.sample(participants, min(len(participants), g["winners"]))

    text = "🏁 Итоги розыгрыша:\n\n🏆 Победители:\n"

    for user_id in winners:
        try:
            user = await bot.get_chat(user_id)
            name = f"@{user.username}" if user.username else user.first_name
            text += f"{name}\n"
        except:
            text += f"{user_id}\n"

    text += f"\n👥 Участников: {len(participants)}"

    await bot.send_message(CHANNEL_ID, text)
    await callback.message.answer("✅ Завершено")

# ========= RUN =========

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
