TachyWooting Documentation
==========================

.. image:: https://img.shields.io/pypi/v/tachywooting
   :target: https://pypi.org/project/tachywooting/
   :alt: PyPI version

.. image:: https://img.shields.io/badge/License-BSD_3--Clause-blue.svg
   :target: https://github.com/Charestlab/tachywooting/blob/main/LICENSE
   :alt: License: BSD-3-Clause

.. image:: https://img.shields.io/pypi/pyversions/tachywooting
   :target: https://pypi.org/project/tachywooting/
   :alt: Python versions

.. image:: https://github.com/Charestlab/tachywooting/actions/workflows/test-install.yml/badge.svg
   :target: https://github.com/Charestlab/tachywooting/actions/workflows/test-install.yml
   :alt: Tests

TachyWooting provides Python bindings and acquisition utilities for Wooting
analog keyboards, with readiness checks, finger-removal tracking, and
hierarchical HDF5 logging for experiment workflows.

On-screen pressure feedback lives in TachyPy. Install ``tachypy[wooting]`` when
you want the interactive fixation-cross feedback inside TachyPy experiments.

.. toctree::
   :maxdepth: 2
   :caption: Guide

   getting_started
   usage
   tachypy
   logging
   scripts
   documentation
   development
   plugin_management
   raw_sdk

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api
