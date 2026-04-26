# Installation

## Requirements

- Python 3.11, 3.12, or 3.13
- Poetry 2.x

## Setup

```bash
poetry install
```

## Run the App

From the repository root:

```bash
poetry run python -m galaxy_graph_lab.main
```

or

```bash
poetry run galaxy-graph-lab
```

If you prefer an activated shell first:

```bash
poetry shell
python -m galaxy_graph_lab.main
```

## Development Checks

```bash
poetry run pytest
poetry run ruff check .
```
