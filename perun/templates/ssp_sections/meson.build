perun_templates_ssp_sections_dir = perun_templates_dir / 'ssp_sections'

perun_templates_ssp_section_files = files(
    'section_general_stats.html.jinja2',
    'section_metadata.html.jinja2',
    'section_profile_stats.html.jinja2',
    'section_table_traces.html.jinja2',
    'section_vulnerabilities.html.jinja2',
)

py3.install_sources(
    perun_templates_ssp_section_files,
    subdir: perun_templates_ssp_sections_dir
)