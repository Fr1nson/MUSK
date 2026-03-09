import asyncio
import html
import json
import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    prompt: str
    example: str
    allow_skip: bool = True
    required: bool = True


@dataclass(frozen=True)
class Section:
    title: str
    fields: List[Field]


SECTIONS: List[Section] = [
    Section(
        title="1. Общая информация о проекте",
        fields=[
            Field("company_name", "Название компании / бренда", "Как называется ваша компания или бренд (точное написание)?", "ООО «Альфа»"),
            Field("business_area", "Сфера деятельности", "Какая у вас сфера деятельности?", "Производство мебели"),
            Field("business_description", "Краткое описание бизнеса", "Опишите бизнес в 1–3 предложениях.", "Производим кухни на заказ под ключ."),
            Field("site", "Сайт", "Есть ли сайт? Если да, пришлите ссылку.", "https://example.ru", allow_skip=True, required=False),
            Field("products_services", "Основные продукты или услуги", "Какие основные продукты или услуги вы предлагаете?", "Кухни, шкафы, дизайн-проект"),
            Field(
                "project_goal",
                "Основная цель проекта",
                "Выберите одну цель: продажи, заявки/лиды, узнаваемость бренда, презентация компании, другое.",
                "заявки/лиды",
            ),
            Field("main_problem", "Основная проблема, которую нужно решить", "Какую ключевую проблему должен решить проект?", "Мало входящих заявок с сайта"),
        ],
    ),
    Section(
        title="2. Целевая аудитория",
        fields=[
            Field("target_client", "Кто ваш основной клиент", "Кто ваш основной клиент?", "Собственники квартир в новостройках"),
            Field("audience_age", "Возраст", "Какой возраст вашей ЦА?", "28–45"),
            Field("audience_gender", "Пол", "Пол аудитории?", "мужчины и женщины"),
            Field("audience_geo", "География", "Где находится ваша аудитория?", "Москва и МО"),
            Field("audience_income", "Уровень дохода", "Какой уровень дохода у аудитории?", "средний и выше среднего"),
            Field("audience_status", "Профессия / статус", "Кем чаще всего являются ваши клиенты?", "семейные пары, офисные специалисты"),
            Field("client_problems", "Какие проблемы у клиента", "Какие боли/задачи у клиента вы решаете?", "Нужна функциональная кухня в ограниченном бюджете"),
            Field("choose_you", "Почему клиент выбирает вас", "Почему клиент выбирает именно вас?", "Фиксированная смета и срок производства 21 день"),
            Field("not_choose_you", "Почему клиент может не выбрать вас", "Почему клиент может не выбрать вас?", "Цена выше, чем у частных мастеров"),
        ],
    ),
    Section(
        title="3. Уникальное предложение (USP)",
        fields=[
            Field("main_difference", "Главное отличие от конкурентов", "В чем ваше главное отличие от конкурентов?", "Собственное производство и гарантия 5 лет"),
            Field("key_advantages", "3–5 ключевых преимуществ", "Перечислите 3–5 ключевых преимуществ.", "Сроки, гарантия, сервис, прозрачная цена"),
            Field("must_emphasize", "Что обязательно нужно подчеркнуть в проекте", "Что обязательно подчеркнуть в проекте?", "Гарантия и фиксированная стоимость"),
        ],
    ),
    Section(
        title="4. Конкуренты",
        fields=[
            Field("competitors", "3–5 конкурентов", "Назовите 3–5 конкурентов.", "brand1.ru, brand2.ru, brand3.ru"),
            Field("like_competitors", "Что нравится у конкурентов", "Что вам нравится у конкурентов?", "Хорошая структура каталога"),
            Field("dislike_competitors", "Что НЕ нравится у конкурентов", "Что вам не нравится у конкурентов?", "Сложная навигация и перегруженный дизайн"),
        ],
    ),
    Section(
        title="5. Структура проекта",
        fields=[
            Field(
                "main_sections",
                "Основные разделы",
                "Какие основные разделы нужны: Главная, О компании, Услуги, Продукты, Кейсы/портфолио, Отзывы, Блог, FAQ, Контакты?",
                "Главная, Услуги, Кейсы, Отзывы, FAQ, Контакты",
            ),
            Field("extra_sections", "Дополнительные разделы", "Нужны ли дополнительные разделы?", "Калькулятор стоимости, Вакансии", allow_skip=True, required=False),
        ],
    ),
    Section(
        title="6. Контент",
        fields=[
            Field("texts", "Тексты", "Тексты уже есть или нужно написать?", "нужно написать"),
            Field("photos", "Фото", "Фото есть или нужно подобрать?", "частично есть, нужно подобрать"),
            Field("video", "Видео", "Видео есть или нужно создать?", "нет, нужно создать"),
            Field("logo", "Логотип", "Логотип есть или нужно разработать?", "есть"),
            Field("brand_style", "Фирменный стиль", "Есть фирменный стиль?", "есть"),
        ],
    ),
    Section(
        title="7. Дизайн",
        fields=[
            Field("design_style", "Какой стиль нравится", "Какой стиль нравится: минимализм, премиум, корпоративный, технологичный, креативный, другой?", "минимализм и премиум"),
            Field("brand_colors", "Цвета бренда", "Какие цвета бренда использовать?", "черный, белый, графит"),
            Field("fonts", "Шрифты", "Какие шрифты использовать (если есть предпочтения)?", "Montserrat, Inter", allow_skip=True, required=False),
            Field("liked_sites", "Примеры сайтов, которые нравятся", "Пришлите примеры сайтов, которые нравятся.", "https://site1.ru, https://site2.ru"),
            Field("what_liked", "Что именно нравится на этих сайтах", "Что именно нравится на этих сайтах?", "чистая типографика и понятные CTA"),
        ],
    ),
    Section(
        title="8. Функциональность",
        fields=[
            Field(
                "required_features",
                "Что должно быть на проекте",
                "Какие функции нужны: форма заявки, онлайн-оплата, личный кабинет, CRM, чат, калькулятор, бронирование, каталог, фильтры?",
                "форма заявки, CRM, калькулятор, каталог, фильтры",
            ),
            Field("extra_features", "Дополнительные функции", "Нужны дополнительные функции?", "интерактивная карта объектов", allow_skip=True, required=False),
        ],
    ),
    Section(
        title="9. Технические требования",
        fields=[
            Field("platform", "Платформа", "На какой платформе делать проект: WordPress, Tilda, индивидуальная разработка?", "индивидуальная разработка"),
            Field("seo", "SEO оптимизация", "Нужна SEO-оптимизация?", "да"),
            Field("responsive", "Адаптивность", "Нужна адаптивность для мобильных устройств?", "да"),
            Field("speed", "Высокая скорость загрузки", "Нужна высокая скорость загрузки?", "да"),
            Field("integrations", "Интеграции с сервисами", "Нужны интеграции с сервисами? Если да, с какими?", "amoCRM, Telegram"),
        ],
    ),
    Section(
        title="10. Маркетинг",
        fields=[
            Field("seo_marketing", "SEO продвижение", "Планируется SEO-продвижение?", "да"),
            Field("context_ads", "Контекстная реклама", "Планируется контекстная реклама?", "да"),
            Field("target_ads", "Таргетированная реклама", "Планируется таргетированная реклама?", "нет"),
            Field("email_marketing", "Email маркетинг", "Планируется email-маркетинг?", "нет"),
            Field("content_marketing", "Контент маркетинг", "Планируется контент-маркетинг?", "да"),
        ],
    ),
    Section(
        title="11. Лиды и конверсия",
        fields=[
            Field("success_result", "Что считается успешным результатом", "Что считается успешным результатом: заявка, звонок, регистрация, покупка?", "заявка"),
            Field("desired_conversion", "Желаемая конверсия", "Какая желаемая конверсия?", "3–5%"),
        ],
    ),
    Section(
        title="12. Сроки",
        fields=[
            Field("start_date", "Когда нужно начать", "Когда нужно начать проект?", "в ближайшие 2 недели"),
            Field("finish_date", "Когда проект должен быть готов", "Когда проект должен быть готов?", "до 30 июня"),
            Field("deadline", "Есть ли дедлайн", "Есть ли жесткий дедлайн?", "да, до 30 июня"),
        ],
    ),
    Section(
        title="13. Бюджет",
        fields=[
            Field("project_budget", "Ориентировочный бюджет проекта", "Какой ориентировочный бюджет проекта?", "400 000 ₽"),
            Field("marketing_budget", "Бюджет на продвижение", "Какой бюджет на продвижение?", "120 000 ₽/мес"),
        ],
    ),
    Section(
        title="14. Поддержка",
        fields=[
            Field("post_support", "Поддержка после запуска", "Нужна ли после запуска техподдержка, SEO, обновление контента, аналитика?", "техподдержка и аналитика"),
        ],
    ),
    Section(
        title="16. Метрики и аналитика",
        fields=[
            Field("tracked_metrics", "Какие показатели отслеживаются", "Какие показатели будете отслеживать?", "трафик, конверсия, CPL"),
            Field("analytics_tools", "Инструменты", "Какие инструменты аналитики нужны: Google Analytics, Яндекс Метрика, CRM?", "Яндекс Метрика и amoCRM"),
        ],
    ),
    Section(
        title="17. Дополнительные пожелания клиента",
        fields=[
            Field("additional_wishes", "Любые идеи, требования или ограничения", "Есть дополнительные идеи, требования или ограничения?", "сайт на русском и английском", allow_skip=True, required=False),
        ],
    ),
    Section(
        title="18. Финальное согласование",
        fields=[
            Field("approval_points", "Что нужно утвердить перед запуском", "Что нужно утвердить перед запуском: структура, дизайн, тексты, функционал, сроки?", "все пункты утверждаются поэтапно"),
        ],
    ),
]


KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Пропустить", "Назад"],
        ["Сводка", "Завершить"],
        ["Написать @Fr1nson"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

QUESTION_LEADS = [
    "Давайте зафиксируем следующий важный пункт.",
    "Двигаемся дальше — уточню следующий момент.",
    "Хороший темп, теперь нужен ещё один блок данных.",
    "Чтобы собрать сильный бриф, уточним это поле.",
]

QUESTION_TIPS = [
    "Можно ответить в свободной форме, я аккуратно структурирую.",
    "Если пункта сейчас нет, можно нажать «Пропустить».",
    "Чем конкретнее ответ, тем точнее получится итоговый документ.",
    "Если хотите поправить прошлый ответ, используйте «Назад».",
]

CONFIRM_TEMPLATES = [
    "Отлично, фиксирую: *{label}* — {value}",
    "Принято, записал: *{label}* — {value}",
    "Спасибо, внес в бриф: *{label}* — {value}",
    "Супер, отмечаю: *{label}* — {value}",
]

CLARIFY_TEMPLATES = [
    "Хочу уточнить чуть точнее по пункту «{label}». Дайте, пожалуйста, немного больше деталей.",
    "Пока ответ выглядит слишком общим для «{label}». Добавьте 1–2 конкретики.",
    "Чтобы бриф был действительно полезным, раскройте пункт «{label}» немного подробнее.",
]

SECTION_DONE_TEMPLATES = [
    "Раздел «{section}» аккуратно заполнен. Переходим дальше.",
    "Отлично, блок «{section}» завершен. Идём к следующему разделу.",
    "Принято, раздел «{section}» закрыли. Продолжаем интервью.",
]

FAREWELL_TEMPLATES = [
    "Спасибо за содержательный диалог. Документ подготовлен и отправлен.",
    "Благодарю за доверие. Бриф оформлен и уже у вас в сообщениях.",
    "Спасибо, всё собрал в аккуратный документ. Можно передавать в работу.",
]


def flatten_fields() -> List[tuple[int, int, Section, Field]]:
    result: List[tuple[int, int, Section, Field]] = []
    for section_index, section in enumerate(SECTIONS):
        for field_index, field in enumerate(section.fields):
            result.append((section_index, field_index, section, field))
    return result


FLAT_FIELDS = flatten_fields()


def question_position(section_index: int, field_index: int, section: Section) -> str:
    return f"Пункт {field_index + 1} из {len(section.fields)}"


def format_saved_value(value: Optional[str], example: str) -> str:
    if value and value.strip():
        return value.strip()
    return f"Не указано. Пример: {example}"


def is_skip(text: str) -> bool:
    return text.strip().lower() in {"пропустить", "skip", "-"}


def is_back(text: str) -> bool:
    return text.strip().lower() in {"назад", "back"}


def is_finish(text: str) -> bool:
    return text.strip().lower() in {"завершить", "finish", "/finish"}


def is_summary(text: str) -> bool:
    return text.strip().lower() in {"сводка", "summary", "/summary"}


def is_contact_support(text: str) -> bool:
    return text.strip().lower() in {"написать @fr1nson", "support", "/support"}


def looks_incomplete(text: str) -> bool:
    trimmed = text.strip().lower()
    if len(trimmed) < 2:
        return True
    weak = {"не знаю", "хз", "потом", "?", "нет", "да"}
    return trimmed in weak


def pick_phrase(options: List[str], index: int) -> str:
    return options[index % len(options)]


def build_confirmation(field: Field, answer: str, index: int) -> str:
    template = pick_phrase(CONFIRM_TEMPLATES, index)
    return template.format(label=field.label, value=html.escape(answer.strip()))


def build_question(section: Section, field: Field, index: int, section_index: int, field_index: int) -> str:
    lead = pick_phrase(QUESTION_LEADS, index)
    tip = pick_phrase(QUESTION_TIPS, index)
    return (
        f"*{section.title}*\n"
        f"{question_position(section_index, field_index, section)}\n\n"
        f"{lead}\n"
        f"{field.prompt}\n"
        f"{tip}\n"
        f"Пример: _{field.example}_"
    )


def build_markdown_brief(answers: Dict[str, str]) -> str:
    lines: List[str] = ["# Готовый технический бриф", ""]
    for section in SECTIONS:
        lines.append(f"## {section.title}")
        for field in section.fields:
            value = format_saved_value(answers.get(field.key), field.example)
            lines.append(f"- **{field.label}:** {value}")
        lines.append("")
    return "\n".join(lines).strip()


def build_formatted_document(answers: Dict[str, str], created_at: str, customer_name: str) -> str:
    lines: List[str] = [
        "# Технический бриф проекта",
        "",
        "Уважаемые коллеги,",
        "ниже приведена структурированная версия клиентского брифа, подготовленная по итогам интервью.",
        "",
        f"**Дата оформления:** {created_at}",
        f"**Контакт клиента:** {customer_name}",
        "",
    ]
    for section in SECTIONS:
        lines.append("---")
        lines.append("")
        lines.append(f"## {section.title}")
        lines.append("")
        for field in section.fields:
            value = format_saved_value(answers.get(field.key), field.example)
            lines.append(f"- **{field.label}:** {value}")
        lines.append("")
    lines.extend(
        [
            "---",
            "",
            "С уважением,",
            "команда подготовки проектного брифа",
        ]
    )
    return "\n".join(lines).strip()


def build_html_document(answers: Dict[str, str], created_at: str, customer_name: str) -> str:
    sections: List[str] = []
    for section in SECTIONS:
        items: List[str] = []
        for field in section.fields:
            value = format_saved_value(answers.get(field.key), field.example)
            items.append(
                "<tr>"
                f"<td class='label'>{html.escape(field.label)}</td>"
                f"<td class='value'>{html.escape(value)}</td>"
                "</tr>"
            )
        sections.append(
            "<section class='card'>"
            f"<h2>{html.escape(section.title)}</h2>"
            "<table>"
            + "".join(items)
            + "</table>"
            "</section>"
        )
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<title>Технический бриф проекта</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;background:#f4f5f7;color:#1f2937;margin:0;padding:24px;}"
        ".wrap{max-width:980px;margin:0 auto;}"
        ".head{background:#111827;color:#fff;padding:28px;border-radius:14px;}"
        ".head h1{margin:0 0 10px;font-size:28px;}"
        ".head p{margin:4px 0;color:#d1d5db;}"
        ".card{background:#fff;border-radius:14px;margin-top:16px;padding:20px;box-shadow:0 4px 14px rgba(17,24,39,.08);}"
        ".card h2{margin:0 0 14px;font-size:20px;}"
        "table{width:100%;border-collapse:collapse;}"
        "td{padding:10px 8px;border-bottom:1px solid #e5e7eb;vertical-align:top;}"
        ".label{width:34%;font-weight:700;color:#111827;}"
        ".value{width:66%;}"
        ".foot{margin-top:24px;background:#fff;border-radius:14px;padding:20px;box-shadow:0 4px 14px rgba(17,24,39,.08);}"
        "</style></head><body><div class='wrap'>"
        "<header class='head'>"
        "<h1>Технический бриф проекта</h1>"
        "<p>Подготовлено по результатам клиентского интервью</p>"
        f"<p><strong>Дата оформления:</strong> {html.escape(created_at)}</p>"
        f"<p><strong>Контакт клиента:</strong> {html.escape(customer_name)}</p>"
        "</header>"
        + "".join(sections)
        + "<section class='foot'><p>С уважением,<br>команда подготовки проектного брифа</p></section>"
        "</div></body></html>"
    )


