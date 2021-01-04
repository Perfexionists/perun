""" A module containing the necessary constants, enumerations, classes, etc., that have to be used
by numerous other modules.
"""


import os
import math
from enum import Enum
from perun.utils.structs import OrderedEnum
import perun.utils as utils
import perun.utils.metrics as metrics


class Optimizations(Enum):
    """ Enumeration of the implemented methods and their CLI name.
    """
    BaselineStatic = 'baseline-static'
    BaselineDynamic = 'baseline-dynamic'
    CallGraphShaping = 'cg-shaping'
    DynamicSampling = 'dynamic-sampling'
    DiffTracing = 'diff-tracing'
    DynamicProbing = 'dynamic-probing'
    TimedSampling = 'timed-sampling'

    @staticmethod
    def supported():
        """ List the currently supported optimization methods.

        :return list: CLI names of the supported optimizations
        """
        return [optimization.value for optimization in Optimizations]


class Pipeline(Enum):
    """ Enumeration of the implemented pipelines and their CLI name.
    Custom represents a defualt pipeline that has no pre-configured methods or parameters
    """
    Custom = 'custom'
    Basic = 'basic'
    Advanced = 'advanced'
    Full = 'full'

    @staticmethod
    def supported():
        """ List the currently supported optimization pipelines.

        :return list: CLI names of the supported pipelines
        """
        return [pipeline.value for pipeline in Pipeline]

    @staticmethod
    def default():
        """ Name of the default pipeline.

        :return str: the CLI name of the default pipeline
        """
        return Pipeline.Custom.value

    def map_to_optimizations(self):
        """ Map the selected optimization pipeline to the set of employed optimization methods.

        :return list: list of the Optimizations enumeration objects
        """
        if self == Pipeline.Basic:
            return [Optimizations.CallGraphShaping, Optimizations.BaselineDynamic]
        elif self == Pipeline.Advanced:
            return [
                Optimizations.DiffTracing, Optimizations.CallGraphShaping,
                Optimizations.BaselineDynamic, Optimizations.DynamicSampling
            ]
        elif self == Pipeline.Full:
            return [
                Optimizations.DiffTracing, Optimizations.CallGraphShaping,
                Optimizations.BaselineStatic, Optimizations.BaselineDynamic,
                Optimizations.DynamicSampling, Optimizations.DynamicProbing,
            ]
        else:
            return []


class CallGraphTypes(Enum):
    """ Enumeration of the implemented call graph types and their CLI names.
    """
    Static = 'static'
    Dynamic = 'dynamic'
    Mixed = 'mixed'

    @staticmethod
    def supported():
        """ List the currently supported call graph types.

        :return list: CLI names of the supported cg types
        """
        return [cg.value for cg in CallGraphTypes]

    @staticmethod
    def default():
        """ Name of the default cg type.

        :return str: the CLI name of the default cg type
        """
        return CallGraphTypes.Static.value


class Parameters(Enum):
    """ Enumeration of the currently supported CLI options for optimization methods and pipelines.
    """
    DiffKeepLeaf = 'diff-keep-leaf'
    DiffInspectAll = 'diff-inspect-all'
    DiffCfgMode = 'diff-cfg-mode'
    SourceFiles = 'source-files'
    SourceDirs = 'source-dirs'
    StaticComplexity = 'static-complexity'
    StaticKeepTop = 'static-keep-top'
    CGShapingMode = 'cg-mode'
    CGTrimLevels = 'cg-trim-levels'
    CGTrimMinFunctions = 'cg-trim-min-functions'
    CGTrimKeepLeaf = 'cg-trim-keep-leaf'
    CGPruneChainLength = 'cg-prune-chain-length'
    CGPruneKeepTop = 'cg-prune-keep-top'
    CGProjLevels = 'cg-proj-levels'
    CGProjKeepLeaf = 'cg-proj-keep-leaf'
    DynSampleStep = 'dyn-sample-step'
    DynSampleThreshold = 'dyn-sample-threshold'
    ProbingThreshold = 'probing-threshold'
    ProbingReattach = 'probing-reattach'
    TimedSampleFreq = 'timed-sample-freq'
    DynBaseSoftThreshold = 'dyn-base-soft-threshold'
    DynBaseHardThreshold = 'dyn-base-hard-threshold'
    ThresholdMode = 'threshold-mode'

    @staticmethod
    def supported():
        """ List the currently supported optimization parameters.

        :return list: CLI names of the supported parameters
        """
        return [parameter.value for parameter in Parameters]


