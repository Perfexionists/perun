perun_templates_units_dir = perun_templates_dir / 'units'

perun_templates_units_files = files(
    'check.jinja2',
    'collect.__init__.jinja2',
    'collect.run.jinja2',
    'postprocess.__init__.jinja2',
    'postprocess.run.jinja2',
    'view.__init__.jinja2',
    'view.run.jinja2',
)

py3.install_sources(
    perun_templates_units_files,
    subdir: perun_templates_units_dir
)
