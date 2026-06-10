import logging
import random
import sqlite3
import threading
import time

from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = "8307541675:AAG5pt1ig8PouMJTy9DPhtnMF8JZI675BMU"

ADMIN_IDS = [
    1205576607
]

CURRENCY = "🏒 Шайбочки"

START_BALANCE = 1000

BONUS_INTERVAL = 18000
BONUS_MIN = 500
BONUS_MAX = 5000
# =========================
# СПИСКИ КВЕСТОВ
# =========================
DAILY_QUESTS = [
    {
        "id": "daily_bets_3",
        "name": "Сделать 3 ставки",
        "target": 3,
        "reward": 500
    },
    {
        "id": "daily_win_1",
        "name": "Выиграть 1 ставку",
        "target": 1,
        "reward": 500
    },
    {
        "id": "daily_bonus",
        "name": "Получить бонус",
        "target": 1,
        "reward": 500
    }
]

WEEKLY_QUESTS = [
    {
        "id": "weekly_bets_20",
        "name": "Сделать 20 ставок",
        "target": 20,
        "reward": 2000
    },
    {
        "id": "weekly_wins_10",
        "name": "Выиграть 10 ставок",
        "target": 10,
        "reward": 2000
    },
    {
        "id": "weekly_invite",
        "name": "Пригласить друга",
        "target": 1,
        "reward": 2000
    }
]

PERMANENT_QUESTS = [
    {
        "id": "perm_bets_10",
        "name": "Сделать 10 ставок",
        "target": 10,
        "reward": 1000
    },
    {
        "id": "perm_bets_50",
        "name": "Сделать 50 ставок",
        "target": 50,
        "reward": 3000
    },
    {
        "id": "perm_bets_100",
        "name": "Сделать 100 ставок",
        "target": 100,
        "reward": 5000
    },
    {
        "id": "perm_wins_100",
        "name": "Выиграть 100 ставок",
        "target": 100,
        "reward": 10000
    }
]
# =========================
# КЛАВИАТУРЫ
# =========================

def get_main_keyboard(user_id):

    keyboard = [
        [
            KeyboardButton("🏒 Матчи"),
            KeyboardButton("🎁 Бонус")
        ],
        [
            KeyboardButton("👤 Профиль"),
            KeyboardButton("🏆 Топ")
        ],
        [
            KeyboardButton("📊 Статистика"),
            KeyboardButton("🎯 Квесты")
        ],
        [
            KeyboardButton("📨 Связаться с админом"),
            KeyboardButton("➕ Добавить друга")
        ],
        [
            KeyboardButton("📊 История баланса"),
            KeyboardButton("🎫 Промокод")
        ]
    ]

    if user_id in ADMIN_IDS:

        keyboard.append(
            [
                KeyboardButton("🔧 Админ панель")
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


from telegram import ReplyKeyboardMarkup, KeyboardButton

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("👥 Пользователи"), KeyboardButton("📊 Статистика бота")],
        [KeyboardButton("💰 Выдать деньги"), KeyboardButton("💸 Списать деньги")],
        [KeyboardButton("🚫 Забанить"), KeyboardButton("✅ Разбанить")],
        [KeyboardButton("🏒 Матчи"), KeyboardButton("🎫 Промокоды")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("📨 Сообщения")],
        [KeyboardButton("🔙 В главное меню")]
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# =========================
# DATABASE
# =========================

class Database:

    def __init__(self, db_name="hockey_bet.db"):

        self.conn = sqlite3.connect(
            db_name,
            check_same_thread=False
        )

        self.cursor = self.conn.cursor()

        self.lock = threading.Lock()

        self.create_tables()


    def create_tables(self):

        with self.lock:

            # Пользователи
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
                referrer_id INTEGER,
                referral_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                registered_at INTEGER DEFAULT 0,
                daily_quest_reset INTEGER DEFAULT 0,
                weekly_quest_reset INTEGER DEFAULT 0,
                friends TEXT DEFAULT ''
            )
            """)

            # Матчи
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
                result TEXT,
                created_at INTEGER,
                finished_at INTEGER
            )
            """)

            # Ставки
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
                created_at INTEGER,
                settled_at INTEGER
            )
            """)

            # Промокоды
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward_type TEXT,
                reward_value TEXT,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
            """)

            # Квесты
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                user_id INTEGER,
                quest_id TEXT,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                completed_at INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, quest_id)
            )
            """)

            # История баланса
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at INTEGER
            )
            """)

            # Сообщения админу
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                reply TEXT,
                created_at INTEGER
            )
            """)

            # Фрибеты
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS freebets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                used INTEGER DEFAULT 0,
                created_at INTEGER,
                expires_at INTEGER
            )
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
# Создание объекта БД

db = Database()
# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def format_balance(amount):

    return f"{amount:,} {CURRENCY}"


def add_balance_history(
    user_id,
    amount,
    reason
):

    db.execute(
        """
        INSERT INTO balance_history
        (
            user_id,
            amount,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            amount,
            reason,
            int(time.time())
        )
    )


