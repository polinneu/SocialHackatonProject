from gigachat import GigaChat
from openai import OpenAI
import requests
import base64
from gigachat.models import Chat, Messages, MessagesRole
from bs4 import BeautifulSoup
from typing import List
import asyncio
from asyncio import Lock

import asyncio

async def run_gigachat(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

KEY = "MDE5OTYxOWUtMmJlYy03ZWEzLTk0YTktNGE5ZjdkMjVjYTE4OjExOWNiNTk2LTY4OGUtNGJkMS05YTFiLWQwYTkyMDUzZDI3YQ=="
TELEGRAM_BOT_TOKEN = "8378449608:AAF4XLIdbWzB439JabmDTSBh92emMPcF44I"

STYLE_PROMPT = ""


def _resolve_style_prompt(style_prompt: str = "") -> str:
    return style_prompt or STYLE_PROMPT


def ask_ai(question: str) -> str:
    with GigaChat(credentials=KEY, verify_ssl_certs=False) as giga:
        response = giga.chat(question)
        return response.choices[0].message.content


def get_img(prompt: str):
    try:
        print(f"🔍 Начинаем генерацию изображения с промптом: {prompt[:100]}...")

        giga = GigaChat(
            credentials=KEY,
            verify_ssl_certs=False,
            timeout=120.0,
        )
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content="Ты — фотограф-волонтер. Создавай качественные изображения для благотворительной организации."
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=prompt
                ),
            ],
            function_call="auto",
        )

        response = giga.chat(payload)
        response_text = response.choices[0].message.content
        print(f"📄 Ответ от GigaChat: {response_text[:200]}...")
        soup = BeautifulSoup(response_text, "html.parser")
        img_tag = soup.find('img')

        if not img_tag:
            raise Exception("GigaChat не вернул изображение в ответе")

        file_id = img_tag.get("src")
        if not file_id:
            raise Exception("Не найден src у тега img")

        print(f"📷 Найден file_id: {file_id}")
        image = giga.get_image(file_id)
        print("✅ Изображение успешно получено")
        return image

    except Exception as e:
        print(f"❌ Ошибка в get_img: {str(e)}")
        raise Exception(f"Ошибка генерации изображения: {str(e)}")


def give_img(image, CHAT_ID):
    image_bytes = base64.b64decode(image.content)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {
        "photo": ("image.jpg", image_bytes)
    }
    data = {
        "chat_id": CHAT_ID,
        "caption": "Вот результат Вашего запроса!"
    }
    requests.post(url, data=data, files=files)


def get_update(base_prompt: str, user_update: str):
    updated_prompt = (
        f"Ранее изображение создавалось по описанию: \"{base_prompt}\".\n"
        f"Теперь доработай/пересоздай изображение, учитывая такие правки пользователя: "
        f"\"{user_update}\".\n"
    )
    return get_img(updated_prompt)