def slugify(value: str) -> str:
    prepared = "".join(char if char.isalnum() else "_" for char in value.strip().lower())
    compact = "_".join(part for part in prepared.split("_") if part)
    return compact[:40] or "client"


def get_storage_dir() -> Path:
    raw_dir = os.getenv("BRIEF_STORAGE_DIR", "saved_briefs")
    path = Path(raw_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_brief_files(update: Update, answers: Dict[str, str]) -> Dict[str, Path]:
    storage_dir = get_storage_dir()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    company_name = (answers.get("company_name") or "").strip() or "Без названия"
    user_label = update.effective_user.username or str(update.effective_user.id)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{stamp}_{slugify(company_name)}_{slugify(user_label)}"
    markdown_text = build_formatted_document(answers, created_at, user_label)
    html_text = build_html_document(answers, created_at, user_label)
    payload = {
        "created_at": created_at,
        "user_id": update.effective_user.id,
        "username": update.effective_user.username,
        "first_name": update.effective_user.first_name,
        "last_name": update.effective_user.last_name,
        "chat_id": update.effective_chat.id if update.effective_chat else None,
        "answers": answers,
    }
    md_path = storage_dir / f"{base}.md"
    html_path = storage_dir / f"{base}.html"
    json_path = storage_dir / f"{base}.json"
    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"md": md_path, "html": html_path, "json": json_path}


