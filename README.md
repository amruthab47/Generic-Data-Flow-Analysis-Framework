# Generic-Data-Flow-Analysis-Frame
This project aims to develop a reusable generic data-flow analysis framework for performing classical data-flow analyses over a Control-Flow Graph (CFG).

Traditional implementations of individual data-flow analyses often duplicate common solving infrastructure such as CFG traversal, meet operations, transfer functions, worklist iteration and convergence checking.

Our framework separates this common solving mechanism from analysis-specific rules, allowing multiple analyses to use the same generic engine.

The framework is designed to support:

Reaching Definitions
Available Expressions
Live Variables
Constant Propagation

The project is implemented as a student-scale educational framework intended to demonstrate the principles of monotone data-flow analysis and reusable compiler infrastructure.
