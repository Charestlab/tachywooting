"""Update vendored Wooting Analog SDK binaries from a GitHub release.

This is a maintainer tool. It downloads official Wooting release assets,
verifies SHA256 digests from GitHub release metadata when available, extracts
the archives, and copies the SDK files into ``tachywooting/libraries``.

It is intentionally not used at package install time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


REPO = "WootingKb/wooting-analog-sdk"
REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOT = REPO_ROOT / "tachywooting" / "libraries"


@dataclass(frozen=True)
class AssetPlan:
    platform: str
    asset_suffix: str
    target_dir: Path


ASSET_PLANS = [
    AssetPlan("darwin_arm64", "aarch64-apple-darwin.tar.gz", TARGET_ROOT / "darwin" / "arm64"),
    AssetPlan("darwin_x86_64", "x86_64-apple-darwin.tar.gz", TARGET_ROOT / "darwin" / "x86_64"),
    AssetPlan("linux", "x86_64-unknown-linux-gnu.tar.gz", TARGET_ROOT / "linux"),
    AssetPlan("windows", "x86_64-pc-windows-msvc.zip", TARGET_ROOT / "windows"),
]


KNOWN_SHA256 = {
    "wooting-analog-sdk-v0.9.1-aarch64-apple-darwin.tar.gz": (
        "c995ec9efc242dfa91b31bb0ce0e37ab0a62e93f3af04d2a921df246b105f40c"
    ),
    "wooting-analog-sdk-v0.9.1-x86_64-apple-darwin.tar.gz": (
        "6b603a8c4adc1708fee3fd874f82c4911174e554f52f9df11e6e5cb514241473"
    ),
    "wooting-analog-sdk-v0.9.1-x86_64-pc-windows-msvc.zip": (
        "27b3b868f4005018d3638e0f485942272134e1e09be1db1747ccc63f33fc187a"
    ),
    "wooting-analog-sdk-v0.9.1-x86_64-unknown-linux-gnu.tar.gz": (
        "8df8ae7ff41c46e57aa9f8a5fa52e1ed82cf88e5dc1b90693fbc87a6213d4a11"
    ),
}


EXCLUDED_TOP_LEVEL_ASSETS = {
    "debug",
    "VIRTUAL_KEYBOARD.md",
    "wooting-analog-virtual-control",
    "wooting-analog-virtual-control.exe",
}


REQUIRED_PATHS = {
    "darwin_arm64": [
        "includes/wooting-analog-sdk.h",
        "release/libwooting_analog_sdk_dist.dylib",
    ],
    "darwin_x86_64": [
        "includes/wooting-analog-sdk.h",
        "release/libwooting_analog_sdk_dist.dylib",
    ],
    "linux": [
        "includes/wooting-analog-sdk.h",
        "release/libwooting_analog_sdk_dist.so",
    ],
    "windows": [
        "includes/wooting-analog-sdk.h",
        "release/wooting_analog_sdk_dist.dll",
        "release/wooting_analog_sdk_dist.dll.lib",
    ],
}

EXPECTED_ARCH_MARKERS = {
    "darwin_arm64": {
        "release/libwooting_analog_sdk_dist.dylib": "arm64",
    },
    "darwin_x86_64": {
        "release/libwooting_analog_sdk_dist.dylib": "x86_64",
    },
}


def github_request(url: str) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wooting-analog-sdk-updater",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def read_json(url: str) -> dict:
    with urllib.request.urlopen(github_request(url)) as response:
        return json.loads(response.read().decode("utf-8"))


VERSION_PATTERN = re.compile(r"v?\d+\.\d+\.\d+")


def parse_version_arg(value: str) -> str:
    """Parse --version, accepting a bare version, a tag, or a release URL/anchor.

    Examples that all resolve to "0.9.1":
      --version=0.9.1
      --version=v0.9.1
      --version=https://github.com/WootingKb/wooting-analog-sdk/releases/tag/v0.9.1
      --version=https://github.com/WootingKb/wooting-analog-sdk/releases#release-v0.9.1
    """
    match = VERSION_PATTERN.search(value)
    if not match:
        raise argparse.ArgumentTypeError(f"Could not find a version (e.g. v0.9.1) in {value!r}")
    return match.group(0)


def normalize_version(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def release_tag(version: str) -> str:
    version = normalize_version(version)
    return f"v{version}"


def find_asset(release: dict, version: str, suffix: str) -> dict:
    expected = f"wooting-analog-sdk-v{normalize_version(version)}-{suffix}"
    for asset in release.get("assets", []):
        if asset.get("name") == expected:
            return asset
    names = ", ".join(asset.get("name", "") for asset in release.get("assets", []))
    raise RuntimeError(f"Could not find release asset {expected!r}. Available assets: {names}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_asset(asset: dict, dest: Path) -> None:
    url = asset["browser_download_url"]
    with urllib.request.urlopen(github_request(url)) as response, dest.open("wb") as file:
        shutil.copyfileobj(response, file)

    digest = asset.get("digest")
    expected = None
    if digest and digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1]
    else:
        expected = KNOWN_SHA256.get(asset["name"])

    if expected:
        actual = sha256_file(dest)
        if actual != expected:
            raise RuntimeError(
                f"SHA256 mismatch for {asset['name']}: expected {expected}, got {actual}"
            )
    else:
        print(f"Warning: no SHA256 digest available for {asset['name']}")


def safe_extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive) as tar:
        root = dest.resolve()
        for member in tar.getmembers():
            member_path = (dest / member.name).resolve()
            if not str(member_path).startswith(str(root)):
                raise RuntimeError(f"Refusing unsafe tar path: {member.name}")
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


def extract_archive(archive: Path, dest: Path) -> None:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(dest)
    else:
        safe_extract_tar(archive, dest)


def archive_root(extracted_root: Path) -> Path:
    children = [path for path in extracted_root.iterdir() if path.name != "__MACOSX"]
    dirs = [path for path in children if path.is_dir()]
    if len(children) == 1 and dirs:
        return dirs[0]
    return extracted_root


def copy_platform_tree(platform: str, extracted_root: Path, target_dir: Path) -> list[str] | None:
    """Vendor one platform's SDK files, or None if the download is unusable."""
    source_root = archive_root(extracted_root)
    missing = [path for path in REQUIRED_PATHS[platform] if not (source_root / path).is_file()]
    if missing:
        raise RuntimeError(
            f"{platform} archive is missing required SDK files: {', '.join(missing)}"
        )
    try:
        check_arch_mismatches(platform, source_root)
    except RuntimeError as e:
        print(f"Skipping {platform}: {e}\nKeeping existing files in {target_dir}.")
        return None

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    copied = []
    for source in source_root.iterdir():
        if source.name == "__MACOSX" or source.name in EXCLUDED_TOP_LEVEL_ASSETS:
            continue
        target = target_dir / source.name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        copied.append(source.name)

    fix_macos_install_names(platform, target_dir)

    return sorted(copied)


