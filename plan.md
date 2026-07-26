# Admin interface implementation plan

## Goal

Add a private Telegram admin interface that allows a small configuration-based allowlist
of Telegram users to:

- browse and process improvement suggestions;
- browse registered users;
- view another user's workout history and workout details;
- view another user's weekly and monthly reports.

The first configured administrator will be the bot owner. The design must support adding
more administrator Telegram IDs later without introducing database roles.

## Scope and assumptions

- Administrator identity is configured through `ADMIN_USER_IDS`; it is not stored in the
  database.
- Telegram numeric user IDs are the only authorization identifiers. Usernames are display
  data and must never grant access.
- Admin writes are limited to changing an improvement request's status to `new`, `done`,
  or `rejected`.
- Other users' workouts and reports are read-only. Admins cannot add, edit, or delete a
  workout on behalf of another user.
- There is no coach entity, user role, athlete assignment, or per-user access table.
- Existing user flows and keyboards remain unchanged.
- All user-facing copy, including admin copy, is Russian and lives in `texts.py`.
- All SQL remains in `db/repo.py`.

## User experience

### Entry point

`/admin` opens an inline admin menu:

1. **Предложения**
2. **Пользователи**
3. **Закрыть**

An unauthorized user who manually sends `/admin` receives a short access-denied response.
Silently ignoring the command is less clear and makes configuration mistakes harder to
diagnose.

The normal persistent reply keyboard is not changed. Optionally register `/admin` only
for configured admin chats with Telegram command scopes; this improves discoverability
but is not an authorization mechanism.

### Suggestions

The suggestions section opens on requests with status `new` and provides filters for:

- new;
- done;
- rejected;
- all.

Requests are paginated newest first. A list row contains the request ID, submission date,
author name, and a truncated text preview. The detail view contains:

- request ID and current status;
- submission date;
- author's escaped full name;
- Telegram user ID;
- escaped request text;
- buttons for the statuses different from the current status;
- a back button preserving filter and page.

Changing a status:

1. performs one parameterized `UPDATE`;
2. checks whether the request still exists;
3. answers the callback;
4. redraws the detail view with the current database value.

The operation is idempotent. A stale callback for a deleted or unavailable request shows
an alert and returns to the current list where possible.

### Users and workouts

The users section lists registered users newest first. Each row contains the best available
display name, optional `@username`, Telegram ID, and workout count. Use one aggregate SQL
query rather than querying workout count separately for every user.

Selecting a user opens a read-only menu:

- workout history;
- current week report;
- current month report;
- back to users.

Workout history is paginated using the existing page size. Workout cards reuse
`formatters.workout_card()` and retain photo support. Admin-specific detail keyboards
contain only navigation; they must not expose the existing edit or delete callbacks.

Weekly and monthly views call the existing shared report builders with the selected user's
ID:

- `services.reports.build_weekly_text(user_id, today)`;
- `services.reports.build_monthly_text(user_id, today)`.

## Authorization design

### Configuration

Accept `ADMIN_USER_IDS` as a comma-separated string and expose a parsed
`settings.admin_user_ids` property returning an immutable set of positive integers. Keeping
the Pydantic field itself as `str` avoids the default JSON decoding that
`pydantic-settings` applies to collection fields:

```env
ADMIN_USER_IDS=123456789
```

Multiple admins:

```env
ADMIN_USER_IDS=123456789,987654321
```

The field validator/property must:

- trim whitespace;
- reject empty items and non-integers;
- reject zero and negative IDs;
- fail startup when the value is missing or resolves to an empty set.

Document the variable in `.env.example` and the README configuration table. It is not a
secret, although it should be managed with the rest of deployment configuration.

### Filter

Create an `IsAdmin` aiogram filter in a small authorization module, for example
`momentum/auth.py`. It compares `event_from_user.id` against `settings.ADMIN_USER_IDS`.

Apply it at the admin router level to both observer types:

```python
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
```

Because a router-level filter rejects unauthorized events before its handlers run, add a
separate `/admin` fallback handler outside the protected router to return the access-denied
text. Do not add broad fallback callback handlers that could consume callbacks belonging
to other routers.

Every admin callback uses a distinct `adm_...` callback prefix. Authorization must be
performed on every callback update through the router filter; previously rendered inline
buttons are not trusted.

Admin callback data may carry target `user_id`, request ID, workout ID, filter, and page.
These values select resources but never establish authorization. Repository workout
queries must continue to include the selected owner's `user_id` so a workout ID cannot be
accidentally resolved under the wrong user.

## Data and repository changes

### Dataclasses and types

Add immutable repository result models:

