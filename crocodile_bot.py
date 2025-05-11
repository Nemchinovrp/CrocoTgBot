import random
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Чтение слов из файла
with open('words.txt', 'r', encoding='utf-8') as f:
    WORDS = [word.strip() for word in f.readlines() if word.strip()]

# Чтение фраз для поздравлений
try:
    with open('wow.txt', 'r', encoding='utf-8') as f:
        WOW_PHRASES = [phrase.strip() for phrase in f.readlines() if phrase.strip()]
except FileNotFoundError:
    logger.warning("Файл wow.txt не найден, используются стандартные фразы")
    WOW_PHRASES = [
        "Вау, это было потрясающе!",
        "Невероятно!",
        "Отличная работа!",
        "Браво!",
        "Ты просто гений!",
        "Как тебе это удалось?",
        "Фантастически!",
        "Потрясающее угадывание!"
    ]

# Состояние игры для каждого чата
game_states = {}


class GameState:
    def __init__(self):
        self.current_word = None
        self.current_leader = None
        self.current_word_index = None
        self.message_id = None
        self.guessed = False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    chat_id = update.effective_chat.id
    if chat_id not in game_states:
        game_states[chat_id] = GameState()

    await update.message.reply_text(
        "🎭 Привет! Я бот для игры в Крокодила.\n"
        "🔹 Чтобы начать игру, используйте команду /play\n"
        "🔹 Когда слово угадано, просто напишите его в чат!"
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает новую игру"""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in game_states:
        game_states[chat_id] = GameState()

    game_state = game_states[chat_id]

    if game_state.current_leader is not None:
        await update.message.reply_text(
            "❗ Игра уже идет! Дождитесь окончания или ведущий должен передать ход."
        )
        return

    word_index = random.randint(0, len(WORDS) - 1)
    game_state.current_word = WORDS[word_index]
    game_state.current_word_index = word_index
    game_state.current_leader = user.id
    game_state.guessed = False

    keyboard = [
        [InlineKeyboardButton("🔎 Показать слово", callback_data="show_word")],
        [InlineKeyboardButton("🔄 Сменить слово", callback_data="change_word")],
        [InlineKeyboardButton("⏭ Не хочу быть ведущим", callback_data="pass_turn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎨 <a href='tg://user?id={user.id}'>{user.full_name}</a> начинает объяснять слово!",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

    game_state.message_id = msg.message_id


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    user = query.from_user

    if chat_id not in game_states:
        await query.answer("❌ Игра не начата. Используйте /play", show_alert=True)
        return

    game_state = game_states[chat_id]

    if user.id != game_state.current_leader:
        await query.answer("⛔ Только ведущий может использовать кнопки!", show_alert=True)
        return

    if query.data == "show_word":
        await query.answer(f"🔐 Ваше слово: {game_state.current_word}", show_alert=True)
    elif query.data == "change_word":
        new_index = random.randint(0, len(WORDS) - 1)
        while new_index == game_state.current_word_index:
            new_index = random.randint(0, len(WORDS) - 1)

        game_state.current_word = WORDS[new_index]
        game_state.current_word_index = new_index

        await query.answer(f"🔄 Слово изменено на: {game_state.current_word}", show_alert=True)
    elif query.data == "pass_turn":
        game_state.current_leader = None
        game_state.current_word = None
        game_state.current_word_index = None

        await context.bot.delete_message(chat_id=chat_id, message_id=game_state.message_id)

        await query.answer("✅ Вы передали ход следующему участнику.", show_alert=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏭ <a href='tg://user?id={user.id}'>{user.full_name}</a> передал ход.\n"
                 "🎭 Следующий участник может начать с /play",
            parse_mode='HTML'
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик сообщений с проверкой угадывания слова"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    message_text = update.message.text

    if chat_id not in game_states:
        return

    game_state = game_states[chat_id]

    if game_state.current_leader is not None and not game_state.guessed:
        normalized_input = re.sub(r'[^\w\s]', '', message_text).strip().lower()
        normalized_word = re.sub(r'[^\w\s]', '', game_state.current_word).strip().lower()

        if normalized_input == normalized_word:
            game_state.guessed = True

            if game_state.message_id:
                await context.bot.delete_message(chat_id=chat_id, message_id=game_state.message_id)

            # Выбираем случайную фразу для поздравления
            wow_phrase = random.choice(WOW_PHRASES)

            await update.message.reply_text(
                f"🎉🎉🎉 <a href='tg://user?id={user.id}'>{user.full_name}</a> угадал(а) слово "
                f"«{game_state.current_word}»!\n\n"
                f"🌟 {wow_phrase}\n\n"
                f"🏆 Теперь <a href='tg://user?id={user.id}'>{user.full_name}</a> становится ведущим!",
                parse_mode='HTML'
            )

            game_state.current_leader = user.id
            game_state.guessed = False
            word_index = random.randint(0, len(WORDS) - 1)
            game_state.current_word = WORDS[word_index]
            game_state.current_word_index = word_index

            keyboard = [
                [InlineKeyboardButton("🔎 Показать слово", callback_data="show_word")],
                [InlineKeyboardButton("🔄 Сменить слово", callback_data="change_word")],
                [InlineKeyboardButton("⏭ Не хочу быть ведущим", callback_data="pass_turn")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎨 <a href='tg://user?id={user.id}'>{user.full_name}</a> начинает объяснять слово!",
                parse_mode='HTML',
                reply_markup=reply_markup
            )

            game_state.message_id = msg.message_id
            return

    if game_state.current_leader == user.id:
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❗❗❗ <a href='tg://user?id={user.id}'>{user.full_name}</a>:\n"
                 f"{message_text}",
            parse_mode='HTML'
        )


def main() -> None:
    """Запуск бота"""
    # Убираем меню бота, устанавливая пустой список команд
    application = Application.builder() \
        .token("7734707595:AAExtqroKgYL7rtCKAZPb8sBhFPaxRoAB9A") \
        .post_init(lambda app: app.bot.set_my_commands([])) \
        .build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == '__main__':
    main()