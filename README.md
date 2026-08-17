# TachyWooting

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/tachywooting)](https://pypi.org/project/tachywooting/)
[![Tests](https://github.com/Charestlab/tachywooting/actions/workflows/test-install.yml/badge.svg)](https://github.com/Charestlab/tachywooting/actions/workflows/test-install.yml)

Python bindings and acquisition utilities for Wooting analog keyboards.

For deeper implementation details, see [documentation.md](documentation.md).
Read the Docs/Sphinx sources live in [docs/](docs/) and use NumPy-style docstrings.
Console scripts are documented in [docs/scripts.md](docs/scripts.md).

## Project Documentation

- [README.md](README.md): project overview and quick start
- [documentation.md](documentation.md): technical details and architecture notes
- [development.md](development.md): maintainer workflow and SDK update process
- [PLUGIN_MANAGEMENT.md](PLUGIN_MANAGEMENT.md): plugin installation and troubleshooting
- [raw_sdk.md](raw_sdk.md): direct `lib`/`ffi` SDK reference for advanced use

- **Analog Key Acquisition**: Read key positions (0.0–1.0) with microsecond-level timing
- **Threshold-Based Triggering**: Automatically capture key press trajectories around actuation threshold
- **HDF5 Logging**: Hierarchical per-trial logging with automatic shard merging
- **Multi-Key Support**: Efficiently read multiple keys simultaneously using full-buffer API
- **Cross-Platform**: Linux, macOS, and Windows support
- **Automatic Setup**: Self-contained installation with system configuration
- **CLI Tools**: Command-line utilities for plugin management and testing

- Read analog key pressure as floats in the `0.0` to `1.0` range.
- Convert analog pressure to integer values in the `0` to `255` range.
- Acquire one or more keys around a threshold crossing.
- Log trials to hierarchical HDF5 files.
- Build against the bundled Wooting Analog SDK headers and native libraries.
- Inspect HDF5 logs with a small visualization CLI.

## Requirements

- Python 3.9 or newer (through 3.14).
- A supported Wooting analog keyboard.
- A local compiler toolchain for the CFFI interface build (see below).
- Platform-specific permissions for USB/native library access.

### Compiler Setup

The CFFI extension is compiled on your machine, not shipped as a prebuilt binary, so
you need a C compiler available before the interface can be built.

- **macOS**: install the Xcode Command Line Tools: `xcode-select --install`.
- **Linux**: install `gcc` via your package manager, e.g. `sudo apt install build-essential`
  (Debian/Ubuntu) or `sudo dnf groupinstall "Development Tools"` (Fedora).
- **Windows**: install the "Desktop development with C++" workload from the
  [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  (no full Visual Studio install needed), or run:

  ```powershell
  winget install --id Microsoft.VisualStudio.2022.BuildTools --override "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
  ```

  Then use an "x64 Native Tools Command Prompt" (or restart your shell so `cl.exe`
  is on `PATH`) before installing `tachywooting`.

### Quick Start

```bash
pip install .
```

### What setup is needed

`pip install` does **not** run system setup — pip installs from wheels, which have
no reliable post-install hook. Setup is split into two parts:

1. **CFFI compilation** happens **automatically the first time** you create a
   `WOOTING_ACQUISITION` (or run `wooting-demo`). It needs only a C compiler —
   no admin rights.
2. **SDK plugins + input permissions** require a **one-time privileged step**:

   ```bash
   wooting-build-interface   # installs SDK plugins + permissions (needs sudo/admin)
   ```

If the keyboard is not detected, the error message tells you exactly to run this
command — you do not have to remember it. To undo it later: `wooting-delete-interface`.

### Development Installation

```bash
python -m pip install -e ".[dev]"
wooting-build-interface
```

## Quick Start

```python
from tachywooting import WOOTING_ACQUISITION

acq = WOOTING_ACQUISITION(threshold=0.8)
acq.initialize_keyboard(verbose=True)

try:
    acq.setup_logging(name="tracking", path="logs", int_analog=2)
    trial = acq.acquire_analog_values(target_keys=["A"])
finally:
    acq.uninitialize_keyboard()
```

## CLI Demo

```bash
wooting-demo --key A --threshold 50
```

## Visual feedback (TachyPy)

On-screen pressure feedback — the interactive fixation cross and
`wait_light_press_visual()` — lives in **TachyPy**, not in this hardware package.
Install it with `pip install 'tachypy[wooting]'`, then:

```python
from tachypy import WOOTING_ACQUISITION  # keyboard + visual feedback
```

## HDF5 Logging

`setup_logging()` writes one temporary shard per trial and merges shards when `uninitialize_keyboard()` is called.

Final files use this layout:

```text
/trials/0001/keys/0004/values
```

Each `values` dataset stores columns in this order:

```text
position, time_from_onset, time_abs
```

## Visualize Logs

```bash
python -m tachywooting.visualize logs/tracking.hdf5 --list
python -m tachywooting.visualize logs/tracking.hdf5 --trial 1 --key 4
```

## Public API

- `WOOTING_ACQUISITION`: acquisition, threshold detection, readiness checks, and logging.
- `convert_char_to_keycode`: convert between key labels and HID keycodes.
- `convert_keycode_to_char`: convert between HID keycodes and key labels.
- `load_trial`: load a single trial from an HDF5 log file.
- `load_session`: load all trials from an HDF5 log file.
- `trial_to_dataframe`: convert a trial dict to a pandas DataFrame.
- `build_interface`: rebuild the CFFI interface.
- `delete_interface`: remove generated CFFI artifacts.
- `lib` and `ffi`: raw CFFI handles for advanced SDK access.

## Troubleshooting

If importing works but acquisition fails with a missing native interface error, run:

```bash
wooting-build-interface
```

If no devices are detected, confirm the keyboard is connected, Wootility recognizes it, and platform permissions have been applied.

## Hardware Requirements

This package was developed and tested with the **Wooting UwU** keypad ([wooting.io/uwu](https://wooting.io/uwu)), and its use is strongly recommended for optimal results.

![Wooting UwU keypad](repo_visuals/UwU_keyboard.png)

The UwU is a 3-key Hall effect keypad using [**Lekker L45 V2 linear switches**](https://wooting.io/product/lekker-switch-l45-v2) — contactless magnetic sensors with a smooth linear force curve (30–45 cN, no tactile bump). Keys can be configured to actuate at any depth from 0.1mm to 4.0mm.
