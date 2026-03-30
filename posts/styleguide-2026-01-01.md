# C++ Style Guide

## Introduction

### Goals of the Guide

- Settle trivial disagreements in code review
- Enable trivial onboarding between projects
- Enable trivial checking in code

> [!NOTE]
> It was a deliberate choice to repeat the word trivial that many times. To pull
> from the broader engineering style guide, "\[building\] is cheap, \[good\] ideas aren't."
>
> We don't want someone else's code to get in the way of your ideation, nor the opposite.

### Scope & Applicability

- All PRs should reference the latest style guide.
- Our goal is to release updated tooling and configs on the same date as a
new style guide.
- PRs that exist explicitly to update to new style guides are likely a waste
of time.

### Relationship to clang-21 & C++23

- Currently we target C++23 features as implemented by clang-21.
    - This __should__ be installed on your development machine.
    - It is the __only__ clang installed on the ``distcc`` and ``sccache``
    servers.

### Enforcement

We recommend the following hierarchy for rules enforcement in review, 1. CI ; 2. reviewer; 3. lint tooling.
With higher number representing higher precedence.

> [!TIP] It is worth noting that if reviewers vehemently disagree with a lint output,
> they should open an issue for the tool and the styleguide.

## Language Version & Compiler Targets

### Target Standard (C++23)

As mentioned earlier, we target C++23 as it is implemented by clang-21.

Therefore, the following ``static_assert`` must be added to every translation unit.

```cpp
#if !defined(__clang__) || __cplusplus < 202302L
static_assert(false, "Build Error: Strict requirement for Clang-21+ and C++23")
#endif
```

There's not much preference for upgrading to new standard library features
since memorizing every new addition is unproductive. It is however
worthwhile to implement them in new features since it lessens testing burden
and "boilerplate" code.

### Required Compiler Flags

Compiler flags are typically handled by tooling and will look as such:

```make
# Release
CXXFLAGS = -std=c++23 -O3 -Wall -Wextra -Wpedantic -Wshadow -DNDEBUG -march=native -flto=full -ffunction-sections -fdata-sections
# DEBUG
    # note: the set of sanitizers can be configured but these are the defaults for debugs
CXXFLAGS = -std=c++23 -O0 -ggdb -Wall -Wextra -Wpedantic -Wshadow -DDEBUG -fsanitize=address,undefined
```

### Prohibited Compiler Flags

- `-Ofast`, this loops in `-ffast-math`.
- `-ffast-math`.
    - NOTE: this is acceptable via ``#pragma push/pop`` in non-critical blocks.
This list is eligible for expansion over time.

### Linking and Linker Flags

Linker flags are again handled by tooling but the underlying goal is to maximize link-time optimization while
minimizing binary size (the goals are often complementary), as such the following is prescribed:

- `-fuse-ld=mold`
    - Mandated for link speed and avoid link-time sequential execution.
- `-flto=full`:
    - To allow for optimization, the linker needs full context of the program, as such full link-time-optimization creates a single massive object and runs multiple compilation passes.
    - Since this makes linking heavily sequential, in `DEBUG` builds, use `-flto=thin`
- `-Wl,-O3`: Instructs the LTO plugin to apply maximum optimization passes across the entire merged AST.
    - To allow for the linker to fully optimize the final object, we run as many LTO passes as possible.
    - This can be omitted in debug builds.
- `-Wl,--gc-sections`: Strips dead code and unused symbols to avoid binary size bloat.
- `-Wl,--icf=safe`:
    - Given our heavy use of templates and `constexpr`, a lot of code is duplicated.
    - This folds identical generated binary sequences into a single copy, massively reducing binary bloat without breaking function pointer equality.
- `-Wl,--as-needed`: Prevents `DT_NEEDED` bloat by only linking shared libraries if we actually use a symbol from them.

#### Other flags

| Flag | Purpose | Approval in DEBUG/RELEASE |
| ---- | ---- | ---- |
| `-Wl,--no-undefined` | Forces the linker to report unresolved symbols in shared libraries at link-time rather than deferring to runtime. Catches missing dependencies immediately instead of segfaulting in production. | Both |
| `-Wl,--hash-style=gnu` | Uses the faster GNU hash table format for dynamic symbol resolution. Massively reduces startup time for dynamically linked executables compared to the default SysV hash. | Both |
| `-Wl,--build-id=sha1` | Embeds a unique cryptographic identifier in the binary. Absolutely crucial for matching production binaries to external debug symbols or accurately tracking crash minidumps. | Both (use `=fast` in Debug for fast builds) |
| `-Wl,-z,relro,-z,now` | Hardens the binary by marking the Global Offset Table (GOT) as read-only and resolving all dynamic symbols at startup (Full RELRO). Mitigates GOT overwrite exploits. | Release Only |
| `-Wl,--strip-all` | Strips all symbol and relocation information from the final executable. Used to aggressively minimize binary bloat before deployment. | Release Only |