def check_quest_completion(
    user_id
):

    # Ежедневные
    for quest in DAILY_QUESTS:

        data = db.fetchone(
            """
            SELECT
                progress,
                completed
            FROM quests
            WHERE user_id = ?
            AND quest_id = ?
            """,
            (
                user_id,
                quest["id"]
            )
        )

        if not data:
            continue

        progress, completed = data

        if completed == 0 and progress >= quest["target"]:

            db.execute(
                """
                UPDATE quests
                SET
                    completed = 1,
                    completed_at = ?
                WHERE user_id = ?
                AND quest_id = ?
                """,
                (
                    int(time.time()),
                    user_id,
                    quest["id"]
                )
            )

            db.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE user_id = ?
                """,
                (
                    quest["reward"],
                    user_id
                )
            )

            add_balance_history(
                user_id,
                quest["reward"],
                f"🎯 Квест: {quest['name']}"
            )

    # Еженедельные
    for quest in WEEKLY_QUESTS:

        data = db.fetchone(
            """
            SELECT
                progress,
                completed
            FROM quests
            WHERE user_id = ?
            AND quest_id = ?
            """,
            (
                user_id,
                quest["id"]
            )
        )

        if not data:
            continue

        progress, completed = data

        if completed == 0 and progress >= quest["target"]:

            db.execute(
                """
                UPDATE quests
                SET
                    completed = 1,
                    completed_at = ?
                WHERE user_id = ?
                AND quest_id = ?
                """,
                (
                    int(time.time()),
                    user_id,
                    quest["id"]
                )
            )

            db.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE user_id = ?
                """,
                (
                    quest["reward"],
                    user_id
                )
            )

            add_balance_history(
                user_id,
                quest["reward"],
                f"🎯 Квест: {quest['name']}"
            )

    # Постоянные
    for quest in PERMANENT_QUESTS:

        data = db.fetchone(
            """
            SELECT
                progress,
                completed
            FROM quests
            WHERE user_id = ?
            AND quest_id = ?
            """,
            (
                user_id,
                quest["id"]
            )
        )

        if not data:
            continue

        progress, completed = data

        if completed == 0 and progress >= quest["target"]:

            db.execute(
                """
                UPDATE quests
                SET
                    completed = 1,
                    completed_at = ?
                WHERE user_id = ?
                AND quest_id = ?
                """,
                (
                    int(time.time()),
                    user_id,
                    quest["id"]
                )
            )

            db.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE user_id = ?
                """,
                (
                    quest["reward"],
                    user_id
                )
            )

            add_balance_history(
                user_id,
                quest["reward"],
                f"🎯 Квест: {quest['name']}"
            )
# =========================
# ОСНОВНЫЕ КОМАНДЫ
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = Database()
    
    existing = db.fetchone("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    
    if not existing:
        db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, balance, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user.id, user.username, user.first_name, user.last_name, START_BALANCE, int(time.time())))
        
        # Инициализация квестов
        for q in DAILY_QUESTS + WEEKLY_QUESTS + PERMANENT_QUESTS:
            db.execute("INSERT INTO quests (user_id, quest_id) VALUES (?, ?)", (user.id, q["id"]))
    
    await update.message.reply_text(
        f"🏒 Добро пожаловать в Hockey Bet!\n\nВаш баланс: {format_balance(START_BALANCE)}",
        reply_markup=get_main_keyboard(user.id)
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    
    user = db.fetchone("SELECT last_bonus_time, balance FROM users WHERE user_id = ?", (user_id,))
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    
    last_bonus_time, balance = user
    now = int(time.time())
    
    if now - last_bonus_time < BONUS_INTERVAL:
        remaining = BONUS_INTERVAL - (now - last_bonus_time)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(f"⏳ Бонус будет доступен через {hours}ч {minutes}м")
        return
    
    amount = random.randint(BONUS_MIN, BONUS_MAX)
    db.execute("UPDATE users SET balance = balance + ?, last_bonus_time = ? WHERE user_id = ?", (amount, now, user_id))
    add_balance_history(user_id, amount, "🎁 Бонус")
    await update.message.reply_text(f"🎁 Вы получили бонус!")


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    
    user = db.fetchone("""
        SELECT username, first_name, last_name, balance, turnover, wins, losses, bets_count
        FROM users WHERE user_id = ?
    """, (user_id,))
    
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    
    username, first_name, last_name, balance, turnover, wins, losses, bets_count = user
    total = wins + losses
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    
    text = f"👤 Профиль\n\n"
    text += f"💰 Баланс: {format_balance(balance)}\n"
    text += f"🔄 Оборот: {format_balance(turnover)}\n"
    text += f"🏆 Победы: {wins}\n"
    text += f"💔 Поражения: {losses}\n"
    text += f"🎯 Всего ставок: {bets_count}\n"
    text += f"📈 Процент побед: {win_rate}%\n"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = Database()
    top_balance = db.fetchall("SELECT user_id, first_name, balance FROM users ORDER BY balance DESC LIMIT 10")
    top_wins = db.fetchall("SELECT user_id, first_name, wins FROM users ORDER BY wins DESC LIMIT 10")
    
    text = "🏆 Топ игроков\n\n"
    text += "💰 По балансу:\n"
    for i, u in enumerate(top_balance):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        text += f"{medal} {u[1] or 'Игрок'} — {format_balance(u[2])}\n"
    
    text += "\n🏒 По победам:\n"
    for i, u in enumerate(top_wins):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
        text += f"{medal} {u[1] or 'Игрок'} — {u[2]} побед\n"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(update.effective_user.id))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    user = db.fetchone("SELECT bets_count, wins, losses, turnover FROM users WHERE user_id = ?", (user_id,))
    
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    
    bets_count, wins, losses, turnover = user
    total = wins + losses
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    
    text = f"📊 Статистика\n\n"
    text += f"📈 Всего ставок: {bets_count}\n"
    text += f"🏆 Победы: {wins}\n"
    text += f"💔 Поражения: {losses}\n"
    text += f"📊 Процент побед: {win_rate}%\n"
    text += f"🔄 Оборот: {format_balance(turnover)}\n"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))


async def quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    
    data = db.fetchall("SELECT quest_id, progress, completed FROM quests WHERE user_id = ?", (user_id,))
    if not data:
        await update.message.reply_text("🎯 Квесты не найдены")
        return
    
    text = "🎯 Квесты\n\n"
    for q in data:
        status = "✅" if q[2] else f"{q[1]}/{q[0]}"  # simplified
        text += f"{q[0]}: {status}\n"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))


async def balance_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = Database()
    
    history = db.fetchall("SELECT amount, reason, created_at FROM balance_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,))
    
    if not history:
        await update.message.reply_text("📊 История баланса пуста", reply_markup=get_main_keyboard(user_id))
        return
    
    text = "📊 История баланса\n\n"
    for h in history:
        date = datetime.fromtimestamp(h[2]).strftime("%d.%m %H:%M")
        sign = "+" if h[0] > 0 else ""
        text += f"{sign}{format_balance(h[0])} — {h[1]} ({date})\n"
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Нет доступа")
        return

    await update.message.reply_text(
        "🔧 Админ панель",
        reply_markup=get_admin_keyboard()
    )
# =========================
# 9. ДРУЗЬЯ
# =========================

async def add_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    context.user_data["adding_friend"] = True

    await update.message.reply_text(
        "👥 Добавление друга\n\n"
        "Отправьте ID пользователя, которого хотите добавить в друзья:"
    )


async def handle_add_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if "adding_friend" not in context.user_data:
        return

    db = Database()

    # проверка что введён ID
    if not text.isdigit():
        await update.message.reply_text("❌ Введите корректный ID пользователя")
        return

    friend_id = int(text)

    # защита от добавления самого себя
    if friend_id == user_id:
        await update.message.reply_text("❌ Вы не можете добавить самого себя")
        del context.user_data["adding_friend"]
        return

    # проверка существования пользователя
    friend = db.fetchone(
        "SELECT user_id, first_name FROM users WHERE user_id = ?",
        (friend_id,)
    )

    if not friend:
        await update.message.reply_text("❌ Пользователь не найден")
        del context.user_data["adding_friend"]
        return

    # добавляем в список друзей (строкой через запятую)
    user = db.fetchone(
        "SELECT friends FROM users WHERE user_id = ?",
        (user_id,)
    )

    friends = user[0] if user and user[0] else ""

    friends_list = friends.split(",") if friends else []

    if str(friend_id) in friends_list:
        await update.message.reply_text("❌ Этот пользователь уже у вас в друзьях")
        del context.user_data["adding_friend"]
        return

    friends_list.append(str(friend_id))

    db.execute(
        "UPDATE users SET friends = ? WHERE user_id = ?",
        (",".join(friends_list), user_id)
    )

    # уведомление другу
    try:
        await context.bot.send_message(
            chat_id=friend_id,
            text=f"👥 Вас добавили в друзья!\n"
                 f"От пользователя ID: {user_id}"
        )
    except:
        pass

    # уведомление отправителю
    await update.message.reply_text(
        f"✅ Пользователь {friend_id} добавлен в друзья"
    )

    del context.user_data["adding_friend"]
# =========================
# 10. СВЯЗЬ С АДМИНОМ
# =========================

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    context.user_data["contacting_admin"] = True

    await update.message.reply_text(
        "📨 Связь с админом\n\n"
        "Напишите ваше сообщение, и оно будет отправлено администрации:"
    )


async def handle_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if "contacting_admin" not in context.user_data:
        return

    db = Database()

    # сохраняем сообщение в БД
    db.execute(
        """
        INSERT INTO admin_messages
        (
            user_id,
            message,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            text,
            int(time.time())
        )
    )

    # уведомление всем админам
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    "📨 Новое сообщение от пользователя\n\n"
                    f"ID: {user_id}\n"
                    f"Сообщение:\n{text}"
                )
            )
        except:
            pass

    # подтверждение пользователю
    await update.message.reply_text(
        "✅ Ваше сообщение отправлено администрации"
    )

    del context.user_data["contacting_admin"] 