async def send_brief_document(context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, file_path: Path, caption: str) -> None:
    with file_path.open("rb") as brief_file:
        await context.bot.send_document(
            chat_id=chat_id,
            document=brief_file,
            filename=file_path.name,
            caption=caption,
        )


async def send_markdown_chunks(update: Update, text: str, chunk_size: int = 3500) -> None:
    if not update.effective_message:
        return
    lines = text.splitlines(keepends=True)
    current = ""
    chunks: List[str] = []
    for line in lines:
        if len(current) + len(line) <= chunk_size:
            current += line
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(line) <= chunk_size:
            current = line
            continue
        start = 0
        while start < len(line):
            chunks.append(line[start : start + chunk_size])
            start += chunk_size
    if current:
        chunks.append(current)
    for chunk in chunks:
        await update.effective_message.reply_text(chunk)


def get_state(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, object]:
    state = context.user_data.setdefault("brief_state", {})
    state.setdefault("index", 0)
    state.setdefault("answers", {})
    return state


async def ask_current_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(context)
    index = int(state["index"])
    if index >= len(FLAT_FIELDS):
        await finish_brief(update, context)
        return
    section_index, field_index, section, field = FLAT_FIELDS[index]
    text = build_question(section, field, index, section_index, field_index)
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KEYBOARD,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    get_state(context)
    await update.effective_message.reply_text(
        "Здравствуйте. Я помогу бережно заполнить бриф: буду задавать вопросы по одному, "
        "фиксировать ваши ответы и деликатно уточнять важные детали.",
        reply_markup=KEYBOARD,
    )
    await ask_current_question(update, context)


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(context)
    answers = state["answers"]
    message = build_markdown_brief(answers)
    await update.effective_message.reply_text("Промежуточная сводка по текущим ответам:")
    await send_markdown_chunks(update, message)