#### Final `LDFLAGS` Configurations

DEBUG `LDFLAGS`:

```make
# Debug builds
LDFLAGS = -fuse-ld=mold -flto=thin -Wl,--as-needed -Wl,--no-undefined -Wl,--hash-style=gnu -Wl,--build-id=fast
# Release Builds
LDFLAGS = -fuse-ld=mold -flto=full -Wl,-O3 -Wl,--gc-sections -Wl,--icf=safe -Wl,--as-needed -Wl,--no-undefined -Wl,-z,relro,-z,now -Wl,--hash-style=gnu -Wl,--build-id=sha1 -Wl,--strip-all
```


## Project Structure

### Monorepo Layout

```
/ (Monorepo Root)
├── WORKSPACE.yaml
└── Projects/
    ├── ProjectA/
    │   ├── catalyst.yaml
    │   ├── build/                          <-- Build output for ProjectA
    │   ├── include/
    │   │   ├── ProjectA/                   <-- Standard namespaced includes
    │   │   │   ├── header1.hpp
    │   │   │   └── header2.hpp
    │   │   └── extra_v1/                   <-- Optional extra one-offs
    │   │       └── legacy_compat.hpp
    │   ├── src/                            <-- src files
    │   │   ├── ProjectA.cpp                <-- Entry point. Must bear the same name as the project.
    │   │   └── utils.cpp
    │   │       └── legacy_compat.hpp
    │   │       └── legacy_compat.hpp
    │   ├── test/                          <-- tests
    │   └── bench/                         <-- benchmark
    └── ProjectB/
```

<!--NOTE: this is outdated; fix to show test.lua/benchmark.lua-->

This monorepo structure makes it abundantly clear what the scope of a project is and
allows instantiation of one project for distribution, testing, compilation, etc.

## Header Standards

### Header Ownership

- In general, every subcomponent of the project has an associated header file.

### Header Closure

- Header files should be self-contained (compile on their own) and end in .hpp.
- Non-header files that are meant for inclusion should end in .inc and be used sparingly.
    - The use of `.inc` is reserved for xxd or other codegen tooling. Such includes, should have a comment, referring to where they come from.
- All header files should be self-contained, i.e. including header_X with or without some header_Y does not have hidden effect.

### Templates & Inline Definitions

- When a header declares inline functions or templates that clients of the header will instantiate,
the inline functions and templates must also have definitions in the header, either directly or in files it includes.

### Include Order Rules

The order is as follows:
1. subsystem header
2. system headers
3. STL headers
4. external library headers
5. internal headers

> [!ERROR] The include_next directive is banned. It leads to non-deterministic builds across systems and it's typically a sign of improper header naming.

#### Header Guards

- Conditional includes are allowed.
- Headers that are conditionally included should follow the order as if the condition does not exist.
- When possible, the condition should be moved to the header itself, to allow users to include without
worrying about the guard.
    - Broad header guards, e.g. ``#ifdef _WIN32`` should be reflected in the header name, e.g. ``win32_xyz``.


### Forward Declarations vs Includes

- Forward Declarations are not allowed, since they let tools like ninja or
catalyst skip over forced rebuilds because of header changes.

We maintain that forward declarations are banned because Catalyst preempts
header precompilation and our build server aggressively builds. As such, we
have sufficient build speed to make the slight hit bearable in exchange for
build determinism.

### Pragma Once Policy

Header guards are disallowed. Use ``#pragma once`` to avoid the off chance of header guard collision.

### Tooling

Most of this will be flagged prior to push by [``pinc-eye``](@DIRECTIVE:COPY:$(self.hostname.root)/tooling/p-include-watcher).

If you observe a disparity between ``pinc-eye``, ``iwyu``, and ``clang-tidy``, use the strictest of the 3 and file a
bug report for `pinc-eye`.

## Naming Conventions

The goal of naming is to provide understanding of what everything in
a statement is just from casing. For example, below are two blocks that achieve
the same functionality, while using different casing.

