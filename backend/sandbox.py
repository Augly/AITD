from __future__ import annotations

import ast
import builtins
import contextlib
import io
import json
import math
import os
import subprocess
import sys
import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import CodeType
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


class SecurityError(RuntimeError):
    """Raised when sandboxed code attempts an unsafe operation."""


_BANNED_BUILTINS: frozenset[str] = frozenset({
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "raw_input",
    "reload",
})

_DANGEROUS_NAMES: frozenset[str] = frozenset({
    "__builtins__",
    "getattr",
    "setattr",
    "delattr",
    "vars",
    "dir",
    "type",
    "object",
})

_DANGEROUS_ATTRIBUTES: frozenset[str] = frozenset({
    "f_back",
    "f_builtins",
    "f_code",
    "f_globals",
    "f_locals",
    "func_globals",
    "gi_code",
    "gi_frame",
    "tb_frame",
})

_DEFAULT_ALLOWED_MODULES: frozenset[str] = frozenset({
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "hashlib",
    "itertools",
    "json",
    "math",
    "random",
    "re",
    "statistics",
    "string",
    "time",
    "typing",
})


SAFE_BUILTINS: dict[str, Any] = {
    "__build_class__": builtins.__build_class__,
    "abs": abs,
    "all": all,
    "any": any,
    "BaseException": BaseException,
    "bin": bin,
    "bool": bool,
    "bytearray": bytearray,
    "bytes": bytes,
    "callable": callable,
    "chr": chr,
    "classmethod": classmethod,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "Exception": Exception,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "ord": ord,
    "pow": pow,
    "print": print,
    "property": property,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "staticmethod": staticmethod,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "ArithmeticError": ArithmeticError,
    "AssertionError": AssertionError,
    "AttributeError": AttributeError,
    "ImportError": ImportError,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "NameError": NameError,
    "OSError": OSError,
    "RuntimeError": RuntimeError,
    "SecurityError": SecurityError,
    "StopIteration": StopIteration,
    "SyntaxError": SyntaxError,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "ZeroDivisionError": ZeroDivisionError,
}

_ACTIVE_WORKERS: set[int] = set()
_ACTIVE_WORKERS_LOCK = threading.Lock()
_WORKER_MODE = "--sandbox-worker"
_MAX_OUTPUT_BYTES = 1_000_000


