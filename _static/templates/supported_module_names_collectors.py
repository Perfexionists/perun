def get_supported_module_names(package):
    """..."""
    if package not in ("vcs", "collect", "postprocess", "view"):
        error(f"trying to call get_supported_module_names with incorrect package '{package}'")
    return {
        "vcs": ["git", "svs"],
        "collect": ["trace", "memory", "time", "mycollector"],
        "postprocess": [
            "moving-average",
            "kernel-regression",
            "regression-analysis",
            "regressogram",
        ],
        "view": [
            "alloclist",
            "bars",
            "flamegraph",
            "flow",
            "heapmap",
            "scatter",
        ],
    }[package]