# =========================
# 11. ПРОМОКОДЫ
# =========================

async def promo_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    context.user_data["entering_promo"] = True

    await update.message.reply_text(
        "🎫 Промокоды\n\n"
        "Введите промокод:"
    )


async def use_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    if "entering_promo" not in context.user_data:
        return

    db = Database()

    promo = db.fetchone(
        """
        SELECT reward_type,
               reward_value,
               max_uses,
               used_count,
               is_active
        FROM promocodes
        WHERE code = ?
        """,
        (text,)
    )

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
        await update.message.reply_text("❌ Промокод уже использован")
        del context.user_data["entering_promo"]
        return

    # =========================
    # ФИКСИРОВАННАЯ СУММА
    # =========================
    if reward_type == "fixed":
        amount = int(reward_value)

        db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )

        add_balance_history(user_id, amount, f"🎫 Промокод {text}")

        await update.message.reply_text(
            f"✅ Промокод активирован!\nВы получили {amount}"
        )

    # =========================
    # ПРОЦЕНТ ОТ БАЛАНСА
    # =========================
    elif reward_type == "percent":
        percent = int(reward_value)

        user = db.fetchone(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,)
        )

        balance = user[0]

        amount = int(balance * percent / 100)

        db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )

        add_balance_history(user_id, amount, f"🎫 Промокод {text}")

        await update.message.reply_text(
            f"✅ Промокод активирован!\n"
            f"Вы получили {percent}% = {amount}"
        )

    # =========================
    # ФРИБЕТ
    # =========================
    elif reward_type == "freebet":
        amount = int(reward_value)

        db.execute(
            """
            INSERT INTO freebets
            (
                user_id,
                amount,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                amount,
                int(time.time()),
                int(time.time()) + 7 * 86400
            )
        )

        await update.message.reply_text(
            f"✅ Вы получили фрибет: {amount}"
        )

    # увеличиваем использование промокода
    db.execute(
        """
        UPDATE promocodes
        SET used_count = used_count + 1
        WHERE code = ?
        """,
        (text,)
    )

    del context.user_data["entering_promo"]
# =========================
# 12. МАТЧИ И СТАВКИ
# =========================

async def matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = Database()

    matches = db.fetchall(
        """
        SELECT id,
               team1,
               team2,
               odds_p1,
               odds_p2,
               odds_tb,
               odds_tm,
               odds_ob
        FROM matches
        WHERE status = 'active'
        """
    )

    if not matches:
        await update.message.reply_text("❌ Активных матчей нет")
        return

    keyboard = []

    for m in matches:
        match_id, t1, t2 = m[0], m[1], m[2]

        keyboard.append([
            InlineKeyboardButton(
                f"{t1} vs {t2}",
                callback_data=f"match_{match_id}"
            )
        ])

    await update.message.reply_text(
        "🏒 Активные матчи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def match_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    match_id = int(query.data.split("_")[1])

    db = Database()

    match = db.fetchone(
        """
        SELECT id,
               team1,
               team2,
               odds_p1,
               odds_p2,
               odds_tb,
               odds_tm,
               odds_ob
        FROM matches
        WHERE id = ?
        """,
        (match_id,)
    )

    if not match:
        await query.edit_message_text("❌ Матч не найден")
        return

    (
        _,
        team1,
        team2,
        p1,
        p2,
        tb,
        tm,
        ob
    ) = match

    keyboard = [
        [InlineKeyboardButton(f"{team1} (П1) {p1}", callback_data=f"bet_{match_id}_p1")],
        [InlineKeyboardButton(f"{team2} (П2) {p2}", callback_data=f"bet_{match_id}_p2")],
        [InlineKeyboardButton(f"ТБ {tb}", callback_data=f"bet_{match_id}_tb")],
        [InlineKeyboardButton(f"ТМ {tm}", callback_data=f"bet_{match_id}_tm")],
        [InlineKeyboardButton(f"ОЗ {ob}", callback_data=f"bet_{match_id}_ob")]
    ]

    await query.edit_message_text(
        f"🏒 {team1} vs {team2}\n\nВыберите тип ставки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, match_id, bet_type = query.data.split("_")

    db = Database()

    match = db.fetchone(
        """
        SELECT team1,
               team2,
               odds_p1,
               odds_p2,
               odds_tb,
               odds_tm,
               odds_ob
        FROM matches
        WHERE id = ?
        """,
        (match_id,)
    )

    if not match:
        await query.edit_message_text("❌ Матч не найден")
        return

    team1, team2 = match[0], match[1]

    odds_map = {
        "p1": match[2],
        "p2": match[3],
        "tb": match[4],
        "tm": match[5],
        "ob": match[6]
    }

    context.user_data["bet"] = {
        "match_id": int(match_id),
        "bet_type": bet_type,
        "odds": odds_map[bet_type]
    }

    await query.edit_message_text(
        f"🏒 {team1} vs {team2}\n\n"
        f"Ставка: {bet_type}\n"
        f"Коэффициент: {odds_map[bet_type]}\n\n"
        f"Введите сумму ставки:"
    )


async def handle_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if "bet" not in context.user_data:
        return

    if not text.isdigit():
        await update.message.reply_text("❌ Введите число")
        return

    amount = int(text)

    db = Database()

    user = db.fetchone(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )

    if not user:
        await update.message.reply_text("❌ Пользователь не найден")
        return

    balance = user[0]

    if amount > balance:
        await update.message.reply_text("❌ Недостаточно средств")
        return

    bet_data = context.user_data["bet"]

    match_id = bet_data["match_id"]
    bet_type = bet_data["bet_type"]
    odds = bet_data["odds"]

    potential_win = int(amount * odds)

    db.execute(
        """
        INSERT INTO bets
        (
            user_id,
            match_id,
            bet_type,
            amount,
            odds,
            potential_win,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            match_id,
            bet_type,
            amount,
            odds,
            potential_win,
            int(time.time())
        )
    )

    db.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (amount, user_id)
    )

    add_balance_history(user_id, -amount, "🏒 Ставка")

    del context.user_data["bet"]

    await update.message.reply_text(
        f"✅ Ставка принята!\n"
        f"Сумма: {amount}\n"
        f"Потенциальный выигрыш: {potential_win}"
    )
