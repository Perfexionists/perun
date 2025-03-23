perun_templates_dir = perun_dir / 'templates'

perun_templates_files = files(
    '__init__.py',
    'check.jinja2',
    'collect.__init__.jinja2',
    'collect.run.jinja2',
    'dataTables.dataTables.min.css',
    'dataTables.min.js',
    'dataTables.select.min.js',
    'diff_view_flamegraph.html.jinja2',
    'diff_view_datatables.html.jinja2',
    'diff_view_sankey.html.jinja2',
    'factory.py',
    'jquery-3.6.0.min.js',
    'macros_accordion.html.jinja2',
    'macros_html_widgets.html.jinja2',
    'macros_profile_overview.html.jinja2',
    'plotly-2.30.0.min.js',
    'postprocess.__init__.jinja2',
    'postprocess.run.jinja2',
    'ssp_general_sidebar_property.html.jinja2',
    'ssp_report.html.jinja2',
    'ssp_sankey.html.jinja2',
    'ssp_table.html.jinja2',
    'view.__init__.jinja2',
    'view.run.jinja2',
)

py3.install_sources(
    perun_templates_files,
    subdir: perun_templates_dir
)

subdir('assets')
subdir('scripts')
subdir('ssp_sections')
subdir('style')
