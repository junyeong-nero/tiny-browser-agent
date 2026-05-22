"""DOM-based interactive element extractor for ARIA snapshot augmentation.

The ARIA tree intentionally drops elements that are aria-hidden, inert, or
hidden inside closed/open shadow roots. Some sites use those exact mechanisms
to render visually-interactive popups (cookie banners, modals layered with
`aria-hidden="true"`, custom Shadow DOM widgets). This module walks the raw
DOM, finds interactive candidates that ARIA would drop, and stamps each with
`data-tba-dom-ref="dom-N"` so they can be resolved by selector after the
snapshot is built.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .aria_snapshot import NodeInfo

DOM_REF_ATTR = "data-tba-dom-ref"

# Run in the page context. Returns a list of dicts describing nodes ARIA would
# drop but that are visible and interactive. Stamps each with DOM_REF_ATTR.
_EXTRACT_JS = r"""
() => {
  const ATTR = 'data-tba-dom-ref';
  const INTERACTIVE_TAGS = new Set([
    'A','BUTTON','INPUT','SELECT','TEXTAREA','SUMMARY','OPTION','LABEL','DETAILS'
  ]);
  const INTERACTIVE_ROLES = new Set([
    'button','link','checkbox','radio','switch','tab','menuitem','option',
    'combobox','textbox','searchbox','slider','spinbutton','menuitemcheckbox',
    'menuitemradio','treeitem'
  ]);

  // Clear any previous stamps so refs are stable per snapshot.
  document.querySelectorAll('[' + ATTR + ']').forEach(el => el.removeAttribute(ATTR));

  let nextId = 0;
  const results = [];

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    const style = el.ownerDocument.defaultView.getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    if (parseFloat(style.opacity || '1') === 0) return false;
    return true;
  };

  const ancestors = (el) => {
    const out = [];
    let cur = el;
    while (cur) {
      out.push(cur);
      const parent = cur.parentNode;
      cur = (parent instanceof ShadowRoot) ? parent.host : cur.parentElement;
    }
    return out;
  };

  const isAriaHidden = (el) =>
    ancestors(el).some(a => a.getAttribute && a.getAttribute('aria-hidden') === 'true');

  const isInert = (el) => ancestors(el).some(a => a.inert === true);

  const inShadowRoot = (el) => {
    let cur = el;
    while (cur) {
      const parent = cur.parentNode;
      if (parent instanceof ShadowRoot) return true;
      cur = (parent instanceof ShadowRoot) ? parent.host : cur.parentElement;
    }
    return false;
  };

  const accName = (el) => {
    const labelled = el.getAttribute('aria-labelledby');
    if (labelled) {
      const ids = labelled.split(/\s+/).filter(Boolean);
      const parts = ids.map(id => {
        const node = el.ownerDocument.getElementById(id);
        return node ? (node.textContent || '').trim() : '';
      }).filter(Boolean);
      if (parts.length) return parts.join(' ').slice(0, 120);
    }
    return (
      el.getAttribute('aria-label') ||
      el.getAttribute('alt') ||
      el.getAttribute('title') ||
      el.getAttribute('placeholder') ||
      (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120)
    ).trim();
  };

  const inferRole = (el) => {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit;
    const tag = el.tagName;
    if (tag === 'A' && el.hasAttribute('href')) return 'link';
    if (tag === 'BUTTON') return 'button';
    if (tag === 'INPUT') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (['submit','button','reset','image'].includes(t)) return 'button';
      return 'textbox';
    }
    if (tag === 'SELECT') return 'combobox';
    if (tag === 'TEXTAREA') return 'textbox';
    if (tag === 'SUMMARY' || tag === 'DETAILS') return 'button';
    if (tag === 'OPTION') return 'option';
    if (tag === 'LABEL') return 'label';
    return 'generic';
  };

  const isInteractive = (el) => {
    if (!(el instanceof Element)) return false;
    if (INTERACTIVE_TAGS.has(el.tagName)) return true;
    const role = el.getAttribute('role');
    if (role && INTERACTIVE_ROLES.has(role)) return true;
    if (el.hasAttribute('onclick')) return true;
    const ti = el.getAttribute('tabindex');
    if (ti !== null && parseInt(ti, 10) >= 0 && el.tagName !== 'BODY' && el.tagName !== 'HTML') return true;
    return false;
  };

  const visit = (root) => {
    if (!root || !root.querySelectorAll) return;
    const all = root.querySelectorAll('*');
    for (const el of all) {
      if (!isInteractive(el)) continue;
      if (!isVisible(el)) continue;
      const ariaHidden = isAriaHidden(el);
      const inert = isInert(el);
      const shadow = inShadowRoot(el);
      // Only surface elements ARIA would drop. ARIA-visible interactive
      // elements are already covered by the regular aria_snapshot pass.
      if (!ariaHidden && !inert && !shadow) continue;
      const refId = 'dom-' + (nextId++);
      el.setAttribute(ATTR, refId);
      results.push({
        dom_ref: refId,
        role: inferRole(el),
        name: accName(el),
        tag: el.tagName.toLowerCase(),
        aria_hidden: ariaHidden,
        inert: inert,
        in_shadow_root: shadow,
      });
      // Recurse into shadow root on this element if present.
      if (el.shadowRoot) visit(el.shadowRoot);
    }
    // Even if root itself isn't interactive, walk its shadow descendants.
    all.forEach((el) => { if (el.shadowRoot) visit(el.shadowRoot); });
  };

  visit(document);
  return results;
}
"""


@dataclass(frozen=True)
class DomInteractiveNode:
    dom_ref: str
    role: str
    name: str
    tag: str
    aria_hidden: bool
    inert: bool
    in_shadow_root: bool


def extract_dom_interactive(target: Any) -> list[DomInteractiveNode]:
    """Stamp interactive ARIA-invisible DOM nodes and return their metadata.

    ``target`` may be a Playwright Page or Frame. Returns an empty list when
    evaluation fails (e.g. detached frame) — callers continue with ARIA-only.
    """
    try:
        raw = target.evaluate(_EXTRACT_JS)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    nodes: list[DomInteractiveNode] = []
    for item in raw:
        if not isinstance(item, dict) or "dom_ref" not in item:
            continue
        nodes.append(
            DomInteractiveNode(
                dom_ref=item["dom_ref"],
                role=item.get("role") or "generic",
                name=(item.get("name") or "").strip(),
                tag=item.get("tag") or "",
                aria_hidden=bool(item.get("aria_hidden")),
                inert=bool(item.get("inert")),
                in_shadow_root=bool(item.get("in_shadow_root")),
            )
        )
    return nodes


def build_dom_node_infos(
    dom_nodes: list[DomInteractiveNode],
    occurrence_counter: dict[tuple[str, str], int],
    next_ref: int,
) -> tuple[dict[int, NodeInfo], list[str], int]:
    """Convert DOM-augmented entries into NodeInfo records and snapshot lines.

    ``occurrence_counter`` is shared with ARIA parsing so the (role, name) nth
    index stays consistent across both sources. Returns the new entries, the
    text lines to append, and the updated ``next_ref``.
    """
    entries: dict[int, NodeInfo] = {}
    lines: list[str] = []
    for node in dom_nodes:
        key = (node.role, node.name)
        nth = occurrence_counter[key]
        occurrence_counter[key] += 1
        states: dict[str, str | bool] = {}
        if node.aria_hidden:
            states["aria-hidden"] = True
        if node.inert:
            states["inert"] = True
        if node.in_shadow_root:
            states["shadow-root"] = True
        ref = next_ref
        next_ref += 1
        entries[ref] = NodeInfo(
            role=node.role,
            name=node.name,
            nth=nth,
            raw_attrs=f"[dom-ref={node.dom_ref}]",
            states=states,
            actionable=True,
            dom_ref=node.dom_ref,
        )
        state_str = " ".join(f"[{k}]" for k in states)
        name_part = f' "{node.name}"' if node.name else ""
        state_suffix = f" {state_str}" if state_str else ""
        lines.append(
            f"- [{ref}] {node.role}{name_part}{state_suffix} dom-augmented"
        )
    return entries, lines, next_ref


def initial_occurrence_counter(
    ref_map: dict[int, NodeInfo],
) -> dict[tuple[str, str], int]:
    """Seed an occurrence counter from an existing ref_map.

    DOM-augmented entries appended after ARIA must continue the nth sequence
    used by ARIA so role-based locators (when shared) do not collide.
    """
    counter: dict[tuple[str, str], int] = defaultdict(int)
    for node in ref_map.values():
        counter[(node.role, node.name)] = max(
            counter[(node.role, node.name)], node.nth + 1
        )
    return counter
