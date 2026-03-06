# Energy Smells Taxonomy

A two-level taxonomy of software energy smells comprising 12 categories and 65 subcategories. Click a category to expand its subcategories.

---

### C1 — Redundant Computation

Energy waste from executing work that does not contribute to the program's required output or that leaves program state unchanged. This includes code whose results are never consumed (dead code, resultless computation), operations that repeat work already done in the same scope (repeated computation, redundant assignments), setup and initialization on paths where results are unused (unnecessary initialization), excessive invocation of runtime housekeeping (GC calls, unchecked logging), and intermediate variables that add overhead without improving clarity. The common thread is that removing or simplifying these operations would not change program behavior but would reduce energy consumption.

<details>
<summary>Show 8 subcategories</summary>

#### C1.S1 — Dead Code

Code that executes but whose results are never consumed, or code that can never be reached on any execution path. This includes assignments to local variables that are never subsequently read (dead stores), unreachable statements placed after return or break, imported modules that are never referenced, and entire conditional branches that can be removed without altering output. The energy cost comes from instruction execution, object creation, and memory management for outputs that serve no purpose.

**Example:** Building a list of transformed items inside a function and then never returning or consuming it; assigning result = expensive_compute(x) in one branch and immediately overwriting it in the next line.

#### C1.S2 — Redundant Assignment

Statements that leave program state effectively unchanged: assigning a variable to its own value, overwriting a value that was never read since the last write, or repeating an idempotent type conversion on an already-correct type. In managed runtimes, each assignment may involve reference counting or pointer updates; in compiled languages, it still consumes store instructions. Even no-op assignments have measurable overhead in hot paths.

**Example:** Repeatedly converting an integer to int() inside a loop when it is already an integer; assigning x = x or overwriting a variable that was set two lines earlier and never read.

#### C1.S3 — Redundant Control Flow

Control flow constructs that do not alter program execution regardless of which branch is taken. This includes if-blocks with empty bodies, evaluating the same condition twice in sequence when the result cannot have changed, switch/match statements that fall through to identical behavior in every case, and try/except blocks where the try body cannot raise the caught exception. Energy is wasted on branch evaluation, comparison operations, and bytecode dispatch for constructs with no observable effect.

**Example:** An if-block with an empty body (if condition: pass) that evaluates the condition but takes no action; checking the same flag twice in the same function when nothing modifies it between checks.

#### C1.S4 — Repeated Computation

Performing the same calculation multiple times within the same scope when the underlying data has not changed between computations. This covers same-scope sequential redundancy: computing a derived value, then computing the identical value again a few lines later, or calling the same pure function with the same arguments at multiple points in a function body.

**Example:** Calling len(data) in two consecutive lines when the list has not been modified between the calls; computing a + b * c on line 10 and the identical expression again on line 20 without any change to a, b, or c.

#### C1.S5 — Resultless Computation

Code that executes, consumes CPU cycles and energy, but produces no output that any subsequent code uses. This includes functions whose return values are discarded by the caller, loops that iterate but never yield a result consumed outside the loop, loops where only the final iteration matters but all prior iterations also execute, and processing that generates semantically useless output. The computation could be removed entirely without affecting program correctness.

**Example:** Calling expensive_format(data) without assigning or returning the result; a loop that builds a cumulative result in each iteration but only the last iteration's value is ever read.

#### C1.S6 — Unnecessary Initialization

Performs setup, allocation, or computation on execution paths where the result may never be used or is immediately overwritten. This includes creating data structures at the top of a function that are only needed inside a rarely-taken branch, computing default values that the very next statement overwrites, and eagerly initializing resources (connections, file handles) before checking whether they are needed.

**Example:** Creating an empty list at the top of a function on every call even though it is only populated inside a rarely-taken if-branch; initializing config = load_config() before checking if cached_config already exists.

#### C1.S7 — Unnecessary Variable

Defining intermediate variables whose overhead exceeds their utility for readability or reuse. Every variable binding involves a store instruction, and in reference-counted runtimes it additionally triggers reference count increments and decrements. Variables used exactly once and not improving clarity add unnecessary binding, lookup, and memory-management overhead. The impact is small per instance but accumulates in hot paths.

**Example:** Assigning result = compute(x) and immediately returning result, when return compute(x) would eliminate the intermediate binding; defining a new variable every time after each computation where you don't use it afterwards.

#### C1.S8 — Excessive Runtime-Management Calls

Invoking expensive runtime housekeeping or logging operations more often than needed, consuming energy on maintenance work rather than useful computation. Explicitly calling garbage collection (e.g., gc.collect() in Python, System.gc() in Java) is expensive and usually unnecessary since modern runtimes have well-tuned automatic collectors. Similarly, evaluating expensive expressions inside logging calls without first checking if the log level is active wastes computation on messages that are never emitted. Also includes forcing finalization, excessive profiling instrumentation, and redundant diagnostic checks in production code.

**Example:** Calling gc.collect() inside a loop after every iteration; computing a complex summary string for a debug log message without guarding with if logger.isEnabledFor(logging.DEBUG).

</details>

---

### C2 — Unnecessary Call Overhead

Energy waste from extra layers of function calls, method delegation, or dynamic dispatch that add overhead without proportional benefit. This includes trivial wrapper methods that only forward to another function (unnecessary delegation), instance methods that never access instance state and could be static (missing static declaration), and performance-critical code paths split into too many tiny functions whose combined call overhead exceeds the useful work (excessive modularization). Each function call creates a stack frame, pushes arguments, and manages return values, making call overhead a significant factor in hot paths.

<details>
<summary>Show 3 subcategories</summary>

#### C2.S1 — Unnecessary Method Delegation

