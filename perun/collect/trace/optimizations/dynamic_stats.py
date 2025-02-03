"""Dynamic Statistics refer to a set of statistics that are obtained from an actual
Tracer run. These statistics can be used in subsequent runs to optimize the profiling.

Currently, the statistics are divided into four distinct categories:
1) Global Stats aggregate statistics across all of the bottom* processes.
2) Per-thread Stats contain statistics on a per-thread basis, i.e., the statistics
   are computed for each thread separately.
3) Process Hierarchy contains traced processes and their parents (ppid), children
   and spawned threads.
4) Threads that are spawned by traced processes during the profiling.

*bottom processes are those that spawn no other process
"""

import array
import collections
import dataclasses

import numpy as np

# The quartiles
_Q1, _Q2, _Q3 = 25, 50, 75


# Remember the thread PID and duration
@dataclasses.dataclass
class _Thread:
    __slots__ = ["pid", "duration"]

    pid: int
    duration: int


class DynamicStats:
    """The Dynamic Statistics class that computes and stores the statistics

    :ivar global_stats: the global statistics for each function: uid -> stats
    :ivar per_thread: per-thread statistics for each function: tid -> uid -> stats
    :ivar process_hierarchy: traced process details: pid -> details
    :ivar threads: spawned threads details: tid -> _Thread (pid, duration)
    """

    def __init__(self):
        self.global_stats = {}
        self.per_thread = {}
        # For each process, we want to know the parent, children, threads and bottom/level
        self.process_hierarchy = collections.defaultdict(
            lambda: {
                "ppid": list(),
                "spawn": list(),
                "threads": list(),
                "bottom": False,
                "level": 0,
            }
        )
        # tid -> (pid, duration)
        self.threads = {}

    @classmethod
    def from_profile(cls, stats_data, probed_functions):
        """Create Dynamic Stats from profile object.

        :param stats_data: compact summary of collected data
        :param probed_functions: profiled functions and their profiling configuration

        :return: the dynamic statistics object
        """
        stats = cls()
        func_values, process_records = stats_data["f"], stats_data["p"]
        stats.threads = stats_data["t"]

        # func_values, process_records = stats._process_resources_of(profile)
        stats.compute_process_hierarchy(process_records)
        stats.compute_global(func_values, probed_functions)
        stats.compute_per_thread(func_values, probed_functions)
        return stats

    @classmethod
    def from_dict(cls, stats_dict):
        """Create Dynamic Stats from dictionary -
        preferably obtained from dynamic stats json cache file.

        :param stats_dict: dictionary containing global, per-thread, process and thread stats

        :return: the dynamic statistics object
        """
        stats = cls()
        stats.global_stats = stats_dict["global_stats"]
        stats.per_thread = stats_dict["per_thread"]
        stats.process_hierarchy = stats_dict["process_hierarchy"]
        stats.threads = stats_dict["thread"]
        return stats

    def to_dict(self):
        """Serialize the DynamicStats object to a simple dictionary that can be stored in a file.

        :return: serialized DynamicStats object
        """
        # First convert the defaultdict to plain dict
        if not isinstance(self.process_hierarchy, dict):
            self.process_hierarchy = dict(self.process_hierarchy)
        # Create JSON serializable dictionary
        stats = {
            "global_stats": self.global_stats,
            "per_thread": self.per_thread,
            "process_hierarchy": self.process_hierarchy,
            "thread": self.threads,
        }
        return stats

    def _process_resources_of(self, profile):
        """Iterate profile resources and classify them to function, process and thread resources.

        :param profile: performance profile with collected resources

        :return: function resources (tid -> uid -> [amounts]), processes (pid -> [processes])
        """
        # tid -> uid -> [amounts]
        funcs = collections.defaultdict(lambda: collections.defaultdict(list))
        # pid -> [processes]
        # We expect that certain processes can be exec'd, so one PID can have multiple processes
        processes = collections.defaultdict(list)
        for _, resource in profile.all_resources():
            try:
                if resource["uid"] in ("!ProcessResource!", "!ThreadResource!"):
                    # Process resources automatically create internal process and thread records
                    self.threads[resource["tid"]] = _Thread(resource["pid"], resource["amount"])
                    if resource["uid"] == "!ProcessResource!":
                        processes[resource["pid"]].append(resource)
                else:
                    # Function resources are aggregated by TID and UID
                    funcs[resource["tid"]][resource["uid"]].append(
                        (resource["amount"], resource["exclusive"])
                    )
            except KeyError:
                pass
        return funcs, processes

    def compute_process_hierarchy(self, processes):
        """Build the process hierarchy structure based on the process resources.

        :param processes: processes dictionary with PID as keys
        """
        # Create the parent-child connection in the hierarchy
        for pid, procs in processes.items():
            for ppid, amount in procs:
                self.process_hierarchy[ppid]["spawn"].append(pid)
                self.process_hierarchy[pid]["ppid"].append(ppid)
                self.process_hierarchy[pid]["duration"] = amount
        # Register spawned threads for each process
        for tid, thread in self.threads.items():
            self.process_hierarchy[thread[0]]["threads"].append(tid)

        # We denote processes that spawn no other processes as bottom
        for proc in self.process_hierarchy.values():
            # Ensure that the lists have only unique values
            proc["ppid"] = list(set(proc["ppid"]))
            proc["spawn"] = list(set(proc["spawn"]))
            proc["threads"] = list(set(proc["threads"]))
            if not proc["spawn"]:
                proc["bottom"] = True

        # Estimate the process level (i.e., its hierarchy depth)
        self._compute_process_level()
        # Transform defaultdict to dict
        self.process_hierarchy = dict(self.process_hierarchy)

    def _compute_process_level(self):
        """Process level characterizes the nestedness level of a process based on the number of
        traced parent processes, e.g.:

        p1 (spawns p2): 0
         p2 (spawns p3, p4): 1
          p3: 2
          p4: 2
        """
        # Approximate the level and find the bottom processes
        top = {pid for pid, proc in self.process_hierarchy.items() if not proc["ppid"]}
        visited = set(top)
        level = 0
        while top:
            # Get all processes that top spawned, except those already processed
            spawned = set()
            for pid in top:
                spawned |= set(self.process_hierarchy[pid]["spawn"])
            spawned -= visited
            # Set the level of the spawned processes
            level += 1
            for pid in spawned:
                self.process_hierarchy[pid]["level"] = level
            # Add the spawned processes to the visited set
            visited |= spawned
            # The spawned processes are now the top ones
            top = spawned

    def compute_global(self, func_values, probed_funcs):
        """Compute global statistics across all bottom processes. Currently, we limit ourselves
        to bottom processes only since we do not have access to exclusive time of functions
        that would be needed otherwise.

        :param func_values: function amount values on a per-thread basis
        :param probed_funcs: profiled functions and their profiling configuration
        """
        # TODO: Currently only bottom-level records are used in global dynamic stats
        # TODO: Seems like the only proper solution would be to use exclusive times instead
        # Eliminate processes that are not bottom, or both are and aren't (e.g., because of exec)
        processes = set(pid for pid, proc in self.process_hierarchy.items() if proc["bottom"])

        # Merge values from the selected processes
        # TODO: how to handle multiple parallel threads in terms of global stats? Currently additive
        merged = collections.defaultdict(lambda: {"e": array.array("Q"), "i": array.array("Q")})
        for tid, tid_funcs in func_values.items():
            # Filter function records that should not be part of the global stats
            if tid in self.threads and self.threads[tid][0] in processes:
                # Otherwise merge them
                for func_name, values in tid_funcs.items():
                    merged[func_name]["i"].extend(values["i"])
                    merged[func_name]["e"].extend(values["e"])
        self.global_stats = _compute_funcs_stats(merged, probed_funcs)

    def compute_per_thread(self, func_values, probed_funcs):
        """Compute per-thread statistics across all threads

        :param func_values: function amount values on a per-thread basis
        :param probed_funcs: profiled functions and their profiling configuration
        """
        self.per_thread = {
            tid: _compute_funcs_stats(uids, probed_funcs)
            for tid, uids in func_values.items()
            if tid in self.threads
        }


