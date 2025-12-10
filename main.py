import os
import time
import telebot
from telebot import types
import re
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=3000)

t = Thread(target=run)
t.start()

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# Удаляем старый webhook, чтобы не было 409 Conflict
bot.remove_webhook()

DATA_FILE = "data.txt"

# ------------------------
# 1. Работа с файлом
# ------------------------
def load_data():
    """Загрузка словаря из файла"""
    if not os.path.exists(DATA_FILE):
        return []
    answers = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "||" in line:
                keys_part, text = line.strip().split("||", 1)
                keys = [k.strip().lower() for k in keys_part.split(",")]
                answers.append({"keys": keys, "text": text})
    return answers

def save_data(answers):
    """Сохранение словаря в файл"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        for item in answers:
            f.write(f"{','.join(item['keys'])}||{item['text']}\n")

answers = load_data()

# Стартовые примеры
if not answers:
    answers = [
        {"keys": ["привет"], "text": "Привет! Я бот-справочник. Напиши слово — я пришлю абзац."},
        {"keys": ["собака"], "text": "Собаки — удивительные животные, известные преданностью."},
        {"keys": ["цистит", "мочевой пузырь"], "text": "Цистит — это воспаление мочевого пузыря.\nОбычно сопровождается болью и частыми мочеиспусканиями.\nРекомендуется обратиться к ветеринару для диагностики и лечения."}
    ]
    save_data(answers)

# ------------------------
# 2. Меню
# ------------------------
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить препарат", "🗑 Удалить препарат", "✏️ Редактировать")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "*Привет!*\n\n"
        "Я бот-справочник. Напиши препарат — я найду дозы и режим дозирования.\n\n"
        "Используй меню ниже или команды:\n\n"
        "`/add название1,название2 (названия без пробелов) текст абзаца`\n\n"
        "`/delete название(любое)`\n\n"
        "`/edit название(любое) новый текст`",
        reply_markup=main_menu()
    )
# ------------------------
# 3. Добавление слов
# ------------------------
@bot.message_handler(func=lambda m: m.text.startswith("/add") or m.text.startswith("➕"))
def add_word(message):
    msg_text = message.text
    if msg_text.startswith("➕"):
        bot.send_message(message.chat.id,
                         "Используй формат:\n`/add название1,название2 (названия без пробелов) текст_абзаца`\n"
                         "Текст абзаца может быть с переносом строк.")
        return
    text = msg_text[len("/add "):].strip()
    if " " not in text:
        bot.reply_to(message, "❗️ Формат: `/add название1,название2(названия без пробелов) текст_абзац`")
        return
    keys_part, value = text.split(" ", 1)
    # Разделяем ключи по запятой, убираем лишние пробелы
    keys = [k.strip().lower() for k in keys_part.split(",") if k.strip()]
    answers.append({"keys": keys, "text": value})
    save_data(answers)
    bot.reply_to(message, f"✅ Препарат *{', '.join(keys)}* добавлен!")

# ------------------------
# 4. Удаление слов
# ------------------------

@bot.message_handler(func=lambda m: m.text.startswith("/delete") or m.text.startswith("🗑"))
def delete_word(message):
    msg_text = message.text
    if msg_text.startswith("🗑"):
        bot.send_message(message.chat.id,
                         "Используй формат:\n`/delete название(любое)`")
        return

    text = msg_text[len("/delete "):].strip()
    keys_to_delete = [k.strip().lower() for k in text.split(",") if k.strip()]
    deleted = []
    not_found = []  # <- обязательно объявляем переменную здесь

    new_answers = []
    for item in answers:
        item_keys_lower = [k.lower() for k in item['keys']]
        if any(k in keys_to_delete for k in item_keys_lower):
            deleted.extend([k for k in keys_to_delete if k in item_keys_lower])
        else:
            new_answers.append(item)

    not_found = [k for k in keys_to_delete if k not in deleted]

    answers.clear()
    answers.extend(new_answers)
    save_data(answers)

    reply = ""
    if deleted:
        reply += f"✅ Препарат *{', '.join(deleted)}* удален!\n"
    if not_found:
        reply += f"⚠️ Препарат *{', '.join(not_found)}* не найден."

    bot.reply_to(message, reply)

# ------------------------
# 4. редактирование слов
# ------------------------

@bot.message_handler(func=lambda m: m.text.startswith("/edit") or m.text.startswith("✏️"))
def edit_word(message):
    msg_text = message.text
    if msg_text.startswith("✏️"):
        bot.send_message(message.chat.id,
                         "Используй формат:\n`/edit название(любое) новый текст`")
        return
    text = msg_text[len("/edit "):].strip()
    if " " not in text:
        bot.reply_to(message, "❗️ Формат: `/edit название(любое) новый текст`")
        return
    keys_part, new_value = text.split(" ", 1)
    keys = [k.strip().lower() for k in keys_part.split(",") if k.strip()]

    # Ищем абзац, где хотя бы один ключ совпадает
    found = False
    for item in answers:
        item_keys_lower = [k.lower() for k in item['keys']]
        if any(k in item_keys_lower for k in keys):
            item['text'] = new_value
            found = True
            break

    if found:
        save_data(answers)
        bot.reply_to(message, f"✅ Абзац для препарата *{', '.join(keys)}* обновлён!")
    else:
        bot.reply_to(message, f"⚠️ Абзац для препарата *{', '.join(keys)}* не найден.")

        
# ------------------------
# 5. Поиск слов (гибкий)
# ------------------------
@bot.message_handler(func=lambda m: True)
def handle_message(message):
        text = message.text.lower()
        # Разбиваем текст пользователя на слова для гибкого поиска
        import re
        user_words = set(re.findall(r'\w+', text))
        found_texts = set()
        for item in answers:
            for key in item['keys']:
                key_words = set(re.findall(r'\w+', key))
                if key_words & user_words:
                    found_texts.add(item['text'])
                    break
        if found_texts:
            for t in found_texts:
                bot.send_message(message.chat.id, t)
        else:
            bot.send_message(message.chat.id,
                             "😕 Я не нашёл подходящего ответа.\n"
                             "Добавь его командой:\n`/add название1,название2(названия без пробелов) текст_абзац`")

# ------------------------
# 6. Запуск
# ------------------------

if __name__ == '__main__':
    print("Бот запущен. Ожидаю сообщений...")
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print("Ошибка polling:", e)
        time.sleep(5)
        
