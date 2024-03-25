/* SPDX-License-Identifier: GPL-2.0 OR BSD-3-Clause
   This file is automatically generated! */

#include "vmlinux.h"
#include <bpf/bpf_tracing.h>
#include "ktrace.h"

char LICENSE[] SEC("license") = "Dual BSD/GPL";

struct {
	__uint(type, BPF_MAP_TYPE_RINGBUF);
	__uint(max_entries, {{ bpfring_size }});
} rb SEC(".maps");

uint64_t events_lost = 0;
{% for i in range(0, command_names|length) %}
pid_t process_pid{{ i }} = 0;
{%- endfor %}

SEC("tp/sched/sched_process_exec")
int handle_exec(struct trace_event_raw_sched_process_exec *ctx)
{
{% for command_name in command_names %}
	char comm{{ loop.index0 }}[{{ command_name|length }} + 1];
	bpf_get_current_comm(comm{{ loop.index0 }}, {{ command_name|length }} + 1);
	if (bpf_strncmp(comm{{ loop.index0 }}, {{ command_name|length }}, "{{ command_name }}" ) == 0) {
		process_pid{{ loop.index0 }} = bpf_get_current_pid_tgid() >> 32;
		bpf_printk("EXEC {{ command_name }}: pid = %d\n", process_pid{{ loop.index0 }});
	}
{% endfor %}
	return 0;
}

SEC("tp/sched/sched_process_exit")
int handle_exit(struct trace_event_raw_sched_process_template *ctx)
{
    pid_t pid;
    pid = bpf_get_current_pid_tgid() >> 32;
{% for i in range(0, command_names|length ) %}
	if (pid == process_pid{{ i }}) {
		bpf_printk("EXIT {{ command_names[i] }}: pid = %d\n", process_pid{{ i }});
		process_pid{{ i }} = 0;
	}
{% endfor %}
	return 0;
}

{% if include_main %}
SEC("uprobe//proc/self/exe:main")
int BPF_KPROBE(uprobe_main, int argc, char** argv)
{
	pid_t pid;
	pid = bpf_get_current_pid_tgid() >> 32;
    if ((pid != process_pid0 {% for it in range(1, command_names|length) %} && pid != process_pid{{ it }}{% endfor %}) || pid == 0) {
		return 0;
	}

	/* reserve sample from BPF ringbuf */
	struct event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
	if (!e) {
		events_lost++;
		return 0;
	}

	// 32 lowest bits: pid, 32 upper bits: func ID (28b) + event type (4b)
	e->data[0] = ({{ main_id }} << 4);
	// Make it the upper bits
	e->data[0] <<= 32;
	// Add PID
	e->data[0] |= pid;
	e->data[1] = bpf_ktime_get_ns();
	/* successfully submit it to user-space for post-processing */
	bpf_ringbuf_submit(e, 0);
	return 0;
}

SEC("uretprobe//proc/self/exe:main")
int BPF_KRETPROBE(uprobe_main_exit, int ret)
{
	pid_t pid;
	pid = bpf_get_current_pid_tgid() >> 32;
    if ((pid != process_pid0 {% for it in range(1, command_names|length) %} && pid != process_pid{{ it }}{% endfor %}) || pid == 0) {
		return 0;
	}

	/* reserve sample from BPF ringbuf */
	struct event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
	if (!e) {
		events_lost++;
		return 0;
	}

	// 32 lowest bits: pid, 32 upper bits: func ID (28b) + event type (4b)
	e->data[0] = ({{ main_id }} << 4) | 0x1;
	// Make it the upper bits
	e->data[0] <<= 32;
	// Add PID
	e->data[0] |= pid;
	e->data[1] = bpf_ktime_get_ns();
	/* successfully submit it to user-space for post-processing */
	bpf_ringbuf_submit(e, 0);
	return 0;
}
{% endif %}

{% for func_name, func_idx in symbols.items() %}
SEC("kprobe/{{ func_name }}")
int BPF_KPROBE({{ func_name|replace(".", "_") }})
{
	pid_t pid;
	pid = bpf_get_current_pid_tgid() >> 32;
    if ((pid != process_pid0 {% for it in range(1, command_names|length) %} && pid != process_pid{{ it }}{% endfor %}) || pid == 0) {
		return 0;
	}

	/* reserve sample from BPF ringbuf */
	struct event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
	if (!e) {
		events_lost++;
		return 0;
	}

	// 32 lowest bits: pid, 32 upper bits: func ID (28b) + event type (4b)
	e->data[0] = ({{ func_idx }} << 4);
	// Make it the upper bits
	e->data[0] <<= 32;
	// Add PID
	e->data[0] |= pid;
	e->data[1] = bpf_ktime_get_ns();
	/* successfully submit it to user-space for post-processing */
	bpf_ringbuf_submit(e, 0);
	return 0;
}

SEC("kretprobe/{{ func_name }}")
int BPF_KRETPROBE({{ func_name|replace(".", "_") }}_exit)
{
	pid_t pid;
	pid = bpf_get_current_pid_tgid() >> 32;
    if ((pid != process_pid0 {% for it in range(1, command_names|length) %} && pid != process_pid{{ it }}{% endfor %}) || pid == 0) {
		return 0;
	}

	/* reserve sample from BPF ringbuf */
	struct event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
	if (!e) {
		events_lost++;
		return 0;
	}

	// 32 lowest bits: pid, 32 upper bits: func ID (28b) + event type (4b)
	e->data[0] = ({{ func_idx }} << 4) | 0x1;
	// Make it the upper bits
	e->data[0] <<= 32;
	// Add PID
	e->data[0] |= pid;
	e->data[1] = bpf_ktime_get_ns();
	/* successfully submit it to user-space for post-processing */
	bpf_ringbuf_submit(e, 0);
	return 0;
}
{% endfor %}