from browser import PlaywrightBrowser, EnvState

from tools.helpers import resolve_ref_locator


def handle_type_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    text = str(args["text"])
    press_enter = bool(args.get("press_enter", False))

    locator = resolve_ref_locator(computer, args)
    locator.click()
    computer._page.wait_for_load_state()
    locator.fill(text)
    computer._page.wait_for_load_state()

    if press_enter:
        computer.key_combination(["Enter"])

    return computer.current_state()
