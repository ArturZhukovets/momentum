# How This Application Runs

This project is a Python **package**, not a single `main.py` script. Its code is
in `src/momentum`.

## Project configuration

`pyproject.toml` has three important parts:

- `[project]` names the project `momentum` and lists its dependencies.
- `[build-system]` tells uv to use Hatchling to build/install the project.
- `packages = ["src/momentum"]` tells Hatchling where the package code is.

`uv` manages Python, dependencies, and `.venv`. Hatchling makes the local
source code installable as a Python package.

## Approach 1: install the project (recommended)

```bash
uv sync
uv run python -m momentum
```

`uv sync` creates `.venv`, installs the dependencies, and installs the local
`momentum` package (normally as an editable package). Editable means code
changes are used directly without reinstalling the project.

`uv run` uses the Python from `.venv`. The `-m momentum` argument tells Python
to find the `momentum` package and execute `src/momentum/__main__.py`.

The startup flow is:

```text
uv run → .venv Python → momentum/__main__.py → app.main()
       → configuration → database → bot and scheduler → polling/webhook
```

`uv run` normally synchronizes the environment automatically, so the explicit
`uv sync` is often optional for local use.

## Approach 2: do not install the project

```bash
uv sync --no-install-project
PYTHONPATH="$PWD/src" uv run --no-sync python -m momentum
```

The first command installs only third-party dependencies. `PYTHONPATH` then
tells Python to search `src/`, the directory that contains `momentum`.
`--no-sync` prevents `uv run` from installing the project automatically.

Both approaches execute the same application code. The difference is how
Python finds `momentum`:

- **Installed:** `.venv` knows where the package is. This is reliable and is
  the normal approach.
- **Not installed:** every run must provide `src/` through `PYTHONPATH` or run
  from inside `src/`.

## Docker

Docker first installs only dependencies for better layer caching. It then
copies `src/` and installs `momentum`. At runtime, `.venv` is already on
`PATH`, so Docker can run:

```bash
python -m momentum
```
