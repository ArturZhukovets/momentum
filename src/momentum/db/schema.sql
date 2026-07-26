CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,      -- telegram id
    username      TEXT,
    first_name    TEXT,
    reports_on    INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS workouts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    kind          TEXT    NOT NULL CHECK (kind IN ('cardio','strength')),
    performed_on  TEXT    NOT NULL,          -- 'YYYY-MM-DD', local date
    description   TEXT    NOT NULL DEFAULT '',
    photo_file_id TEXT,                      -- cardio only
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_workouts_user_date ON workouts(user_id, performed_on);

CREATE TABLE IF NOT EXISTS improvement_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user_full_name TEXT    NOT NULL,
    request_text   TEXT    NOT NULL CHECK (length(trim(request_text)) > 0),
    status         TEXT    NOT NULL DEFAULT 'new'
                           CHECK (status IN ('new','done','rejected')),
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_body_parts (
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    body_part  TEXT    NOT NULL,
    PRIMARY KEY (workout_id, body_part)
);