class DiffCfgMode(Enum):
    """ Enumeration of the currently supported CFG comparison mode.
    """
    Coloring = 'color'
    Soft = 'soft'
    Semistrict = 'semistrict'
    Strict = 'strict'

    @staticmethod
    def supported():
        """ List the currently supported CFG comparison modes.

        :return list: CLI names of the supported modes
        """
        return [mode.value for mode in DiffCfgMode]


class CGShapingMode(Enum):
    """ Enumeration of the currently supported Call Graph Shaping modes.
    """
    Match = 'match'
    Prune = 'prune'
    Soft = 'soft'
    Strict = 'strict'
    Bottom_up = 'bottom-up'
    Top_down = 'top-down'

    @staticmethod
    def supported():
        """ List the currently supported Call Graph Shaping modes.

        :return list: CLI names of the supported modes
        """
        return [mode.value for mode in CGShapingMode]


class ThresholdMode(Enum):
    """ Enumeration of the currently supported threshold modes.
    """
    Soft = 'soft'
    Strict = 'strict'

    @staticmethod
    def supported():
        """ List the currently supported Threshold modes.

        :return list: CLI names of the supported modes
        """
        return [mode.value for mode in ThresholdMode]


class Complexity(OrderedEnum):
    """ Enumeration of the complexity degrees that we distinguish in the Bounds collector output.
    """
    Constant = 'constant'
    Linear = 'linear'
    Quadratic = 'quadratic'
    Cubic = 'cubic'
    Quartic = 'quartic'
    Generic = 'generic'

    @staticmethod
    def supported():
        """ List the currently supported Complexity degrees.

        :return list: CLI names of the supported complexities
        """
        return [complexity.value for complexity in Complexity if complexity != Complexity.Generic]

    @staticmethod
    def max(values):
        """ Compare a collection of Complexity values and select the one with maximum degree.

        :param collection values: the set of Complexity values

        :return Complexity: the Complexity object with the highest degree of polynomial
        """
        return sorted(values, key=lambda complexity: complexity.order, reverse=True)[0]

    @classmethod
    def from_poly(cls, polynomial):
        """ Create a Complexity object from string representing a polynomial.

        :param str polynomial: a string representation of a supported polynomial

        :return Complexity: the corresponding Complexity object
        """
        if polynomial == 'O(1)':
            return cls.Constant
        elif polynomial == 'O(n^1)':
            return cls.Linear
        elif polynomial == 'O(n^2)':
            return cls.Quadratic
        elif polynomial == 'O(n^3)':
            return cls.Cubic
        elif polynomial == 'O(n^4)':
            return cls.Quartic
        else:
            return cls.Generic


