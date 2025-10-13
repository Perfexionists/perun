perun_templates_script_dir = perun_templates_dir / 'scripts'

perun_templates_script_files = files(
    'chatbot.html.jinja2',
    'division_anchor.js',
    'environment_sidepanel.js',
    'flame_graph_js.html.jinja2',
    'navigation_sidepanel.js',
    'notes.js',
    'sankey_graph_js.html.jinja2',
    'themes_js.html.jinja2',
    'tooltip.js',
    'traces_table_js.html.jinja2',
    'value_formatters_js.html.jinja2',
)

py3.install_sources(
    perun_templates_script_files,
    subdir: perun_templates_script_dir
)