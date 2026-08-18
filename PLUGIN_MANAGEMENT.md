# Plugin Management Guide

## Overview

The Wooting SDK requires system plugins to communicate with keyboards. This guide explains how to install, verify, and troubleshoot the plugin installation.

## Automatic Installation

Plugins are automatically installed during the first use of the package:

1. **First time you run** `wooting-demo` or import the package
2. The package detects that plugins are missing
3. Automatically runs the complete setup (permissions → interface → plugins)
4. SDK and plugins are installed to system directories

No manual intervention required for most users!

## System Installation Paths

### Linux
| Component | Location |
|-----------|----------|
| SDK | `/usr/local/lib/libwooting_analog_sdk.so` |
| Plugin | `/usr/local/share/WootingAnalogPlugins/libwooting_analog_plugin.so` |
| Permissions | `/etc/udev/rules.d/70-wooting.rules` |

### macOS
| Component | Location |
|-----------|----------|
| SDK | `/usr/local/lib/libwooting_analog_sdk.dylib` |
| Plugin | `/usr/local/share/WootingAnalogPlugins/libwooting_analog_plugin.dylib` |
| Gatekeeper | Automatic (handled during setup) |

### Windows
| Component | Location |
|-----------|----------|
| SDK & Plugin | `C:\Program Files\WootingAnalogPlugins\` |

## Manual Plugin Management

### Install Plugins

If you need to manually install or reinstall plugins:

**CLI (full post-install setup):**
```bash
wooting-build-interface
```

This command runs:
- permission setup (Linux/macOS)
- CFFI interface build (if missing)
- SDK/plugin installation
- macOS Gatekeeper fixups

**Python API:**
```python
from tachywooting.package_setup import install_plugins
install_plugins()
```

### Uninstall Plugins Only

Remove SDK and plugins but keep the Python interface:

No dedicated CLI command is exposed for plugin-only uninstall.

**Python API:**
```python
from tachywooting.package_setup import uninstall_plugins
uninstall_plugins()
```

### Clean Everything

Remove interface, plugins, and all system files (for complete reinstall):

**CLI:**
```bash
wooting-delete-interface --cleanup-plugins
```

This removes:
- Compiled CFFI interface files
- Python `__pycache__` directories
- SDK from system directories
- Plugins from system directories
- Udev rules (Linux only)

**Python API:**
```python
from tachywooting.package_setup import delete_interface
delete_interface(cleanup_plugins=True)
```

### Clean Interface Only

Remove compiled interface without touching system plugins:

**CLI:**
```bash
wooting-delete-interface
```

**Python API:**
```python
from tachywooting.package_setup import delete_interface
delete_interface()  # or delete_interface(cleanup_plugins=False)
```

## Verification

### Verify Installation

Check if plugins are correctly installed:

```bash
# Linux
ls -lh /usr/local/lib/libwooting_analog_sdk.so
ls -lh /usr/local/share/WootingAnalogPlugins/libwooting_analog_plugin.so

# macOS
ls -lh /usr/local/lib/libwooting_analog_sdk.dylib
ls -lh /usr/local/share/WootingAnalogPlugins/libwooting_analog_plugin.dylib

# Windows
dir "C:\Program Files\WootingAnalogPlugins"
```

### Test Installation

Test that everything is working:

```bash
wooting-demo
```

Or programmatically:

```python
from tachywooting.interface import lib

# Initialize the SDK
result = lib.wooting_analog_initialise()

if result > 0:
    print(f"✓ Found {result} device(s)")
    lib.wooting_analog_uninitialise()
else:
    print(f"✗ Failed to initialize: error code {result}")
```

## Troubleshooting

### "No Wooting devices found" or "NoPlugins" error (-1995)

**Cause**: Plugins are not installed in the system directory

**Solution**:
```bash
wooting-build-interface
```

Then test again:
```bash
wooting-demo
```

### "Failed to initialize keyboard"

**Common causes**:
1. Keyboard not connected via USB
2. Plugins not installed
3. Permissions issues (Linux)
4. Version mismatch between wrapper and SDK

**Steps to diagnose**:

```bash
# 1. Check if keyboard is connected
lsusb | grep -i wooting          # Linux
system_profiler SPUSBDataType    # macOS

# 2. Check if plugins are installed
ls /usr/local/lib/libwooting*
ls /usr/local/share/WootingAnalogPlugins/

# 3. Check USB permissions (Linux)
ls -l /dev/hidraw*

# 4. Reinstall everything
wooting-delete-interface --cleanup-plugins
# Then run any wooting command to trigger auto-install
wooting-demo
```

### "Version mismatch" or "Incompatible SDK"

This can occur after updating the package but not the system plugins.

**Solution**:
```bash
# Complete reinstall
wooting-delete-interface --cleanup-plugins

# Auto-reinstall on next use
wooting-demo
```

### macOS: "Code signature invalid"

The Gatekeeper setup should handle code signing automatically, but if you encounter this:

```bash
# Reinstall and let Gatekeeper setup run
wooting-build-interface
```

No Wooting-specific doc for this. `wooting-build-interface` runs
[`PERMISSIONS_mac.sh`](tachywooting/permissions/PERMISSIONS_mac.sh) — see that file for what
the `xattr`/`codesign` flags do.

### Linux: "Permission denied" when accessing keyboard

**Problem**: User is not in the `input` group or udev rules are not applied

The udev rules `tachywooting` installs follow Wooting's own official recommendations:
[Configuring device access for Wootility under Linux (udev rules)](https://help.wooting.io/article/147-configuring-device-access-for-wootility-under-linux-udev-rules).

**Solution**:

```bash
# 1. Verify your user is in input group
groups $USER | grep input

# 2. If not, add user to group
sudo usermod -a -G input $USER

# 3. Log out and log back in (or use: newgrp input)

# 4. Verify udev rules
cat /etc/udev/rules.d/70-wooting.rules

# 5. If missing, reinstall permissions
wooting-build-interface
```

## Advanced: Custom Plugin Paths

For special use cases, you can inspect where plugins are loaded from:

```python
from tachywooting.interface import lib
import os

# SDK will look for plugins in:
# - Linux/macOS: /usr/local/share/WootingAnalogPlugins/
# - Windows: C:\Program Files\WootingAnalogPlugins\

# To verify, check the system directories
plugin_dirs = {
    "Linux": "/usr/local/share/WootingAnalogPlugins/",
    "macOS": "/usr/local/share/WootingAnalogPlugins/",
    "Windows": r"C:\Program Files\WootingAnalogPlugins"
}
```

## Support

- **Issues?** Check the troubleshooting section above
- **Still stuck?** Verify file permissions and paths match the platform
- **Need help?** See the repository README for more information

## Security Considerations

- Plugin installation requires `sudo`/admin privileges
- Files are installed in standard system directories
- Uninstallation completely removes system files
- No residual files remain after cleanup
- All operations are logged to stdout for transparency