Delegates a simple operation through extra layers of calls, wrappers, getter/setter methods, or property accessors that add per-call overhead without meaningful abstraction benefit. Accessing an attribute via a property accessor invokes dynamic dispatch overhead: in Python the descriptor protocol creates a bound method, in Java the JVM performs virtual method dispatch, and in C# the property getter executes as a method call. For attributes accessed frequently in loops, this overhead is significant compared to direct field access. Similarly, trivial one-line methods that only forward calls add a full stack frame creation for no semantic value.

**Example:** A hot function calls helperA(), which only calls helperB() and returns its result unchanged, adding an extra frame creation for no value; accessing internal fields through @property getters/setters in a tight loop when direct self.attr access would avoid descriptor protocol overhead.

#### C2.S2 — Missing Static Declaration

Uses instance methods or dynamic dispatch when the operation does not depend on any instance state. Calling an instance method incurs dispatch overhead: in many languages this involves creating a bound method object, passing the implicit self/this reference, and traversing the method resolution order. Methods that never access instance state should be declared static (or equivalent) to avoid this overhead. The cost is small per call but accumulates in tight loops or frequently-called utility methods.

**Example:** Defining a helper as an instance method even though it never references self, causing unnecessary bound method creation on every invocation; a utility function like validate_email(s) defined as a regular method inside a class when it should be @staticmethod or a module-level function.

#### C2.S3 — Excessive Modularization in Hot Path

Splits a performance-critical flow into too many tiny layers (methods, wrappers, adapters, decorators) whose combined function call overhead exceeds or rivals the useful work performed. Each function call creates a new stack frame, pushes arguments, and manages the return value. In interpreted languages, each frame may cost ~200-400 bytes of memory, but even in compiled languages the overhead is non-trivial in tight loops. Consider inlining trivial functions in hot paths or merging sequential thin wrappers into a single function.

**Example:** A tight loop that calls validate(x), then normalize(x), then convert(x), where each is a one-line function, adding three frame creations per iteration when a single combined transform(x) function would suffice.

</details>

---

### C3 — Inefficient Iteration Patterns

Energy waste from loops that perform more per-iteration work than necessary, iterate more times than required, use suboptimal loop constructs, or fail to terminate correctly. This includes using slow iteration forms when faster alternatives exist (inefficient construct), recomputing values inside the loop that do not change across iterations (loop-invariant recomputation), performing expensive setup or allocation on every iteration (per-iteration setup), nested loops that could be flattened with better data structures (inefficient nesting), processing all items when only a subset is needed (unfiltered iteration), continuing past the point of usefulness (missing early exit), and modifying collections during iteration (array mutation).

<details>
<summary>Show 7 subcategories</summary>

#### C3.S1 — Inefficient Iteration Construct

Uses an iteration form with avoidable overhead when a more efficient or idiomatic alternative exists. Common instances include using index-based access (e.g., for i in range(len(lst))) instead of direct element iteration, not using comprehensions or builder patterns that compile to optimized internal instructions, explicitly calling methods like dict.keys() when the default iteration already returns keys, and using higher-order reduction functions where a simpler built-in or loop would be faster. The waste comes from unnecessary index lookups, redundant method calls, or per-element function call overhead.

**Example:** Iterating over a list with for i in range(len(a)) and repeatedly indexing a[i], instead of for item in a which avoids the index lookup; using a for-loop with .append() to build a list instead of a list comprehension [f(x) for x in data].

#### C3.S2 — Recomputing Loop-Invariant Values

Recomputes values inside the loop that remain constant across all iterations, paying the computation cost N times instead of once. This includes calling functions in the loop condition (e.g., while i < len(list) recalculating len() every iteration), evaluating static conditions inside the loop body, re-deriving values that depend only on variables unchanged within the loop, and using multiple sequential loops over the same data when a single pass would produce all needed results. Hoist invariant computations outside the loop to pay the cost once.

**Example:** Calling len(list) in the loop condition each iteration instead of caching n = len(list) before the loop; computing config["threshold"] * scale_factor inside every iteration when both values are constant throughout the loop.

#### C3.S3 — Inefficient Per-Iteration Setup

Creates expensive objects, performs heavy initialization, or allocates resources inside a loop body on every iteration when the work could be done once before the loop, reused across iterations, or avoided entirely. This includes initializing new containers inside the loop body, defining functions or closures within loops (creating new function objects each iteration), compiling regex patterns that should be pre-compiled once, and acquiring platform resources (file handles, locks, network connections) per iteration. The energy cost is the per-iteration allocation and cleanup multiplied by the full iteration count.

**Example:** Initializing a new list inside every iteration; defining a lambda inside a loop; calling re.search(pattern, text) in a loop instead of pre-compiling compiled = re.compile(pattern).

#### C3.S4 — Inefficient Nested Iteration

Uses nested loops where an equivalent approach would reduce overall complexity, typically from O(n^2) or worse to O(n). Common examples include nested scans over two lists to find matches that could be replaced with a set/dict lookup, Cartesian-product loops that could be replaced with database-level joins or vectorized operations, and nested loops over large data where the inner loop performs linear search that a hash-based structure would eliminate. Also the cases where we we can decrease from n^2 computation to n(n+1)/2 computation, this can be considered which indicates we should do it in triangular upper matrix search rather than full matrix search.

**Example:** Checking if any pair of numbers in two lists sums to a target using nested for-loops (O(n^2)), instead of building a set of complements and checking membership in a single pass (O(n)).

#### C3.S5 — Missing Loop Early Exit

Continues iterating after the required result has already been determined, wasting energy on iterations that cannot change the outcome. This includes search loops that find the target item but do not break, validation loops that discover the first failure but continue checking remaining items, and aggregation loops that reach a conclusive state but keep iterating. Use break, early return, or language-provided short-circuiting functions (e.g., any()/all() in Python, Stream.anyMatch() in Java) to terminate early.