# =========================
# 13. АДМИНКА
# =========================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ Доступ запрещен")
        return

    await update.message.reply_text(
        "🔧 Админ панель"
    )


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    db = Database()

    users = db.fetchall(
        """
        SELECT user_id,
               balance,
               wins,
               losses,
               bets_count
        FROM users
        ORDER BY balance DESC
        """
    )

    text = "👥 Пользователи:\n\n"

    for u in users:
        text += (
            f"ID: {u[0]}\n"
            f"💰 Баланс: {u[1]}\n"
            f"🏆 Wins: {u[2]} | ❌ Losses: {u[3]}\n"
            f"🎯 Bets: {u[4]}\n\n"
        )

    await update.message.reply_text(text)


async def admin_give_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        _, target_id, amount = update.message.text.split()
        target_id = int(target_id)
        amount = int(amount)

        db = Database()

        db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, target_id)
        )

        add_balance_history(target_id, amount, "💳 Админ начислил")

        await update.message.reply_text("✅ Деньги выданы")

    except:
        await update.message.reply_text("❌ Ошибка")


async def admin_take_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        _, target_id, amount = update.message.text.split()
        target_id = int(target_id)
        amount = int(amount)

        db = Database()

        db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, target_id)
        )

        add_balance_history(target_id, -amount, "💳 Админ списал")

        await update.message.reply_text("✅ Деньги списаны")

    except:
        await update.message.reply_text("❌ Ошибка")


