import sys, os

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# Add any Sphinx extension module names here, as strings.
# They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions += ['sphinx.ext.inheritance_diagram', 'sphinxcontrib.blockdiag',
               'sphinxcontrib.actdiag', 'sphinxcontrib.seqdiag',
               'sphinxcontrib.nwdiag']

# The encoding of source files.
source_encoding = 'utf-8-sig'
#source_encoding = 'shift_jis'

# The language for content autogenerated by Sphinx.
language = 'en'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "fuel"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    # Navigation bar title. (Default: ``project`` value)
    'navbar_title': "Documentation",

    # Tab name for entire site. (Default: "Site")
    'navbar_site_name': "Guide",

    # A list of tuples containing pages or urls to link to.
    # Valid tuples should be in the following forms:
    #    (name, page)                 # a link to a page
    #    (name, "/aa/bb", 1)          # a link to an arbitrary relative url
    #    (name, "http://example.com", True) # arbitrary absolute url
    # Note the "1" or "True" value above as the third argument to indicate
    # an arbitrary url.
    # 'navbar_links': [
    #     ("Examples", "examples"),
    #     ("Link", "http://example.com", True),
    # ],

    # Render the next and previous page links in navbar. (Default: true)
    'navbar_sidebarrel': True,

    # Render the current pages TOC in the navbar. (Default: true)
    'navbar_pagenav': True,

    # Tab name for the current pages TOC. (Default: "Page")
    'navbar_pagenav_name': "Section",

    # Global TOC depth for "site" navbar tab. (Default: 1)
    # Switching to -1 shows all levels.
    'globaltoc_depth': 2,

    # Include hidden TOCs in Site navbar?
    #
    # Note: If this is "false", you cannot have mixed ``:hidden:`` and
    # non-hidden ``toctree`` directives in the same page, or else the build
    # will break.
    #
    # Values: "true" (default) or "false"
    'globaltoc_includehidden': "true",

    # HTML navbar class (Default: "navbar") to attach to <div> element.
    # For black navbar, do "navbar navbar-inverse"
    'navbar_class': "navbar",

    # Fix navigation bar to top of page?
    # Values: "true" (default) or "false"
    'navbar_fixed_top': "true",

    # Location of link to source.
    # Options are "nav" (default), "footer" or anything else to exclude.
    'source_link_position': "nav",

    # Bootswatch (http://bootswatch.com/) theme.
    #
    # Options are nothing (default) or the name of a valid theme
    # such as "amelia" or "cosmo".
    'bootswatch_theme': "yeti",

    # Choose Bootstrap version.
    # Values: "3" (default) or "2" (in quotes)
    'bootstrap_version': "3",
}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['_templates']

html_show_sourcelink = False

html_add_permalinks = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = '_static/Fuel-Logo.png'

# If this is not the empty string, a 'Last updated on:' timestamp
# is inserted at every page bottom, using the given strftime() format.
# Default is '%b %d, %Y' (or a locale-dependent equivalent).
html_last_updated_fmt = '%Y/%m/%d'

# Enable Antialiasing
blockdiag_antialias = True
acttdiag_antialias = True
seqdiag_antialias = True
nwdiag_antialias = True

extensions += ['rst2pdf.pdfbuilder']
pdf_documents = [
    (master_doc, project, project, copyright),
]
pdf_stylesheets = ['sphinx', 'kerning', 'a4']
pdf_language = "en_US"
# Mode for literal blocks wider than the frame. Can be
# overflow, shrink or truncate
pdf_fit_mode = "shrink"

# Section level that forces a break page.
# For example: 1 means top-level sections start in a new page
# 0 means disabled
#pdf_break_level = 0

# When a section starts in a new page, force it to be 'even', 'odd',
# or just use 'any'
pdf_breakside = 'any'

# Insert footnotes where they are defined instead of
# at the end.
pdf_inline_footnotes = False

# verbosity level. 0 1 or 2
pdf_verbosity = 0

# If false, no index is generated.
pdf_use_index = True

# If false, no modindex is generated.
pdf_use_modindex = True

# If false, no coverpage is generated.
pdf_use_coverpage = True

# Name of the cover page template to use
#pdf_cover_template = 'sphinxcover.tmpl'

# Documents to append as an appendix to all manuals.
#pdf_appendices = []

# Enable experimental feature to split table cells. Use it
# if you get "DelayedTable too big" errors
#pdf_splittables = False

# Set the default DPI for images
#pdf_default_dpi = 72

# Enable rst2pdf extension modules (default is only vectorpdf)
# you need vectorpdf if you want to use sphinx's graphviz support
#pdf_extensions = ['vectorpdf']

# Page template name for "regular" pages
#pdf_page_template = 'cutePage'

# Show Table Of Contents at the beginning?
pdf_use_toc = True

# How many levels deep should the table of contents be?
pdf_toc_depth = 3

# Add section number to section references
pdf_use_numbered_links = False

# Background images fitting mode
pdf_fit_background_mode = 'scale'