class _SandboxValidator(ast.NodeVisitor):
    """Reject obviously unsafe syntax before execution."""

    def __init__(self, allowed_modules: set[str]) -> None:
        self.allowed_modules = allowed_modules

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_level = alias.name.split(".")[0]
            if top_level not in self.allowed_modules:
                raise SecurityError(f"Import of module {alias.name!r} is not allowed.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            raise SecurityError("Relative imports are not allowed.")
        if not node.module:
            raise SecurityError("Import target is required.")
        top_level = node.module.split(".")[0]
        if top_level not in self.allowed_modules:
            raise SecurityError(f"Import of module {node.module!r} is not allowed.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _BANNED_BUILTINS or node.id in _DANGEROUS_NAMES:
            raise SecurityError(f"Use of name {node.id!r} is not allowed in the sandbox.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        attr = node.attr
        if attr.startswith("_") or attr in _DANGEROUS_ATTRIBUTES:
            raise SecurityError(f"Access to attribute {attr!r} is not allowed in the sandbox.")
        if any(token in attr for token in ("globals", "builtins", "subclasses", "mro", "frame", "code")):
            raise SecurityError(f"Access to attribute {attr!r} is not allowed in the sandbox.")
        self.generic_visit(node)


def _validate_source(source_code: str, allowed_modules: set[str]) -> CodeType:
    tree = ast.parse(source_code, filename="<sandbox>", mode="exec")
    _SandboxValidator(allowed_modules).visit(tree)
    return compile(tree, "<sandbox>", "exec")


def _make_restricted_import(allowed_modules: set[str]) -> Any:
    def restricted_import(
        name: str,
        globals: dict[str, Any] | None = None,  # noqa: A002
        locals: dict[str, Any] | None = None,  # noqa: A002
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if level:
            raise SecurityError("Relative imports are not allowed.")
        top_level = name.split(".")[0]
        if top_level not in allowed_modules:
            raise SecurityError(f"Import of module {name!r} is not allowed.")
        return __import__(name, globals, locals, fromlist, level)

    return restricted_import


def _build_exec_scope(
    scope: dict[str, Any],
    allowed_modules: set[str],
) -> dict[str, Any]:
    safe_scope = dict(scope)
    safe_scope.setdefault("__name__", "__sandbox__")
    safe_scope.setdefault("__package__", None)
    safe_builtins = dict(SAFE_BUILTINS)
    safe_builtins["__import__"] = _make_restricted_import(allowed_modules)
    safe_scope["__builtins__"] = safe_builtins
    return safe_scope


def _to_wire(value: Any) -> dict[str, Any]:
    if value is None or isinstance(value, (bool, int, float, str)):
        return {"type": "primitive", "value": value}
    if isinstance(value, list):
        return {"type": "list", "items": [_to_wire(item) for item in value]}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [_to_wire(item) for item in value]}
    if isinstance(value, set):
        return {"type": "set", "items": [_to_wire(item) for item in sorted(value, key=repr)]}
    if isinstance(value, dict):
        return {
            "type": "dict",
            "items": [
                {"key": str(key), "value": _to_wire(item)}
                for key, item in value.items()
            ],
        }
    if isinstance(value, date) and not isinstance(value, datetime):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, time):
        return {"type": "time", "value": value.isoformat()}
    if isinstance(value, timedelta):
        return {"type": "timedelta", "value": value.total_seconds()}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, Fraction):
        return {
            "type": "fraction",
            "numerator": value.numerator,
            "denominator": value.denominator,
        }
    raise TypeError(f"Value of type {type(value).__name__} is not serializable for sandbox transport.")


def _from_wire(payload: dict[str, Any]) -> Any:
    payload_type = payload["type"]
    if payload_type == "primitive":
        return payload["value"]
    if payload_type == "list":
        return [_from_wire(item) for item in payload["items"]]
    if payload_type == "tuple":
        return tuple(_from_wire(item) for item in payload["items"])
    if payload_type == "set":
        return {_from_wire(item) for item in payload["items"]}
    if payload_type == "dict":
        return {
            item["key"]: _from_wire(item["value"])
            for item in payload["items"]
        }
    if payload_type == "date":
        return date.fromisoformat(payload["value"])
    if payload_type == "datetime":
        return datetime.fromisoformat(payload["value"])
    if payload_type == "time":
        return time.fromisoformat(payload["value"])
    if payload_type == "timedelta":
        return timedelta(seconds=float(payload["value"]))
    if payload_type == "decimal":
        return Decimal(payload["value"])
    if payload_type == "fraction":
        return Fraction(payload["numerator"], payload["denominator"])
    raise TypeError(f"Unsupported sandbox payload type: {payload_type}")


def _serialize_scope(scope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    serialized: dict[str, dict[str, Any]] = {}
    for key, value in scope.items():
        if key == "__builtins__":
            continue
        try:
            serialized[str(key)] = _to_wire(value)
        except TypeError:
            continue
    return serialized


def _deserialize_scope(scope: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        str(key): _from_wire(value)
        for key, value in scope.items()
    }


def _encode_payload(
    *,
    mode: str,
    source_code: str,
    scope: dict[str, Any],
    allowed_modules: set[str],
    function_name: str | None = None,
    function_args: list[Any] | None = None,
    function_kwargs: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    payload = {
        "mode": mode,
        "source_code": source_code,
        "scope": _serialize_scope(scope),
        "allowed_modules": sorted(allowed_modules),
        "timeout_seconds": timeout_seconds,
        "function_name": function_name,
        "function_args": [_to_wire(item) for item in (function_args or [])],
        "function_kwargs": {
            str(key): _to_wire(value)
            for key, value in (function_kwargs or {}).items()
        },
    }
    return json.dumps(payload)


def _decode_response(raw_response: str) -> dict[str, Any]:
    response = json.loads(raw_response)
    if response.get("ok"):
        return {
            "scope": _deserialize_scope(response.get("scope", {})),
            "result": _from_wire(response["result"]) if response.get("has_result") else None,
            "stdout": str(response.get("stdout") or ""),
        }

    error = response.get("error", {})
    name = str(error.get("name") or "RuntimeError")
    message = str(error.get("message") or "Sandbox execution failed.")
    if name == "SecurityError":
        raise SecurityError(message)
    if name == "TimeoutError":
        raise TimeoutError(message)
    if name == "SyntaxError":
        details = error.get("details", {})
        raise SyntaxError(
            message,
            (
                "<sandbox>",
                int(details.get("lineno") or 0),
                int(details.get("offset") or 0),
                details.get("text"),
            ),
        )
    exception_type = getattr(builtins, name, RuntimeError)
    if isinstance(exception_type, type) and issubclass(exception_type, BaseException):
        raise exception_type(message)
    raise RuntimeError(message)


def _register_worker(pid: int) -> None:
    with _ACTIVE_WORKERS_LOCK:
        _ACTIVE_WORKERS.add(pid)


def _unregister_worker(pid: int) -> None:
    with _ACTIVE_WORKERS_LOCK:
        _ACTIVE_WORKERS.discard(pid)


def _active_worker_count() -> int:
    with _ACTIVE_WORKERS_LOCK:
        return len(_ACTIVE_WORKERS)


def _invoke_worker(payload: str, timeout_seconds: float) -> dict[str, Any]:
    worker_cmd = [sys.executable, "-I", __file__, _WORKER_MODE]
    process = subprocess.Popen(
        worker_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
        env={"PYTHONIOENCODING": "utf-8"},
    )
    _register_worker(process.pid)
    try:
        try:
            stdout, stderr = process.communicate(payload, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise TimeoutError(f"Sandboxed code exceeded {timeout_seconds}s timeout.") from exc
        if process.returncode != 0 and not stdout.strip():
            detail = stderr.strip() or f"sandbox worker exited with {process.returncode}"
            raise RuntimeError(f"Sandbox worker failed: {detail}")
        if len(stdout.encode("utf-8")) > _MAX_OUTPUT_BYTES:
            raise SecurityError("Sandbox output exceeded the allowed size.")
        return _decode_response(stdout)
    finally:
        _unregister_worker(process.pid)


def run_restricted_python(
    source_code: str,
    scope: dict[str, Any] | None = None,
    allowed_modules: set[str] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Execute Python source code in an isolated restricted subprocess."""
    safe_scope = dict(scope or {})
    allowed = set(allowed_modules) if allowed_modules is not None else set(_DEFAULT_ALLOWED_MODULES)
    payload = _encode_payload(
        mode="exec",
        source_code=source_code,
        scope=safe_scope,
        allowed_modules=allowed,
        timeout_seconds=timeout_seconds,
    )
    return _invoke_worker(payload, timeout_seconds)["scope"]


def call_restricted_function(
    source_code: str,
    function_name: str,
    *,
    scope: dict[str, Any] | None = None,
    function_args: list[Any] | None = None,
    function_kwargs: dict[str, Any] | None = None,
    allowed_modules: set[str] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Execute code in the sandbox, call one function, and return its result."""
    safe_scope = dict(scope or {})
    allowed = set(allowed_modules) if allowed_modules is not None else set(_DEFAULT_ALLOWED_MODULES)
    payload = _encode_payload(
        mode="call",
        source_code=source_code,
        scope=safe_scope,
        allowed_modules=allowed,
        function_name=function_name,
        function_args=function_args,
        function_kwargs=function_kwargs,
        timeout_seconds=timeout_seconds,
    )
    return _invoke_worker(payload, timeout_seconds)


def _apply_resource_limits(timeout_seconds: float) -> None:
    if resource is None:
        return
    try:
        cpu_limit = max(1, math.ceil(timeout_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX_OUTPUT_BYTES, _MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        memory_limit = 256 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    except (ValueError, OSError):
        return


def _worker_error_payload(exc: BaseException) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "name": type(exc).__name__,
            "message": str(exc),
        },
    }
    if isinstance(exc, SyntaxError):
        payload["error"]["details"] = {
            "lineno": exc.lineno,
            "offset": exc.offset,
            "text": exc.text,
        }
    return payload


def _execute_in_worker(raw_payload: str) -> dict[str, Any]:
    payload = json.loads(raw_payload)
    source_code = str(payload["source_code"])
    allowed_modules = {str(item) for item in payload.get("allowed_modules", [])}
    timeout_seconds = float(payload.get("timeout_seconds") or 30.0)
    scope = _deserialize_scope(payload.get("scope", {}))

    _apply_resource_limits(timeout_seconds)
    compiled = _validate_source(source_code, allowed_modules)
    exec_scope = _build_exec_scope(scope, allowed_modules)

    stdout_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer):
        exec(compiled, exec_scope, exec_scope)  # noqa: S102
        result: Any = None
        has_result = False
        if payload.get("mode") == "call":
            function_name = str(payload.get("function_name") or "").strip()
            func = exec_scope.get(function_name)
            if not callable(func):
                raise ValueError(f"Dynamic candidate source must define `{function_name}`.")
            args = [_from_wire(item) for item in payload.get("function_args", [])]
            kwargs = {
                str(key): _from_wire(value)
                for key, value in payload.get("function_kwargs", {}).items()
            }
            result = func(*args, **kwargs)
            has_result = True

    response: dict[str, Any] = {
        "ok": True,
        "scope": _serialize_scope(exec_scope),
        "stdout": stdout_buffer.getvalue(),
        "has_result": has_result,
    }
    if has_result:
        response["result"] = _to_wire(result)
    return response


def _worker_main() -> int:
    raw_payload = sys.stdin.read()
    try:
        response = _execute_in_worker(raw_payload)
    except BaseException as exc:  # pragma: no cover - exercised via parent process
        response = _worker_error_payload(exc)
    sys.stdout.write(json.dumps(response))
    return 0


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == _WORKER_MODE:
    raise SystemExit(_worker_main())
