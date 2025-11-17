# Telegram Digest Bot

Бот получает последние обсуждения в чате Telegram, передаёт их в OpenRouter или Ollama для генерации дайджеста и публикует результат обратно в чат.

## Содержание

- [Требования](#требования)
- [Установка](#установка)
- [Настройка](#настройка)
- [Использование](#использование)
- [Команды](#команды)
- [Планировщик](#планировщик)
- [Разработка](#разработка)

## Требования

- Python 3.9 или выше
- Telegram бот (созданный через [@BotFather](https://t.me/BotFather))
- API ключ от OpenRouter (если используете OpenRouter) или локально установленный Ollama

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/agrloki/telegram-bot.git
cd telegram-bot
```

### 2. Создание виртуального окружения (рекомендуется)

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -e .
```

Или используйте `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Настройка

### 1. Создание Telegram бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Сохраните полученный токен (формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Получение Chat ID

**Для группы/канала:**
1. Добавьте бота в группу/канал
2. Отправьте любое сообщение в группу/канал
3. Откройте в браузере: `https://api.telegram.org/bot<ВАШ_ТОКЕН>/getUpdates`
4. Найдите `"chat":{"id":-1001234567890}` — это и есть Chat ID

**Альтернативный способ:**
- Используйте бота [@userinfobot](https://t.me/userinfobot) или [@getidsbot](https://t.me/getidsbot)
- Для групп: добавьте бота в группу и отправьте команду `/start`

### 3. Настройка OpenRouter (опционально)

1. Зарегистрируйтесь на [OpenRouter.ai](https://openrouter.ai/)
2. Получите API ключ в разделе "Keys"
3. Выберите модель из списка доступных (см. [free_models.md](free_models.md) для бесплатных моделей)

### 4. Настройка Ollama (опционально)

1. Установите [Ollama](https://ollama.ai/)
2. Скачайте модель: `ollama pull llama3` (или другую)
3. Убедитесь, что Ollama запущен: `ollama serve`

### 5. Создание файла конфигурации

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

Отредактируйте `.env` и заполните необходимые значения:

```env
# Обязательные параметры
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TARGET_CHAT_ID=-1001234567890  # Опционально: если не задан, обрабатываются все чаты

# База данных
DATABASE_PATH=messages.db

# Провайдер LLM (openrouter или ollama)
LLM_PROVIDER=openrouter

# Настройки OpenRouter
OPENROUTER_API_KEY=ваш_ключ_openrouter
OPENROUTER_MODEL=openrouter/anthropic/claude-3.5-sonnet
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Настройки Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Стиль промпта (default, hk47-light, hk47)
PROMPT_STYLE=default

# Параметры дайджеста
DIGEST_LOOKBACK_DAYS=7
MAX_MESSAGES=400
REQUEST_TIMEOUT=60
```

## Быстрый старт

После настройки `.env` файла выполните следующие шаги:

1. **Соберите сообщения из чатов:**
   ```bash
   python -m src.main sync
   ```

2. **Проверьте список чатов:**
   ```bash
   python -m src.main list-chats
   ```

3. **Сгенерируйте дайджест (тестовый запуск):**
   ```bash
   python -m src.main digest --dry-run
   ```

4. **Отправьте дайджест:**
   ```bash
   python -m src.main digest
   ```

Подробные инструкции по каждой команде см. в разделе [Команды](#команды).

## Команды

### `sync`

Собирает новые сообщения из всех чатов, куда добавлен бот, и сохраняет их в базу данных.

```bash
python -m src.main sync
python -m src.main sync --debug  # С отладочными логами
```

**Что делает:**
- Получает обновления через Telegram Bot API (`getUpdates`)
- Сохраняет текстовые сообщения в SQLite
- Обновляет `last_update_id` для отслеживания прогресса

### `list-chats`

Показывает список чатов, из которых уже пришли сообщения (хранятся в базе данных).

```bash
python -m src.main list-chats
```

**Вывод:**
- ID чата
- Тип чата (group, supergroup, channel)
- Название чата
- Время последнего сообщения

### `list-bot-chats`

Показывает список всех чатов из базы данных, где бот является участником (проверяет доступность через API).

```bash
python -m src.main list-bot-chats
```

**Что делает:**
- Берет чаты из базы данных
- Проверяет доступность каждого чата через `getChat`
- Показывает только те чаты, где бот все еще имеет доступ

**Примечание:** Если база данных пустая, команда предложит сначала запустить `sync`.

### `digest`

Генерирует и отправляет дайджест обсуждений за последние N дней (по умолчанию 7).

```bash
# Тестовый запуск (вывод в консоль)
python -m src.main digest --dry-run

# Реальная отправка
python -m src.main digest

# С другой моделью
python -m src.main digest --model openrouter/google/gemini-flash-1.5

# С другим провайдером
python -m src.main digest --provider ollama --model llama3
```

**Параметры:**
- `--dry-run` — не отправлять в чат, вывести в stdout
- `--model` — переопределить модель для текущего запуска
- `--provider` — временно выбрать провайдера (openrouter/ollama)

**Поведение:**
- Если `TARGET_CHAT_ID` задан — отправляет в указанный чат
- Если `TARGET_CHAT_ID` не задан — обрабатывает все чаты из базы отдельно
- После успешной отправки очищает базу для каждого чата

### `force-send`

Отправляет дайджест из всех сообщений в базе, игнорируя период `DIGEST_LOOKBACK_DAYS`.

```bash
python -m src.main force-send
python -m src.main force-send --dry-run
```

**Использование:**
- Когда нужно обработать все накопленные сообщения
- Для тестирования на полном наборе данных

### `clear-db`

Очищает базу данных сообщений.

```bash
# Очистить только целевой чат
python -m src.main clear-db

# Очистить все чаты
python -m src.main clear-db --all-chats

# Очистить все чаты и сбросить offset
python -m src.main clear-db --all-chats --reset-offset
```

**Параметры:**
- `--all-chats` — очистить все чаты, иначе только целевой
- `--reset-offset` — сбросить `last_update_id` после очистки

**Когда использовать:**
- Для очистки старых данных
- После ошибок синхронизации
- Для полного сброса состояния

## Использование

### Режимы работы

**Режим 1: Один целевой чат (TARGET_CHAT_ID задан)**
- Бот собирает сообщения из всех чатов, но обрабатывает только указанный
- Дайджест отправляется в указанный чат
- Подходит для централизованного сбора дайджестов

**Режим 2: Все чаты (TARGET_CHAT_ID не задан)**
- Бот собирает сообщения из всех чатов, куда он добавлен
- Для каждого чата генерируется отдельный дайджест
- Дайджест отправляется в тот же чат, откуда собраны сообщения
- Подходит для автоматической обработки нескольких чатов

### Стили промптов

Бот поддерживает три стиля системных промптов:

1. **`default`** — стандартный аналитический стиль
2. **`hk47-light`** — саркастичный стиль в духе HK-47 (легкий вариант)
3. **`hk47`** — полный стиль HK-47 с техническими метафорами и философскими выводами

Установите `PROMPT_STYLE` в `.env` для выбора стиля.

### Примеры использования

**Ежедневная синхронизация:**
```bash
# Добавьте в cron
0 8 * * * cd /path/to/telegram-bot && /usr/bin/python3 -m src.main sync >> sync.log 2>&1
```

**Еженедельный дайджест:**
```bash
# Добавьте в cron
0 9 * * MON cd /path/to/telegram-bot && /usr/bin/python3 -m src.main digest >> digest.log 2>&1
```

**Тестирование перед отправкой:**
```bash
python -m src.main digest --dry-run
```

**Использование локальной модели Ollama:**
```bash
python -m src.main digest --provider ollama --model llama3
```

## Функции

- ✅ Кэширует входящие сообщения через `getUpdates` и хранит их в `messages.db`
- ✅ Собирает сообщения из всех чатов, куда добавлен бот (без фильтрации по `TARGET_CHAT_ID`)
- ✅ При генерации использует последние `DIGEST_LOOKBACK_DAYS` суток (по умолчанию 7)
- ✅ Группирует сообщения по цепочкам обсуждений и строит ссылки `https://t.me/c/<chat_id>/<message_id>`
- ✅ Поддерживает несколько стилей промптов (default, hk47-light, hk47)
- ✅ Работает с OpenRouter и Ollama
- ✅ Автоматически очищает базу после успешной отправки дайджеста
- ✅ Отправляет текстовое резюме:
  - Если `TARGET_CHAT_ID` задан — в указанный чат (режим обратной совместимости)
  - Если `TARGET_CHAT_ID` не задан — отдельно в каждый чат, откуда собраны сообщения

## Планировщик

Для автоматического запуска используйте cron (Linux/Mac) или Task Scheduler (Windows).

### Настройка cron (Linux/Mac)

Откройте crontab:
```bash
crontab -e
```

Добавьте задачи:
```cron
# Ежедневная синхронизация в 8:00
0 8 * * * cd /path/to/telegram-bot && /usr/bin/python3 -m src.main sync >> sync.log 2>&1

# Еженедельный дайджест в понедельник в 9:00
0 9 * * MON cd /path/to/telegram-bot && /usr/bin/python3 -m src.main digest >> digest.log 2>&1
```

**Важно:** Замените `/path/to/telegram-bot` на реальный путь к проекту и `/usr/bin/python3` на путь к вашему Python.

### Настройка systemd (Linux)

Создайте файл `/etc/systemd/system/telegram-digest-bot.service`:

```ini
[Unit]
Description=Telegram Digest Bot
After=network.target

[Service]
Type=oneshot
User=ваш_пользователь
WorkingDirectory=/path/to/telegram-bot
ExecStart=/usr/bin/python3 -m src.main digest
Environment="PATH=/usr/bin:/usr/local/bin"
```

Создайте таймер `/etc/systemd/system/telegram-digest-bot.timer`:

```ini
[Unit]
Description=Run Telegram Digest Bot weekly
Requires=telegram-digest-bot.service

[Timer]
OnCalendar=Mon *-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Активируйте таймер:
```bash
sudo systemctl enable telegram-digest-bot.timer
sudo systemctl start telegram-digest-bot.timer
```

## Разработка

### Отладка

Включите отладочные логи для диагностики:

```bash
python -m src.main sync --debug
python -m src.main digest --debug --dry-run
```

Флаг `--debug` включает подробные логи взаимодействия с Telegram API и LLM провайдерами.

### Тестирование

```bash
# Тест синхронизации
python -m src.main sync --debug

# Тест генерации дайджеста (без отправки)
python -m src.main digest --dry-run

# Тест с другой моделью
python -m src.main digest --dry-run --model openrouter/google/gemini-flash-1.5

# Тест с Ollama
python -m src.main digest --dry-run --provider ollama --model llama3
```

### Структура проекта

```
telegram-bot/
├── src/
│   ├── bot.py              # Основная логика бота
│   ├── config.py            # Конфигурация и настройки
│   ├── digest.py            # Генерация дайджестов
│   ├── main.py              # CLI интерфейс
│   ├── openrouter_client.py # Клиенты для LLM (OpenRouter/Ollama)
│   ├── prompts.py           # Промпты для генерации дайджестов
│   ├── storage.py            # Работа с базой данных
│   └── sync_service.py      # Синхронизация с Telegram
├── .env                     # Конфигурация (не в git)
├── .env.example             # Пример конфигурации
├── messages.db              # База данных SQLite (не в git)
├── pyproject.toml           # Метаданные проекта
├── requirements.txt         # Зависимости
└── README.md                # Документация
```

## Решение проблем

### Бот не получает сообщения

1. Убедитесь, что бот добавлен в группу/канал
2. Проверьте, что бот имеет права на чтение сообщений
3. Запустите `sync` с флагом `--debug` для диагностики

### Ошибка "Некорректные переменные окружения"

Проверьте, что все обязательные переменные заполнены в `.env`:
- `TELEGRAM_BOT_TOKEN` (обязательно)
- `OPENROUTER_API_KEY` (если используете OpenRouter)
- `OLLAMA_BASE_URL` и `OLLAMA_MODEL` (если используете Ollama)

### Ошибка подключения к OpenRouter

1. Проверьте правильность API ключа
2. Убедитесь, что модель доступна (см. [free_models.md](free_models.md))
3. Проверьте интернет-соединение

### Ошибка подключения к Ollama

1. Убедитесь, что Ollama запущен: `ollama serve`
2. Проверьте, что модель установлена: `ollama list`
3. Проверьте `OLLAMA_BASE_URL` в `.env`

### База данных пустая после sync

1. Убедитесь, что в чатах есть текстовые сообщения (бот сохраняет только текстовые)
2. Проверьте, что бот имеет доступ к чату
3. Запустите `sync` с `--debug` для диагностики

### Дайджест не отправляется

1. Проверьте права бота на отправку сообщений в чат
2. Убедитесь, что в базе есть сообщения: `python -m src.main list-chats`
3. Попробуйте `--dry-run` для проверки генерации

## Лицензия

[Укажите лицензию проекта]

## Поддержка

[Укажите способ связи для поддержки]

