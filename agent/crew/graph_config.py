"""Graph configuration helpers — source selection, template mapping, etc."""

_FAL_PLATFORMS = {"linkedin", "twitter", "instagram", "youtube"}


def get_visual_source(platform: str) -> str:
    """Return the primary visual generation source for a given platform.

    fal.ai Flux is the default for all known platforms.
    Template renderer is the fallback for unknown platforms.
    """
    return "fal" if platform in _FAL_PLATFORMS else "template"
