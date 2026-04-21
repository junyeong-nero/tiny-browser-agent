from browser import PlaywrightBrowser, EnvState


def handle_type_by_ref(computer: PlaywrightBrowser, args: dict) -> EnvState:
    ref = int(args["ref"])
    text = str(args["text"])
    press_enter = bool(args.get("press_enter", False))

    locator = computer.resolve_ref(ref)
    locator.click()
    computer._page.wait_for_load_state()
    locator.fill(text)
    computer._page.wait_for_load_state()

    if press_enter:
        computer.key_combination(["Enter"])

    return computer.current_state()