async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        target_id = int(update.message.text.split()[1])

        db = Database()

        db.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?",
            (target_id,)
        )

        await update.message.reply_text("🚫 Забанен")

    except:
        await update.message.reply_text("❌ Ошибка")


async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        target_id = int(update.message.text.split()[1])

        db = Database()

        db.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?",
            (target_id,)
        )

        await update.message.reply_text("✅ Разбанен")

    except:
        await update.message.reply_text("❌ Ошибка")


async def admin_create_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        _, team1, team2 = update.message.text.split(" ", 2)

        db = Database()

        db.execute(
            """
            INSERT INTO matches
            (
                team1,
                team2,
                status
            )
            VALUES (?, ?, 'active')
            """,
            (team1, team2)
        )

        await update.message.reply_text("🏒 Матч создан")

    except:
        await update.message.reply_text("❌ Ошибка")


async def admin_end_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    db = Database()

    matches = db.fetchall(
        "SELECT id, team1, team2 FROM matches WHERE status = 'active'"
    )

    text = "🏒 Активные матчи:\n\n"

    for m in matches:
        text += f"{m[0]}: {m[1]} vs {m[2]}\n"

    await update.message.reply_text(text)


async def admin_end_match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        _, match_id, result = update.message.text.split()

        db = Database()

        db.execute(
            "UPDATE matches SET status = 'finished', result = ? WHERE id = ?",
            (result, match_id)
        )

        # Показываем обновлённый список
        active = db.fetchall("SELECT id, team1, team2 FROM matches WHERE status = 'active'")
        text = "📋 Активные матчи:\n\n"
        if active:
            for m in active:
                text += f"{m[0]}: {m[1]} vs {m[2]}\n"
        else:
            text += "Нет активных матчей"
        await update.message.reply_text(text)

    except:
        await update.message.reply_text("❌ Ошибка")


