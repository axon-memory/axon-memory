# -- Sphinx Configuration for Axon Memory ------------------------------------
# Full documentation: https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# -- Path Setup --------------------------------------------------------------
# Add the backend root so that ``import axon_memory`` works during autodoc.
sys.path.insert(0, os.path.abspath(".."))

# Set a dummy API key so autodoc can import modules that initialize the engine at module level
os.environ["GEMINI_API_KEY"] = "dummy_sphinx_key_for_autodoc_only"

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
    # Duration tracking for build profiling
    "sphinx.ext.duration",
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
napoleon_use_ivar = True
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
    "fastapi",
    "neo4j",
]

# -- Autosummary Settings ----------------------------------------------------
autosummary_generate = True

# -- Type Hints Settings -----------------------------------------------------
typehints_fully_qualified = False
always_document_param_types = True
typehints_document_rtype = True

# -- Intersphinx Mapping -----------------------------------------------------
# Cross-reference links to Python, Pydantic, and NumPy docs.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# -- Mermaid Settings --------------------------------------------------------
mermaid_output_format = "raw"  # JS-based rendering (no external binary needed)
mermaid_version = "11.4.1"
mermaid_init_js = """
mermaid.initialize({
    startOnLoad: true,
    theme: "neutral",
    themeVariables: {
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: "15px"
    },
    flowchart: {
        curve: "basis",
        padding: 20,
        nodeSpacing: 35,
        rankSpacing: 50,
        htmlLabels: true
    }
});
"""

# -- HTML Output -------------------------------------------------------------
html_theme = "furo"
html_title = "Axon Memory"
html_short_title = "Axon Memory"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# Furo theme customization
html_theme_options = {
    # --- Colour Palette ---
    "light_css_variables": {
        "color-brand-primary": "#6C63FF",
        "color-brand-content": "#5A52D5",
        "color-admonition-background": "rgba(108, 99, 255, 0.05)",
        "color-announcement-background": "#6C63FF",
        "color-announcement-text": "#ffffff",
    },
    "dark_css_variables": {
        "color-brand-primary": "#A29BFE",
        "color-brand-content": "#A29BFE",
        "color-admonition-background": "rgba(162, 155, 254, 0.08)",
        "color-announcement-background": "#2d2b55",
        "color-announcement-text": "#A29BFE",
    },
    # --- Sidebar ---
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    # --- Top-of-page ---
    "top_of_page_button": "edit",
    # --- Source / Edit on GitHub ---
    "source_repository": "https://github.com/your-org/axon-memory",
    "source_branch": "main",
    "source_directory": "backend/docs/",
    # --- Footer ---
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/your-org/axon-memory",
            "html": (
                '<svg stroke="currentColor" fill="currentColor" stroke-width="0" '
                'viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 '
                '3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01'
                '-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13'
                '-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 '
                '2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31'
                '-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 '
                '1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 '
                '1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 '
                '3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55'
                '.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>'
            ),
            "class": "",
        },
    ],
}

# -- Announcement Banner -----------------------------------------------------
html_theme_options["announcement"] = (
    "📡 <b>v0.4 Intelligence Layer</b> is live — LLM-powered conflict "
    "detection, hierarchy generation, and memory consolidation. "
    '<a href="changelog.html">See what\'s new →</a>'
)

# -- Exclude Patterns --------------------------------------------------------
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Source Suffix -----------------------------------------------------------
source_suffix = ".rst"

# -- Master Document ---------------------------------------------------------
master_doc = "index"
