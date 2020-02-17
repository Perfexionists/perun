""" The Probes class stores the probe specification as well as several other related parameters.
"""

from enum import Enum

from perun.collect.trace.values import Strategy, DEFAULT_SAMPLE
from perun.utils.helpers import SuppressedExceptions


class Probes:
    """ Stores the function and USDT probe specifications, extraction strategy, global sampling etc.

    :ivar dict func: the function probes specification with function name as the key
    :ivar dict usdt: the USDT probes specification
    :ivar list sampled_func: a list of function names that are sampled
    :ivar list sampled_usdt: a list of USDT names that are sampled
    :ivar dict usdt_reversed: a reverse USDT pairs mapping
    :ivar Strategy strategy: the probes extraction strategy
    :ivar bool with_usdt: specifies if USDT probes should be collected
    :ivar int global_sampling: a sampling value applied to all the probes, if specific sampling is
                               not provided by the user
    """
    def __init__(self, **cli_config):
        """ Constructs the Probes object using the CLI parameters.

        :param cli_config: the CLI configuration
        """
        # The dicts of function and USDT probes
        self.func = {}
        self.usdt = {}
        # Store the sampled probe names for easier future access
        self.sampled_func = []
        self.sampled_usdt = []
        # Store the user-specified functions separately
        self.user_func = {}
        # Store the USDT reverse mapping
        self.usdt_reversed = None
        # Get the specified strategy and convert it to the Strategy enum
        self.strategy = Strategy(cli_config.get('strategy', Strategy.default()))
        self.with_usdt = cli_config.get('with_usdt', True)

        # Normalize global sampling
        global_sampling = cli_config.get('global_sampling', DEFAULT_SAMPLE)
        self.global_sampling = 1 if global_sampling < 1 else global_sampling
        # Set the default sampling if sampled strategy is selected but sampling is not provided
        if (self.strategy in (Strategy.Userspace_sampled, Strategy.All_sampled) and
                self.global_sampling == 1):
            self.global_sampling = DEFAULT_SAMPLE

        # Parse the supplied specification
        func_probes = list(cli_config.get('func', ''))
        usdt_probes = list(cli_config.get('usdt', ''))
        for probe in func_probes:
            parsed = self._parse_probe(probe, ProbeType.Func)
            self.user_func[parsed['name']] = parsed
        # Process the USDT probes only if enabled
        if self.with_usdt:
            for probe in usdt_probes:
                parsed = self._parse_probe(probe, ProbeType.USDT)
                self.usdt[parsed['name']] = parsed

    def _parse_probe(self, probe_specification, probe_type):
        """ Parses the given probe specification in format <lib>#<probe>#<sampling> into the
        separate components and builds the probe dictionary.

        :param str probe_specification: the probe specification as a string
        :param ProbeType probe_type: the type of the probe

        :return dict: the created probe dictionary
        """
        parts = probe_specification.split('#')
        name, lib, sample = None, None, self.global_sampling
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
        pair = name if probe_type == ProbeType.Func else None
        sample = sample if sample > 1 else 1
        # Create the probe dictionary
        return self.create_probe_record(name, probe_type, pair=pair, lib=lib, sample=sample)

    @staticmethod
    def create_probe_record(
            name, probe_type, pair=None, lib=None, sample=1, sample_index=-1, probe_id=-1
    ):
        """ Build the probe dictionary according to the given parameters

        :param str name: the name of probed function or USDT
        :param ProbeType probe_type: the type of the probe
        :param str pair: the name of the paired probe, used only by the USDT probes
        :param str lib: a library (if any) which contains the specified probe
        :param int sample: the probe sampling value
        :param int sample_index: a sampling index, used during the script / program assembling
        :param int probe_id: a unique probe identification

        :return dict: the resulting probe dictionary
        """
        return {
            'type': probe_type,
            'name': name,
            'pair': pair,
            'lib': lib,
            'sample': sample,
            'sample_index': sample_index,
            'id': probe_id
        }

    def add_probe_ids(self):
        """ Adds unique probe and sampling identification to all the function and USDT probes.
        """
        probe_id = 0
        sample_index = 0
        self.sampled_func, self.sampled_usdt = [], []
        # Iterate all probe lists
        for probe_collection in [self.func, self.usdt]:
            for probe in sorted(probe_collection.values(), key=lambda value: value['name']):
                # Add a unique id to the probe
                probe['id'] = probe_id
                probe_id += 1
                # Index probes that actually have sampling
                if probe['sample'] > 1:
                    probe['sample_index'] = sample_index
                    sample_index += 1
                    # Add the probe name to a sampled list for easier future retrieval
                    self._register_sampled_probe(probe['name'], probe['type'])
        return probe_id - 1

    def _register_sampled_probe(self, probe_name, probe_type):
        """ Stores a record about sampled probe into the sampled list based on the probe type

        :param str probe_name: the name of the probe
        :param ProbeType probe_type: the type of the probe
        """
        if probe_type == ProbeType.Func:
            self.sampled_func.append(probe_name)
        else:
            self.sampled_usdt.append(probe_name)

    def get_sampled_probes(self):
        """ Provides the dictionary of all the sampled probes from all the probe sources (i.e.
        func and USDT).

        :return iterable: a generator object which provides the dictionaries
        """
        # Generate the sequence of sampled probes from all the sources
        for probes, sampled in [(self.func, self.sampled_func), (self.usdt, self.sampled_usdt)]:
            for probe_name in sampled:
                yield probes[probe_name]


class ProbeType(str, Enum):
    """ A definition of the supported Probe types.

    Inherited from the str class so that JSON encoder can serialize it
    """
    Func = 'F'
    USDT = 'U'