**Example:** After finding a target item in a list, the loop continues processing remaining elements instead of breaking; a validation loop that checks all 10,000 records even after finding an invalid one on the 3rd record.

#### C3.S6 — Unfiltered Bulk Iteration

Processes all items in a collection even though only a subset, window, or top-k is needed for the final result. This includes mapping a transformation over an entire collection when only the first N results are consumed, sorting an entire collection to find the minimum or maximum when a single linear scan suffices, and loading all records from a data source to filter in application code when a query-level filter would reduce the result set at the source.

**Example:** When only the first 10 items of a list need to be doubled, mapping 2 * x over all 100,000 items instead of using itertools.islice or a generator that stops after 10; sorting an entire list to find the maximum element when max() does a single pass.

#### C3.S7 — Inefficient Array Mutation in Loop

Modifies the same collection being iterated (inserts, removes, reorders, appends), causing iteration anomalies, redundant re-indexing, or unbounded loop growth. In most languages, removing items from a list while iterating causes skipped elements or concurrent modification exceptions. Also includes loops that fail to terminate due to missing or incorrect break conditions.

**Example:** Removing items from a Python list while looping over it with for item in list, causing elements to be skipped; an infinite while loop due to forgetting to increment the loop counter or update the termination condition.

</details>

---

### C4 — Inefficient Control Flow

Energy waste from branching, conditions, or dispatch logic that performs unnecessary checks, uses suboptimal evaluation order, or employs patterns that prevent runtime optimization. This includes ordering conditions so expensive checks run before cheap ones (poor short-circuit ordering), evaluating conditions that are always true/false (redundant evaluation), using deeply nested branches instead of guard clauses (inefficient nesting), missing mutually-exclusive else-if chains, using expensive type introspection in tight loops (expensive comparison), using exception handling for frequent expected paths (expensive exception flow), not guarding against trivial edge cases (missing guards), and using non-idiomatic conditional patterns that miss runtime optimizations (non-idiomatic condition).

<details>
<summary>Show 8 subcategories</summary>

#### C4.S1 — Poor Short-Circuit Ordering

Orders AND/OR operands so that expensive or low-probability checks execute before cheap, high-probability ones, preventing the language's short-circuit evaluation from skipping unnecessary work. Most languages' logical AND stops at the first false; OR stops at the first true. Placing the cheapest or most-likely-to-terminate condition first avoids evaluating subsequent expensive conditions. Also includes using bitwise operators (& or |) instead of logical operators for boolean expressions, which forces evaluation of both operands.

**Example:** if expensive_check(x) and x is not None instead of if x is not None and expensive_check(x), where the cheap None check should come first to potentially skip the expensive call.

#### C4.S2 — Redundant Conditional Evaluation

Evaluates conditions that are always true or always false in the relevant context, or re-evaluates conditions whose result cannot have changed since the previous check. This includes OR between mutually exclusive conditions (always True), checking a flag that was just set to a known value, and testing a variable twice in the same branch path without any intervening modification.

**Example:** Checking x != None twice in the same branch path when nothing modifies x between checks; if a or not a which always evaluates to True, wasting cycles on an expression with a known result. Or for example when you know some number is always greater than zero, but you again check that if number is greater than zero (calling abs(x) on it).

#### C4.S3 — Inefficient Conditional Nesting

Uses deeply nested or monolithic conditional expressions that prevent early returns, cause repeated checks on overlapping conditions, and hinder readability and branch optimization. Refactor deep nesting with guard clauses (early returns), dictionary/map-based dispatch, or pattern matching constructs (e.g., match/case in Python 3.10+, switch expressions in Java 14+). Also includes selecting code paths that lead to unnecessary computation when simpler branch structures would suffice.

**Example:** Multiple nested if blocks that only gate access to a final simple operation, when a series of guard clauses with early returns would flatten the logic; a 15-deep if/else tree that could be replaced with a dictionary dispatch table.

#### C4.S4 — Missing Else-If

Uses multiple independent if statements when the branches are mutually exclusive. Each independent if evaluates its condition regardless of whether a prior branch already matched, whereas an if/elif chain stops evaluation at the first matching branch. For N mutually exclusive conditions, independent ifs always evaluate all N conditions; an elif chain evaluates on average N/2.

**Example:** Three separate if blocks checking ranges of the same value (0-10, 11-20, 21+), where an if/elif/else chain would stop at the first match instead of evaluating all three conditions.

#### C4.S5 — Expensive Comparison

