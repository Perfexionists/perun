perun_templates_diff_components_dir = perun_templates_dir / 'diff_components'

perun_templates_diff_components_files = files(
    'chatbot.html.jinja2',
    'division_anchor.html.jinja2',
)

py3.install_sources(
    perun_templates_diff_components_files,
    subdir: perun_templates_diff_components_dir
)

subdir('side_panels')
