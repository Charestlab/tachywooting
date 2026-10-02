Usage
=====

Keyboard Initialization
-----------------------

.. code:: python

   from tachywooting import WOOTING_ACQUISITION

   acq = WOOTING_ACQUISITION(
       threshold=0.8,
       min_pressure_start=0.33,
       max_pressure_start=0.66,
   )
   acq.initialize_keyboard(verbose=True)

Light-press readiness
---------------------

.. code:: python

   acq.wait_keys_light_press(target_keys=["z", "c"], quit_key="q")

For experiments with on-screen pressure feedback, we highly recommend using
TachyWooting through TachyPy instead. See :doc:`tachypy` for the recommended
install and the visual-feedback import path.

.. _usage_tachypy_direct_example:

Usage example: TachyPy screen + TachyWooting logging
----------------------------------------------------

This example is for experiments that use TachyPy for stimulus presentation but
use TachyWooting directly for keyboard readiness, acquisition, and logging. It
intentionally uses ``wait_keys_light_press`` rather than
``wait_light_press_visual``. If you want visual pressure feedback, use the
TachyPy integration described in :doc:`tachypy`.

.. code:: python

   from tachypy import FixationCross, ResponseHandler, Screen
   from tachywooting import WOOTING_ACQUISITION, convert_char_to_keycode

   YES, NO = "z", "c"

   acq = WOOTING_ACQUISITION(
       threshold=0.8,
       min_pressure_start=0.33,
       max_pressure_start=0.66,
   )
   acq.initialize_keyboard()
   acq.setup_logging(name="participant_01", path="logs", int_analog=2)

   screen = Screen(fullscreen=False)
   rh = ResponseHandler(screen=screen)
   fixation = FixationCross(
       center=(screen.width // 2, screen.height // 2),
       half_width=18,
       half_height=18,
       thickness=8,
       color=(0, 0, 0),
   )

   try:
       for trial in range(1, 21):
           # 1) Readiness: wait until both fingers rest lightly on the keys.
           if not acq.wait_keys_light_press(target_keys=[YES, NO], quit_key="q"):
               break

           # 2) Present the stimulus and time-lock the trial to the flip.
           screen.fill((128, 128, 128))
           fixation.draw()
           # ... draw your stimulus here ...
           onset = screen.flip()

           # 3) Acquire the response trajectory. This writes one HDF5 shard.
           hier = acq.acquire_analog_values(
               [YES, NO],
               trial_start_ns=onset,
               trial_start_clock="mono",
           )
           response = acq.get_response_key(hier, [YES, NO])
           label = convert_char_to_keycode([response])[0]
           print(f"trial {trial}: response = {label}")

   finally:
       acq.uninitialize_keyboard()
       screen.close()

``screen.flip()`` returns TachyPy's post-swap timestamp. Passing it to
``acquire_analog_values(..., trial_start_clock="mono")`` makes every logged
``time_from_onset`` sample relative to the displayed stimulus onset. See
:doc:`logging` for the resulting HDF5 layout and metadata.

Acquisition
-----------

.. code:: python

   data = acq.acquire_analog_values(target_keys=["z", "c"])

Show a blank immediately after the response while continuing to record pressure:

.. code:: python

   def show_response_blank():
       screen.fill((128, 128, 128))
       screen.flip()

   data = acq.acquire_analog_values(
       target_keys=["z", "c"],
       duration_after_threshold=0.5,
       threshold_callback=show_response_blank,
   )

``threshold_callback`` runs once when either target key crosses the response
threshold. The crossing sample and the following ``duration_after_threshold``
seconds remain in ``data`` and, when logging is enabled, in the trial's HDF5
file. Keep the callback short because acquisition resumes after it returns; its
execution time is part of that post-threshold wall-clock interval.

This is especially useful when the post-response recording period should also
be the inter-trial blank. In the example above, the blank begins at the response
and TachyWooting records during the same 0.5 seconds. Do not add another
0.5-second blank afterward, or the response-to-next-trial interval would become
1.0 second. If the desired blank is longer than the recording period, wait only
for the remainder:

.. code:: python

   import time

   blank_duration = 0.8
   post_response_recording = 0.5

   data = acq.acquire_analog_values(
       target_keys=["z", "c"],
       duration_after_threshold=post_response_recording,
       threshold_callback=show_response_blank,
   )
   time.sleep(max(0.0, blank_duration - post_response_recording))

This differs from ``callback`` with ``callback_delay``: that callback runs at a
scheduled time before a response, and is canceled if the threshold is crossed
first.

Logging
-------

.. code:: python

   acq.setup_logging(path="logs", name="participant_001", int_analog=2)
   acq.acquire_analog_values(target_keys=["z", "c"])
   acq.uninitialize_keyboard()

See :doc:`logging` for the HDF5 lifecycle, file layout, trial metadata, and
helpers for reading logs back into Python.
