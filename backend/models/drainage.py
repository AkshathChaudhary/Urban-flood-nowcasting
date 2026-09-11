"""
Backwards Compatibility Shim for backend.models.drainage.
Canonical module relocated to backend.app.models.drainage.
"""

from backend.app.models.drainage import *  # noqa: F401, F403
from backend.app.models.drainage import DrainageGraph
