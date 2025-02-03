"""A module containing the necessary constants, enumerations, classes, etc., that have to be used
by numerous other modules.
"""

import os
import math
from functools import partial

from enum import Enum
from perun.utils.structs.common_structs import OrderedEnum
from perun.utils.common import common_kit
import perun.utils.metrics as metrics
from perun.utils.structs import collect_structs


class DiffCfgMode(Enum):
    """Enumeration of the currently supported CFG comparison mode."""

    COLORING = "color"
    SOFT = "soft"
    SEMISTRICT = "semistrict"
    STRICT = "strict"

    @staticmethod
    def supported():
        """List the currently supported CFG comparison modes.

        :return: CLI names of the supported modes
        """
        return [mode.value for mode in DiffCfgMode]


class CGShapingMode(Enum):
    """Enumeration of the currently supported Call Graph Shaping modes."""

    MATCH = "match"
    BOTTOM_UP = "bottom-up"
    TOP_DOWN = "top-down"

    @staticmethod
    def supported():
        """List the currently supported Call Graph Shaping modes.

        :return: CLI names of the supported modes
        """
        return [mode.value for mode in CGShapingMode]


class ThresholdMode(Enum):
    """Enumeration of the currently supported threshold modes."""

    SOFT = "soft"
    STRICT = "strict"

    @staticmethod
    def supported():
        """List the currently supported Threshold modes.

        :return: CLI names of the supported modes
        """
        return [mode.value for mode in ThresholdMode]


class Complexity(OrderedEnum):
    """Enumeration of the complexity degrees that we distinguish in the Bounds collector output."""

    # Polynomial-to-complexity map
    _ignore_ = ["map"]

    # Complexities
    ZERO = "zero"
    CONSTANT = "constant"
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    CUBIC = "cubic"
    QUARTIC = "quartic"
    GENERIC = "generic"

    @staticmethod
    def supported():
        """List the currently supported Complexity degrees.

        :return: CLI names of the supported complexities
        """
        return [complexity.value for complexity in Complexity]

    @staticmethod
    def max(values):
        """Compare a collection of Complexity values and select the one with maximum degree.

        :param values: the set of Complexity values

        :return: the Complexity object with the highest degree of polynomial
        """
        return sorted(values, key=lambda complexity: complexity.order, reverse=True)[0]

    @classmethod
    def from_poly(cls, polynomial):
        """Create a Complexity object from string representing a polynomial.

        :param polynomial: a string representation of a supported polynomial

        :return: the corresponding Complexity object
        """
        return Complexity.map.get(polynomial, cls.GENERIC)


Complexity.map = {  # type: ignore # static variable, that cannot be initialized anywhere else
    "O(1)": Complexity.CONSTANT,
    "O(n^1)": Complexity.LINEAR,
    "O(n^2)": Complexity.QUADRATIC,
    "O(n^3)": Complexity.CUBIC,
    "O(n^4)": Complexity.QUARTIC,
}


