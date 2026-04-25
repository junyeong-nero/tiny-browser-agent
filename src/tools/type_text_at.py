from browser import PlaywrightBrowser, EnvState

from tools.helpers import denormalized_point


def handle_type_text_at(computer: PlaywrightBrowser, args: dict) -> EnvState:
    x, y = denormalized_point(args, computer)
    return computer.type_text_at(
        x=x,
        y=y,
        text=args["text"],
        press_enter=args.get("press_enter", False),
        clear_before_typing=args.get("clear_before_typing", True),
    )
