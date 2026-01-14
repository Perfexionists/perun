from __future__ import annotations

# Standard Imports
from collections import defaultdict
import enum
from typing import Type, Any, Callable, TYPE_CHECKING

# Third-Party Imports

# Perun Imports

if TYPE_CHECKING:
    from perun import profile


DEFAULT_AGGREGATE_FUNC: str = "median"

FG_DEFAULT_IMAGE_WIDTH: int = 800
FG_DEFAULT_MIN_WIDTH: float = 0.1

DEFAULT_MAX_FUNCTION_TRACES: int = 10
DEFAULT_TOP_DIFFS: int = 50
DEFAULT_FUNCTION_THRESHOLD: float = 0.1
DEFAULT_TRACE_THRESHOLD: float = 0.001
DEFAULT_SQUASH_RE: str = r".*"


class HeaderDisplayStyle(enum.Enum):
    """Supported styles of displaying profile specification and metadata."""

    FULL = "full"
    DIFF = "diff"

    @staticmethod
    def supported() -> list[str]:
        """Obtain the collection of supported display styles.

        :return: the collection of valid display styles
        """
        return [style.value for style in HeaderDisplayStyle]

    @staticmethod
    def default() -> str:
        """Provide the default display style.

        :return: the default display style
        """
        return HeaderDisplayStyle.FULL.value


def singleton_class(cls: Type[Any]) -> Callable[[], Config]:
    """Helper class for creating singleton objects"""
    instances = {}

    def getinstance() -> Config:
        """Singleton instance"""
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance


@singleton_class
class Config:
    """Singleton config for generation of sankey graphs

    :ivar trace_is_inclusive: whether then the amounts are distributed among the whole traces
    """

    DefaultTopN: int = 10
    DefaultRelativeThreshold: float = 0.01
    DefaultHeightCoefficient: int = 50

    def __init__(self) -> None:
        """Initializes the config

        By default, we consider that the traces are not inclusive
        """
        self.trace_is_inclusive: bool = False
        self.top_n_traces: int = self.DefaultTopN
        self.relative_threshold = self.DefaultRelativeThreshold
        self.max_seen_trace: int = 0
        self.max_per_resource: dict[str, float] = defaultdict(float)
        self.minimize: bool = False
        self.profile_stats: dict[str, list[profile.ProfileStat]] = {
            "baseline": [],
            "target": [],
        }