class ParametersManager:
    """Class that parses and stores the user-supplied optimization parameters, as well as predicts
    suitable values for the optimization parameters that were not supplied.

    :ivar cli_params: contains the list of user-supplied parameters before they are applied
    :ivar param_map: stores the default values for all parameters and provides a function
                          to validate the user-supplied values.

    """

    def __init__(self):
        """Initializes all of the optimization parameters to their default values."""
        # Keep leaves when the number of profiled functions is low enough
        self._functions_keep_leaves = 20
        # Keep top 10% of call graph levels, however minimum of 1
        self._keep_top_ratio = 0.1
        self._default_keep_top = 1
        # Call graph default levels to keep: top 50%, minimum 2 levels
        self._levels_ratio = 0.5
        self._default_min_levels = 2
        # Pruning chain length: minimum 1 - i.e. only leaf nodes kept
        self._default_chain_length = 1
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
            # TODO: add proper check
            collect_structs.Parameters.DIFF_VERSION: {"value": None, "validate": lambda x: x},
            collect_structs.Parameters.DIFF_KEEP_LEAF: {
                "value": False,
                "validate": self._validate_bool,
            },
            collect_structs.Parameters.DIFF_INSPECT_ALL: {
                "value": True,
                "validate": self._validate_bool,
            },
            collect_structs.Parameters.DIFF_CG_MODE: {
                "value": DiffCfgMode.SEMISTRICT,
                "validate": partial(self._validate_enum, DiffCfgMode),
            },
            collect_structs.Parameters.SOURCE_FILES: {"value": [], "validate": self._validate_path},
            collect_structs.Parameters.SOURCE_DIRS: {"value": [], "validate": self._validate_path},
            collect_structs.Parameters.STATIC_COMPLEXITY: {
                "value": Complexity.CONSTANT,
                "validate": partial(self._validate_enum, Complexity),
            },
            collect_structs.Parameters.STATIC_KEEP_TOP: {
                "value": self._default_keep_top,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.CG_SHAPING_MODE: {
                "value": CGShapingMode.MATCH,
                "validate": partial(self._validate_enum, CGShapingMode),
            },
            collect_structs.Parameters.CG_PROJ_LEVELS: {
                "value": self._default_chain_length,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.CG_PROJ_KEEP_LEAF: {
                "value": False,
                "validate": self._validate_bool,
            },
            collect_structs.Parameters.DYNSAMPLE_STEP: {
                "value": self._default_sampling_step,
                "validate": self._validate_ufloat,
            },
            collect_structs.Parameters.DYNSAMPLE_THRESHOLD: {
                "value": self._threshold_soft_base,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.PROBING_THRESHOLD: {
                "value": self._probing_threshold,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.PROBING_REATTACH: {
                "value": False,
                "validate": self._validate_bool,
            },
            collect_structs.Parameters.TIMEDSAMPLE_FREQ: {
                "value": 1,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.DYNBASE_SOFT_THRESHOLD: {
                "value": self._threshold_soft_base,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.DYNBASE_HARD_THRESHOLD: {
                "value": self._threshold_soft_base * self._hard_threshold_coefficient,
                "validate": self._validate_uint,
            },
            collect_structs.Parameters.THRESHOLD_MODE: {
                "value": ThresholdMode.SOFT,
                "validate": partial(self._validate_enum, ThresholdMode),
            },
        }

    def __getitem__(self, item):
        """Allows quick access to parameter values in the param_map

        :param item: the parameter we want value for

        :return: the corresponding value
        """
        return self.param_map[item]["value"]

    def __setitem__(self, key, value):
        """Allows to directly set param_map values

        :param key: the parameter to change
        :param value: the new value
        """
        self.param_map[key]["value"] = value

    def add_cli_parameter(self, name, value):
        """Add new CLI parameter to the list of user-supplied arguments.

        :param name: the string representation of a Parameter
        :param value: the Parameter value

        :return: the parameter value if the validation is successful, else None
        """
        param = collect_structs.Parameters(name)
        validated = self.param_map[param]["validate"](value)
        if validated is not None:
            self.cli_params.append((param, validated))
            return validated
        return None

    def infer_params(self, call_graph, pipeline, binary):
        """Attempts to infer sensible default values for the parameters that were not supplied
        by the user. The prediction is done safely in several steps since various modes and
        parameters can affect other parameters as well.

        :param call_graph: the CGR instance
        :param pipeline: the currently selected pipeline
        :param binary: path to the executable binary
        """
        metrics.start_timer("optimization_parameters")
        func_count, level_count = 0, 0
        if call_graph is not None:
            func_count, level_count = len(call_graph.cg_map.keys()), len(call_graph.levels)
            # Update the default keep top according to the first call graph branching
            self._default_keep_top = call_graph.coverage_max_cut()[1] + 1
        # Extract the user-supplied modes and parameters
        modes = [
            collect_structs.Parameters.DIFF_CG_MODE,
            collect_structs.Parameters.CG_SHAPING_MODE,
            collect_structs.Parameters.THRESHOLD_MODE,
        ]
        cli_modes, cli_params = common_kit.partition_list(
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
        metrics.end_timer("optimization_parameters")

    def _infer_general_parameters(self, func_count, level_count):
        """Predicts parameters that are applied across multiple optimization methods.

        :param func_count: the number of extracted functions
        :param level_count: the amount of call graph levels
        """
        if func_count == 0 and level_count == 0:
            return
        # Keep the leaf functions if the total number of profiled functions is low
        if func_count <= self._functions_keep_leaves:
            self[collect_structs.Parameters.DIFF_KEEP_LEAF] = True
            self[collect_structs.Parameters.CG_PROJ_KEEP_LEAF] = True
        # Keep-top: 10% of levels, minimum is default
        keep_top = max(math.ceil(level_count * self._keep_top_ratio), self._default_keep_top)
        self[collect_structs.Parameters.STATIC_KEEP_TOP] = keep_top

    def _infer_modes(self, selected_pipeline, user_modes):
        """Predicts the mode parameters based on the used pipeline.

        :param selected_pipeline: the currently selected pipeline
        :param user_modes: list of pairs with user-specified modes
        """
        self[collect_structs.Parameters.DIFF_CG_MODE] = DiffCfgMode.COLORING
        self[collect_structs.Parameters.CG_SHAPING_MODE] = CGShapingMode.TOP_DOWN
        # The selected pipeline determines the used modes
        if selected_pipeline == collect_structs.Pipeline.BASIC:
            self[collect_structs.Parameters.THRESHOLD_MODE] = ThresholdMode.STRICT
        else:
            self[collect_structs.Parameters.THRESHOLD_MODE] = ThresholdMode.SOFT
        # Apply the user-supplied modes
        for mode_type, mode_value in user_modes:
            self[mode_type] = mode_value

    def _infer_cg_shaping_parameters(self, func_count, level_count):
        """Predicts the Call Graph Shaping parameters based on the number of functions and levels.

        :param func_count: the number of extracted functions
        :param level_count: the amount of call graph levels
        """
        if func_count == 0 and level_count == 0:
            return
        # Determine the number of trimmed levels
        trim_levels = round(level_count * self._levels_ratio)
        # Set the trim levels
        self[collect_structs.Parameters.CG_PROJ_LEVELS] = max(trim_levels, self._default_min_levels)

    def _infer_thresholds(self):
        """Infer the threshold values based on the selected modes."""
        # Determine the thresholds based on the mode
        base = self._threshold_soft_base
        if self[collect_structs.Parameters.THRESHOLD_MODE] == ThresholdMode.STRICT:
            base = self._threshold_strict_base
        # Set the threshold
        self[collect_structs.Parameters.DYNSAMPLE_THRESHOLD] = base
        self[collect_structs.Parameters.DYNBASE_SOFT_THRESHOLD] = base
        self[collect_structs.Parameters.DYNBASE_HARD_THRESHOLD] = (
            base * self._hard_threshold_coefficient
        )

    def _infer_dynamic_probing(self, cli_params):
        """Predict parameters and threshold values for Dynamic Probing .

        :param cli_params: a collection of user-supplied parameters
        """
        # Update the probing threshold if reattach is enabled and probing threshold is not set
        probing_threshold_set = collect_structs.Parameters.PROBING_THRESHOLD in [
            param for param, _ in cli_params
        ]
        if self[collect_structs.Parameters.PROBING_REATTACH] and not probing_threshold_set:
            probing_threshold = self._probing_threshold * self._probing_reattach_coefficient
            self[collect_structs.Parameters.PROBING_THRESHOLD] = probing_threshold

    def _extract_sources(self, binary):
        """Search for source files of the project in the binary directory, if none are given.

        :param binary: path to the binary executable
        """
        files, dirs = (
            self[collect_structs.Parameters.SOURCE_FILES],
            self[collect_structs.Parameters.SOURCE_DIRS],
        )
        # No need to extract if only source files are supplied
        if files and not dirs:
            return
        # If no files or directories are supplied, assume the binary directory contains sources
        if not files and not dirs:
            dirs.append(os.path.dirname(binary))

        # Save the sources
        self[collect_structs.Parameters.SOURCE_FILES] = list(set(_get_source_files(dirs, files)))

    @staticmethod
    def _validate_bool(value):
        """Bool validation function that accepts boolean values as 1 or 0.

        :param value: the boolean value to validate
        :return: the boolean value if the validation is successful
        """
        if value in ["0", "1"]:
            return bool(int(value))
        return None

    @staticmethod
    def _validate_uint(value):
        """Uint validation function.

        :param value: the uint value to validate
        :return: the uint value if the validation is successful
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
        """unsigned float validation function.

        :param value: the ufloat value to validate
        :return: the ufloat value if the validation is successful
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
        """Path validation function that takes string and resolves the path.

        :param path: the path to validate
        :return: fully resolved path if the validation is successful
        """
        if not os.path.exists(os.path.realpath(path)):
            return None
        return os.path.realpath(path)

    @staticmethod
    def _validate_enum(enumclass, value):
        """Validate if value is supported in the given enum class

        :param enumclass: Enum class
        :param value: value to check

        :return: Enum item corresponding to the given string value
        """
        return enumclass(value) if value in enumclass.supported() else None


def _get_source_files(dirs, files):
    """Get all source files in the supplied dirs and files

    :param dirs: list of directories
    :param files: list of files

    :return: list of file paths
    """
    candidate_files = []
    for src in dirs + files:
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                candidate_files.extend(os.path.join(root, file) for file in files)
        elif os.path.isfile(src):
            candidate_files.append(src)

    return [file for file in candidate_files if os.path.splitext(file)[1] == ".c"]
