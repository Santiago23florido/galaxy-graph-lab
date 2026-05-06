# Galaxy Graph Lab

Galaxy Graph Lab is a Python project for modeling, generating, solving, and
playing **Galaxy**-style logic puzzles. The codebase combines exact MILP
formulations, a callback-style connectivity-rejection solver, a constructive
heuristic solver, dataset-generation utilities, batch-evaluation commands, and
an interactive Pygame interface.

## Installation

The project is managed with Poetry. Use Python `3.11`, `3.12`, or `3.13`.

1. Install dependencies from the repository root:

```bash
poetry install
```

2. Run commands directly through Poetry:

```bash
poetry run python -m galaxy_graph_lab.main
```

3. If you prefer an activated shell:

```bash
poetry shell
python -m galaxy_graph_lab.main
```

## Game Interface

The game interface lets you generate puzzles, inspect the current board state,
request solver assistance, and visualize solutions inside the same UI.

![Difficulty selection](<report/sections/images/Difficulty selection.png>)

![Game solution](<report/sections/images/Game Solution.png>)

## Project Components

1. **Interactive game application**

   The interactive front end is implemented in the Pygame layer under
   `galaxy_graph_lab/ui/`. It provides the start screen, difficulty selection,
   board rendering, live validation, and solver-assisted play.

   Command:

   ```bash
   poetry run python -m galaxy_graph_lab.main
   ```

   You can also choose one concrete solver backend:

   ```bash
   poetry run python -m galaxy_graph_lab.main --solver-backend exact_flow
   poetry run python -m galaxy_graph_lab.main --solver-backend parallel_callback
   poetry run python -m galaxy_graph_lab.main --solver-backend heuristic_orbit
   ```

2. **Puzzle representation and validation**

   The core layer represents boards, centers, puzzle geometry, grid-graph
   structure, and candidate assignments. It also provides the structural
   validators for partition, admissibility, symmetry, kernel containment, and
   connectivity. These components are implemented mainly in:

   - `galaxy_graph_lab/core/board.py`
   - `galaxy_graph_lab/core/centers.py`
   - `galaxy_graph_lab/core/model_data.py`
   - `galaxy_graph_lab/core/geometry.py`
   - `galaxy_graph_lab/core/graph.py`
   - `galaxy_graph_lab/core/validators.py`

3. **Unified solver service**

   The public solver entry point is `solve_puzzle(...)` in
   `galaxy_graph_lab/core/solver_service.py`. It normalizes backend selection,
   public statuses, solution payloads, and backend-specific time limits.

   The three public backends are:

   - `exact_flow`
   - `parallel_callback`
   - `heuristic_orbit`

4. **Exact MILP solver**

   The `exact_flow` backend solves the puzzle with the full MILP formulation
   that embeds connectivity directly through flow variables and constraints.
   Its implementation lives mainly in:

   - `galaxy_graph_lab/core/milp/flow_model.py`
   - `galaxy_graph_lab/core/solver_service.py`

   This is the default backend across the project.

5. **Callback-style connectivity solver**

   The `parallel_callback` backend solves the base MILP first and then rejects
   disconnected assignments through an iterative connectivity check on the grid
   graph. Its implementation lives in:

   - `galaxy_graph_lab/core/milp/callback_parallel_model.py`
   - `galaxy_graph_lab/core/milp/callback_parallel_backend.py`

   You can use it in the game or in dataset evaluation with:

   ```bash
   poetry run python -m galaxy_graph_lab.main --solver-backend parallel_callback
   ```

6. **Heuristic orbit solver**

   The `heuristic_orbit` backend is a constructive multi-start heuristic that
   grows symmetric regions from kernel cells, repairs conflicts, and validates
   final assignments structurally before returning them. Its implementation
   lives in:

   - `galaxy_graph_lab/core/milp/heuristic_orbit_model.py`
   - `galaxy_graph_lab/core/milp/heuristic_orbit_backend.py`

   It can be launched from the game or from batch solving:

   ```bash
   poetry run python -m galaxy_graph_lab.main --solver-backend heuristic_orbit
   ```

7. **Automatic puzzle generation**

   The generation pipeline creates certified Galaxy instances from difficulty
   profiles. It includes center placement, constructive region growth,
   partition closure, preference shaping, and solver-based certification.
   The main generation modules live in:

   - `galaxy_graph_lab/core/generation/profiles.py`
   - `galaxy_graph_lab/core/generation/center_placement.py`
   - `galaxy_graph_lab/core/generation/region_growth.py`
   - `galaxy_graph_lab/core/generation/partition_closure.py`
   - `galaxy_graph_lab/core/generation/preference_shaping.py`
   - `galaxy_graph_lab/core/generation/certification.py`
   - `galaxy_graph_lab/core/generation/service.py`

8. **Stored instances**

   Generated instances are stored as structured JSON files in `data/`. They are
   loaded and saved through:

   - `save_instance(...)`
   - `load_instance(...)`

   from `galaxy_graph_lab/core/dataset.py`.

   The interactive game now also checks the shared instance base before solving
   a newly generated board. If the same board and center configuration already
   exists and a solution is already stored, the game reuses that solution
   instead of solving the instance again.

9. **Hard-threshold search**

   The project includes a dedicated search routine for estimating how far the
   `hard` family remains solvable under a selected time threshold. This command
   generates increasing square instances, solves them with the selected solver,
   and stores the threshold-search artifacts in `data/threshold`.

   Command:

   ```bash
   poetry run python -m galaxy_graph_lab.dataset_cli find-hard-threshold
   ```

   Example with explicit parameters:

   ```bash
   poetry run python -m galaxy_graph_lab.dataset_cli find-hard-threshold --threshold-seconds 0.5 --start-side 7 --max-side 31
   ```

10. **Dataset generation**

    The fixed dataset generator creates valid instances for all three
    difficulties over the selected board-size window and writes them to `data/`.
    By default, it generates `20` valid instances per size and difficulty for
    square boards from `7x7` to `11x11`.

    Command:

    ```bash
    poetry run python -m galaxy_graph_lab.dataset_cli generate-dataset
    ```

    Example with explicit seed and output directory:

    ```bash
    poetry run python -m galaxy_graph_lab.dataset_cli generate-dataset --base-seed 0 --data-dir data
    ```

11. **Batch solving and solver comparison**

    The dataset-solving pipeline resolves every stored instance with one solver
    or several solvers, writes one result file per instance under `res/cplex`,
    and produces aggregate summaries.

    Solve the dataset with all three solvers:

    ```bash
    poetry run python -m galaxy_graph_lab.dataset_cli solve-dataset --solver-backend all
    ```

    Solve it only with the default exact backend:

    ```bash
    poetry run python -m galaxy_graph_lab.dataset_cli solve-dataset --solver-backend exact_flow
    ```

12. **Result summaries and graphs**

    Experimental results are exported as text files and summaries in
    `res/cplex/`, and plotting utilities in `res/` generate the figures used in
    the report.

    Command:

    ```bash
    poetry run python res/generate_result_graphs.py --results-dir res/cplex --output-dir report/sections/images --threshold-dir data/threshold
    ```

13. **Tests and development checks**

    The repository contains unit and integration tests for the core,
    generation, solvers, dataset pipeline, and Pygame UI.

    Commands:

    ```bash
    poetry run pytest
    poetry run ruff check .
    ```

## Additional documentation

More installation details are available in:

- [docs/en/installation.md](docs/en/installation.md)
