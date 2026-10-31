# Спрашивай темп цели вместо срока и показывай его в отчётах

## WHAT

> Заменить в `user_goals` неиспользуемую колонку `target_date` на `target_rate_kg_per_month`, спросить темп кнопками в goal-FSM, посчитать фактический темп изменения веса по истории взвешиваний и добавить в недельный/месячный отчёт строку «идёшь быстрее плана / в графике / отстаёшь».

Отчёты сейчас отвечают на вопрос «что изменилось», но не на вопрос «успеваю ли я». `ReportBody` даёт дельту веса за период и остаток до таргета, но ни фактической скорости, ни ожидаемой в данных нет.

## WHY

Колонка `target_date` существует в схеме (`db/tables.py`), в модели и в `create_goal`, `formatters/profile.py` её даже печатает — но ни один FSM-шаг её не спрашивает, поэтому она всегда `NULL`. Без плановой скорости требуемый темп не из чего вывести.

Спрашивать срок — плохой вариант, и по психологии, и по данным: дата это обещание, которое протухает ровно в тот момент, когда пользователь отстал, и превращает отчёт в «до цели 3 недели, осталось 6 кг». Темп («сколько кг в месяц») остаётся корректным всегда, говорит о поведении, а не о провале срока, поддаётся проверке на безопасность и служит прямым входом в будущий калорийный слой (1 кг ≈ 7700 ккал).

## Вердикт

Относится к боту: да.
Уже реализовано: нет. Колонка `target_date` есть, но не заполняется ничем; расчёта темпа в проекте нет (`services/` содержит `periods`, `stats`, `measurements`, `workout_types`, `reports`).
Реализуемо: да. Новых зависимостей не требуется, регрессия — десяток строк арифметики без numpy. Единственное узкое место — batch-миграция SQLite (см. T-1).

## План

Интерпретация: строка темпа должна появиться одновременно в `/week`, `/month` и в рассылке планировщика — все трое уже сходятся в `build_weekly_text` / `build_monthly_text`, поэтому `handlers/reports.py` и `scheduler.py` не трогаем.

Решения, принятые до начала работы:
- храним темп, а не производную от него дату — дата считается на лету как прогноз от *сегодняшнего* веса и потому не устаревает;
- пресеты темпа **фиксированные, в кг/месяц** (не в процентах от массы): в онбординге вопрос про цель идёт до вопроса про текущий вес, так что вес на этом шаге может быть неизвестен;
- `target_date` удаляется полностью, а не остаётся «на будущее».

### T-1 — Схема: колонка темпа вместо даты

В `db/tables.py`, класс `UserGoal`: удалить `target_date`, добавить `target_rate_kg_per_month: Mapped[float | None] = mapped_column(Float)` и `CheckConstraint("target_rate_kg_per_month IS NULL OR target_rate_kg_per_month > 0")` рядом с существующими чеками. Хранится **модуль без знака** — направление берётся из `goal_type`, чтобы значение не могло противоречить типу цели.

Затем `uv run alembic revision --autogenerate -m "goal rate instead of target date"` и **прочитать сгенерированный файл до коммита**. Два места под особым вниманием, потому что `render_as_batch=True` пересобирает таблицу из отражённого DDL:

- partial-индекс `ux_user_goals_active` (`sqlite_where=text("is_active = 1")`) — отражение `WHERE` у SQLite не гарантировано, поэтому индекс, скорее всего, придётся явно дропнуть и пересоздать внутри миграции. Если `WHERE` потеряется, инвариант «одна активная цель на пользователя» молча превратится в «одна цель вообще»;
- table-level `FOREIGN KEY ... ON DELETE CASCADE` — см. `docs/db-rebuild.md`.

После `upgrade head` повторный `--autogenerate` обязан выдать пустую миграцию.

Дальше по слоям: `db/models.py` — поле в датаклассе `UserGoal`; `db/goals.py` — `_goal_from_row` и параметр `create_goal(target_rate_kg_per_month=...)` вместо `target_date`.

Перед выкаткой проверить прод: `sqlite3 data/momentum.db "select id, target_date from user_goals;"` — если везде `NULL`, потери данных нет.

### T-2 — Вопрос о темпе в goal-FSM

Пресеты — константа в новом `services/pace.py` (например `RATE_PRESETS: dict[GoalType, tuple[float, ...]]`), отдельные для `muscle`: мышцы растут ~0.5–1 кг/мес даже у новичка, предлагать там «3 кг/мес» значит обещать воду и жир. Русские подписи — только в `texts/profile.py`.

- `states.py` — `Onboarding.goal_rate` после `target_weight`;
- `keyboards/callbacks.py` — `GoalRateCB` (свой префикс, например `grate`) с `value: float`;
- `keyboards/profile.py` — `goal_rate_kb(goal_type, step=..., cancel=...)` по образцу `goal_type_kb`: кнопки пресетов + `_skip_button(step)`;
- `handlers/_profile_common.py` — `STEP_GOAL_RATE = "rate"`; добавить `GoalRateCB` в декораторы `ignore_stale_click`;
- `handlers/onboarding.py` — `_ask_goal_rate` / `got_goal_rate` / `skip_goal_rate` между `got_target_weight`–`skip_target_weight` и `_after_goal_steps`. При `goal_type == "maintain"` шаг пропускается целиком (темп там по определению ноль). Значение кладётся в `state.update_data` и прорастает в оба места сохранения — `_save_goal_only` и `_finish_onboarding`;
- фоллбэк `expects_button` внизу модуля — добавить `Onboarding.goal_rate` в `StateFilter`, как у `sex` и `goal_type`.

