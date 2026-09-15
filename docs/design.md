# Design — Analysis-Specific Layer

**Scope of this document:** the analysis-specific layer only
(`src/analyses/*`) and the minimal framework contract it depends on
(`src/framework/analysis.py`). It does not describe the TAC parser,
CFG builder, generic solver, or output/visualization layers, which are
other team members' Review 2 deliverables.

Owner: Jani Rose Lawwellman (24BCE2603).

## Architecture recap (Review 1)

```
TAC -> PARSER -> BASIC BLOCKS -> CFG -> GENERIC SOLVER -> ANALYSIS -> RESULTS
```

The analysis-specific layer sits between the generic solver and the
results. Each analysis is a class implementing a common interface
(`Analysis`, in `src/framework/analysis.py`); the generic solver is
expected to drive any `Analysis` subclass without knowing which specific
analysis it is running.

## Framework contract (`src/framework/analysis.py`)

This file was empty in the repository; the following minimal contract
was added so the four analyses below have something to implement against.
See the file's own docstring for the "why" and a note for whoever owns
`src/framework/` to review it.

- `Direction` — `FORWARD` or `BACKWARD`.
- `Analysis` (ABC) — constructed with the CFG's blocks; exposes
  `boundary_value()`, `initial_value()`, `meet(values)`,
  `transfer(block, value)`, plus `equal()`/`copy_value()` helpers for the
  solver's convergence check.
- `BasicBlockLike` / `InstructionLike` — `typing.Protocol` descriptions of
  the attributes an analysis needs from a basic block / instruction
  (`instructions`, `predecessors`, `successors`, `kind`, `dest`, `uses`,
  …). These are structural contracts, not new concrete IR/CFG classes.

`transfer(block, value)` always takes the value flowing **into** the
block in the analysis's own direction, and returns the value flowing
**out**, in that same direction. For a forward analysis that's
`IN[block] -> OUT[block]`; for a backward analysis it's
`OUT[block] -> IN[block]`. This lets one solver loop drive both
directions without analysis-specific branching.

## The four analyses

### 1. Reaching Definitions

| | |
|---|---|
| Purpose | which definitions may reach each program point |
| Direction | Forward |
| Domain | `frozenset[str]` of definition ids (one id per assignment instruction) |
| Boundary (entry) | `∅` |
| Initial (other blocks) | `∅` |
| Meet | set union (MAY analysis) |
| Transfer | for each assignment `dest=…` with id `d`: kill every *other* definition of `dest` anywhere in the program, then add `d` |

The kill set for a variable is computed once per `Analysis` instance
(`_precompute`), from *all* blocks — a single block cannot know about
definitions of the same variable elsewhere in the program on its own.

### 2. Available Expressions

| | |
|---|---|
| Purpose | which computed expressions (`a+b`-style) are safe to reuse |
| Direction | Forward |
| Domain | `frozenset[str]` of expression keys (only `assign_binop` right-hand sides are tracked) |
| Boundary (entry) | `∅` |
| Initial (other blocks) | the universe of all expression keys in the program |
| Meet | set **intersection** (MUST analysis) |
| Transfer | an assignment to `v` kills every tracked expression that uses `v` as an operand; a binop assignment then generates its own expression key, unless `v` is itself one of that expression's operands (e.g. `v = v + 1` cannot make `v+1` available going forward) |

Starting non-entry blocks at the *universal* set (rather than `∅`) is
required for a MUST/intersection analysis to converge to a sound
fixed point — the dual of starting a MAY/union analysis at `∅`.

### 3. Live Variables

| | |
|---|---|
| Purpose | which variables may be read before being redefined |
| Direction | Backward |
| Domain | `frozenset[str]` of variable names |
| Boundary (exit) | `∅` |
| Initial (other blocks) | `∅` |
| Meet | set union (MAY analysis) |
| Transfer | process a block's instructions in **reverse**: for each instruction, first remove its `dest` (if any) from the live set, then add its `uses` — in that order, so `v = v + 1` still counts `v` as live going in |

### 4. Constant Propagation

| | |
|---|---|
| Purpose | which variables are guaranteed to hold one known constant value |
| Direction | Forward |
| Domain | `Dict[str, ConstValue]`, a 3-level lattice per variable: `UNDEF` (top) → `CONST(c)` → `NAC` (bottom). A variable absent from the map is `UNDEF`. |
| Boundary (entry) | `{}` (every variable `UNDEF`) |
| Initial (other blocks) | `{}` |
| Meet | pointwise per variable: `meet(UNDEF, x) = x`; `meet(NAC, x) = NAC`; `meet(CONST(a), CONST(b)) = CONST(a)` if `a == b` else `NAC` |
| Transfer | `assign_const` sets the constant directly; `assign_copy` copies the source's current value; `assign_binop` evaluates the operator if both operands are known constants, produces `NAC` if either operand is `NAC`, otherwise stays `UNDEF` |

Two branches assigning the *same* constant to a variable keep it
constant at the join; two branches assigning *different* constants
collapse it to `NAC` — this is what the conflicting-join test in
`tests/test_analyses.py` checks.

## How the analysis layer connects to the generic solver

Intended integration (once `src/framework/solver.py`, `src/cfg/*` and
`src/ir/*` are implemented):

```python
analysis = ReachingDefinitions(cfg.blocks)   # or AvailableExpressions / LiveVariables / ConstantPropagation
results = generic_solver.solve(cfg, analysis)  # -> {block: (IN, OUT)}
```

The generic solver only needs `analysis.direction`, `boundary_value()`,
`initial_value()`, `meet()`, `transfer()` and `equal()` — it never needs
to know which of the four analyses it is running, and none of the four
analysis classes contain a worklist loop of their own.

**Current status:** `src/framework/solver.py`, `src/cfg/*` and
`src/ir/*` are still empty (Phase 2/3 not yet landed), so this
integration cannot be exercised end-to-end yet. To validate the analysis
logic in the meantime, `tests/fixtures.py` hand-builds small CFGs (via a
`Block`/`Instruction` structure satisfying `BasicBlockLike`/
`InstructionLike`) and a small test-only fixed-point driver
(`run_to_fixed_point`) that exercises exactly the same five-method
interface the real solver will use. `tests/fixtures.py` is not the
official IR/CFG implementation and should be replaced once the real
parser/CFG builder land.
