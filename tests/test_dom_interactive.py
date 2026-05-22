import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from browser.aria_snapshot import NodeInfo, build_aria_snapshot
from browser.dom_interactive import (
    DomInteractiveNode,
    build_dom_node_infos,
    extract_dom_interactive,
    initial_occurrence_counter,
)


def _dom(dom_ref="dom-0", role="button", name="Accept", **overrides):
    return DomInteractiveNode(
        dom_ref=dom_ref,
        role=role,
        name=name,
        tag=overrides.pop("tag", "button"),
        aria_hidden=overrides.pop("aria_hidden", True),
        inert=overrides.pop("inert", False),
        in_shadow_root=overrides.pop("in_shadow_root", False),
    )


def test_extract_dom_interactive_returns_empty_on_evaluate_failure():
    target = MagicMock()
    target.evaluate.side_effect = RuntimeError("frame detached")
    assert extract_dom_interactive(target) == []


def test_extract_dom_interactive_maps_raw_results():
    target = MagicMock()
    target.evaluate.return_value = [
        {
            "dom_ref": "dom-0",
            "role": "button",
            "name": "Accept",
            "tag": "button",
            "aria_hidden": True,
            "inert": False,
            "in_shadow_root": False,
        },
        {
            "dom_ref": "dom-1",
            "role": None,  # falsy role should default to 'generic'
            "name": None,
            "tag": "div",
            "aria_hidden": False,
            "inert": True,
            "in_shadow_root": False,
        },
    ]
    nodes = extract_dom_interactive(target)
    assert len(nodes) == 2
    assert nodes[0].role == "button" and nodes[0].aria_hidden is True
    assert nodes[1].role == "generic"
    assert nodes[1].name == ""
    assert nodes[1].inert is True


def test_build_dom_node_infos_assigns_sequential_refs_and_marks_dom_ref():
    counter = initial_occurrence_counter({})
    entries, lines, next_ref = build_dom_node_infos(
        [_dom(dom_ref="dom-0"), _dom(dom_ref="dom-1", name="Reject")],
        counter,
        next_ref=10,
    )
    assert list(entries.keys()) == [10, 11]
    assert next_ref == 12
    assert entries[10].dom_ref == "dom-0"
    assert entries[10].actionable is True
    assert entries[10].states == {"aria-hidden": True}
    assert "dom-augmented" in lines[0]
    assert "[10]" in lines[0]


def test_build_dom_node_infos_continues_nth_from_existing_ref_map():
    aria_map = build_aria_snapshot(
        '- button "Accept"\n', "https://x"
    ).ref_map
    counter = initial_occurrence_counter(aria_map)
    entries, _lines, _next = build_dom_node_infos(
        [_dom(dom_ref="dom-0", role="button", name="Accept")],
        counter,
        next_ref=99,
    )
    new_node = next(iter(entries.values()))
    # ARIA already had nth=0 for ("button", "Accept"); DOM continues at nth=1.
    assert new_node.nth == 1


def test_initial_occurrence_counter_uses_highest_nth_plus_one():
    ref_map = {
        1: NodeInfo(role="link", name="Home", nth=0),
        2: NodeInfo(role="link", name="Home", nth=1),
        3: NodeInfo(role="button", name="Go", nth=0),
    }
    counter = initial_occurrence_counter(ref_map)
    assert counter[("link", "Home")] == 2
    assert counter[("button", "Go")] == 1
    assert counter[("button", "Missing")] == 0


def test_states_include_inert_and_shadow_flags():
    counter = initial_occurrence_counter({})
    entries, _lines, _ = build_dom_node_infos(
        [
            _dom(
                dom_ref="dom-7",
                aria_hidden=False,
                inert=True,
                in_shadow_root=True,
            )
        ],
        counter,
        next_ref=1,
    )
    node = entries[1]
    assert node.states == {"inert": True, "shadow-root": True}
    assert node.raw_attrs == "[dom-ref=dom-7]"
