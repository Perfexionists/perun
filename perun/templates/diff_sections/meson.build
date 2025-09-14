perun_templates_diff_sections_dir = perun_templates_dir / 'diff_sections'

perun_templates_diff_section_files = files(
    'section_environment.html.jinja2',
    'section_flame_graphs.html.jinja2',
    'section_metadata.html.jinja2',
    'section_page_footer.html.jinja2',
    'section_page_title.html.jinja2',
    'section_profile_stats.html.jinja2',
    'section_sankey_graph.html.jinja2',
    'section_traces_table.html.jinja2',
    'section_vulnerabilities.html.jinja2',
)

py3.install_sources(
    perun_templates_diff_section_files,
    subdir: perun_templates_diff_sections_dir
)