"""
Backwards Compatibility Shim for backend.api.drainage.
Canonical router relocated to backend.app.api.drainage.
"""

from backend.app.api.drainage import *  # noqa: F401, F403
from backend.app.api.drainage import router, get_drainage_graph
