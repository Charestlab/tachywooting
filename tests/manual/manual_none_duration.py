#!/usr/bin/env python3
"""
Manual hardware script (not run by pytest/CI) for acquire_analog_values with
duration_before_threshold=None. Requires a physical Wooting keyboard.
Press 'C' key to trigger acquisition. Run directly: python tests/manual/manual_none_duration.py
"""
from tachywooting.wooting_utils import WOOTING_ACQUISITION


def main():
    print("\n" + "="*60)
    print("Test: acquire_analog_values with duration_before_threshold=None")
    print("="*60)
    
    # Initialize acquisition
    acq = WOOTING_ACQUISITION(
        threshold=0.6,
        max_pressure_start=0.3,
        backend="auto",
    )
    
    print("\n[1] Initializing keyboard...")
    acq.initialize_keyboard(verbose=True)
    
    print("\n[2] Setup logging...")
    acq.setup_logging(
        name="test_none_duration",
        path="/tmp",
        int_analog=2  # analog mode
    )
    
    print("\n[3] Ready to acquire!")
    print("    Press 'C' key slowly until threshold (0.6)...")
    print("    All samples from the start will be logged (no time limit before threshold)\n")
    
    # Acquire with duration_before_threshold=None
    data = acq.acquire_analog_values(
        target_keys=['C'],
        duration_after_threshold=0.5,
        duration_before_threshold=None,  # <<< None = log everything before threshold
        sampling_interval=1/1000,  # 1 kHz
        verbose=True,
    )
    
    print("\n[4] Acquisition completed!")
    
    # Extract data for key C
    trial_id = str(acq.trial - 1)  # last trial
    key_id = str(6)  # C = keycode 6
    
    if trial_id in data and key_id in data[trial_id]:
        serie = data[trial_id][key_id]
        n_samples = len(serie['position'])
        time_from_onset = serie['time_from_onset']
        position = serie['position']
        
        print("\n[5] Data summary:")
        print(f"    Total samples: {n_samples}")
        print(f"    Time span: {time_from_onset[0]:.4f}s to {time_from_onset[-1]:.4f}s")
        print(f"    Duration before threshold: {abs(time_from_onset[0]):.4f}s")
        print(f"    Position range: [{position.min():.3f}, {position.max():.3f}]")
        
        # Find threshold crossing
        threshold_idx = None
        for i, pos in enumerate(position):
            if pos >= 0.6:
                threshold_idx = i
                break
        
        if threshold_idx is not None:
            print(f"\n    Threshold crossed at sample {threshold_idx}/{n_samples}")
            print(f"    Samples before threshold: {threshold_idx}")
            print(f"    Samples after threshold: {n_samples - threshold_idx}")
        
        print("\n[6] First 10 samples:")
        for i in range(min(10, n_samples)):
            print(f"    [{i:3d}] t={time_from_onset[i]:8.4f}s  pos={position[i]:.4f}")
        
        if n_samples > 10:
            print(f"    ... ({n_samples - 10} more samples)")
    
    print("\n[7] Cleaning up...")
    acq.uninitialize_keyboard()
    
    print(f"\n[8] HDF5 file saved to: {acq.output_paths['hdf5']}")
    print("\n✓ Test completed successfully!\n")

if __name__ == "__main__":
    main()
