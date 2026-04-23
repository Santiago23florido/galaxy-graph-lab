# Galaxy Core Implementation Notes

These notes are intentionally written as a developer-facing roadmap, not as a
full design document and not as a complete implementation spec. The goal is to
build the core solver in small, testable layers while staying aligned with the
mathematical model from `Model.pdf`.

## 1. Implementation Goal

The `core` package should eventually support two solver strategies:

1. An exact MILP model with explicit flow variables for connectivity.
2. A lighter branch-and-cut model that starts from a base assignment model and
   adds lazy constraints for hard global rules.

Do not implement both at once. Build the shared mathematical layer first, then
the base MILP, then the connectivity layer, and only after that the callback
workflow.

## 2. Mathematical Objects That Must Exist in Code

The model in the PDF is built around a few discrete objects. These should be
explicit in the codebase before any solver model is written.

### Board

- `N`: number of rows
- `M`: number of columns
- `U = [N] x [M]`: set of all cells

In code, `U` should not remain implicit. Add a canonical iterator over all
cells so every later step can reuse the same ordering.

### Grid Graph

- `H = (U, E)`
- `{u, v} in E` when `u` and `v` share a side

This graph is the connectivity backbone of the puzzle. All connectivity checks,
component searches, and flow arcs depend on it.

### Centers

Each center `g` has a geometric position:

- `L(g) = (a_g, b_g)`
- coordinates may be integer or half-integer

That means the center may lie:

- inside a cell,
- on an edge,
- or on a vertex.

This is why the kernel size may be 1, 2, or 4.

### Rotation Operator

For each center `g`, define:

- `tau_g(i, j) = (2a_g - i, 2b_g - j)`

This is the 180-degree rotation map. It is not optional utility logic. It is a
core mathematical primitive and should have dedicated tests.

### Admissible Domain Per Center

- `U_g = {u in U : tau_g(u) in U}`

If `u` rotates outside the board for center `g`, then assignment `x[u, g]` is
forbidden.

### Kernel

- `K(g)` is the set of board cells geometrically incident to center `g`

This is a mandatory subset of the final galaxy for center `g`.

## 3. Recommended Internal Architecture

Do not put everything into one solver file. Split the core package by
mathematical responsibility.

Suggested layout:

- `core/board.py`
  - board dimensions
  - cell enumeration
  - neighbor generation
- `core/centers.py`
  - center representation
  - integer / half-integer coordinate handling
- `core/geometry.py`
  - `tau_g`
  - admissible cell computation
  - kernel computation
- `core/graph.py`
  - grid graph helpers
  - connected component extraction
- `core/validators.py`
  - partition validation
  - symmetry validation
  - kernel validation
  - connectivity validation
  - optional hole detection later
- `core/model_data.py`
  - immutable precomputed puzzle data
  - board, centers, `U_g`, `K(g)`, adjacency
- `core/milp/base_model.py`
  - variables `x[u, g]`
  - constraints (14)-(17)
- `core/milp/flow_model.py`
  - flow variables and constraints (21)-(25)
- `core/milp/callbacks.py`
  - lazy separation logic
  - disconnected-component cuts

The important design decision is this: precomputed geometry and graph data
should be solver-agnostic. The MILP code should consume those structures, not
recompute them.

## 4. Phase-by-Phase Build Order

This is the safest order to implement the core logic.

### Phase 1: Geometry Layer

Implement first:

1. A cell type.
2. A center type.
3. Board bounds checks.
4. The rotation map `tau_g`.
5. The admissible set `U_g`.
6. The kernel `K(g)`.

Expected output of this phase:

- given a board and a list of centers, the code can tell:
  - all board cells,
  - the rotated twin of a cell for a given center,
  - whether that twin is valid,
  - and which cells are forced by the center kernel.

This phase should contain no solver code.

### Phase 2: Graph Layer

Implement next:

1. Orthogonal adjacency for every cell.
2. The undirected grid graph `H`.
3. Induced subgraph traversal for a chosen set of cells.
4. Connected component extraction.

Expected output of this phase:

- given a candidate galaxy `X_g`, the code can test whether `H[X_g]` is
  connected.

Again, still no MILP code yet.

### Phase 3: Structural Validators

Before writing the solver, implement direct validators over a candidate
assignment:

1. Partition check:
   every cell belongs to exactly one center.
2. Admissibility check:
   no cell assigned outside `U_g`.
3. Symmetry check:
   `u in X_g => tau_g(u) in X_g`.
4. Kernel check:
   `K(g) subseteq X_g`.
5. Connectivity check:
   `H[X_g]` is connected.

This gives you a pure-Python correctness oracle that later MILP solutions can
be validated against.

### Phase 4: Base MILP Model

Now implement only the base binary model with:

- binary variables `x[u, g]`
- partition constraint (14)
- inadmissible assignment elimination (15)
- symmetry equalities (16)
- kernel fixing (17)

At this point, the model is intentionally incomplete with respect to the full
puzzle because connectivity is still missing.

This is the right first solver milestone because:

- it is simple,
- easy to debug,
- and already matches the callback-ready base model described in Section 8.2 of
  the PDF.

### Phase 5: Exact Connectivity via Flow

Only after the base model is stable should the exact flow formulation be added.

Implement:

1. Directed arcs from the undirected grid:
   `E_dir = {(u, v), (v, u) : {u, v} in E}`.
2. One artificial source `s_g` per center.
3. Source-to-kernel arcs `(s_g, u)` for each `u in K(g)`.
4. Nonnegative flow variables over all such arcs.

Then add the flow constraints:

- arc capacities tied to selected cells, equations (21) and (22)
- source capacity, equation (23)
- per-cell flow balance, equation (24)
- total source supply, equation (25)

The intended reading is:

- every selected cell must absorb one unit of flow,
- and that flow must originate from the kernel of its own center,
- which forces the selected region to be connected to the kernel.

### Phase 6: Callback-Based Connectivity

Only start this phase after the flow formulation works and the geometry layer is
well tested.

The callback version should reuse the base model from Phase 4 and add
connectivity lazily.

Runtime callback flow:

1. Read the integer solution `x*`.
2. Reconstruct each selected cell set `X_g*`.
3. Compute connected components of `H[X_g*]`.
4. Detect any component `C` that does not contain a kernel cell.
5. Add the separation cut from equation (30):

   `sum_{u in C} x[u, g] <= |C| - 1 + sum_{v in delta(C)} x[v, g]`

Where:

- `C` is a disconnected component,
- `delta(C)` is the side-neighbor frontier outside `C`.

Interpretation:

- if all cells in `C` remain assigned to center `g`,
- then at least one frontier cell must also be assigned to `g`,
- otherwise `C` would stay isolated.

This is the preferred structured cut. The generic no-good cut from equation
(32) should only be used as a temporary fallback.

## 5. Data Contracts Between Layers

The most important integration rule is to keep a stable representation of
problem data across all layers.

Suggested shared structures:

- `BoardSpec`
  - `rows`
  - `cols`
- `CenterSpec`
  - `id`
  - `row_coord`
  - `col_coord`
- `PuzzleData`
  - `cells`
  - `centers`
  - `neighbors`
  - `admissible_cells_by_center`
  - `kernel_by_center`
  - `twin_by_center_and_cell`

The solver should accept `PuzzleData` and produce a solution object, not a raw
dictionary with loose conventions.

Suggested solver output:

- `GalaxyAssignment`
  - `assigned_center_by_cell`
  - `cells_by_center`
  - optional raw solver metadata

That makes it easier for the UI and tests to consume results consistently.

## 6. How the Math Maps to Code

This mapping should remain explicit while implementing.

### Binary Assignment Variable

Math:

- `x[u, g] in {0, 1}`

Code meaning:

- `1` means cell `u` belongs to center `g`
- `0` means it does not

Recommended implementation note:

- keep one canonical indexing layer between Python objects and solver variable
  names; avoid rebuilding keys ad hoc in many places.

### Partition

Math:

- for every cell `u`, `sum_g x[u, g] = 1`

Code impact:

- every cell must resolve to exactly one owning galaxy

### Admissibility

Math:

- `x[u, g] = 0` for `u not in U_g`

Code impact:

- if a twin cell goes out of bounds, that assignment must not even be available

### Symmetry

Math:

- `x[u, g] = x[tau_g(u), g]`

Code impact:

- assignments occur in rotationally symmetric pairs relative to the center

### Kernel

Math:

- `x[u, g] = 1` for `u in K(g)`

Code impact:

- kernel cells are forced seed cells of each galaxy

### Connectivity

Math:

- exact via flow, or lazy via cuts

Code impact:

- disconnected but locally valid symmetric regions must be rejected

## 7. Integration With the Rest of the Repository

The `core` package should stay independent from the UI.

Recommended dependency direction:

- `ui` may import `core`
- `core` must not import `ui`

Recommended integration flow:

1. Puzzle instance is parsed or created by a high-level loader.
2. Loader builds `PuzzleData`.
3. A solver entry point in `core` receives `PuzzleData`.
4. Solver returns `GalaxyAssignment`.
5. UI consumes `GalaxyAssignment` to render regions.

This keeps the mathematical engine reusable for:

- CLI experiments,
- tests,
- future benchmark scripts,
- and the Pygame interface.

## 8. Suggested Milestones

Use these as real development checkpoints.

### Milestone A

- geometry primitives implemented
- kernel computation implemented
- admissibility computation implemented
- unit tests for center cases:
  - center in cell
  - center on edge
  - center on vertex

### Milestone B

- grid adjacency implemented
- connected component search implemented
- pure-Python validators implemented

### Milestone C

- base MILP model implemented
- model can produce assignments satisfying partition + symmetry + kernel
- solutions can be validated with the Python validators

### Milestone D

- exact flow connectivity added
- solver rejects disconnected assignments

### Milestone E

- callback version added
- disconnected components produce lazy cuts
- results match the exact flow solver on small benchmark boards

## 9. What Not To Do Early

Avoid these mistakes in the first implementation pass:

- do not mix geometry precomputation with solver model construction
- do not start with callbacks before a stable connectivity checker exists
- do not let UI concerns leak into the core package
- do not encode cells and centers with inconsistent indexing schemes
- do not skip the pure-Python validators just because the solver exists

## 10. First Concrete Coding Tasks

If implementation starts tomorrow, the first tasks should be:

1. Create board, cell, and center data structures.
2. Implement `tau_g`.
3. Implement `K(g)`.
4. Implement `U_g`.
5. Implement orthogonal neighbors.
6. Implement connected component detection.
7. Write tests for the geometry edge cases.
8. Only then create the base MILP builder.

That sequence matches the mathematical dependency chain of the model and keeps
the early code small enough to debug.

## 11. Final Development Note

The PDF already suggests the right long-term architecture:

- one exact formulation with flow for robustness,
- one callback-based formulation for scalability.

The right implementation strategy is not to choose one immediately, but to
build the shared mathematical core so both solver paths can rely on the same
geometry, graph, and validation logic.
