"""
Available Expressions.

Owner: Jani Rose Lawwellman (24BCE2603) - analysis-specific layer, Review 2.

Purpose
-------
For each program point, determine which computed expressions (a+b style
binary-operation right-hand-sides) are guaranteed to have already been
computed - and not since invalidated - along EVERY path from the entry.
This is what makes an expression safely reusable (common-subexpression
elimination).

Direction: FORWARD.
Domain:    sets of expression keys (frozenset[str]), e.g. {"a+b", "c*d"}.
           Only assign_binop right-hand sides are tracked as "expressions"
           (constants and plain copies are not computed expressions in the
           classical formulation).
Meet:      set INTERSECTION - this is a MUST analysis. An expression is
           only available at a join if it is available along ALL incoming
           paths (spec 4B: "expressions that have not been computed on
           all relevant incoming paths" must NOT be considered available).
Boundary:  empty set at the entry block (nothing has been computed yet).
Initial:   the UNIVERSE of all expressions in the program, for every
           non-entry block, before the first iteration. This is required
           for an intersection-based (MUST) analysis: starting from the
           universal set is the correct optimistic starting point that
           iterates down to a sound fixed point, exactly the mirror image
           of starting a MAY/union analysis from the empty set.
Transfer:  for a block B with IN[B] available at entry, process B's
           instructions in order. For each instruction:
             - assign_binop dest=v, expr=e: first KILL every available
               expression that uses v as an operand (v is about to
               change), then GEN e - unless v is itself one of e's own
               operands (e.g. "v = v + 1" cannot make "v+1" available
               going forward, since v changes in the same instruction).
             - assign_const/assign_copy dest=v: KILL every available
               expression that uses v as an operand. No GEN (no new
               computed expression).
             - control instructions (if/goto/label): no effect.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, Set

from src.framework.analysis import Analysis, BasicBlockLike, Direction


class AvailableExpressions(Analysis[FrozenSet[str]]):
    direction = Direction.FORWARD

    def _precompute(self) -> None:
        universe: Set[str] = set()
        for block in self.blocks:
            for instr in block.instructions:
                if instr.kind == "assign_binop" and instr.expr_key is not None:
                    universe.add(instr.expr_key)
        self.universe: FrozenSet[str] = frozenset(universe)

    def boundary_value(self) -> FrozenSet[str]:
        return frozenset()

    def initial_value(self) -> FrozenSet[str]:
        return self.universe

    def meet(self, values: Iterable[FrozenSet[str]]) -> FrozenSet[str]:
        values = list(values)
        if not values:
            return frozenset()
        result: Set[str] = set(values[0])
        for v in values[1:]:
            result &= v
        return frozenset(result)

    @staticmethod
    def _expr_operands(expr_key: str) -> Set[str]:
        """Extract the variable operand names from a stored expr_key like
        'a+b' or 'i+1' (used to decide which available expressions a
        redefinition of `v` invalidates)."""
        for op in ("+", "-", "*", "/"):
            if op in expr_key:
                left, _, right = expr_key.partition(op)
                return {left, right}
        return {expr_key}

    def _kill_set(self, cur: FrozenSet[str], var: str) -> Set[str]:
        return {e for e in cur if var in self._expr_operands(e)}

    def transfer(self, block: BasicBlockLike, value: FrozenSet[str]) -> FrozenSet[str]:
        cur: Set[str] = set(value)
        for instr in block.instructions:
            if instr.kind == "assign_binop":
                v = instr.dest
                cur -= self._kill_set(frozenset(cur), v)
                operands = {o for o in (instr.left, instr.right) if isinstance(o, str)}
                if v not in operands:
                    cur.add(instr.expr_key)
            elif instr.kind in ("assign_const", "assign_copy"):
                v = instr.dest
                cur -= self._kill_set(frozenset(cur), v)
            # "if" / "goto" / "label": no data effect
        return frozenset(cur)
