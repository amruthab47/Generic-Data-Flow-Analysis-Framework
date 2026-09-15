"""
Generic data-flow Analysis interface.

COMPATIBILITY NOTE (added for Review 2, by Jani Rose Lawwellman / analysis layer):
This file was found EMPTY in the repository. Since every analysis-specific
module (src/analyses/reaching_def.py, avl_exp.py, live_var.py,
const_propagation.py) must implement a common interface so the generic
solver (src/framework/solver.py) can drive them without analysis-specific
code, some interface had to exist first. The contract below is the
smallest thing that unblocks that work:

    - Direction enum (FORWARD / BACKWARD)
    - Analysis ABC: boundary_value, initial_value, meet, transfer
    - BasicBlockLike / InstructionLike: typing.Protocol descriptions of the
      minimal attributes an analysis needs from the CFG's basic blocks and
      the IR's instructions. These are *not* new concrete IR/CFG classes -
      they are structural (duck-typed) contracts. The real BasicBlock and
      Instruction classes (owned by the CFG/IR team members) just need to
      expose attributes with these names/shapes; they don't need to inherit
      from anything here.

This should be reviewed by whoever owns src/framework/ and src/cfg/ /
src/ir/, and reconciled with any interface they had already planned, per
the Review 1 architecture (CFG -> Generic Data-Flow Engine -> Analysis-
specific modules -> IN/OUT results).
"""

from __future__ import annotations

import copy as _copy
from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, Iterable, List, Optional, Protocol, TypeVar, runtime_checkable


class Direction(Enum):
    """Direction in which an analysis flows over the CFG."""
    FORWARD = "forward"
    BACKWARD = "backward"


@runtime_checkable
class InstructionLike(Protocol):
    """Minimal shape an IR instruction must have for analyses to consume it.

    See docs/design.md for the full contract and tests/fixtures.py for a
    concrete implementation used by the analysis-layer tests (since the
    real parser/IR is not implemented yet).
    """
    kind: str
    dest: Optional[str]
    uses: List[str]


@runtime_checkable
class BasicBlockLike(Protocol):
    """Minimal shape a CFG basic block must have for analyses to consume it."""
    name: str
    instructions: List[InstructionLike]
    predecessors: List["BasicBlockLike"]
    successors: List["BasicBlockLike"]


# T is the data-flow "domain" element type for a given analysis
# (e.g. frozenset[str] for reaching definitions, dict[str, ConstValue]
# for constant propagation).
T = TypeVar("T")


class Analysis(ABC, Generic[T]):
    """Base class every analysis-specific module implements.

    An Analysis instance is constructed with the full list of CFG blocks
    (so it can precompute program-wide facts such as "all definitions of
    each variable", or "the universe of computed expressions") and then
    exposes the five ingredients named in the Review 1 design:

        - direction              (class attribute)
        - boundary_value()       (initial value at the graph's entry/exit)
        - initial_value()        (starting value for all other blocks)
        - meet(values)           (combine operator at join points)
        - transfer(block, value) (analysis-specific effect of one block)

    `transfer(block, value)` takes the value flowing INTO the block in the
    analysis's own direction (IN[block] for a forward analysis, OUT[block]
    for a backward analysis) and returns the value flowing back OUT in
    that same direction. This lets the generic solver stay direction-
    agnostic: it just needs to know which neighbours ("predecessors" for
    forward, "successors" for backward) feed a block's input.

    The generic solver (src/framework/solver.py) is expected to run the
    standard iterative worklist algorithm using exactly these five
    ingredients; no analysis subclasses that loop over the CFG to a fixed
    point themselves.
    """

    direction: Direction

    def __init__(self, blocks: Iterable[BasicBlockLike]):
        self.blocks: List[BasicBlockLike] = list(blocks)
        self._precompute()

    def _precompute(self) -> None:
        """Optional hook for program-wide precomputation (e.g. building
        the universe of definitions/expressions). No-op by default."""
        return None

    @abstractmethod
    def boundary_value(self) -> T:
        """Value at the graph's entry (forward) or exit (backward) block."""
        raise NotImplementedError

    @abstractmethod
    def initial_value(self) -> T:
        """Starting value used for every non-boundary block before the
        first iteration of the fixed-point computation."""
        raise NotImplementedError

    @abstractmethod
    def meet(self, values: Iterable[T]) -> T:
        """Combine the values coming from multiple predecessors/successors
        at a control-flow join. Must be idempotent, commutative and
        associative for the analysis to be a correctly monotone framework."""
        raise NotImplementedError

    @abstractmethod
    def transfer(self, block: BasicBlockLike, value: T) -> T:
        """Analysis-specific effect of executing `block`, applied to the
        value flowing into it (see class docstring for direction handling)."""
        raise NotImplementedError

    def equal(self, a: T, b: T) -> bool:
        """Equality used by the solver to detect convergence. Overridable
        for domains where '==' isn't the right notion (default is fine for
        sets/dicts of hashable/comparable values, which all four analyses
        in this project use)."""
        return a == b

    def copy_value(self, value: T) -> T:
        """Defensive copy used by the solver so blocks don't share mutable
        state. Overridable for performance; deepcopy is correct by
        default for the set/dict domains used here."""
        return _copy.deepcopy(value)
