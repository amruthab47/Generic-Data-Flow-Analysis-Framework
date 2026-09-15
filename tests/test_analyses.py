"""
Semantic tests for the analysis-specific layer (Reaching Definitions,
Available Expressions, Live Variables, Constant Propagation).

Owner: Jani Rose Lawwellman (24BCE2603) - testing is part of her
supporting responsibility (requirements + testing) for Review 2.

These tests exercise the real analysis classes in src/analyses/ through
the real Analysis interface in src/framework/analysis.py. They run to a
fixed point using tests/fixtures.run_to_fixed_point, a small test-only
worklist driver (NOT the official generic solver - see fixtures.py's
module docstring for why). Every expected IN/OUT value below is derived
by hand from the corresponding CFG in tests/fixtures.py; none of it is
"whatever the code happens to produce".

Run with:  python -m unittest tests.test_analyses  -v
(or `pytest tests/test_analyses.py -v` once pytest is available)
"""

import unittest

from src.analyses.avl_exp import AvailableExpressions
from src.analyses.const_propagation import ConstantPropagation, NAC, const
from src.analyses.live_var import LiveVariables
from src.analyses.reaching_def import ReachingDefinitions
from tests.fixtures import (
    branch_cfg,
    const_agree_join_cfg,
    const_conflict_join_cfg,
    dead_def_cfg,
    join_available_expressions_cfg,
    loop_cfg,
    redefinition_cfg,
    run_to_fixed_point,
    sequential_cfg,
)


def by_name(blocks):
    return {b.name: b for b in blocks}


class TestReachingDefinitions(unittest.TestCase):
    """Direction: forward. Domain: sets of def ids. Meet: union."""

    def test_sequential_program(self):
        # a=5(d1); b=10(d2); c=a+b(d3) - a single block, so OUT should
        # simply accumulate every definition in program order.
        blocks = sequential_cfg()
        rd = ReachingDefinitions(blocks)
        result = run_to_fixed_point(rd, blocks)
        in_b0, out_b0 = result["B0"]
        self.assertEqual(in_b0, frozenset())          # boundary: nothing reaches entry
        self.assertEqual(out_b0, frozenset({"d1", "d2", "d3"}))

    def test_redefinition_kills_earlier_definition(self):
        # x=5(d1); x=10(d2); y=x(d3). d1 (x=5) must NOT reach the end of
        # the block: it is killed by d2 (x=10) before y=x executes.
        blocks = redefinition_cfg()
        rd = ReachingDefinitions(blocks)
        result = run_to_fixed_point(rd, blocks)
        _, out_b0 = result["B0"]
        self.assertNotIn("d1", out_b0, "x=5 (d1) should be killed by x=10 (d2)")
        self.assertIn("d2", out_b0)
        self.assertIn("d3", out_b0)

    def test_branch_join_unions_both_paths(self):
        # B0: a=5(d1); if a>0 goto L1
        # B1: b=10(d2); goto L2      B2: L1: b=20(d3)
        # B3: L2: c=b(d4)
        # Both d2 and d3 define b and both paths reach B3, so a MAY
        # analysis must show BOTH reaching B3's entry (this is exactly
        # why reaching definitions is not "the latest assignment").
        blocks = branch_cfg()
        rd = ReachingDefinitions(blocks)
        result = run_to_fixed_point(rd, blocks)
        in_b3, out_b3 = result["B3"]
        self.assertIn("d2", in_b3, "b=10 on the not-taken-branch path must still reach the join")
        self.assertIn("d3", in_b3, "b=20 on the taken-branch path must still reach the join")
        self.assertIn("d1", in_b3, "a=5 is never redefined, so it still reaches the join")
        self.assertIn("d4", out_b3)

    def test_loop_needs_iteration_to_reach_fixed_point(self):
        # i=0(d1); L1: if i>=10 goto L2; i=i+1(d2); goto L1; L2: x=i(d3)
        # d2 (i=i+1) reaches the loop header's IN via the back edge - this
        # is only discoverable by iterating the fixed-point computation
        # more than once (B1's IN depends on B2's OUT, which depends on
        # B1's OUT, i.e. on itself through the loop).
        blocks = loop_cfg()
        rd = ReachingDefinitions(blocks)
        result = run_to_fixed_point(rd, blocks)
        in_b1, _ = result["B1"]
        self.assertIn("d1", in_b1, "i=0 reaches the loop header on entry")
        self.assertIn("d2", in_b1, "i=i+1 (from the back edge) reaches the loop header")
        in_b3, _ = result["B3"]
        self.assertIn("d2", in_b3, "the loop-updated i must reach the exit use x=i")


class TestAvailableExpressions(unittest.TestCase):
    """Direction: forward. Domain: sets of expr keys. Meet: intersection."""

    def test_expression_available_on_all_paths(self):
        blocks = sequential_cfg()  # a=5; b=10; c=a+b
        ae = AvailableExpressions(blocks)
        result = run_to_fixed_point(ae, blocks)
        _, out_b0 = result["B0"]
        self.assertIn("a+b", out_b0)

    def test_expression_invalidated_by_redefining_an_operand(self):
        # a=5; b=10; c=a+b; if we then redefined a, "a+b" must be killed.
        from tests.fixtures import Block, assign_const, assign_binop
        b0 = Block("B0", [
            assign_const("a", 5, "d1"),
            assign_const("b", 10, "d2"),
            assign_binop("c", "a", "+", "b", "d3"),
            assign_const("a", 99, "d4"),  # redefine an operand of a+b
        ])
        blocks = [b0]
        ae = AvailableExpressions(blocks)
        result = run_to_fixed_point(ae, blocks)
        _, out_b0 = result["B0"]
        self.assertNotIn("a+b", out_b0, "a+b must be killed once 'a' is redefined")

    def test_not_available_unless_computed_on_every_incoming_path(self):
        # a+b is computed on the B0->B1->B3 path but NOT on B0->B2->B3,
        # so it must NOT be available at B3's entry (this is the case a
        # naive "record every expression seen so far" union would get
        # wrong - it must use intersection, not union).
        blocks = join_available_expressions_cfg()
        ae = AvailableExpressions(blocks)
        result = run_to_fixed_point(ae, blocks)
        in_b3, _ = result["B3"]
        self.assertNotIn("a+b", in_b3,
                          "a+b was not computed along the B0->B2->B3 path, so it isn't available at the join")