class ParametersManager:
    """ Class that parses and stores the user-supplied optimization parameters, as well as predicts
    suitable values for the optimization parameters that were not supplied.

    :ivar list cli_params: contains the list of user-supplied parameters before they are applied
    :ivar dict param_map: stores the default values for all parameters and provides a function
                          to validate the user-supplied values.

    """
    def __init__(self):
        """ Initializes all of the optimization parameters to their default values.
        """
        # Keep leaves when the number of profiled functions is low enough
        self._functions_keep_leaves = 20
        # Keep top 10% of call graph levels, however minimum of 1
        self._keep_top_ratio = 0.1
        self._default_keep_top = 1
        # Call graph levels based on CG mode: strict - 25%, soft - 50%, minimum 2 levels
        self._levels_strict_ratio = 0.25
        self._levels_soft_ratio = 0.5
        self._default_min_levels = 2
        # Pruning chain length: bottom 10% of the graph, minimum 1 - i.e. only leaf nodes removed
        self._chain_length_ratio = 0.1
        self._default_chain_length = 1
        # Minimum number of functions left after trimming is 10%, minimum 10
        self._min_functions_ratio = 0.1
        self._default_min_functions = 10
        # Default sampling step does not scale
        self._default_sampling_step = 2
        # Soft function call threshold for dynamic baseline / sampling is set 10000
        self._threshold_soft_base = 10000
        # Strict function call threshold is set to 1000
        self._threshold_strict_base = 1000
        # Hard function call threshold used by dynamic baseline is 100x more than the used threshold
        self._hard_threshold_coefficient = 100
        # Dynamic probing threshold is set to 100000, however multiplied by 0.2 in reattach mode
        self._probing_threshold = 100000
        self._probing_reattach_coefficient = 0.2

        self.cli_params = []
        self.param_map = {
            Parameters.DiffKeepLeaf: {
                'value': False,
                'validate': self._validate_bool
            },
            Parameters.DiffInspectAll: {
                'value': True,
                'validate': self._validate_bool
            },
            Parameters.DiffCfgMode: {
                'value': DiffCfgMode.Semistrict,
                'validate': lambda mode: DiffCfgMode(mode)
                if mode in DiffCfgMode.supported() else None
            },
            Parameters.SourceFiles: {
                'value': [],
                'validate': self._validate_path
            },
            Parameters.SourceDirs: {
                'value': [],
                'validate': self._validate_path
            },
            Parameters.StaticComplexity: {
                'value': Complexity.Constant,
                'validate': lambda complexity: Complexity(complexity)
                if complexity in Complexity.supported() else None
            },
            Parameters.StaticKeepTop: {
                'value': self._default_keep_top,
                'validate': self._validate_uint
            },
            Parameters.CGShapingMode: {
                'value': CGShapingMode.Match,
                'validate': lambda mode: CGShapingMode(mode)
                if mode in CGShapingMode.supported() else None
            },
            Parameters.CGTrimLevels: {
                'value': self._default_min_levels,
                'validate': self._validate_uint
            },
            Parameters.CGTrimMinFunctions: {
                'value': self._default_min_functions,
                'validate': self._validate_uint
            },
            Parameters.CGTrimKeepLeaf: {
                'value': False,
                'validate': self._validate_bool
            },
            Parameters.CGPruneChainLength: {
                'value': self._default_chain_length,
                'validate': self._validate_uint
            },
            Parameters.CGPruneKeepTop: {
                'value': self._default_keep_top,
                'validate': self._validate_uint
            },
            Parameters.CGProjLevels: {
                'value': self._default_chain_length,
                'validate': self._validate_uint
            },
            Parameters.CGProjKeepLeaf: {
                'value': False,
                'validate': self._validate_bool
            },
            Parameters.DynSampleStep: {
                'value': self._default_sampling_step,
                'validate': self._validate_ufloat
            },
            Parameters.DynSampleThreshold: {
                'value': self._threshold_soft_base,
                'validate': self._validate_uint
            },
            Parameters.ProbingThreshold: {
                'value': self._probing_threshold,
                'validate': self._validate_uint
            },
            Parameters.ProbingReattach: {
                'value': False,
                'validate': self._validate_bool
            },
            Parameters.TimedSampleFreq: {
                'value': 1,
                'validate': self._validate_uint
            },
            Parameters.DynBaseSoftThreshold: {
                'value': self._threshold_soft_base,
                'validate': self._validate_uint
            },
            Parameters.DynBaseHardThreshold: {
                'value': self._threshold_soft_base * self._hard_threshold_coefficient,
                'validate': self._validate_uint
            },
            Parameters.ThresholdMode: {
                'value': ThresholdMode.Soft,
                'validate': lambda mode: ThresholdMode(mode)
                if mode in ThresholdMode.supported() else None
            }
        }

    def __getitem__(self, item):
        """ Allows quick access to parameter values in the param_map

        :param Parameters item: the parameter we want value for

        :return object: the corresponding value
        """
        return self.param_map[item]['value']

    def __setitem__(self, key, value):
        """ Allows to directly set param_map values

        :param Parameters key: the parameter to change
        :param object value: the new value
        """
        self.param_map[key]['value'] = value

    def add_cli_parameter(self, name, value):
        """ Add new CLI parameter to the list of user-supplied arguments.

        :param str name: the string representation of a Parameter
        :param object value: the Parameter value

        :return object or None: the parameter value if the validation is successful, else None
        """
        param = Parameters(name)
        validated = self.param_map[param]['validate'](value)
        if validated is not None:
            self.cli_params.append((param, validated))
            return validated
        return None

    def infer_params(self, call_graph, pipeline, binary):
        """ Attempts to infer sensible default values for the parameters that were not supplied
        by the user. The prediction is done safely in several steps since various modes and
        parameters can affect other parameters as well.

        :param CallGraphResource call_graph: the CGR instance
        :param Pipeline pipeline: the currently selected pipeline
        :param str binary: path to the executable binary
        """
        metrics.start_timer('optimization_parameters')
        func_count, level_count = 0, 0
        if call_graph is not None:
            func_count, level_count = len(call_graph.cg_map.keys()), len(call_graph.levels)
            # Update the default keep top according to the first call graph branching
            self._default_keep_top = call_graph.coverage_max_cut()[1] + 1
        # Extract the user-supplied modes and parameters
        modes = [Parameters.DiffCfgMode, Parameters.CGShapingMode, Parameters.ThresholdMode]
        cli_modes, cli_params = utils.partition_list(
            self.cli_params, lambda param: param[0] in modes
        )

        # Infer general parameters (used in multiple methods) based on the call graph
        self._infer_general_parameters(func_count, level_count)
        # Infer modes used by some methods based on the pipeline
        self._infer_modes(pipeline, cli_modes)
        # Infer the call graph shaping parameters
        self._infer_cg_shaping_parameters(func_count, level_count)
        # Infer the thresholds used by various methods
        self._infer_thresholds()

        # Set user-supplied parameters to override the inferred ones
        for param_name, param_value in cli_params:
            if isinstance(self[param_name], list):
                self[param_name].append(param_value)
            else:
                self[param_name] = param_value

        # Infer the dynamic probing parameters
        self._infer_dynamic_probing(cli_params)
        # Extract source files based on the supplied parameters
        self._extract_sources(binary)
        metrics.end_timer('optimization_parameters')

    def _infer_general_parameters(self, func_count, level_count):
        """ Predicts parameters that are applied across multiple optimization methods.

        :param int func_count: the number of extracted functions
        :param int level_count: the amount of call graph levels
        """
        if func_count == 0 and level_count == 0:
            return
        # Keep the leaf functions if the total number of profiled functions is low
        if func_count <= self._functions_keep_leaves:
            self[Parameters.DiffKeepLeaf] = True
            self[Parameters.CGTrimKeepLeaf] = True
            self[Parameters.CGProjKeepLeaf] = True
        # Keep-top: 10% of levels, minimum is default
        keep_top = max(math.ceil(level_count * self._keep_top_ratio), self._default_keep_top)
        self[Parameters.CGPruneKeepTop] = keep_top
        self[Parameters.StaticKeepTop] = keep_top

    def _infer_modes(self, selected_pipeline, user_modes):
        """ Predicts the mode parameters based on the used pipeline.

        :param Pipeline selected_pipeline: the currently selected pipeline
        :param list user_modes: list of pairs with user-specified modes
        """
        # The selected pipeline determines the used modes
        if selected_pipeline == Pipeline.Basic:
            self[Parameters.DiffCfgMode] = DiffCfgMode.Soft
            self[Parameters.CGShapingMode] = CGShapingMode.Strict
            self[Parameters.ThresholdMode] = ThresholdMode.Strict
        elif selected_pipeline == Pipeline.Advanced:
            self[Parameters.DiffCfgMode] = DiffCfgMode.Semistrict
            self[Parameters.CGShapingMode] = CGShapingMode.Soft
            self[Parameters.ThresholdMode] = ThresholdMode.Soft
        elif selected_pipeline == Pipeline.Full:
            self[Parameters.DiffCfgMode] = DiffCfgMode.Strict
            self[Parameters.CGShapingMode] = CGShapingMode.Prune
            self[Parameters.ThresholdMode] = ThresholdMode.Soft
        # Apply the user-supplied modes
        for mode_type, mode_value in user_modes:
            self[mode_type] = mode_value

    def _infer_cg_shaping_parameters(self, func_count, level_count):
        """ Predicts the Call Graph Shaping parameters based on the number of functions and levels.

        :param int func_count: the number of extracted functions
        :param int level_count: the amount of call graph levels
        """
        if func_count == 0 and level_count == 0:
            return
        # Determine the number of trimmed levels based on the CG shaping mode
        trim_levels = 0
        if self[Parameters.CGShapingMode] == CGShapingMode.Strict:
            trim_levels = math.ceil(level_count * self._levels_strict_ratio)
        elif self[Parameters.CGShapingMode] in (CGShapingMode.Soft, CGShapingMode.Top_down,
                                                CGShapingMode.Bottom_up):
            trim_levels = round(level_count * self._levels_soft_ratio)

        # Set the trim levels, the chain length and the minimum number of functions
        self[Parameters.CGTrimLevels] = max(trim_levels, self._default_min_levels)
        self[Parameters.CGProjLevels] = max(trim_levels, self._default_min_levels)
        self[Parameters.CGPruneChainLength] = max(
            math.floor(level_count * self._chain_length_ratio), self._default_chain_length
        )
        self[Parameters.CGTrimMinFunctions] = max(
            math.ceil(func_count * self._min_functions_ratio), self._default_min_functions
        )

    def _infer_thresholds(self):
        """ Infer the threshold values based on the selected modes.
        """
        # Determine the thresholds based on the mode
        base = self._threshold_soft_base
        if self[Parameters.ThresholdMode] == ThresholdMode.Strict:
            base = self._threshold_strict_base
        # Set the threshold
        self[Parameters.DynSampleThreshold] = base
        self[Parameters.DynBaseSoftThreshold] = base
        self[Parameters.DynBaseHardThreshold] = base * self._hard_threshold_coefficient

    def _infer_dynamic_probing(self, cli_params):
        """ Predict parameters and threshold values for Dynamic Probing .

        :param list cli_params: a collection of user-supplied parameters
        """
        # Update the probing threshold if reattach is enabled and probing threshold is not set
        probing_threshold_set = Parameters.ProbingThreshold in [param for param, _ in cli_params]
        if self[Parameters.ProbingReattach] and not probing_threshold_set:
            probing_threshold = self._probing_threshold * self._probing_reattach_coefficient
            self[Parameters.ProbingThreshold] = probing_threshold

    def _extract_sources(self, binary):
        """ Search for source files of the project in the binary directory, if none are given.

        :param str binary: path to the binary executable
        """
        files, dirs = self[Parameters.SourceFiles], self[Parameters.SourceDirs]
        # No need to extract if only source files are supplied
        if files and not dirs:
            return
        # If no files or directories are supplied, assume the binary directory contains sources
        if not files and not dirs:
            dirs.append(os.path.dirname(binary))

        sources = []
        for src in dirs + files:
            if os.path.isdir(src):
                for root, _, files in os.walk(src):
                    for file in files:
                        if os.path.splitext(file)[1] in {'.c'}:
                            sources.append(os.path.join(root, file))
            elif os.path.splitext(src)[1] in {'.c'}:
                sources.append(src)
        # Save the sources
        self[Parameters.SourceFiles] = list(set(sources))

    @staticmethod
    def _validate_bool(value):
        """ Bool validation function that accepts boolean values as 1 or 0.

        :param str value: the boolean value to validate
        :return bool or None: the boolean value if the validation is successful
        """
        if value in ['0', '1']:
            return bool(int(value))
        return None

    @staticmethod
    def _validate_uint(value):
        """ Uint validation function.

        :param str value: the uint value to validate
        :return int or None: the uint value if the validation is successful
        """
        try:
            value = int(value)
            if value >= 0:
                return value
            return None
        except ValueError:
            return None

    @staticmethod
    def _validate_ufloat(value):
        """ unsigned float validation function.

        :param str value: the ufloat value to validate
        :return float or None: the ufloat value if the validation is successful
        """
        try:
            value = float(value)
            if value > 0:
                return value
            return None
        except ValueError:
            return None

    @staticmethod
    def _validate_path(path):
        """ Path validation function that takes string and resolves the path.

        :param str path: the path to validate
        :return str or None: fully resolved path if the validation is successful
        """
        if not os.path.exists(os.path.realpath(path)):
            return None
        return os.path.realpath(path)
