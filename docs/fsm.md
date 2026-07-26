# How FSM Works in Momentum

## What FSM means

FSM means **Finite State Machine**. In a Telegram bot, it is short-term memory that tells
the bot which step of a conversation a user is currently on.

Without FSM, these two messages are just unrelated updates:

```text
User: /suggest
User: Please add workout goals
```

With FSM, the bot remembers that after `/suggest` it is waiting for suggestion text, so it
knows what the second message means.

An FSM record has two parts:

```text
state: the current step
data:  temporary values collected during the flow
```

For example:

```text
state = "Suggestion:awaiting_text"
data  = {"prompt_id": 12345}
```

The state decides which handlers are allowed to run. The data carries values from one
step to another.

## The main pieces in aiogram

### State and StatesGroup

Momentum declares its states in `src/momentum/states.py`:

```python
class Suggestion(StatesGroup):
    awaiting_text = State()
```

`StatesGroup` groups related states under one flow name. `State()` is a marker for one
step. Internally, aiogram turns this state into the string:

```text
Suggestion:awaiting_text
```

The state object does not execute code and does not automatically move to another state.
The application must call `set_state()` explicitly.

### FSMContext

Aiogram injects an `FSMContext` argument into handlers:

```python
async def start_suggestion(message: Message, state: FSMContext) -> None:
    ...
```

It is a small interface to the current user's FSM record:

- `set_state(...)` changes the current step.
- `get_state()` returns the current step.
- `update_data(...)` adds or replaces temporary values.
- `get_data()` returns all temporary values.
- `clear()` removes both the state and all temporary data.

Conceptually, `clear()` does this:

```python
await state.set_state(None)
await state.set_data({})
```

### Storage

Momentum creates its dispatcher with `MemoryStorage` in `src/momentum/app.py`:

```python
dp = Dispatcher(storage=MemoryStorage())
```

`MemoryStorage` is an in-memory Python dictionary. Each entry contains:

```text
MemoryStorageRecord(
    state="Suggestion:awaiting_text",
    data={"prompt_id": 12345},
)
```

The default aiogram strategy is `USER_IN_CHAT`. The dictionary key identifies the bot,
chat, and user. Therefore, Alice and Bob have separate states, and one user's flow does
not replace another user's flow.

In a private Telegram chat, a simplified view is:

```text
(bot=Momentum, chat=Alice, user=Alice) -> Alice's state and data
(bot=Momentum, chat=Bob,   user=Bob)   -> Bob's state and data
```

Because this storage is only RAM:

- Restarting the bot deletes all unfinished FSM flows.
- Deploying a new version also deletes unfinished flows.
- Completed workouts and suggestions remain safe because they are stored in SQLite.
- Multiple bot processes would not share FSM state.

This behavior is acceptable for the current application: losing an unfinished form is
not the same as losing saved data.

### FSM middleware

For every Telegram update, aiogram's FSM middleware:

1. Determines the bot, chat, and user.
2. Builds the storage key.
3. Reads that key's current state.
4. Creates an `FSMContext`.
5. Adds `state` and `raw_state` to the handler data.
6. Starts handler matching.

That is why application handlers can request `state: FSMContext` without constructing it.
Aiogram's dependency injection supplies it.

Momentum does not configure event isolation, so aiogram uses its disabled-isolation
default. Two updates from the same user that arrive almost simultaneously can therefore
run concurrently. The current flows are simple and normally receive one action at a
time, but this is worth reconsidering if the bot becomes busier or runs flows where
double submission would be costly.

## How handlers use state

A decorator registers a function and its filters:

```python
@router.message(Suggestion.awaiting_text, F.text)
async def save_suggestion(...):
    ...
```

This handler requires all of the following:

1. The update is a Telegram message.
2. The current state equals `Suggestion:awaiting_text`.
3. The message has text.

When an update arrives, the dispatcher checks registered handlers in router and
registration order. It runs the first matching handler for that event.

A state marker used in a decorator is therefore a filter. Under the hood it compares the
stored raw state string with its own full state string.

Handlers can also filter callback queries from inline buttons:

```python
@router.callback_query(AddWorkout.choosing_kind, KindCB.filter())
```

This requires both the correct current state and callback-data format. A button intended
for another step should not activate this handler.

## Suggestion flow

The suggestion feature has one state:

```text
no state -> awaiting_text -> no state
```

### Step 1: enter the flow

The `/suggest` command runs `start_suggestion()`:

```python
await state.clear()
await state.set_state(Suggestion.awaiting_text)
prompt = await message.answer(...)
await state.update_data(prompt_id=prompt.message_id)
```

The initial `clear()` abandons any unfinished flow for this user. The bot then sets the
new state, sends its question, and remembers the question's Telegram message ID.

The temporary record now resembles:

```text
state = "Suggestion:awaiting_text"
data  = {"prompt_id": 12345}
```

### Step 2: receive valid text

If the user sends:

```text
Please add monthly workout goals
```

the `awaiting_text + F.text` handler matches. It:

