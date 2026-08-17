import os
import re
import sys

import pytest

import tachywooting
from tachywooting import (
    WOOTING_ACQUISITION,
    convert_char_to_keycode,
    package_setup,
    wooting_interface_builder,
)


def test_import_does_not_require_built_native_interface():
    assert hasattr(tachywooting, "build_interface")
    assert hasattr(tachywooting, "delete_interface")


def test_convert_char_to_keycode_round_trip():
    assert convert_char_to_keycode(["A", "Esc", "Space"]) == [4, 41, 44]
    assert convert_char_to_keycode([4, 41, 44]) == ["A", "Esc", "Space"]


def test_acquisition_requires_native_interface_when_missing():
    if tachywooting.ffi is not None and tachywooting.lib is not None:
        pytest.skip("native interface is already built in this environment")

    with pytest.raises(RuntimeError, match="wooting-build-interface"):
        WOOTING_ACQUISITION()


def test_interface_console_scripts_target_package_setup():
    pyproject_text = open("pyproject.toml", encoding="utf-8").read()

    assert re.search(
        r'^wooting-build-interface\s*=\s*"tachywooting\.package_setup:run_post_install"$',
        pyproject_text,
        re.MULTILINE,
    )
    assert re.search(
        r'^wooting-delete-interface\s*=\s*"tachywooting\.package_setup:main_delete_interface"$',
        pyproject_text,
        re.MULTILINE,
    )


def test_package_does_not_expose_tachypy_feedback_extra_or_scripts():
    pyproject_text = open("pyproject.toml", encoding="utf-8").read()

    assert "[project.optional-dependencies]" in pyproject_text
    assert "tachywooting[tachypy]" not in pyproject_text
    assert "tachypy>=" not in pyproject_text
    assert "wooting-visual-fixation-demo" not in pyproject_text
    assert "wooting-mini-bw-experiment" not in pyproject_text
    assert not hasattr(WOOTING_ACQUISITION, "wait_light_press_visual")


def test_run_post_install_calls_setup_steps_in_order(monkeypatch):
    calls = []

    monkeypatch.setattr(package_setup, "setup_permissions", lambda: calls.append("permissions"))
    monkeypatch.setattr(package_setup, "build_interface_if_needed", lambda: calls.append("build"))
    monkeypatch.setattr(package_setup, "install_plugins", lambda: calls.append("plugins"))
    monkeypatch.setattr(package_setup, "apply_macos_gatekeeper", lambda: calls.append("gatekeeper"))

    package_setup.run_post_install()

    assert calls == ["permissions", "build", "plugins", "gatekeeper"]


def test_main_delete_interface_removes_plugins_by_default(monkeypatch):
    calls = []

    monkeypatch.setattr(sys, "argv", ["wooting-delete-interface"])
    monkeypatch.setattr(
        package_setup,
        "delete_interface",
        lambda cleanup_plugins=True: calls.append(cleanup_plugins),
    )

    package_setup.main_delete_interface()

    assert calls == [True]


def test_main_delete_interface_can_keep_plugins(monkeypatch):
    calls = []

    monkeypatch.setattr(sys, "argv", ["wooting-delete-interface", "--no-plugins"])
    monkeypatch.setattr(
        package_setup,
        "delete_interface",
        lambda cleanup_plugins=True: calls.append(cleanup_plugins),
    )

    package_setup.main_delete_interface()

    assert calls == [False]


@pytest.mark.parametrize(
    ("system", "script_attr"),
    [
        ("Darwin", "_PERM_MAC_SH"),
        ("Linux", "_PERM_LINUX_SH"),
    ],
)
def test_setup_permissions_runs_platform_script(monkeypatch, system, script_attr):
    calls = []
    expected_script = getattr(package_setup, script_attr)

    monkeypatch.setattr(package_setup, "_compiled_interface_present", lambda: False)
    monkeypatch.setattr(package_setup.platform, "system", lambda: system)
    monkeypatch.setattr(package_setup.os.path, "isfile", lambda path: path == expected_script)
    monkeypatch.setattr(package_setup, "_make_executable", lambda path: calls.append(("chmod", path)))
    monkeypatch.setattr(
        package_setup.subprocess,
        "run",
        lambda cmd, check, cwd: calls.append(("run", cmd, check, cwd)),
    )

    package_setup.setup_permissions()

    assert calls == [
        ("chmod", expected_script),
        ("run", ["/bin/bash", expected_script], True, package_setup._PKG_DIR),
    ]


