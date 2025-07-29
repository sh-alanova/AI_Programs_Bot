# bot.py
import telebot
import requests
import json
import re
import os
from bs4 import BeautifulSoup
from typing import Dict, List

# === НАСТРОЙКИ ===
BOT_TOKEN = "my_token"  # ← Замените на свой токен от @BotFather
PROGRAM_URLS = {
    "ai": "https://abit.itmo.ru/program/master/ai",
    "ai_product": "https://abit.itmo.ru/program/master/ai_product"
}

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Кэш данных о программах
PROGRAM_DATA = {}

# Состояния пользователей
USER_STATE = {}  # user_id -> {stage: str, background: str, preferences: list}


def load_all_programs():
    """
    Загружает все JSON-файлы из папки data/ и сохраняет в PROGRAM_DATA.
    Имя файла (без .json) используется как ключ.
    """
    global PROGRAM_DATA
    data_dir = "data"

    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Папка '{data_dir}' не найдена.")

    PROGRAM_DATA = {}
    loaded_files = 0

    for filename in os.listdir(data_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(data_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Используем имя файла (без .json) как ключ
                key = filename[:-5]  # убираем последний 5 символов: .json
                PROGRAM_DATA[key] = data
                print(f"✅ Загружен файл: {filename} → ключ '{key}'")
                loaded_files += 1
            except Exception as e:
                print(f"❌ Ошибка при загрузке {filename}: {e}")

    if loaded_files == 0:
        print("⚠️ В папке 'data' не найдено ни одного JSON-файла.")
    else:
        print(f"🎉 Успешно загружено {loaded_files} программ.")


# === КОМАНДЫ БОТА ===
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    USER_STATE[user_id] = {"stage": "start"}

    bot.send_message(
        message.chat.id,
        "Привет! Я — бот-помощник по магистратуре ИТМО.\n"
        "Я помогу тебе выбрать между программами:\n\n"
        "🔹 *Искусственный интеллект*\n"
        "🔹 *Управление ИИ-продуктами*\n\n"
        "Используй /help, чтобы начать подбор.\n"
        "Или задай вопрос напрямую, например:\n"
        "«Чем отличаются программы?»",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['help'])
def help_command(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("Сравнить программы")
    btn2 = telebot.types.KeyboardButton("Порекомендовать программу")
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "Выбери, что тебя интересует:",
        reply_markup=markup
    )


@bot.message_handler(commands=['compare'])
def compare(message):
    ai = PROGRAM_DATA.get("itmo_ai_parsed", {})
    ai_p = PROGRAM_DATA.get("itmo_ai_product_parsed", {})

    msg = (
        "📊 *Сравнение программ*\n\n"
        f"🎯 *Название:* {ai.get('title', '—')}\n"
        f"📘 *Фокус:* Техническая разработка ИИ (ML, Data Engineering)\n"
        f"💰 *Стоимость:* {ai.get('education_cost', {}).get('russian', '—')} ₽/год\n"
        f"👥 *Карьера:* ML Engineer, Data Analyst, AI Developer\n\n"

        f"🎯 *Название:* {ai_p.get('title', '—')}\n"
        f"📘 *Фокус:* Управление и коммерциализация ИИ-продуктов\n"
        f"💰 *Стоимость:* {ai_p.get('education_cost', {}).get('russian', '—')} ₽/год\n"
        f"👥 *Карьера:* AI Product Manager, Product Lead, AI Analyst\n\n"

        "Используй /recommend, чтобы получить персональную рекомендацию."
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")


@bot.message_handler(commands=['recommend'])
def recommend(message):
    user_id = message.from_user.id
    USER_STATE[user_id] = {}
    USER_STATE[user_id]["stage"] = "question_0"
    bot.send_message(message.chat.id, "Какой у вас образовательный бэкграунд? (например: программирование, менеджмент)")
    bot.send_message(message.chat.id, "Напишите один ответ.")


# === ОБРАБОТКА ОПРОСА ===
@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get("stage", "").startswith("question_"))
def handle_questionnaire(message):
    user_id = message.from_user.id
    stage = USER_STATE[user_id]["stage"]
    text = message.text.lower()

    if stage == "question_0":
        USER_STATE[user_id]["background"] = text
        bot.send_message(message.chat.id, "Что вас больше интересует: разработка моделей или управление продуктами?")
        USER_STATE[user_id]["stage"] = "question_1"
    elif stage == "question_1":
        USER_STATE[user_id]["interest"] = text
        bot.send_message(message.chat.id, "Хотите ли вы запускать стартап или работать в компании?")
        USER_STATE[user_id]["stage"] = "question_2"
    elif stage == "question_2":
        USER_STATE[user_id]["startup"] = text
        give_recommendation(message)
        USER_STATE[user_id]["stage"] = "advised"


def give_recommendation(message):
    user_id = message.from_user.id
    bg = USER_STATE[user_id].get("background", "")
    interest = USER_STATE[user_id].get("interest", "")
    startup = USER_STATE[user_id].get("startup", "")
    print(USER_STATE)

    ai_score = 0
    ai_p_score = 0

    tech_words = ["программирование", "ml", "data", "инженер", "математика", "разработка", "python"]
    product_words = ["менеджмент", "бизнес", "стартап", "product", "маркетинг", "управление"]

    for w in tech_words:
        if w in bg or w in interest:
            ai_score += 1
    for w in product_words:
        if w in bg or w in interest or w in startup:
            ai_p_score += 1

    if ai_score > ai_p_score:
        rec = PROGRAM_DATA["itmo_ai_parsed"]
        reason = "Ваш бэкграунд и интересы ближе к технической разработке."
    elif ai_p_score > ai_score:
        rec = PROGRAM_DATA["itmo_ai_product_parsed"]
        reason = "Вы склонны к управлению и коммерциализации."
    else:
        bot.send_message(message.chat.id, "Обе программы вам подходят! Используйте /compare.")
        return

    msg = (
        f"*Рекомендуем:* {rec['title']}\n\n"
        # f"*Описание:* {rec['about']['lead']}\n"
        # f"*Карьера:* {rec['career']['text']}\n"
        # f"Подробнее: https://abit.itmo.ru/program/master/{rec['slug']}\n\n"
        f"💡 *Причина:* {reason}",
        )
    
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    suggest_courses(message, rec)

@bot.message_handler(commands=['recommend'])
def suggest_courses(message, program):
    course_map = {
        "ai": [
            "Глубокое обучение",
            "ML в продакшене",
            "Обработка естественного языка",
            "Computer Vision",
            "Data Engineering"
        ],
        "ai_product": [
            "Управление AI-продуктами",
            "UX для ИИ",
            "Монетизация технологий",
            "AI Project Management"
        ]
    }
    slug = program.get("slug", "")
    courses = course_map.get(slug, [])
    bot.send_message(
        message.chat.id,
        "*Рекомендуемые курсы:*\n" + "\n".join(f"- {c}" for c in courses),
        parse_mode="Markdown"
    )


# === ОБРАБОТКА ОБЩИХ ВОПРОСОВ ===
@bot.message_handler(func=lambda message: True)
def handle_query(message):
    text = message.text.lower()

    # Только релевантные темы
    allowed = ["искусственный интеллект", "ai", "product", "магистратура", "итмо", 
               "управление", "управление ии", "поступить", "курсы", "карьера", 
               "команда", "руководитель", "сравнить", "руковод", "срав", "выбрать",
               "менеджер", "экзамен", "дата", "даты"]
    if not any(word in text for word in allowed):
        bot.reply_to(message, "Я отвечаю только о магистерских программах ИТМО по AI и AI Product.")
        bot.reply_to(message, "Напиши чуть подробнее свой вопрос.")
        return

    # Определение программы
    if "ai_product" in text or "ai product" in text or "управление ии" in text:
        prog = PROGRAM_DATA.get("itmo_ai_product_parsed")
    elif "ai" in text or "искусственный интеллект" in text:
        prog = PROGRAM_DATA.get("itmo_ai_parsed")
    else:
        bot.reply_to(message, "Я не понял вопрос(\n\nНапиши чуть подробнее свой вопрос.")

    # Обработка команд
    if "сравн" in text or "сравнить" in text or "выбрать" in text:
        bot.send_message(message.chat.id, "Используйте /compare")
        return
    elif "рекоменд" in text:
        bot.send_message(message.chat.id, "Используйте /recommend")
        return
    elif "команда" in text:
        if prog:
            team_list = "\n".join(f"• {m['name']} — {m['position']}" for m in prog['team'][:5])
            bot.send_message(message.chat.id, f"*Команда программы:* {prog['title']}\n\n{team_list}", parse_mode="Markdown")
        return
    elif "руковод" in text or "руководитель" in text or "менеджер" in text:
        if prog:
            sup = prog['supervisor']
            bot.send_message(message.chat.id, f"*Менеджер:* {sup['name']}\n", parse_mode="Markdown")
        return
    elif "поступить" in text or "экзамен" in text or "дата" in text or "даты" in text:
        if prog:
            dates = ", ".join(d.split("T")[0] for d in prog['exam_dates'][:3])
            bot.send_message(message.chat.id, f"*Даты экзаменов:* {dates}", parse_mode="Markdown")
        return

    # Ответ по программе
    if prog:
        bot.send_message(
            message.chat.id,
            f"*{prog['title']}*\n\n"
            f"{prog['about']['lead']}\n\n"
            f"*Карьера:* {prog['career']['text']}\n"
            f"*Стоимость:* {prog['education_cost'].get('russian', '—')} ₽/год\n"
            f"*Учебный план:* [Скачать PDF]({prog['academic_plan_url']})",
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
    else:
        bot.send_message(message.chat.id, "О какой программе вы спрашиваете? Уточните: AI или AI Product?")


# === ЗАПУСК ===
if __name__ == '__main__':
    print("Загрузка данных...")
    load_all_programs()

    print("Запуск бота...")
    bot.polling(none_stop=True)