async def admin_promocodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    await update.message.reply_text(
        "🎫 Создание промокода:\n"
        "/create_promo CODE TYPE VALUE MAX_USES"
    )


async def admin_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    try:
        _, code, rtype, value, max_uses = update.message.text.split()

        db = Database()

        db.execute(
            """
            INSERT INTO promocodes
            (
                code,
                reward_type,
                reward_value,
                max_uses
            )
            VALUES (?, ?, ?, ?)
            """,
            (code.upper(), rtype, value, max_uses)
        )

        await update.message.reply_text("✅ Промокод создан")

    except:
        await update.message.reply_text("❌ Ошибка")


async def promo_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    db = Database()

    promos = db.fetchall("SELECT code, used_count, max_uses FROM promocodes")

    text = "🎫 Промокоды:\n\n"

    for p in promos:
        text += f"{p[0]}: {p[1]}/{p[2]}\n"

    await update.message.reply_text(text)


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    await update.message.reply_text("📢 Используй: /broadcast текст")


async def admin_broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    text = update.message.text.replace("/broadcast", "").strip()

    db = Database()

    users = db.fetchall("SELECT user_id FROM users")

    for u in users:
        try:
            await context.bot.send_message(u[0], text)
        except:
            pass

    await update.message.reply_text("📢 Рассылка завершена")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    db = Database()

    users = db.fetchone("SELECT COUNT(*) FROM users")[0]
    bets = db.fetchone("SELECT COUNT(*) FROM bets")[0]

    await update.message.reply_text(
        f"📊 Статистика\n\n👥 Users: {users}\n🎯 Bets: {bets}"
    )


