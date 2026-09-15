"""
Live Variables.

Owner: Jani Rose Lawwellman (24BCE2603) - analysis-specific layer, Review 2.

Purpose
-------
For each program point, determine which variables may be read (used)
along some future path before being redefined. A variable defined but
never subsequently used is "dead" at that definition.

Direction: BACKWARD.
Domain:    sets of variable names (frozenset[str]).
Meet:      set union - a variable is live if it is live along ANY
           successor path (MAY analysis).
Boundary:  empty set at the exit block(s) (nothing is live "after" the
           program ends, since this is an intraprocedural, closed
           program with no caller to report values back to).
Initial:   empty set for every other block, before the first iteration.
Transfer:  per the Analysis base class's direction contract, `transfer`
           receives the value flowing OUT of the block (in backward-
           analysis terms) and returns the value flowing IN. Given
           OUT[B], process B's instructions in REVERSE order:
             - an instruction that defines v removes v from the live set
               (its earlier value is no longer needed going backward,
               i.e. going forward it is about to be overwritten and its
               old value is dead beyond this point) - this must happen
               BEFORE adding this instruction's own uses, so that a
               variable used to compute its own new value (e.g. "a=a+1")
               is correctly still counted as live going into the
               instruction.
             - the instruction's own uses are then added to the live set.
           IN[B] is the result after processing all instructions.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, Set

from src.framework.analysis import Analysis, BasicBlockLike, Direction


class LiveVariables(Analysis[FrozenSet[str]]):
    direction = Direction.BACKWARD

    def boundary_value(self) -> FrozenSet[str]:
        return frozenset()

    def initial_value(self) -> FrozenSet[str]:
        return frozenset()

    def meet(self, values: Iterable[FrozenSet[str]]) -> FrozenSet[str]:
        result: Set[str] = set()
        for v in values:
            result |= v
        return frozenset(result)

    def transfer(self, block: BasicBlockLike, value: FrozenSet[str]) -> FrozenSet[str]:
        # `value` here is OUT[block] (see class docstring / Analysis base
        # class docstring for the backward-direction convention).
        cur: Set[str] = set(value)
        for instr in reversed(block.instructions):
            if instr.dest is not None:
                cur.discard(instr.dest)
            cur |= set(instr.uses)
        return frozenset(cur)  # this is IN[block]
