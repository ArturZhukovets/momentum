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

-- Everything the bot asks the user about lives here, never in `users`:
-- that table is written only by the identity middleware.

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
    waist_cm      REAL,
    chest_cm      REAL,
    hips_cm       REAL,
    thigh_cm      REAL,
    arm_cm        REAL,
    note          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_body_measurements_user_date
    ON body_measurements(user_id, recorded_on);
