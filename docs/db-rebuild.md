# Rebuilding the server database

The old database was created by a hand-written `schema.sql` whose column types
(`TEXT` for dates, `INTEGER` for booleans) and inline foreign keys differ from
what the models declare. Alembic cannot fully reflect that DDL, so the database
is rebuilt once: dump the data, delete the file, let Alembic create the schema,
replay the data. **No values change** — only the declared types.
a
Do this once. `db/migrate.py` refuses to start the bot until it is done.

## Procedure

Run everything from the project directory on the server. `./data` is
bind-mounted to `/app/data` in the container, so both see the same files.

```bash
cd /path/to/momentum
git pull
mkdir -p data/backups
TS=$(date +%Y%m%d-%H%M%S)

# 1. Stop the bot and build the new image.
docker compose down
docker compose build

# 2. Back up twice — a replayable dump and the raw file.
python3 scripts/dump_data.py --db data/momentum.db -o data/backups/momentum-$TS.sql
cp data/momentum.db data/backups/momentum-$TS.db
grep -c '^INSERT' data/backups/momentum-$TS.sql      # sanity check before deleting

# 3. Delete the old database.
rm -f data/momentum.db data/momentum.db-wal data/momentum.db-shm

# 4. Create the new schema (inside the container — it has Alembic).
docker compose run --rm --no-deps bot alembic upgrade head

# 5. Replay the data. The container writes as uid 1000, so take ownership first
#    if your host user differs (a no-op otherwise).
[ -w data/momentum.db ] || sudo chown $USER data/momentum.db
python3 scripts/load_data.py data/backups/momentum-$TS.sql --db data/momentum.db

# 6. Start the bot.
docker compose up -d
docker compose logs -f --tail 50 bot
```

Steps 2 and 5 run on the host and need only a stock `python3` — no venv, no
dependencies. Steps 4 and 6 run in the container.

Step 5 prints a row count per table and runs `PRAGMA foreign_key_check`. It
refuses if the database already holds rows, so re-running it is safe.

The log in step 6 should show `Schema is at head` with no migration running —
step 4 already did that.

## If something goes wrong

Nothing is destroyed until step 3, and both backups survive it:

```bash
docker compose down
cp data/backups/momentum-$TS.db data/momentum.db
docker compose up -d
```