async def finish_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = get_state(context)
    answers = state["answers"]
    message = build_markdown_brief(answers)
    saved_files = save_brief_files(update, answers)
    
    # 1. Сначала отправляем документ
    await send_brief_document(
        context=context,
        chat_id=update.effective_chat.id,
        file_path=saved_files["html"],
        caption="Готовый бриф в аккуратно оформленном документе.",
    )

    # 2. Потом прощальную фразу
    await update.effective_message.reply_text(
        pick_phrase(FAREWELL_TEMPLATES, len(answers)),
        reply_markup=KEYBOARD,
    )
    
    admin_chat_id = os.getenv("ADMIN_CHAT_ID", "987487673")
    if admin_chat_id:
        try:
            intro = f"Бриф от @{update.effective_user.username or update.effective_user.id}"
            await context.bot.send_message(chat_id=admin_chat_id, text=intro)
            await send_brief_document(
                context=context,
                chat_id=admin_chat_id,
                file_path=saved_files["html"],
                caption="Новый заполненный клиентский бриф.",
            )
            # Пользователю уже ответили выше, здесь дублировать не нужно
        except Exception as exc:
            # Если не удалось отправить админу, пользователю об этом знать не обязательно,
            # но в лог или консоль вывести стоит.
            print(f"Не удалось отправить копию администратору: {exc}")
            
    context.user_data.clear()


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.text:
        return
    text = update.effective_message.text.strip()
    state = get_state(context)
    index = int(state["index"])
    answers: Dict[str, str] = state["answers"]
    if is_summary(text):
        await summary(update, context)
        return
    if is_contact_support(text):
        await update.effective_message.reply_text(
            "Если возникли сложности или нужен персональный подход, "
            "напишите напрямую: @Fr1nson.\n\n"
            "После этого можем продолжить заполнение здесь.",
            parse_mode=ParseMode.MARKDOWN
        )
        # Не меняем стейт, просто отвечаем и ждем дальше ответ на вопрос
        return
    if is_finish(text):
        await finish_brief(update, context)
        return
    if index >= len(FLAT_FIELDS):
        await finish_brief(update, context)
        return
    _, _, section, field = FLAT_FIELDS[index]
    if is_back(text):
        if index == 0:
            await update.effective_message.reply_text("Сейчас вы на первом вопросе, вернуться назад пока нельзя.")
            await ask_current_question(update, context)
            return
        state["index"] = index - 1
        prev_field = FLAT_FIELDS[index - 1][3]
        answers.pop(prev_field.key, None)
        await update.effective_message.reply_text("Хорошо, вернулся на предыдущий вопрос и снял последний ответ.")
        await ask_current_question(update, context)
        return
    if is_skip(text):
        if field.required and not field.allow_skip:
            await update.effective_message.reply_text("Этот пункт критично важен для качества брифа. Дайте краткий ответ.")
            await ask_current_question(update, context)
            return
        answers[field.key] = ""
        await update.effective_message.reply_text(f"Понял, пункт «{field.label}» пока оставляю пустым.")
        state["index"] = index + 1
        await ask_current_question(update, context)
        return
    if looks_incomplete(text):
        await update.effective_message.reply_text(
            pick_phrase(CLARIFY_TEMPLATES, index).format(label=field.label)
        )
        await ask_current_question(update, context)
        return
    answers[field.key] = text
    await update.effective_message.reply_text(build_confirmation(field, text, index), parse_mode=ParseMode.MARKDOWN)
    state["index"] = index + 1
    if section != FLAT_FIELDS[min(index + 1, len(FLAT_FIELDS) - 1)][2]:
        await update.effective_message.reply_text(
            pick_phrase(SECTION_DONE_TEMPLATES, index).format(section=section.title)
        )
    await ask_current_question(update, context)


import sys

def ensure_token() -> str:
    # 1. Сначала ищем в аргументах командной строки (python bot.py ТОКЕН)
    if len(sys.argv) > 1 and ":" in sys.argv[1]:
        return sys.argv[1]

    # 2. Потом в переменных окружения
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("\n\n" + "!" * 50)
        print("ОШИБКА: Токен не найден!")
        print("Запустите бота одной из команд:")
        print("1.  python bot.py ВАШ_ТОКЕН")
        print("2.  $env:BOT_TOKEN='ВАШ_ТОКЕН'; python bot.py")
        print("!" * 50 + "\n\n")
        raise RuntimeError("Токен не передан.")
    return token


def run() -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(ensure_token()).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("finish", finish_brief))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling()


if __name__ == "__main__":
    run()
