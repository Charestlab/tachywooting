"""
Low-level CFFI compilation for the Wooting Analog SDK Python bindings.

This file is kept separate from package_setup.py for a hard technical reason:
setup.py must reference it by file path via the cffi_modules keyword:

    cffi_modules=["tachywooting/wooting_interface_builder.py:ffibuilder"]

CFFI's setuptools plugin reads that file directly and expects a module-level
``ffibuilder`` object. Merging this into package_setup.py would break that
mechanism.

Responsibilities
----------------
- Parse the C headers shipped with the SDK (wooting-analog-wrapper.h, etc.)
- Configure the FFI builder with platform-specific library paths and flags
- Compile the Python extension module:
      tachywooting/interface/wooting_interface.<platform>.so  (Linux/macOS)
      tachywooting/interface/wooting_interface.<platform>.pyd (Windows)

Do NOT put orchestration logic here (permissions, plugin install, CLI entry
points). That belongs in package_setup.py, which calls build_interface() from
this module.

SDK Components
--------------
wooting-analog-sdk
    Core Analog SDK. Handles loading of plugins. Installed system-wide and
    updated separately from this package.
wooting-analog-common
    Common definitions (enums, structs) shared by all SDK components.
wooting-analog-plugin-dev
    Elements needed to write plugins. Re-exports wooting-analog-common, so
    plugins do not need to depend on it separately.
wooting-analog-wrapper
    The wrapper applications link against to talk to the SDK. The compiled
    dylib/dll/so is shipped inside this Python package (tachywooting/libraries/).
wooting-analog-test-plugin
    Dummy plugin backed by shared memory so other processes can inject key
    values — used for unit testing and the virtual keyboard.
wooting-analog-virtual-kb
    GTK virtual keyboard that drives the test plugin; useful for development
    without a physical analog device.
wooting-analog-sdk-updater
    Standalone tool for updating the SDK from GitHub releases.

C Headers
---------
wooting-analog-wrapper.h
    Top-level header for SDK consumers. Pulls in wooting-analog-common.h for
    enums and structs.
wooting-analog-common.h
    Common enums, structs, and constants used by both plugins and SDK users.
wooting-analog-plugin-dev.h
    Extends wooting-analog-common.h with functions from the static
    analog-sdk-common library needed when writing plugins.
plugin.h
    Minimal header that plugins must use to export their entry-point functions.
"""
import os
import platform
import subprocess
import sysconfig

from cffi import FFI

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INTERFACE_DIR = os.path.join(CURRENT_DIR, "interface")
LIBRARIES_DIR = os.path.join(CURRENT_DIR, "libraries")

SDK_LIBRARY_NAME = "wooting_analog_sdk_dist"
SDK_HEADER_FILENAME = "wooting-analog-sdk.h"
COMMON_HEADER_FILENAME = "wooting-analog-common.h"
WRAPPER_HEADER_FILENAME = "wooting-analog-wrapper.h"

SYSTEM = platform.system().lower()


def extract_header_code(*header_paths):
    comment_chars = ("#", "/", "*")

    extracted_code = []
    for header_path in header_paths:
        with open(header_path, encoding="utf-8") as file:
            for line in file:
                stripped_line = line.lstrip()
                if not stripped_line:
                    continue
                if stripped_line[0] in comment_chars:
                    continue
                if "extern" in stripped_line:
                    continue
                if stripped_line.startswith("}") and "extern" in line:
                    continue
                extracted_code.append(line)

    return "".join(extracted_code)


def _norm_arch():
    """Normalize architecture names we care about."""
    arch = platform.machine().lower()
    if arch in ("arm64", "aarch64", "arm64e"):
        return "arm64"
    if arch in ("x86_64", "amd64"):
        return "x86_64"
    raise RuntimeError(f"Unsupported CPU architecture: {arch}")


def get_platform_dir():
    """Return the correct platform SDK directory based on OS and architecture."""
    if SYSTEM not in {"darwin", "linux", "windows"}:
        raise RuntimeError(f"Unsupported platform: {SYSTEM}")

    # macOS ships separate SDK binaries per architecture; Linux/Windows use one folder.
    base_dir = os.path.join(LIBRARIES_DIR, SYSTEM)
    if SYSTEM == "darwin":
        arch = _norm_arch()
        return os.path.join(base_dir, arch)
    return base_dir


def get_include_dir(platform_dir):
    """Return the directory containing SDK headers."""
    include_dir = os.path.join(platform_dir, "includes")
    return include_dir if os.path.isdir(include_dir) else platform_dir


def get_binary_dir(platform_dir):
    """Return the directory containing SDK link/runtime binaries."""
    release_dir = os.path.join(platform_dir, "release")
    return release_dir if os.path.isdir(release_dir) else platform_dir


def get_library_dir():
    """Return the directory containing SDK link/runtime binaries."""
    return get_binary_dir(get_platform_dir())


