"""
Wooting Analog Keyboard Demo (CLI)

This module provides a command-line tool to demonstrate analog key
functionality by reading and displaying the pressure value of a key
in real-time. It shows a colored progress bar whose color depends on
the analog value, and appends (in dim text) the corresponding uint8
value (0–255) as a postfix.

Dependencies:
    - tqdm
    - rich
    - tachywooting (your own wrapper around the Wooting Analog SDK)

Usage examples:
    python -m wooting_demo
    python -m wooting_demo -k A
    python -m wooting_demo -k SPACE --interval 0.05
    python -m wooting_demo --threshold 50
"""

import signal
import sys
import time
from typing import Optional

try:
    from rich.console import Console
    from tqdm import tqdm
except ImportError:
    print('Error: Missing CLI dependencies. Install them with: pip install "tachywooting"')
    sys.exit(1)

from tachywooting import convert_char_to_keycode, lib
from tachywooting.wooting_utils import WOOTING_ACQUISITION

# Global flag for graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    """
    Handle interrupt signals gracefully by setting the global shutdown flag.
    """
    global _shutdown_requested
    _shutdown_requested = True


def _value_to_rainbow_256(value: float, threshold: Optional[float] = None) -> int:
    """
    Convert an analog value (0.0–1.0) to a 256-color ANSI code.

    If a threshold is provided:
        - Below threshold: bright red
        - At or above threshold: bright green

    Without threshold:
        - The color smoothly interpolates from dark red → red → yellow → green.

    Args:
        value: Analog value between 0.0 and 1.0.
        threshold: Optional threshold in normalized units (0.0–1.0).

    Returns:
        An integer ANSI 256-color code in the 16–231 RGB range.
    """
    # No pressure: use white so the bar is visible but neutral
    if value <= 0.0:
        return 231  # white

    # Threshold mode: light red before threshold, green after
    if threshold is not None:
        if value < threshold:
            return 196  # bright red
        else:
            return 46   # bright green

    # Clamp to [0, 1]
    value = max(0.0, min(1.0, value))

    # Interpolate through: dark red -> red -> yellow -> green
    if value < 0.33:
        # Dark red to red
        t = value / 0.33
        r = 0.5 + 0.5 * t
        g = 0.0
        b = 0.0
    elif value < 0.66:
        # Red to yellow
        t = (value - 0.33) / 0.33
        r = 1.0
        g = t
        b = 0.0
    else:
        # Yellow to green
        t = (value - 0.66) / 0.34
        r = 1.0 - t
        g = 1.0
        b = 0.0

    # Convert RGB [0,1] → indices [0,5]
    r_idx = int(r * 5.999)
    g_idx = int(g * 5.999)
    b_idx = int(b * 5.999)

    r_idx = max(0, min(5, r_idx))
    g_idx = max(0, min(5, g_idx))
    b_idx = max(0, min(5, b_idx))

    # RGB part of the 256-color palette: 16 + 36*r + 6*g + b
    ansi_color = 16 + 36 * r_idx + 6 * g_idx + b_idx
    return ansi_color


def _get_rainbow_bar_format(value: float, threshold: Optional[float] = None) -> str:
    """
    Build an ANSI escape sequence for the bar color based on the analog value.

    Args:
        value: Analog value between 0.0 and 1.0.
        threshold: Optional normalized threshold (0.0–1.0).

    Returns:
        A string containing the ANSI escape code to set the foreground color.
    """
    color_code = _value_to_rainbow_256(value, threshold)
    return f"\033[38;5;{color_code}m"


def _to_uint8(value: float) -> int:
    """
    Convert a normalized analog value (0.0–1.0) to uint8 (0–255).

    Args:
        value: Analog value between 0.0 and 1.0.

    Returns:
        An integer in range 0–255.
    """
    value = max(0.0, min(1.0, value))
    return int(round(value * 255.0))


def demo_key(key: str = "C", update_interval: float = 0.01, threshold: Optional[float] = None):
    """
    Demonstrate analog key reading with visual feedback.

    The function:
        - Initializes the Wooting keyboard.
        - Monitors a single key in real time.
        - Displays a colored progress bar whose color depends on the
          analog value (rainbow gradient or threshold mode).
        - Appends in dim text the current uint8 pressure value (0–255)
          as a tqdm postfix, right after the elapsed time.

    Args:
        key: Key to monitor (e.g., "C", "A", "SPACE"). Default is "C".
        update_interval: Time between updates in seconds. Default is 0.01 (100 Hz).
        threshold: Optional threshold in percentage (0–100). If provided,
                   the bar color switches from red to green at this point.
    """
    console = Console()
    if lib is None:
        console.print("[red]Error:[/red] Native interface is not built. Run [bold]wooting-build-interface[/bold].")
        sys.exit(1)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Convert key character/name to keycode using your helper
    try:
        keycodes = convert_char_to_keycode([key.upper()])
        if not keycodes or keycodes[0] == 0:
            console.print(f"[red]Error:[/red] Invalid key '{key}'. Please use a valid key (A-Z, 0-9, etc.)")
            sys.exit(1)
        keycode = keycodes[0]
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to convert key '{key}': {e}")
        sys.exit(1)

    # Header
    console.print("\n[bold cyan]Wooting Analog Keyboard Demo[/bold cyan]")
    console.print(f"[dim]Monitoring key: [bold]{key.upper()}[/bold][/dim]\n")

    # Initialize keyboard acquisition
    try:
        acquisition = WOOTING_ACQUISITION()
        acquisition.initialize_keyboard(verbose=True)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to initialize keyboard: {e}")
        console.print("[dim]Make sure your Wooting keyboard is connected and permissions are set up.[/dim]")
        sys.exit(1)

    console.print("\n[green]✓[/green] Keyboard initialized successfully!")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    # Optional threshold: convert from percent [0,100] to normalized [0,1]
    threshold_normalized = None
    if threshold is not None:
        if threshold < 0 or threshold > 100:
            console.print("[red]Error:[/red] Threshold must be between 0 and 100")
            sys.exit(1)
        threshold_normalized = threshold / 100.0
        threshold_uint8 = int(threshold_normalized * 255)
        console.print(f"[dim]Threshold: {threshold:.1f}% ({threshold_uint8} uint8)[/dim]\n")

    # Progress bar setup
    desc_template = f"Key '{key.upper()}' Pressure"
    desc_width = max(len(desc_template), 25)
    reset_code = "\033[0m"
    initial_color = _get_rainbow_bar_format(0.0, threshold_normalized)

    # NOTE: include {postfix} at the end so tqdm can display our uint8 string.
    pbar = tqdm(
        total=100,
        desc=desc_template.ljust(desc_width),
        unit="%",
        bar_format=(
            f"{{desc}}{initial_color}{{bar}}{reset_code}"
            "| {n:.1f}%/{total}% [{elapsed}] {postfix}"
        ),
        ncols=100,
        dynamic_ncols=False,
        leave=False,
    )

    # ANSI attributes for dim and reset
    DIM = "\033[2m"
    RESET = "\033[0m"

    try:
        while not _shutdown_requested:
            # Read analog value from the Wooting SDK
            value = lib.wooting_analog_read_analog(keycode)

            # Handle error codes (negative values)
            if value < 0:
                pbar.set_description(desc_template.ljust(desc_width))
                error_color = "\033[38;5;196m"  # bright red
                reset_code = "\033[0m"
                pbar.bar_format = (
                    f"{{desc}}{error_color}{{bar}}{reset_code}"
                    "| {n:.1f}%/{total}% [{elapsed}] {postfix}"
                )
                err_code = int(value)
                pbar.set_postfix_str(f"{DIM}Error {err_code}{RESET}")
                pbar.refresh()
                time.sleep(update_interval)
                continue

            # Update progress bar percentage
            percentage = value * 100.0
            pbar.n = percentage

            # Update bar color
            bar_color = _get_rainbow_bar_format(value, threshold_normalized)
            reset_code = "\033[0m"
            pbar.bar_format = (
                f"{{desc}}{bar_color}{{bar}}{reset_code}"
                "| {n:.1f}%/{total}% [{elapsed}] {postfix}"
            )

            # Compute uint8 value and set it as dim postfix
            uint8_val = _to_uint8(value)
            postfix = f"{DIM}{uint8_val:3d} uint8{RESET}"
            pbar.set_postfix_str(postfix)

            # Refresh display
            pbar.refresh()
            time.sleep(update_interval)

    except KeyboardInterrupt:
        # Normal exit on Ctrl+C
        pass
    finally:
        # Clean up progress bar and uninitialize keyboard
        pbar.close()
        try:
            acquisition.uninitialize_keyboard()
            console.print("\n[green]✓[/green] Keyboard uninitialized. Goodbye!")
        except Exception as e:
            console.print(f"\n[yellow]Warning:[/yellow] Error during cleanup: {e}")


def main():
    """
    Entry point for the CLI.

    Parses command-line arguments and starts the demo.
    """
    print("\n" * 3)
    print(r"""
   ████████╗ █████╗  ██████╗██╗  ██╗██╗   ██╗██╗    ██╗ ██████╗       
   ╚══██╔══╝██╔══██╗██╔════╝██║  ██║╚██╗ ██╔╝██║    ██║██╔════╝       
      ██║   ███████║██║     ███████║ ╚████╔╝ ██║ █╗ ██║██║  ███╗      
      ██║   ██╔══██║██║     ██╔══██║  ╚██╔╝  ██║███╗██║██║   ██║      
      ██║   ██║  ██║╚██████╗██║  ██║   ██║   ╚███╔███╔╝╚██████╔╝      
      ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝   ╚═╝    ╚══╝╚══╝  ╚═════╝       
                                                                      
                         Analog Keyboard Demo                         
""")
    print("\n" * 3)

    
    import argparse

    parser = argparse.ArgumentParser(
        description="Wooting Analog Keyboard Demo - Real-time key pressure visualization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                  # Monitor 'C' key (default)
  %(prog)s -k A             # Monitor 'A' key
  %(prog)s -k SPACE         # Monitor spacebar
  %(prog)s -i 0.05          # Update every 50ms (slower)
  %(prog)s --threshold=50   # Threshold at 50%%
        """,
    )

    parser.add_argument(
        "-k", "--key",
        type=str,
        default="C",
        help="Key to monitor (default: C)",
    )

    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=0.01,
        help="Update interval in seconds (default: 0.01 = 100 Hz)",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "Threshold in percentage (0-100). "
            "If set, the bar is bright red below the threshold and bright green above it."
        ),
    )

    args = parser.parse_args()

    try:
        demo_key(key=args.key, update_interval=args.interval, threshold=args.threshold)
    except Exception as e:
        console = Console()
        console.print(f"[red]Fatal error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