def check_arch_mismatches(platform: str, source_root: Path) -> None:
    """Abort if an official archive's Mach-O architecture doesn't match its name."""
    expected_markers = EXPECTED_ARCH_MARKERS.get(platform)
    if not expected_markers:
        return

    for relative_path, expected_marker in expected_markers.items():
        path = source_root / relative_path
        result = subprocess.run(["file", str(path)], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            continue  # `file` unavailable; nothing we can verify

        description = result.stdout.strip().split(":", 1)[-1]
        if expected_marker not in description:
            raise RuntimeError(
                f"{platform}: expected {expected_marker} for {relative_path}, "
                f"but file reports: {description}. This is an upstream Wooting "
                f"SDK packaging bug -- do not vendor this asset."
            )


def fix_macos_install_names(platform: str, target_dir: Path) -> None:
    """Make macOS vendored dylibs relocatable from the Python extension rpath."""
    if not platform.startswith("darwin"):
        return
    install_name_tool = shutil.which("install_name_tool")
    if not install_name_tool:
        print("Warning: install_name_tool not available; macOS dylib IDs were not rewritten")
        return

    for dylib in (target_dir / "release").glob("libwooting_analog_sdk_dist.dylib"):
        subprocess.run(
            [
                install_name_tool,
                "-id",
                "@rpath/libwooting_analog_sdk_dist.dylib",
                str(dylib),
            ],
            check=True,
        )


def read_manifest_platforms(path: Path) -> dict[str, dict]:
    """Load per-platform manifest entries, migrating the old flat schema if needed.

    The manifest used to have a single top-level "version"/"source" applied to
    every platform. That breaks down once a platform's update is skipped (e.g.
    an upstream arch-mismatch bug) and it stays on an older SDK version than
    its siblings, so each platform now tracks its own version/source/files.
    """
    if not path.is_file():
        return {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    platforms = existing.get("platforms", {})
    old_version = existing.get("version")
    old_source = existing.get("source")

    migrated = {}
    for platform, entry in platforms.items():
        if isinstance(entry, list):
            migrated[platform] = {"version": old_version, "source": old_source, "files": entry}
        else:
            migrated[platform] = entry
    return migrated


def write_manifest(version: str, copied: dict[str, list[str]]) -> None:
    path = TARGET_ROOT / "VERSION.json"
    platforms = read_manifest_platforms(path)

    source = f"https://github.com/{REPO}/releases/tag/{release_tag(version)}"
    for platform, files in copied.items():
        platforms[platform] = {
            "version": normalize_version(version),
            "source": source,
            "files": files,
        }

    manifest = {"platforms": platforms}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update(version: str) -> None:
    release_url = f"https://api.github.com/repos/{REPO}/releases/tags/{release_tag(version)}"
    release = read_json(release_url)
    copied_by_platform: dict[str, list[str]] = {}

    with tempfile.TemporaryDirectory(prefix="wooting-sdk-") as tmp:
        tmp_dir = Path(tmp)
        for plan in ASSET_PLANS:
            asset = find_asset(release, version, plan.asset_suffix)
            archive = tmp_dir / asset["name"]
            extract_dir = tmp_dir / f"extract-{plan.platform}"

            print(f"Downloading {asset['name']}...")
            download_asset(asset, archive)
            extract_dir.mkdir()
            extract_archive(archive, extract_dir)

            copied = copy_platform_tree(plan.platform, extract_dir, plan.target_dir)
            if copied is None:
                continue  # unusable upstream asset; existing vendored files kept as-is
            copied_by_platform[plan.platform] = copied
            print(f"Updated {plan.target_dir}: {', '.join(copied) if copied else 'no files copied'}")

    write_manifest(version, copied_by_platform)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default="0.9.1",
        type=parse_version_arg,
        help=(
            "Wooting SDK version to vendor. Accepts a bare version (0.9.1), a tag "
            "(v0.9.1), or a GitHub release URL/anchor, e.g. "
            "https://github.com/WootingKb/wooting-analog-sdk/releases/tag/v0.9.1 or "
            "https://github.com/WootingKb/wooting-analog-sdk/releases#release-v0.9.1"
        ),
    )
    args = parser.parse_args()
    update(args.version)


if __name__ == "__main__":
    main()