def _ensure_sane_shared_lib_name(lib_path: str, filename: str) -> None:
    """Fix a vendored lib's embedded name if upstream baked in a build-machine
    path instead of a bare filename (breaks our rpath-based linking). No-op
    on Windows, which has no equivalent concept for .dll files.
    """
    if SYSTEM == "linux":
        read = ["patchelf", "--print-soname", lib_path]
        expected, write = filename, ["patchelf", "--set-soname", filename, lib_path]
    elif SYSTEM == "darwin":
        read = ["otool", "-D", lib_path]
        expected, write = f"@rpath/{filename}", ["install_name_tool", "-id", f"@rpath/{filename}", lib_path]
    else:
        return

    try:
        current = subprocess.run(read, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return

    if current != expected:
        print(f"[Wooting] Fixing {lib_path} name: {current!r} -> {expected!r}")
        subprocess.run(write, check=True)


def get_platform_config(binary_dir, include_dir):
    """Return platform-specific compile/link configuration."""
    arch = _norm_arch()
    # CFFI compiles a Python extension, so the Python C headers must be discoverable.
    py_inc = sysconfig.get_config_var("INCLUDEPY") or sysconfig.get_paths()["include"]

    if SYSTEM == "darwin":
        compile_args = [
            f"-I{include_dir}",
        ]
        _ensure_sane_shared_lib_name(
            os.path.join(binary_dir, f"lib{SDK_LIBRARY_NAME}.dylib"), f"lib{SDK_LIBRARY_NAME}.dylib"
        )
        # @loader_path resolves relative to the compiled extension at runtime.
        extra_link_args = [
            f"-Wl,-rpath,@loader_path/../libraries/darwin/{arch}/release",
        ]
        system_libs = []

    elif SYSTEM == "linux":
        compile_args = [
            "-Wall",
            "-Wextra",
            "-O2",
            f"-I{include_dir}",
            f"-I{py_inc}",
        ]
        sdk_so_path = os.path.join(binary_dir, f"lib{SDK_LIBRARY_NAME}.so")
        _ensure_sane_shared_lib_name(sdk_so_path, f"lib{SDK_LIBRARY_NAME}.so")
        # $ORIGIN resolves relative to the compiled extension on ELF platforms.
        extra_link_args = [
            sdk_so_path,
            "-Wl,-rpath,$ORIGIN/../libraries/linux/release",
        ]
        system_libs = []

    else:
        compile_args = [
            "/W4",
            "/O2",
            f"/I{include_dir}",
        ]
        # The official Windows archive ships the import library as
        # wooting_analog_sdk_dist.dll.lib, which MSVC will not find from the
        # shorter library name alone.
        extra_link_args = [
            os.path.join(binary_dir, f"{SDK_LIBRARY_NAME}.dll.lib"),
        ]
        system_libs = [
            "ws2_32",
            "kernel32",
            "advapi32",
            "ntdll",
            "bcrypt",
            "userenv",
        ]

    return {
        "compile_args": compile_args,
        "extra_link_args": extra_link_args,
        "system_libs": system_libs,
    }


def get_link_libraries(system_libs):
    """Return native libraries to link for the current platform."""
    if SYSTEM in {"linux", "windows"}:
        return system_libs
    return [SDK_LIBRARY_NAME] + system_libs


def create_ffibuilder(module_name: str = "wooting_interface") -> FFI:
    """Create a CFFI builder for the Wooting Analog SDK wrapper.

    Parameters
    ----------
    module_name : str, default="wooting_interface"
        Name of the generated Python extension module.

    Returns
    -------
    cffi.FFI
        Configured CFFI builder.

    Raises
    ------
    FileNotFoundError
        If required Wooting SDK headers are missing for the current platform.
    """
    platform_dir = get_platform_dir()
    include_dir = get_include_dir(platform_dir)
    binary_dir = get_binary_dir(platform_dir)

    # Prefer the modern upstream SDK header layout. Keep a fallback for older
    # vendored layouts so error messages remain useful during updates.
    sdk_header_path = os.path.join(include_dir, SDK_HEADER_FILENAME)
    common_header_path = os.path.join(include_dir, COMMON_HEADER_FILENAME)
    wrapper_header_path = os.path.join(include_dir, WRAPPER_HEADER_FILENAME)
    if os.path.isfile(sdk_header_path):
        header_paths = [sdk_header_path]
    else:
        if not os.path.isfile(common_header_path):
            raise FileNotFoundError(f"Missing header: {common_header_path}")
        if not os.path.isfile(wrapper_header_path):
            raise FileNotFoundError(f"Missing header: {wrapper_header_path}")
        header_paths = [common_header_path, wrapper_header_path]

    # Extract C declarations from headers
    header_code = extract_header_code(*header_paths)

    ffib = FFI()
    ffib.cdef(header_code)
    cfg = get_platform_config(binary_dir, include_dir)

    # Keep the generated module name stable: interface/__init__.py imports this exact name.
    ffib.set_source(
        module_name,
        f"#include <{os.path.basename(header_paths[-1])}>\n",
        libraries=get_link_libraries(cfg["system_libs"]),
        library_dirs=[binary_dir],
        extra_compile_args=cfg["compile_args"],
        extra_link_args=cfg["extra_link_args"],
    )
    return ffib


ffibuilder = create_ffibuilder("tachywooting.interface.wooting_interface")


def build_interface():
    """Compile the Wooting CFFI extension in the package interface directory.

    Returns
    -------
    None

    Raises
    ------
    Exception
        Propagates compiler, linker, or CFFI errors so callers can present a
        clear installation failure.
    """
    print("\n\nBuilding Wooting interface...")
    print(f"\n\tUsing libraries from: {get_library_dir()}")
    os.makedirs(INTERFACE_DIR, exist_ok=True)
    ffib = create_ffibuilder("wooting_interface")

    old_cwd = os.getcwd()
    try:
        # CFFI writes generated .c/.o/.so artifacts to the current working directory.
        os.chdir(INTERFACE_DIR)
        ffib.compile(verbose=True)
        print("\n\tInterface compiled successfully!\n")
    except Exception as e:
        print(f"\n\tCompilation error: {e}")
        if isinstance(e, subprocess.CalledProcessError) and e.output:
            print(f"\tCommand output:\n{e.output.decode(errors='ignore')}")
        raise
    finally:
        os.chdir(old_cwd)


if __name__ == "__main__":
    build_interface()
