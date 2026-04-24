from __future__ import annotations

from pathlib import Path

import pytest

from .sandbox import (
    SecurityError,
    call_restricted_function,
    run_restricted_python,
)


class TestRunRestrictedPython:
    def test_returns_scope_with_defined_variables(self) -> None:
        source = "result = 1 + 2\n"
        scope = run_restricted_python(source)
        assert scope["result"] == 3

    def test_preserves_injected_scope(self) -> None:
        source = "output = greeting + ' World'"
        scope = run_restricted_python(source, scope={"greeting": "Hello"})
        assert scope["output"] == "Hello World"

    def test_allows_json_module(self) -> None:
        source = (
            "import json\n"
            "result = json.dumps({'key': 'value'})\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == '{"key": "value"}'

    def test_allows_math_module(self) -> None:
        source = (
            "import math\n"
            "result = math.sqrt(16)\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == 4.0

    def test_allows_re_module(self) -> None:
        source = (
            "import re\n"
            "result = re.match(r'\\d+', '123abc').group()\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == "123"

    def test_allows_datetime_module(self) -> None:
        source = (
            "import datetime\n"
            "result = datetime.date(2024, 1, 1)\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == __import__("datetime").date(2024, 1, 1)

    def test_allows_itertools_module(self) -> None:
        source = (
            "import itertools\n"
            "result = list(itertools.islice(itertools.count(3), 4))\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == [3, 4, 5, 6]

    def test_blocks_bare___import__(self) -> None:
        source = "__import__('os').system('echo pwned')"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_eval(self) -> None:
        source = "eval('1 + 1')"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_exec(self) -> None:
        source = "exec('a = 1')"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_compile(self) -> None:
        source = "compile('a = 1', '<string>', 'exec')"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_open(self) -> None:
        source = "open('/etc/passwd')"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_disallowed_module_import(self) -> None:
        source = "import os"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_submodule_of_disallowed_module(self) -> None:
        source = "import os.path"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_blocks_relative_import(self) -> None:
        source = "from . import something"
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_allows_custom_allowed_modules(self) -> None:
        source = (
            "import os\n"
            "result = os.path.join('a', 'b')\n"
        )
        scope = run_restricted_python(source, allowed_modules={"os"})
        assert scope["result"] == "a/b"

    def test_blocks_non_whitelisted_module_when_custom_allowed(self) -> None:
        source = "import sys"
        with pytest.raises(SecurityError):
            run_restricted_python(source, allowed_modules={"os"})

    def test_timeout_raises_on_infinite_loop(self) -> None:
        source = "while True: pass"
        with pytest.raises(TimeoutError):
            run_restricted_python(source, timeout_seconds=0.5)

    def test_timeout_terminates_worker_for_exec_mode(self) -> None:
        source = "while True: pass"
        with pytest.raises(TimeoutError):
            run_restricted_python(source, timeout_seconds=0.2)
        assert not __import__("backend.sandbox", fromlist=["_active_worker_count"])._active_worker_count()

    def test_blocks_reflection_escape_via_builtin_importer(self, tmp_path: Path) -> None:
        marker_path = tmp_path / "escape.txt"
        source = (
            "result = [c for c in ().__class__.__base__.__subclasses__() "
            "if c.__name__ == 'BuiltinImporter'][0].load_module('os').system("
            f"{('echo sandbox_escape > ' + marker_path.as_posix())!r})\n"
        )
        with pytest.raises(SecurityError):
            run_restricted_python(source)
        assert not marker_path.exists()

    def test_blocks_function_globals_escape(self) -> None:
        source = (
            "def safe():\n"
            "    return 1\n"
            "result = safe.__globals__\n"
        )
        with pytest.raises(SecurityError):
            run_restricted_python(source)

    def test_function_definition_and_call(self) -> None:
        source = (
            "def add(a, b):\n"
            "    return a + b\n"
            "result = add(2, 3)\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == 5

    def test_class_definition_and_instantiation(self) -> None:
        source = (
            "class Point:\n"
            "    def __init__(self, x, y):\n"
            "        self.x = x\n"
            "        self.y = y\n"
            "p = Point(1, 2)\n"
            "result = (p.x, p.y)\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == (1, 2)

    def test_list_comprehension(self) -> None:
        source = "result = [x * 2 for x in range(5)]"
        scope = run_restricted_python(source)
        assert scope["result"] == [0, 2, 4, 6, 8]

    def test_dict_comprehension(self) -> None:
        source = "result = {str(x): x * x for x in range(3)}"
        scope = run_restricted_python(source)
        assert scope["result"] == {"0": 0, "1": 1, "2": 4}

    def test_lambda(self) -> None:
        source = (
            "f = lambda x: x + 1\n"
            "result = f(5)\n"
        )
        scope = run_restricted_python(source)
        assert scope["result"] == 6

    def test_exception_propagates(self) -> None:
        source = "raise ValueError('boom')"
        with pytest.raises(ValueError, match="boom"):
            run_restricted_python(source)

    def test_syntax_error_propagates(self) -> None:
        source = "if True"
        with pytest.raises(SyntaxError):
            run_restricted_python(source)

    def test_call_restricted_function_uses_scope_and_returns_stdout(self) -> None:
        source = (
            "def load_candidate_symbols(context):\n"
            "    print(context['scan_path'])\n"
            "    return context['manual_symbols']\n"
        )
        result = call_restricted_function(
            source,
            "load_candidate_symbols",
            function_args=[{"manual_symbols": ["BTCUSDT"], "scan_path": "/tmp/scan.json"}],
        )
        assert result["result"] == ["BTCUSDT"]
        assert result["stdout"] == "/tmp/scan.json\n"

    def test_call_restricted_function_timeout_terminates_worker(self) -> None:
        source = (
            "def loop_forever(context):\n"
            "    while True:\n"
            "        pass\n"
        )
        with pytest.raises(TimeoutError):
            call_restricted_function(
                source,
                "loop_forever",
                function_args=[{}],
                timeout_seconds=0.2,
            )
        assert not __import__("backend.sandbox", fromlist=["_active_worker_count"])._active_worker_count()


class TestSafeBuiltins:
    def test_safe_builtins_has_no_banned_functions(self) -> None:
        from .sandbox import SAFE_BUILTINS, _BANNED_BUILTINS

        for name in _BANNED_BUILTINS:
            assert name not in SAFE_BUILTINS, f"{name} should not be in SAFE_BUILTINS"

    def test_safe_builtins_has_common_functions(self) -> None:
        from .sandbox import SAFE_BUILTINS

        expected = {
            "len", "range", "print", "str", "int", "list", "dict", "set",
            "tuple", "map", "filter", "zip", "enumerate", "sum", "min", "max",
            "abs", "round", "pow", "divmod", "sorted", "reversed", "any", "all",
            "bool", "float", "isinstance", "issubclass", "repr", "format", "chr",
            "ord", "bin", "hex", "callable", "staticmethod",
            "classmethod", "property", "Exception",
            "BaseException", "ValueError", "TypeError", "KeyError",
            "IndexError", "AttributeError", "RuntimeError", "StopIteration",
            "SyntaxError", "NameError", "OSError", "ZeroDivisionError", "SecurityError",
            "__build_class__",
        }
        for name in expected:
            assert name in SAFE_BUILTINS, f"{name!r} should be in SAFE_BUILTINS"