def generate_post_from_free_text(user_text: str, style_prompt: str = "", org_info: str = "",
                                 projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    prompt = f"""
Ты — редактор благотворительной организации и пишешь тексты для постов в социальных сетях.

Задача:
На основе мыслей пользователя напиши готовый, связный текст поста на русском языке.

Требования к тексту:
- Пиши простым, понятным языком.
- Сохрани смысл и интонацию пользователя.
- Убери лишние повторы, "мусор" и неструктурированные фрагменты.
- Не придумывай от себя факты, которых пользователь не писал.
- Можно чуть-чуть улучшить формулировки, чтобы текст читался легко.
- Не добавляй никаких пояснений от себя, выведи только текст поста.
{context_info}

Мысли пользователя:
\"\"\"{user_text}\"\"\"
"""
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""
{use_style}

Теперь на основе этого стиля напиши новый текст поста."""
    return ask_ai(prompt)


def update_post_from_free_text(original_post: str, user_feedback: str, style_prompt: str = "", org_info: str = "",
                               projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    prompt = f"""
Ты — редактор благотворительной организации и дорабатываешь уже готовый текст поста
на основе комментариев пользователя.

Вот исходный текст поста:
\"\"\"{original_post}\"\"\"

Вот комментарии и правки пользователя:
\"\"\"{user_feedback}\"\"\"
{context_info}

Требования к результату:
- Внеси правки в текст, опираясь на комментарии пользователя.
- Если пользователь просит что-то убрать — убери.
- Если просит что-то добавить — добавь, формулируя понятно и аккуратно.
- Сохрани общий смысл и стиль исходного текста, если явно не просят изменить.
- Не придумывай новые факты, которых нет в исходном тексте или в комментариях пользователя.
- Не добавляй никаких пояснений, выведи только финальный текст поста.

Исправь текст поста.
"""
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""
{use_style}

Теперь на основе этого стиля напиши новый текст поста."""

    return ask_ai(prompt)


def _post_from_structured_form(form_data: str, style_prompt: str = "", org_info: str = "",
                                       projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    prompt = f"""
Ты — редактор благотворительной организации и пишешь короткие анонсы событий
для социальных сетей.

У тебя есть ответы пользователя на простую анкету о событии.
На основе этих данных составь один связный текст поста на русском языке.

Вот данные (вопросы и ответы, какие-то ответы могут отсутствовать):
\"\"\"{form_data}\"\"\"
{context_info}

Требования к тексту:
- Сделай понятный и живой анонс события.
- По возможности укажи:
  • что за событие,
  • когда и во сколько оно будет,
  • где оно будет проходить,
  • для кого оно (подопечные, волонтёры, доноры и т.п.),
  • важные детали: регистрация, что взять с собой, контактный телефон — только если это есть в данных.
- Не придумывай от себя факты, которых нет в ответах.
- Можно немного сгладить формулировки, чтобы текст читался естественно.
- Не используй списки и разметку, напиши обычный текст (один или несколько абзацев).
- Не добавляй никаких пояснений, выведи только текст поста.

Составь текст поста-анонса на основе этих данных.
"""
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""
{use_style}

Теперь на основе этого стиля напиши новый текст поста."""

    return ask_ai(prompt)


def build_style_prompt(example_posts: List[str]) -> str:
    examples_text = "\n\n---\n\n".join(example_posts)
    style_prompt = f"""
Ты — копирайтер благотворительной организации.

Ниже приведены несколько примеров постов. Проанализируй их и запомни стиль организации:
- тон (насколько он официальный или дружелюбный),
- длина и ритм предложений,
- использование эмодзи,
- типичные обращения к читателю,
- структура (лид, основной текст, призыв к действию),
- любимые фразы и формулировки.

Примеры постов организации:
\"\"\"{examples_text}\"\"\"

С этого момента, когда я попрошу тебя написать новый текст поста,
ты обязан максимально точно придерживаться этого стиля:
- используй тот же тон и уровень формальности;
- по возможности используй похожие фразы и конструкции;
- не копируй примеры дословно, а создавай новый текст;
- помни, что это тексты НКО, они должны быть этичными и понятными.

"""
    return style_prompt.strip()


def generate_post_with_style(user_request: str, style_prompt: str = "", org_info: str = "",
                             projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    use_style = _resolve_style_prompt(style_prompt)
    full_prompt = f"""
{use_style}
{context_info}

Теперь на основе этого стиля напиши новый текст поста.

Запрос пользователя:
\"\"\"{user_request}\"\"\"

Требования к результату:
- строго соблюдай стиль, который ты выучил по примерам;
- не добавляй факты, которых пользователь не просил;
- не объясняй свои действия;
- выведи только готовый текст поста.
"""
    return ask_ai(full_prompt)


def edit_text(user_text: str, style_prompt: str = "", org_info: str = "", projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    prompt = f'''
Ты — добрый редактор текста для благотворительной организации.
Твоя задача — помочь человеку сформулировать текст понятнее и аккуратнее.

Пользователь прислал текст (может быть длинный или короткий):
\"\"\"{user_text}\"\"\"
{context_info}

Сделай две вещи:

1) Исправь текст:
- поправь орфографию и пунктуацию;
- сделай формулировки более простыми и понятными;
- не меняй смысл;
- не добавляй новые факты от себя.

2) Дай короткий отчёт простым человеческим языком, без сложной лингвистики.
Примеры формулировок:
- "Исправил орфографию в нескольких словах."
- "Разделил одно длинное предложение на два, чтобы легче читалось."
- "Заменил слишком официальные выражения на более простые."
- "Предлагаю добавить благодарность волонтёрам в конце."

Формат ответа:
Сначала выведи ИСПРАВЛЕННЫЙ ТЕКСТ целиком.
Потом на отдельной строке выведи три дефиса:
---
После этого выведи КРАТКИЙ ОТЧЁТ.

Не объясняй формат, просто следуй ему.
'''
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""
{use_style}

Теперь на основе этого стиля."""
    
    try:
        answer = ask_ai(prompt)
        return answer
    except Exception as e:
        return f"❌ Ошибка при редактировании текста: {str(e)}\n\nИсходный текст:\n{user_text}"


def make_plan(qa_text: str, style_prompt: str = "", org_info: str = "", projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    prompt = f'''
Ты помогаешь благотворительной организации составить простой план постов для соцсетей.

У тебя есть ответы человека на несколько вопросов (про период, частоту постов и деятельность организации).
Вот эти ответы:
\"\"\"{qa_text}\"\"\"
{context_info}

На основе этих ответов составь понятный текстовый контент-план.

Требования:
- Учитывай период (например, 1 неделя, 2 недели, месяц).
- Учитывай, как часто человек готов постить (например, 2-3 раза в неделю).
- Учитывай специфику деятельности организации (описание из ответов).

Формат результата — простая текстовая "таблица" по неделям и дням, например:

Неделя 1
Пн — История подопечного
Ср — Пост "как мы помогаем" (отчёт за неделю)
Пт — Поиск волонтёров на ближайшую акцию
Неделя 2
Пн — "Спасибо донору" (рассказ о партнёре)
Ср — Полезная памятка (что делать, если…)
Пт — Бекстейдж: как работает команда

Правила:
- Пиши на русском.
- Не используй сложную терминологию.
- Не объясняй, что ты делаешь, просто выведи готовый план.
- Если период короче (например, 1 неделя), делай план только на этот период.
- Если пользователь указал частоту, постарайся примерно её соблюдать.
'''
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""

Также по возможности соблюдай следующий стиль текстов:
{use_style}
"""
    answer = ask_ai(prompt)
    return answer


def update_plan(old_plan: str, user_feedback: str, qa_text: str | None = None, style_prompt: str = "",
                org_info: str = "", projects_info: str = "") -> str:
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    extra_info = ""
    if qa_text is not None:
        extra_info = f'''
Дополнительная информация об организации и предпочтениях:
\"\"\"{qa_text}\"\"\"
'''

    prompt = f'''
Ты помогаешь благотворительной организации исправить план постов для соцсетей.

Есть исходный план:
\"\"\"{old_plan}\"\"\"

Есть комментарии и правки пользователя:
\"\"\"{user_feedback}\"\"\"
{extra_info}
{context_info}
Твоя задача — скорректировать план с учётом правок пользователя.

Правила:
- Сохрани общий формат: по неделям и дням, в стиле:
  Неделя 1
  Пн — ...
  Ср — ...
  Пт — ...
- Если пользователь просит что-то убрать — убери.
- Если просит добавить темы/перенести публикации — сделай это аккуратно.
- Старайся сохранять частоту постов и период, который был в исходном плане (если явно не просят изменить).
- Не придумывай от себя лишние детали про организацию, если их нет в исходных данных.
- Пиши простым и понятным языком.

Формат ответа:
1) Сначала выведи ОБНОВЛЁННЫЙ ПЛАН целиком в текстовом виде.
2) Затем на отдельной строке выведи три дефиса:
---
3) После этого выведи короткое объяснение по-человечески, что ты изменил.
   Примеры формулировок:
   - "Перенёс пост с благодарностью волонтёрам на следующую неделю."
   - "Убрал один пост в выходные, как вы просили."
   - "Добавил больше историй подопечных."

Не объясняй формат, просто следуй ему.
'''
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""

Также по возможности соблюдай следующий стиль текстов:
{use_style}
"""
    answer = ask_ai(prompt)
    return answer


def generate_post_from_plan_item(plan_text: str, item_text: str, style_prompt: str = "", org_info: str = "",
                                 projects_info: str = "") -> str:
    """
    Пост по конкретному пункту контент-плана.
    """
    context_info = ""
    if org_info:
        context_info += f"\n\nКонтекст организации:\n{org_info}"
    if projects_info:
        context_info += f"\n\nПроекты организации:\n{projects_info}"

    prompt = f"""
Ты помогаешь благотворительной организации написать пост по готовому контент-плану.

Вот фрагмент контент-плана:
\"\"\"{plan_text}\"\"\"

Нужно написать текст поста для следующего пункта плана:
\"\"\"{item_text}\"\"\"
{context_info}

Требования:
- Пиши простым понятным языком.
- Сделай связный пост для соцсетей.
- Можно добавить лёгкий призыв к действию (прийти, поддержать, поделиться), если это уместно.
- Не добавляй новые факты, которых нет в описании.
"""
    use_style = _resolve_style_prompt(style_prompt)
    if use_style:
        prompt += f"""

Обязательно соблюдай стиль организации:
{use_style}
"""
    return ask_ai(prompt)


import logging
import sqlite3
import random
import string
import re
from datetime import datetime
import asyncio

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

(
    CHOOSING,
    ENTER_ORG_CODE,
    ENTER_ORG_NAME,
    ENTER_ORG_DESCRIPTION,
    CONFIRM_RESET,
    PROJECT_CHOICE,
    ENTER_PROJECT_NAME,
    ENTER_PROJECT_DESCRIPTION,
    SELECT_PROJECT,
    PROJECT_ACTIONS,
    EDIT_PROJECT_NAME,
    EDIT_PROJECT_DESCRIPTION,
    CONFIRM_DELETE_PROJECT,
    POST_MODE_CHOICE,
    POST_FREE_INPUT,
    POST_STRUCT_ASK,
    POST_STRUCT_GET_ANSWER,
    STYLE_EXAMPLES_COLLECT,
    STYLE_NEW_POST_REQUEST,
    TEXT_EDITOR_INPUT,
    CONTENT_PLAN_PERIOD,
    CONTENT_PLAN_FREQUENCY,
    CONTENT_PLAN_DESCRIPTION,
    CONTENT_PLAN_RESULT_ACTION,
    IMAGE_MAIN_MODE_CHOICE,
    IMAGE_PROMPT_INPUT,
    IMAGE_EDIT_PROMPT,
    ORG_PROFILE_MENU,
    ORG_PROFILE_EDIT_NAME,
    ORG_PROFILE_EDIT_DESCRIPTION,
    ETHICAL_REPLACE_CONFIRM,
    POST_TEXT_IMAGE_OFFER,
) = range(32) 

BOT_TOKEN = "8378449608:AAF4XLIdbWzB439JabmDTSBh92emMPcF44I"

ETHICAL_REPLACEMENTS = {
    "бомж": "человек без дома",
    "бомжей": "людей без дома",
    "бомжам": "людям без дома",
    "инвалид": "человек с инвалидностью",
    "инвалиды": "люди с инвалидностью",
    "инвалидов": "людей с инвалидностью",
    "алкаш": "человек с зависимостью от алкоголя",
    "алкаши": "люди с зависимостью от алкоголя",
    "алкашей": "людей с зависимостью от алкоголя",
    "наркоман": "человек с зависимостью от наркотиков",
    "наркоманы": "люди с зависимостью от наркотиков",
}

STRUCT_QUESTIONS = [
    ("event", "Что за событие?"),
    ("datetime", "Когда и во сколько?"),
    ("place", "Где будет проходить?"),
    ("audience", "Для кого это? (подопечные, волонтёры, доноры и т.п.)"),
    ("extra", "Есть ли что-то важное: регистрация, что взять с собой, контактный телефон?"),
]

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    style_prompt TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute("PRAGMA table_info(organizations)")
            columns = [row[1] for row in cursor.fetchall()]
            if "style_prompt" not in columns:
                cursor.execute("ALTER TABLE organizations ADD COLUMN style_prompt TEXT")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    org_id INTEGER,
                    FOREIGN KEY (org_id) REFERENCES organizations(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    org_id INTEGER NOT NULL,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (org_id) REFERENCES organizations(id),
                    FOREIGN KEY (created_by) REFERENCES users(telegram_id)
                )
            ''')
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
            if cursor.fetchone():
                cursor.execute('''
                    INSERT INTO projects_new (id, name, description, org_id, created_by, created_at)
                    SELECT id, name, description, org_id, created_by, created_at FROM projects
                ''')
                cursor.execute("DROP TABLE projects")

            cursor.execute("ALTER TABLE projects_new RENAME TO projects")

            conn.commit()

    def get_connection(self):
        return sqlite3.connect(self.db_path)


class OrganizationManager:
    def __init__(self, db: Database):
        self.db = db

    def create_organization(self, name: str, description: str = "", style_prompt: str = "") -> tuple:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO organizations (code, name, description, style_prompt) VALUES (?, ?, ?, ?)",
                    (code, name, description, style_prompt)
                )
                conn.commit()
                return True, code
            except sqlite3.IntegrityError:
                return self.create_organization(name, description, style_prompt)

    def get_organization_by_code(self, code: str):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, code, name, description, style_prompt FROM organizations WHERE code = ?",
                (code,)
            )
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'code': result[1],
                    'name': result[2],
                    'description': result[3],
                    'style_prompt': result[4],
                }
            return None

    def update_organization(self, org_id: int, name: str = None, description: str = None,
                            style_prompt: str = None) -> bool:
        if not any([name is not None, description is not None, style_prompt is not None]):
            return False

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            params = []

            if name is not None:
                fields.append("name = ?")
                params.append(name)
            if description is not None:
                fields.append("description = ?")
                params.append(description)
            if style_prompt is not None:
                fields.append("style_prompt = ?")
                params.append(style_prompt)

            params.append(org_id)
            query = "UPDATE organizations SET " + ", ".join(fields) + " WHERE id = ?"
            cursor.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount > 0

    def get_org_style(self, org_id: int) -> str:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT style_prompt FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return ""

    def set_org_style(self, org_id: int, style_prompt: str) -> bool:
        return self.update_organization(org_id, style_prompt=style_prompt)

    def delete_org_style(self, org_id: int) -> bool:
        return self.update_organization(org_id, style_prompt="")


class ProjectManager:
    def __init__(self, db: Database):
        self.db = db

    def create_project(self, name: str, description: str, org_id: int, created_by: int) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO projects (name, description, org_id, created_by) VALUES (?, ?, ?, ?)",
                    (name, description, org_id, created_by)
                )
                conn.commit()
                return True
            except Exception as e:
                print(f"Ошибка при создании проекта: {e}")
                return False

    def get_organization_projects(self, org_id: int):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.name, p.description, p.created_at, p.updated_at,
                       u.full_name as creator_name
                FROM projects p
                LEFT JOIN users u ON p.created_by = u.telegram_id
                WHERE p.org_id = ?
                ORDER BY p.created_at DESC
            ''', (org_id,))
            results = cursor.fetchall()
            projects = []
            for result in results:
                projects.append({
                    'id': result[0],
                    'name': result[1],
                    'description': result[2],
                    'created_at': result[3],
                    'updated_at': result[4],
                    'creator_name': result[5]
                })
            return projects

    def get_project_by_id(self, project_id: int):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.name, p.description, p.org_id, p.created_by, p.created_at, p.updated_at,
                       u.full_name as creator_name, o.name as org_name
                FROM projects p
                LEFT JOIN users u ON p.created_by = u.telegram_id
                LEFT JOIN organizations o ON p.org_id = o.id
                WHERE p.id = ?
            ''', (project_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'name': result[1],
                    'description': result[2],
                    'org_id': result[3],
                    'created_by': result[4],
                    'created_at': result[5],
                    'updated_at': result[6],
                    'creator_name': result[7],
                    'org_name': result[8]
                }
            return None

    def update_project(self, project_id: int, name: str = None, description: str = None) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if name and description:
                    cursor.execute(
                        "UPDATE projects SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, description, project_id)
                    )
                elif name:
                    cursor.execute(
                        "UPDATE projects SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, project_id)
                    )
                elif description:
                    cursor.execute(
                        "UPDATE projects SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (description, project_id)
                    )
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Ошибка при обновлении проекта: {e}")
                return False

    def delete_project(self, project_id: int) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Ошибка при удалении проекта: {e}")
                return False


class UserManager:
    def __init__(self, db: Database):
        self.db = db

    def register_user(self, telegram_id: int, username: str, full_name: str, org_code: str) -> tuple:
        org_manager = OrganizationManager(self.db)
        organization = org_manager.get_organization_by_code(org_code)

        if not organization:
            return False, "❌ Организация с таким кодом не найдена"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (telegram_id, username, full_name, org_id) VALUES (?, ?, ?, ?)",
                    (telegram_id, username, full_name, organization['id'])
                )
                conn.commit()
                return True, f"✅ Вы успешно зарегистрированы в организации: {organization['name']}"
            except sqlite3.IntegrityError:
                return False, "❌ Пользователь уже зарегистрирован"

    def get_user(self, telegram_id: int):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.telegram_id, u.username, u.full_name, u.org_id, 
                       o.name as org_name, o.code as org_code, o.description as org_description
                FROM users u 
                LEFT JOIN organizations o ON u.org_id = o.id 
                WHERE u.telegram_id = ?
            ''', (telegram_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'telegram_id': result[0],
                    'username': result[1],
                    'full_name': result[2],
                    'org_id': result[3],
                    'org_name': result[4],
                    'org_code': result[5],
                    'org_description': result[6]
                }
            return None

    def is_user_registered(self, telegram_id: int) -> bool:
        return self.get_user(telegram_id) is not None

    def delete_user(self, telegram_id: int) -> bool:
        """Удалить пользователя из базы данных"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            return cursor.rowcount > 0


class RegistrationBot:
    def __init__(self, token: str):
        self.token = token
        self.db = Database()
        self.org_manager = OrganizationManager(self.db)
        self.user_manager = UserManager(self.db)
        self.project_manager = ProjectManager(self.db)
        self.user_image_locks: dict[int, asyncio.Lock] = {}
    def _get_user_image_lock(self, user_id: int) -> asyncio.Lock:
        lock = self.user_image_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self.user_image_locks[user_id] = lock
        return lock

    def get_style_prompt_for_user(self, telegram_id: int) -> str:
        user_info = self.user_manager.get_user(telegram_id)
        if not user_info or not user_info.get('org_id'):
            return ""
        try:
            return self.org_manager.get_org_style(user_info['org_id']) or ""
        except Exception:
            return ""

    def get_org_info_for_user(self, telegram_id: int) -> str:
        user_info = self.user_manager.get_user(telegram_id)
        if not user_info:
            return ""

        org_info = f"Организация: {user_info['org_name']}"
        if user_info.get('org_description'):
            org_info += f"\nОписание: {user_info['org_description']}"

        return org_info

    def get_projects_info_for_user(self, telegram_id: int) -> str:
        user_info = self.user_manager.get_user(telegram_id)
        if not user_info:
            return ""

        projects = self.project_manager.get_organization_projects(user_info['org_id'])
        if not projects:
            return ""

        projects_info = "Проекты организации:\n"
        for i, project in enumerate(projects, 1):
            projects_info += f"{i}. {project['name']}"
            if project.get('description'):
                projects_info += f" - {project['description']}"
            projects_info += "\n"

        return projects_info

    def check_ethical_issues(self, text: str):
        issues = []
        lowered = text.lower()
        for bad, good in ETHICAL_REPLACEMENTS.items():
            pattern = r"\b" + re.escape(bad) + r"\b"
            if re.search(pattern, lowered):
                issues.append({"word": bad, "replacement": good})
        return issues

    def apply_ethical_replacements(self, text: str, issues):
        new_text = text
        for issue in issues:
            bad = issue["word"]
            good = issue["replacement"]
            pattern = re.compile(r"\b" + re.escape(bad) + r"\b", flags=re.IGNORECASE)

            def repl(match):
                original = match.group(0)
                if original.isupper():
                    return good.upper()
                elif original[0].isupper():
                    return good.capitalize()
                else:
                    return good

            new_text = pattern.sub(repl, new_text)
        return new_text

    async def send_text_with_ethical_check(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            text_to_check: str,
            followup_type: str | None = None
    ):

        issues = self.check_ethical_issues(text_to_check)
        user_info = self.user_manager.get_user(update.effective_user.id)

        if not issues:
            await update.message.reply_text(text_to_check)
            if followup_type == "post":
                await self.ask_image_for_post(update, context)
                return POST_TEXT_IMAGE_OFFER
            else:
                if user_info:
                    await self.show_registered_menu(update, user_info)
                return CHOOSING

        context.user_data["pending_text"] = text_to_check
        context.user_data["pending_ethical_issues"] = issues
        context.user_data["pending_followup_type"] = followup_type

        await update.message.reply_text(text_to_check)

        parts = [f"«{i['word']}» → «{i['replacement']}»" for i in issues]
        replacements_preview = "; ".join(parts)

        keyboard = [["✅ Заменить выражения", "❌ Оставить как есть"], ["🔙 В главное меню"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "Я заметил в тексте формулировки, которые могут звучать стигматизирующе.\n"
            f"Обычно НКО используют более уважительные выражения, например: {replacements_preview}.\n"
            "Заменить автоматически?",
            reply_markup=reply_markup
        )

        return ETHICAL_REPLACE_CONFIRM

    async def ask_image_for_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            ["🖼 Да, хочу картинку", "🙅‍♀️ Нет, текст достаточно"],
            ["🔙 В главное меню"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Хотите картинку к этому посту?",
            reply_markup=reply_markup
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        if user_info:
            await self.show_registered_menu(update, user_info)
            return CHOOSING
        else:
            await self.show_unregistered_menu(update, user)
            return CHOOSING

    async def show_registered_menu(self, update: Update, user_info):
        keyboard = [
            ["✏️ Текст для поста", "🖼 Картинка к посту"],
            ["🪄 Исправить мой текст", "📅 Сделать контент-план"],
            ["🧩 О нас (НКО-профиль)"],
            ["📋 Проекты", "👤 Профиль"],
            ["🔄 Сбросить регистрацию", "🏢 Создать новую организацию"],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"👋 С возвращением, {user_info['full_name']}!\n"
            f"🏢 Организация: {user_info['org_name']}\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )

    async def show_unregistered_menu(self, update: Update, user):
        keyboard = [["📝 Зарегистрироваться", "🏢 Создать организацию"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            "Вы еще не зарегистрированы в системе.\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )

    async def handle_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        print(f"Обрабатываем кнопку: {text}")

        if user_info:
            if text == "✏️ Текст для поста":
                return await self.start_post_flow(update, context)

            elif text == "🖼 Картинка к посту":
                context.user_data["image_base_from_post"] = False
                return await self.start_image_flow(update, context)

            elif text == "🪄 Исправить мой текст":
                await update.message.reply_text(
                    "Пришлите текст, который нужно аккуратно отредактировать.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return TEXT_EDITOR_INPUT

            elif text == "📅 Сделать контент-план":
                return await self.start_content_plan(update, context)

            elif text == "🧩 О нас (НКО-профиль)":
                return await self.show_org_profile(update, context)

            elif text == "👤 Профиль":
                await self.profile(update, context)
                return CHOOSING

            elif text == "📋 Проекты":
                return await self.show_projects_menu(update, context, user_info)

            elif text == "🔄 Сбросить регистрацию":
                keyboard = [["✅ Да, сбросить", "❌ Нет, отмена"]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    "⚠️ Вы уверены, что хотите сбросить свою регистрацию?\n\n"
                    "Это удалит вашу привязку к организации, и вам придется регистрироваться заново.",
                    reply_markup=reply_markup
                )
                return CONFIRM_RESET

            elif text == "🏢 Создать новую организацию":
                await update.message.reply_text(
                    "🏢 Создание новой организации\n\n"
                    "Введите название вашей организации:",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ENTER_ORG_NAME

        else:
            if text == "📝 Зарегистрироваться":
                await update.message.reply_text(
                    "🔐 Регистрация\n\n"
                    "Пожалуйста, введите код вашей организации:",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ENTER_ORG_CODE

            elif text == "🏢 Создать организацию":
                await update.message.reply_text(
                    "🏢 Создание новой организации\n\n"
                    "Введите название вашей организации:",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ENTER_ORG_NAME

        await update.message.reply_text("Пожалуйста, используйте кнопки меню")
        return CHOOSING

    async def start_post_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            ["🧠 Свободная форма", "📋 По шагам (очень просто)"],
            ["✨ По примерам постов"],
            ["🔙 В главное меню"],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Как удобнее сделать текст для поста?",
            reply_markup=reply_markup
        )
        return POST_MODE_CHOICE

    async def handle_post_mode_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "🧠 Свободная форма":
            await update.message.reply_text(
                "Напишите свои мысли или черновик текста. Я помогу превратить его в готовый пост.",
                reply_markup=ReplyKeyboardRemove()
            )
            return POST_FREE_INPUT

        elif text == "📋 По шагам (очень просто)":
            context.user_data["structured_form_data"] = {}
            context.user_data["structured_question_index"] = 0
            return await self.ask_next_struct_question(update, context)

        elif text == "✨ По примерам постов":
            context.user_data["style_examples"] = []
            keyboard = [["✅ Готово", "🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Пришлите 2–3 своих поста (можно несколькими сообщениями).\n"
                "Когда закончите, нажмите «✅ Готово».",
                reply_markup=reply_markup
            )
            return STYLE_EXAMPLES_COLLECT

        elif text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        else:
            await update.message.reply_text("Пожалуйста, выберите один из вариантов меню.")
            return POST_MODE_CHOICE

    async def ask_next_struct_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        idx = context.user_data.get("structured_question_index", 0)
        struct_data = context.user_data.get("structured_form_data", {})
    
        if idx >= len(STRUCT_QUESTIONS):
            # Показываем статус генерации
            status_msg = await update.message.reply_text("🔄 Генерирую текст поста...")
            
            try:
                lines = []
                for key, question in STRUCT_QUESTIONS:
                    answer = struct_data.get(key)
                    if answer:
                        lines.append(f"{question} {answer}")
                qa_text = "\n".join(lines)
    
                user = update.effective_user
                style_prompt = self.get_style_prompt_for_user(user.id)
                org_info = self.get_org_info_for_user(user.id)
                projects_info = self.get_projects_info_for_user(user.id)
    
                post_text = await run_gigachat(
                    _post_from_structured_form,
                    qa_text,
                    style_prompt=style_prompt,
                    org_info=org_info,
                    projects_info=projects_info,
                )
    
                context.user_data["last_post_text"] = post_text
                context.user_data["last_post_source"] = "structured"
    
                context.user_data.pop("structured_form_data", None)
                context.user_data.pop("structured_question_index", None)
    
                await status_msg.delete()
                return await self.send_text_with_ethical_check(update, context, post_text, followup_type="post")
            
            except Exception as e:
                await status_msg.delete()
                await update.message.reply_text(f"❌ Ошибка при генерации поста: {str(e)}")
                return await self.start(update, context)

        _, question = STRUCT_QUESTIONS[idx]
        keyboard = [["✍️ Ответить", "⏭ Пропустить"], ["🔙 В главное меню"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(question, reply_markup=reply_markup)
        return POST_STRUCT_ASK

    async def handle_structured_form_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "✍️ Ответить":
            await update.message.reply_text(
                "Напишите ваш ответ:",
                reply_markup=ReplyKeyboardRemove()
            )
            return POST_STRUCT_GET_ANSWER

        elif text == "⏭ Пропустить":
            idx = context.user_data.get("structured_question_index", 0)
            struct_data = context.user_data.get("structured_form_data", {})
            key, _ = STRUCT_QUESTIONS[idx]
            struct_data[key] = ""
            context.user_data["structured_form_data"] = struct_data
            context.user_data["structured_question_index"] = idx + 1
            return await self.ask_next_struct_question(update, context)
        elif text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки «Ответить» или «Пропустить».")
            return POST_STRUCT_ASK

    async def handle_structured_form_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        struct_data = context.user_data.get("structured_form_data", {})
        idx = context.user_data.get("structured_question_index", 0)
    
        if idx >= len(STRUCT_QUESTIONS):
            return await self.start(update, context)
    
        key, _ = STRUCT_QUESTIONS[idx]
        struct_data[key] = text
        context.user_data["structured_form_data"] = struct_data
        context.user_data["structured_question_index"] = idx + 1
    
        # Показываем статус генерации
        status_msg = await update.message.reply_text("🔄 Генерирую текст поста...")
    
        try:
            # Получаем данные для генерации
            idx = context.user_data.get("structured_question_index", 0)
            if idx >= len(STRUCT_QUESTIONS):
                lines = []
                for key, question in STRUCT_QUESTIONS:
                    answer = struct_data.get(key)
                    if answer:
                        lines.append(f"{question} {answer}")
                qa_text = "\n".join(lines)
    
                user = update.effective_user
                style_prompt = self.get_style_prompt_for_user(user.id)
                org_info = self.get_org_info_for_user(user.id)
                projects_info = self.get_projects_info_for_user(user.id)
    
                # Генерируем пост асинхронно
                post_text = await run_gigachat(
                    _post_from_structured_form,
                    qa_text,
                    style_prompt=style_prompt,
                    org_info=org_info,
                    projects_info=projects_info,
                )
    
                context.user_data["last_post_text"] = post_text
                context.user_data["last_post_source"] = "structured"
    
                context.user_data.pop("structured_form_data", None)
                context.user_data.pop("structured_question_index", None)
    
                # Удаляем статус и отправляем результат
                await status_msg.delete()
                return await self.send_text_with_ethical_check(update, context, post_text, followup_type="post")
            else:
                await status_msg.delete()
                return await self.ask_next_struct_question(update, context)
    
        except Exception as e:
            await status_msg.delete()
            await update.message.reply_text(f"❌ Ошибка при генерации поста: {str(e)}")
            return await self.start(update, context)

    async def handle_text_editor_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_text = update.message.text
        
        # Показываем статус
        status_msg = await update.message.reply_text("🔄 Редактирую текст...")
    
        try:
            style_prompt = self.get_style_prompt_for_user(user.id)
            org_info = self.get_org_info_for_user(user.id)
            projects_info = self.get_projects_info_for_user(user.id)
    
            # Редактируем текст асинхронно
            edited = await run_gigachat(
                edit_text,
                user_text,
                style_prompt=style_prompt,
                org_info=org_info,
                projects_info=projects_info,
            )
            
            await status_msg.delete()
            return await self.send_text_with_ethical_check(update, context, edited, followup_type="edit")
        
        except Exception as e:
            await status_msg.delete()
            await update.message.reply_text(f"❌ Ошибка при редактировании текста: {str(e)}")
            return await self.start(update, context)

    async def handle_post_free_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_text = update.message.text
        style_prompt = self.get_style_prompt_for_user(user.id)
        org_info = self.get_org_info_for_user(user.id)
        projects_info = self.get_projects_info_for_user(user.id)

        from_plan = context.user_data.pop("from_plan", False)

        if from_plan:
            plan_text = context.user_data.get("last_plan_text", "")
            generated = await run_gigachat(
                generate_post_from_plan_item,
                plan_text, user_text,
                style_prompt=style_prompt,
                org_info=org_info,
                projects_info=projects_info,
            )
            context.user_data["last_post_source"] = "from_plan"
        else:
            generated = await run_gigachat(
                generate_post_from_free_text,
                user_text,
                style_prompt=style_prompt,
                org_info=org_info,
                projects_info=projects_info,
            )
            context.user_data["last_post_source"] = "free"

        context.user_data["last_post_text"] = generated
        context.user_data["last_post_original_input"] = user_text

        return await self.send_text_with_ethical_check(update, context, generated, followup_type="post")

    async def handle_post_text_image_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "🖼 Да, хочу картинку":
            context.user_data["image_base_from_post"] = True
            return await self.start_image_flow(update, context)
        elif text == "🙅‍♀️ Нет, текст достаточно":
            await update.message.reply_text(
                "Хорошо! Если понадобится, вы всегда можете сгенерировать картинку из главного меню.",
                reply_markup=ReplyKeyboardRemove()
            )
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING
        elif text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING
        else:
            await update.message.reply_text("Пожалуйста, выберите один из вариантов.")
            return POST_TEXT_IMAGE_OFFER

    async def handle_text_editor_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_text = update.message.text
        style_prompt = self.get_style_prompt_for_user(user.id)
        org_info = self.get_org_info_for_user(user.id)
        projects_info = self.get_projects_info_for_user(user.id)

        edited = await run_gigachat(
            edit_text,
            user_text,
            style_prompt=style_prompt,
            org_info=org_info,
            projects_info=projects_info,
        )
        return await self.send_text_with_ethical_check(update, context, edited, followup_type="edit")

    async def handle_ethical_replace_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        pending_text = context.user_data.get("pending_text")
        issues = context.user_data.get("pending_ethical_issues", [])
        followup_type = context.user_data.get("pending_followup_type")

        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "🔙 В главное меню":
            context.user_data.pop("pending_text", None)
            context.user_data.pop("pending_ethical_issues", None)
            context.user_data.pop("pending_followup_type", None)

            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING
        context.user_data.pop("pending_text", None)
        context.user_data.pop("pending_ethical_issues", None)
        context.user_data.pop("pending_followup_type", None)

        if text == "✅ Заменить выражения":
            if pending_text is None:
                await update.message.reply_text(
                    "Текст для замены не найден. Попробуйте сгенерировать его заново.",
                    reply_markup=ReplyKeyboardRemove()
                )
                if user_info:
                    await self.show_registered_menu(update, user_info)
                return CHOOSING

            fixed_text = self.apply_ethical_replacements(pending_text, issues)
            await update.message.reply_text(fixed_text, reply_markup=ReplyKeyboardRemove())

        elif text == "❌ Оставить как есть":
            await update.message.reply_text(
                "Хорошо, оставляем текст без замен.",
                reply_markup=ReplyKeyboardRemove()
            )
            if pending_text and followup_type is None:
                # если нужно, можно снова показать исходный текст — но обычно он уже был отправлен
                pass
        else:
            context.user_data["pending_text"] = pending_text
            context.user_data["pending_ethical_issues"] = issues
            context.user_data["pending_followup_type"] = followup_type

            keyboard = [["✅ Заменить выражения", "❌ Оставить как есть"], ["🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Пожалуйста, выберите один из вариантов ниже.",
                reply_markup=reply_markup
            )
            return ETHICAL_REPLACE_CONFIRM
        if followup_type == "post":
            await self.ask_image_for_post(update, context)
            return POST_TEXT_IMAGE_OFFER
        else:
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

    async def start_content_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [["1 неделя", "2 недели", "Месяц"], ["🔙 В главное меню"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "На какой период сделать план? (1 неделя, 2 недели, месяц)",
            reply_markup=reply_markup
        )
        return CONTENT_PLAN_PERIOD

    async def handle_plan_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        context.user_data["plan_period"] = text
        await update.message.reply_text(
            "Как часто вы готовы постить? Например: 2 раза в неделю.",
            reply_markup=ReplyKeyboardRemove()
        )
        return CONTENT_PLAN_FREQUENCY

    async def handle_plan_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["plan_frequency"] = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)
        org_description = user_info.get("org_description") if user_info else None

        if org_description:
            keyboard = [["Использовать описание организации", "Написать свой вариант"], ["🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            text = (
                "Коротко опишите деятельность вашей организации,\n"
                "или выберите «Использовать описание организации»."
            )
        else:
            keyboard = [["🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            text = "Напишите пару фраз о том, чем занимается ваша организация."

        await update.message.reply_text(text, reply_markup=reply_markup)
        return CONTENT_PLAN_DESCRIPTION

    async def handle_plan_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        text = update.message.text

        if text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        if text == "Использовать описание организации" and user_info:
            descr = user_info.get("org_description") or ""
            if not descr:
                descr = "Благотворительная организация (описание не заполнено)."
        else:
            descr = text

        period = context.user_data.get("plan_period", "не указан")
        frequency = context.user_data.get("plan_frequency", "не указана")

        qa_text = (
            f"Период: {period}\n"
            f"Частота постов: {frequency}\n"
            f"Деятельность организации: {descr}"
        )
        context.user_data["plan_qa_text"] = qa_text

        style_prompt = self.get_style_prompt_for_user(user.id)
        org_info = self.get_org_info_for_user(user.id)
        projects_info = self.get_projects_info_for_user(user.id)

        plan_text = await run_gigachat(
            make_plan,
            qa_text,
            style_prompt=style_prompt,
            org_info=org_info,
            projects_info=projects_info,
        )

        context.user_data["last_plan_text"] = plan_text

        await update.message.reply_text(
            "Вот ваш контент-план:\n\n" + plan_text
        )

        keyboard = [["✏️ Сделать пост по этому плану", "🔙 В главное меню"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Можем сразу сделать пост по одному из пунктов плана.",
            reply_markup=reply_markup
        )
        return CONTENT_PLAN_RESULT_ACTION

    async def handle_plan_result_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        if text == "✏️ Сделать пост по этому плану":
            await update.message.reply_text(
                "Скопируйте из плана строку, для которой нужен пост,\n"
                "или опишите её своими словами.",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data["from_plan"] = True
            return POST_FREE_INPUT

        elif text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        else:
            await update.message.reply_text("Пожалуйста, выберите один из вариантов.")
            return CONTENT_PLAN_RESULT_ACTION

    # ==== БЛОК: КАРТИНКА К ПОСТУ ====

    async def start_image_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            ["🎨 Ввести описание картинки"],
            ["🔙 В главное меню"],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Сделаем картинку для поста.\nВыберите действие:",
            reply_markup=reply_markup
        )
        return IMAGE_MAIN_MODE_CHOICE

    async def handle_image_main_mode_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "🎨 Ввести описание картинки":
            context.user_data["image_mode"] = "direct"

            # Если картинка генерируется для поста, используем текст поста как основу
            from_post = context.user_data.get("image_base_from_post", False)
            if from_post:
                post_text = context.user_data.get("last_post_text", "")
                if post_text:
                    await update.message.reply_text(
                        f"📝 Текст вашего поста:\n\n{post_text}\n\n"
                        "Теперь опишите картинку для этого поста: кого или что показать, настроение, фон и т.п.\n"
                        "Или просто нажмите Enter, чтобы использовать текст поста как основу.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    await update.message.reply_text(
                        "Опишите картинку: кого или что показать, настроение, фон и т.п.",
                        reply_markup=ReplyKeyboardRemove()
                    )
            else:
                await update.message.reply_text(
                    "Опишите картинку: кого или что показать, настроение, фон и т.п.",
                    reply_markup=ReplyKeyboardRemove()
                )
            return IMAGE_PROMPT_INPUT

        elif text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        else:
            await update.message.reply_text("Пожалуйста, выберите один из вариантов.")
            return IMAGE_MAIN_MODE_CHOICE

    async def handle_image_prompt_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_description = update.message.text
        context.user_data["last_image_prompt"] = user_description

        # Если картинка генерируется для поста и пользователь не ввел описание, используем текст поста
        from_post = context.user_data.get("image_base_from_post", False)
        if from_post and not user_description.strip():
            post_text = context.user_data.get("last_post_text", "")
            if post_text:
                user_description = f"Иллюстрация для поста благотворительной организации. Текст поста: {post_text}"
                context.user_data["last_image_prompt"] = user_description

        # Добавляем информацию об организации в промпт
        user = update.effective_user
        org_info = self.get_org_info_for_user(user.id)
        if org_info:
            user_description = f"{user_description}\n\nКонтекст: {org_info}"

        try:
            success = await self.generate_and_send_image(update, user_description)

            if success:
                await self.ask_image_edit(update, context)
                return IMAGE_EDIT_PROMPT
            else:
                # Если генерация не удалась, предлагаем вернуться в меню
                keyboard = [["🔄 Попробовать снова", "🔙 В главное меню"]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    "Что вы хотите сделать?",
                    reply_markup=reply_markup
                )
                return IMAGE_MAIN_MODE_CHOICE

        except Exception as e:
            await update.message.reply_text(f"❌ Неожиданная ошибка: {str(e)}")
            return await self.start_image_flow(update, context)

    async def generate_and_send_image(self, update: Update, prompt: str):
        """Генерирует и отправляет одну картинку; блокировка только на уровне ОДНОГО пользователя"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        user_lock = self._get_user_image_lock(user_id)
        if user_lock.locked():
            await update.message.reply_text(
                "⏳ У вас уже идёт генерация картинки. Дождитесь, пожалуйста, результата предыдущего запроса."
            )
            return False

        async with user_lock:
            try:
                status_msg = await update.message.reply_text(
                    "🔄 Генерация картинки... Это займет около 30–60 секунд."
                )

                loop = asyncio.get_running_loop()
                image = await loop.run_in_executor(None, get_img, prompt)
                await loop.run_in_executor(None, give_img, image, chat_id)

                await status_msg.delete()
                return True

            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка при генерации картинки: {str(e)}")
                return False

    async def ask_image_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [["🔁 Хочу поменять картинку", "✅ Всё нравится"], ["🔙 В главное меню"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Хотите внести какие-то изменения в картинку?",
            reply_markup=reply_markup
        )

    async def handle_image_edit_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = update.message.text
        user_info = self.user_manager.get_user(user.id)
        awaiting_update = context.user_data.get("awaiting_image_update", False)

        if text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        if text == "🔄 Попробовать снова":
            return await self.start_image_flow(update, context)

        if awaiting_update:
            context.user_data["awaiting_image_update"] = False
            base_prompt = context.user_data.get("last_image_prompt", "Картинка для поста НКО")

            try:
                success = await self.generate_and_send_image(update, base_prompt + f"\nПравки: {text}")

                if success:
                    context.user_data["last_image_prompt"] = base_prompt + f"\nПравки: {text}"
                    await self.ask_image_edit(update, context)
                    return IMAGE_EDIT_PROMPT
                else:
                    keyboard = [["🔄 Попробовать снова", "🔙 В главное меню"]]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    await update.message.reply_text(
                        "Что вы хотите сделать?",
                        reply_markup=reply_markup
                    )
                    return IMAGE_MAIN_MODE_CHOICE

            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка при генерации картинки: {str(e)}")
                return await self.start_image_flow(update, context)

    async def handle_style_examples_collect(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        if text == "✅ Готово":
            examples = context.user_data.get("style_examples", [])
            if not examples:
                await update.message.reply_text(
                    "Пока нет ни одного примера. Пришлите хотя бы один пост, затем снова нажмите «✅ Готово»."
                )
                return STYLE_EXAMPLES_COLLECT

            style_prompt = build_style_prompt(examples)
            if user_info and user_info.get("org_id"):
                self.org_manager.set_org_style(user_info["org_id"], style_prompt)

            context.user_data.pop("style_examples", None)

            await update.message.reply_text(
                "✅ Стиль успешно сохранен! Теперь все тексты будут создаваться в этом стиле.\n\n"
                "Напишите, какой пост нужно подготовить:",
                reply_markup=ReplyKeyboardRemove()
            )
            return STYLE_NEW_POST_REQUEST

        elif text == "🔙 В главное меню":
            context.user_data.pop("style_examples", None)
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        else:
            examples = context.user_data.setdefault("style_examples", [])
            examples.append(text)
            await update.message.reply_text(
                "Записал этот текст как пример стиля. "
                "Пришлите ещё пример(ы) или нажмите «✅ Готово», когда закончите."
            )
            return STYLE_EXAMPLES_COLLECT

    async def handle_style_new_post_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)
        request_text = update.message.text

        style_prompt = self.get_style_prompt_for_user(user.id)
        if not style_prompt:
            await update.message.reply_text(
                "Кажется, стиль ещё не настроен. "
                "Вы можете сначала выбрать вариант «По примерам постов» и прислать несколько примеров."
            )
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        org_info = self.get_org_info_for_user(user.id)
        projects_info = self.get_projects_info_for_user(user.id)

        generated = await run_gigachat(
            generate_post_with_style,
            request_text,
            style_prompt=style_prompt,
            org_info=org_info,
            projects_info=projects_info,
        )
        context.user_data["last_post_text"] = generated
        context.user_data["last_post_source"] = "style"

        return await self.send_text_with_ethical_check(update, context, generated, followup_type="post")


    async def show_org_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_info = self.user_manager.get_user(update.effective_user.id)
        if not user_info:
            await update.message.reply_text(
                "❌ Вы ещё не зарегистрированы. Используйте /start."
            )
            return CHOOSING

        org_style = self.org_manager.get_org_style(user_info["org_id"])
        profile_text = (
            f"🏢 Профиль вашей НКО:\n\n"
            f"Название: {user_info['org_name']}\n"
            f"Описание: {user_info.get('org_description') or 'Не указано'}\n"
        )
        if org_style:
            profile_text += "\n✅ Стиль постов настроен на основе примеров."
        else:
            profile_text += (
                "\nℹ️ Стиль постов ещё не настроен. "
                "Вы можете обучить его через «Текст для поста» → «По примерам постов»."
            )

        keyboard = [
            ["✏️ Изменить описание", "🏷 Изменить название"],
            ["🗑️ Удалить стиль постов"] if org_style else [],
            ["🔙 В главное меню"],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(profile_text, reply_markup=reply_markup)
        return ORG_PROFILE_MENU

    async def handle_org_profile_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "✏️ Изменить описание":
            await update.message.reply_text(
                "Напишите новый текст «О нас» (описание организации):",
                reply_markup=ReplyKeyboardRemove()
            )
            return ORG_PROFILE_EDIT_DESCRIPTION

        elif text == "🏷 Изменить название":
            await update.message.reply_text(
                "Введите новое название организации:",
                reply_markup=ReplyKeyboardRemove()
            )
            return ORG_PROFILE_EDIT_NAME

        elif text == "🗑️ Удалить стиль постов":
            if user_info and user_info.get('org_id'):
                self.org_manager.delete_org_style(user_info['org_id'])
                await update.message.reply_text(
                    "✅ Стиль постов удален. Теперь тексты будут создаваться в стандартном стиле.",
                    reply_markup=ReplyKeyboardRemove()
                )
            return await self.show_org_profile(update, context)

        elif text == "🔙 В главное меню":
            if user_info:
                await self.show_registered_menu(update, user_info)
            return CHOOSING

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки меню.")
            return ORG_PROFILE_MENU

    async def handle_org_profile_edit_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_name = update.message.text.strip()
        user_info = self.user_manager.get_user(update.effective_user.id)

        if not user_info:
            await update.message.reply_text("❌ Вы ещё не зарегистрированы.")
            return CHOOSING

        self.org_manager.update_organization(user_info["org_id"], name=new_name)
        await update.message.reply_text(f"✅ Название организации обновлено: {new_name}")
        return await self.show_org_profile(update, context)

    async def handle_org_profile_edit_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_description = update.message.text.strip()
        user_info = self.user_manager.get_user(update.effective_user.id)

        if not user_info:
            await update.message.reply_text("❌ Вы ещё не зарегистрированы.")
            return CHOOSING

        self.org_manager.update_organization(user_info["org_id"], description=new_description)
        await update.message.reply_text("✅ Описание организации обновлено.")
        return await self.show_org_profile(update, context)

    # ==== БЛОК: ПРОЕКТЫ (как было) ====

    async def show_projects_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_info):
        projects = self.project_manager.get_organization_projects(user_info['org_id'])

        if not projects:
            keyboard = [["➕ Создать проект", "🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "📋 Проекты вашей организации\n\n"
                "Пока нет созданных проектов.\n"
                "Хотите создать первый проект?",
                reply_markup=reply_markup
            )
        else:
            projects_text = "📋 Проекты вашей организации:\n\n"
            for i, project in enumerate(projects, 1):
                projects_text += f"{i}. {project['name']}\n"
                if project['description']:
                    projects_text += f"   📝 {project['description']}\n"
                projects_text += f"   👤 Создатель: {project['creator_name']}\n"
                projects_text += f"   📅 Создан: {project['created_at'][:10]}\n\n"

            keyboard = [["➕ Создать проект", "🔍 Выбрать проект"], ["🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                projects_text + "Выберите действие:",
                reply_markup=reply_markup
            )

            context.user_data['projects'] = projects

        return PROJECT_CHOICE

    async def handle_project_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_info = self.user_manager.get_user(update.effective_user.id)

        if text == "➕ Создать проект":
            await update.message.reply_text(
                "🆕 Создание нового проекта\n\n"
                "Введите название проекта:",
                reply_markup=ReplyKeyboardRemove()
            )
            return ENTER_PROJECT_NAME

        elif text == "🔍 Выбрать проект":
            projects = context.user_data.get('projects', [])
            if not projects:
                await update.message.reply_text("Нет доступных проектов для выбора")
                return await self.show_projects_menu(update, context, user_info)

            keyboard = []
            project_mapping = {}

            for project in projects:
                button_text = f"📁 {project['name']}"
                keyboard.append([button_text])
                project_mapping[button_text] = project

            keyboard.append(["🔙 В главное меню"])

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Выберите проект для просмотра:",
                reply_markup=reply_markup
            )

            context.user_data['project_mapping'] = project_mapping
            return SELECT_PROJECT

        elif text == "🔙 В главное меню":
            return await self.start(update, context)

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки меню")
            return PROJECT_CHOICE

    async def handle_project_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        if text == "🔙 В главное меню":
            return await self.show_projects_menu(update, context, user_info)

        project_mapping = context.user_data.get('project_mapping', {})
        project = project_mapping.get(text)

        if project:
            context.user_data['selected_project'] = project

            await self.show_project_details(update, project)

            keyboard = [
                ["✏️ Редактировать проект", "🗑️ Удалить проект"],
                ["🔙 В главное меню"]
            ]

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Выберите действие с проектом:",
                reply_markup=reply_markup
            )

            return PROJECT_ACTIONS
        else:
            await update.message.reply_text("❌ Проект не найден. Попробуйте еще раз.")
            return SELECT_PROJECT

    async def handle_project_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user = update.effective_user
        project = context.user_data.get('selected_project')

        if not project:
            await update.message.reply_text("❌ Проект не найден. Вернитесь к списку проектов.")
            return await self.show_projects_menu(update, context, self.user_manager.get_user(user.id))

        if text == "🔙 В главное меню":
            return await self.show_projects_menu(update, context, self.user_manager.get_user(user.id))

        elif text == "✏️ Редактировать проект":
            keyboard = [["📝 Изменить название", "📋 Изменить описание"], ["🔙 В главное меню"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Что вы хотите изменить?",
                reply_markup=reply_markup
            )
            return PROJECT_ACTIONS

        elif text == "📝 Изменить название":
            await update.message.reply_text(
                "Введите новое название проекта:",
                reply_markup=ReplyKeyboardRemove()
            )
            return EDIT_PROJECT_NAME

        elif text == "📋 Изменить описание":
            await update.message.reply_text(
                "Введите новое описание проекта:",
                reply_markup=ReplyKeyboardRemove()
            )
            return EDIT_PROJECT_DESCRIPTION

        elif text == "🗑️ Удалить проект":
            keyboard = [["✅ Да, удалить", "❌ Нет, отмена"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                f"⚠️ Вы уверены, что хотите удалить проект '{project['name']}'?\n\n"
                "Это действие нельзя отменить!",
                reply_markup=reply_markup
            )
            return CONFIRM_DELETE_PROJECT

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки меню")
            return PROJECT_ACTIONS

    async def handle_edit_project_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_name = update.message.text
        project = context.user_data.get('selected_project')

        if not project:
            await update.message.reply_text("❌ Проект не найден.")
            return await self.start(update, context)

        success = self.project_manager.update_project(project['id'], name=new_name)

        if success:
            await update.message.reply_text(f"✅ Название проекта изменено на: {new_name}")
            updated_project = self.project_manager.get_project_by_id(project['id'])
            context.user_data['selected_project'] = updated_project

            await self.show_project_details(update, updated_project)

            keyboard = [
                ["✏️ Редактировать проект", "🗑️ Удалить проект"],
                ["🔙 В главное меню"]
            ]

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Выберите действие с проектом:",
                reply_markup=reply_markup
            )

            return PROJECT_ACTIONS
        else:
            await update.message.reply_text("❌ Ошибка при изменении названия проекта")
            return PROJECT_ACTIONS

    async def handle_edit_project_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_description = update.message.text
        project = context.user_data.get('selected_project')

        if not project:
            await update.message.reply_text("❌ Проект не найден.")
            return await self.start(update, context)

        success = self.project_manager.update_project(project['id'], description=new_description)

        if success:
            await update.message.reply_text("✅ Описание проекта успешно обновлено")
            updated_project = self.project_manager.get_project_by_id(project['id'])
            context.user_data['selected_project'] = updated_project

            await self.show_project_details(update, updated_project)

            keyboard = [
                ["✏️ Редактировать проект", "🗑️ Удалить проект"],
                ["🔙 В главное меню"]
            ]

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Выберите действие с проектом:",
                reply_markup=reply_markup
            )

            return PROJECT_ACTIONS
        else:
            await update.message.reply_text("❌ Ошибка при изменении описания проекта")
            return PROJECT_ACTIONS

    async def handle_confirm_delete_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        project = context.user_data.get('selected_project')
        user = update.effective_user

        if text == "✅ Да, удалить":
            if not project:
                await update.message.reply_text("❌ Проект не найден.")
                return await self.start(update, context)

            success = self.project_manager.delete_project(project['id'])

            if success:
                await update.message.reply_text(
                    f"✅ Проект '{project['name']}' успешно удален",
                    reply_markup=ReplyKeyboardRemove()
                )
                context.user_data.pop('selected_project', None)
            else:
                await update.message.reply_text("❌ Ошибка при удалении проекта")

            return await self.show_projects_menu(update, context, self.user_manager.get_user(user.id))

        elif text == "❌ Нет, отмена":
            await update.message.reply_text("Удаление проекта отменено")
            return await self.handle_project_selection(update, context)

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки подтверждения")
            return CONFIRM_DELETE_PROJECT

    async def show_project_details(self, update: Update, project):
        await update.message.reply_text(
            f"📁 Детали проекта:\n\n"
            f"🏷️ Название: {project['name']}\n"
            f"📝 Описание: {project.get('description', 'Не указано')}\n"
            f"👤 Создатель: {project['creator_name']}\n"
            f"📅 Создан: {project['created_at'][:10]}\n"
        )

    async def create_project_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['project_name'] = update.message.text
        await update.message.reply_text(
            "📝 Введите описание проекта (или отправьте '-' чтобы пропустить):"
        )
        return ENTER_PROJECT_DESCRIPTION

    async def create_project_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        description = update.message.text
        if description == '-':
            description = ""

        user = update.effective_user
        user_info = self.user_manager.get_user(user.id)

        success = self.project_manager.create_project(
            name=context.user_data['project_name'],
            description=description,
            org_id=user_info['org_id'],
            created_by=user.id
        )

        if success:
            await update.message.reply_text(
                f"🎉 Проект '{context.user_data['project_name']}' успешно создан!\n\n"
                f"Теперь он доступен всем сотрудникам вашей организации."
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при создании проекта. Попробуйте еще раз."
            )

        return await self.start(update, context)

    async def handle_reset_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user = update.effective_user

        if text == "✅ Да, сбросить":
            success = self.user_manager.delete_user(user.id)
            if success:
                await update.message.reply_text(
                    "✅ Ваша регистрация сброшена!\n\n"
                    "Теперь вы можете зарегистрироваться заново.",
                    reply_markup=ReplyKeyboardRemove()
                )
                await self.show_unregistered_menu(update, user)
                return CHOOSING
            else:
                await update.message.reply_text(
                    "❌ Произошла ошибка при сбросе регистрации",
                    reply_markup=ReplyKeyboardRemove()
                )
                return await self.start(update, context)

        elif text == "❌ Нет, отмена":
            await update.message.reply_text(
                "Сброс регистрации отменен.",
                reply_markup=ReplyKeyboardRemove()
            )
            return await self.start(update, context)

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки подтверждения")
            return CONFIRM_RESET

    async def register_org_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        org_code = update.message.text.upper().strip()
        user = update.effective_user

        success, message = self.user_manager.register_user(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name,
            org_code=org_code
        )

        if success:
            user_info = self.user_manager.get_user(user.id)
            org_description = user_info.get('org_description', 'Не указано')
            await update.message.reply_text(
                f"{message}\n\n"
                f"🏢 Организация: {user_info['org_name']}\n"
                f"📝 Описание: {org_description}\n\n"
                "Теперь вы можете пользоваться ботом! 🎉"
            )
            return await self.start(update, context)
        else:
            await update.message.reply_text(
                f"{message}\n\n"
                "Пожалуйста, проверьте код и попробуйте еще раз:\n"
                "Или отправьте /cancel для отмены"
            )
            return ENTER_ORG_CODE

    async def create_org_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['org_name'] = update.message.text
        await update.message.reply_text(
            "📝 Введите описание организации (или отправьте '-' чтобы пропустить):"
        )
        return ENTER_ORG_DESCRIPTION

    async def create_org_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        description = update.message.text
        if description == '-':
            description = ""

        success, code = self.org_manager.create_organization(
            name=context.user_data['org_name'],
            description=description
        )

        if success:
            user = update.effective_user

            if self.user_manager.is_user_registered(user.id):
                self.user_manager.delete_user(user.id)

            self.user_manager.register_user(
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name,
                org_code=code
            )

            await update.message.reply_text(
                f"🎉 Организация успешно создана!\n\n"
                f"🏢 Название: {context.user_data['org_name']}\n"
                f"📝 Описание: {description if description else 'Не указано'}\n"
                f"🔑 Код организации: {code}\n\n"
                f"📣 Передайте этот код сотрудникам для регистрации!"
            )
            return await self.start(update, context)
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при создании организации. Попробуйте еще раз с /start"
            )
            return await self.start(update, context)

    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_info = self.user_manager.get_user(update.effective_user.id)

        if not user_info:
            await update.message.reply_text(
                "❌ Вы еще не зарегистрированы.\n"
                "Используйте /start для регистрации."
            )
            return

        projects = self.project_manager.get_organization_projects(user_info['org_id'])

        profile_text = (
            f"👤 Ваш профиль:\n\n"
            f"🆔 ID: {user_info['telegram_id']}\n"
            f"👤 Имя: {user_info['full_name']}\n"
            f"📛 Username: {user_info['username'] or 'Не указан'}\n"
            f"🏢 Организация: {user_info['org_name']}\n"
            f"🔑 Код организации: {user_info['org_code']}\n"
            f"📝 Описание организации: {user_info.get('org_description', 'Не указано')}\n"
            f"📊 Проектов в организации: {len(projects)}"
        )

        await update.message.reply_text(profile_text)

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        success = self.user_manager.delete_user(user.id)

        if success:
            await update.message.reply_text(
                "✅ Ваша регистрация полностью сброшена!\n\n"
                "Теперь вы можете зарегистрироваться заново. Используйте /start",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "❌ Вы еще не зарегистрированы или произошла ошибка"
            )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Операция отменена. Используйте /start для начала.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await self.start(update, context)

    def setup_handlers(self, application: Application):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                CHOOSING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_choice)
                ],
                CONFIRM_RESET: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_reset_confirmation)
                ],
                PROJECT_CHOICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_project_choice)
                ],
                SELECT_PROJECT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_project_selection)
                ],
                PROJECT_ACTIONS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_project_actions)
                ],
                EDIT_PROJECT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_edit_project_name)
                ],
                EDIT_PROJECT_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_edit_project_description)
                ],
                CONFIRM_DELETE_PROJECT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_confirm_delete_project)
                ],
                ENTER_ORG_CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_org_code)
                ],
                ENTER_ORG_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_org_name)
                ],
                ENTER_ORG_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_org_description)
                ],
                ENTER_PROJECT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_project_name)
                ],
                ENTER_PROJECT_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_project_description)
                ],
                # Новые состояния
                POST_MODE_CHOICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_post_mode_choice)
                ],
                POST_FREE_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_post_free_input)
                ],
                POST_STRUCT_ASK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_structured_form_choice)
                ],
                POST_STRUCT_GET_ANSWER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_structured_form_answer)
                ],
                STYLE_EXAMPLES_COLLECT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_style_examples_collect)
                ],
                STYLE_NEW_POST_REQUEST: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_style_new_post_request)
                ],
                TEXT_EDITOR_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_editor_input)
                ],
                CONTENT_PLAN_PERIOD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_plan_period)
                ],
                CONTENT_PLAN_FREQUENCY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_plan_frequency)
                ],
                CONTENT_PLAN_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_plan_description)
                ],
                CONTENT_PLAN_RESULT_ACTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_plan_result_action)
                ],
                IMAGE_MAIN_MODE_CHOICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_image_main_mode_choice)
                ],
                IMAGE_PROMPT_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_image_prompt_input)
                ],
                # УБРАТЬ ЭТУ СТРОКУ: IMAGE_IDEA_CHOICE
                IMAGE_EDIT_PROMPT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_image_edit_prompt)
                ],
                ORG_PROFILE_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_org_profile_menu)
                ],
                ORG_PROFILE_EDIT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_org_profile_edit_name)
                ],
                ORG_PROFILE_EDIT_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_org_profile_edit_description)
                ],
                ETHICAL_REPLACE_CONFIRM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ethical_replace_confirm)
                ],
                POST_TEXT_IMAGE_OFFER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_post_text_image_offer)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("profile", self.profile))
        application.add_handler(CommandHandler("reset", self.reset))
        application.add_handler(CommandHandler("cancel", self.cancel))
    async def run(self):
    
        application = (
            Application.builder()
            .token(self.token)
            .concurrent_updates(16)
            .build()
        )
    
        self.setup_handlers(application)
    
        logging.info("Бот @helping_hand_nko_bot запущен!")
        print("✅ Бот запущен! Проверьте его в Telegram: @helping_hand_nko_bot")
    
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
    
        try:
            await asyncio.Event().wait()
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

async def main():
    bot = RegistrationBot(BOT_TOKEN)
    await bot.run()

bot = RegistrationBot(BOT_TOKEN)
await bot.run()
