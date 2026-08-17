"""Python interface for Wooting analog keyboards.

The package exposes analog acquisition, hierarchical HDF5 logging, and
light-press / release readiness checks for Wooting keyboards.

On-screen visual feedback (the interactive fixation cross, ``wait_light_press_visual``)
lives in TachyPy and is available via ``pip install tachypy[wooting]`` — it is not
part of this hardware-focused package.

See Also
--------
WOOTING_ACQUISITION
    Main acquisition class.
"""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tachywooting")
except PackageNotFoundError:
    __version__ = "unknown"

# Keep package import side-effect free: building permissions/native CFFI is done explicitly
# with `wooting-build-interface` so imports stay safe in tests, docs, and CI.
from .interface import ffi, lib
from .package_setup import delete_interface
from .wooting_interface_builder import build_interface
from .wooting_utils import (
    WOOTING_ACQUISITION,
    convert_char_to_keycode,
    convert_keycode_to_char,
    load_session,
    load_trial,
    trial_to_dataframe,
)

__all__ = [
    "WOOTING_ACQUISITION",
    "__version__",
    "build_interface",
    "convert_char_to_keycode",
    "convert_keycode_to_char",
    "delete_interface",
    "lib",
    "ffi",
    "load_trial",
    "load_session",
    "trial_to_dataframe",
]