async def admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    db = Database()

    msgs = db.fetchall(
        "SELECT user_id, message FROM admin_messages ORDER BY id DESC LIMIT 10"
    )

    text = "📨 Сообщения:\n\n"

    for m in msgs:
        text += f"{m[0]}: {m[1]}\n\n"

    await update.message.reply_text(text)
# =========================
# 14. CALLBACK КНОПКИ
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # =========================
    # МЕНЮ / НАВИГАЦИЯ
    # =========================
    if data == "menu":
        await query.message.edit_text("🏒 Главное меню")
        return

    # =========================
    # МАТЧИ
    # =========================
    if data == "matches":
        await matches(update, context)
        return

    if data.startswith("match_"):
        await match_detail(update, context)
        return

    # =========================
    # СТАВКИ
    # =========================
    if data.startswith("bet_"):
        await place_bet(update, context)
        return

    # =========================
    # АДМИН ПАНЕЛЬ
    # =========================
    if data == "admin_panel":
        if user_id not in ADMIN_IDS:
            await query.message.edit_text("⛔ Доступ запрещен")
            return

        await admin_panel(update, context)
        return

    if data == "admin_users":
        await admin_users(update, context)
        return

    if data == "admin_stats":
        await admin_stats(update, context)
        return

    if data == "admin_messages":
        await admin_messages(update, context)
        return

    # =========================
    # ПРОЧЕЕ
    # =========================
    await query.message.edit_text("❌ Неизвестная кнопка")
# =========================
# 15. ТЕКСТОВЫЕ КНОПКИ
# =========================

