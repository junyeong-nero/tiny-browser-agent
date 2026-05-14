from browser import PlaywrightBrowser, EnvState

from tools.helpers import (
    click_locator,
    mark_and_resolve_ref_locator,
    wait_for_page_ready,
)


def handle_type_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    locator = mark_and_resolve_ref_locator(computer, args, "type_by_ref")
    text = str(args["text"])
    press_enter = bool(args.get("press_enter", False))

    computer.highlight_locator(locator, kind="type")
    click_locator(locator)
    wait_for_page_ready(computer)
    locator.fill(text)
    wait_for_page_ready(computer)

    if press_enter:
        return computer.key_combination(["Enter"])

    return computer.current_state()