class TestLiveVariables(unittest.TestCase):
    """Direction: backward. Domain: sets of variable names. Meet: union."""

    def test_variable_used_in_successor_is_live_in_predecessor(self):
        # B1: b=10; goto L2      B2: L1: b=20
        # B3: L2: c=b
        # b is used in B3, so b must be live in OUT[B1] and OUT[B2]
        # (both predecessors of B3), even though neither B1 nor B2 itself
        # reads b after defining it.
        blocks = branch_cfg()
        blocks_by_name = by_name(blocks)
        lv = LiveVariables(blocks)
        result = run_to_fixed_point(lv, blocks)
        _, out_b1 = result["B1"]
        _, out_b2 = result["B2"]
        self.assertIn("b", out_b1)
        self.assertIn("b", out_b2)

    def test_dead_definition_not_live_after_its_own_statement(self):
        # a=1; b=2; c=a  -> b is defined but never used afterwards, so it
        # must be dead immediately after its own definition. a IS used
        # (by c=a) so it must be live at that same point.
        from tests.fixtures import Block, assign_copy
        blocks = dead_def_cfg()
        lv = LiveVariables(blocks)
        result = run_to_fixed_point(lv, blocks)
        in_b0, out_b0 = result["B0"]
        self.assertEqual(out_b0, frozenset(), "nothing is live after the block (no successors)")
        self.assertEqual(in_b0, frozenset(), "both a and b are defined before any use reaches block entry")

        # Check liveness at the specific point right after "b=2" (i.e. the
        # live-in of the remaining tail "c=a") by re-running transfer on
        # just that suffix of instructions with the same OUT boundary.
        tail = Block("tail", [assign_copy("c", "a", "d3")])
        live_after_b2 = lv.transfer(tail, frozenset())
        self.assertNotIn("b", live_after_b2, "b is never read after its definition, so it is dead")
        self.assertIn("a", live_after_b2, "a is read by c=a, so it is live right after b=2")

    def test_loop_variable_live_across_back_edge(self):
        # i is tested (if i>=10), incremented, and used again next
        # iteration and after the loop (x=i) - it must be live entering
        # the loop header from both predecessors.
        blocks = loop_cfg()
        lv = LiveVariables(blocks)
        result = run_to_fixed_point(lv, blocks)
        in_b1, _ = result["B1"]
        self.assertIn("i", in_b1)


class TestConstantPropagation(unittest.TestCase):
    """Direction: forward. Domain: var -> {UNDEF, CONST(c), NAC}. Meet: pointwise."""

    def test_simple_assignments_and_expression(self):
        # a=5; b=10; c=a+b  =>  c must be known constant 15.
        blocks = sequential_cfg()
        cp = ConstantPropagation(blocks)
        result = run_to_fixed_point(cp, blocks)
        _, out_b0 = result["B0"]
        self.assertEqual(out_b0["a"], const(5))
        self.assertEqual(out_b0["b"], const(10))
        self.assertEqual(out_b0["c"], const(15))

    def test_redefinition_uses_latest_value(self):
        # x=5; x=10; y=x  => y must be 10, not 5.
        blocks = redefinition_cfg()
        cp = ConstantPropagation(blocks)
        result = run_to_fixed_point(cp, blocks)
        _, out_b0 = result["B0"]
        self.assertEqual(out_b0["y"], const(10))

    def test_conflicting_constants_at_join_become_nac(self):
        # b=5 on one branch, b=7 on the other -> NAC at the join.
        blocks = const_conflict_join_cfg()
        cp = ConstantPropagation(blocks)
        result = run_to_fixed_point(cp, blocks)
        in_b3, out_b3 = result["B3"]
        self.assertEqual(in_b3.get("b", NAC), NAC)
        self.assertEqual(out_b3["c"], NAC, "c=b copies the conflicting, non-constant b")

    def test_agreeing_constants_at_join_stay_constant(self):
        # b=10 on BOTH branches -> still known-constant 10 at the join.
        blocks = const_agree_join_cfg()
        cp = ConstantPropagation(blocks)
        result = run_to_fixed_point(cp, blocks)
        in_b3, out_b3 = result["B3"]
        self.assertEqual(in_b3.get("b"), const(10))
        self.assertEqual(out_b3["c"], const(10))

    def test_loop_variable_becomes_non_constant(self):
        # i=0; i=i+1 in a loop -> i cannot be a single known constant at
        # the loop header once the back edge is accounted for.
        blocks = loop_cfg()
        cp = ConstantPropagation(blocks)
        result = run_to_fixed_point(cp, blocks)
        in_b1, _ = result["B1"]
        self.assertEqual(in_b1.get("i", NAC), NAC,
                          "i varies across loop iterations, so it is not a single constant at the header")


if __name__ == "__main__":
    unittest.main()
