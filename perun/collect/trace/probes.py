"""The Probes class stores the probe specification as well as several other related parameters."""

from enum import Enum

from perun.collect.trace.values import Strategy, DEFAULT_SAMPLE
from perun.utils.exceptions import SuppressedExceptions
from perun.utils.common.common_kit import partition_list


# TODO: change the API of probe retrieval to something universal and practical
class Probes:
    """Stores the function and USDT probe specifications, extraction strategy, global sampling etc.

    :ivar func: the function probes specification with function name as the key
    :ivar usdt: the USDT probes specification
    :ivar sampled_func: a list of function names that are sampled
    :ivar sampled_usdt: a list of USDT names that are sampled
    :ivar usdt_reversed: a reverse USDT pairs mapping
    :ivar strategy: the probes extraction strategy
    :ivar with_usdt: specifies if USDT probes should be collected
    :ivar global_sampling: a sampling value applied to all the probes, if specific sampling is
                               not provided by the user
    """

    # TODO: use the libraries to cross-check
    def __init__(self, main_binary, libraries, **cli_config):
        """Constructs the Probes object using the profiled binary and CLI parameters.

        :param main_binary: the main profiled binary
        :param libraries: a list of profiled libraries
        :param cli_config: the CLI configuration
        """
        # The dicts of function and USDT probes
        self.func = {}
        self.usdt = {}
        # TODO: remove, store the len instead
        # Store the sampled probe names for easier future access
        self.sampled_func = []
        self.sampled_usdt = []
        # Store the user-specified functions separately
        self.user_func = {}
        # Store the USDT reverse mapping
        self.usdt_reversed = None
        # Get the specified strategy and convert it to the Strategy enum
        self.strategy = Strategy(cli_config.get("strategy", Strategy.default()))
        self.with_usdt = cli_config.get("with_usdt", True)

        # Normalize global sampling
        global_sampling = cli_config.get("global_sampling", DEFAULT_SAMPLE)
        self.global_sampling = 1 if global_sampling < 1 else global_sampling
        # Set the default sampling if sampled strategy is selected but sampling is not provided
        if (
            self.strategy in (Strategy.USERSPACE_SAMPLED, Strategy.ALL_SAMPLED)
            and self.global_sampling == 1
        ):
            self.global_sampling = DEFAULT_SAMPLE

        # Parse the supplied specification
        # TODO: check that the probe and lib are valid
        func_probes = list(cli_config.get("func", ""))
        usdt_probes = list(cli_config.get("usdt", ""))
        self._add_probes(func_probes, self.user_func, ProbeType.FUNC, main_binary)
        # Process the USDT probes only if enabled
        if self.with_usdt:
            self._add_probes(usdt_probes, self.usdt, ProbeType.USDT, main_binary)

    def _add_probes(self, probe_set, storage, probe_type, binary):
        """Parse probes and store them in the appropriate storage.

        :param probe_set: list of probe names
        :param storage: target dictionary to store the probes into
        :param probe_type: type of the parsed probe
        :param binary: name of the binary file
        """
        for probe in probe_set:
            parsed = self._parse_probe(probe, probe_type, binary)
            storage[parsed["name"]] = parsed

    def _parse_probe(self, probe_specification, probe_type, binary):
        """Parses the given probe specification in format <lib>#<probe>#<sampling> into the
        separate components and builds the probe dictionary.

        :param probe_specification: the probe specification as a string
        :param probe_type: the type of the probe

        :return: the created probe dictionary
        """
        parts = probe_specification.split("#")
        name, lib, sample = None, binary, self.global_sampling
        # Only the probe name was given
        if len(parts) == 1:
            name = parts[0]
        # The possible combinations are <lib>#<name> or <name>#<sample>
        elif len(parts) == 2:
            try:
                sample = int(parts[1])
                name = parts[0]
            except ValueError:
                lib = parts[0]
                name = parts[1]
        # A full specification <lib>#<name>#<sample> was given
        elif len(parts) == 3:
            lib = parts[0]
            name = parts[1]
            # Attempt to convert the sample to int, keep the default global_sampling if it fails
            with SuppressedExceptions(ValueError):
                sample = int(parts[2])

        # Set the default pair for function and normalize specified sampling
        pair = name if probe_type == ProbeType.FUNC else None
        sample = sample if sample > 1 else 1
        # Create the probe dictionary
        return self.create_probe_record(name, probe_type, pair=pair, lib=lib, sample=sample)

    @staticmethod
    def create_probe_record(
        name, probe_type, pair=None, lib=None, sample=1, sample_index=-1, probe_id=-1
    ):
        """Build the probe dictionary according to the given parameters

        :param name: the name of probed function or USDT
        :param probe_type: the type of the probe
        :param pair: the name of the paired probe, used only by the USDT probes
        :param lib: a library (if any) which contains the specified probe
        :param sample: the probe sampling value
        :param sample_index: a sampling index, used during the script / program assembling
        :param probe_id: a unique probe identification

        :return: the resulting probe dictionary
        """
        return {
            "type": probe_type,
            "name": name,
            "pair": pair,
            "lib": lib,
            "sample": sample,
            "sample_index": sample_index,
            "id": probe_id,
        }

    def add_probe_ids(self):
        """Adds unique probe and sampling identification to all the function and USDT probes."""
        probe_id = 0
        sample_index = 0
        self.sampled_func, self.sampled_usdt = [], []
        # Iterate all probe lists
        for probe_collection in [self.func, self.usdt]:
            for probe in sorted(probe_collection.values(), key=lambda value: value["name"]):
                # Add a unique id to the probe
                probe["id"] = probe_id
                probe_id += 1
                # Index probes that actually have sampling
                if probe["sample"] > 1:
                    probe["sample_index"] = sample_index
                    sample_index += 1
                    # Add the probe name to a sampled list for easier future retrieval
                    self._register_sampled_probe(probe["name"], probe["type"])
        return probe_id - 1

    def _register_sampled_probe(self, probe_name, probe_type):
        """Stores a record about sampled probe into the sampled list based on the probe type

        :param probe_name: the name of the probe
        :param probe_type: the type of the probe
        """
        if probe_type == ProbeType.FUNC:
            self.sampled_func.append(probe_name)
        else:
            self.sampled_usdt.append(probe_name)

    def get_probes(self):
        """Return all function and USDT probes, sorted according to the name of the probe.

        :return: a generator object which provides the probe dictionaries
        """
        for probe_set in [self.func.values(), self.usdt.values()]:
            for probe in sorted(list(probe_set), key=lambda value: value["name"]):
                yield probe

    def get_partitioned_func_probes(self):
        """Return all registered function probes, sorted by name and partitioned into two lists
        based on the sampling: [sampled] and [unsampled] probes.

        :return: lists of sampled and unsampled function probes
        """
        return partition_list(
            sorted(list(self.func.values()), key=lambda value: value["name"]),
            lambda func: func["sample"] > 1,
        )

    def get_partitioned_usdt_probes(self):
        """Return all registered USDT probes, sorted by name and partitioned into three lists
        based on the sampling and probe type: [sampled (paired)], [unsampled (paired)] and
        [single (non-paired)] probes.

        :return: lists of sampled, unsampled and single USDT probes.
        """
        paired_sampled, paired_nonsampled, single = [], [], []
        # Sort the collection of USDT probes
        for probe in sorted(list(self.usdt.values()), key=lambda value: value["name"]):
            if probe["pair"] == probe["name"]:
                single.append(probe)
            elif probe["sample"] > 1:
                paired_sampled.append(probe)
            else:
                paired_nonsampled.append(probe)
        return paired_sampled, paired_nonsampled, single

    def get_sampled_probes(self):
        """Provides the dictionary of all the sampled probes from all the probe sources (i.e.
        func and USDT).

        :return: a generator object which provides the dictionaries
        """
        # Generate the sequence of sampled probes from all the sources
        for probes, sampled in [
            (self.func, self.sampled_func),
            (self.usdt, self.sampled_usdt),
        ]:
            for probe_name in sorted(sampled):
                yield probes[probe_name]

    def sampled_probes_len(self):
        """Counts the number of sampled function and USDT probes.

        :return: the number of sampled probes
        """
        return len(self.sampled_func) + len(self.sampled_usdt)

    def total_probes_len(self):
        """Counts the number of total function and USDT probes.

        :return: the total number of probes
        """
        return len(self.func.keys()) + len(self.usdt.keys())


def _retrieve_probes(probe_list):
    """Sort a list of probes by name and transform them to a generator

    :param probe_list: a list of probe dictionaries to generate
    :return: generator object
    """
    for probe in sorted(probe_list, key=lambda value: value["name"]):
        yield probe


class ProbeType(str, Enum):
    """A definition of the supported Probe types.

    Inherited from the str class so that JSON encoder can serialize it
    """

    FUNC = "F"
    USDT = "U"
