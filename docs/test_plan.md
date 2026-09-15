# Test Plan — Analysis-Specific Layer

**Scope of this document:** tests for `src/analyses/*`, in
`tests/test_analyses.py`. Owner: Jani Rose Lawwellman (24BCE2603),
testing is her supporting responsibility for Review 2.

`tests/test_basicblocks.py`, `tests/test_cfg.py`, `tests/test_parser.py`
and `tests/test_solver.py` are out of scope here — they belong to the
CFG/IR/solver components other team members own, and are currently
empty pending those components.

## How correctness is established

Every expected value in `tests/test_analyses.py` is derived **by hand**
from the corresponding small CFG (built in `tests/fixtures.py`) using the
standard textbook GEN/KILL and meet/transfer definitions for each
analysis — not copied from whatever the code first produced. Where a
result depends on iterating to a fixed point (loop tests), the
hand-derivation traces the fixed-point computation by hand across the
back edge.

Tests run against the real `src/analyses/*` classes through the real
`src/framework/analysis.Analysis` interface, driven by
`tests/fixtures.run_to_fixed_point` — a small, generic-over-`Analysis`
worklist loop that exists only so these tests don't have to wait for the
official `src/framework/solver.py` (still empty). It is not a substitute
for that solver; see `tests/fixtures.py`'s docstring.

## Test inputs used

| Input | Structure | Used for |
|---|---|---|
| `tests/input/sequential.txt` (`sequential_cfg`) | `a=5; b=10; c=a+b`, one block | sequential coverage for all four analyses |
| `tests/input/redefinition.tac` (`redefinition_cfg`) | `x=5; x=10; y=x`, one block | redefinition/kill coverage |
| `tests/input/branch.tac` (`branch_cfg`) | if/else join, 4 blocks | branch + join-point coverage |
| `tests/input/loop.tac` (`loop_cfg`) | while-style loop, 4 blocks incl. back edge | loop / iterative fixed-point coverage |
| `join_available_expressions_cfg` (new, purpose-built) | if/else join where an expression is computed on only one path | "not available unless computed on every path" — none of the existing `.tac` inputs happen to exercise this |
| `const_conflict_join_cfg` / `const_agree_join_cfg` (new, purpose-built) | if/else join, differing vs. matching constants | constant-propagation join behaviour |
| `dead_def_cfg` (new, purpose-built) | `a=1; b=2; c=a`, one block | dead/unused definition coverage |

The existing `.tac` files were kept as the source of truth for CFG shape
(same variables, same branch/label/loop structure); nothing already
checked in under `tests/input/` was deleted.

## Test matrix

| Test | Analysis | What it validates |
|---|---|---|
| `test_sequential_program` | Reaching Defs | all three defs in a straight-line block reach the exit |
| `test_redefinition_kills_earlier_definition` | Reaching Defs | a redefinition kills the earlier definition of the same variable |
| `test_branch_join_unions_both_paths` | Reaching Defs | both branches' definitions of `b` reach the join (MAY/union, not "latest assignment") |
| `test_loop_needs_iteration_to_reach_fixed_point` | Reaching Defs | the loop-updated definition reaches the header only after iterating across the back edge |
| `test_expression_available_on_all_paths` | Available Exprs | a straight-line computed expression is available afterward |
| `test_expression_invalidated_by_redefining_an_operand` | Available Exprs | redefining an operand kills the expression that used it |
| `test_not_available_unless_computed_on_every_incoming_path` | Available Exprs | an expression computed on only one branch is NOT available at the join (intersection, not union) |
| `test_variable_used_in_successor_is_live_in_predecessor` | Live Vars | a variable used in a join successor is live at the end of both predecessors |
| `test_dead_definition_not_live_after_its_own_statement` | Live Vars | a variable defined but never subsequently used is dead right after its definition |
| `test_loop_variable_live_across_back_edge` | Live Vars | the loop condition variable is live entering the loop header |
| `test_simple_assignments_and_expression` | Const Prop | constants propagate through a simple binary expression |
| `test_redefinition_uses_latest_value` | Const Prop | a copy picks up the most recent constant value |
| `test_conflicting_constants_at_join_become_nac` | Const Prop | differing constants on two branches collapse to NAC at the join |
| `test_agreeing_constants_at_join_stay_constant` | Const Prop | matching constants on two branches stay constant at the join |
| `test_loop_variable_becomes_non_constant` | Const Prop | a variable modified every loop iteration becomes NAC at the header |

## Coverage against the required categories

Sequential, redefinition, branch, loop, multiple definitions, join
points, expression invalidation, live-then-used variables, dead
definitions, constant propagation through assignments/expressions, and
conflicting constants at joins are each covered by at least one test
above (see the "What it validates" column). Boundary behaviour (entry
block's `IN` equals each analysis's `boundary_value()`, e.g. `∅` for the
set-based analyses) is checked as part of `test_sequential_program` and
`test_dead_definition_not_live_after_its_own_statement`.

## How to run

```
python -m unittest tests.test_analyses -v
```

`pytest` is listed in `requirements.txt` (corrected from a `pytext` typo)
and can run the same file once installed:

```
pytest tests/test_analyses.py -v
```

## Known limitation

These tests validate the analysis-specific logic in isolation, against
hand-built fixture CFGs. They do **not** yet validate the full pipeline
`TAC file -> parser -> CFG -> generic solver -> results`, because the
parser, CFG builder and generic solver are still empty. Once those land,
the fixture-based tests here should be supplemented (not necessarily
replaced) with end-to-end tests that parse the real `.tac` files.
