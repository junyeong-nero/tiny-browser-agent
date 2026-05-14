"""Shared ffmpeg filters for browser GIF artifacts."""

GIF_MAX_WIDTH = 1920
GIF_MAX_HEIGHT = 1080


def build_high_quality_gif_filter(source: str) -> str:
    """Return a palette-optimized GIF filter capped to full-HD output."""
    scale_filter = (
        f"scale=w='min(iw\\,{GIF_MAX_WIDTH})':h='min(ih\\,{GIF_MAX_HEIGHT})'"
        ":force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos"
    )
    palette_filter = (
        "split[p0][p1];"
        "[p0]palettegen=max_colors=256:stats_mode=full:reserve_transparent=0[p];"
        "[p1][p]paletteuse=dither=sierra2_4a"
    )
    return f"{source},{scale_filter},{palette_filter}"
