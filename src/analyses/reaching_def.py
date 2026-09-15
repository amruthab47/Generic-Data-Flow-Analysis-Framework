"""
Reaching Definitions.

Owner: Jani Rose Lawwellman (24BCE2603) - analysis-specific layer, Review 2.

Purpose
-------
For each program point, determine which *definitions* (specific
assignment instructions, not just variable names) may reach it along
some path from the entry.

Direction: FORWARD.
Domain:    sets of definition ids (frozenset[str]). Each assignment
           instruction in the program is given a unique id (see
           tests/fixtures.py, field `def_id`); the domain element at a
           point is the set of def ids that may reach that point.
Meet:      set union (this is a MAY analysis - a definition reaches a
           point if it reaches along *any* incoming path).
Boundary:  empty set at the entry block (no definitions reach the very
           start of the program).
Initial:   empty set for every other block, before the first iteration.
Transfer:  for a block B with IN[B] reaching it, process B's assignment
           instructions in order; each assignment to variable v with id d
           kills every *other* definition of v (from anywhere in the
           program) and generates {d}.

This module does NOT implement its own fixed-point loop - it only
supplies boundary_value/initial_value/meet/transfer for the generic
solver (src/framework/solver.py) to drive.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Set

from src.framework.analysis import Analysis, BasicBlockLike, Direction


class ReachingDefinitions(Analysis[FrozenSet[str]]):
    direction = Direction.FORWARD

    def _precompute(self) -> None:
        # all_defs_of[var] = set of every def_id anywhere in the program
        # that assigns to `var`. Needed to compute KILL sets, since a
        # single block's own instructions aren't enough to know about
        # every other definition of the same variable.
        all_defs: Dict[str, Set[str]] = {}
        for block in self.blocks:
            for instr in block.instructions:
                if instr.dest is not None and instr.def_id is not None:
                    all_defs.setdefault(instr.dest, set()).add(instr.def_id)
        self.all_defs_of: Dict[str, FrozenSet[str]] = {
            v: frozenset(ids) for v, ids in all_defs.items()
        }

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
        cur: Set[str] = set(value)
        for instr in block.instructions:
            if instr.dest is None or instr.def_id is None:
                continue  # control-flow instructions don't affect reaching defs
            kill = self.all_defs_of.get(instr.dest, frozenset())
            cur -= kill
            cur.add(instr.def_id)
        return frozenset(cur)
