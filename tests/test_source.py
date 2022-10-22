from chai.source import _get_module_deps


def test_can_extract_single_module_deps_from_tla_module() -> None:
    spec = """
---- MODULE M ----
EXTENDS Integers
====
"""
    assert _get_module_deps(spec) == ["Integers"]


def test_can_extract_multiple_module_deps_from_tla_module() -> None:
    spec = """
---- MODULE M ----
EXTENDS Integers, Sequences, Reals
====
"""
    assert _get_module_deps(spec) == ["Integers", "Sequences", "Reals"]


def test_can_extract_multiple_module_deps_on_multiple_lines_from_tla_module() -> None:
    spec = """
---- MODULE M ----
EXTENDS Integers,
        Sequences,

        Reals
====
"""
    assert _get_module_deps(spec) == ["Integers", "Sequences", "Reals"]


def test_can_extract_module_deps_from_instances_in_lta_module() -> None:
    spec = """
---- MODULE M ----
EXTENDS Integers,
        Sequences

INSTANCE Foo
INSTANCE Foo1, Foo2
LOCAL INSTANCE Bar
INSTANCE Baz WITH x <- y
M == INSTANCE Qux
N(_) == INSTANCE Kos
====
"""
    assert _get_module_deps(spec) == [
        "Integers",
        "Sequences",
        "Foo",
        "Foo1",
        "Foo2",
        "Bar",
        "Baz",
        "Qux",
        "Kos",
    ]
