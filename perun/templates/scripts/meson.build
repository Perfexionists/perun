perun_templates_script_dir = perun_templates_dir / 'scripts'

perun_templates_script_files = files(
    'division_anchor.js',
    'drag_n_drop.js',
    'environment_sidepanel.js',
    'flame_graph_js.html.jinja2',
    'graph_grids.js',
    'chatbot.html.jinja2',
    'navigation_sidepanel.js',
    'notes.js',
    'sankey_graph_js.html.jinja2',
    'overview.js',
    'themes_js.html.jinja2',
    'tooltip.js',
    'traces_table.js',
    'tree_map.js',
    'value_formatters_js.html.jinja2',
)

py3.install_sources(
    perun_templates_script_files,
    subdir: perun_templates_script_dir
)