1. Trims surrounding whitespace.
2. Rejects an empty result without changing state.
3. Writes the request to SQLite.
4. Reads the stored `prompt_id`.
5. Clears the FSM.
6. Removes the old Cancel button.
7. Sends confirmation and the main menu.

The important boundary is:

```text
FSM data       = temporary conversation data
SQLite data    = permanent application data
```

The suggestion exists permanently only after `repo.add_improvement_request()` commits it
to SQLite.

### Invalid input

This fallback handler has a state filter but no `F.text` filter:

```python
@router.message(Suggestion.awaiting_text)
async def suggestion_invalid(message: Message) -> None:
    ...
```

It catches a photo, sticker, voice message, or other non-text message while the bot is
waiting for text. It sends an error but does not clear or change the state, so the user
can try again.

### Cancellation

The inline Cancel button is handled globally in `handlers/common.py`. Its callback data
contains the action `cancel`. The global handler clears the state and edits the prompt to
say that the action was cancelled.

The `/cancel` command performs the same state cleanup with a new reply message.

No suggestion is inserted because cancellation never calls the repository.

## Add-workout flow

Adding a workout demonstrates a branching, multi-step FSM:

```text
                          +-> cardio_photo -> cardio_description --+
no state -> choosing_kind                                         +-> choosing_date
                          +-> strength_parts -> strength_description+
                                                                    |
                                       save <- today/yesterday <----+
                                       save <- custom_date <---------+
```

### Entry

`/add` clears an old flow and sets:

```text
state = "AddWorkout:choosing_kind"
data  = {"prompt_id": ...}
```

### Cardio branch

After the user selects cardio:

```text
state = cardio_photo
data  = {"kind": "cardio", "prompt_id": ...}
```

If a photo arrives, its Telegram `file_id` is added to data. If Skip is pressed, no photo
ID is added. Both paths then move to `cardio_description`.

After description or Skip, the flow moves to `choosing_date`.

### Strength branch

After the user selects strength:

```text
state = strength_parts
data  = {
    "kind": "strength",
    "parts": [],
    "prompt_id": ...,
}
```

Every body-part button updates `parts` but leaves the state unchanged. This allows any
number of toggle actions while remaining on the same step.

Pressing Done validates that at least one part is selected, then moves to
`strength_description`, followed by `choosing_date`.

### Date and completion

Today and Yesterday can finish directly from `choosing_date`. Choosing a custom date
moves to `custom_date`, where the next text message is parsed and validated.

At completion, `_finish()`:

1. Reads all temporary FSM data.
2. Clears the FSM.
3. Inserts the workout and body parts into SQLite.
4. Reads the saved workout and current weekly progress.
5. Sends the finished card.

Typical cardio data before completion:

```python
{
    "kind": "cardio",
    "photo_file_id": "telegram-file-id",
    "description": "30 minute run",
    "prompt_id": 12345,
}
```

Typical strength data:

```python
{
    "kind": "strength",
    "parts": ["chest", "arms"],
    "description": "Bench press and curls",
    "prompt_id": 12345,
}
```

## Edit-workout flows

Editing uses two independent states:

```text
EditWorkout.awaiting_description
EditWorkout.awaiting_date
```

When an edit button is pressed, the handler stores:

```python
{
    "workout_id": 42,
    "page": 2,
}
```

`workout_id` identifies what to update. `page` remembers which history page to show
afterward.

For description editing:

```text
press Description -> awaiting_description -> receive text -> update SQLite -> clear
```

For date editing:

```text
press Date -> awaiting_date -> receive valid date -> update SQLite -> clear
```

An invalid date leaves the state active so the user can correct it.

## Why `prompt_id` is stored

Inline keyboards remain attached to old Telegram messages unless the bot edits those
messages. A stale Cancel, Skip, or Done button could otherwise be clicked after the user
has already moved to another step.

Momentum remembers the latest prompt's message ID in FSM data. When the user replies, the
bot removes that prompt's keyboard and updates or clears `prompt_id`.

This is UI bookkeeping, not permanent domain data, so FSM storage is the correct place
for it.

## Global reset behavior

Several entry points deliberately call `state.clear()`:

- `/start`
- `/cancel`
- the Cancel inline button
- starting `/add`
- starting `/suggest`
- opening history or a workout
- successfully completing a flow

This prevents data from an old unfinished flow from leaking into a new one.

For example, if a user begins adding a strength workout and then sends `/suggest`, the
partially collected workout fields are discarded before the suggestion flow starts.

## Practical rules for new flows

When adding another FSM flow to Momentum:

1. Define a dedicated `StatesGroup` in `states.py`.
2. Clear incompatible previous state at the entry command.
3. Set the state before waiting for the next update.
4. Store only temporary conversation values in FSM data.
5. Use state and content filters together for valid input.
6. Add a state-only fallback for invalid input.
7. Keep the same state after recoverable validation errors.
8. Remove stale inline keyboards.
9. Write permanent data through `db/repo.py`.
10. Clear FSM state when the flow succeeds or is cancelled.

Do not treat FSM storage as a database. It coordinates an unfinished conversation; SQLite
stores completed application records.