def _compute_funcs_stats(source, probed_funcs):
    """Compute the dynamic statistics for a whole collection of functions.

    :param source: dictionary of collected data per function
    :param probed_funcs: profiled functions and their profiling configuration

    :return: computed statistics per each function
    """
    return {
        uid: _compute_func_stats(amounts, probed_funcs[uid]["sample"])
        for uid, amounts in source.items()
    }


def _compute_func_stats(values, func_sample):
    """Compute the dynamic statistics for the given values and sample.

    :param values: the measured function call durations
    :param func_sample: the sampling configuration of the given function

    :return: the computed statistics
    """
    # Sort the 'amount' values in order to compute various statistics
    # inclusive, exclusive = map(list, zip(*values))
    inclusive = np.array(values["i"])
    inclusive.sort()
    exclusive = values["e"]

    percentiles = np.percentile(inclusive, [_Q1, _Q2, _Q3])
    func_stats = {
        "count": len(inclusive) + ((len(inclusive) - 1) * (func_sample - 1)),
        "sampled_count": len(inclusive),
        "sample": func_sample,
        "total_exclusive": sum(exclusive),
        "total": sum(inclusive),
        "min": int(inclusive[0]),
        "max": int(inclusive[-1]),
        "avg": sum(inclusive) / len(inclusive),
        "Q1": percentiles[0],
        "median": percentiles[1],
        "Q3": percentiles[2],
    }
    func_stats["IQR"] = func_stats["Q3"] - func_stats["Q1"]
    return func_stats