The different cases enables easy "textural" differentiation.


### Files

File systems have different case sensitivity i.e. mac/windows are insensitive while linux is sensitive. To avoid
compilation bugs between platforms, we use ``snake_case``. File names should also be as concise and precise as possible.

> [!TIP] If a file name is too long, it could possibly be nested deeper as it's likely part of a broader niche within the system.

#### Example:

```
src/MathMatrixOperations.cpp                    # BAD: this file is not in snake_case
src/math_la_matrix_operations.cpp               # BAD: this file is too long
src/math/linear_algebra/matrix_operations.cpp   # GOOD: this file is descriptively named and nested
```

### Types (Classes, Structs, Enums)

We use ``PascalCase`` for naming of types. This distinguishes "User Types" from
"Standard Library Types" (which are snake_case) and variables. It signals that
this identifier creates a new object layout.

PascalCase vs snake_case should immediately signal high scrutiny towards user
defined types.

```cpp
// GOOD
class PulseSchedule, struct QubitMap, using ImageBuffer = std::vector<byte>;
// BAD
class pulse_schedule, struct QUBIT_MAP
```

Suffix `_t` is disallowed.

#### Exceptions

There are a few exceptions to this rule. Often times, we will roll our own types that are meant to be used
interchangeably with standard library types, e.g. ``std::priority_queue`` vs ``pq::priority_queue``. Here it makes sense
to name them interchangeably too.

### Functions & Methods

Functions and methods follow ``camelCase``.

Named lambdas in global scope should follow the function naming convention, while named lambdas in inner scopes
follow variable naming convention.

### Variables

Variables follow ``snake_case`` to distinguish from classes, and functions.

### Constants & constexpr

Constants should follow ``SCREAMING_CASE`` for constexpr defined, const defined, and macro defined constants.
This makes it immediately obvious that something cannot be changed and that possibly, it doesn't have a strong type to
refer to. For variables that need to be tuned as a build parameter, namespace with the ``TUNABLE_`` prefix. Catalyst
will automatically pull these out into the config file.

### Template Parameters

Template parameters follow ``PascalCase_T`` to denote that something is a template parameter.

> [!TIP] Most of the time, you should provide a using declaration that binds to the template parameter and use that. This makes code introspection for stuff like template meta programming easier.

### Namespaces

Namespace should follow ``lower`` case, i.e., no delimiters. If you find the need for one, you should consider nesting
namespaces.

> [!NOTE] This should fairly closely resemble the directory naming convention

## Namespaces & Scoping

### Namespace Usage Rules

- All code must exist within the project's top-level namespace (e.g., catalyst:: or pq::).
- The global namespace is strictly reserved for main() and system calls that require it (e.g., extern "C").

#### Directory Correspondence
- Namespaces should roughly correspond to the directory structure, but do not be slavish about it.

```
Good: src/compiler/ast -> catalyst::compiler::ast
Bad: src/compiler/backend/llvm/utils/strings -> catalyst::compiler::backend::llvm::utils::strings (Too deep; flatter is better).
```

#### using namespace

- Never use ``using namespace`` a header file.
    - This forces your namespace choices onto every file that includes that header, creating invisible conflicts.
- Exception: Inside a .cpp file, after all includes, you may use using namespace but explicit qualification is still preferred.

### Anonymous Namespaces

- Use anonymous namespaces (``namespace { ... }``) to define file-local functions, variables, and types in .cpp files.
- Prefer anonymous namespaces to static since it enables better LTO.
- Never put an anonymous namespace inside a header.
    - This causes every translation unit that includes the header to define it's own copy of the symbols.


###  Inline Namespaces

- Inline namespaces (``inline namespace v2 { ... }``) are reserved strictly for ABI Versioning.
- Context: They allow the library to present a default interface while keeping older binary symbols available.
- Rule: Do not use them for organizational structure.

###  Namespace Aliases

We maintain a strictly approved list of namespace aliases (See Section 21) that are safe to use project-wide.

Local Aliases: You may define local aliases inside a .cpp file or inline header function/class definition. Even
in these contexts, you should use the common names defined in the appendix.

```cpp
// Good (inside function)
void process() {
    namespace sv = std::views;
    auto view = sv::iota(0, 10);
}

// BAD
namespace sv = std::views; // Pollutes everyone's build and breaks interpretability
```

### ADL

