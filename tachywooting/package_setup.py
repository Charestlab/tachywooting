"""
Orchestrates installation and removal of the Wooting package on the host system.

This is the high-level counterpart to wooting_interface_builder.py:

    wooting_interface_builder.py  — *how* to compile the CFFI extension (low-level,
                                    must stay a separate file for setup.py / cffi_modules)
    package_setup.py              — *when and in what order* to build, install, and
                                    clean up (permissions, plugins, Gatekeeper, CFFI)

CLI entry points
----------------
wooting-build-interface   →  run_post_install()
wooting-delete-interface  →  main_delete_interface()

Typical first-time setup
------------------------
    pip install -e .
    wooting-build-interface   # builds the CFFI .so, installs plugins system-wide

Cleanup
-------
    wooting-delete-interface            # removes .so + system plugins (default)
    wooting-delete-interface --no-plugins  # removes .so only
"""

import argparse
import glob
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

# --- Paths ---
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_INTERFACE_DIR = os.path.join(_PKG_DIR, "interface")
_PERM_MAC_SH = os.path.join(_PKG_DIR, "permissions", "PERMISSIONS_mac.sh")
_PERM_LINUX_SH = os.path.join(_PKG_DIR, "permissions", "PERMISSIONS_linux.sh")
_LIBRARIES_DIR = os.path.join(_PKG_DIR, "libraries")
_SDK_LIBRARY_BASENAME = "wooting_analog_sdk"
_SDK_DIST_LIBRARY_BASENAME = "wooting_analog_sdk_dist"

# Compiled CFFI extension only (.so on Linux/macOS, .pyd on Windows)
_COMPILED_GLOBS = (
    os.path.join(_INTERFACE_DIR, "wooting_interface*.so"),
    os.path.join(_INTERFACE_DIR, "wooting_interface*.pyd"),
)

# Plugin directory paths per platform
_PLUGIN_DIRS = {
    "Darwin": "/usr/local/share/WootingAnalogPlugins",
    "Linux": "/usr/local/share/WootingAnalogPlugins",
    "Windows": r"C:\Program Files\WootingAnalogPlugins"
}


def _compiled_interface_present() -> bool:
    """Return True if any compiled CFFI module is already present."""
    return any(glob.glob(pattern) for pattern in _COMPILED_GLOBS)


def _make_executable(path: str) -> None:
    """Ensure the .sh script is executable (no-op if it already is)."""
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR)  # add user-exec bit
    except Exception:
        # Soft-fail: permissions will be tried by /bin/bash anyway.
        pass


def setup_permissions() -> None:
    """
    Run platform-specific permission script only if the interface
    is not yet compiled. No-op if compiled or on unsupported OS.

    NOTE: This is called during post-installation, not on every import.
    """
    if _compiled_interface_present():
        return  # already compiled ⇒ do nothing

    system = platform.system()
    if system == "Darwin" and os.path.isfile(_PERM_MAC_SH):
        _make_executable(_PERM_MAC_SH)
        try:
            print("[Wooting] Setting up macOS permissions...")
            subprocess.run(["/bin/bash", _PERM_MAC_SH], check=True, cwd=_PKG_DIR)
            print("[Wooting] macOS permissions configured successfully.")
        except Exception as e:
            print(f"[Wooting] macOS permission setup skipped (script error): {e}")

    elif system == "Linux" and os.path.isfile(_PERM_LINUX_SH):
        _make_executable(_PERM_LINUX_SH)
        try:
            print("[Wooting] Setting up Linux permissions...")
            subprocess.run(["/bin/bash", _PERM_LINUX_SH], check=True, cwd=_PKG_DIR)
            print("[Wooting] Linux permissions configured successfully.")
        except Exception as e:
            print(f"[Wooting] Linux permission setup skipped (script error): {e}")
    # Windows or missing script: silently skip


