# Requirements — Analysis-Specific Layer

No requirements document existed in the repository. This adds the
concise set relevant to the analysis-specific layer only (Jani Rose
Lawwellman, 24BCE2603).

## Functional requirements

- FR1: The framework shall support all four specified analyses:
  Reaching Definitions, Available Expressions, Live Variables,
  Constant Propagation.
- FR2: The framework shall support both forward analyses (Reaching
  Definitions, Available Expressions, Constant Propagation) and
  backward analyses (Live Variables).
- FR3: Each analysis shall define its own boundary value, initial
  value, meet operator, and transfer function, without depending on
  any other analysis's implementation.
- FR4: The solver shall iterate the analysis's transfer/meet
  operations over the CFG until the computed IN/OUT values stabilize
  (fixed point).
- FR5: Results shall expose, per basic block, the IN and OUT
  data-flow values.
- FR6: Analyses shall operate on the CFG produced by the CFG builder
  (or, until that exists, on any object satisfying the same
  `BasicBlockLike`/`InstructionLike` shape).

## Non-functional requirements

- NFR1 (Modularity): analysis-specific logic must not be duplicated
  inside a generic solver, and the generic solver must not contain
  analysis-specific logic.
- NFR2 (Reusability): one solver implementation must be able to drive
  any of the four analyses unmodified.
- NFR3 (Correctness): each analysis's meet operator must be the
  mathematically correct one for its "MAY" vs "MUST" nature (union vs.
  intersection), and each transfer function must implement the
  standard GEN/KILL or lattice-transfer definition for that analysis.
- NFR4 (Testability): each analysis must be testable independently of
  the parser/CFG builder/solver, given any object satisfying the
  block/instruction contract.
- NFR5 (Extensibility): adding a fifth analysis should require only a
  new `Analysis` subclass, no changes to the solver.
