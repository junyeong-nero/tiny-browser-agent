from browser import PlaywrightBrowser, EnvState

from tools.helpers import current_state_after_page_ready, mark_and_resolve_ref_locator


def handle_wait_for_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    locator = mark_and_resolve_ref_locator(computer, args, "wait_for_ref")
    state = args.get("state", "visible")
    timeout_ms = int(args.get("timeout_ms", 5000))
    locator.wait_for(state=state, timeout=timeout_ms)
    return current_state_after_page_ready(computer)
