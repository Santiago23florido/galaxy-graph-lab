# Galaxy Graph Lab

Python-based Galaxy graph lab project with a future Pygame interface layer.

Use Python 3.11, 3.12, or 3.13 for the initial setup so `pygame` installs cleanly.

Initial setup focuses on:

- a Poetry-managed virtual environment,
- lightweight dependencies,
- a runnable smoke entrypoint,
- and installation documentation for new contributors.

## Setup

Create or reuse the Poetry virtual environment and install dependencies from
the repository root:

```bash
poetry install
```

## Run the Pygame MVP

Launch the current Pygame Phase A window from the repository root with either
of these commands:

```bash
poetry run python -m galaxy_graph_lab.main
```

or

```bash
poetry run galaxy-graph-lab
```

If you prefer to activate the environment first:

```bash
poetry shell
python -m galaxy_graph_lab.main
```

## Development Checks

Run tests and linting through Poetry as well:

```bash
poetry run pytest
poetry run ruff check .
```

Full installation instructions are available in
[docs/en/installation.md](docs/en/installation.md).
