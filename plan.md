# План: профиль пользователя, цели и замеры

Собираем опциональные данные о пользователе (профиль), его цель и историю
телесных замеров. Точка сбора — онбординг-FSM после `/start`; правка и
добавление — отдельными командами позже.

Границы ответственности:

- `users` пишет только Telegram/middleware (identity). Не трогаем.
- Всё, что спрашивает бот, — в новые доменные таблицы, каждая scoped by `user_id`.

## 1. Схема (`db/schema.sql`)

Добавить три таблицы + индексы (идемпотентно, как остальное). Итоговый DDL:

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    sex         TEXT    CHECK (sex IN ('male','female')),
    birth_date  TEXT,                                        -- 'YYYY-MM-DD'
    height_cm   REAL    CHECK (height_cm IS NULL OR height_cm > 0),
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS user_goals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    goal_type        TEXT    NOT NULL
                             CHECK (goal_type IN ('lose','gain','maintain','muscle')),
    start_weight_kg  REAL    CHECK (start_weight_kg IS NULL OR start_weight_kg > 0),
    target_weight_kg REAL    CHECK (target_weight_kg IS NULL OR target_weight_kg > 0),
    target_date      TEXT,
    note             TEXT    NOT NULL DEFAULT '',
    is_active        INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_user_goals_active
    ON user_goals(user_id) WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS body_measurements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    recorded_on   TEXT    NOT NULL,                          -- 'YYYY-MM-DD'
    weight_kg     REAL    CHECK (weight_kg IS NULL OR weight_kg > 0),
    waist_cm      REAL,   -- талия
    chest_cm      REAL,   -- грудь
    hips_cm       REAL,   -- бёдра
    thigh_cm      REAL,   -- бедро
    arm_cm        REAL,   -- рука
    note          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_body_measurements_user_date
    ON body_measurements(user_id, recorded_on);
```



## 2. Модели (`db/models.py`)

Frozen dataclasses: `UserProfile`, `UserGoal`, `BodyMeasurement`.

- `birth_date`/`target_date`/`recorded_on` → `date | None`, конвертация через
существующие `to_date`/`ISO_DATE` на границе `db/`.
- Литералы: `Sex = Literal["male","female"]`,
`GoalType = Literal["lose","gain","maintain","muscle"]`.



## 3. SQL-слой (новые submodule'и в `db/`)

Каждый запрос scoped by `user_id`. Ничего не реэкспортим через `__init__.py`.

- `db/profiles.py` — `get_profile(user_id)`, `upsert_profile(...)` (обновляет `updated_at`).
- `db/goals.py` — `get_active_goal(user_id)`, `create_goal(...)`.
(Смена/архивация активной цели — позже; пока считаем, что цель одна.)
- `db/measurements.py` — `add_measurement(...)`, `latest_measurement(user_id)`,
`list_measurements(user_id, limit, offset)`.



## 4. Состояния (`states.py`)

`Onboarding` FSM (`MemoryStorage`), шаги с возможностью «Пропустить»:
`birth_date → sex → height_cm → goal_type → target_weight → first_measurement`.
Базовое (ДР/пол/рост) — на старте; шаги цели и замера можно скипнуть.

## 5. Callbacks и клавиатуры

- `keyboards/callbacks.py` — новые фабрики: `SexCB`, `GoalTypeCB`, `SkipCB`.
- `keyboards/profile.py` — инлайн-клавиатуры выбора пола/типа цели + кнопка «Пропустить».
Переиспользовать паттерн `_drop_prompt_kb` из `handlers/add_workout.py`.



## 6. Тексты (`texts/profile.py`)

Все русские строки онбординга/профиля/замеров. Инлайн-строк в коде нет.

## 7. Форматтеры (`formatters/profile.py`)

Рендер профиля, активной цели и «прогресса»
(текущий вес vs `start_weight_kg`/`target_weight_kg`).

## 8. Хендлеры (`handlers/profile.py`, новый Router)

- `/start` → запуск `Onboarding` FSM (строка `users` уже есть благодаря middleware;
FSM только заполняет доменные таблицы).
- `/profile` → показать/редактировать профиль.
- `/measure` → добавить новый замер.
- `/goal` → показать активную цель.
- Зарегистрировать router в `app.build_dispatcher()` рядом с
`common`, `add_workout`, `history`, `reports`.



## 9. Прогресс-аналитика (позже, `services/`) НЕ ВЫПОЛНЯТЬ!

Чистые функции (по образцу `services/stats.py`): динамика веса/обмеров,
% до цели, наложение на историю тренировок. Переиспользуемо в командах и отчётах.

## Отложено (не в этой итерации)

- Создание новой цели при наличии активной (архивация `is_active`).
- Редактирование/удаление отдельных замеров.
- `services/` прогресс-аналитика и графики.

