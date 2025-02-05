"""Assembles the eBPF collection program according to the supplied probe specification.
Inspired by:
 - https://github.com/iovisor/bcc/blob/master/tools/funcslower.py
 - https://github.com/iovisor/bcc/blob/master/tools/funccount.py
"""

from perun.collect.trace.watchdog import WATCH_DOG
from perun.utils.structs.collect_structs import Optimizations


def assemble_ebpf_program(src_file, probes, config, **_):
    """Assembles the eBPF program.

    :param src_file: path to the program file, that should be generated
    :param probes: the probes object
    :param config: the collection configuration
    """
    WATCH_DOG.info(f"Attempting to assembly the eBPF program '{src_file}'")

    # Add unique probe and sampling ID to the probes
    max_id = probes.add_probe_ids()

    timed_sampling_on = Optimizations.TIMED_SAMPLING.value in config.run_optimizations

    # Open the eBPF program file
    with open(src_file, "w") as prog_handle:
        # Initialize the program
        sampled_count = len(probes.sampled_func) + len(probes.sampled_usdt)
        _add_structs_and_init(
            prog_handle,
            len(probes.func) + len(probes.usdt),
            sampled_count,
            timed_sampling_on,
        )
        if timed_sampling_on:
            _add_timed_event(prog_handle, max_id + 1)

        # Add entry and exit probe handlers for every traced function
        for func_probe in sorted(probes.func.values(), key=lambda value: value["name"]):
            _add_entry_probe(prog_handle, func_probe, timed_sampling_on)
            _add_exit_probe(prog_handle, func_probe, timed_sampling_on)
        # TODO: add USDT and cache tracing after BPF properly supports it

    WATCH_DOG.info("eBPF program successfully assembled")
    WATCH_DOG.log_probes(len(probes.func), len(probes.usdt), src_file)


def _add_structs_and_init(handle, probe_count, sampled_count, timed_sampling):
    """Add include statements, perf_event struct and the required BPF data structures.

    :param handle: the program file handle
    :param probe_count: the number of traced function and USDT locations
    :param sampled_count: the number of sampled probes
    """
    # Create the sampling BPF array if there are any sampled probes
    if sampled_count > 0:
        sampling_array = f"BPF_ARRAY(sampling, u32, {sampled_count});"
    else:
        sampling_array = "// sampling array omitted"
    # Create the timed sampling array to dynamically enable or disable records gathering
    if timed_sampling:
        timed_switch = "BPF_ARRAY(enabled, u32, 1);"
    else:
        timed_switch = "// timed sampling switch omitted"
    # The initial program code
    prog_init = f"""
#include <linux/sched.h>     // for TASK_COMM_LEN
#include <uapi/linux/bpf_perf_event.h>

struct duration_data {{
    u32 id;
    u32 pid;
    u64 entry_ns;
    u64 exit_ns;
    char comm[TASK_COMM_LEN];
}};

// BPF_ARRAY(cache, u64, 2);
BPF_ARRAY(timestamps, u64, {probe_count});
{timed_switch}
{sampling_array}
BPF_PERF_OUTPUT(records);
"""
    handle.write(prog_init)


def _add_timed_event(handle, probe_id):
    event_template = f"""
int set_enabled(struct bpf_perf_event_data *ctx)
{{
    u32 idx = 0;
    u32 *is_enabled = enabled.lookup(&idx);
    if (is_enabled == NULL) {{
        return 0;
    }}

    if (*is_enabled) {{
        *is_enabled = 0;
    }} else {{
        *is_enabled = 1;
    }}

    struct duration_data data = {{}};
    data.id = {probe_id};
    data.pid = bpf_get_current_pid_tgid();
    data.entry_ns = bpf_ktime_get_ns();
    data.exit_ns = bpf_ktime_get_ns();

    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    records.perf_submit(ctx, &data, sizeof(data));
    return 0;
}}
"""
    handle.write(event_template)


