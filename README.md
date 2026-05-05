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

## Dataset Commands

Search the empirical hard-difficulty limit, increasing the square board size by
one unit at a time from `7x7` onward until the solve time exceeds the selected
threshold:

```bash
python3 -m galaxy_graph_lab.dataset_cli find-hard-threshold
```

For example, to use a `0.5s` threshold and stop the search at `31x31`:

```bash
python3 -m galaxy_graph_lab.dataset_cli find-hard-threshold --threshold-seconds 0.5 --start-side 7 --max-side 31
```

Generate the fixed dataset directly, without running the threshold search
first. By default, this command generates `20` valid instances per size and per
difficulty for all square sizes from `7x7` to `11x11`:

```bash
python3 -m galaxy_graph_lab.dataset_cli generate-dataset
```

You can also fix the output directory and the base seed:

```bash
python3 -m galaxy_graph_lab.dataset_cli generate-dataset --base-seed 0 --data-dir data
```

Full installation instructions are available in
[docs/en/installation.md](docs/en/installation.md).
