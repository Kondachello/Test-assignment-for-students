# Архитектура

## Общая схема

```
HTTP-запрос
   │
   ▼
FastAPI (/query)
   │
   ▼
LLM-классификатор интента ──► OpenRouter (httpx + tenacity)
   │
   ▼
Реестр хендлеров (Intent → handler)
   │
   ▼
TelemetryStore (Polars DataFrame, in-memory)
   │
   ▼
JSON-ответ {status, query, intent, result}
```

## Ключевые решения

### LLM — только классификатор интента

LLM получает закрытый список из 6 ярлыков (`max_speed`, `bad_quality`, `twilight_position`, `hard_braking`, `m11_route`, `unknown`) и возвращает JSON с одним полем `intent`. Все числовые вычисления — детерминированный Polars-код. Это даёт нулевые галлюцинации по числам и сохраняет языковую обобщающую способность модели.

### Singleton-store через `lifespan`

CSV читается один раз при старте, обогащается производными полями (`horizontal_speed`, `speed_kmh`, `acceleration`, `datetime_msk`, `hour_msk`) и хранится как иммутабельный `DataFrame` в `app.state`. Все хендлеры — чистые функции `(store, settings) → dict`.

### Реестр хендлеров (Strategy + decorator-register)

`HANDLERS: dict[Intent, QueryHandler]` заполняется при импорте модулей. Добавление интента = новый файл + `@register(Intent.X)`, без правок диспетчера.

### Устойчивость LLM-клиента

- `tenacity` с экспоненциальным backoff на 5xx/429/transport-ошибках.
- Регэксп-фоллбек, выдёргивающий первый JSON-объект из ответа.
- Неизвестные ярлыки маппятся в `Intent.UNKNOWN` вместо падения.

### Конфигурация через pydantic-settings

Все магические числа из ТЗ (пороги, bbox M11, MSK-смещение, окно сумерек) вынесены в `Settings` и читаются из `.env`. Это упрощает тесты (в фикстурах подменяем `model_copy(update=...)`) и позволяет менять пороги без правок кода.

### Таймзоны

В CSV таймстемпы без TZ — считаем UTC. Для «сумерек» (16:00–19:00 MSK) добавляем фиксированное смещение `+3 ч` и фильтруем по `hour_msk`.

### `acceleration[0] = 0`

Первый сэмпл не имеет соседа слева, поэтому `diff` даёт `null`. Заполняем нулём, чтобы фильтр `acceleration < -2` не ловил NaN.

### Серии торможения

Подряд идущие сэмплы с `acceleration < threshold` группируются через `cum_sum` по флагу-флипу (классический трюк run-length encoding в Polars). В каждом событии берётся пиковая децелерация и сэмплы до/после события для отчёта о скорости.

## Структура

```
app/
├── main.py              FastAPI, lifespan, /query, /health
├── config.py            pydantic Settings
├── schemas.py           Intent, QueryRequest, QueryResponse
├── logging_config.py    stdout-логгер
├── data/loader.py       TelemetryStore + enrich
├── llm/
│   ├── client.py        OpenRouter, ретраи, парсинг JSON
│   └── prompts.py       системный промпт с описанием интентов
└── handlers/
    ├── base.py          реестр + dispatch
    ├── serialization.py хелперы для JSON
    ├── max_speed.py
    ├── bad_quality.py
    ├── twilight_position.py
    ├── hard_braking.py
    └── m11_route.py
```
