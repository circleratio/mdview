#!/usr/bin/env python3
"""Generate the portable single-file version of mdview-tui.

All modules of the package (src/mdview_tui/) are concatenated into
portable/mdview-tui.py in dependency order. Package-internal imports are
removed and external imports are hoisted to the top of the file.

Usage (in the tui/ directory):
    python3 tools/bundle.py          # regenerate portable/mdview-tui.py
    python3 tools/bundle.py --check  # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import ast
import heapq
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TUI_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = TUI_DIR / "src" / "mdview_tui"
OUTPUT = TUI_DIR / "portable" / "mdview-tui.py"

# Files that must not be bundled: the `python -m` entry point and pure re-export modules.
EXCLUDE = {"__main__.py", "widgets/__init__.py"}
MAX_LINE = 100


class BundleError(Exception):
    pass


@dataclass
class _Module:
    rel: str  # path relative to the package directory, e.g. "widgets/view.py"
    dotted: str  # e.g. "mdview_tui.widgets.view"
    source: str
    tree: ast.Module
    deps: set[str] = field(default_factory=set)  # rel paths of bundled modules
    drop: set[int] = field(default_factory=set)  # 1-based line numbers to remove
    imports: list[ast.Import | ast.ImportFrom] = field(default_factory=list)  # hoisted


def _dotted(package: str, rel: str) -> str:
    parts = rel[: -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([package, *parts])


def _lines(node: ast.AST) -> range:
    return range(node.lineno, (node.end_lineno or node.lineno) + 1)


def _is_internal(node: ast.Import | ast.ImportFrom, package: str) -> bool:
    if isinstance(node, ast.ImportFrom):
        return node.level > 0 or node.module == package or (node.module or "").startswith(package + ".")
    return any(a.name == package or a.name.startswith(package + ".") for a in node.names)


def _load(package_dir: Path) -> dict[str, _Module]:
    package = package_dir.name
    modules: dict[str, _Module] = {}
    for path in sorted(package_dir.rglob("*.py")):
        rel = path.relative_to(package_dir).as_posix()
        if rel in EXCLUDE:
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            raise BundleError(f"{rel}: {exc}") from exc
        modules[rel] = _Module(rel, _dotted(package, rel), source, tree)
    return modules


def _resolve_internal(mod: _Module, node: ast.Import | ast.ImportFrom, by_dotted: dict[str, str],
                      excluded_packages: dict[str, list[str]]) -> set[str]:
    """Return the rel paths `node` depends on; reject forms that change meaning when bundled."""
    where = f"{mod.rel}:{node.lineno}"
    if isinstance(node, ast.Import) or node.level > 0:
        raise BundleError(f"{where}: only absolute 'from {mod.dotted.split('.')[0]}... import ...' is supported")
    target = node.module or ""
    deps: set[str] = set()
    for alias in node.names:
        if alias.asname:
            raise BundleError(f"{where}: aliased import '{alias.name} as {alias.asname}' is not supported")
        if f"{target}.{alias.name}" in by_dotted or f"{target}.{alias.name}" in excluded_packages:
            raise BundleError(f"{where}: importing the module object '{target}.{alias.name}' is not supported")
    if target in by_dotted:
        deps.add(by_dotted[target])
    elif target in excluded_packages:
        deps.update(excluded_packages[target])  # re-exporting __init__: depend on the whole subpackage
    else:
        raise BundleError(f"{where}: unknown module '{target}'")
    return deps


def _analyze(modules: dict[str, _Module], package: str) -> None:
    by_dotted = {m.dotted: m.rel for m in modules.values()}
    excluded_packages: dict[str, list[str]] = {}
    for rel in EXCLUDE:
        if rel.endswith("/__init__.py"):
            prefix = rel[: -len("__init__.py")]
            excluded_packages[_dotted(package, rel)] = [r for r in modules if r.startswith(prefix)]

    for mod in modules.values():
        body = mod.tree.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            mod.drop.update(_lines(body[0]))  # module docstring
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and _is_internal(node, package):
                mod.deps |= _resolve_internal(mod, node, by_dotted, excluded_packages)
                mod.drop.update(_lines(node))
        for node in body:
            if isinstance(node, (ast.Import, ast.ImportFrom)) and not _is_internal(node, package):
                mod.drop.update(_lines(node))
                if not (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
                    mod.imports.append(node)
        mod.deps.discard(mod.rel)


def _order(modules: dict[str, _Module]) -> list[_Module]:
    """Topological order (dependencies first); ties are broken by path name."""
    remaining = {rel: set(m.deps) for rel, m in modules.items()}
    ready = [rel for rel, deps in remaining.items() if not deps]
    heapq.heapify(ready)
    ordered: list[_Module] = []
    while ready:
        rel = heapq.heappop(ready)
        ordered.append(modules[rel])
        del remaining[rel]
        for other, deps in remaining.items():
            if rel in deps:
                deps.discard(rel)
                if not deps:
                    heapq.heappush(ready, other)
    if remaining:
        raise BundleError(f"circular imports among: {', '.join(sorted(remaining))}")
    return ordered


def _defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _check_names(ordered: list[_Module]) -> None:
    """Fail if two modules bind the same top-level name to different things."""
    owners: dict[str, tuple[str, str]] = {}  # name -> (what it is bound to, module)

    def bind(name: str, what: str, rel: str) -> None:
        if name in owners and owners[name][0] != what:
            raise BundleError(f"name '{name}' is defined in both {owners[name][1]} and {rel}")
        owners.setdefault(name, (what, rel))

    for mod in ordered:
        for node in mod.imports:
            for alias in node.names:
                if isinstance(node, ast.ImportFrom):
                    bind(alias.asname or alias.name, f"import {node.module}.{alias.name}", mod.rel)
                else:
                    bind(alias.asname or alias.name.split(".")[0], f"import {alias.name}", mod.rel)
        for name in sorted(_defined_names(mod.tree)):
            bind(name, f"definition in {mod.rel}", mod.rel)


def _import_block(ordered: list[_Module]) -> str:
    plain: set[str] = set()
    froms: dict[str, set[str]] = {}
    for mod in ordered:
        for node in mod.imports:
            for alias in node.names:
                text = alias.name + (f" as {alias.asname}" if alias.asname else "")
                if isinstance(node, ast.ImportFrom):
                    froms.setdefault(node.module or "", set()).add(text)
                else:
                    plain.add(text)

    def top(module: str) -> str:
        return module.split(".")[0]

    stdlib, third = [], []
    for name in plain:
        (stdlib if top(name) in sys.stdlib_module_names else third).append((name, f"import {name}"))
    for module, names in froms.items():
        line = f"from {module} import {', '.join(sorted(names))}"
        if len(line) > MAX_LINE:
            line = f"from {module} import (\n" + "".join(f"    {n},\n" for n in sorted(names)) + ")"
        (stdlib if top(module) in sys.stdlib_module_names else third).append((module, line))
    groups = [[line for _, line in sorted(g)] for g in (stdlib, third) if g]
    return "\n\n".join("\n".join(g) for g in groups)


def _body(mod: _Module) -> str:
    lines = [ln for i, ln in enumerate(mod.source.splitlines(), start=1) if i not in mod.drop]
    text = "\n".join(lines).strip("\n")
    return re.sub(r"\n{4,}", "\n\n\n", text)


def _version(modules: dict[str, _Module]) -> str:
    init = modules.get("__init__.py")
    for node in init.tree.body if init else []:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets):
            return ast.literal_eval(node.value)
    raise BundleError("__version__ is not defined in __init__.py")


def _requirements(pyproject: Path) -> list[str]:
    if not pyproject.is_file():
        return []
    m = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", pyproject.read_text(encoding="utf-8"), re.M | re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def bundle(package_dir: Path, pyproject: Path | None = None) -> str:
    """Return the source text of the single-file version of the package at `package_dir`."""
    package = package_dir.name
    modules = _load(package_dir)
    _analyze(modules, package)
    ordered = _order(modules)
    _check_names(ordered)
    requires = _requirements(pyproject or package_dir.parent.parent / "pyproject.toml")

    header = [
        "#!/usr/bin/env python3",
        f"# mdview-tui {_version(modules)} -- portable single-file version.",
        "#",
        "# GENERATED FILE: do not edit. The source of truth is tui/src/mdview_tui/;",
        "# regenerate with `python3 tools/bundle.py` in the tui/ directory.",
        "#",
        "# Requires Python 3.10+" + (f" and: {', '.join(requires)}" if requires else ""),
        "# Usage: python3 mdview-tui.py [OPTIONS] [FILE]",
        '"""mdview-tui: a TUI viewer for Markdown files (portable single-file version)."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    parts = ["\n".join(header) + "\n" + _import_block(ordered)]
    parts += [f"# ---- {package}/{mod.rel} ----\n\n{_body(mod)}" for mod in ordered]
    parts.append('if __name__ == "__main__":\n    sys.exit(main())')
    text = "\n\n\n".join(parts) + "\n"
    try:
        compile(text, OUTPUT.name, "exec")
    except SyntaxError as exc:
        raise BundleError(f"generated source does not compile: {exc}") from exc
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bundle.py", description="Generate portable/mdview-tui.py.")
    parser.add_argument("--check", action="store_true", help="only check that the file is up to date")
    args = parser.parse_args(argv)
    try:
        text = bundle(PACKAGE_DIR)
    except BundleError as exc:
        print(f"bundle.py: {exc}", file=sys.stderr)
        return 1
    rel = OUTPUT.relative_to(TUI_DIR).as_posix()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else None
        if current != text:
            reason = "missing" if current is None else "out of date"
            print(f"bundle.py: {rel} is {reason}; run `python3 tools/bundle.py`", file=sys.stderr)
            return 1
        print(f"{rel} is up to date")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    try:
        os.chmod(OUTPUT, OUTPUT.stat().st_mode | 0o111)
    except OSError:
        pass  # e.g. file systems without POSIX permissions
    print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