Uses higher-cost type introspection, reflection, or runtime type checking when a simpler, cheaper comparison exists. Runtime type checks (isinstance in Python, instanceof in Java, is/as in C#) are fast individually, but become expensive when called per-element in large collections or tight loops. Prefer polymorphism, duck typing, pre-grouping objects by type, or visitor/dispatch patterns to eliminate per-iteration type checks.

**Example:** Using isinstance() checks inside a tight loop to dispatch different logic per type, instead of defining a common method interface and using polymorphic dispatch; using str(type(x)) string comparison instead of isinstance(x, TargetType). Or using high-precision float comparisons when integer/boolean checks suffice.

#### C4.S6 — Expensive Exception Control Flow

Uses try/catch (or try/except) as the primary mechanism for selecting between expected outcomes in contexts where exceptions are raised frequently, causing expensive exception object creation on every occurrence. Exception handling is efficient when exceptions are rare. However, when exceptions are the common case (e.g., most iterations in a loop raise), the cost of creating exception objects and unwinding the call stack makes conditional checks (if/else) more energy-efficient. The smell is not using exception handling itself, but using it in high-frequency exception contexts.

**Example:** Attempting a dictionary lookup via try: value = d[key] / except KeyError on a path where most keys are missing, instead of using value = d.get(key, default) or checking if key in d first.

#### C4.S7 — Missing Edge-Case Guards

Fails to check trivial, common, or degenerate inputs that would allow skipping expensive general-case processing entirely. This includes not checking for empty or single-element input before running a full sort algorithm, not checking for a simple type before performing complex generic serialization, and not modifying input flags to trigger existing fast execution paths within called functions.

**Example:** Not checking for an empty list before running a full sort algorithm, when returning immediately would save all computation; performing full JSON parsing on an input string without first checking if it is a simple numeric literal.

#### C4.S8 — Non-Idiomatic Condition

Uses non-idiomatic conditional patterns that are verbose, error-prone, or miss runtime optimizations. Modern runtimes optimize common idiomatic patterns, so deviating from them incurs unnecessary overhead. This includes explicit length-based emptiness testing (if len(x) == 0) instead of direct boolean evaluation (if not x), unchained comparisons (if a < b and b < c instead of a < b < c in languages that support chaining), comparing floating-point numbers for exact equality instead of tolerance-based comparison, and comparing with NaN using equality instead of dedicated NaN-check functions.

**Example:** Using if len(my_list) == 0 instead of if not my_list; writing if a < b and b < c instead of if a < b < c which Python evaluates more efficiently.

</details>

---

### C5 — Suboptimal Data Structures

Energy waste from choosing, provisioning, or converting data structures that do not match the workload's access pattern or size requirements. This includes using a structure with worse complexity for the dominant operation (inefficient choice), failing to introduce an auxiliary index or lookup structure that would eliminate repeated scans (missing helper), choosing a heavier representation than the data requires (over-provisioned type), and converting between formats without a net efficiency gain (unnecessary representation change).

<details>
<summary>Show 4 subcategories</summary>

#### C5.S1 — Inefficient Data Structure Choice

Uses a data structure with worse asymptotic or constant-factor behavior for the workload's dominant operations. Common mismatches include using a list/array for frequent membership tests (O(n)) when a hash set provides O(1), using a hash map for ordered sequences of dense integer keys when an array provides direct index access, and using heavyweight class instances for simple records when lighter alternatives exist (e.g., structs, records, data classes with slot optimization, or plain tuples).

**Example:** Using a list for frequent membership tests when a set would give O(1) lookup instead of O(n); storing records as dicts of dicts when a list of namedtuples would provide faster attribute access and lower memory overhead.

#### C5.S2 — Missing Helper Type

Fails to introduce an auxiliary data structure (index, lookup table, cache) that would turn repeated expensive operations into cheap lookups. This includes repeatedly scanning a list to find matching entries instead of building a dict/set index once, performing O(n) search in a sorted collection instead of building a set for O(1) membership, and not precomputing a mapping that would eliminate repeated linear traversals.

**Example:** Repeatedly scanning a list of 10,000 records to find matching IDs in an inner loop, instead of building a lookup dictionary id_map = {r.id: r for r in records} once and using O(1) dict access.

#### C5.S3 — Over-Provisioned Data Type

Chooses a heavier type, structure, or representation than the data's constraints require. This includes using a hash map for simple enumerable data when an enum or constant set suffices, using a sorted container when insertion-order preservation by a standard map meets the need, creating full class instances with per-instance dictionary overhead when lightweight record types or tuples would work, and using complex collection wrappers for data that could be stored as a simple array.

**Example:** Storing a single-character value as a full string object where a character code would suffice in a tight numerical loop; using a SortedDict when insertion-order preservation by plain dict is sufficient.

#### C5.S4 — Unnecessary Representation Change

Introduces an intermediate structure or converts between data representations without a net efficiency gain. This includes converting a generator to a list only to iterate over it once, repeatedly serializing/deserializing data on frequently executed paths, and performing data transformations whose creation cost exceeds the operational benefit of the new structure.

**Example:** Converting a generator to a list only to iterate once and discard it, when for item in generator would avoid the allocation; repeatedly converting between dict and JSON string representations on every API call when keeping a consistent internal format would eliminate conversion.

</details>

---

### C6 — Unnecessary Memory Usage

Patterns that allocate, copy, retain, or leak memory beyond what the workload requires, increasing garbage collection overhead, memory-bus traffic, and system energy consumption. This includes creating more objects than needed (unnecessary creation), copying data when in-place operations or references suffice (unnecessary copying), materializing lazy sequences into full collections prematurely (unnecessary materialization), retaining oversized structures when compact representations would work (oversized retaining), pre-allocating far more capacity than typical usage (over-allocation), failing to release system resources (leaked handles), and mutable default arguments that accumulate state across calls (leaking defaults).

<details>
<summary>Show 7 subcategories</summary>

#### C6.S1 — Unnecessary Object

Creates more objects than necessary, including short-lived, duplicate, or oversized instances that increase garbage collection pressure. This includes creating new objects via concatenation when interned or pooled literals would suffice, instantiating objects inside loops when a single instance could be reused or cleared, creating multiple identical immutable instances instead of sharing a single flyweight, and using heavyweight class instantiation when lighter record types or tuples would work.

**Example:** Creating a new empty list inside every loop iteration to collect temporary results, when a single list created before the loop and cleared with .clear() each iteration would avoid repeated allocation.

#### C6.S2 — Unnecessary Copying

Copies objects or data structures when a reference, view, slice, or in-place operation would preserve correctness without extra allocation. This includes using a function that returns a new sorted copy when in-place sort would work, using temporary variables for swapping when the language provides tuple unpacking or parallel assignment, manually copying collections element-by-element when built-in copy mechanisms exist, and storing redundant copies of the same data in multiple locations instead of sharing references.

**Example:** Copying an entire list before read-only iteration when the original list is not modified; using tmp = a; a = b; b = tmp to swap values instead of Pythonic a, b = b, a.

#### C6.S3 — Unnecessary Data Materialization

Materializes intermediate data structures fully in memory when lazy evaluation would suffice. Use lazy sequences (generators in Python, streams in Java, IEnumerable in C#) instead of eager collection construction when the result is consumed exactly once. Avoid converting lazy sequences to concrete collections before passing to functions that already accept iterables. Stream file content incrementally instead of reading entire files into memory. Lazy evaluation produces one element at a time without allocating memory for the full result, which is critical for large datasets where full materialization could exhaust available memory.

**Example:** Reading a whole file into memory with file.read() when line-by-line streaming with for line in file would process data incrementally; using list(generator) before passing to sum() when sum(generator) directly consumes the generator lazily.

#### C6.S4 — Oversized Data Retaining

Keeps entire data structures in memory when smaller representations (indices, IDs, compressed forms, aggregates) would suffice for the use case. This includes retaining full object graphs in caches when only identifiers are needed for later lookup, storing complete strings or records when storing offsets/indices into a shared buffer would reduce footprint, and keeping uncompressed data in memory when compression would significantly reduce resident set size.

**Example:** Storing full user profile objects (name, email, preferences, history) in a session cache when only user IDs are needed for subsequent lookups; keeping entire file contents in a variable when only a hash or line count is needed downstream.

#### C6.S5 — Over-Allocation

Allocates larger buffers, containers, or memory regions than typical inputs require, increasing memory footprint, cache pressure, and garbage collection cost for capacity that is never utilized. This includes pre-allocating very large fixed-size arrays/buffers for functions that typically process small inputs, and using initial capacity hints that vastly overestimate actual usage.

**Example:** Allocating a 10,000-element buffer for a function that typically processes fewer than 100 items; pre-sizing a dict with capacity for 1 million entries when the typical workload stores fewer than 1,000.

#### C6.S6 — Leaked Resource Handles

Fails to release external resources (file handles, sockets, database connections, cursors) promptly after use. Use language-provided resource management constructs (with-statement in Python, try-with-resources in Java, using-statement in C#, RAII in C++) to ensure deterministic cleanup even if exceptions occur. Relying on garbage collection to close resources is unreliable across runtimes and can exhaust OS resource limits.

**Example:** Opening database connections in a loop without closing them, eventually exhausting the connection pool; opening files with open() without using a "with" block, relying on GC to close them.

#### C6.S7 — Leaking Mutable Default Arguments

Uses a mutable object (list, dict, set) as a default parameter value, causing it to persist and grow silently across function calls. In languages where default values are evaluated once at function definition time (notably Python), each call that mutates the default object leaves accumulated state that increases memory usage. Fix by using a sentinel default (e.g., None) and creating the mutable object inside the function body.

**Example:** def f(x, acc=[]): acc.append(x); return acc -- calling f(1), f(2), f(3) returns [1], [1, 2], [1, 2, 3] because the same list object persists and grows across calls.

</details>

---

### C7 — Suboptimal Algorithmic

Energy waste from choosing an algorithm, decomposition, or computation strategy that explores more of the problem space than necessary or uses higher complexity than the problem requires. This includes selecting algorithms with worse complexity (suboptimal choice), failing to prune, order, or memoize subproblem exploration (inefficient decomposition), using recursion where iterative solutions are straightforward and more efficient (avoidable recursion), performing operations in a suboptimal order (inefficient ordering), and failing to simplify inputs before applying expensive operations (unsimplified operation).

<details>
<summary>Show 5 subcategories</summary>

#### C7.S1 — Suboptimal Algorithm Choice

Uses an algorithm with known worse time or space complexity, or higher constant factors, for the problem at hand when a more efficient alternative is available. Common examples include using O(n^2) nested iteration when O(n) hash-based approaches exist, implementing a naive sort in a hot path when the language's optimized standard library sort is available, and CPU-intensive methods that could benefit from algorithmic redesign or delegation to optimized native libraries.

**Example:** Using a naive O(n^2) bubble sort in a hot path when Python's built-in sorted() uses optimized Timsort; linearly scanning a sorted list for a value instead of using bisect.bisect_left() for O(log n) binary search.

#### C7.S2 — Inefficient Problem Decomposition

Decomposes a problem in a way that leads to unnecessary, redundant, or poorly-ordered subproblem computation. This includes brute-force approaches that explore the full combinatorial space without applying constraints or pruning, solving subproblems that cannot affect the final output, exploring subproblems in an order that delays pruning or early termination, and re-solving overlapping subproblems without storing intermediate results.

**Example:** Trying every possible combination of parameters exhaustively when simple bound checks could prune 90% of candidates; sorting an entire list to find the maximum element when max() suffices; a recursive function that recomputes the same Fibonacci sub-values thousands of times without caching.

#### C7.S3 — Avoidable Recursive Implementation

Uses recursion where an iterative solution is straightforward and more efficient. Many runtimes do not perform tail-call optimization (notably CPython, JVM by default) and impose recursion depth limits. Each recursive call creates a new stack frame with its own local variables, argument bindings, and instruction pointer. For problems with deep recursion, convert to iterative approaches using explicit stacks, queues, or accumulator patterns.

**Example:** Computing a simple cumulative sum via recursion over a list instead of an iterative loop with an accumulator; implementing tree traversal recursively when an explicit stack-based iteration would avoid frame overhead for deep trees.

#### C7.S4 — Inefficient Operation Ordering

When two or more operations can be applied in any order and produce the same result, executes the more expensive operation first. Reordering cheap filter, prune, or validation steps before expensive transformations reduces the input size for the costly step. This principle applies to database queries (filter before join), data pipelines (validate before transform), and any sequential processing where a cheap early step can reduce the volume flowing into an expensive later step.

**Example:** Sorting a 100,000-element list and then filtering to items > 100 (sorting all 100K), instead of filtering first (producing maybe 5K items) and then sorting the smaller result.

#### C7.S5 — Unsimplified Operation

Performs a heavy operation on inputs that could be algebraically simplified, pre-reduced, or partially evaluated first. By simplifying the input before applying the expensive operation, the total work is reduced. This includes computing expressions with known-zero or known-identity terms, running full parsing on input that could be short-circuited by a cheap pre-check, and applying general-case logic when algebraic simplification would eliminate entire branches of computation.

**Example:** Computing (x * 0) + (y * 1) instead of simplifying to y; running a full regex match when a simple str.startswith() check would determine the result for the common case.

</details>

---

### C8 — Missing Reuse

Energy waste from failing to store and reuse results of expensive computations, lookups, or data fetches, causing the same work to be repeated across calls, requests, or access sites. This includes not caching deterministic function results for repeated identical inputs (missing memoization), not pre-computing and storing derived artifacts like compiled regex or parsed configs (missing derived-value reuse), not caching chained attribute/scope lookups in local variables in hot code (missing local lookup caching), and repeatedly fetching the same data from external sources when local caching would eliminate the round-trip (redundant data fetching). Distinguished from Redundant Computation (C1) by spanning across calls or access sites rather than within a single scope.

<details>
<summary>Show 4 subcategories</summary>

#### C8.S1 — Missing Memoization Cache

Recomputes deterministic, expensive function results for identical inputs instead of caching and returning the stored result. Use language-provided memoization mechanisms (e.g., functools.lru_cache in Python, @Cacheable in Spring) or explicit dictionaries/maps to store previously computed values. The key characteristic is that the function is deterministic and the recomputation spans different call sites or invocations, not sequential lines in the same function.

**Example:** Recomputing an expensive parse/analysis function for the same string key on every request, when @functools.lru_cache(maxsize=128) would store and return the cached result for repeated inputs. Computing expensive function on the same numbers where you can use reuse the already computed values, like is_prime(x), where multiple x (same value) exist in the set.

#### C8.S2 — Missing Derived-Value Reuse

Recreates expensive derived artifacts (compiled regex patterns, parsed configuration, prepared SQL statements, formatted template objects) on every use instead of computing once and storing for reuse. Compile regex once and reuse the compiled object, parse configuration at startup and cache at module/class level, and prepare database statements once rather than re-parsing on every query execution.

**Example:** Compiling the same regular expression on every function call with re.search(r"\d+", text) inside a loop, instead of compiled = re.compile(r"\d+") once before the loop and compiled.search(text) inside.

#### C8.S3 — Missing Local Lookup Caching

Repeatedly performs chained attribute access, global variable lookups, or built-in function resolution in hot code instead of caching the result in a local variable. In many languages, global and nested attribute lookups are slower than local variable access due to scope chain traversal and dynamic dispatch. Caching frequently accessed references in local variables before a loop eliminates per-iteration lookup overhead.

**Example:** Inside a loop, repeatedly reading obj.config.settings.threshold instead of caching threshold = obj.config.settings.threshold before the loop; calling len (a global built-in) inside a tight loop instead of local_len = len before the loop.

#### C8.S4 — Redundant Data Fetching

Repeatedly retrieves the same data from an external source (database, network API, file system) when the result could be cached locally because it has not changed or changes infrequently. This includes issuing identical database queries multiple times within a single request, repeatedly loading the same configuration file from disk when it only changes on restart, and making redundant API calls for data that could be cached with a TTL.

**Example:** Loading a configuration file from disk on every incoming request when it only changes on application restart; querying SELECT * FROM settings WHERE key = "theme" five times in the same request handler without caching the first result.

</details>

---

### C9 — Inefficient External Data Access

Energy waste from inefficient interaction with external systems: databases, file systems, network services, and APIs. This includes performing many small operations individually instead of batching (fragmented I/O), fetching or transmitting more data than the application consumes (oversized retrieval), requiring multiple dependent round-trips when a single joined or combined query would suffice (inefficient retrieval paths), and using query patterns that are inherently expensive to execute (expensive query patterns). Each external interaction involves system call overhead, network latency, serialization/deserialization, and potentially database query planning, making efficiency in this category high-impact.

<details>
<summary>Show 4 subcategories</summary>

#### C9.S1 — Fragmented I/O Calls

Performs many small I/O, network, or database operations individually instead of batching into fewer, larger bulk transfers. This includes saving database records one-by-one instead of using bulk create/update APIs, writing to files line-by-line instead of using buffered I/O or batch-write functions, making N individual HTTP requests instead of a single batch API call, and issuing multiple separate database queries for data that could be retrieved in one combined query.

**Example:** Issuing one database INSERT per row in a loop of 10,000 rows instead of using bulk_create() for a single batch operation; writing log entries one line at a time with file.write() instead of buffering and using writelines().

#### C9.S2 — Oversized Data Retrieval

Fetches, transmits, or stores more data than the application logic actually consumes. This includes using SELECT * when only specific columns are needed, issuing unbounded queries without LIMIT, retrieving full result sets to display a small subset, transmitting data without compression when compression would significantly reduce transfer cost, downloading full records including large binary fields when only small metadata is needed, and over-eager loading that pulls in large related datasets causing memory pressure.

**Example:** Downloading full records including large blobs when only a small identifier field is needed; using SELECT * FROM users (retrieving all 50 columns) when only name and email are used in the application.

#### C9.S3 — Inefficient Retrieval Paths

Requires multiple dependent data retrieval steps when a single combined or pre-joined query would produce the same result. This includes the N+1 query anti-pattern (one initial query returning N results, then N additional queries for related data), chaining sequential lookups across tables, and ORM APIs that generate suboptimal SQL behind the scenes. Use eager loading or join strategies provided by the ORM framework to avoid N+1 patterns.

**Example:** Querying a list of 100 orders, then issuing 100 separate queries to fetch each order's customer details, instead of a single JOIN or select_related("customer") that retrieves everything in one round-trip.

#### C9.S4 — Expensive Query Pattern

Uses query structures that are inherently costly for the database engine to execute. This includes cartesian products from missing join conditions, UNION with deduplication instead of UNION ALL when results are known to be disjoint, excessive joins and sub-queries on large tables, and not using parameterized queries (prepared statements), forfeiting query plan caching and forcing the database to re-parse on every execution.

**Example:** Using UNION (which sorts and deduplicates) instead of UNION ALL when the underlying queries produce disjoint results; building SQL strings with f-strings instead of parameterized placeholders, preventing the database from caching execution plans.

</details>

---

### C10 — Underused Language Primitives

Energy waste from not using available optimized language features, standard library functions, or runtime-specific constructs that would accomplish the same task more efficiently. This includes manually reimplementing functionality available as optimized built-ins (skipping built-ins), choosing a less efficient built-in when a faster one exists (inefficient choice), using per-element loops when bulk/vectorized primitives exist (missing bulk usage), building strings via repeated concatenation instead of mutable builders (inefficient string concatenation), placing variables in scopes with unnecessary lookup overhead (inefficient scope), and using operators on custom types that trigger expensive overloaded methods (expensive operator overloads).

<details>
<summary>Show 6 subcategories</summary>

#### C10.S1 — Skipping Optimized Built-ins

Manually implements functionality already available as a highly optimized built-in or standard library function. Most languages provide optimized native implementations for common operations (sum, min, max, sort, search). These are typically implemented in a lower-level language (C for Python, native code for JVM/CLR) and execute significantly faster than equivalent hand-written loops in the host language.

**Example:** Writing a manual min/max scan with a loop and comparison when the built-in min()/max() does the same in C; implementing a custom merge function when itertools.chain() or heapq.merge() would be faster and more correct.

#### C10.S2 — Inefficient Built-in Choice

Chooses a built-in, standard library function, or language construct that is semantically equivalent to a faster alternative for the specific task. Examples include using length-based emptiness checks instead of direct boolean evaluation, using runtime type comparison instead of polymorphic dispatch, using regex for simple prefix/suffix checks when dedicated string methods are faster, and using modulo for parity checks in tight numerical loops when bitwise AND is faster.

**Example:** Using re.match("^prefix", s) to check if a string starts with "prefix" instead of s.startswith("prefix"), which avoids the overhead of regex compilation and matching.

#### C10.S3 — Missing Bulk Primitive Usage

Uses per-element operations in a loop when a bulk, batched, or vectorized language primitive exists that does the same work in optimized native code. This includes appending elements one at a time instead of using batch-add operations, copying collections element-by-element instead of using built-in copy/slice mechanisms, and looping over numerical array elements instead of using vectorized operations (e.g., NumPy in Python, SIMD intrinsics in C/C++). Vectorized operations can be 10-100x faster than equivalent interpreted loops for numerical data.

**Example:** Appending elements one at a time in a for-loop with .append() instead of using list.extend(new_items); looping over a NumPy array element-by-element to compute a sum instead of using np.sum(array).

#### C10.S4 — Inefficient String Concatenation

Builds strings via repeated concatenation (s += part), especially inside loops, causing repeated allocation of new immutable string objects in languages where strings are immutable (Python, Java, C#, Go). Each concatenation creates a new string, copies all previous content plus the new part, and discards the old string. For N concatenations of average length M, this is O(N*M) total copying. Use mutable string builders (StringBuilder in Java/C#, list join in Python, strings.Builder in Go) for O(N+M) total.

**Example:** s = s + part inside a loop over 10,000 parts, creating 10,000 intermediate string objects, instead of parts.append(part) followed by s = "".join(parts) which creates only the final string.

#### C10.S5 — Inefficient Scope Lookup

Places variables in a scope that incurs unnecessary lookup overhead for the access frequency and pattern. In many languages, local variable access is faster than global or module-level access due to scope chain traversal. For example, local variables use direct array indexing in Python and stack-allocated slots in JVM languages. Assigning a frequently accessed global or module-level variable to a local variable before a tight loop converts each access from a chain lookup to a direct local access.

**Example:** Repeatedly reading a global constant MAX_RETRIES inside a tight loop of 100,000 iterations, instead of local_max = MAX_RETRIES before the loop, saving a LEGB chain traversal per iteration.

#### C10.S6 — Expensive Operator Overloads

Uses operator syntax (+, *, ==, <, in) on non-primitive or user-defined types where the operator invokes expensive overloaded methods (e.g., __add__ in Python, operator+ in C++, compareTo in Java) with full method dispatch overhead. Each operator on a custom object triggers method lookup, dispatch, and function call mechanics. In tight loops, this overhead accumulates significantly.

**Example:** Using A + B in a tight loop where A and B are custom Matrix objects whose __add__ creates a new Matrix each time, adding method dispatch + object creation overhead per iteration.

</details>

---

### C11 — Inefficient Concurrency Management

Energy waste from thread/task misuse, synchronization overhead, contention, or failure to exploit available parallelism. This includes heavyweight or over-broad locking (excessive contention), architectural bottlenecks that force serial execution (serial bottleneck), threads or tasks that are never properly stopped (leaked threads), running heavy work on the main/UI thread (blocking main thread), and executing independent work serially when concurrency would reduce total time and energy (missed parallelism). In runtimes with a global interpreter lock, threading is ineffective for CPU-bound work; use multiprocessing or parallel frameworks instead.

<details>
<summary>Show 5 subcategories</summary>

#### C11.S1 — Excessive Lock Contention

Uses heavyweight synchronization too frequently, on overly broad critical sections, or with coarse-grained locks that serialize work that could safely proceed in parallel. In runtimes with a global interpreter lock (e.g., CPython), additional application-level locks further degrade performance. Use fine-grained locks, lock-free data structures, atomic operations, or per-thread state to reduce contention.

**Example:** Guarding a frequently updated counter with a global lock across many threads, causing all threads to wait for each increment, when per-thread counters merged periodically would eliminate contention.

#### C11.S2 — Forced Serial Bottleneck

Architecture forces single-file execution through a single shared resource, global lock, or pipeline stage that all threads/processes must pass through, negating the benefit of parallelism. This turns a theoretically parallel system into an effectively serial one while still paying the overhead of thread/process management.

**Example:** A pipeline with many worker threads that all must acquire a single global database connection for every operation, meaning only one thread can do useful work at a time while all others wait.

#### C11.S3 — Leaked Background Threads

Starts threads, processes, or async tasks that are never stopped, joined, or allowed to terminate cleanly. Leaked threads consume memory for their stack, may contend for shared resources (including interpreter locks), and can prevent clean process shutdown. Use daemon threads for background work that should not prevent shutdown, implement proper shutdown signals, and always join threads that perform critical work.

**Example:** Spawning a background thread per incoming request and never terminating it, leading to thousands of idle threads consuming memory and periodically acquiring the GIL.

#### C11.S4 — Blocking The Main Thread

Performs long-running CPU or I/O work on the main event loop or UI thread, causing the application to freeze while wasting energy on idle synchronization waits. In async applications, blocking the event loop with synchronous calls (time.sleep, synchronous HTTP requests, file I/O) stalls all other coroutines. Offload heavy work to background threads, processes, or use async-native libraries.

**Example:** Running a large database query on the main UI thread, freezing the application for seconds; calling requests.get() (synchronous) inside an async def function, blocking the asyncio event loop.

#### C11.S5 — Missed Parallelism Opportunities

Executes independent work items serially even though they could run concurrently, underutilizing available CPU cores or I/O bandwidth. For CPU-bound work, use multiprocessing or parallel execution frameworks. For I/O-bound work, use asynchronous I/O or thread pools. A common mistake in runtimes with a global interpreter lock is using threads for CPU-bound work, which provides no speedup.

**Example:** Processing 1,000 independent image files one-by-one on an 8-core machine, instead of using ProcessPoolExecutor(max_workers=8) to process 8 images simultaneously; making 50 sequential HTTP API calls when asyncio.gather() would execute them concurrently.

</details>

---

### C12 — Poor Hardware Locality Usage

Energy waste driven by CPU and memory hierarchy behavior such as cache misses, branch misprediction, and suboptimal memory access patterns. While developers in high-level languages have limited direct control over hardware-level behavior compared to C/C++, certain access patterns (especially when using contiguous-memory array libraries or native extensions) can still trigger cache inefficiencies. This category covers patterns where restructuring data access order or layout can improve cache utilization, reduce memory-bus traffic, and lower branch misprediction penalties.

<details>
<summary>Show 4 subcategories</summary>

#### C12.S1 — Inefficient Large-Stride Traversal

Traverses arrays, matrices, or multi-dimensional data structures with a stride pattern that causes frequent cache misses. When data is stored in contiguous memory (e.g., C arrays, NumPy arrays, Java primitive arrays), accessing elements in a non-sequential order (e.g., column-by-column in a row-major layout) skips over memory regions, defeating spatial locality and hardware prefetching.

**Example:** Accessing a 2D NumPy array column-by-column (arr[:, j] in an inner loop over j) when it is stored in row-major (C) order; transposing the iteration order or the array layout would improve cache hits.

#### C12.S2 — Sparse Element Access

Touches a small, scattered subset of elements inside a large contiguous data structure repeatedly, preventing efficient cache line utilization. Each access to a random position in a large array brings an entire cache line into L1/L2 cache, but if subsequent accesses are far apart, most of that cache line's data goes unused before eviction.

**Example:** Repeatedly accessing random indices of a large NumPy array (1M elements) in a tight loop, where each access loads a cache line but the next access is far away, wasting the loaded data.

#### C12.S3 — Unpredictable Branches

Uses highly data-dependent branching patterns in tight loops that defeat branch prediction hardware, causing pipeline stalls and wasted speculative execution energy. Modern CPUs predict branch outcomes to keep the pipeline full; when predictions are wrong (e.g., a branch that goes 50/50 based on random data), the pipeline must be flushed and restarted. This effect is most measurable in compiled code, JIT-compiled hot paths, or native extensions called from high-level languages.

**Example:** A tight loop with if random_data[i] > 0.5 where the condition is essentially random, causing ~50% branch misprediction; sorting the data first would make the branch pattern predictable.

#### C12.S4 — Inefficient Array Declaration Order

Declares or allocates frequently-used arrays or buffers after less-used ones, causing the hot data to be placed at memory offsets that are less cache-friendly. In compiled languages and native extensions, this directly affects addressing efficiency. Placing frequently accessed data structures first in declaration order or in adjacent memory regions improves spatial locality.

**Example:** In a C extension or Cython module called from Python, declaring a rarely-accessed error_logging buffer before a frequently-accessed data_processing buffer, pushing the hot buffer further from the frame base address.

</details>

---
