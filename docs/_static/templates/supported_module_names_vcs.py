def get_supported_module_names(package):
    """..."""
    if package not in ('vcs', 'collect', 'postprocess', 'view'):
        error("trying to call get_supported_module_names with incorrect package '{}'".format(
            package
        ))
    return {
        'vcs': ['git', 'myvcs'],
        'collect': ['complexity', 'memory', 'time'],
        'postprocess': ['filter', 'normalizer', 'regression_analysis'],
        'view': ['alloclist', 'bars', 'flamegraph', 'flow', 'heapmap', 'raw', 'scatter']
    }[package]