def _add_entry_probe(handle, probe, timed_sampling=False):
    """Add entry code for the given probe.

    :param handle: the program file handle
    :param probe: the traced probe
    """
    name = (probe["name"],)
    probe_id = (probe["id"],)
    sampling_before = (_create_sampling_before(probe["sample"]),)
    entry_body = (_create_entry_body(),)
    sampling_after = (_create_sampling_after(probe["sample"]),)
    timed_sampling = (_add_enabled_check(timed_sampling, probe["name"]),)
    probe_template = f"""
int entry_{name}(struct pt_regs *ctx)
{{
{timed_sampling}

    u32 id = {probe_id};
{sampling_before}
{entry_body}
{sampling_after}

    return 0;
}}
"""
    handle.write(probe_template)


def _add_exit_probe(handle, probe, timed_sampling=False):
    """Add exit code for the given probe.

    :param handle: the program file handle
    :param probe: the traced probe
    """
    name = (probe["name"],)
    probe_id = (probe["id"],)
    timed_sampling = (_add_enabled_check(timed_sampling, probe["name"]),)
    probe_template = f"""
int exit_{name}(struct pt_regs *ctx)
{{
{timed_sampling}

    u64 exit_timestamp = bpf_ktime_get_ns();
    u32 id = {probe_id};

    u64 *entry_timestamp = timestamps.lookup(&id);
    if (entry_timestamp == NULL || *entry_timestamp == 0) {{
        return 0;
    }}

    struct duration_data data = {{}};
    data.id = id;
    data.pid = bpf_get_current_pid_tgid();
    data.entry_ns = *entry_timestamp;
    data.exit_ns = exit_timestamp;

    (*entry_timestamp) = 0;

    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    records.perf_submit(ctx, &data, sizeof(data));

    return 0;
}}
"""
    handle.write(probe_template)


def _add_single_probe(handle, probe):
    """Add code for probe that has no paired probe, e.g. single USDT locations with no pairing.

    :param handle: the program file handle
    :param probe: the traced probe
    """
    probe_template = f"""
    int usdt_{probe['name']}(struct pt_regs *ctx)
    {{
        u64 usdt_timestamp = bpf_ktime_get_ns();

        struct duration_data data = {{}};
        data.id = {probe['id']};
        data.pid = bpf_get_current_pid_tgid();
        data.entry_ns = usdt_timestamp;
        data.exit_ns = usdt_timestamp;

        bpf_get_current_comm(&data.comm, sizeof(data.comm));
        records.perf_submit(ctx, &data, sizeof(data));

        return 0;
    }}
"""
    handle.write(probe_template)


def _add_cache_probes(handle):
    """Add code for cache probes that simply counts the HW cache events.
    Inspired by: https://github.com/iovisor/bcc/blob/master/tools/llcstat.py

    :param handle: the program file handle
    """
    template = """
int on_cache_ref(struct bpf_perf_event_data *ctx) {
    cache.increment(0, ctx->sample_period);
    return 0;
}

int on_cache_miss(struct bpf_perf_event_data *ctx) {
    cache.increment(1, ctx->sample_period);
    return 0;
}
"""
    handle.write(template)


def _create_sampling_before(sample_value):
    """Generate code that goes before the body for sampled probes.

    :param sample_value: the sample value of the probe
    :return: the generated code chunk
    """
    if sample_value == 1:
        return "   // sampling code omitted"
    return """
    u32 *sample = sampling.lookup(&id);
    if (sample == NULL) {
        return 0;
    }

    if (*sample == 0) {"""


def _create_sampling_after(sample_value):
    """Generate code that goes after the body for sampled probes.

    :param sample_value: the sample value of the probe
    :return: the generated code chunk
    """
    if sample_value == 1:
        return "   // sampling code omitted"
    return f"""
    }}

    (*sample)++;
    if (*sample == {sample_value}) {{
        (*sample) = 0;
    }}"""


def _create_entry_body():
    """Generate the generic body for all entry probes.

    :return: the generated code chunk
    """
    return """
    u64 entry_timestamp = bpf_ktime_get_ns();
    timestamps.update(&id, &entry_timestamp);"""


def _add_enabled_check(enabled, name):
    if not enabled or name == "main":
        return "    // timed sampling code omitted"
    return """    u32 enabled_idx = 0;
    u32 *is_disabled = enabled.lookup(&enabled_idx);
    if (is_disabled == NULL || (*is_disabled)) {
        return 0;
    }"""
