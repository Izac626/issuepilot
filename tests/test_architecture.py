"""헥사고날 의존 규칙을 강제한다.

  domain       → 표준 라이브러리, pydantic만
  application  → domain만
  adapters     → application, domain, config (어댑터끼리는 서로 모른다)
  bootstrap    → 전부 (유일한 조립 지점)
"""
import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "issuepilot"
THIRD_PARTY = {"anthropic", "github", "git", "dotenv", "chromadb", "sentence_transformers", "requests",
               "fastembed", "numpy", "onnxruntime"}


def imports_of(path: Path) -> set[str]:
    """파일이 import하는 모듈을 issuepilot 기준 절대 이름으로 돌려준다."""
    rel = path.relative_to(PKG.parent).with_suffix("")
    package = list(rel.parts[:-1])
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                found.add(".".join(base + ([node.module] if node.module else [])))
            elif node.module:
                found.add(node.module)
    return found


def files(layer: str) -> list[Path]:
    return sorted((PKG / layer).rglob("*.py"))


def violations(path: Path, forbidden_prefixes: tuple[str, ...], forbidden_roots: set[str]) -> list[str]:
    bad = []
    for mod in imports_of(path):
        if mod.startswith(forbidden_prefixes) or mod.split(".")[0] in forbidden_roots:
            bad.append(mod)
    return bad


@pytest.mark.parametrize("path", files("domain"), ids=lambda p: p.name)
def test_domain_depends_on_nothing_outside(path):
    bad = violations(path, ("issuepilot.application", "issuepilot.adapters", "issuepilot.bootstrap",
                            "issuepilot.config"), THIRD_PARTY | {"os", "subprocess"})
    assert not bad, f"{path.name} → {bad}"


@pytest.mark.parametrize("path", files("application"), ids=lambda p: p.name)
def test_application_depends_only_on_domain(path):
    bad = violations(path, ("issuepilot.adapters", "issuepilot.bootstrap", "issuepilot.config"), THIRD_PARTY)
    assert not bad, f"{path.name} → {bad}"


@pytest.mark.parametrize("path", files("adapters"), ids=lambda p: p.name)
def test_adapters_do_not_import_each_other_or_bootstrap(path):
    own = ".".join(path.relative_to(PKG.parent).with_suffix("").parts[:-1])
    for mod in imports_of(path):
        if mod.startswith("issuepilot.adapters") and not mod.startswith(own):
            # inbound는 bootstrap을 통해서만 outbound를 얻는다
            pytest.fail(f"{path.name} → {mod}")
    side = path.relative_to(PKG / "adapters").parts[0]
    if side == "outbound":
        assert not violations(path, ("issuepilot.bootstrap",), set()), path.name


def test_only_bootstrap_wires_adapters():
    for path in PKG.glob("*.py"):
        if path.name in {"bootstrap.py", "__main__.py"}:
            continue
        assert not violations(path, ("issuepilot.adapters",), set()), path.name
