Development Guide
=================

This document is a maintainer guide for the TachyWooting project.

1) Development Setup
--------------------

Prerequisites
~~~~~~~~~~~~~

- Python 3.9+ (CI covers 3.9-3.14)
- A local C compiler toolchain (for CFFI)
- Docker Desktop (if you run workflows with ``act``)

Local installation
~~~~~~~~~~~~~~~~~~

.. code:: bash

   python -m pip install -e ".[dev]"
   wooting-build-interface

2) ``update-wooting-sdk`` Workflow
----------------------------------

The GitHub Actions workflow ``update-wooting-sdk`` updates vendored SDK
assets under ``tachywooting/libraries`` from an official Wooting SDK
release.

Workflow file: ``.github/workflows/update-wooting-sdk.yml`` Script used:
``scripts/update_wooting_sdk.py``

What the workflow does
~~~~~~~~~~~~~~~~~~~~~~

1. Runs manually (``workflow_dispatch``) with a ``version`` input
   (default ``0.9.1``).
2. Executes:

.. code:: bash

   python scripts/update_wooting_sdk.py --version "<version>"

3. Checks whether ``tachywooting/libraries`` changed.
4. If changed:

- creates branch ``update-wooting-sdk-<version>``
- commits changes
- pushes branch
- opens a PR automatically

Running SDK updates locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   python scripts/update_wooting_sdk.py --version 0.9.1
   git status --short

The script:

- downloads GitHub release assets for macOS arm64/x86_64, Linux, and Windows;
- verifies SHA256 digests from release metadata or the ``KNOWN_SHA256``
  fallback;
- extracts archives and replaces target platform directories;
- removes SDK assets that are not shipped with the Python package;
- updates ``tachywooting/libraries/VERSION.json``;
- adjusts macOS release-library install names for dylibs when needed.

Excluded SDK assets
~~~~~~~~~~~~~~~~~~~

TachyWooting vendors only the SDK pieces needed for normal package installs and
CFFI builds. The updater intentionally excludes:

- ``debug/`` SDK libraries;
- ``VIRTUAL_KEYBOARD.md``;
- ``wooting-analog-virtual-control``;
- ``wooting-analog-virtual-control.exe``.

Those assets support Wooting SDK development and virtual-keyboard testing, but
they are not required to use TachyWooting with a real keyboard. Keeping them out
of the repository and PyPI package keeps ``pip install tachywooting`` small and
consistent across platforms. If a maintainer needs to test the Wooting virtual
keyboard locally, download the official Wooting SDK release assets into a local
scratch directory instead of vendoring them in this package.

SDK update best practices
~~~~~~~~~~~~~~~~~~~~~~~~~

- Always inspect ``git diff tachywooting/libraries`` before commit.
- Ensure required release artifacts still exist, especially
  ``tachywooting/libraries/linux/release`` for CI Linux builds.
- Ensure excluded SDK assets did not come back after an update.
- Do not remove binaries required by the CFFI build.

3) Running workflows locally with ``act``
-----------------------------------------

You can run ``test-install.yml`` locally.

Local config file: ``.actrc`` (ignored by Git).

Examples:

.. code:: bash

   act -W .github/workflows/test-install.yml -l
   act pull_request -W .github/workflows/test-install.yml -j install --matrix os:ubuntu-latest --matrix python-version:3.12 --matrix extras:dev
   act pull_request -W .github/workflows/test-install.yml -j test --matrix os:ubuntu-latest --matrix python-version:3.12

Notes: - ``act`` mainly emulates Linux; macOS/Windows are not reproduced
1:1. - On Apple Silicon, use ``linux/amd64`` to reduce compatibility
issues.

4) Documentation Structure
--------------------------

Documentation is built with Sphinx under ``docs/``.

Main entry points
~~~~~~~~~~~~~~~~~

- ``docs/index.rst``: main table of contents
- ``docs/getting_started.rst``: overview and quick start
- ``docs/usage.rst``: usage examples
- ``docs/tachypy.rst``: TachyPy integration and experiment example
- ``docs/logging.rst``: HDF5 logging lifecycle and file layout
- ``docs/scripts.rst``: console-script documentation
- ``docs/api.rst``: API reference
- ``docs/documentation.rst``: technical notes

Sphinx configuration
~~~~~~~~~~~~~~~~~~~~

File: ``docs/conf.py``

Enabled extensions:

- ``sphinx.ext.autodoc``
- ``sphinx.ext.autosummary``
- ``sphinx.ext.napoleon``

Conventions:

- NumPy-style docstrings
- autosummary generation enabled
- theme: ``furo``

Useful docs directories
~~~~~~~~~~~~~~~~~~~~~~~

- ``docs/_build/``: generated build output
- ``docs/generated/``: generated API pages
- ``docs/_static/``: static assets

5) Quality Checks Before PR
---------------------------

Tests
~~~~~

.. code:: bash

   pytest tests/ -v --tb=short

Package installation check (CI-like)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   python -m pip install .
   python -m pip show tachywooting

Clean CFFI rebuild (if needed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   wooting-delete-interface
   wooting-build-interface

6) Important Project Files
--------------------------

- ``pyproject.toml``: package metadata, dependencies, scripts
- ``tachywooting/wooting_interface_builder.py``: CFFI build and native
  linking
- ``tachywooting/package_setup.py``: post-install orchestration
  (permissions/plugins)
- ``scripts/update_wooting_sdk.py``: vendored SDK updater
- ``.github/workflows/test-install.yml``: install/test matrix CI
- ``.github/workflows/update-wooting-sdk.yml``: automated SDK update
  workflow

7) Practical Notes
------------------

- ``.DS_Store`` and ``.actrc`` are local files and should remain
  ignored.
- ``pip as root`` warnings in ``act`` containers are expected.
- If ``rg`` is not installed locally, use ``grep`` to filter logs.