async def text_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    print(f"DEBUG: '{text}'")
    
    # ... остальной код ...
    # =========================
    # 1. ADMIN ACTION MODE (ПРИОРИТЕТ №1)
    # =========================
    if context.user_data.get("admin_action"):

        action = context.user_data["admin_action"]

        try:
            if action == "give_money":
                target_id, amount = map(int, text.split())
                # TODO: Database.add_balance(target_id, amount)
                await update.message.reply_text("✅ Выдано")
                context.user_data["admin_action"] = None
                return

            if action == "take_money":
                target_id, amount = map(int, text.split())
                # TODO: Database.remove_balance(target_id, amount)
                await update.message.reply_text("💸 Списано")
                context.user_data["admin_action"] = None
                return

            if action == "ban":
                target_id = int(text)
                # TODO: Database.ban_user(target_id)
                await update.message.reply_text("🚫 Забанен")
                context.user_data["admin_action"] = None
                return

            if action == "unban":
                target_id = int(text)
                # TODO: Database.unban_user(target_id)
                await update.message.reply_text("✅ Разбанен")
                context.user_data["admin_action"] = None
                return

            if action == "broadcast":
                # TODO: broadcast_all(text)
                await update.message.reply_text("📢 Рассылка отправлена")
                context.user_data["admin_action"] = None
                return

        except Exception:
            await update.message.reply_text("❌ Ошибка формата ввода")
            return

    # =========================
    # 2. РЕЖИМЫ ВВОДА (ВТОРОЙ ПРИОРИТЕТ)
    # =========================
    if context.user_data.get("adding_friend"):
        await handle_add_friend(update, context)
        return

    if context.user_data.get("contacting_admin"):
        await handle_contact_admin(update, context)
        return

    if context.user_data.get("entering_promo"):
        await use_promo(update, context)
        return

    if context.user_data.get("bet"):
        await handle_bet_amount(update, context)
        return

    # =========================
    # 3. ГЛАВНОЕ МЕНЮ
    # =========================
    if text == "🏒 Матчи":
        await matches(update, context)
        return

    if text == "🎁 Бонус":
        await bonus(update, context)
        return

    if text == "👤 Профиль":
        await profile(update, context)
        return

    if text == "🏆 Топ":
        await top(update, context)
        return

    if text == "📊 Статистика":
        await stats(update, context)
        return

    if text == "📊 История баланса":
        await balance_history(update, context)
        return

    # =========================
    # 4. ДОП КНОПКИ
    # =========================
    if text == "➕ Добавить друга":
        await add_friend(update, context)
        return

    if text == "📨 Связаться с админом":
        await contact_admin(update, context)
        return

    if text == "🎫 Промокод":
        await promo_button_handler(update, context)
        return

    # =========================
    # 5. АДМИН КНОПКИ (ВАЖНО: ТОЛЬКО ЕСЛИ ADMIN)
    # =========================
    if user_id in ADMIN_IDS:

        if text == "🔧 Админ панель":
            await admin_panel(update, context)
            return

        if text == "👥 Пользователи":
            await admin_users(update, context)
            return

        if text == "📊 Статистика бота":
            await admin_stats(update, context)
            return

        if text == "💰 Выдать деньги":
            context.user_data["admin_action"] = "give_money"
            await update.message.reply_text("Введите: ID СУММА")
            return

        if text == "💸 Списать деньги":
            context.user_data["admin_action"] = "take_money"
            await update.message.reply_text("Введите: ID СУММА")
            return

        if text == "🚫 Забанить":
            context.user_data["admin_action"] = "ban"
            await update.message.reply_text("Введите ID")
            return

        if text == "✅ Разбанить":
            context.user_data["admin_action"] = "unban"
            await update.message.reply_text("Введите ID")
            return

        if text == "📢 Рассылка":
            context.user_data["admin_action"] = "broadcast"
            await update.message.reply_text("Введите текст рассылки")
            return

        if text == "🔙 В главное меню":
            await update.message.reply_text(
                "🏠 Главное меню",
                reply_markup=get_main_keyboard()
            )
            return

    # =========================
    # 6. FALLBACK
    # =========================
    await update.message.reply_text("❌ Неизвестная команда")
# =========================
# 16. MAIN
# =========================

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    app = Application.builder().token(TOKEN).build()

    # =========================
    # COMMAND HANDLERS (команды /start и т.д.)
    # =========================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("bonus", bonus))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("quests", quests))
    app.add_handler(CommandHandler("balance_history", balance_history))

    # =========================
    # ADMIN COMMANDS
    # =========================
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("create_match", admin_create_match))
    app.add_handler(CommandHandler("end_match", admin_end_match_command))
    app.add_handler(CommandHandler("give_money", admin_give_money))
    app.add_handler(CommandHandler("take_money", admin_take_money))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("create_promo", admin_create_promo))
    app.add_handler(CommandHandler("broadcast_all", admin_broadcast_all))

    # =========================
    # CALLBACK (inline кнопки)
    # =========================
    app.add_handler(CallbackQueryHandler(button_handler))

    # =========================
    # TEXT BUTTONS (главный роутер)
    # ⚠️ ДОЛЖЕН БЫТЬ ОДИН
    # =========================
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_button_handler
        )
    )

    print("🏒 Bot started successfully!")
    app.run_polling()
# =========================
# 17. ЗАПУСК
# =========================

if __name__ == "__main__":
    main()