def test_setup_permissions_skips_windows(monkeypatch):
    calls = []

    monkeypatch.setattr(package_setup, "_compiled_interface_present", lambda: False)
    monkeypatch.setattr(package_setup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(package_setup, "_make_executable", lambda path: calls.append(path))
    monkeypatch.setattr(
        package_setup.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    package_setup.setup_permissions()

    assert calls == []


@pytest.mark.parametrize(
    ("system", "expected_native_libs"),
    [
        ("windows", []),
        ("linux", []),
        ("darwin", ["wooting_analog_sdk_dist"]),
    ],
)
def test_interface_builder_links_expected_platform_libraries(
    monkeypatch,
    system,
    expected_native_libs,
):
    monkeypatch.setattr(wooting_interface_builder, "SYSTEM", system)

    libraries = wooting_interface_builder.get_link_libraries(["example_system_lib"])

    assert libraries == expected_native_libs + ["example_system_lib"]


def test_interface_builder_uses_windows_import_library_path(monkeypatch, tmp_path):
    monkeypatch.setattr(wooting_interface_builder, "SYSTEM", "windows")

    cfg = wooting_interface_builder.get_platform_config(
        str(tmp_path / "release"),
        str(tmp_path / "includes"),
    )

    assert cfg["extra_link_args"] == [
        str(tmp_path / "release" / "wooting_analog_sdk_dist.dll.lib")
    ]


def test_interface_builder_uses_linux_shared_library_path(monkeypatch, tmp_path):
    monkeypatch.setattr(wooting_interface_builder, "SYSTEM", "linux")

    cfg = wooting_interface_builder.get_platform_config(
        str(tmp_path / "release"),
        str(tmp_path / "includes"),
    )

    assert str(tmp_path / "release" / "libwooting_analog_sdk_dist.so") in cfg[
        "extra_link_args"
    ]
    assert "-Wl,-rpath,$ORIGIN/../libraries/linux/release" in cfg["extra_link_args"]


def test_windows_ffibuilder_does_not_request_missing_sdk_lib(monkeypatch, tmp_path):
    platform_dir = tmp_path / "libraries" / "windows"
    include_dir = platform_dir / "includes"
    release_dir = platform_dir / "release"
    include_dir.mkdir(parents=True)
    release_dir.mkdir()
    (include_dir / "wooting-analog-sdk.h").write_text(
        "int wooting_analog_initialise(void);\n",
        encoding="utf-8",
    )

    captured = {}

    class FakeFFI:
        def cdef(self, header_code):
            captured["header_code"] = header_code

        def set_source(self, module_name, source, **kwargs):
            captured["module_name"] = module_name
            captured["source"] = source
            captured.update(kwargs)

    monkeypatch.setattr(wooting_interface_builder, "SYSTEM", "windows")
    monkeypatch.setattr(wooting_interface_builder, "LIBRARIES_DIR", str(tmp_path / "libraries"))
    monkeypatch.setattr(wooting_interface_builder, "FFI", FakeFFI)

    wooting_interface_builder.create_ffibuilder("test_wooting_interface")

    assert captured["source"] == "#include <wooting-analog-sdk.h>\n"
    assert captured["library_dirs"] == [str(release_dir)]
    assert "wooting_analog_sdk" not in captured["libraries"]
    assert "wooting_analog_sdk_dist" not in captured["libraries"]
    assert str(release_dir / "wooting_analog_sdk_dist.dll.lib") in captured["extra_link_args"]


def test_linux_ffibuilder_links_release_shared_library(monkeypatch, tmp_path):
    platform_dir = tmp_path / "libraries" / "linux"
    include_dir = platform_dir / "includes"
    release_dir = platform_dir / "release"
    include_dir.mkdir(parents=True)
    release_dir.mkdir()
    (include_dir / "wooting-analog-sdk.h").write_text(
        "int wooting_analog_initialise(void);\n",
        encoding="utf-8",
    )

    captured = {}

    class FakeFFI:
        def cdef(self, header_code):
            captured["header_code"] = header_code

        def set_source(self, module_name, source, **kwargs):
            captured["module_name"] = module_name
            captured["source"] = source
            captured.update(kwargs)

    monkeypatch.setattr(wooting_interface_builder, "SYSTEM", "linux")
    monkeypatch.setattr(wooting_interface_builder, "LIBRARIES_DIR", str(tmp_path / "libraries"))
    monkeypatch.setattr(wooting_interface_builder, "FFI", FakeFFI)

    wooting_interface_builder.create_ffibuilder("test_wooting_interface")

    assert captured["library_dirs"] == [str(release_dir)]
    assert "wooting_analog_sdk_dist" not in captured["libraries"]
    assert str(release_dir / "libwooting_analog_sdk_dist.so") in captured["extra_link_args"]


def test_interface_builder_uses_upstream_include_and_release_dirs(tmp_path):
    platform_dir = tmp_path / "darwin" / "arm64"
    include_dir = platform_dir / "includes"
    release_dir = platform_dir / "release"
    include_dir.mkdir(parents=True)
    release_dir.mkdir()

    assert wooting_interface_builder.get_include_dir(str(platform_dir)) == str(include_dir)
    assert wooting_interface_builder.get_binary_dir(str(platform_dir)) == str(release_dir)


def test_interface_builder_falls_back_to_flat_vendor_layout(tmp_path):
    platform_dir = tmp_path / "linux"
    platform_dir.mkdir()

    assert wooting_interface_builder.get_include_dir(str(platform_dir)) == str(platform_dir)
    assert wooting_interface_builder.get_binary_dir(str(platform_dir)) == str(platform_dir)


def test_install_plugins_uses_release_directory_without_required_plugin(monkeypatch, tmp_path):
    release_dir = tmp_path / "libraries" / "linux" / "release"
    release_dir.mkdir(parents=True)
    sdk_file = release_dir / "libwooting_analog_sdk_dist.so"
    sdk_file.write_bytes(b"sdk")
    calls = []

    monkeypatch.setattr(package_setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(package_setup, "_LIBRARIES_DIR", str(tmp_path / "libraries"))
    monkeypatch.setattr(package_setup.os.path, "exists", lambda path: path == str(sdk_file))
    monkeypatch.setattr(package_setup.os.path, "isdir", lambda path: path == str(release_dir))
    monkeypatch.setattr(
        package_setup.subprocess,
        "run",
        lambda cmd, check=False, **kwargs: calls.append((cmd, check, kwargs)),
    )

    package_setup.install_plugins()

    cp_calls = [call for call in calls if call[0][:2] == ["sudo", "cp"]]
    assert len(cp_calls) == 1
    assert cp_calls[0][0][2] == str(sdk_file)
    assert os.path.normpath(cp_calls[0][0][3]) == os.path.normpath(
        "/usr/local/lib/libwooting_analog_sdk_dist.so"
    )
    assert cp_calls[0][1:] == (True, {})
    assert not any("WootingAnalogPlugins" in " ".join(call[0]) for call in calls)


def test_macos_gatekeeper_uses_release_directory(monkeypatch, tmp_path):
    release_dir = tmp_path / "libraries" / "darwin" / "arm64" / "release"
    release_dir.mkdir(parents=True)
    sdk_file = release_dir / "libwooting_analog_sdk.dylib"
    sdk_dist_file = release_dir / "libwooting_analog_sdk_dist.dylib"
    sdk_file.write_bytes(b"sdk")
    sdk_dist_file.write_bytes(b"dist")
    calls = []

    monkeypatch.setattr(package_setup.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(package_setup.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(package_setup, "_PKG_DIR", str(tmp_path))
    monkeypatch.setattr(
        package_setup.subprocess,
        "run",
        lambda cmd, check=False: calls.append((cmd, check)),
    )

    package_setup.apply_macos_gatekeeper()

    assert (["xattr", "-dr", "com.apple.quarantine", str(release_dir)], False) in calls
    assert (["codesign", "--force", "--sign", "-", str(sdk_file)], False) in calls
    assert (["codesign", "--force", "--sign", "-", str(sdk_dist_file)], False) in calls


def test_removal_tracking_statistics():
    tracker = WOOTING_ACQUISITION.__new__(WOOTING_ACQUISITION)
    tracker.total_trials = 0
    tracker.removal_trials = 0
    tracker.removal_trial_indices = []
    tracker._removal_trial_index_set = set()
    tracker.current_removal_streak = 0
    tracker.max_removal_streak = 0
    tracker.last_trial_had_removal = False

    tracker._record_trial_removal_status(1, True)
    tracker._record_trial_removal_status(2, True)
    tracker._record_trial_removal_status(3, False)
    tracker._record_trial_removal_status(4, True)

    assert tracker.total_trials == 4
    assert tracker.removal_trials == 3
    assert tracker.removal_trial_indices == [1, 2, 4]
    assert tracker.removal_trial_proportion == 0.75
    assert tracker.current_removal_streak == 1
    assert tracker.max_removal_streak == 2
    assert tracker.trial_contains_removal(2)
    assert not tracker.trial_contains_removal(3)


def test_removal_limit_helpers():
    tracker = WOOTING_ACQUISITION.__new__(WOOTING_ACQUISITION)
    tracker.total_trials = 0
    tracker.removal_trials = 0
    tracker.removal_trial_indices = []
    tracker._removal_trial_index_set = set()
    tracker.current_removal_streak = 2
    tracker.max_removal_streak = 2
    tracker.last_trial_had_removal = True

    assert tracker.reached_consecutive_removal_limit(2)
    assert not tracker.reached_consecutive_removal_limit(3)

    tracker.removal_trials = 5
    assert tracker.reached_total_removal_limit(5)
    assert not tracker.reached_total_removal_limit(3)

    with pytest.raises(ValueError, match="positive"):
        tracker.reached_consecutive_removal_limit(0)
    with pytest.raises(ValueError, match="positive"):
        tracker.reached_total_removal_limit(0)


def test_snapshot_finger_removal_detection():
    snapshot = [
        {"key": 4, "position": 0.8},
        {"key": 5, "position": 0.0},
    ]

    assert WOOTING_ACQUISITION._snapshot_has_finger_removal(snapshot, 0.01)
    assert not WOOTING_ACQUISITION._snapshot_has_finger_removal(snapshot, 0.0)


def test_pre_threshold_missing_contact_flags_trial_removal():
    tracker = WOOTING_ACQUISITION.__new__(WOOTING_ACQUISITION)
    tracker.threshold = 0.8
    tracker.finger_present_threshold = 0.01
    tracker.trial = 1
    tracker._to_keycodes = lambda keys: [1, 2]
    tracker._wait_until_next_tick = lambda next_t: None
    tracker._last_trial_start_perf_ns = None
    tracker._last_stim_on_clock = None

    samples = [
        {1: 0.0, 2: 0.5},  # pre-threshold missing contact
        {1: 0.9, 2: 0.5},  # trigger
        {1: 0.9, 2: 0.5},
    ]

    def read_positions(target_codes):
        if samples:
            return samples.pop(0)
        return {1: 0.9, 2: 0.5}

    tracker._read_positions_for_targets = read_positions

    tracker._acquire_raw_values(
        target_keys=["z", "c"],
        duration_after_threshold=0.000001,
        duration_before_threshold=0.1,
        sampling_interval=0.000001,
    )

    assert tracker._pending_trial_had_removal is True


def test_post_threshold_missing_contact_is_optional_for_trial_removal():
    def make_tracker(count_post_threshold_removals):
        tracker = WOOTING_ACQUISITION.__new__(WOOTING_ACQUISITION)
        tracker.threshold = 0.8
        tracker.finger_present_threshold = 0.01
        tracker.count_post_threshold_removals = count_post_threshold_removals
        tracker.trial = 1
        tracker._to_keycodes = lambda keys: [1, 2]
        tracker._wait_until_next_tick = lambda next_t: None
        tracker._last_trial_start_perf_ns = None
        tracker._last_stim_on_clock = None
        samples = [
            {1: 0.5, 2: 0.5},
            {1: 0.9, 2: 0.5},  # trigger, all fingers present
            {1: 0.9, 2: 0.0},  # post-threshold missing contact
        ]

        def read_positions(target_codes):
            if samples:
                return samples.pop(0)
            return {1: 0.9, 2: 0.5}

        tracker._read_positions_for_targets = read_positions
        return tracker

    default_tracker = make_tracker(False)
    default_tracker._acquire_raw_values(
        target_keys=["z", "c"],
        duration_after_threshold=0.000001,
        duration_before_threshold=0.1,
        sampling_interval=0.000001,
    )
    assert default_tracker._pending_trial_had_removal is False

    post_tracker = make_tracker(True)
    post_tracker._acquire_raw_values(
        target_keys=["z", "c"],
        duration_after_threshold=0.000001,
        duration_before_threshold=0.1,
        sampling_interval=0.000001,
    )
    assert post_tracker._pending_trial_had_removal is True
