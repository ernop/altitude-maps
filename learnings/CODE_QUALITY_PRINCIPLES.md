# Code Quality Principles - Agent Guidance

## Core Principles

### 1. Question Defensive Patterns
**Pattern:** Defensive checks for things that are guaranteed to exist
- `if (typeof X === 'function')` when script is always loaded
- `if (element)` checks for elements we control
- Manual cache busting when browser handles HTTP cache

**Rule:** Trust the architecture. If dependencies are guaranteed, call them directly. Let the platform (browser, HTTP) handle what it's designed to handle.

### 2. Consolidate Before Optimizing
**Pattern:** Duplicate logic in multiple places
- Same grouping logic in two functions
- Hardcoded patterns repeated 3+ times

**Rule:** Duplication is worse than performance. Extract shared functions first, then optimize if needed.

### 3. Genericize Closed Sets
**Pattern:** Hardcoded cases for a fixed set of values
- Three separate arrays/blocks for three region types
- Switch statements with identical structure

**Rule:** Use data-driven patterns (config objects + loops) instead of hardcoding each case. Makes extension easier.

### 4. Remove Unnecessary Complexity
**Pattern:** Complex solutions for simple problems
- 15+ string checks for console.log filtering → just log everything
- Chunked JSON loading with progress → direct decompression works fine
- Manual cache detection → browser handles it

**Rule:** Complexity must solve a real problem. If it doesn't, remove it.

### 5. Organize by Purpose, Not Type
**Pattern:** Variables scattered by declaration type (`let`, `const`)
- All `let` declarations together, regardless of purpose

**Rule:** Group by logical purpose (CORE THREE.JS STATE, DATA STATE, REGION STATE). Reflects mental models, easier to navigate.

### 6. Cache Expensive Computations, Not Simple Lookups
**Pattern:** Caching everything vs caching selectively
- Good: Bucketing cache (expensive computation, reused frequently)
- Bad: Manual HTTP cache busting (simple fetch, browser handles it)

**Rule:** Cache what's expensive to compute, not what's expensive to fetch.

### 7. Comments Explain Why, Not What
**Pattern:** Comments that restate code
- `// Color scheme` above `colorScheme` parameter
- `// Resolution (bucket size)` above `bucketSize` parameter

**Rule:** Comments should explain non-obvious behavior or intent. If the code is self-explanatory, skip the comment.

### 8. Constants for Magic Values
**Pattern:** Magic strings/numbers repeated multiple times
- `'california'` appears 3 times → `DEFAULT_REGION` constant
- Even if only used 2-3 times, constants provide single source of truth

**Rule:** Magic values should be constants. Makes changes easier and intent clearer.

### 9. Module Boundaries Matter
**Pattern:** Functions placed "wherever they're used"
- `debounce()` in main file → belongs in `format-utils.js` (utility)
- `logResourceTiming()` in main file → belongs in `activity-log.js` (logging)

**Rule:** Functions belong with related functionality, not just where they're first used. Better cohesion, clearer dependencies.

### 10. Question the Architecture
**Pattern:** Adding layers to work around existing complexity
- `trueScaleValue` conversion layer is necessary for current design
- Could be simplified, but requires refactoring rendering pipeline

**Rule:** Some complexity is architectural debt. Document it clearly, but don't add more layers on top. Consider refactoring if it becomes a maintenance burden.

## Red Flags to Watch For

- **Defensive checks** for guaranteed dependencies
- **Duplicate logic** in 2+ places
- **Hardcoded cases** for closed sets (use data-driven approach)
- **Complex solutions** for simple problems
- **Comments** that just restate parameter names
- **Magic values** repeated 2+ times
- **Functions** in wrong modules (check cohesion)
- **Manual workarounds** for platform features (cache, HTTP, etc.)

## Questions to Ask

1. Is this defensive check actually needed, or is the dependency guaranteed?
2. Is this logic duplicated elsewhere? Can we extract it?
3. Is this a closed set that could be data-driven instead of hardcoded?
4. Does this complexity solve a real problem, or can we simplify?
5. Would organizing this differently make it easier to understand?
6. Should this be cached, or is the platform handling it?
7. Does this comment add value, or just restate the code?
8. Is this magic value used multiple times? Should it be a constant?
9. Is this function in the right module based on its purpose?
10. Is this architectural debt that needs refactoring, or necessary complexity?

## Overall Theme

**Simplicity beats cleverness.** Remove code that doesn't solve a real problem. Consolidate duplication. Trust the platform. Organize by purpose. Question assumptions.

