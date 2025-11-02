# Linter Type Stubs Setup

## The Problem

When using libraries without type annotations (like `rasterio`), Pylance/Pyright will report "Stub file not found" and "partially unknown" type errors. These are noisy and unhelpful when the code works fine at runtime.

## Current Approach: Diagnostic Suppression

We suppress these specific noisy warnings in `.vscode/settings.json`:

```json
"python.analysis.diagnosticSeverityOverrides": {
    "reportUnusedImport": "none",
    "reportMissingTypeStubs": "none",
    "reportUnknownMemberType": "none",
    "reportUnknownArgumentType": "none",
    "reportUnknownVariableType": "none",
    "reportUnknownParameterType": "none",
    "reportUnknownLambdaType": "none",
    "reportUnknownReturnType": "none"
}
```

This keeps the development environment clean without losing legitimate type checking.

## Alternative: Custom Type Stubs

We attempted to create custom type stubs for `rasterio` and place them in the package directory (`venv/Lib/site-packages/rasterio/__init__.pyi`), but Pylance wasn't picking them up reliably. This approach has the following challenges:

1. **Installation location**: Stubs must be in the exact package directory where the library is installed
2. **Maintenance**: Manual stub creation requires keeping them in sync with library updates
3. **Cache issues**: Pylance caches aggressively; requires editor restart to pick up new stubs
4. **Effectiveness**: Many errors remain even with stubs because stubgen output is limited

## Recommendation

**Use diagnostic suppression** as configured. This is the pragmatic approach that works reliably across all machines without manual intervention.

If you want to be more thorough, you could:
- Install official type stub packages when available (e.g., `types-requests`)
- Contribute official stubs to the library maintainers
- Wait for libraries to adopt PEP 484 type annotations natively

## References

- PEP 484: Type Hints - https://peps.python.org/pep-0484/
- PEP 561: Distributing and Packaging Type Information - https://peps.python.org/pep-0561/




