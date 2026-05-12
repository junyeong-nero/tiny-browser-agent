from browser import PlaywrightBrowser, EnvState


def handle_key_combination(computer: PlaywrightBrowser, args: dict) -> EnvState:
    raw_keys = args["keys"]
    if isinstance(raw_keys, str):
        keys = [key.strip() for key in raw_keys.split("+")]
    elif isinstance(raw_keys, (list, tuple)):
        keys = [str(key).strip() for key in raw_keys]
    else:
        raise TypeError(
            "key_combination keys must be a '+'-separated string or list of key names"
        )

    keys = [key for key in keys if key]
    if not keys:
        raise ValueError("key_combination requires at least one key")

    return computer.key_combination(keys)