```python
ImprovementRequestStatus = Literal["new", "done", "rejected"]

@dataclass(frozen=True)
class ImprovementRequest:
    id: int
    user_id: int
    user_full_name: str
    request_text: str
    status: ImprovementRequestStatus
    created_at: datetime

@dataclass(frozen=True)
class AdminUserSummary:
    user_id: int
    username: str | None
    first_name: str | None
    created_at: datetime
    workout_count: int
```

Parse stored ISO timestamps at the repository boundary, as workout dates are already
parsed there.

### Suggestion queries

Add:

```python
count_improvement_requests(status: ImprovementRequestStatus | None) -> int
list_improvement_requests(
    status: ImprovementRequestStatus | None,
    limit: int,
    offset: int,
) -> list[ImprovementRequest]
get_improvement_request(request_id: int) -> ImprovementRequest | None
set_improvement_request_status(
    request_id: int,
    status: ImprovementRequestStatus,
) -> bool
```

Requirements:

- `None` means all statuses;
- lists use `ORDER BY created_at DESC, id DESC`;
- pagination parameters are bounded by the handler;
- updates use the constrained status type and return `rowcount > 0`;
- each write commits exactly once.

### User queries

Add:

```python
count_users() -> int
list_admin_user_summaries(limit: int, offset: int) -> list[AdminUserSummary]
get_admin_user_summary(user_id: int) -> AdminUserSummary | None
```

The list query uses `LEFT JOIN workouts`, `COUNT(workouts.id)`, and `GROUP BY users.user_id`.
Use deterministic ordering: `users.created_at DESC, users.user_id DESC`.

Existing workout functions remain unchanged and are called with the selected target user:

- `count_workouts(target_user_id)`;
- `list_workouts(target_user_id, limit, offset)`;
- `get_workout(target_user_id, workout_id)`.

### Schema indexes

Add idempotent indexes:

```sql
CREATE INDEX IF NOT EXISTS ix_improvement_requests_status_created
ON improvement_requests(status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_users_created
ON users(created_at DESC);
```

No table or column migration is required.

## Callback and keyboard design

Add dedicated callback factories. Exact names may be adjusted during implementation, but
their responsibilities should remain separate:

```python
class AdminMenuCB(CallbackData, prefix="adm_menu"):
    section: str

class AdminSuggestionCB(CallbackData, prefix="adm_sug"):
    action: str
    status: str
    request_id: int = 0
    page: int = 1

class AdminUserCB(CallbackData, prefix="adm_usr"):
    action: str
    user_id: int = 0
    page: int = 1

class AdminWorkoutCB(CallbackData, prefix="adm_wk"):
    action: str
    user_id: int
    workout_id: int = 0
    page: int = 1
```

Keep packed callback data under Telegram's 64-byte limit. Use short fixed action and status
values and integer identifiers. Do not place names, suggestion text, or other arbitrary
strings in callback data.

Add keyboard builders for:

- admin menu;
- suggestion filters and pagination;
- suggestion detail/status actions;
- user pagination;
- selected-user menu;
- read-only workout pagination;
- read-only workout detail/back navigation.

All labels are constants from `texts.py`.

## Formatting and HTML safety

The bot has global HTML parse mode. Any Telegram-derived or database-derived user text must
be escaped before interpolation:

- suggestion author name;
- suggestion request text;
- first name;
- username;
- workout descriptions are already escaped by `formatters.workout_card()`.

Add formatter functions for suggestion details and user summaries rather than assembling
large HTML blocks in handlers. Literal labels used by those formatters still come from
`texts.py`.

Truncate list-button labels after escaping is not necessary because button text is plain
text, but truncate by characters before building buttons to keep rows readable.

## Handler structure

Create `handlers/admin.py` with small sections:

1. menu and `/admin`;
2. suggestion list/detail/status callbacks;
3. user list/detail/report callbacks;
4. workout list/detail callbacks;
5. shared message replacement/photo helpers.

Recommended internal helpers:

```python
_suggestion_page(status, page)
_show_suggestion(callback, request_id, status, page)
_user_page(page)
_show_user(callback, user_id, users_page)
_workout_page(user_id, page)
_show_workout(callback, user_id, workout_id, page)
_replace_admin_message(callback, text, markup)
```

Page helpers clamp requested pages to valid bounds, as the existing history handler does.
All callback handlers call `callback.answer()` exactly once, including error paths.

When replacing a photo detail with text, follow the existing history behavior: delete the
photo message and send a fresh text message. Catch Telegram API exceptions narrowly where
practical and log failures without exposing internals to the user.

No admin FSM state is needed for this version because all operations are button-driven.

## Dispatcher and command registration

In `app.py`:

