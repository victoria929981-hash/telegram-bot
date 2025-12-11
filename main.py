import os
import time
import re
import telebot
from telebot import types
from flask import Flask
from threading import Thread
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------------------------
# Flask для Bothost
# ----------------------------
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=3000)

t = Thread(target=run)
t.start()

# ----------------------------
# Telegram Bot
# ----------------------------
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ----------------------------
# Google Sheets подключение
# ----------------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1t3qbSdSgSKUUOmLqqHE_IOon2PpjkgkLbd6Tc14dAM4"  # замените на свой
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ----------------------------
# Работа с данными через Google Sheets
# ----------------------------
def load_data():
    try:
        rows = sheet.get_all_records()
    except Exception as e:
        print("Ошибка загрузки данных из Google Sheets:", e)
        return []

    answers = []
    for row in rows:
        if "Keys" in row and "Text" in row:
            keys = [k.strip().lower() for k in row["Keys"].split(",") if k.strip()]
            text = row["Text"]
            answers.append({"keys": keys, "text": text})
    return answers

def save_data(answers):
    try:
        sheet.clear()
        sheet.append_row(["Keys", "Text"])
        for item in answers:
            sheet.append_row([",".join(item["keys"]), item["text"]])
    except Exception as e:
        print("Ошибка сохранения данных в Google Sheets:", e)

answers = load_data()

# ----------------------------
# Удаляем старый webhook
# ----------------------------
bot.remove_webhook()

# ----------------------------
# Меню
# ----------------------------
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
        "`/add название1,название2 текст_абзаца`\n"
        "`/delete название(любое)`\n"
        "`/edit название(любое) новый текст`",
        reply_markup=main_menu()
    )

# ----------------------------
# Добавление слов
# ----------------------------
@bot.message_handler(func=lambda m: m.text.startswith("/add") or m.text.startswith("➕"))
def add_word(message):
    msg_text = message.text
    if msg_text.startswith("➕"):
        bot.send_message(message.chat.id,
                         "Используй формат:\n`/add название1,название2 текст_абзаца`")
        return
    text = msg_text[len("/add "):].strip()
    if " " not in text:
        bot.reply_to(message, "❗️ Формат: `/add название1,название2 текст_абзаца`")
        return
    keys_part, value = text.split(" ", 1)
    keys = [k.strip().lower() for k in keys_part.split(",") if k.strip()]
    answers.append({"keys": keys, "text": value})
    save_data(answers)
    bot.reply_to(message, f"✅ Препарат *{', '.join(keys)}* добавлен!")

# ----------------------------
# Удаление слов
# ----------------------------
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
        reply += f"✅ Препарат *{', '.join(deleted)}* удалён!\n"
    if not_found:
        reply += f"⚠️ Препарат *{', '.join(not_found)}* не найден."
    bot.reply_to(message, reply)

# ----------------------------
# Редактирование слов
# ----------------------------
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

# ----------------------------
# Поиск слов (гибкий)
# ----------------------------
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.lower()
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
                         "Добавь его командой:\n`/add название1,название2 текст_абзац`")

# ----------------------------
# Запуск polling
# ----------------------------
if __name__ == "__main__":
    print("Бот запущен!")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            print("Ошибка polling:", e)
            time.sleep(5)
