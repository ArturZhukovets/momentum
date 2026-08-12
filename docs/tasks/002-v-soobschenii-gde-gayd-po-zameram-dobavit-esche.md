# Improve measurement-flow copy: frequency note, imperative prompts, "parameters" label

## Idea
> В сообщении, где гайд по замерам
> Добавить еще текст
> Замеры желательно но делать раз в неделю утром и натощак❗️
>
> И сразу после этого сообщения выходит текст «обхват груди в сантиметрах», добавить слово «УКАЖИТЕ обхват груди в см», возможно во всех сообщ можно добавить это слово
>
> Мэйби заменить «замер сохранен» на «Ваши параметры»

Three copy tweaks to the `/measure` body-measurement flow: (1) add a note to the guide
message recommending measuring once a week, in the morning, on an empty stomach; (2) make
the circumference prompts imperative ("УКАЖИТЕ обхват груди в см" instead of "Обхват груди
в сантиметрах"), and apply the same imperative phrasing to the other prompts too; (3)
maybe rename the "Замер сохранён" confirmation to "Ваши параметры".

## Verdict
Relevant: yes — touches only `/measure` copy in `texts/profile.py`.
Already implemented: no.
Feasible: yes — pure string edits, no schema/handler-logic changes.

## Current state
- `src/momentum/texts/profile.py:136-143` — `MEASURE_GUIDE`, sent once in
  `src/momentum/handlers/measure.py:94` (`start_body_measure`) right before the first
  circumference question is asked via `_ask_girth(bot, callback.message.chat.id, state,
  index=0)` (`measure.py:95,105-108`). No mention of frequency/timing today.
- `src/momentum/texts/profile.py:125-129` — girth prompts `ASK_CHEST`, `ASK_WAIST`,
  `ASK_HIPS`, `ASK_THIGH`, `ASK_ARM`, all phrased as noun phrases ("Обхват груди в
  сантиметрах (например, 90)"), consumed via `_MEASURE_STEPS` in `measure.py:30-36` and
  rendered with `send_prompt`/`edit_prompt` (`handlers/_prompts.py`).
- `src/momentum/texts/profile.py:124` — `ASK_MEASURE_WEIGHT` ("Укажи свой текущий вес в
  килограммах...") is already imperative-ish ("Укажи"), used in `measure.py:60,43`.
- `src/momentum/texts/profile.py:184` — `MEASURE_SAVED = "✅ Замер сохранён."`, used in
  `measure.py:202`: `f"{texts_profile.MEASURE_SAVED}\n\n{card}"`, where `card` is built by
  `fmt_profile.measurement_card(measurement)` and already lists the individual values
  (weight, chest, waist, etc. — see `src/momentum/formatters/profile.py`), so "Ваши
  параметры" as a heading above that card reads naturally.

## Implementation plan
1. `src/momentum/texts/profile.py` — extend `MEASURE_GUIDE` with an added paragraph
   recommending weekly, morning, fasted measurements, keeping the existing "❗️ Важно
   каждый раз мерить в одном и том же месте" line and its style (short paragraphs,
   blank-line separated, occasional emoji). Suggested addition, placed as the last
   paragraph: `"❗️ Замеры желательно делать раз в неделю, утром и натощак"`.
2. `src/momentum/texts/profile.py` — reword `ASK_CHEST`, `ASK_WAIST`, `ASK_HIPS`,
   `ASK_THIGH`, `ASK_ARM` to the imperative form requested ("Укажите обхват груди в
   сантиметрах (например, 90)", etc.), mirroring the existing `ASK_MEASURE_WEIGHT` and
   `ASK_HEIGHT`/`ASK_TARGET_WEIGHT` phrasing ("Укажи ...") for consistency — pick "Укажите"
   (formal, matches the suggestion's capitalised ask) vs the bot's existing informal
   "Укажи"/"ты" register used everywhere else (`ASK_BIRTH_DATE` "Когда ты родился?",
   `ASK_MEASURE_WEIGHT` "Укажи свой текущий вес"). **Decision: use "Укажи" (informal,
   lower-case) to stay consistent with the bot's existing tone** rather than "УКАЖИТЕ"
   verbatim — call out in Additional suggestions that the request's formal/caps form
   clashes with the established voice. Only `ASK_CHEST`/`ASK_WAIST`/`ASK_HIPS`/
   `ASK_THIGH`/`ASK_ARM` need changing; `ASK_MEASURE_WEIGHT` already starts with "Укажи".
3. `src/momentum/texts/profile.py:184` — change `MEASURE_SAVED` from `"✅ Замер сохранён."`
   to `"✅ Ваши параметры:"` (colon, since the card with values follows immediately in
   `measure.py:202`) — keeps the existing `f"{texts_profile.MEASURE_SAVED}\n\n{card}"`
   composition in `handlers/measure.py` working unchanged.
4. No handler, keyboard, or schema changes required — `measure.py`, `formatters/profile.py`
   and `db/measurements.py` stay untouched since only the string constants change.

## User-facing copy
`texts/profile.py` (`momentum.texts.profile`):
- `MEASURE_GUIDE` — append a line recommending weekly, morning, fasted measurements.
- `ASK_CHEST`, `ASK_WAIST`, `ASK_HIPS`, `ASK_THIGH`, `ASK_ARM` — reword to imperative
  "Укажи обхват ... в сантиметрах (например, N)" form.
- `MEASURE_SAVED` — reword from "Замер сохранён" to "Ваши параметры" (as a heading before
  the measurement card).
