import logging
import random
import time
import sqlite3
import threading
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ========== НАСТРОЙКИ ==========
TOKEN = "8307541675:AAG5pt1ig8PouMJTy9DPhtnMF8JZI675BMU"  # Вставьте сюда ваш токен
ADMIN_IDS = [1205576607]  # Вставьте ваш ID
# Экономика
CURRENCY = "🏒  Шайбочки"
START_BALANCE = 1000
BONUS_INTERVAL = 18000
BONUS_MIN = 500
BONUS_MAX = 5000
# Реферальная система
REFERRAL_BONUS_HOST = 1000
REFERRAL_BONUS_FRIEND = 500
TEAMS = [
    "Автомобилист", "Ак Барс", "Авангард", "Адмирал", "Амур",
    "Барыс", "Юность", "Динамо Москва", "Динамо Минск", "Норильск",
    "Локомотив", "Металлург", "Нефтехимик", "Салават Юлаев",
    "Северсталь", "Сибирь", "СКА", "Спартак", "Торпедо",
    "Трактор", "ЦСКА", "Сочи", "Шанхайские Драконы", "Лада",
    "Химик", "Югра", "Металлург Новокузнецк", "Сарыарка", "Динамо Санкт Петурбург", "Рубин"
]
# ========== МЕНЮ ==========
def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🏒 Матчи"), KeyboardButton("🎁 Бонус")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("🏆 Топ")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🎯 Квесты")],
        [KeyboardButton("📨 Связаться с админом"), KeyboardButton("➕ Добавить друга")],
        [KeyboardButton("📊 История баланса"), KeyboardButton("🎫 Промокод")]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([KeyboardButton("🔧 Админ панель")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("👥 Список пользователей")],
        [KeyboardButton("💳 Выдать деньги"), KeyboardButton("💳 Списать деньги")],
        [KeyboardButton("🚫 Забанить"), KeyboardButton("✅ Разбанить")],
        [KeyboardButton("🏒 Создать матч"), KeyboardButton("🏒 Завершить матч")],
        [KeyboardButton("🎫 Создать промокод"), KeyboardButton("📢 Рассылка")],
        [KeyboardButton("📊 Статистика бота"), KeyboardButton("📨 Состояние промокодов")],
        [KeyboardButton("🔙 В главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# ========== БАЗА ДАННЫХ ==========
import sqlite3
import threading

class Database:
    def __init__(self, db_path="hockey_bet.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.lock = threading.Lock()
        self._create_tables()
    
    def _create_tables(self):
        with self.lock:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 1000,
                    turnover INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    bets_count INTEGER DEFAULT 0,
                    last_bonus_time INTEGER DEFAULT 0,
                    referrer_id INTEGER DEFAULT NULL,
                    referral_count INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    registered_at INTEGER DEFAULT 0,
                    daily_quest_reset INTEGER DEFAULT 0,
                    weekly_quest_reset INTEGER DEFAULT 0,
                    friends TEXT DEFAULT ''
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS freebets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    used INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT 0,
                    expires_at INTEGER DEFAULT 0
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team1 TEXT,
                    team2 TEXT,
                    odds_p1 REAL DEFAULT 1.9,
                    odds_p2 REAL DEFAULT 1.9,
                    odds_tb REAL DEFAULT 1.9,
                    odds_tm REAL DEFAULT 1.9,
                    odds_ob REAL DEFAULT 1.9,
                    status TEXT DEFAULT 'active',
                    result TEXT DEFAULT NULL,
                    created_at INTEGER DEFAULT 0,
                    finished_at INTEGER DEFAULT NULL
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    match_id INTEGER,
                    bet_type TEXT,
                    bet_choice TEXT,
                    amount INTEGER,
                    odds REAL,
                    potential_win INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER DEFAULT 0,
                    settled_at INTEGER DEFAULT NULL
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    code TEXT PRIMARY KEY,
                    reward_type TEXT,
                    reward_value TEXT,
                    max_uses INTEGER DEFAULT 1,
                    used_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS quests (
                    user_id INTEGER,
                    quest_id TEXT,
                    progress INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    completed_at INTEGER DEFAULT 0,
                    last_reset INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, quest_id)
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    reason TEXT,
                    created_at INTEGER DEFAULT 0
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message TEXT,
                    reply TEXT DEFAULT NULL,
                    created_at INTEGER DEFAULT 0,
                    replied_at INTEGER DEFAULT NULL
                );
            """)
            self.conn.commit()
    
    def execute(self, query, params=()):
        with self.lock:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
    
    def fetchone(self, query, params=()):
        with self.lock:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
    
    def fetchall(self, query, params=()):
        with self.lock:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
# ========== ОБРАБОТЧИКИ ==========
# ========== УТИЛИТЫ ==========
def format_balance(amount):
    return f"{amount:,} {CURRENCY}"
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    db = Database()
    existing = db.fetchone("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    if not existing:
        referrer_id = None
        if args and args[0].isdigit():
            referrer_id = int(args[0])
            if referrer_id == user.id:
                referrer_id = None
        db.execute("""
            INSERT INTO users 
            (user_id, username, first_name, last_name, balance, registered_at, referrer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.username, user.first_name, user.last_name, START_BALANCE, int(time.time()), referrer_id))
        if referrer_id:
            db.execute("UPDATE users SET balance = balance + ?, referral_count = referral_count + 1 WHERE user_id = ?",
                      (REFERRAL_BONUS_HOST, referrer_id))
            db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                      (REFERRAL_BONUS_FRIEND, user.id))
        for q in DAILY_QUESTS + WEEKLY_QUESTS + PERMANENT_QUESTS:
            db.execute("INSERT OR IGNORE INTO quests (user_id, quest_id) VALUES (?, ?)", (user.id, q["id"]))
    await update.message.reply_text(
        f"🏒 Добро пожаловать в Hockey Bet!\n\n"
        f"Ваш баланс: {format_balance(START_BALANCE)}\n"
        f"Используйте кнопки ниже для навигации.",
        reply_markup=get_main_keyboard(user.id)
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("🏒 Меню", reply_markup=get_main_keyboard(user_id))

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    user = db.fetchone("SELECT last_bonus_time, balance FROM users WHERE user_id = ?", (user_id,))
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы. Напишите /start")
        return
    last_bonus_time, balance = user
    current_time = int(time.time())
    if current_time - last_bonus_time < BONUS_INTERVAL:
        remaining = BONUS_INTERVAL - (current_time - last_bonus_time)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(f"⏳ Бонус еще не доступен. Осталось: {hours}ч {minutes}м")
        return
    bonus_amount = random.randint(BONUS_MIN, BONUS_MAX)
    db.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?",
               (bonus_amount, current_time, user_id))
    add_balance_history(user_id, bonus_amount, "🎁 Бонус", db)
    msg = f"🎁 Вы получили бонус: {format_balance(bonus_amount)}!"
    await update.message.reply_text(msg)

async def matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = Database()
    matches = db.fetchall("SELECT id, team1, team2, odds_p1, odds_p2, odds_tb, odds_tm, odds_ob FROM matches WHERE status = 'active'")
    if not matches:
        await update.message.reply_text("❌ Активных матчей нет.", reply_markup=get_main_keyboard(update.effective_user.id))
        return
    keyboard = []
    for m in matches:
        keyboard.append([InlineKeyboardButton(format_match_row(m), callback_data=f"match_{m[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏒 Выберите матч для ставки:", reply_markup=reply_markup)

async def match_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = int(query.data.split("_")[1])
    db = Database()
    match = db.fetchone("SELECT id, team1, team2, odds_p1, odds_p2, odds_tb, odds_tm, odds_ob FROM matches WHERE id = ?", (match_id,))
    if not match:
        await query.edit_message_text("❌ Матч не найден")
        return
    text = f"🏒 {match[1]} vs {match[2]}\n\n"
    text += f"П1: {match[3]} | П2: {match[4]}\n"
    text += f"ТБ: {match[5]} | ТМ: {match[6]}\n"
    text += f"Обе забьют: {match[7]}\n\n"
    text += "Выберите тип ставки:"
    keyboard = [
        [InlineKeyboardButton(f"П1 ({match[3]})", callback_data=f"bet_{match_id}_p1")],
        [InlineKeyboardButton(f"П2 ({match[4]})", callback_data=f"bet_{match_id}_p2")],
        [InlineKeyboardButton(f"ТБ ({match[5]})", callback_data=f"bet_{match_id}_tb")],
        [InlineKeyboardButton(f"ТМ ({match[6]})", callback_data=f"bet_{match_id}_tm")],
        [InlineKeyboardButton(f"Обе забьют ({match[7]})", callback_data=f"bet_{match_id}_ob")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"match_{match_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    match_id = int(data[1])
    bet_choice = data[2]
    db = Database()
    user_id = update.effective_user.id
    match = db.fetchone("SELECT team1, team2, odds_p1, odds_p2, odds_tb, odds_tm, odds_ob FROM matches WHERE id = ?", (match_id,))
    if not match:
        await query.edit_message_text("❌ Матч не найден")
        return
    odds_map = {
        "p1": (match[2], "П1"),
        "p2": (match[3], "П2"),
        "tb": (match[4], "ТБ"),
        "tm": (match[5], "ТМ"),
        "ob": (match[6], "Обе забьют")
    }
    if bet_choice not in odds_map:
        await query.edit_message_text("❌ Неверный тип ставки")
        return
    odds, bet_type = odds_map[bet_choice]
    # Сохраняем информацию о матче в user_data
    context.user_data["bet_data"] = {
        "match_id": match_id,
        "bet_choice": bet_choice,
        "bet_type": bet_type,
        "odds": odds,
        "team1": match[0],
        "team2": match[1]
    }
    await query.edit_message_text(
        f"🏒 {match[0]} vs {match[1]}\n"
        f"Ставка: {bet_type} (кф {odds})\n\n"
        f"Введите сумму ставки (число):"
    )

async def handle_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if "bet_data" not in context.user_data:
        await update.message.reply_text("❌ Сначала выберите ставку через /matches")
        return
    try:
        amount = int(text)
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Введите положительное число")
        return
    bet_data = context.user_data["bet_data"]
    match_id = bet_data["match_id"]
    bet_choice = bet_data["bet_choice"]
    bet_type = bet_data["bet_type"]
    odds = bet_data["odds"]
    team1 = bet_data["team1"]
    team2 = bet_data["team2"]
    db = Database()
    user = db.fetchone("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    balance = user[0]
    if amount > balance:
        await update.message.reply_text(f"❌ Недостаточно средств. Ваш баланс: {format_balance(balance)}")
        return
    potential_win = int(amount * odds)
    current_time = int(time.time())
    db.execute("""
        INSERT INTO bets (user_id, match_id, bet_type, bet_choice, amount, odds, potential_win, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, match_id, bet_type, bet_choice, amount, odds, potential_win, current_time))
    db.execute("UPDATE users SET balance = balance - ?, turnover = turnover + ?, bets_count = bets_count + 1 WHERE user_id = ?",
               (amount, amount, user_id))
    add_balance_history(user_id, -amount, f"🏒 Ставка на {bet_type}", db)
    del context.user_data["bet_data"]
    await update.message.reply_text(
        f"✅ Ставка принята!\n\n"
        f"Матч: {team1} vs {team2}\n"
        f"Ставка: {bet_type} (кф {odds})\n"
        f"Сумма: {format_balance(amount)}\n"
        f"Потенциальный выигрыш: {format_balance(potential_win)}"
    )
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    user = db.fetchone("""
        SELECT username, first_name, last_name, balance, turnover, wins, losses, bets_count, referral_count, registered_at
        FROM users WHERE user_id = ?
    """, (user_id,))
    
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    
    # user[0] = username
    # user[1] = first_name
    # user[2] = last_name
    # user[3] = balance
    # user[4] = turnover
    # user[5] = wins
    # user[6] = losses
    # user[7] = bets_count
    # user[8] = referral_count
    # user[9] = registered_at
    
    reg_date = "Неизвестно"
    if user[9]:
        reg_date = datetime.fromtimestamp(user[9]).strftime("%d.%m.%Y")
    
    total_bets = user[5] + user[6]
    win_percent = round(user[5] / total_bets * 100, 1) if total_bets > 0 else 0
    
    text = f"👤 Профиль\n\n"
    text += f"ID: {user_id}\n"
    text += f"Имя: {user[1] or 'Не указано'} {user[2] or ''}\n"
    text += f"Зарегистрирован: {reg_date}\n\n"
    text += f"💰 Баланс: {format_balance(user[3])}\n"
    text += f"🔄 Оборот: {format_balance(user[4])}\n"
    text += f"🏆 Победы: {user[5]}\n"
    text += f"💔 Поражения: {user[6]}\n"
    text += f"📊 Всего ставок: {user[7]}\n"
    text += f"📈 Процент побед: {win_percent}%\n"
    text += f"👥 Приглашено: {user[8]}\n"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
async def promo_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    db = Database()
    promos = db.fetchall("SELECT code, reward_type, reward_value, max_uses, used_count, is_active FROM promocodes ORDER BY code")
    text = "📨 Состояние промокодов\n\n"
    for p in promos:
        status = "✅ Активен" if p[5] else "❌ Неактивен"
        text += f"Код: {p[0]}\n"
        text += f"Тип: {p[1]}, Значение: {p[2]}\n"
        text += f"Использовано: {p[4]} / {p[3]}\n"
        text += f"Статус: {status}\n\n"
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())
# ========== ДОБАВЛЕНИЕ ДРУГА ==========

# ========== СВЯЗЬ С АДМИНОМ ==========
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data["contacting_admin"] = True
    await update.message.reply_text("✍️ Напишите сообщение админу (анонимно):")

async def handle_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if "contacting_admin" not in context.user_data:
        return
    text = update.message.text.strip()
    db = Database()
    db.execute("INSERT INTO admin_messages (user_id, message, created_at) VALUES (?, ?, ?)",
               (user_id, text, int(time.time())))
    await update.message.reply_text("✅ Сообщение отправлено админу (анонимно).")
    del context.user_data["contacting_admin"]

# ========== ТОП ==========
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = Database()
    top_balance = db.fetchall("""
        SELECT user_id, first_name, balance FROM users 
        WHERE is_banned = 0 ORDER BY balance DESC LIMIT 10
    """)
    top_wins = db.fetchall("""
        SELECT user_id, first_name, wins FROM users 
        WHERE is_banned = 0 ORDER BY wins DESC LIMIT 10
    """)
    text = "🏆 Топ игроков\n\n"
    text += "💰 По балансу:\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(top_balance):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {u[1] or 'Игрок'} - {format_balance(u[2])}\n"
    text += "\n🏒 По победам:\n"
    for i, u in enumerate(top_wins):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {u[1] or 'Игрок'} - {u[2]} побед\n"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(update.effective_user.id))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    user = db.fetchone("SELECT bets_count, wins, losses, turnover, balance FROM users WHERE user_id = ?", (user_id,))
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    bets_count, wins, losses, turnover, balance = user
    total_bets = wins + losses
    win_percent = round(wins / total_bets * 100, 1) if total_bets > 0 else 0
    text = f"📊 Статистика\n\n"
    text += f"💰 Баланс: {format_balance(balance)}\n"
    text += f"🔄 Оборот: {format_balance(turnover)}\n"
    text += f"📈 Всего ставок: {bets_count}\n"
    text += f"🏆 Победы: {wins}\n"
    text += f"💔 Поражения: {losses}\n"
    text += f"📊 Процент побед: {win_percent}%\n"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

# ========== КВЕСТЫ ==========
DAILY_QUESTS = [
    {"id": "daily_bets_3", "name": "Сделать 3 ставки", "target": 3, "reward": 500},
    {"id": "daily_win_1", "name": "Выиграть 1 ставку", "target": 1, "reward": 500},
    {"id": "daily_bonus", "name": "Получить бонус", "target": 1, "reward": 500}
]

WEEKLY_QUESTS = [
    {"id": "weekly_bets_20", "name": "Сделать 20 ставок", "target": 20, "reward": 2000},
    {"id": "weekly_wins_10", "name": "Выиграть 10 ставок", "target": 10, "reward": 2000},
    {"id": "weekly_invite", "name": "Пригласить друга", "target": 1, "reward": 2000}
]

PERMANENT_QUESTS = [
    {"id": "perm_bets_10", "name": "10 ставок", "target": 10, "reward": 1000},
    {"id": "perm_bets_50", "name": "50 ставок", "target": 50, "reward": 3000},
    {"id": "perm_bets_100", "name": "100 ставок", "target": 100, "reward": 5000},
    {"id": "perm_wins_100", "name": "100 побед", "target": 100, "reward": 10000}
]

async def quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    user = db.fetchone("SELECT daily_quest_reset, weekly_quest_reset FROM users WHERE user_id = ?", (user_id,))
    if user and user[0] < int(time.time()) - 86400:
        for q in DAILY_QUESTS:
            db.execute("UPDATE quests SET progress = 0, completed = 0 WHERE user_id = ? AND quest_id = ?",
                       (user_id, q["id"]))
        db.execute("UPDATE users SET daily_quest_reset = ? WHERE user_id = ?", (int(time.time()), user_id))
    if user and user[1] < int(time.time()) - 7 * 86400:
        for q in WEEKLY_QUESTS:
            db.execute("UPDATE quests SET progress = 0, completed = 0 WHERE user_id = ? AND quest_id = ?",
                       (user_id, q["id"]))
        db.execute("UPDATE users SET weekly_quest_reset = ? WHERE user_id = ?", (int(time.time()), user_id))
    text = "🎯 Квесты\n\n"
    text += "📅 Ежедневные:\n"
    for q in DAILY_QUESTS:
        qdata = db.fetchone("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?",
                            (user_id, q["id"]))
        if qdata:
            progress, completed = qdata
            status = "✅" if completed else f"{progress}/{q['target']}"
            text += f"{q['name']}: {status} (+{q['reward']} 🏒)\n"
    text += "\n📅 Еженедельные:\n"
    for q in WEEKLY_QUESTS:
        qdata = db.fetchone("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?",
                            (user_id, q["id"]))
        if qdata:
            progress, completed = qdata
            status = "✅" if completed else f"{progress}/{q['target']}"
            text += f"{q['name']}: {status} (+{q['reward']} 🏒)\n"
    text += "\n🏆 Постоянные:\n"
    for q in PERMANENT_QUESTS:
        qdata = db.fetchone("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?",
                            (user_id, q["id"]))
        if qdata:
            progress, completed = qdata
            status = "✅" if completed else f"{progress}/{q['target']}"
            text += f"{q['name']}: {status} (+{q['reward']} 🏒)\n"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

def check_quest_completion(user_id, db):
    for q in DAILY_QUESTS:
        quest = db.fetchone("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?", 
                           (user_id, q["id"]))
        if quest and quest[1] == 0 and quest[0] >= q["target"]:
            db.execute("UPDATE quests SET completed = 1, completed_at = ? WHERE user_id = ? AND quest_id = ?",
                       (int(time.time()), user_id, q["id"]))
            db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (q["reward"], user_id))
    for q in WEEKLY_QUESTS:
        quest = db.fetchone("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?", 
                           (user_id, q["id"]))
        if quest and quest[1] == 0 and quest[0] >= q["target"]:
            db.execute("UPDATE quests SET completed = 1, completed_at = ? WHERE user_id = ? AND quest_id = ?",
                       (int(time.time()), user_id, q["id"]))
            db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (q["reward"], user_id))
    for q in PERMANENT_QUESTS:
        quest = db.fetchone("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?", 
                           (user_id, q["id"]))
        if quest and quest[1] == 0 and quest[0] >= q["target"]:
            db.execute("UPDATE quests SET completed = 1, completed_at = ? WHERE user_id = ? AND quest_id = ?",
                       (int(time.time()), user_id, q["id"]))
            db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (q["reward"], user_id))

# ========== АДМИН КОМАНДЫ ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    await update.message.reply_text("🔧 Админ панель", reply_markup=get_admin_keyboard())

# ========== АДМИН: ПОЛЬЗОВАТЕЛИ ==========
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    db = Database()
    users = db.fetchall("""
        SELECT user_id, username, first_name, last_name, balance, turnover, wins, losses, bets_count, 
               referral_count, is_banned, registered_at 
        FROM users ORDER BY balance DESC
    """)
    text = "👥 Список пользователей\n\n"
    for u in users:
        reg_date = datetime.fromtimestamp(u[11]).strftime("%d.%m.%Y")
        status = "🚫 Забанен" if u[10] else "✅ Активен"
        text += f"ID: {u[0]} | {u[2] or 'Не указано'} {u[3] or ''}\n"
        text += f"💰 {format_balance(u[4])} | 📈 {u[5]} | 🏆 {u[6]}\n"
        text += f"📊 {u[7]} | 🎯 {u[8]} | 👥 {u[9]}\n"
        text += f"📅 {reg_date} | {status}\n\n"
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# ========== АДМИН: ВЫДАТЬ ДЕНЬГИ ==========
async def admin_give_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 2)
        if len(parts) < 3:
            await update.message.reply_text("❌ Формат: /give_money id сумма", reply_markup=get_admin_keyboard())
            return
        target_id = int(parts[1])
        amount = int(parts[2])
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной", reply_markup=get_admin_keyboard())
            return
        db = Database()
        db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        add_balance_history(target_id, amount, "💳 Выдача админом", db)
        
        # ✅ Уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"💳 Админ выдал вам {format_balance(amount)}"
            )
        except:
            pass
        
        await update.message.reply_text(f"✅ Выдано {format_balance(amount)} пользователю {target_id}", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())

# ========== АДМИН: СПИСАТЬ ДЕНЬГИ ==========
async def admin_take_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 2)
        if len(parts) < 3:
            await update.message.reply_text("❌ Формат: /take_money id сумма", reply_markup=get_admin_keyboard())
            return
        target_id = int(parts[1])
        amount = int(parts[2])
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной", reply_markup=get_admin_keyboard())
            return
        db = Database()
        db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_id))
        add_balance_history(target_id, -amount, "💳 Списание админом", db)
        
        # ✅ Уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"💳 Админ списал {format_balance(amount)} с вашего счета"
            )
        except:
            pass
        
        await update.message.reply_text(f"✅ Списано {format_balance(amount)} с пользователя {target_id}", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())

# ========== АДМИН: ЗАБАНИТЬ ==========
async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: /ban id", reply_markup=get_admin_keyboard())
            return
        target_id = int(parts[1])
        db = Database()
        db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        await update.message.reply_text(f"✅ Пользователь {target_id} забанен", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())

# ========== АДМИН: РАЗБАНИТЬ ==========
async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: /unban id", reply_markup=get_admin_keyboard())
            return
        target_id = int(parts[1])
        db = Database()
        db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        await update.message.reply_text(f"✅ Пользователь {target_id} разбанен", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())

# ========== АДМИН: СОЗДАТЬ МАТЧ (ФИКСИРОВАННЫЕ КОЭФФИЦИЕНТЫ) ==========
async def admin_create_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: /create_match Команда1 vs Команда2")
            return
        match_text = parts[1]
        if ' vs ' not in match_text:
            await update.message.reply_text("❌ Используйте ' vs ' для разделения команд")
            return
        team1, team2 = match_text.split(' vs ', 1)
        db = Database()
        db.execute("INSERT INTO matches (team1, team2, created_at) VALUES (?, ?, ?)",
                   (team1.strip(), team2.strip(), int(time.time())))
        await update.message.reply_text(f"✅ Матч создан: {team1} vs {team2}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ========== АДМИН: ЗАВЕРШИТЬ МАТЧ ==========
# ... предыдущий код ...

async def admin_end_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    db = Database()
    matches = db.fetchall("SELECT id, team1, team2 FROM matches WHERE status = 'active'")
    if not matches:
        await update.message.reply_text("❌ Нет активных матчей", reply_markup=get_admin_keyboard())
        return
    
    text = "📋 Список активных матчей\n\n"
    for m in matches:
        text += f"ID: {m[0]} — {m[1]} vs {m[2]} — активен\n"
    text += "\nВведите команду:\n/end_match <id> <счёт>\n\nПример: /end_match 1 2:1"
    
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())
async def admin_end_match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 2)
        if len(parts) < 3:
            await update.message.reply_text("❌ Формат: /end_match <id> <счёт>")
            return
        match_id = int(parts[1])
        score_str = parts[2]
        # ... остальной код ...
        
        # Разбираем счёт
        try:
            score1, score2 = map(int, score_str.split(':'))
        except:
            await update.message.reply_text("❌ Неверный формат счёта. Используйте '2:1'")
            return
        
        # Определяем результаты для всех типов ставок
        result = "П1" if score1 > score2 else "П2" if score2 > score1 else "Х"
        result_tb = "ТБ" if score1 + score2 > 5 else "ТМ"
        result_ob = "ОБ" if score1 > 0 and score2 > 0 else "НЕТ"
        
        db = Database()
        db.execute("UPDATE matches SET status = 'finished', result = ? WHERE id = ?", (result, match_id))
        
        bets = db.fetchall("SELECT id, user_id, bet_choice, amount, odds, potential_win FROM bets WHERE match_id = ? AND status = 'pending'", (match_id,))
        win_count = 0
        
        for bet in bets:
            bet_id, bet_user_id, bet_choice, amount, odds, potential = bet
            win = False
            
            if bet_choice == 'p1' and result == "П1":
                win = True
            elif bet_choice == 'p2' and result == "П2":
                win = True
            elif bet_choice == 'tb' and result_tb == "ТБ":
                win = True
            elif bet_choice == 'tm' and result_tb == "ТМ":
                win = True
            elif bet_choice == 'ob' and result_ob == "ОБ":
                win = True
            
            if win:
                db.execute("UPDATE bets SET status = 'won', settled_at = ? WHERE id = ?", (int(time.time()), bet_id))
                db.execute("UPDATE users SET balance = balance + ?, wins = wins + 1 WHERE user_id = ?", (potential, bet_user_id))
                win_count += 1
            else:
                db.execute("UPDATE bets SET status = 'lost', settled_at = ? WHERE id = ?", (int(time.time()), bet_id))
                db.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (bet_user_id,))
        
        # Обновляем список
        matches = db.fetchall("SELECT id, team1, team2 FROM matches WHERE status = 'active'")
        if matches:
            text = "📋 Обновлённая таблица активных матчей\n\n"
            for m in matches:
                text += f"ID: {m[0]} — {m[1]} vs {m[2]} — активен\n"
            text += "\nВведите команду:\n/end_match <id> <счёт>\n\nПример: /end_match 1 2:1"
        else:
            text = "✅ Все матчи завершены. Активных матчей нет."
        
        await update.message.reply_text(
            f"✅ Матч #{match_id} завершен. Счёт: {score1}:{score2}.\n\n{text}",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
# ========== АДМИН: ПРОМОКОДЫ ==========
async def admin_promocodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    await update.message.reply_text(
        "🎫 Создание промокода (пошагово)\n\n"
        "Введите данные через пробел:\n"
        "код тип_награды значение [макс_использований]\n\n"
        "Пример:\n"
        "/create_promo START2026 фикс 500 10\n"
        "/create_promo NEWYEAR процент 20 5\n"
        "/create_promo VIP777 фрибет 1000 1\n\n"
        "Типы награды:\n"
        "фикс — фиксированная сумма\n"
        "процент — процент от баланса\n"
        "фрибет — бесплатная ставка",
        reply_markup=get_admin_keyboard()
    )

async def admin_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: /create_promo код тип_награды значение [макс_использований]", reply_markup=get_admin_keyboard())
            return
        args = parts[1].split()
        if len(args) < 3:
            await update.message.reply_text("❌ Формат: /create_promo код тип_награды значение [макс_использований]", reply_markup=get_admin_keyboard())
            return
        code = args[0].upper()
        reward_type = args[1]
        reward_value = args[2]
        max_uses = int(args[3]) if len(args) > 3 else 1
        valid_types = ['фикс', 'процент', 'фрибет']
        if reward_type not in valid_types:
            await update.message.reply_text(f"❌ Неверный тип награды. Допустимые: фикс, процент, фрибет", reply_markup=get_admin_keyboard())
            return
        db_type_map = {
            'фикс': 'fixed',
            'процент': 'percent',
            'фрибет': 'freebet'
        }
        db_reward_type = db_type_map[reward_type]
        db = Database()
        existing = db.fetchone("SELECT code FROM promocodes WHERE code = ?", (code,))
        if existing:
            await update.message.reply_text("❌ Такой код уже существует", reply_markup=get_admin_keyboard())
            return
        db.execute("INSERT INTO promocodes (code, reward_type, reward_value, max_uses) VALUES (?, ?, ?, ?)",
                   (code, db_reward_type, reward_value, max_uses))
        await update.message.reply_text(f"✅ Промокод {code} создан!", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())

# ========== АДМИН: РАССЫЛКА ==========
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    await update.message.reply_text("📢 Рассылка\n\n/broadcast_all сообщение", reply_markup=get_admin_keyboard())

async def admin_broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    try:
        text = update.message.text
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: /broadcast_all сообщение", reply_markup=get_admin_keyboard())
            return
        message = parts[1]
        db = Database()
        users = db.fetchall("SELECT user_id FROM users WHERE is_banned = 0")
        await update.message.reply_text(f"📢 Начинаю рассылку {len(users)} пользователям...", reply_markup=get_admin_keyboard())
        count = 0
        for u in users:
            try:
                await context.bot.send_message(chat_id=u[0], text=f"📢 Админ рассылка:\n\n{message}")
                count += 1
            except:
                pass
        await update.message.reply_text(f"✅ Рассылка завершена. Отправлено {count} сообщений", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())

# ========== АДМИН: СТАТИСТИКА ==========
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    db = Database()
    total_users = db.fetchone("SELECT COUNT(*) FROM users")[0]
    total_bets = db.fetchone("SELECT COUNT(*) FROM bets")[0]
    total_wins = db.fetchone("SELECT COUNT(*) FROM bets WHERE status = 'won'")[0]
    total_losses = db.fetchone("SELECT COUNT(*) FROM bets WHERE status = 'lost'")[0]
    total_turnover = db.fetchone("SELECT SUM(turnover) FROM users")[0] or 0
    text = "📊 Статистика бота\n\n"
    text += f"👥 Пользователей: {total_users}\n"
    text += f"📈 Всего ставок: {total_bets}\n"
    text += f"🏆 Выиграно: {total_wins}\n"
    text += f"💔 Проиграно: {total_losses}\n"
    text += f"💰 Общий оборот: {format_balance(total_turnover)}"
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# ========== АДМИН: ПРОСМОТР СООБЩЕНИЙ ==========
async def admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    db = Database()
    messages = db.fetchall("SELECT id, user_id, message, reply, created_at FROM admin_messages ORDER BY created_at DESC LIMIT 20")
    text = "📨 Сообщения от пользователей\n\n"
    for m in messages:
        date = datetime.fromtimestamp(m[4]).strftime("%d.%m %H:%M")
        text += f"ID: {m[1]} | {date}\n{m[2]}\n"
        if m[3]:
            text += f"📩 Ответ: {m[3]}\n"
        text += "\n"
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# ========== ОБРАБОТЧИК КНОПОК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "menu":
        await menu(update, context)
    elif data == "matches":
        await matches(update, context)
    elif data.startswith("match_"):
        await match_detail(update, context)
    elif data.startswith("bet_"):
        await place_bet(update, context)
    elif data.startswith("match_team1_"):
        await match_team1(update, context)
    elif data.startswith("match_team2_"):
        await match_team2(update, context)
    elif data.startswith("end_match_"):
        await end_match_select(update, context)
    elif data.startswith("end_result_"):
        await end_result(update, context)
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data.startswith("admin_"):
        if query.from_user.id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Доступ запрещен")
            return
        if data == "admin_users":
            await admin_users(update, context)
        elif data == "admin_matches":
            await admin_matches(update, context)
        elif data == "admin_promocodes":
            await admin_promocodes(update, context)
        elif data == "admin_broadcast":
            await admin_broadcast(update, context)
        elif data == "admin_stats":
            await admin_stats(update, context)
        elif data == "admin_messages":
            await admin_messages(update, context)

# ========== ИСТОРИЯ БАЛАНСА ==========
async def balance_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    history = db.fetchall("SELECT amount, reason, created_at FROM balance_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,))
    if not history:
        await update.message.reply_text("📊 История баланса пуста.", reply_markup=get_main_keyboard(user_id))
        return
    text = "📊 История баланса (последние 10 операций)\n\n"
    for h in history:
        date = datetime.fromtimestamp(h[2]).strftime("%d.%m %H:%M")
        sign = "+" if h[0] > 0 else ""
        text += f"{sign}{format_balance(h[0])} — {h[1]} ({date})\n"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
# ========== ОБРАБОТЧИК ТЕКСТОВЫХ КНОПОК ==========
async def text_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Если пользователь в режиме добавления друга
    if "adding_friend" in context.user_data:
        await handle_add_friend(update, context)
        return
    
    # Если пользователь в режиме связи с админом
    if "contacting_admin" in context.user_data:
        await handle_contact_admin(update, context)
        return
    
    # Если пользователь вводит промокод
    if "entering_promo" in context.user_data:
        await use_promo(update, context)
        return
    
    # Обработка кнопок
    if text == "🏒 Матчи":
        await matches(update, context)
        return
    elif text == "🎁 Бонус":
        await bonus(update, context)
        return
    elif text == "👤 Профиль":
        await profile(update, context)
        return
    elif text == "🏆 Топ":
        await top(update, context)
        return
    elif text == "📊 Статистика":
        await stats(update, context)
        return
    elif text == "🎯 Квесты":
        await quests(update, context)
        return
    elif text == "📨 Связаться с админом":
        await contact_admin(update, context)
        return
    elif text == "➕ Добавить друга":
        await add_friend(update, context)
        return
    elif text == "📊 История баланса":
        await balance_history(update, context)
        return
    elif text == "🎫 Промокод":
        await promo_button_handler(update, context)
        return
    elif text == "🏒 Создать матч" and user_id in ADMIN_IDS:
        await admin_create_match(update, context)
        return
    elif text == "🏒 Завершить матч" and user_id in ADMIN_IDS:
        await admin_end_match(update, context)
        return
    elif text == "🔧 Админ панель" and user_id in ADMIN_IDS:
        await admin_panel(update, context)
        return
    elif text == "👥 Список пользователей" and user_id in ADMIN_IDS:
        await admin_users(update, context)
        return
    elif text == "💳 Выдать деньги" and user_id in ADMIN_IDS:
        await update.message.reply_text("Введите: /give_money id сумма", reply_markup=get_admin_keyboard())
        return
    elif text == "💳 Списать деньги" and user_id in ADMIN_IDS:
        await update.message.reply_text("Введите: /take_money id сумма", reply_markup=get_admin_keyboard())
        return
    elif text == "🚫 Забанить" and user_id in ADMIN_IDS:
        await update.message.reply_text("Введите: /ban id", reply_markup=get_admin_keyboard())
        return
    elif text == "✅ Разбанить" and user_id in ADMIN_IDS:
        await update.message.reply_text("Введите: /unban id", reply_markup=get_admin_keyboard())
        return
    else:
        # Если текст не совпал — просто игнорируем
        print(f"Неизвестная кнопка: {text}")
        return
# ========== ОБРАБОТЧИК ПРОМОКОДОВ ==========
async def promo_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎫 Введите код промокода (например, START2026):")
    context.user_data["entering_promo"] = True

async def use_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if "entering_promo" not in context.user_data:
        return
    text = update.message.text.strip()
    code = text.upper()
    db = Database()
    promo = db.fetchone("""
        SELECT reward_type, reward_value, max_uses, used_count, is_active 
        FROM promocodes WHERE code = ?
    """, (code,))
    if not promo:
        await update.message.reply_text("❌ Промокод не найден")
        del context.user_data["entering_promo"]
        return
    reward_type, reward_value, max_uses, used_count, is_active = promo
    if not is_active:
        await update.message.reply_text("❌ Промокод неактивен")
        del context.user_data["entering_promo"]
        return
    if used_count >= max_uses:
        await update.message.reply_text("❌ Промокод уже использован максимальное количество раз")
        del context.user_data["entering_promo"]
        return
    if reward_type == 'fixed':
        amount = int(reward_value)
        db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await update.message.reply_text(f"✅ Промокод активирован! Вы получили {format_balance(amount)}")
    elif reward_type == 'percent':
        percent = int(reward_value)
        if percent < 0 or percent > 100:
            await update.message.reply_text("❌ Неверный процент")
            del context.user_data["entering_promo"]
            return
        balance = db.fetchone("SELECT balance FROM users WHERE user_id = ?", (user_id,))[0]
        amount = int(balance * percent / 100)
        db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await update.message.reply_text(f"✅ Промокод активирован! Вы получили {percent}% от баланса = {format_balance(amount)}")
    elif reward_type == 'freebet':
        amount = int(reward_value)
        expires_at = int(time.time()) + 7 * 86400
        db.execute("INSERT INTO freebets (user_id, amount, created_at, expires_at) VALUES (?, ?, ?, ?)",
                   (user_id, amount, int(time.time()), expires_at))
        await update.message.reply_text(f"✅ Промокод активирован! Вы получили фрибет на {format_balance(amount)}!")
    db.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
    del context.user_data["entering_promo"]

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("bonus", bonus))
    app.add_handler(CommandHandler("matches", matches))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("quests", quests))
    app.add_handler(CommandHandler("balance_history", balance_history))
    
    # Админ команды
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("create_match", admin_create_match))
    app.add_handler(CommandHandler("end_match", admin_end_match))
    app.add_handler(CommandHandler("create_promo", admin_create_promo))
    app.add_handler(CommandHandler("broadcast_all", admin_broadcast_all))
    app.add_handler(CommandHandler("give_money", admin_give_money))
    app.add_handler(CommandHandler("take_money", admin_take_money))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("admin_messages", admin_messages))
    
    # Обработчики
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet_amount))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🏒 Hockey Bet Bot запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
