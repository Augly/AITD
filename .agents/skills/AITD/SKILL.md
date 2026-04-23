```markdown
# AITD Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill guides you through the core development patterns in the AITD Python codebase. You'll learn the project's coding conventions, commit practices, and how to structure code for consistency and maintainability. While no framework is enforced, the repository follows clear standards in file naming, imports, and exports. Testing patterns are identified, and suggested commands are provided for common workflows.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `data_processor.py`, `user_utils.py`

### Import Style
- Use **relative imports** within modules.
  - Example:
    ```python
    from .helpers import compute_score
    from ..models import User
    ```

### Export Style
- Use **named exports** by explicitly listing public objects in `__all__`.
  - Example:
    ```python
    __all__ = ['MyClass', 'my_function']
    ```

### Commit Patterns
- Commit types are **mixed**, but commonly use the `feat` prefix.
- Commit messages are concise (average ~35 characters).
  - Example:
    ```
    feat: add user authentication logic
    ```

## Workflows

### Adding a New Feature
**Trigger:** When implementing a new functionality.
**Command:** `/add-feature`

1. Create a new Python file using snake_case.
2. Implement your feature using relative imports as needed.
3. Add named exports to `__all__` if applicable.
4. Commit your changes with a message starting with `feat:`.
5. (Optional) Add or update test files.

### Refactoring Existing Code
**Trigger:** When improving or restructuring code without changing external behavior.
**Command:** `/refactor`

1. Identify code to refactor.
2. Apply changes, maintaining snake_case file naming and relative imports.
3. Update `__all__` if public API changes.
4. Commit with a clear message (e.g., `refactor: improve data parsing logic`).

### Writing Tests
**Trigger:** When adding or updating tests.
**Command:** `/write-test`

1. Create a test file following the `*.test.ts` pattern (if applicable).
2. Write test cases for your Python code.
3. Ensure tests cover edge cases and expected behavior.
4. Commit with a message like `test: add tests for data_processor`.

## Testing Patterns

- The testing framework is **unknown**, but test files follow the `*.test.ts` pattern.
- Place test files alongside or within a dedicated `tests/` directory.
- Ensure each test file corresponds to a module or feature.

  Example test file name:
  ```
  data_processor.test.ts
  ```

## Commands
| Command        | Purpose                                   |
|----------------|-------------------------------------------|
| /add-feature   | Start the workflow for adding a new feature|
| /refactor      | Begin a code refactoring workflow         |
| /write-test    | Initiate writing or updating tests         |
```
