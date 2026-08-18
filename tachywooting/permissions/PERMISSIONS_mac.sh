#!/bin/bash
set -euo pipefail

# No Wooting-specific macOS permissions doc (unlike the Linux udev rules).
# The two steps below exist because vendored .dylibs get Gatekeeper-checked
# like any other third-party binary.

# Detect architecture (arm64 or x86_64)
ARCH="$(uname -m)"

# BASE_DIR = script directory (script is in permissions/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Go up one level to access the package root
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Path to libraries
LIB_DIR="$BASE_DIR/libraries/darwin/$ARCH"

echo "Removing quarantine from: $LIB_DIR"
if [ -d "$LIB_DIR" ]; then
  # xattr: macOS tool to view/edit a file's extended attributes (metadata
  # stored alongside it, outside the file's actual content).
  # -d                    delete the named attribute
  # -r                    recurse into the directory
  # com.apple.quarantine  tag macOS sets on files from a browser/curl/archive-extract;
  #                       its presence triggers Gatekeeper's first-launch check
  # || true               ignore xattr's exit code if the attribute is already absent
  #                       on some file
  xattr -dr com.apple.quarantine "$LIB_DIR" || true
else
  echo "Directory not found: $LIB_DIR"
  exit 0
fi

# Sign .dylib files only if present
SDK="$LIB_DIR/libwooting_analog_sdk.dylib"
WRAPPER="$LIB_DIR/libwooting_analog_wrapper.dylib"

echo "Signing .dylib files (best-effort)…"
# codesign: Apple's tool to apply/inspect/verify code signatures on Mach-O
# binaries; macOS checks that signature before letting the binary run.
# --force   re-sign even if already signed (codesign otherwise refuses)
# --sign -  sign with the reserved "ad-hoc" identity: asserts the bytes are
#           unmodified, no real certificate behind it (vs. --sign "Developer ID
#           Application: ...")
if [ -f "$SDK" ]; then
  codesign --force --sign - "$SDK" || echo "codesign failed for $SDK (non-fatal)"
else
  echo "Missing: $SDK"
fi

if [ -f "$WRAPPER" ]; then
  codesign --force --sign - "$WRAPPER" || echo "codesign failed for $WRAPPER (non-fatal)"
else
  echo "Missing: $WRAPPER"
fi

echo "Gatekeeper permissions applied for $ARCH."