- ADL allows the compiler to find functions in namespaces based on the arguments passed to them. This breaks determinism.
- Explicitly qualify function calls unless ADL is strictly required (e.g., for swap or operator overloads).
    - Good: ``std::sort(...)``
    - Bad: ``sort(...)`` (Might pick ``std::sort``, might pick ``catalyst::sort``, might fail).

#### Exceptions
- Operators (operator<<, operator+) rely on ADL to function. This is acceptable.

### Symbol Visibility
Default: We build with "hidden" visibility by default (-fvisibility=hidden).
Public API: Explicitly mark classes and functions intended for external consumption (outside the shared library/DLL) with the project's export macro (e.g., CATALYST_API).

Reasoning: This creates a smaller binary size, faster load times, and enforces a strict boundary between "Public API" and "Internal Implementation."

## Classes & Structs

### Class Layout Order

Class layout should have the goal of optimizing performance. The primary layout related causes of bad performance are:

- False Sharing
- Poor Cache Locality from layout
- Poor Cache Locality from padding

Since different structs have different applications, and the goals above conflict, the only possible remedy is
microbenchmarks. To make this type of benchmark trivial, you can do the following to allow for easier benchmarking:

```cpp
template <int k>
struct S {
#ifdef DEBUG
    static_assert(false, "you should use specialized member order")
#else
    // final chosen layout
#endif
}

#ifdef DEBUG
template<> struct S<0> {
    Type1 a;
    Type2 b;
    Type3 c;
};

template<> struct S<1> {
    Type1 a;
    Type3 c;
    Type2 b;
};

// ...
#endif
```

### Rule of Zero/Five

Object semantics should be strict until otherwise needed. Therefore, the order is as such:

1. Delete everything first.
2. Re-enable the __default__ when semantically valid.
3. Specialize when needed for extra behavior.

### Constructors & Explicitness

Constructors are allowed to be implicit when all of the following are true:
- The incoming type is semantically equivalent to the constructed type
- The conversion is obvious at the call site
- No ownership, allocation, lifetime, or narrowing ambiguity is introduced

Examples where implicit is acceptable:
- view/wrapper types over the same underlying representation
- strong semantic aliases of existing types
- cheap value-preserving transformations

Examples where implicit is forbidden:
- ownership transfer
- allocation
- lossy conversion
- policy-changing wrappers
- anything that alters threading or synchronization guarantees

> [!TIP] If a reader cannot immediately infer that a constructor is being invoked, it must be explicit.

### Inheritance Policy

Prefer compile-time polymorphism via enum-dispatch templates over runtime polymorphism.

```cpp
enum class Backend { CPU, CUDA, Metal };

template <Backend B>
struct Engine;
```


This yields:
- static specialization
- branch elimination
- layout visibility
- optimizer-friendly code paths

#### Virtual Functions
- runtime polymorphism is required
- specialization explosion is worse than dispatch cost
- call frequency is low or amortized

> VTable overhead is widely overstated in modern CPUs.
> indirect calls are typically cached and predictable.
> However, inheritance hierarchies must remain shallow and semantically clean. Since "abstraction hell" is harder to
> reason about than "specialization hell"

#### Multiple Inheritance
Multiple inheritance is strongly discouraged outside interface-only layering.

#### PIMPL Usage

PIMPL (pointer to implementation) is allowed for ABI stability across releases, and isolation of heavy dependencies.
However, it should not lead to performance regression. When PIMPL is used

- The owning object must aggressively inline hot-paths
- Construction must pre-touch or warm referenced memory when latency-sensitive
- Dereference chains must be minimized inside tight loops
- Heap allocation must be justified by benchmark

## Functions

- We model functions as a premise, things that should be true at the call site, and a promise, things that will be true
of "side-effects", if premise is met.
    - Side Effects constitute, io, mutating global state, and returning values. The first 2 are discussed in more detail later.

### Function Size & Responsibility

- We define responsibility as how many promises a function makes, and how many side effects it produces.
- We try to restrict a function to 1 direct promise and 1 direct side-effect, with infinitely many indirect promises/side-effects from function calls within the body.

### Return Types

- For functions that return a value, it's useful to wrap in a ``pq::expected``
    - This is basically ``std::expected`` standardizes the error type to string and implements SOO.

#### Exceptions

- For performance critical code, even with SSO, the indirection overhead is unacceptable. Mark the function
- ``noexcept`` and throw (triggering ``std::terminate``).

### Parameter Correctness