1. import the admin handler module;
2. include its protected router;
3. include the unauthorized `/admin` fallback after the protected router;
4. keep callback prefixes unique so router order does not alter behavior.

Keep normal commands registered globally. Register `/admin` for each configured admin with
`BotCommandScopeChat(chat_id=admin_id)` by extending the normal command list with the admin
command. Failure to register an admin-scoped command should be logged and should not stop
bot startup; typing `/admin` still works.

## File-by-file implementation sequence

1. **`src/momentum/config.py`**
   - add and validate `ADMIN_USER_IDS`;
   - expose it as an immutable integer set.

2. **`.env.example` and `README.md`**
   - document the admin allowlist syntax and behavior;
   - mention that admin workout access is read-only.

3. **`src/momentum/auth.py`**
   - implement `IsAdmin`;
   - keep authorization independent of handlers and database access.

4. **`src/momentum/db/schema.sql`**
   - add the two idempotent indexes.

5. **`src/momentum/db/repo.py`**
   - add result dataclasses and timestamp conversion;
   - add suggestion list/detail/status queries;
   - add aggregated user list/detail queries.

6. **`src/momentum/texts.py`**
   - add Russian admin menu, status, empty-state, pagination, error, and confirmation copy;
   - add status-label mapping and small dynamic text helpers where pluralization is needed.

7. **`src/momentum/formatters.py`**
   - add escaped suggestion detail and user summary formatting.

8. **`src/momentum/keyboards.py`**
   - add admin callback factories;
   - add admin-only keyboard builders;
   - ensure no admin workout keyboard emits `HistCB` or `WorkoutCB`.

9. **`src/momentum/handlers/admin.py`**
   - implement the protected menu and all read/write callbacks;
   - implement the unauthorized `/admin` response separately;
   - reuse report services and workout formatters.

10. **`src/momentum/app.py`**
    - register routers and admin-scoped commands.

11. **Documentation**
    - update `docs/fsm.md` only if it documents non-FSM navigation; otherwise state in the
      README that the admin interface is callback-driven and has no FSM state.

## Verification plan

### Static checks

Run:

```bash
uv run ruff format .
uv run ruff check .
```

Check that no Russian string was introduced outside `texts.py`, and no SQL was introduced
outside `db/repo.py`.

### Repository checks

Using a temporary database or a backed-up development database:

1. insert suggestions with all three statuses;
2. verify status and all-status counts;
3. verify newest-first pagination has no duplicates between pages;
4. update a status and verify persistence after reopening the connection;
5. verify the aggregate user query includes users with zero workouts;
6. verify workout counts and deterministic ordering;
7. verify invalid IDs return `None` or `False`, not exceptions.

### Telegram authorization checks

1. configured admin can open `/admin`;
2. non-admin receives access denied for `/admin`;
3. non-admin cannot execute a copied admin callback;
4. adding a second ID in configuration grants access after restart;
5. removing an ID revokes access after restart;
6. malformed or empty admin configuration fails startup with a useful error.

### Suggestions checks

1. empty filters render a useful empty state;
2. filter and page survive list → detail → back;
3. status update redraws the correct request;
4. user text containing `<`, `>`, `&`, or HTML tags renders literally;
5. stale request callbacks are handled without crashing.

### User/workout checks

1. users with and without workouts appear correctly;
2. histories are isolated by selected `user_id`;
3. a workout ID paired with the wrong user ID is rejected;
4. cardio photos render and back navigation returns to the correct page;
5. admin workout details contain no edit/delete controls;
6. weekly and monthly reports match what the selected user receives;
7. stale user and workout callbacks show a controlled error.

### Regression checks

Verify `/start`, workout creation, `/history`, workout editing/deletion, `/week`, `/month`,
report toggles, `/suggest`, and global cancel behavior are unchanged.

## Acceptance criteria

- Only configured Telegram IDs can use any admin command or callback.
- Suggestions can be filtered, paginated, opened, and moved between statuses.
- Admins can browse all registered users without N+1 queries.
- Admins can view another user's paginated workouts, photos, weekly report, and monthly
  report.
- No admin path can modify or delete another user's workout.
- Every workout lookup remains scoped by both workout ID and owner user ID.
- User-controlled HTML is escaped.
- Admin callback data stays within Telegram limits and uses dedicated prefixes.
- Schema application remains idempotent for existing installations.
- Ruff formatting and lint checks pass.

## Deferred work

- coach and athlete entities;
- database-backed roles;
- per-athlete access grants;
- editing or deleting another user's workouts;
- admin audit log;
- replying to users about suggestions;
- suggestion assignment, comments, or status history;
- a web admin panel.
