#!/bin/bash

set -e  # Exit on first error

# Define rule target following Wootility recommendations
RULES_FILE="/etc/udev/rules.d/70-wooting.rules"

echo "Setting up Wooting udev rules following Wootility recommendations..."

# Create comprehensive udev rules for all Wooting keyboards
# Following: https://help.wooting.io/article/147-configuring-device-access-for-wootility-under-linux-udev-rules
#   "https://help.wooting.io/" -> "Wootility" subsection -> "Configuring device access for Wootility under Linux (udev rules)"
cat << 'EOF' | sudo tee "$RULES_FILE" > /dev/null
# Wooting One Legacy
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff01", MODE:="0660", GROUP="input", TAG+="uaccess"
SUBSYSTEM=="usb", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff01", MODE:="0660", GROUP="input", TAG+="uaccess"
# Wooting One update mode
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2402", MODE:="0660", GROUP="input", TAG+="uaccess"

# Wooting Two Legacy
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff02", MODE:="0660", GROUP="input", TAG+="uaccess"
SUBSYSTEM=="usb", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff02", MODE:="0660", GROUP="input", TAG+="uaccess"
# Wooting Two update mode
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2403", MODE:="0660", GROUP="input", TAG+="uaccess"

# Generic Wootings (covers newer models like UwU, 60HE, etc.)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="31e3", MODE:="0660", GROUP="input", TAG+="uaccess" 
SUBSYSTEM=="usb", ATTRS{idVendor}=="31e3", MODE:="0660", GROUP="input", TAG+="uaccess"

# Wooting One Legacy for snap Chromium (Ubuntu)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff01", TAG+="snap_chromium_chromedriver"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff01", TAG+="snap_chromium_chromium"

# Wooting One update mode for snap Chromium (Ubuntu)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2402", TAG+="snap_chromium_chromedriver"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2402", TAG+="snap_chromium_chromium"

# Wooting Two Legacy for snap Chromium (Ubuntu)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff02", TAG+="snap_chromium_chromedriver"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="ff02", TAG+="snap_chromium_chromium"

# Wooting Two update mode for snap Chromium (Ubuntu)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2403", TAG+="snap_chromium_chromedriver"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2403", TAG+="snap_chromium_chromium"

# Generic Wootings for snap Chromium (Ubuntu)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="31e3", TAG+="snap_chromium_chromedriver"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="31e3", TAG+="snap_chromium_chromium"
EOF

echo "Udev rules created at $RULES_FILE"

# Reload and apply rules
echo "Reloading udev rules..."
sudo udevadm control --reload-rules && sudo udevadm trigger

sleep 1

# Check if any Wooting device is connected
VENDOR_ID="31e3"
DEVICE_PATH=$(for dev in /dev/hidraw*; do
  udevadm info -a -n "$dev" 2>/dev/null | grep -q "ATTRS{idVendor}==\"$VENDOR_ID\"" && echo "$dev" && break
done)

if [[ -n "$DEVICE_PATH" ]]; then
    echo "Wooting device detected at $DEVICE_PATH"
    ID_PRODUCT=$(udevadm info -a -n "$DEVICE_PATH" | grep 'ATTRS{idProduct}' | head -n1 | sed -E 's/.*"([0-9a-fA-F]+)".*/\1/')
    echo "Product ID: $ID_PRODUCT"
    echo "Current permissions:"
    ls -l "$DEVICE_PATH"
else
    echo "No Wooting device currently connected (this is OK)."
fi

echo ""
echo "Done! Udev rules are now configured for all Wooting keyboards."
echo "If the device is still not accessible, try unplugging and replugging the keyboard."