This is the order of preference for parameter types
- Const Reference
    - Exception: when the size of the parameter is less than 8 bytes or less than 16 bytes when optimization is enabled. In these cases, we just pass by value
        - NOTE: the 8 byte rule is typical on 64-bit architecture, but the 16 byte rule is specific to us since compilers will try and use the SIMD registers to "smuggle" in parameters instead of normal register.
- Reference
    - This is for when the side effect of the function is mutating the "out parameter".
    - Your function should typically chose between out paramaters and returns, not both.
- RValue
    - This for when the parameter belongs to a move only type and the function assumes ownership of the object.
- Value
    - This is typically never useful, except for the exception to const references mentioned above.
- Pointers
    - This isn't recommended since it litters the code with ``&,*,->`` and doesn't provide good ownership semantics
    clarity, but we might still need it for C interop.

### Lambda Usage

- Lambdas are almost always preferable to functions since they explicitly mark any global capture, but not an explicit requirement.
- When using lambas as functions,
    - adhere to function naming conventions,
    - mark the lambda constexpr,
    - and explicitly define the return type

#### Examples

```cpp
// BAD: no constexpr declaration
auto lambda = [] () {
};

// BAD: constexpr declaration applies to the call operator, not the return value
auto lambda = [] () constexpr {
};
// BAD: no return value
constexpr auto lambda = [] () {
};
// BAD: implicit global capture
constexpr auto lambda = [&] () {
};
// GOOD
constexpr auto lambda = [&x, &y, z] () -> void {
};
```

## Memory Management

### Ownership Rules

We use RAII for cleanup of objects. As such, we rely on wrapper types to both clarify ownership semantics and handle
RAII properly for those ownership semantics. Mainly we rely on smart pointers, ``std::unique_ptr``, ``pq::nonatomic_ptr``, and
``std::shared_ptr``.

### Pointer Policy

- Always use smart pointers, when an object or scope retains ownership of the pointed to object.
    - Use ``std::unique_ptr`` in unique ownership cases
    - Use ``std::shared_ptr`` in shared ownership in multi threaded code
    - Use ``pq::nonatomic_ptr`` in shared ownership in single threaded code, e.g. graph-like data structures.
- Use ``std::weak_ptr`` when it doesn't signify ownership and when in cyclic data structures.
- Use ``pq::deferred_allocator`` for cleanup in hot paths.
- Never use or accept raw pointers, except for C interop.

### Stack vs Heap
- Always prefer the stack to the heap as it better optimizes cache locality and cleanup.

## Concurrency

We've broken this section out into a [broader concurrency guide](@DIRECTIVE:copy:$(self.hostname.root)/guides/concurrent-code-practice), and the specific [C++ section of that guide](@DIRECTIVE:copy:$(self.hostname.root)/guides/concurrent-code#cpp).


## Formatting & Layout

Use the following ``.clang-format``

```
BasedOnStyle: LLVM
IndentWidth: 4
ColumnLimit: 100
AccessModifierOffset: -4
AllowShortFunctionsOnASingleLine: None
AlignAfterOpenBracket: Align
AlignConsecutiveAssignments: false
BinPackArguments: false
BinPackParameters: false
FixNamespaceComments: true
IncludeBlocks: Regroup
IndentCaseLabels: true
SortIncludes: true
```

## Documentation

Source code documentation is generated by Jocasta, our attribute driven
documentation generation.

We use Jocasta primarily because Doxygen is hard to parse and painfully
slow to deploy. By making documentation an emitted artifact of compilation, we
significantly speed up documentation generation. In order to achieve
documentation as an artifact of compilation, we need some way of hooking the
docs framework to compiler-native data structures, i.e. the AST. The most
extensible method at our disposal is attributes and as such, that's what
Jocasta mandates.

Going beyond compiler artifacts, attributes enable defining "scope" in that
it's obvious exactly what is being documented since docs are attributable to
the documented structure.
### Jocasta Example

```cpp
[[doc::brief("Allocates memory on the heap")]]
[[doc::param(bytes, "The number of bytes to allocate")]]
[[doc::return("A pointer to the heap or nullptr in case of an exception")]]
void *malloc(size_t bytes);
```

This will generate a markdown file in a docs directory, to be served by ``mkdocs``.

## Appendix

### Namespace Aliases

| Alias | Actual Namespace | Reason |
|-------|------------------|--------|
| ``clk`` | ``std::chrono`` | "clock" |
| ``rv`` | std::views | originally an alias for ``std::ranges::views`` |
| ``fs`` | std::filesystem | standard abbreviation |

