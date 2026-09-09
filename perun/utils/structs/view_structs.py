"""Helper structures and constants for (diff) view modules."""

from __future__ import annotations

# Standard Imports
from typing import Any, ClassVar

# Third-Party Imports

# Perun Imports


DEFAULT_SQUASH_RE: str = r".*"


class FlameGraphSettings:
    """A collection of flamegraph parameters and settings to be used when rendering flamegraphs.

    :ivar width: the width of the flamegraph image
    :ivar height: the height of each function frame in the flamegraph
    :ivar min_width: the minimum width of a function frame, either pixels or percentage of time
    :ivar maxtrace: the longest trace in the flamegraph, should account for the min_width filtering
    :ivar fonttype: the font type
    :ivar fontsize: the font size
    :ivar countname: the resource type used in the profile, e.g., samples or CPU cycles
    :ivar colors: the color palette to use for frames
    :ivar bgcolors: the image background color
    :ivar inverted: whether an icicle graph should be rendered instead
    :ivar rootnode: the root node name
    :ivar subrootnode: the sub-root node name
    :ivar total: the total amount of consumed resources
    :ivar normalize: normalize the sample counts in differential graphs
    :ivar parallelize: parallelize the creation of flamegraph grids
    :ivar use_perl: use the Perl variants of flame graph scripts
    """

    __slots__ = (
        "width",
        "height",
        "min_width",
        "maxtrace",
        "fonttype",
        "fontsize",
        "countname",
        "colors",
        "bgcolors",
        "inverted",
        "rootnode",
        "subrootnode",
        "total",
        "normalize",
        "parallelize",
        "use_perl",
    )

    # Default flamegraph parameters reconstructed from the flamegraph.pl script.
    DefaultImageWidth: ClassVar[int] = 1200
    DefaultFrameHeight: ClassVar[int] = 16
    DefaultMinWidth: ClassVar[str] = "0.1"
    DefaultMaxTrace: ClassVar[int] = 0
    DefaultFontType: ClassVar[str] = "Verdana"
    DefaultFontSize: ClassVar[int] = 12
    DefaultCountName: ClassVar[str] = "samples"
    DefaultColors: ClassVar[str] = "hot"
    DefaultBgColors: ClassVar[str] = ""
    DefaultInverted: ClassVar[bool] = False
    DefaultRootNode: ClassVar[str] = "all"
    DefaultSubRootNode: ClassVar[str] = "subtotal"
    DefaultTotal: ClassVar[int] = 0

    # The map links the attribute names and their default values for easier iteration over the
    # keyword parameters. This map ignores the flags, e.g., 'inverted'.
    KwAttributeMap: ClassVar[dict[str, int | str]] = {
        "width": DefaultImageWidth,
        "height": DefaultFrameHeight,
        "min_width": DefaultMinWidth,
        "maxtrace": DefaultMaxTrace,
        "fonttype": DefaultFontType,
        "fontsize": DefaultFontSize,
        "countname": DefaultCountName,
        "colors": DefaultColors,
        "bgcolors": DefaultBgColors,
        "rootnode": DefaultRootNode,
        "subrootnode": DefaultSubRootNode,
        "total": DefaultTotal,
    }

    def __init__(
        self,
        width: int = DefaultImageWidth,
        height: int = DefaultFrameHeight,
        min_width: str = DefaultMinWidth,
        maxtrace: int = DefaultMaxTrace,
        fonttype: str = DefaultFontType,
        fontsize: int = DefaultFontSize,
        countname: str = DefaultCountName,
        colors: str = DefaultColors,
        bgcolors: str = DefaultBgColors,
        inverted: bool = DefaultInverted,
        rootnode: str = DefaultRootNode,
        subrootnode: str = DefaultSubRootNode,
        total: int = DefaultTotal,
        normalize: bool = False,
        parallelize: bool = True,
        use_perl_scripts: bool = False,
        **_: Any,
    ) -> None:
        """
        :param width: the width of the flamegraph image
        :param height: the height of each function frame in the flamegraph
        :param min_width: the minimum width of a function frame, either pixels or percentage of time
        :param maxtrace: the longest trace in the flamegraph after the min_width filtering
        :param fonttype: the font type
        :param fontsize: the font size
        :param countname: the resource type used in the profile, e.g., samples or CPU cycles
        :param colors: the color palette to use for frames
        :param bgcolors: the image background color
        :param inverted: whether an icicle graph should be rendered instead
        :param rootnode: the root node name
        :param subrootnode: the sub-root node name
        :param total: the total amount of consumed resources
        :param parallelize: parallelize the creation of flamegraph grids
        :param use_perl_scripts: use the Perl variants of flame graph scripts
        """
        # We call the type conversion functions since the parameters may be supplied from CLI
        # where the types do not necessarily have to match.
        self.width: int = int(width)
        self.height: int = int(height)
        self.min_width: str = str(min_width)
        self.maxtrace: int = int(maxtrace)
        self.fonttype: str = str(fonttype)
        self.fontsize: int = int(fontsize)
        self.countname: str = str(countname)
        self.colors: str = str(colors)
        self.bgcolors: str = str(bgcolors)
        self.inverted: bool = bool(inverted)
        self.rootnode: str = str(rootnode)
        self.subrootnode: str = str(subrootnode)
        self.total: int = int(total)
        self.normalize: bool = bool(normalize)

        self.parallelize: bool = parallelize
        self.use_perl = use_perl_scripts

    @classmethod
    def from_cli(cls, **cli_kwargs: Any) -> FlameGraphSettings:
        """Initialize the flamegraph settings from CLI and init parameters.

        The parameters supplied through CLI will have a 'flamegraph_' prefix. Parameters supplied
        additionally by the caller (e.g., to overwrite certain CLI parameters) do not have to use
        the prefix. However, the order of specification matters: in order to overwrite CLI
        parameters, the additional parameters need to be specified after the CLI parameters.

        :param cli_kwargs: the CLI parameters
        :return: an initialized FlameGraphSettings instance
        """
        return cls(
            **{
                arg_name.replace("flamegraph_", ""): arg_value
                for arg_name, arg_value in cli_kwargs.items()
                if arg_value is not None
            }
        )

    def get_nondefault_kw_attributes(self) -> dict[str, str | int]:
        """Construct a collection of keyword attributes that have non-default values.

        :return: a dictionary of all keyword attributes with non-default values
        """
        params: dict[str, str | int] = {}
        for attr_name, attr_default_value in self.KwAttributeMap.items():
            if (value := getattr(self, attr_name)) != attr_default_value:
                params[attr_name] = value
        return params

    def compute_minwidth_threshold(self) -> float:
        """Compute the minimum width threshold for flamegraph blocks to be displayed.

        The threshold is needed to correctly compute the maxtrace value so that flamegraphs in
        a grid are correctly aligned and have the appropriate height.

        Reconstructed from the flamegraph.pl script.

        :return: the minimum width threshold
        """
        try:
            # The minimum width was provided as a percentage
            if self.min_width.endswith("%"):
                return self.total * float(self.min_width[:-1]) / 100
            # The minimum width is set in pixels
            x_padding: int = 10
            width_per_time: float = (self.width - 2 * x_padding) / self.total
            return float(self.min_width) / width_per_time
        except ZeroDivisionError:
            # No total provided, we set the threshold so that it does not filter anything.
            return 0.0
