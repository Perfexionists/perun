/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
   Copyright (c) 2023 Perun Team
   Based on bootstrap.c */

#include <stdio.h>
#include <signal.h>
#include <bpf/libbpf.h>
#include "ktrace.h"
#include "ktrace.skel.h"


static int libbpf_print_fn(enum libbpf_print_level level, const char *format, va_list args)
{
	return vfprintf(stderr, format, args);
}

static volatile bool exiting = false;

static void sig_handler(int sig)
{
	exiting = true;
}

static int handle_event(void *ctx, void *data, size_t data_sz)
{
	const struct event *e = data;
	FILE *out = (FILE *)ctx;
	fwrite(e->data, sizeof(e->data), 1, out);
	return 0;
}

int main(int argc, char **argv)
{
	FILE *out = NULL;
	struct ring_buffer *rb = NULL;
	struct ktrace_bpf *skel;
	int err;

	/* Set up libbpf errors and debug info callback */
	libbpf_set_print(libbpf_print_fn);

	/* Cleaner handling of Ctrl-C */
	signal(SIGINT, sig_handler);
	signal(SIGTERM, sig_handler);

	/* Open load and verify BPF application */
	skel = ktrace_bpf__open_and_load();
	if (!skel) {
		fprintf(stderr, "Failed to open BPF skeleton\n");
		return 1;
	}

	/* Attach tracepoint handler */
	err = ktrace_bpf__attach(skel);
	if (err) {
		fprintf(stderr, "Failed to attach BPF skeleton\n");
		goto cleanup;
	}

	// Prepare an output file
	out = fopen("output.log", "wb+");
	if (out == NULL) {
		goto cleanup;
	}

	/* Set up ring buffer polling */
	rb = ring_buffer__new(bpf_map__fd(skel->maps.rb), handle_event, (void *)out, NULL);
	if (!rb) {
		err = -1;
		fprintf(stderr, "Failed to create ring buffer\n");
		goto cleanup;
	}

	/* Process events */
	while (!exiting) {
		err = ring_buffer__poll(rb, 10 /* timeout, ms */);
		/* Ctrl-C will cause -EINTR */
		if (err == -EINTR) {
			err = 0;
			break;
		}
		if (err < 0) {
			printf("Error polling perf buffer: %d\n", err);
			break;
		}
	}

cleanup:
	/* Clean up */
	// Did we lose any data?
	fprintf(stderr, "Lost events: %lu\n", skel->bss->events_lost);
	ring_buffer__free(rb);
	ktrace_bpf__destroy(skel);
	if (out != NULL) {
		fclose(out);
	}
	return err < 0 ? -err : 0;
}
