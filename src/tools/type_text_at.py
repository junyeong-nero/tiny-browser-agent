from browser import PlaywrightBrowser, EnvState

from tools.types import denormalize_x, denormalize_y


def handle_type_text_at(computer: PlaywrightBrowser, args: dict) -> EnvState:
    return computer.type_text_at(
        x=denormalize_x(args["x"], computer),
        y=denormalize_y(args["y"], computer),
        text=args["text"],
        press_enter=args.get("press_enter", False),
        clear_before_typing=args.get("clear_before_typing", True),
    )