def install_plugins() -> None:
    r"""
    Install Wooting SDK and plugins to system directories.
    This is required for the SDK to detect and initialize devices.

    Installation structure:
    - SDK library: /usr/local/lib/ (Linux/macOS)
    - Plugins: /usr/local/share/WootingAnalogPlugins/ (Linux/macOS)
    - Windows: C:\Program Files\WootingAnalogPlugins\

    Requires sudo/admin privileges on Linux/macOS.
    """
    system = platform.system()

    if system not in _PLUGIN_DIRS:
        print(f"[Wooting] Plugin installation not supported on {system}")
        return

    plugin_dir = _PLUGIN_DIRS[system]

    # Determine source directories and files based on platform. New upstream SDK
    # archives keep runtime binaries under release/; older vendored layouts kept
    # them directly in the platform folder.
    if system == "Darwin":
        arch = platform.machine()  # 'arm64' or 'x86_64'
        platform_dir = os.path.join(_LIBRARIES_DIR, "darwin", arch)
        sdk_dest = "/usr/local/lib"
        plugin_files = ["libwooting_analog_plugin.dylib"]
        sdk_files = ["libwooting_analog_sdk.dylib", "libwooting_analog_sdk_dist.dylib"]
    elif system == "Linux":
        platform_dir = os.path.join(_LIBRARIES_DIR, "linux")
        sdk_dest = "/usr/local/lib"
        plugin_files = ["libwooting_analog_plugin.so"]
        sdk_files = ["libwooting_analog_sdk.so", "libwooting_analog_sdk_dist.so"]
    elif system == "Windows":
        platform_dir = os.path.join(_LIBRARIES_DIR, "windows")
        plugin_dir = r"C:\\Program Files\\WootingAnalogPlugins"
        sdk_dest = plugin_dir  # On Windows, everything goes in the same place
        plugin_files = ["wooting_analog_plugin.dll"]
        sdk_files = ["wooting_analog_sdk.dll", "wooting_analog_sdk_dist.dll"]
    else:
        return

    release_dir = os.path.join(platform_dir, "release")
    source_dir = release_dir if os.path.isdir(release_dir) else platform_dir

    existing_sdk_files = [
        file_name for file_name in sdk_files if os.path.exists(os.path.join(source_dir, file_name))
    ]
    existing_plugin_files = [
        file_name for file_name in plugin_files if os.path.exists(os.path.join(source_dir, file_name))
    ]
    if not existing_sdk_files and not existing_plugin_files:
        print(f"[Wooting] Warning: no installable SDK files found in {source_dir}")
        return

    try:
        # Install SDK to /usr/local/lib (or system lib directory)
        if existing_sdk_files:
            print(f"[Wooting] Installing SDK to {sdk_dest}...")

        if system in ["Linux", "Darwin"] and existing_sdk_files:
            # Create lib directory if needed
            if not os.path.exists(sdk_dest):
                subprocess.run(["sudo", "mkdir", "-p", sdk_dest], check=True)

            # Copy SDK files
            for sdk_file in existing_sdk_files:
                source_path = os.path.join(source_dir, sdk_file)
                dest_path = os.path.join(sdk_dest, sdk_file)
                subprocess.run(["sudo", "cp", source_path, dest_path], check=True)
                subprocess.run(["sudo", "chmod", "755", dest_path], check=True)

            # Run ldconfig to update library cache
            subprocess.run(["sudo", "ldconfig"], check=False)

        if system == "Windows" and existing_sdk_files:
            if not os.path.exists(sdk_dest):
                os.makedirs(sdk_dest, exist_ok=True)
            for sdk_file in existing_sdk_files:
                shutil.copy2(os.path.join(source_dir, sdk_file), os.path.join(sdk_dest, sdk_file))

        # Install plugins to plugin directory when an archive contains them. The
        # current official SDK archives may rely on the system Wooting install
        # for plugins and only ship SDK runtime binaries.
        if existing_plugin_files:
            print(f"[Wooting] Installing plugins to {plugin_dir}...")

            if not os.path.exists(plugin_dir):
                if system in ["Linux", "Darwin"]:
                    subprocess.run(["sudo", "mkdir", "-p", plugin_dir], check=True)
                else:
                    os.makedirs(plugin_dir, exist_ok=True)

        # Copy plugin files
        for plugin_file in existing_plugin_files:
            source_path = os.path.join(source_dir, plugin_file)
            dest_path = os.path.join(plugin_dir, plugin_file)

            if system in ["Linux", "Darwin"]:
                subprocess.run(["sudo", "cp", source_path, dest_path], check=True)
                subprocess.run(["sudo", "chmod", "755", dest_path], check=True)
            else:
                shutil.copy2(source_path, dest_path)

        print("[Wooting] SDK setup completed successfully.")

    except subprocess.CalledProcessError as e:
        print(f"[Wooting] Failed to install (may require sudo): {e}")
    except Exception as e:
        print(f"[Wooting] Installation error: {e}")


