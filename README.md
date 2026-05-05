# Telemetry Semantic Search

REST-сервис на FastAPI, который принимает запросы на естественном языке
(русский или английский), классифицирует их через бесплатные LLM
OpenRouter и отдаёт релевантный срез по NovAtel GNSS/INS-телеметрии.

Архитектурные решения — в [architecture.md](architecture.md).

## Архитектура

```
data/data.csv
tests/
app/
├── main.py            # FastAPI: lifespan, /query, /health
├── config.py          # pydantic-settings (env-vars + .env)
├── schemas.py         # Pydantic-модели запроса/ответа + Intent
├── logging_config.py  # единая настройка логирования
├── llm/
│   ├── client.py      # OpenRouter client + retry + JSON-парсинг
│   └── prompts.py     # системный промпт классификатора
├── data/
│   └── loader.py      # Polars: чтение CSV + производные поля
└── handlers/
    ├── base.py        # реестр + dispatch
    ├── max_speed.py
    ├── bad_quality.py
    ├── twilight_position.py
    ├── hard_braking.py
    └── m11_route.py
```

Поток запроса:

```
POST /query  ──►  classify_intent (OpenRouter)  ──►  HANDLERS[intent]  ──►  Polars frame
```

Данные читаются один раз при старте (lifespan), все производные поля
(`horizontal_speed`, `acceleration`, `datetime_msk`, `hour_msk`)
вычисляются одним проходом и хранятся в памяти как иммутабельный
`polars.DataFrame`.

## Запуск через Docker (рекомендуемый способ)

```bash
cp .env.example .env
# вставьте свой OPENROUTER_API_KEY
docker compose up --build
```

Сервис поднимется на `http://localhost:8000`. Документация — `/docs`.

## Локальный запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-v1-...
uvicorn app.main:app --reload
```

## Примеры запросов

```bash
curl -s http://localhost:8000/health | jq
```

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Какая была максимальная скорость?"}' | jq
```

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Где были проблемы с GPS?"}' | jq
```

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Найди резкие торможения"}' | jq
```

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Когда тягач ехал по М11?"}' | jq
```

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Положение в сумерках"}' | jq
```

## Поддерживаемые интенты

| intent              | описание                                          |
|---------------------|---------------------------------------------------|
| `max_speed`         | максимум `horizontal_speed`, время и координаты   |
| `bad_quality`       | строки `pos_type__type == 19`, % от поездки       |
| `twilight_position` | срез по MSK 16:00–19:00                           |
| `hard_braking`      | события с ускорением `< -2 м/с²`, сгруппированные |
| `m11_route`         | геобокс `lat 55.5–60.0, lon 30.0–37.5`            |
| `unknown`           | fallback с подсказкой по поддерживаемым сценариям |

LLM сам подбирает интент: формулировки вроде «максималка», «top speed»,
«где fix терялся», «на закате», «по трассе М11» сводятся к одному из
этих ярлыков. Список интентов и их пороги — единственное «жёсткое»
знание системы, всё остальное делегируется модели.

## Конфигурация

Все настройки читаются из переменных окружения / `.env` (см. [`app/config.py`](../../../app/config.py)):

| ENV                       | по умолчанию                         |
|---------------------------|--------------------------------------|
| `OPENROUTER_API_KEY`      | — (обязательная)                     |
| `OPENROUTER_MODEL`        | `mistralai/mistral-7b-instruct:free` |
| `OPENROUTER_TIMEOUT`      | `30.0` (сек)                         |
| `OPENROUTER_MAX_RETRIES`  | `3`                                  |
| `DATA_PATH`               | `data/data.csv`                      |
| `RESPONSE_MAX_POINTS`     | `100` (предел точек в ответе)        |
| `LOG_LEVEL`               | `INFO`                               |

Пороги (`twilight_*_hour`, `hard_braking_threshold`, `m11_*`) тоже
настраиваются через ENV, но имеют разумные дефолты из ТЗ.

## Тесты

```bash
pip install -r requirements-dev.txt
pytest
```

Покрытие:
- `tests/test_data_loader.py` — производные метрики и загрузка реального CSV;
- `tests/test_handlers.py` — все 5 хендлеров на синтетическом датасете;
- `tests/test_llm.py` — устойчивый JSON-парсинг вывода LLM (markdown-фенсы, неизвестные ярлыки).

## Обработка ошибок

| Ситуация                     | Поведение                                     |
|------------------------------|-----------------------------------------------|
| LLM вернул не-JSON           | regex вытаскивает первый JSON-блок            |
| LLM вернул неизвестный ярлык | мапим в `unknown`, отдаём подсказку           |
| Таймаут / 5xx / 429          | 3 ретрая с экспоненциальной задержкой         |
| 4xx (кроме 429)              | `502 LLM error`                               |
| Нет API-ключа                | `502 LLM error: OPENROUTER_API_KEY ...`       |
| Внутренний сбой              | `500 internal_error` + лог traceback          |
