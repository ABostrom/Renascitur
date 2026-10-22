"""Guards against the usual ways a "deterministic" simulation stops being deterministic.

- Iterating a set: string hashing is randomised per process, so set order changes between runs.
  `find_set_iteration` flags it statically. Wrap the set in `sorted()`, or mark a line where order
  truly does not matter with `# determinism: ok`.
- Multi-threaded BLAS: floating-point reductions can change with thread count.
- Library versions: NumPy may change its random streams between versions, so they belong to the recipe.
"""

from __future__ import annotations

import ast
import os
import platform

import numpy as np

from renasci import __version__

THREAD_VARS = ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")
_ITERATING_CALLS = {"list", "tuple", "enumerate", "zip", "iter", "next", "reversed", "dict", "min", "max"}
_SET_OPS = (ast.BitOr, ast.Sub, ast.BitAnd, ast.BitXor)


def _setish(node: ast.AST) -> bool:
    if isinstance(node, (ast.Set, ast.SetComp)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("set", "frozenset"):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, _SET_OPS):
        return _setish(node.left) or _setish(node.right)
    return False


def find_set_iteration(source: str) -> list[int]:
    """Line numbers where code iterates something that is visibly a set."""
    tree = ast.parse(source)
    allowed = {i + 1 for i, line in enumerate(source.splitlines()) if "# determinism: ok" in line}
    hits = []
    for node in ast.walk(tree):
        iterated = []
        if isinstance(node, (ast.For, ast.AsyncFor)):
            iterated.append(node.iter)
        elif isinstance(node, ast.comprehension):
            iterated.append(node.iter)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ITERATING_CALLS:
            iterated.extend(node.args)
        for it in iterated:
            if _setish(it) and it.lineno not in allowed and getattr(node, "lineno", it.lineno) not in allowed:
                hits.append(it.lineno)
    return sorted(set(hits))  # determinism: ok (sorted)


def check_environment() -> None:
    """Fail loudly if BLAS may run multi-threaded."""
    for var in THREAD_VARS:
        if os.environ.get(var) != "1":
            raise RuntimeError(f"{var} must be '1' for deterministic floating point (import renasci first)")


def versions() -> dict[str, str]:
    """The versions that are part of what a recipe means."""
    return {"engine": __version__, "python": platform.python_version(), "numpy": np.__version__}
