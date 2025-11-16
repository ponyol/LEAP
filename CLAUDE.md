# Project Development Guidelines

These are my core principles for working with code. Please follow them when generating, refactoring, or analyzing code for my projects.

## 1. Functional Programming (FP) Approach

When writing code, please adhere to functional programming principles where it is practical and appropriate.

* **Pure Functions:** Strive to write functions whose results depend only on their input arguments, with no side effects.
* **Immutability:** Prefer creating new data structures instead of mutating (modifying in-place) existing ones.
* **Composition:** Build complex logic by composing smaller, simpler functions.
* **Declarative Style:** Favor a declarative style (what to do) over an imperative one (how to do it). For example, use `map`, `filter`, `reduce` instead of complex `for` loops.
* **State Management:** Avoid global state. If state is necessary, it should be explicitly managed and isolated.

## 2. Project Structure and Modularity

We adhere to a modular structure that combines logical grouping with a clean public API.

**The Core Rule:** We do *not* use a "one function per file" approach. Instead, we use **"one file per logical unit"** (e.g., all functions related to user management).

We then use a "facade" file (`__init__.py` or `index.ts`) to expose a clean, intentional API for that logical package.

### 2.1. Development Environment (Python)

**Primary Version:** `Python 3.14` (standard build).
**Reason:** This is the latest stable version with the best performance and `asyncio` support. We use it by default for production-ready code to ensure maximum ecosystem compatibility.

#### Preferred Architecture

**Approach:** Async-first.
**Description:** All new projects, especially web/API, must use an `asyncio`-first approach by default.
**Stack:**
* **Web/API:** FastAPI
* **HTTP Client:** httpx
* **Database:** asyncpg (for Postgres), SQLAlchemy 2.0+ (async engine)
**Reason:** This architecture is the most efficient on standard Python 3.14 and is the only viable path for future migration to Free-Threading (`3.14t`) once the ecosystem matures.

#### Core Libraries (Stable)

**Description:** These libraries are vetted and recommended for use in the `async-first` architecture.
* `fastapi` (≥ 4.0)
* `pydantic` (≥ 2.11.0)
* `uvicorn` (≥ 0.24)
* `httpx`
* `asyncpg` (≥ 0.29)
* `sqlalchemy` (≥ 2.0)
* `langchain` (as it is pure Python)

#### Experimental: Free-Threading (3.14t) Projects

**Status:** R&D only, not for production.
**Objective:** Testing CPU-bound workloads and preparing for the future.

##### 🔴 CRITICAL WARNING: GIL Re-enabling

**Problem:** Importing *any* C-extension not compiled with the `Py_MOD_GIL_NOT_USED` (or `Py_MOD_GIL_USED`) flag will **immediately and permanently re-enable the GIL** for the entire process, nullifying all benefits.
**Verification:** Always run tests with `python3.14t -X gil=0 -v` and monitor for `RuntimeWarning`.

##### High-Risk / In-Development Libraries

**Description:** Use with caution. Verify the availability of `cp314t` wheels and the absence of GIL warnings.

* **`numpy` (≥ 2.1.0):** Requires `cp314t` wheel.
* **`pytorch` (≥ 2.6.0 / 2.7.0):** Heavily dependent on C-extensions (Triton). High risk of bugs causing GIL re-enabling.
* **`transformers`:** **DO NOT USE** (as of Nov 2025). Installation is blocked by incompatible dependencies (e.g., `hf-xet`).
* **`llama-cpp-python`:** **NOT READY**. The library does not officially support Python 3.14.

### 2.2. Python (Packages)

* **Logic:** All related logic (e.g., `users`) is contained within its own module (`core/users.py`).
* **Facade (`__init__.py`):** This file imports *only* the functions and classes that should be accessible "from the outside" and provides them as the package's (`core`) API.

**Example Structure:**
```

my\_project/
└── core/
├── **init**.py  \# \<-- Our Facade (Public API)
├── users.py     \# \<-- Module with all User logic
└── auth.py      \# \<-- Module with all Auth logic

````

**File Content (`core/users.py`):**
```python
# Internal functions can exist but are not exported via __init__.py
def _get_db_connection():
    pass

# Public-facing functions for this module
def get_user_by_id(user_id: int) -> dict:
    """Gets a user from the database by their ID."""
    # ... logic
    return {"id": user_id, "name": "Oleh"}

def create_user(username: str) -> dict:
    """Creates a new user."""
    # ... logic
    return {"id": 123, "name": username}
````

**File Content (`core/__init__.py`):**

```python
# Import only what we want to expose
from .users import get_user_by_id, create_user
from .auth import login, logout

# (Best Practice) Explicitly define the public API
__all__ = [
    "get_user_by_id",
    "create_user",
    "login",
    "logout",
]
```

