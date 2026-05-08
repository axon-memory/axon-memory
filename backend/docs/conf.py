# -- Sphinx Configuration for Axon Memory ------------------------------------
# Full documentation: https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# -- Path Setup --------------------------------------------------------------
# Add the backend root so that ``import axon_memory`` works during autodoc.
sys.path.insert(0, os.path.abspath(".."))

# -- Project Information -----------------------------------------------------
project = "Axon Memory"
copyright = "2026, Axon Memory Contributors"
author = "Axon Memory Contributors"
release = "0.4.0"
version = "0.4"

# -- General Configuration ---------------------------------------------------
extensions = [
    # Auto-generate API docs from docstrings
    "sphinx.ext.autodoc",
    # Support Google / NumPy style docstrings
    "sphinx.ext.napoleon",
    # Add [source] links beside every documented object
    "sphinx.ext.viewcode",
    # Render Mermaid diagrams in documentation
    "sphinxcontrib.mermaid",
    # Inline type-hint annotations in signatures & descriptions
    "sphinx_autodoc_typehints",
    # Cross-reference Python objects in external projects
    "sphinx.ext.intersphinx",
    # Auto-generate summary tables for modules / classes
    "sphinx.ext.autosummary",
]

# -- Napoleon Settings -------------------------------------------------------
napoleon_google_docstrings = True
napoleon_numpy_docstrings = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False

# -- Autodoc Settings --------------------------------------------------------
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "exclude-members": "__weakref__",
}
autodoc_typehints = "both"
autodoc_class_signature = "separated"

# Mock imports for packages that may not be installable in the docs environment
# (C-extensions, GPU libraries, API clients, etc.)
autodoc_mock_imports = [
    "sqlite_vec",
    "sentence_transformers",
    "ollama",
    "google",
    "google.genai",
    "dotenv",
    "uvicorn",
    "mcp",
]

# -- Autosummary Settings ----------------------------------------------------
autosummary_generate = True

# -- Type Hints Settings -----------------------------------------------------
typehints_fully_qualified = False
always_document_param_types = True
typehints_document_rtype = True

# -- Intersphinx Mapping -----------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# -- Mermaid Settings --------------------------------------------------------
mermaid_output_format = "raw"  # Use JS-based rendering (no external binary needed)
mermaid_version = "10.9.0"

# -- HTML Output -------------------------------------------------------------
html_theme = "furo"
html_title = "Axon Memory Documentation"
html_short_title = "Axon Memory"
html_static_path = ["_static"]

# Furo theme customization
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#6C63FF",
        "color-brand-content": "#6C63FF",
    },
    "dark_css_variables": {
        "color-brand-primary": "#A29BFE",
        "color-brand-content": "#A29BFE",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
}

# -- Exclude Patterns --------------------------------------------------------
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Source Suffix -----------------------------------------------------------
source_suffix = ".rst"

# -- Master Document ---------------------------------------------------------
master_doc = "index"
