#!/usr/bin/env python3
"""
Manual hardware script (not run by pytest/CI) for threshold metadata logging
with multiple keys. Requires a physical Wooting keyboard.
Run directly: python tests/manual/manual_threshold_metadata.py
"""
import h5py

from tachywooting.wooting_utils import WOOTING_ACQUISITION


def main():
    print("\n" + "="*70)
    print("Test: Threshold metadata (time + key) with multiple target keys")
    print("="*70)
    
    acq = WOOTING_ACQUISITION(threshold=0.6, max_pressure_start=0.3)
    acq.initialize_keyboard(verbose=True)
    acq.setup_logging(name='test_threshold_metadata', path='/tmp', int_analog=2)
    
    print("\n[Trial 1] Press 'Z' key to threshold (0.6)...")
    acq.acquire_analog_values(
        ['Z', 'C'],  # monitoring both Z and C
        duration_after_threshold=0.3,
        duration_before_threshold=0.1,
        sampling_interval=1/1000
    )
    
    print("\n[Trial 2] Press 'C' key to threshold (0.6)...")
    acq.acquire_analog_values(
        ['Z', 'C'],  # monitoring both Z and C
        duration_after_threshold=0.3,
        duration_before_threshold=0.1,
        sampling_interval=1/1000
    )
    
    acq.uninitialize_keyboard()
    
    # Read and display metadata
    print("\n" + "="*70)
    print("HDF5 Metadata:")
    print("="*70)
    
    with h5py.File('/tmp/test_threshold_metadata.hdf5', 'r') as f:
        for trial_name in sorted(f['trials'].keys()):
            trial = f['trials'][trial_name]
            print(f"\n{trial_name}:")
            
            attrs = dict(trial.attrs)
            
            # Decode bytes
            for k, v in attrs.items():
                if isinstance(v, bytes):
                    attrs[k] = v.decode('utf-8')
            
            threshold = attrs.get('threshold', 'N/A')
            threshold_time = attrs.get('threshold_time', 'N/A')
            threshold_key = attrs.get('threshold_key', 'N/A')
            
            print(f"  threshold:      {threshold}")
            print(f"  threshold_time: {threshold_time:.6f}s" if isinstance(threshold_time, (int, float)) else f"  threshold_time: {threshold_time}")
            print(f"  threshold_key:  {threshold_key}", end="")
            
            # Convert keycode to key name
            if isinstance(threshold_key, (int, float)):
                from tachywooting.wooting_utils import convert_char_to_keycode
                key_name = convert_char_to_keycode([int(threshold_key)])
                if key_name:
                    print(f" ({key_name[0]})")
                else:
                    print()
            else:
                print()
    
    print("\n✓ Test completed!\n")

if __name__ == "__main__":
    main()