Формулировка вопроса — про скорость, не про срок: «С какой скоростью хочешь двигаться?». Шаг скипаемый, как все остальные.

### T-3 — `services/pace.py`: фактический темп

Новый **чистый** модуль, тот же контракт, что у `services/stats.py` и `services/measurements.py`: строки и даты на вход, фрозен-датакласс на выход, ни aiogram, ни сессий БД, ни русского текста.

```python
PaceStatus = Literal["ahead", "on_track", "behind", "stalled", "unsafe", "none"]

@dataclass(frozen=True)
class PaceStats:
    actual_kg_per_week: float
    required_kg_per_week: float | None
    projected_date: date | None
    status: PaceStatus
    points: int
```

- `pace_range(ref)` — окно выборки (8–12 недель назад от `ref`), по образцу `stats.weekly_range`;
- `build_pace(rows, goal, ref)` — фактический темп линейной регрессией (МНК вручную, ~10 строк, без numpy) по всем весам в окне. Именно регрессией, а не «первое минус последнее»: вес скачет на ±1 кг в сутки от воды, соли и еды, и одна выпадающая точка на краю перевернула бы вывод на противоположный;
- `required_kg_per_week` = `goal.target_rate_kg_per_month / 4.345`; знак определяется по `goal_type`, как в `measurements.delta_is_good`;
- `projected_date` — экстраполяция до `target_weight_kg`; `None`, если темп нулевой или направлен от цели, иначе получится дата в 2043 году.

Граничные случаи закладывать прямо в код — тестов в проекте нет:

| Случай | Поведение |
|---|---|
| < 2 взвешиваний в окне | `status="none"`, строка в отчёт не попадает |
| темп не задан (шаг пропущен) | `required=None`, но фактический темп и прогноз показываем |
| `maintain` | логика перевёрнута: хорошо, когда темп около нуля |
| цель достигнута (`tone == "reached"`) | строку темпа не печатать вовсе, иначе «цель достигнута» и следом «отстаёшь» |
| потеря > ~1% массы тела в неделю | `status="unsafe"` |

Порог «около нуля» — переиспользовать идею `WEIGHT_NOISE_KG` из `services/measurements.py`, а не заводить третью константу шума без нужды.

### T-4 — Врезка в отчёты

Новых запросов к БД не нужно: `_report_body()` в `services/reports.py` уже грузит всю историю измерений до `end`, включая до-периодную.

- `services/measurements.py` — поле `pace: PaceStats | None` в `ReportBody`, рядом с `change` / `goal` / `tone` / `kg_left`;
- `services/reports.py`, `_report_body()` — одна строка `pace=build_pace(rows, goal, end)`. Окно обрезает сам `pace.py`, либо передать `start=` в `list_measurements`, чтобы не тащить всю историю;
- `formatters/reports.py` — `_pace_line(body)` после `_tone_line` в `_body_block`; фразы по `status` — в `texts/reports.py` рядом с `tone_progress` / `tone_setback`, числа через `fmt_number`.

### T-5 — Карточка цели и зачистка

`formatters/profile.py` — заменить блок `target_date` на строку темпа; `LABEL_TARGET_DATE` → `LABEL_TARGET_RATE` в `texts/profile.py`. Проверить `grep -rn target_date src/` — упоминаний остаться не должно.

## Проверка

1. `uv run ruff check . && uv run ruff format .`
2. `uv run alembic upgrade head`, затем `uv run alembic revision --autogenerate -m drift-check` → файл обязан быть пустым (иначе дрейф), после проверки удалить.
3. `sqlite3 data/momentum.db ".schema user_goals"` — после batch-пересборки на месте должны быть и `FOREIGN KEY ... ON DELETE CASCADE`, и `ux_user_goals_active` со своим `WHERE`.
4. `uv run python -m momentum`, в боте:
   - `/goal` без цели → пройти flow, выбрать темп → карточка показывает темп;
   - цель `maintain` → шага про темп нет;
   - пропустить шаг темпа → цель сохраняется, отчёт не падает;
   - `/measure` несколько раз с разными датами и весом → `/week` показывает строку темпа;
   - совсем без замеров → `/week` работает и строку темпа не печатает;
   - клик по протухшей клавиатуре темпа из предыдущего шага ничего не ломает (`SkipCB.step`, `ignore_stale_click`).

Вне скоупа этой задачи: расчёт калорий и BMR (см. `02-energy-layer.md`), LLM-комментарий (см. `03-llm-report-graph.md`), смена и архивирование целей, возврат поля «срок» как альтернативного способа задать темп, кэш посчитанного темпа в БД.
