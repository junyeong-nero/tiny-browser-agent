import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from browser.aria_snapshot import AriaSnapshot, NodeInfo, build_aria_snapshot


FIXTURE_YAML = """\
- heading "Welcome" [level=1]
- link "Home"
- link "About"
- textbox "Search"
- button "Submit"
- link "Home"
"""


def test_build_aria_snapshot_assigns_refs():
    snapshot = build_aria_snapshot(FIXTURE_YAML, "https://example.com")
    assert isinstance(snapshot, AriaSnapshot)
    assert len(snapshot.ref_map) == 6
    assert snapshot.url == "https://example.com"


def test_refs_are_sequential():
    snapshot = build_aria_snapshot(FIXTURE_YAML, "https://example.com")
    assert list(snapshot.ref_map.keys()) == [1, 2, 3, 4, 5, 6]


def test_node_info_role_and_name():
    snapshot = build_aria_snapshot(FIXTURE_YAML, "https://example.com")
    node = snapshot.ref_map[1]
    assert node.role == "heading"
    assert node.name == "Welcome"
    assert node.nth == 0


def test_duplicate_role_name_nth():
    snapshot = build_aria_snapshot(FIXTURE_YAML, "https://example.com")
    # "link Home" appears at ref 2 (nth=0) and ref 6 (nth=1)
    first_home = snapshot.ref_map[2]
    second_home = snapshot.ref_map[6]
    assert first_home.role == "link"
    assert first_home.name == "Home"
    assert first_home.nth == 0
    assert second_home.role == "link"
    assert second_home.name == "Home"
    assert second_home.nth == 1


def test_text_contains_ref_brackets():
    snapshot = build_aria_snapshot(FIXTURE_YAML, "https://example.com")
    assert "[1]" in snapshot.text
    assert "[4]" in snapshot.text
    assert "textbox" in snapshot.text


def test_non_node_lines_preserved():
    yaml_with_props = """\
- link "About":
  - /url: /about
"""
    snapshot = build_aria_snapshot(yaml_with_props, "https://example.com")
    # The property line "  - /url: /about" should NOT get a ref (starts with - /)
    assert "  - /url: /about" in snapshot.text
    # Only "About" link gets a ref
    assert len(snapshot.ref_map) == 1


def test_empty_yaml():
    snapshot = build_aria_snapshot("", "https://example.com")
    assert snapshot.ref_map == {}
    assert snapshot.text == ""


def test_node_without_name():
    yaml = "- main\n"
    snapshot = build_aria_snapshot(yaml, "https://example.com")
    node = snapshot.ref_map[1]
    assert node.role == "main"
    assert node.name == ""
    assert node.nth == 0
    assert "[1] main" in snapshot.text
