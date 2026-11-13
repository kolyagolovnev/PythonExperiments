# Python-проекты: портфолио и учебные эксперименты

Этот репозиторий — моя песочница для изучения backend-разработки на Python и всё, что с ним связано. Каждый подкаталог — самостоятельный проект со своей структурой, зависимостями и README (где он есть).

Главный проект — **VkazarmePython**: учебный backend социальной сети для сослуживцев на Python, переделанная копия моего [`старого учебного проекта по Web на C++`](https://github.com/rkolyan/VKazarme), сделанного совместно с [`Егором Ворониным`](https://gitlab.com/soulnottechnique). Он находится в активной разработке (я пытаюсь почти всё ручками перебрать, чтобы не быть просто обезъянкой, наобум пользуйщейся ИИ-ассистентами).

## Сводная таблица

| Проект | Что это | Стек | Статус |
|---|---|---|---|
| **VkazarmePython** | Backend социальной сети для сослуживцев | Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL, bcrypt, JWT, Docker | В разработке (WIP) |
| **VkazarmePython_failed** | Расширенная версия Vkazarme с OAuth2 и подтверждением email | FastAPI, Pydantic, SQLAlchemy, Redis, PostgreSQL, SMTP/DNS, Docker, nginx | Остановлена и сохранена как архив |
| **VkazarmePython_Vibecoding** | Полная реализация того же API в режиме vibe coding | FastAPI, Pydantic, SQLAlchemy 2.0, PostgreSQL/SQLite, WebSocket, pytest | Завершена как учебный эталон |
| **ConsoleMatch3** | ИИ-слопная Match-3 игра в терминале | Python standard library: `curses`, `argparse`, `unittest` | Завершён |
| **playwright_mailpit** | Стенд для проверки регистрации с подтверждением по почте | FastAPI, Mailpit, Docker Compose, pytest, requests, Playwright | Завершён |
| **JWTPentest** | Мини-лаборатория по проверке JWT | FastAPI, PyJWT, Pydantic, pytest, requests | Завершён |
| **NLPPractice** | Курсовой проект по NLP | NLP, LLM, Python (план) | Этап планирования |

(Самое смешное - прежде чем ИИ-агент написал свою версию (**VkazarmePython_Vibecoding**), он вышел за пределы указанной директории и скопировал мои измученные изначальные версии (**VkazarmePython_failed**, **VkazarmePython**), почти полностью их потом переделав на свой лад).

# Сводка использованных технологий

## Язык и базовые технологии

- Python 3.12/3.13, виртуальные окружения, типизация, generics.
- Аннотации типов, `TypeVar`, `Generic`, `Protocol`/ABC, композиция и наследование.
- `async`/`await`, асинхронные контекстные менеджеры, работа с конкурентностью.
- Стандартная библиотека.

## Web и API

- FastAPI: роутеры, зависимости, middleware, DI
- Pydantic v2
- OpenAPI 3.x и AsyncAPI: описание контракта, REST, Swagger UI.
- JWT (PyJWT), bcrypt, OAuth 2.0 Authorization Code Flow, `state`/CSRF.
- HTTP-клиенты: `httpx`, `requests`; тестирование через `TestClient`.

## Данные и хранение

- SQLAlchemy 2.0: async engine, `async_sessionmaker`, DeclarativeBase, `Mapped`, `mapped_column`, `UniqueConstraint`, `Enum`, `TypeDecorator`.
- PostgreSQL: схема, внешние ключи, каскады, индексы, роли, транзакции.
- SQLite как тестовая БД; `aiosqlite`.
- Redis: TTL-ключи, хранение временных аккаунтов.
- In-memory репозитории как mock-слой.
- SQL: `SELECT`, ограничения, нормализация, связи many-to-many через join-таблицы.

## Тестирование

- `pytest`, `pytest-asyncio`, `pytest-cov`, параметризация, фикстуры.
- `unittest`.
- `MagicMock`/`AsyncMock`, проверка вызовов и порядка вызовов.
- Unit / integration / e2e тесты.
- `httpx.AsyncClient`, FastAPI `TestClient`, WebSocket-тесты.
- `testcontainers` для PostgreSQL.
- Playwright (затрагивал ради эксперимента, подготовлен в стенде).
- `mypy` в качестве статического анализатора кода.
- BDD-стиль Given/When/Then, TDD-подход «сверху вниз».

## Инфраструктура и инструменты

- Docker: multi-stage builds, запуск тестов в контейнерах.
- Docker Compose: сети, health-check, зависимости, тома, переменные окружения.
- Nginx как reverse proxy для мок-сервисов.
- Mailpit для локального SMTP.
- Работа с внешними API и мок-серверами.

## Архитектура и инженерные практики

- Слоистая архитектура: HTTP → service → repository → domain.
- Repository pattern, ports & adapters, dependency inversion.
- Composition root и DI-контейнер.
- Разделение DTO и доменных сущностей.
- Contract-first разработка.
- Централизованная обработка ошибок и маппинг исключений в HTTP-коды.
- Осознанные компромиссы: in-memory vs БД, строгая схема vs гибкость, REST vs оптимизация.
- Применение принципов DRY, KISS