def uninstall_plugins() -> None:
    """
    Remove installed Wooting SDK and plugins from system directories.
    This is useful for cleanup and testing.

    Removes:
    - SDK library from /usr/local/lib/ (Linux/macOS)
    - Plugin directory /usr/local/share/WootingAnalogPlugins/
    - Udev rules /etc/udev/rules.d/70-wooting.rules (Linux)

    Requires sudo/admin privileges on Linux/macOS.
    """
    system = platform.system()

    if system not in _PLUGIN_DIRS:
        print(f"[Wooting] Plugin uninstallation not supported on {system}")
        return

    plugin_dir = _PLUGIN_DIRS[system]

    # Determine SDK location and files based on platform
    if system == "Darwin":
        sdk_dir = "/usr/local/lib"
        sdk_files = ["libwooting_analog_sdk.dylib"]
    elif system == "Linux":
        sdk_dir = "/usr/local/lib"
        sdk_files = ["libwooting_analog_sdk.so"]
    elif system == "Windows":
        sdk_dir = plugin_dir  # On Windows, everything is in the same place
        sdk_files = ["wooting_analog_sdk.dll"]
    else:
        return

    try:
        # Remove plugins directory
        if os.path.exists(plugin_dir):
            print(f"[Wooting] Removing plugins from {plugin_dir}...")
            if system in ["Linux", "Darwin"]:
                subprocess.run(["sudo", "rm", "-rf", plugin_dir], check=True)
            else:
                shutil.rmtree(plugin_dir, ignore_errors=True)

        # Remove SDK files from lib directory (Linux/macOS only)
        if system in ["Linux", "Darwin"]:
            print(f"[Wooting] Removing SDK from {sdk_dir}...")
            for sdk_file in sdk_files:
                sdk_path = os.path.join(sdk_dir, sdk_file)
                if os.path.exists(sdk_path):
                    subprocess.run(["sudo", "rm", sdk_path], check=True)

            # Update library cache
            subprocess.run(["sudo", "ldconfig"], check=False)

        # Remove udev rules on Linux
        if system == "Linux":
            udev_rules = "/etc/udev/rules.d/70-wooting.rules"
            if os.path.exists(udev_rules):
                print(f"[Wooting] Removing udev rules from {udev_rules}...")
                try:
                    subprocess.run(["sudo", "rm", udev_rules], check=True)
                    subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=False)
                    print("[Wooting] Udev rules removed successfully.")
                except subprocess.CalledProcessError as e:
                    print(f"[Wooting] Failed to remove udev rules: {e}")

        print("[Wooting] SDK and plugins removed successfully.")

    except subprocess.CalledProcessError as e:
        print(f"[Wooting] Failed to remove (may require sudo): {e}")
    except Exception as e:
        print(f"[Wooting] Removal error: {e}")


def apply_macos_gatekeeper() -> None:
    """
    Best-effort: remove quarantine and ad-hoc sign dylibs shipped in:
        <pkg>/libraries/darwin/<arch>/release/
    Runs only on macOS, no-op otherwise. Never raises.
    """
    if platform.system() != "Darwin":
        return

    arch = platform.machine()  # 'arm64' or 'x86_64'
    platform_dir = Path(_PKG_DIR) / "libraries" / "darwin" / arch
    dylib_dir = platform_dir / "release" if (platform_dir / "release").is_dir() else platform_dir
    sdk_path = dylib_dir / f"lib{_SDK_LIBRARY_BASENAME}.dylib"
    sdk_dist_path = dylib_dir / f"lib{_SDK_DIST_LIBRARY_BASENAME}.dylib"

    try:
        if dylib_dir.is_dir():
            # Remove quarantine on the folder (recursive)
            print(f"[Wooting] Removing macOS quarantine from: {dylib_dir}")
            subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(dylib_dir)], check=False)
        else:
            # Nothing to do if the folder is not present yet (e.g., sdist)
            return

        # Sign only if files exist (first install/build may not have copied them yet)
        if sdk_path.exists():
            subprocess.run(["codesign", "--force", "--sign", "-", str(sdk_path)], check=False)
        if sdk_dist_path.exists():
            subprocess.run(["codesign", "--force", "--sign", "-", str(sdk_dist_path)], check=False)
        print("[Wooting] macOS Gatekeeper setup completed.")
    except Exception as e:
        # Never hard-fail here; keep import working and just inform.
        print(f"[Wooting] macOS Gatekeeper step skipped: {e}")


