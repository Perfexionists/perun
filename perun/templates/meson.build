perun_templates_dir = perun_dir / 'templates'

perun_templates_files = files(
    'check.jinja2',
    'collect.__init__.jinja2',
    'collect.run.jinja2',
    'diff_view_flamegraph.html.jinja2',
    'diff_view_report.html.jinja2',
    'macros_accordion.html.jinja2',
    'macros_profile_overview.html.jinja2',
    'postprocess.__init__.jinja2',
    'postprocess.run.jinja2',
    'view.__init__.jinja2',
    'view.run.jinja2',
)

py3.install_sources(
    perun_templates_files,
    subdir: perun_templates_dir
)