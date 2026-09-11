"""
Backwards Compatibility Shim for backend.models.location.
Canonical module relocated to backend.app.models.location.
"""

from backend.app.models.location import *  # noqa: F401, F403
from backend.app.models.location import (
    get_live_location,
    resolve_destination,
    STUDY_AREA_LANDMARKS,
)