def build_interface_if_needed() -> None:
    """Build the CFFI interface when no compiled module is present.

    Returns
    -------
    None

    Raises
    ------
    RuntimeError
        If ``setuptools`` is missing or if CFFI compilation fails.
    """
    if _compiled_interface_present():
        return  # already built

    try:
        try:
            import setuptools  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "setuptools is required to build the CFFI interface on Python >= 3.12. "
                'Install it with: python -m pip install "setuptools>=77.0"'
            ) from exc

        from .wooting_interface_builder import build_interface
        print("[Wooting] Building CFFI interface...")
        build_interface()
        print("[Wooting] Interface built successfully.")
    except Exception as e:
        # Surface a clear error so users know why the build failed
        raise RuntimeError(f"[Wooting] Failed to build CFFI interface: {e}") from e


def delete_interface(file: Optional[str] = None, cleanup_plugins: bool = True) -> None:
    """Remove compiled CFFI artifacts, __pycache__, and egg-info leftovers.

    Parameters
    ----------
    file : str, optional
        If given, also removes a same-named file from the project root
        (legacy behaviour, kept for backward compatibility).
    cleanup_plugins : bool
        When True (default) also calls :func:`uninstall_plugins`.
    """
    interface_dir = os.path.join(_PKG_DIR, "interface")
    for file_path in glob.glob(os.path.join(interface_dir, "wooting_interface*")):
        try:
            os.remove(file_path)
        except OSError:
            pass

    for pycache_dir in [
        os.path.join(_PKG_DIR, "__pycache__"),
        os.path.join(_PKG_DIR, "interface", "__pycache__"),
    ]:
        if os.path.isdir(pycache_dir):
            try:
                shutil.rmtree(pycache_dir)
            except Exception:
                pass

    if file:
        project_root = os.path.dirname(_PKG_DIR)
        for filename in [file, "plot.png"]:
            fp = os.path.join(project_root, filename)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass

    egg_info_dir = os.path.join(os.path.dirname(_PKG_DIR), "wooting_interface.egg-info")
    if os.path.isdir(egg_info_dir):
        try:
            shutil.rmtree(egg_info_dir)
        except Exception:
            pass

    if cleanup_plugins:
        uninstall_plugins()


def run_post_install() -> None:
    """Run permissions, native interface build, and macOS Gatekeeper setup.

    Returns
    -------
    None

    Notes
    -----
    This function backs the ``wooting-build-interface`` console script.
    """
    print("\n[Wooting] Running post-installation setup...\n")

    # 1) Setup permissions (only if not compiled yet)
    setup_permissions()

    # 2) Build interface on first import if missing
    build_interface_if_needed()

    # 3) Install plugins (required for SDK to work)
    install_plugins()

    # 4) Apply macOS Gatekeeper fixups (best-effort), now that files likely exist
    apply_macos_gatekeeper()

    print("\n[Wooting] Post-installation setup completed.\n")


def main_delete_interface() -> None:
    """CLI entry point for the ``wooting-delete-interface`` command."""
    parser = argparse.ArgumentParser(
        description="Remove the compiled Wooting CFFI interface and system plugins.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wooting-delete-interface                    # Remove interface + plugins (default)
  wooting-delete-interface --no-plugins       # Remove interface only, keep plugins
        """,
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="Keep system-wide installed plugins (skip sudo removal)",
    )
    args = parser.parse_args()

    cleanup_plugins = not args.no_plugins
    try:
        print("\n[Wooting] Removing compiled interface...")
        if cleanup_plugins:
            print("[Wooting] System plugins will also be removed...")
        delete_interface(cleanup_plugins=cleanup_plugins)
        print("[Wooting] Done.\n")
    except KeyboardInterrupt:
        print("\n[Wooting] Cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Wooting] Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_post_install()
