from browser import PlaywrightBrowser, EnvState

from tools.helpers import resolve_ref_locator


def handle_wait_for_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    computer._mark_last_action("wait_for_ref")
    locator = resolve_ref_locator(computer, args)
    state = args.get("state", "visible")
    timeout_ms = int(args.get("timeout_ms", 5000))
    locator.wait_for(state=state, timeout=timeout_ms)
    computer._page.wait_for_load_state()
    return computer.current_state()