**Usage (e.g., in `main.py`):**

```python
# Correct: Import from the package facade
from core import get_user_by_id

# Discouraged: Bypassing the API
# from core.users import get_user_by_id
```

### 2.3. TypeScript (Barrel Files)

We use the same concept in TypeScript, but the facade file is conventionally named `index.ts` (the "barrel file").

**Example Structure:**

```
my_project/
└── core/
    ├── index.ts     # <-- Our Barrel File (Public API)
    ├── users.ts     # <-- Module with all User logic
    └── auth.ts      # <-- Module with all Auth logic
```

**File Content (`core/users.ts`):**

```typescript
/**
 * Gets a user by their ID.
 * @param userId - The ID of the user to retrieve.
 * @returns The user object.
 */
export function getUserById(userId: number): object {
  // ... logic
  return { id: userId, name: "Oleh" };
}

export function createUser(username: string): object {
  // ... logic
  return { id: 123, name: username };
}
```

**File Content (`core/index.ts`):**

```typescript
// Re-export the public API from our internal modules
export * from './users';
export * from './auth';
```

**Usage (e.g., in `main.ts`):**

```typescript
// Correct: TS automatically picks up index.ts
import { getUserById, login } from './core';

// Discouraged: Bypassing the barrel file
// import { getUserById } from './core/users';
```

-----

## 3\. Documentation and Commenting

Code should be clear, but documentation is essential for *why* things are done.

  * **Structure:** Information must be structured logically and sequentially.
  * **Comments:** Write detailed comments inside the code for complex logic, business rules, or "magic" values. Explain the "why," not just the "what."
  * **Docstrings/JSDoc:** All public functions (especially those exposed in `__init__.py` or `index.ts`) *must* have clear docstrings (Python) or JSDoc (TS), explaining:
      * A brief summary of what the function does.
      * Its parameters (`@param`).
      * What it returns (`@return`).
      * Any errors it might explicitly throw (`@throws`).
  * **Examples:** Add usage examples in the documentation where it adds value.
  * **Key Points:** Use `NOTE:`, `TODO:`, or `WARNING:` prefixes to highlight important points or potential issues.

-----

## 4\. Error Handling

Errors should be treated as part of the program flow, not just as exceptions.

  * **No `null`/`None`:** Avoid returning `null` or `None` to indicate failure. This is ambiguous.
  * **Python:**
      * Raise specific, custom exceptions (e.g., `UserNotFoundError`) rather than generic `Exception`.
      * The caller is responsible for catching exceptions it expects.
  * **TypeScript:**
      * Do not `throw` errors for predictable failures (e.g., "not found").
      * Prefer returning a **discriminated union (a "Result" type)** to force the caller to handle both success and failure cases at compile time.
      * **Example (TS Result Type):**
        ```typescript
        type Success<T> = { success: true; value: T };
        type Failure<E> = { success: false; error: E };
        type Result<T, E> = Success<T> | Failure<E>;

        function findUser(id: number): Result<User, string> {
          if (id === 1) {
            return { success: true, value: { id: 1, name: "Oleh" } };
          }
          return { success: false, error: "User not found" };
        }
        ```
  * **Handling:** Errors should be handled at the "edge" of the system (e.g., in the API route handler, the main script) rather than deep in the business logic.

-----

## 5\. Logging

Logging is crucial for observability and debugging.

  * **Structured Logging:** All log output must be in a structured format (preferably **JSON**). This is non-negotiable for parsing in production environments (ELK, Splunk, Datadog, etc.).
  * **Log Levels:** Use log levels appropriately:
      * `DEBUG`: Detailed info for development (e.g., variable values, function entry/exit).
      * `INFO`: High-level flow of the application (e.g., "Service started", "User logged in").
      * `WARN`: A potential issue that doesn't stop the application (e.g., "Deprecated API used", "Config file missing, using defaults").
      * `ERROR`: A failure that stopped the *current operation* but not the app (e.g., "Failed to process request X", "Database connection failed").
      * `FATAL` / `CRITICAL`: An error that will cause the application to terminate.
  * **What to Log:**
      * **Context is King:** Always include relevant context, such as `user_id`, `request_id`, or a `correlation_id`. This is essential for tracing a single request through multiple services.
      * **No Sensitive Data:** Never log passwords, API keys, full bank details, or other PII. Log user IDs, not emails or names, where possible.
      * **Log Outcome:** Log the intent and the outcome (e.g., "User login successful for user\_id: 123" or "User login failed for user\_id: 123, reason: invalid\_password").
      * **Log Errors Correctly:** When you *handle* an exception, log it as an `ERROR` and **include the stack trace**.
