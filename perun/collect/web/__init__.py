"""Trace collector collects running times of C/C++ functions.
The collected data are suitable for further postprocessing using
the regression analysis and visualization by scatter plots.
"""

COLLECTOR_TYPE = "web"
COLLECTOR_DEFAULT_UNITS = {
    "page_requests":              "",
    "error_count":                "",
    "error_code_count":           "",
    "error_message_count":        "",
    "memory_usage_counter":       "MB",
    "request_latency_summary":    "ms",
    "throughput":                 "requests per second",
    "user_cpu_usage":             "s",
    "system_cpu_usage":           "s",
    "user_cpu_time":              "s",
    "system_cpu_time":            "s",
    "fs_read":                    "",
    "fs_write":                   "",
    "voluntary_context_switches": "",
}
