"""
Test-only IR/CFG fixtures for the analysis-specific layer.

WHY THIS FILE EXISTS
---------------------
src/ir/instruction.py, src/ir/parser.py, src/cfg/basicblock.py,
src/cfg/basicblockbuilder.py and src/cfg/cfg_builder.py are all currently
empty (Phase 2 / "Program representation and CFG implementation" has not
landed yet). The analysis-specific layer (src/analyses/*) is Review 2's
responsibility and needs *something* satisfying the BasicBlockLike /
InstructionLike contract in src/framework/analysis.py to be tested against.

This module hand-builds small, explicit CFGs that mirror the four TAC
programs already checked in under tests/input/ (sequential.txt,
redefinition.tac, branch.tac, loop.tac), plus a join-point example for
available expressions. It is deliberately NOT a parser: it does not read
.tac files or implement general TAC syntax. It exists purely so the
analysis logic can be validated with hand-derived expected results before
the real parser/CFG builder exist.

Once the real src/ir and src/cfg modules land, these fixtures should be
replaced by CFGs built from the actual parser + CFG builder, and this
file can be deleted. Until then it is intentionally isolated here in
tests/ rather than under src/, so it can't be mistaken for the official
IR/CFG implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

Operand = Union[str, int]  # a variable name, or an integer literal


@dataclass
class Instruction:
    """Satisfies the InstructionLike protocol (kind, dest, uses), plus the
    extra fields the four analyses need (documented per-field below)."""

    kind: str
    # one of: "assign_const", "assign_copy", "assign_binop",
    #         "if", "goto", "label", "nop"

    dest: Optional[str] = None          # variable written (assign_* only)
    uses: List[str] = field(default_factory=list)  # variables read

    const_value: Optional[int] = None   # literal for assign_const
    op: Optional[str] = None            # arithmetic operator for assign_binop
    left: Optional[Operand] = None      # left operand (assign_binop / if)
    right: Optional[Operand] = None     # right operand (assign_binop / if)

    expr_key: Optional[str] = None      # canonical RHS text, e.g. "a+b"
    def_id: Optional[str] = None        # unique id for this definition site

    label: Optional[str] = None         # for kind == "label"
    target: Optional[str] = None        # for kind in {"goto", "if"}

    text: str = ""                      # human-readable source line (for debugging/output)


@dataclass(eq=False)  # eq=False: blocks reference each other (pred/succ), so
# identity equality is used deliberately - a structural dataclass __eq__
# would recurse through the whole predecessor/successor graph.
class Block:
    """Satisfies the BasicBlockLike protocol."""

    name: str
    instructions: List[Instruction] = field(default_factory=list)
    predecessors: List["Block"] = field(default_factory=list)
    successors: List["Block"] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Block({self.name})"


def link(pred: Block, succ: Block) -> None:
    pred.successors.append(succ)
    succ.predecessors.append(pred)


# ---------------------------------------------------------------------------
# Instruction builders (small helpers, not a parser)
# ---------------------------------------------------------------------------

def assign_const(dest: str, value: int, def_id: str) -> Instruction:
    return Instruction(
        kind="assign_const", dest=dest, uses=[], const_value=value,
        def_id=def_id, text=f"{dest}={value}",
    )


def assign_copy(dest: str, src: str, def_id: str) -> Instruction:
    return Instruction(
        kind="assign_copy", dest=dest, uses=[src], left=src,
        def_id=def_id, text=f"{dest}={src}",
    )


def assign_binop(dest: str, left: Operand, op: str, right: Operand, def_id: str) -> Instruction:
    uses = [o for o in (left, right) if isinstance(o, str)]
    expr_key = f"{left}{op}{right}"
    return Instruction(
        kind="assign_binop", dest=dest, uses=uses, op=op, left=left, right=right,
        expr_key=expr_key, def_id=def_id, text=f"{dest}={left}{op}{right}",
    )


def if_goto(left: Operand, op: str, right: Operand, target: str) -> Instruction:
    uses = [o for o in (left, right) if isinstance(o, str)]
    return Instruction(
        kind="if", uses=uses, op=op, left=left, right=right, target=target,
        text=f"if {left}{op}{right} goto {target}",
    )


def goto(target: str) -> Instruction:
    return Instruction(kind="goto", target=target, text=f"goto {target}")


def label(name: str) -> Instruction:
    return Instruction(kind="label", label=name, text=f"{name}:")


# ---------------------------------------------------------------------------
# Fixture CFGs, matching tests/input/*.tac and tests/input/sequential.txt
# ---------------------------------------------------------------------------

def sequential_cfg() -> List[Block]:
    """tests/input/sequential.txt:
        a=5
        b=10
        c=a+b
    One block, no control flow.
    """
    b0 = Block("B0", [
        assign_const("a", 5, "d1"),
        assign_const("b", 10, "d2"),
        assign_binop("c", "a", "+", "b", "d3"),
    ])
    return [b0]


def redefinition_cfg() -> List[Block]:
    """tests/input/redefinition.tac:
        x=5
        x=10
        y=x
    One block; the first definition of x is killed by the second.
    """
    b0 = Block("B0", [
        assign_const("x", 5, "d1"),
        assign_const("x", 10, "d2"),
        assign_copy("y", "x", "d3"),
    ])
    return [b0]


def branch_cfg() -> List[Block]:
    """tests/input/branch.tac:
        a=5
        if a>0 goto L1
        b=10
        goto L2
        L1: b=20
        L2: c=b

    B0 (entry: a=5; if a>0 goto L1) -> B1 (b=10; goto L2), B2 (L1: b=20)
    B1 -> B3 (L2: c=b)
    B2 -> B3
    """
    b0 = Block("B0", [
        assign_const("a", 5, "d1"),
        if_goto("a", ">", 0, "L1"),
    ])
    b1 = Block("B1", [
        assign_const("b", 10, "d2"),
        goto("L2"),
    ])
    b2 = Block("B2", [
        label("L1"),
        assign_const("b", 20, "d3"),
    ])
    b3 = Block("B3", [
        label("L2"),
        assign_copy("c", "b", "d4"),
    ])
    link(b0, b1)
    link(b0, b2)
    link(b1, b3)
    link(b2, b3)
    return [b0, b1, b2, b3]


def loop_cfg() -> List[Block]:
    """tests/input/loop.tac:
        i=0
        L1: if i>=10 goto L2
        i=i+1
        goto L1
        L2: x=i

    B0 (i=0) -> B1 (L1: if i>=10 goto L2)
    B1 -> B2 (i=i+1; goto L1) [loop back-edge to B1]
    B1 -> B3 (L2: x=i)
    B2 -> B1
    """
    b0 = Block("B0", [assign_const("i", 0, "d1")])
    b1 = Block("B1", [
        label("L1"),
        if_goto("i", ">=", 10, "L2"),
    ])
    b2 = Block("B2", [
        assign_binop("i", "i", "+", 1, "d2"),
        goto("L1"),
    ])
    b3 = Block("B3", [
        label("L2"),
        assign_copy("x", "i", "d3"),
    ])
    link(b0, b1)
    link(b1, b2)
    link(b1, b3)
    link(b2, b1)
    return [b0, b1, b2, b3]


def join_available_expressions_cfg() -> List[Block]:
    """Purpose-built join example for available expressions (not from a
    checked-in .tac file, since none of the existing test inputs happen to
    recompute the same expression down only one branch):

        a=1
        b=2
        if a>0 goto L1
        c=a+b        ; B1: computes a+b on this path only
        goto L2
        L1: d=5      ; B2: does NOT compute a+b
        L2: e=a+b    ; B3: a+b is available only if computed on ALL paths in -> NOT available

    a+b must NOT be available at the start of B3, because it was not
    computed along the B0->B2->B3 path.
    """
    b0 = Block("B0", [
        assign_const("a", 1, "d1"),
        assign_const("b", 2, "d2"),
        if_goto("a", ">", 0, "L1"),
    ])
    b1 = Block("B1", [
        assign_binop("c", "a", "+", "b", "d3"),
        goto("L2"),
    ])
    b2 = Block("B2", [
        label("L1"),
        assign_const("d", 5, "d4"),
    ])
    b3 = Block("B3", [
        label("L2"),
        assign_binop("e", "a", "+", "b", "d5"),
    ])
    link(b0, b1)
    link(b0, b2)
    link(b1, b3)
    link(b2, b3)
    return [b0, b1, b2, b3]


def const_conflict_join_cfg() -> List[Block]:
    """Join point where two paths assign different constants to the same
    variable, forcing NAC (not-a-constant) at the join - for constant
    propagation:

        a=1
        if a>0 goto L1
        b=5          ; B1
        goto L2
        L1: b=7      ; B2 (different constant)
        L2: c=b      ; B3: b is NOT a known constant here (5 vs 7 conflict)
    """
    b0 = Block("B0", [
        assign_const("a", 1, "d1"),
        if_goto("a", ">", 0, "L1"),
    ])
    b1 = Block("B1", [
        assign_const("b", 5, "d2"),
        goto("L2"),
    ])
    b2 = Block("B2", [
        label("L1"),
        assign_const("b", 7, "d3"),
    ])
    b3 = Block("B3", [
        label("L2"),
        assign_copy("c", "b", "d4"),
    ])
    link(b0, b1)
    link(b0, b2)
    link(b1, b3)
    link(b2, b3)
    return [b0, b1, b2, b3]


def const_agree_join_cfg() -> List[Block]:
    """Join point where two paths assign the SAME constant - c should be
    known constant (10) after the join."""
    b0 = Block("B0", [
        assign_const("a", 1, "d1"),
        if_goto("a", ">", 0, "L1"),
    ])
    b1 = Block("B1", [
        assign_const("b", 10, "d2"),
        goto("L2"),
    ])
    b2 = Block("B2", [
        label("L1"),
        assign_const("b", 10, "d3"),
    ])
    b3 = Block("B3", [
        label("L2"),
        assign_copy("c", "b", "d4"),
    ])
    link(b0, b1)
    link(b0, b2)
    link(b1, b3)
    link(b2, b3)
    return [b0, b1, b2, b3]


def dead_def_cfg() -> List[Block]:
    """Variable defined but never used afterwards - for live variables:
        a=1
        b=2
        c=a
    b is dead immediately after its definition (never used).
    """
    b0 = Block("B0", [
        assign_const("a", 1, "d1"),
        assign_const("b", 2, "d2"),
        assign_copy("c", "a", "d3"),
    ])
    return [b0]


# ---------------------------------------------------------------------------
# Minimal fixed-point driver used ONLY by the analysis-layer tests.
# ---------------------------------------------------------------------------
#
# This is NOT the generic solver (src/framework/solver.py stays untouched -
# that is the CFG/framework team's Phase 3 deliverable). It is a small,
# generic-over-Analysis worklist loop that exists purely so these tests can
# check analysis correctness (transfer/meet) end-to-end without waiting on
# the real solver. It uses only the public Analysis interface
# (direction/boundary_value/initial_value/meet/transfer/equal), so once the
# real solver exists, swapping this helper out for it should not require any
# changes to the analyses themselves.

from src.framework.analysis import Analysis, Direction  # noqa: E402


def run_to_fixed_point(analysis: Analysis, blocks: List[Block]) -> Dict[str, tuple]:
    """Iterative worklist fixed-point computation. Returns
    {block_name: (IN, OUT)} using the analysis's own direction convention:
    for FORWARD analyses IN=entry value, OUT=exit value; for BACKWARD
    analyses IN=exit value, OUT=entry value flip is handled below so callers
    can always read result[name].in_value / .out_value in program-order
    terms (IN = value before the block executes, OUT = value after)."""

    forward = analysis.direction == Direction.FORWARD
    preds_of = (lambda b: b.predecessors) if forward else (lambda b: b.successors)
    entry_blocks = [b for b in blocks if not preds_of(b)]

    program_in: Dict[str, object] = {}
    program_out: Dict[str, object] = {}
    for b in blocks:
        if b in entry_blocks:
            val = analysis.boundary_value()
        else:
            val = analysis.initial_value()
        if forward:
            program_out[b.name] = val
        else:
            program_in[b.name] = val

    changed = True
    iterations = 0
    while changed:
        changed = False
        iterations += 1
        for b in blocks:
            if forward:
                incoming = [program_out[p.name] for p in b.predecessors]
                in_val = analysis.boundary_value() if b in entry_blocks else analysis.meet(incoming) if incoming else analysis.initial_value()
                out_val = analysis.transfer(b, in_val)
                program_in[b.name] = in_val
                if b.name not in program_out or not analysis.equal(program_out[b.name], out_val):
                    changed = True
                program_out[b.name] = out_val
            else:
                incoming = [program_in[s.name] for s in b.successors]
                out_val = analysis.boundary_value() if b in entry_blocks else analysis.meet(incoming) if incoming else analysis.initial_value()
                in_val = analysis.transfer(b, out_val)
                program_out[b.name] = out_val
                if b.name not in program_in or not analysis.equal(program_in[b.name], in_val):
                    changed = True
                program_in[b.name] = in_val
        if iterations > 1000:  # pragma: no cover - safety net for test bugs
            raise RuntimeError("fixed point not reached after 1000 iterations")

    return {b.name: (program_in[b.name], program_out[b.name]) for b in blocks}
