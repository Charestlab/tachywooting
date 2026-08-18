"""Sphinx configuration for TachyWooting docs."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

project = "TachyWooting"
author = "Mathias Salvas-Hébert"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]
autosummary_generate = True
autodoc_mock_imports = [
    "h5py",
    "matplotlib",
    "numpy",
    "pandas",
    "rich",
    "tqdm",
]
templates_path = ["_templates"]
exclude_patterns = ["_build"]
html_theme = "furo"
html_title = "TachyWooting"
html_static_path = ["_static"]
html_theme_options = {
    "sidebar_hide_name": False,
    "source_repository": "https://github.com/Charestlab/TachyWooting/",
    "source_branch": "main",
    "source_directory": "docs/",
}

os.environ.setdefault("WOOTING_DOCS_BUILD", "1")
