from docutils import nodes
import perun

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.mathjax', 'sphinx.ext.viewcode',
              'sphinx.ext.todo', 'sphinx.ext.intersphinx', 'sphinx_click.ext']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'Perun'
copyright = '2021, Tomas Fiedor, Jiri Pavela, Simon Stupinsky, Matus Liscinsky, Adam Rogalewicz, Tomas Vojnar'
author = 'Tomas Fiedor, Jiri Pavela, Simon Stupinsky, Matus Liscinsky, Adam Rogalewicz, Tomas Vojnar'

version = perun.__version__
release = perun.__version__
language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True


# html_theme = 'alabaster'
html_style = "perun.css"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    'show_related': True
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# This is required for the alabaster theme
# refs: http://alabaster.readthedocs.io/en/latest/installation.html#sidebars
html_sidebars = {
    'index': [
        'about.html', 'sourcelink.html', 'searchbox.html'
    ],
    '**': [
        'logo.html',
        'localtoc.html',
        'relations.html',  # needs 'show_related': True theme option to display
        'sourcelink.html',
        'searchbox.html',
    ]
}


# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'Perundoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'Perun.tex', 'Perun Evaluation',
     'Tomas Fiedor, Jiri Pavela, et al.', 'manual'),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'perun', 'Perun Documentation',
     [author], 1)
]


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'Perun', 'Perun Documentation',
     author, 'Perun', 'One line description of project.',
     'Miscellaneous'),
]


def setup(app):
    pass
