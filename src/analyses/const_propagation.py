"""
Constant Propagation.

Owner: Jani Rose Lawwellman (24BCE2603) - analysis-specific layer, Review 2.

Purpose
-------
For each program point, determine which variables are guaranteed to hold
a single, known constant value, as opposed to a value that is either not
yet known or provably not constant.

Domain (the lattice)
---------------------
Each variable's value is one of three lattice elements, forming the
classic three-level constant-propagation lattice:

    UNDEF (top, "no information yet / unreachable-so-far")
       |
    CONST(c)   (one node per possible constant value c)
       |
    NAC (bottom, "not a constant" - two or more different constants, or
         a value that depends on something non-constant, reach this
         point)

The overall domain element at a program point is a mapping
Dict[str, ConstValue]; a variable absent from the mapping is treated as
UNDEF (this keeps boundary/initial values compact - see below).

Direction: FORWARD.
Meet:      per-variable lattice meet, applied pointwise over the union of
           variable names appearing in either map:
             meet(UNDEF, x)      = x
             meet(NAC, x)        = NAC
             meet(CONST(a), CONST(b)) = CONST(a) if a == b else NAC
           This is exactly why a join point where two branches assign the
           SAME constant keeps that constant, but two branches assigning
           DIFFERENT constants collapse to NAC (spec 4D).
Boundary:  empty map (every variable UNDEF) at the entry block - nothing
           is known about any variable before the program starts.
Initial:   empty map (every variable UNDEF) for every other block too.
           Starting all blocks at UNDEF (the lattice's top element) and
           only ever moving down (UNDEF -> CONST(c) -> NAC) is what makes
           the iteration monotone and guarantees termination on this
           finite-height-per-variable lattice.
Transfer:  process a block's instructions in order, updating a working
           copy of the incoming map:
             - assign_const v = k:            v -> CONST(k)
             - assign_copy  v = u:             v -> value_of(u)
             - assign_binop v = l OP r:  evaluate CONST OP CONST if both
               operands are known constants (or literals); if either
               operand is NAC, result is NAC; otherwise (either operand
               still UNDEF) the result is UNDEF - we don't yet know
               enough to say anything.
           if/goto/label instructions have no effect on the map.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Union

from src.framework.analysis import Analysis, BasicBlockLike, Direction

ConstMap = Dict[str, "ConstValue"]


@dataclass(frozen=True)
class ConstValue:
    """One element of the three-level constant-propagation lattice.

    kind is one of "undef" (top), "const" (middle, with `value` set) or
    "nac" (bottom, not-a-constant). Use the module-level UNDEF and NAC
    singletons rather than constructing kind="undef"/"nac" directly.
    """

    kind: str
    value: Optional[int] = None

    def is_undef(self) -> bool:
        return self.kind == "undef"

    def is_const(self) -> bool:
        return self.kind == "const"

    def is_nac(self) -> bool:
        return self.kind == "nac"


UNDEF = ConstValue(kind="undef")
NAC = ConstValue(kind="nac")


def const(value: int) -> ConstValue:
    return ConstValue(kind="const", value=value)


def meet_value(a: ConstValue, b: ConstValue) -> ConstValue:
    if a.is_undef():
        return b
    if b.is_undef():
        return a
    if a.is_nac() or b.is_nac():
        return NAC
    # both const
    return a if a.value == b.value else NAC


_BINOPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a // b if b != 0 else None,
    ">": lambda a, b: int(a > b),
    ">=": lambda a, b: int(a >= b),
    "<": lambda a, b: int(a < b),
    "<=": lambda a, b: int(a <= b),
    "==": lambda a, b: int(a == b),
}


class ConstantPropagation(Analysis[ConstMap]):
    direction = Direction.FORWARD

    def boundary_value(self) -> ConstMap:
        return {}

    def initial_value(self) -> ConstMap:
        return {}

    def _lookup(self, m: ConstMap, operand) -> ConstValue:
        if isinstance(operand, int):
            return const(operand)
        return m.get(operand, UNDEF)

    def meet(self, values: Iterable[ConstMap]) -> ConstMap:
        values = list(values)
        keys = set()
        for m in values:
            keys |= m.keys()
        result: ConstMap = {}
        for k in keys:
            acc = UNDEF
            for m in values:
                acc = meet_value(acc, m.get(k, UNDEF))
            if not acc.is_undef():
                result[k] = acc
        return result

    def transfer(self, block: BasicBlockLike, value: ConstMap) -> ConstMap:
        cur: ConstMap = dict(value)
        for instr in block.instructions:
            if instr.kind == "assign_const":
                cur[instr.dest] = const(instr.const_value)
            elif instr.kind == "assign_copy":
                cur[instr.dest] = self._lookup(cur, instr.left)
            elif instr.kind == "assign_binop":
                lv = self._lookup(cur, instr.left)
                rv = self._lookup(cur, instr.right)
                if lv.is_nac() or rv.is_nac():
                    cur[instr.dest] = NAC
                elif lv.is_const() and rv.is_const():
                    fn = _BINOPS.get(instr.op)
                    result = fn(lv.value, rv.value) if fn else None
                    cur[instr.dest] = const(result) if result is not None else NAC
                else:
                    cur[instr.dest] = UNDEF
                    # keep the map compact: UNDEF entries carry no info
                    del cur[instr.dest]
            # if/goto/label: no effect
        return cur
