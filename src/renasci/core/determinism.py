"""Guards against the usual ways a "deterministic" simulation stops being deterministic.

- Iterating a set: string hashing is randomised per process, so set order changes between runs.
  `find_set_iteration` flags it statically: set literals and comprehensions, `set()`/`frozenset()`,
  set operators and methods, and names assigned from those, when they are looped over, listed,
  joined, summed, mapped, star-unpacked or popped. Wrap the set in `sorted()`, or mark a line where
  order truly does not matter with `# determinism: ok`. Sets held in attributes (e.g.
  `system.reads`) are invisible to a static check; the cross-process hash-seed test covers those.
  Dict iteration is not flagged: dicts keep insertion order, which is deterministic when the
  insertions are.
- Multi-threaded BLAS: floating-point reductions can change with thread count. The thread limits
  must be set before NumPy loads, so `import renasci` first.
- Library versions: NumPy may change its random streams between minor versions, so Python and NumPy
  major.minor versions belong to the recipe.

Results are reproducible on the same platform. Across operating systems the platform maths library
(`math.log`, NumPy's normal tails) may differ in the last bit.
"""

from __future__ import annotations

import ast
import os
import platform

import numpy as np

import renasci
from renasci import __version__

THREAD_VARS = renasci.THREAD_VARS
_ITERATING_CALLS = {"list", "tuple", "enumerate", "zip", "iter", "next", "reversed", "dict", "map", "filter", "sum"}
_SET_METHODS = {"union", "intersection", "difference", "symmetric_difference"}
_SET_OPS = (ast.BitOr, ast.Sub, ast.BitAnd, ast.BitXor)


def _setish(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, (ast.Set, ast.SetComp)):
        return True
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id in ("set", "frozenset"):
            return True
        if isinstance(f, ast.Attribute) and f.attr in _SET_METHODS:
            return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, _SET_OPS):
        return _setish(node.left, names) or _setish(node.right, names)
    if isinstance(node, ast.IfExp):
        return _setish(node.body, names) or _setish(node.orelse, names)
    return False


def _set_names(tree: ast.AST) -> set[str]:
    """Names assigned a set-ish value anywhere in the module (a deliberately simple over-approximation)."""
    names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            targets, value = [], None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            if value is not None and _setish(value, names):
                for t in targets:
                    if isinstance(t, ast.Name) and t.id not in names:
                        names.add(t.id)
                        changed = True
    return names


def find_set_iteration(source: str) -> list[int]:
    """Line numbers where code depends on the order of something that is visibly a set."""
    tree = ast.parse(source)
    names = _set_names(tree)
    allowed = {i + 1 for i, line in enumerate(source.splitlines()) if "# determinism: ok" in line}
    hits: list[int] = []
    for node in ast.walk(tree):
        ordered = []
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            ordered.append(node.iter)
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in _ITERATING_CALLS:
                ordered.extend(node.args)
            elif isinstance(f, ast.Attribute) and f.attr == "join":
                ordered.extend(node.args)
            elif isinstance(f, ast.Attribute) and f.attr == "pop" and not node.args:
                ordered.append(f.value)
            ordered.extend(a.value for a in node.args if isinstance(a, ast.Starred))
        for it in ordered:
            line = getattr(node, "lineno", it.lineno)
            if _setish(it, names) and it.lineno not in allowed and line not in allowed:
                hits.append(it.lineno)
    return sorted(dict.fromkeys(hits))


def check_environment() -> None:
    """Fail loudly if BLAS may run multi-threaded."""
    if renasci.NUMPY_LOADED_FIRST:
        raise RuntimeError("numpy was imported before renasci without single-thread BLAS limits; "
                           "import renasci first (or set OPENBLAS/MKL/OMP_NUM_THREADS=1 in the environment)")
    for var in THREAD_VARS:
        if os.environ.get(var) != "1":
            raise RuntimeError(f"{var} must be '1' for deterministic floating point (import renasci first)")


def versions() -> dict[str, str]:
    """The versions that are part of what a recipe means. Patch releases are not included."""
    py = platform.python_version_tuple()
    return {"engine": __version__, "python": f"{py[0]}.{py[1]}",
            "numpy": ".".join(np.__version__.split(".")[:2])}
