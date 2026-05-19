#!/usr/bin/env python3
"""flamegraph.py		flame stack grapher.

This takes stack samples and renders a call graph, allowing hot functions
and codepaths to be quickly identified.  Stack samples can be generated using
tools such as DTrace, perf, SystemTap, and Instruments.

USAGE: ./flamegraph.py [options] input.folded > graph.svg
       ./flamegraph.py [options] --outfile graph.svg input.folded
       grep funcA input.txt | ./flamegraph.pl [options] > graph.svg

Then open the resulting .svg in a web browser, for interactivity: mouse-over
frames for info, click to zoom, and ctrl-F to search.

Options are listed in the usage message (--help).

The input is stack frames and sample counts formatted as single lines.  Each
frame in the stack is semicolon separated, with a space and count at the end
of the line.  These can be generated for Linux perf script output using
stackcollapse-perf.pl, for DTrace using stackcollapse.pl, and for other tools
using the other stackcollapse programs.  Example input:

 swapper;start_kernel;rest_init;cpu_idle;default_idle;native_safe_halt 1

An optional extra column of counts can be provided to generate a differential
flame graph of the counts, colored red for more, and blue for less.  This
can be useful when using flame graphs for non-regression testing.
See the header comment in the difffolded.py program for instructions.

The input functions can optionally have annotations at the end of each
function name, following a precedent by some tools (Linux perf's _[k]):
    _[k] for kernel
    _[i] for inlined
        _[j] for jit
        _[w] for waker
Some of the stackcollapse programs support adding these annotations, eg,
stackcollapse-perf.pl --kernel --jit. They are used merely for colors by
some palettes, eg, flamegraph.pl --color=java.

The output flame graph shows relative presence of functions in stack samples.
The ordering on the x-axis has no meaning; since the data is samples, time
order of events is not known.  The order used sorts function names
alphabetically.

While intended to process stack samples, this can also process stack traces.
For example, tracing stacks for memory allocation, or resource usage.  You
can use --title to set the title to reflect the content, and --countname
to change "samples" to "bytes" etc.

There are a few different palettes, selectable using --color.  By default,
the colors are selected at random (except for differentials).  Functions
called "-" will be printed gray, which can be used for stack separators (eg,
between user and kernel stacks).

*******************************************************************************
* Python version details
*******************************************************************************

This Python version is meant as a drop-in replacement for the original Perl
script. As such, it requires only a Python interpreter with the Python standard
library: it deliberately avoids any 3rd party dependencies.

The Python version has been optimized for processing large folded profiles and,
based on some crude local measurements (Python 3.14, cached bytecode), appears
to be almost 8x faster for standard flame graphs and 4.5x faster for
differential flamegraphs using an example ~150 MB folded profile. Small profiles
(approximatelly < 500 KB based on local measurements) tend to exhibit a slowdown
compared to the Perl version as the execution time is dominated by the Python
interpreter startup cost (~40ms+ on a local machine). Also note that the
optimizations cause some code duplication as we have no macros or templates
in Python.

Additionally, this version introduces some minor changes compared to the
original Perl script:

 - The colors of individual frames do not match exactly since Perl and Python
   use different PRNG in their random modules.

 - The original Perl script has more CLI options than displayed in its help
   (usage) message. The Python script lists all the options.

 - The CLI contains two additional options. Namely, the ``outfile`` option
   allows to specify the output file directly (instead of relying solely on OS
   pipes); and the ``max_trace`` option allows the users to override the flame
   graph height (suitable for aligning multiple graphs in a grid or truncating
   too deep graphs).

 - Large count figures (e.g., CPU cycles) are often difficult to read. Hence,
   this version formats the numbers using SI suffixes to improve readability.

 - An additional JS code related to our particular use in flame graph grids.

  TODO: remove some of the new additions if we decide to make the flame graph
   scripts available in a standalone repo / a fork of B. Gregg's repo.

*******************************************************************************

HISTORY

This was inspired by Neelakanth Nadgir's excellent function_call_graph.rb
program, which visualized function entry and return trace events.  As Neel
wrote: "The output displayed is inspired by Roch's CallStackAnalyzer which
was in turn inspired by the work on vftrace by Jan Boerhout".  See:
https://blogs.oracle.com/realneel/entry/visualizing_callstacks_via_dtrace_and

Copyright 2016 Netflix, Inc.
Copyright 2011 Joyent, Inc.  All rights reserved.
Copyright 2011 Brendan Gregg.  All rights reserved.

CDDL HEADER START

The contents of this file are subject to the terms of the
Common Development and Distribution License (the "License").
You may not use this file except in compliance with the License.

You can obtain a copy of the license at docs/cddl1.txt or
http://opensource.org/licenses/CDDL-1.0.
See the License for the specific language governing permissions
and limitations under the License.

When distributing Covered Code, include this CDDL HEADER in each
file and include the License file at docs/cddl1.txt.
If applicable, add the following below this CDDL HEADER, with the
fields enclosed by brackets "[]" replaced with your own identifying
information: Portions Copyright [yyyy] [name of copyright owner]

CDDL HEADER END

01-May-2026 Jiri Pavela     Optimized and ported to Python.
11-Oct-2014	Adrien Mahieux	Added zoom.
21-Nov-2013 Shawn Sterling  Added consistent palette file option
17-Mar-2013 Tim Bunce       Added options and more tunables.
15-Dec-2011	Dave Pacheco	Support for frames with whitespace.
10-Sep-2011	Brendan Gregg	Created this.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
import enum
from operator import itemgetter
from pathlib import Path
import random
import re
import sys
from typing import Any, TextIO, ClassVar, Literal, TypeAlias, overload, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from _typeshed import OpenTextModeReading

ColoringFn: TypeAlias = Callable[[str], str]
ColoringCtxFn: TypeAlias = Callable[["Colors", str], str]


class ColorPalettes(enum.Enum):
    """Supported color palettes for SVG frames (CLI parameter ``--colors``).

    Each member value is the palette name accepted on the command line.
    """

    HOT = "hot"
    MEM = "mem"
    IO = "io"
    WAKEUP = "wakeup"
    CHAIN = "chain"
    JAVA = "java"
    JS = "js"
    PERL = "perl"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    AQUA = "aqua"
    YELLOW = "yellow"
    PURPLE = "purple"
    ORANGE = "orange"

    @staticmethod
    def supported() -> list[str]:
        """Get the collection of supported color palettes.

        :return: palette string names accepted by ``--colors``.
        """
        return [palette.value for palette in ColorPalettes]

    @staticmethod
    def default() -> ColorPalettes:
        """Get the default color palette.

        :return: the default HOT color palette.
        """
        return ColorPalettes.HOT


class NameAttributes:
    """A cache for pre-processed name-attribute entries.

    Users may optionally supply a so-called name-attribute file which lists
    additional HTML attributes that should be associated with certain names
    (e.g., functions). These attributes are then embedded into the SVG frames
    depicting these names.

    Each line in the name-attribute file must have the following format:
    <name>TAB<attribute1>=<value1>TAB<attribute2>=<value2>[...]

    This class wraps the loading and processing of these name-attribute entries,
    and builds a cache that can be queried for already partially pre-processed
    HTML markup.

    :ivar attr_cache: name -> (opening markup, closing markup).
    """

    __slots__ = ("attr_cache",)

    def __init__(self, filepath: str) -> None:
        """Loads name-attribute mappings from ``filepath``.

        The program will be terminated if the file does not exist, or if it
        is malformed.

        :param filepath: path to the name-attr file, or ``""`` for no file.
        """
        self.attr_cache: dict[str, tuple[str, str]] = self._init_attr_cache(filepath)

    def get_frame(self, name: str, title: str) -> tuple[str, str]:
        """Return SVG opening and closing markup for the ``name``.

        When the ``name`` is not in the cache, the method returns the standard
        opening and closing markup used for names without any user-supplied
        attributes.

        The opening markup has a formatting placeholder for ``data-*``
        attributes used to store exclusive consumption values.

        :param name: the frame name used as a key in the cache lookup.
        :param title: the inner ``<title>`` text.

        :return: (opening markup, closing markup).
        """
        try:
            begin, end = self.attr_cache[name]
        except KeyError:
            begin, end = ("<g {}>\n<title>", "</g>\n")
        return f"{begin}{title}</title>\n", end

    @staticmethod
    def _init_attr_cache(filepath: str) -> dict[str, tuple[str, str]]:
        """Parse ``filepath`` into the name-attr cache.

        :param filepath: the name-attr file path, or ``""`` for no file.

        :return: a constructed cache.
        """
        cache: dict[str, tuple[str, str]] = {}
        if not filepath:
            return cache
        try:
            with open(filepath, "r") as fh:
                for line in fh:
                    func_name, *attrs = line.split("\t")
                    cache[func_name] = NameAttributes._construct_name_attrs(
                        **dict(attr.split("=") for attr in attrs)
                    )
            return cache
        except IOError as e:
            print(f"ERROR: Can't read {filepath}: {e}", file=sys.stderr)
            sys.exit(1)
        except (ValueError, IndexError):
            print(f"ERROR: Invalid format in {filepath}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _construct_name_attrs(
        g_extra: str | None = None,
        href: str | None = None,
        target: str | None = None,
        a_extra: str | None = None,
        **rest: str,
    ) -> tuple[str, str]:
        """Build the opening and closing SVG fragments for the given attributes.

        :param g_extra: extra attributes to use in ``<g>``.
        :param href: if set, emit ``<a xlink:href=...>`` instead of ``<g>``.
        :param target: link target (defaults to ``_top`` when ``href`` is set).
        :param a_extra: extra attributes to use in ``<a>`` when ``href`` is set.
        :param rest: remaining ``name=value`` pairs (e.g. ``class``, ``id``).

        :return: (opening markup, closing markup).
        """
        # Process the ``<g>`` attributes.
        g_attrs = []
        if (g_id := rest.get("id")) is not None:
            g_attrs.append(f'id="{g_id}"')
        if (g_class := rest.get("class")) is not None:
            # Cannot name the parameter ``class`` (reserved keyword).
            g_attrs.append(f'class="{g_class}"')
        if g_extra is not None:
            g_attrs.append(g_extra)

        # Use ``<a>`` instead of ``<g>`` when a link is requested.
        if href is not None:
            a_attrs = [
                f'xlink:href="{href}"',
                f'target="{target}"' if target is not None else "_top",
            ]
            if a_extra is not None:
                a_attrs.append(a_extra)
            return f'<a {{}} {" ".join(a_attrs + g_attrs)}>\n<title>', "</a>\n"
        # Create a placeholder for additional ``data-*`` attributes.
        return f'<g {{}} {" ".join(g_attrs)}>\n<title>', "</g>\n"


class Settings:
    """The flame graph construction options as available through the CLI."""

    __slots__ = (
        "infile",
        "outfile",
        "bg_colors",
        "colors",
        "count_name",
        "encoding",
        "factor",
        "flame_chart_flag",
        "font_size",
        "font_type",
        "font_width",
        "frame_height",
        "hash_flag",
        "image_width",
        "inverted",
        "max_trace",
        "min_width_value",
        "min_width_relative",
        "name_attr",
        "name_type",
        "negate",
        "notes_text",
        "consistent_palette_flag",
        "random_flag",
        "root_node",
        "sub_root_node",
        "stack_reverse_flag",
        "subtitle",
        "total",
        "title",
    )

    DefaultBgColors: ClassVar[str] = ""
    DefaultColors: ClassVar[ColorPalettes] = ColorPalettes.default()
    DefaultCountName: ClassVar[str] = "samples"
    DefaultEncoding: ClassVar[str] = ""
    DefaultFactor: ClassVar[float] = 1.0
    DefaultFlameChartFlag: ClassVar[bool] = False
    DefaultFontSize: ClassVar[float] = 12.0
    DefaultFontType: ClassVar[str] = "Verdana"
    DefaultFontWidth: ClassVar[float] = 0.59
    DefaultFrameHeight: ClassVar[int] = 16
    DefaultHashFlag: ClassVar[bool] = False
    DefaultImageWidth: ClassVar[int] = 1200
    DefaultInvertedFlag: ClassVar[bool] = False
    DefaultMaxTrace: ClassVar[int] = 0
    DefaultMinWidth: ClassVar[str] = "0.1"
    DefaultNameType: ClassVar[str] = "Function:"
    DefaultNameAttrFile: ClassVar[str] = ""
    DefaultNegateFlag: ClassVar[bool] = False
    DefaultNotesText: ClassVar[str] = ""
    DefaultOutFile: ClassVar[str] = ""
    DefaultPaletteFlag: ClassVar[bool] = False
    DefaultRandomFlag: ClassVar[bool] = False
    DefaultRootNode: ClassVar[str] = "all"
    DefaultSubRootNode: ClassVar[str] = "subtotal"
    DefaultStackReverseFlag: ClassVar[bool] = False
    DefaultSubtitle: ClassVar[str] = ""
    DefaultTotal: ClassVar[int] = 0
    DefaultTitle: ClassVar[str] = ""

    # Used to cheaply translate SVG-breaking characters.
    TranslationTable: ClassVar[dict[int, str]] = str.maketrans(
        {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}
    )

    def __init__(
        self,
        infile: Path,
        *,
        bgcolors: str = DefaultBgColors,
        colors: ColorPalettes = DefaultColors,
        countname: str = DefaultCountName,
        cp: bool = DefaultPaletteFlag,
        encoding: str = DefaultEncoding,
        factor: float = DefaultFactor,
        flamechart: bool = DefaultFlameChartFlag,
        fontsize: float = DefaultFontSize,
        fonttype: str = DefaultFontType,
        fontwidth: float = DefaultFontWidth,
        hash: bool = DefaultHashFlag,
        height: int = DefaultFrameHeight,
        inverted: bool = DefaultInvertedFlag,
        maxtrace: int = DefaultMaxTrace,
        minwidth: str = DefaultMinWidth,
        nameattr: str = DefaultNameAttrFile,
        nametype: str = DefaultNameType,
        negate: bool = DefaultNegateFlag,
        notes: str = DefaultNotesText,
        outfile: str = DefaultOutFile,
        random: bool = DefaultRandomFlag,
        reverse: bool = DefaultStackReverseFlag,
        rootnode: str = DefaultRootNode,
        subrootnode: str = DefaultSubRootNode,
        subtitle: str = DefaultSubtitle,
        total: int = DefaultTotal,
        title: str = DefaultTitle,
        width: int = DefaultImageWidth,
        **_: Any,
    ) -> None:
        """Store normalized processing and rendering settings.

        :param infile: a path to the input folded profile. May be set to
               a dummy value ``Path()`` when using the programmatic API
               (see ``create_flame_graph``).
        :param bgcolors: the background color (gradient). Supports:
               - named gradients (``yellow``, ``blue``, ``green``, ``grey``,
                 and ``gray``),
               - hex colors in the ``#RRGGBB`` format (will result in a flat
                 color, not a gradient), or
               - ``""`` for a palette-derived default gradient.
        :param colors: the color palette for SVG frames.
        :param countname: the counts name (e.g. ``samples``, ``cycles``).
        :param encoding: a specific encoding to use in the XML declaration.
        :param factor: a multiplier applied to parsed counts.
        :param flamechart: draw a flame chart instead (sorts by time, does not
               merge stacks).
        :param fontsize: SVG text font size (px).
        :param fonttype: CSS ``font-family`` name for SVG text.
        :param fontwidth: average character width relative to ``font_size``.
        :param height: the height of each frame (px).
        :param hash: color frames using a deterministic hash function.
        :param inverted: draw an icicle chart instead (deepest frames at top).
        :param maxtrace: overrides the computation of the canvas height.
               The height is determined by the maximum trace depth (after
               filtering the data using ``minwidth``). This option may be used
               to align two SVGs with possibly different data side-by-side.
        :param minwidth: specifies the minimum width of displayed frames.
               Narrower frames will be discarded. May be specified either as
               a fixed pixel width, e.g., ``0.5``, or relative to the actual
               total (not the user-supplied ``--total``) count, e.g., ``0.1%``.
        :param nameattr: a path to the name-attribute file
               (see ``NameAttributes``).
        :param nametype: the name of the frames in stacks
              (e.g., ``Function:``, ``Basic Block:``).
        :param negate: flip the differential red/blue hues when ``True``.
        :param notes: addition notes to embedd into the SVG comment header.
        :param outfile: store the flamegraph in a file instead of printing it
               to the standard output.
        :param cp: use consistent palette that loads and stores stable colors
               via a ``palette.map`` file.
        :param random: use randomized frame colors within the selected palette.
               Note that even frames with identical names will have their
               colors chosen randomly.
        :param reverse: the stacks in the folded profile are in the
               callee-to-caller (instead of caller-to-callee) order.
        :param rootnode: the label on the synthetic root frame.
        :param subrootnode: the label on the synthetic sub-root frame used when
               '--total' is supplied. The sub-root allows to scale (zoom) the
               rendered frames when the root node is much wider than the data.
        :param subtitle: optional second title line below the main title.
        :param total: overrides the sum of all counts, which causes the root
               node to be wider (suitable for comparing two profiles
               side-by-side). Must be higher or equal than the actual sum.
        :param title: the graph title.
        :param width: the width of the SVG canvas (px).

        Extra keyword arguments are ignored so that dictionaries with possibly
        additional keys may be unpacked directly when constructing the object.
        """
        self.infile: Path = infile
        self.bg_colors: str = bgcolors
        self.colors: ColorPalettes = colors
        self.count_name: str = countname
        self.encoding: str = encoding
        self.factor: float = factor
        self.flame_chart_flag: bool = flamechart
        self.font_size: float = fontsize
        self.font_type: str = fonttype
        self.font_width: float = fontwidth
        self.frame_height: int = height
        self.hash_flag: bool = hash
        self.image_width: int = width
        self.inverted: bool = inverted
        self.max_trace: int = maxtrace
        self.min_width_value: float = self._init_min_width(minwidth)
        self.min_width_relative: bool = minwidth.endswith("%")
        self.name_attr: NameAttributes = NameAttributes(nameattr)
        self.name_type: str = nametype
        self.negate: bool = negate
        self.notes_text: str = notes.translate(self.TranslationTable)
        self.outfile: str = outfile
        self.consistent_palette_flag: bool = cp
        self.random_flag: bool = random
        self.root_node: str = rootnode
        self.sub_root_node: str = subrootnode
        self.stack_reverse_flag: bool = reverse
        self.subtitle: str = subtitle
        self.total: int = total
        self.title: str = self._init_title(title, flamechart, inverted)

    @staticmethod
    def _init_title(title: str, is_flame_chart: bool, is_inverted: bool) -> str:
        """Initialize the graph title.

        Uses a user-supplied title if available, otherwise synthesizes
        a default title based on the type of the graph being drawn.

        :param title: the user-supplied title, or ``""``.
        :param is_flame_chart: flame-chart mode enabled.
        :param is_inverted: icicle mode enabled.

        :return: the (synthesized) graph title.
        """
        if title:
            return title
        graph_type = "Icicle" if is_inverted else "Flame"
        suffix = "Chart" if is_flame_chart else "Graph"
        return f"{graph_type} {suffix}"

    @staticmethod
    def _init_min_width(min_width: str) -> float:
        """Parse the ``minwidth`` string and obtain the numerical threshold.

        In case of a malformed value, the default minwidth value is used.

        :param min_width: the raw ``--minwidth`` parameter.

        :return: a nonnegative float threshold.
        """
        min_width_match = re.match(r"^([0-9.]+)%?$", min_width)
        if not min_width_match:
            print(
                f"Warning: Invalid minwidth value: '{min_width}', expected a"
                " float with an optional '%' suffix. Using the default value"
                f" '{Settings.DefaultMinWidth}'.'",
                file=sys.stderr,
            )
            return float(Settings.DefaultMinWidth)
        return float(min_width_match.group(1))


class Geometry:
    """Rendering geometry for the SVG layout.

    The class wraps many constants and parameters (dimensions, paddings,
    offset tables, etc.) used when rendering the SVG canvas, elements,
    and frames.

    :ivar y_pad_2: a bottom legend/control padding.
    :ivar x_pad_2: a horizontal padding used for matched-percent labels.
    :ivar width_per_count_unit: the pixel fraction corresponding to a single
          count unit.
    :ivar title_size: the font size of the graph title (px).
    :ivar char_space: an approximate width of a font glyph. Used to compute the
          available space for frame names.
    :ivar profile_total: the sum of all counts in the folded records.
    :ivar total: the total count used for horizontal scaling: either
          ``profile_total`` or ``--total`` depending on which is bigger.
    :ivar total_factor: scales the total counts by the user-supplied factor.
    :ivar image_width: the SVG canvas width.
    :ivar image_height: the SVG canvas height w.r.t. maximum trace length.
    :ivar y1_table: pre-computed Y-coordinates for frame bottom edges.
    :ivar y2_table: pre-computed Y-coordinates for frame top edges.
    """

    __slots__ = (
        "y_pad_2",
        "x_pad_2",
        "width_per_count_unit",
        "total",
        "title_size",
        "char_space",
        "profile_total",
        "total",
        "total_factor",
        "image_width",
        "image_height",
        "y1_table",
        "y2_table",
    )

    XPad1: ClassVar[int] = 10

    def __init__(
        self,
        settings: Settings,
        profile_total: float,
        width_per_count_unit: float,
        max_profile_trace: int,
    ) -> None:
        """Compute dimensions, pads and offset tables.

        :param settings: rendering and processing options.
        :param profile_total: the sum of all counts in folded records.
        :param width_per_count_unit: pixels per a unit of count.
        :param max_profile_trace: the depth of the longest trace found in the
               profile (possibly overridden by the user).
        """
        self.y_pad_2: int = int(settings.font_size * 3 + 10)
        self.x_pad_2: int = int(settings.font_size**2)
        self.width_per_count_unit: float = width_per_count_unit
        self.title_size = int(settings.font_size) + 5
        self.char_space: float = settings.font_size * settings.font_width
        self.profile_total: float = profile_total
        self.total: float = max(profile_total, settings.total)
        self.total_factor: float = self.total * settings.factor
        self.image_width: int = settings.image_width
        self.image_height, self.y1_table, self.y2_table = self._init_heights(
            settings,
            max_profile_trace,
            self.y_pad_2,
        )

    @staticmethod
    def _init_heights(
        settings: Settings,
        max_profile_trace: int,
        y_pad_2: int,
    ) -> tuple[int, list[int], list[int]]:
        """Compute the canvas height and per-frame Y-coordinate tables.

        :param settings: rendering and processing options.
        :param max_profile_trace: the depth of the longest trace found in the
               profile (possibly overridden by the user).
        :param y_pad_2: a bottom legend/control padding.

        :return: (canvas_height,
                  Y-coordinate table for frame bottom edges,
                  Y-coordinate table for frame top edges).
        """
        y_pad_1 = int(settings.font_size * 3)  # Pad top, include title.
        frame_pad: int = 1  # Vertical padding between frames.
        image_height: int = y_pad_1 + y_pad_2

        # The depth offset is influenced by the number of root nodes (1/2).
        depth_offset = 3 if settings.total else 2
        if settings.max_trace:
            image_height += (settings.max_trace + depth_offset - 1) * settings.frame_height
        else:
            image_height += (max_profile_trace + depth_offset) * settings.frame_height
        if settings.subtitle:
            y_pad_3 = int(settings.font_size * 2)  # Pad top, include subtitle.
            image_height += y_pad_3

        if settings.inverted:
            y1_table = [
                y_pad_1 + depth * settings.frame_height
                for depth in range(max_profile_trace + depth_offset)
            ]
            y2_table = [
                y_pad_1 + (depth + 1) * settings.frame_height - frame_pad
                for depth in range(max_profile_trace + depth_offset)
            ]
        else:
            y1_base: int = image_height - y_pad_2
            y1_table = [
                y1_base - (depth + 1) * settings.frame_height + frame_pad
                for depth in range(max_profile_trace + depth_offset)
            ]
            y2_table = [
                y1_base - depth * settings.frame_height
                for depth in range(max_profile_trace + depth_offset)
            ]
        return image_height, y1_table, y2_table


class Colors:
    """Color management for the SVG canvas and frames.

    This class tries to efficiently wrap all color-related processing. Note that
    the original Perl script supports a large range of color options and
    variants which results in a slight code bloat when trying to implement the
    coloring efficiently.

    Concretely, the original script does a lot of unnecessary processing in each
    ``color()`` call. The Python implementation instead splits the coloring code
    into separate per-palette and per-mode functions (e.g., ``color_hot_hash``,
    ``color_hot_random``, and ``color_hot``) and can thus quickly dispatch each
    request for a new color. Furthermore, we utilize a color cache where
    applicable (i.e., unless random coloring is requested).

    :ivar color_functions: a collection of per-mode (e.g., random, hash)
          coloring functions for each solid palette indexable by ``PaletteIdx``.
          This collection is used mainly by the language-specific palettes to
          quickly dispatch to the correct coloring function based on the
          coloring mode.
    :ivar color_fn: the coloring function selected based on the chosen palette.
    :ivar bg_color_1: the background gradient start color.
    :ivar bg_color_2: the background gradient end color.
    :ivar palette_map: a ``name -> RGB`` cache.
    :ivar consistent_palette_flag: whether persistent palette is enabled.
    """

    __slots__ = (
        "color_functions",
        "color_fn",
        "bg_color_1",
        "bg_color_2",
        "palette_map",
        "consistent_palette_flag",
        "__getitem__",
    )

    class PaletteIdx(enum.IntEnum):
        """Named indices into the ``color_functions`` collection."""

        RED = 0
        GREEN = 1
        BLUE = 2
        YELLOW = 3
        PURPLE = 4
        AQUA = 5
        ORANGE = 6
        HOT = 7
        MEM = 8
        IO = 9

    PaletteFileName: ClassVar[str] = "palette.map"
    JavaRegex: ClassVar[re.Pattern[str]] = re.compile(r"^L?(java|javax|jdk|net|org|com|io|sun)/")
    JSRegex: ClassVar[re.Pattern[str]] = re.compile(r"/.*\.js")
    PerlRegex: ClassVar[re.Pattern[str]] = re.compile(r"Perl|\.pl")
    NameHashModuleSkip: ClassVar[re.Pattern[str]] = re.compile(r"^.(.*?)`")

    RGBblack = "rgb(0,0,0)"
    RGBvdgrey = "rgb(160,160,160)"
    RGBdgrey = "rgb(200,200,200)"
    RGBsearch = "rgb(230,0,230)"  # Search highlight fill color.
    # Search highlight fill color for overlay rectangles.
    RGBsearchOverlay = "rgb(200,0,200)"
    RGBhover = "rgb(0,230,230)"  # Hover highlight fill color.
    # Hover highlight fill color for overlay rectangles.
    RGBhoverOverlay = "rgb(0,200,200)"

    def __init__(
        self,
        palette: ColorPalettes,
        bg_colors: str,
        has_consistent_palette: bool,
        use_hash: bool,
        use_random: bool,
    ) -> None:
        """Initializes frames and background coloring scheme.

        :param palette: the requested color palette for frames.
        :param bg_colors: the background color specification. Could be named
               gradients, flat hex colors, or ``""`` to force automatic
               selection based on the color palette.
        :param has_consistent_palette: indicator whether a consistent palette
               mode using the ``palette.map`` file is desired.
        :param use_hash: color frames using the deterministic ``*_hash``
               coloring functions.
        :param use_random: color frames randomly w.r.t the selected palette.
               Note that even frames with identical names will have different
               colors.
        """
        self.color_functions: list[ColoringFn] = self._init_color_functions(use_hash, use_random)
        self.color_fn: ColoringFn | ColoringCtxFn = self._init_color_callable(
            palette, self.color_functions
        )
        self.bg_color_1, self.bg_color_2 = self._init_bg_color_gradient(palette, bg_colors)
        self.palette_map: dict[str, str] = self._init_palette_cache(has_consistent_palette)
        self.consistent_palette_flag: bool = has_consistent_palette
        # Select the appropriate __getitem__ method depending on whether we can
        # or cannot use a color cache. When random coloring is requested, even
        # frames with identical names should compute a new color every time,
        # hence the cache cannot be used.
        if use_random:
            self.__getitem__ = self._getitem_random
        else:
            self.__getitem__ = self._getitem_cached

    @staticmethod
    def _init_color_functions(use_hash: bool, use_random: bool) -> list[ColoringFn]:
        """Create a mode-specific indexable collection of palette callables.

        Used to quickly dispatch to the appropriate coloring function from the
        language-specific palettes.

        :param use_hash: use the ``*_hash`` coloring functions.
        :param use_random: use the ``*_random`` coloring functions.

        :return: an indexable collection of coloring callables.
        """
        if use_hash:
            return [
                Colors.color_red_hash,
                Colors.color_green_hash,
                Colors.color_blue_hash,
                Colors.color_yellow_hash,
                Colors.color_purple_hash,
                Colors.color_aqua_hash,
                Colors.color_orange_hash,
                Colors.color_hot_hash,
                Colors.color_mem_hash,
                Colors.color_io_hash,
            ]
        if use_random:
            return [
                Colors.color_red_random,
                Colors.color_green_random,
                Colors.color_blue_random,
                Colors.color_yellow_random,
                Colors.color_purple_random,
                Colors.color_aqua_random,
                Colors.color_orange_random,
                Colors.color_hot_random,
                Colors.color_mem_random,
                Colors.color_io_random,
            ]
        return [
            Colors.color_red,
            Colors.color_green,
            Colors.color_blue,
            Colors.color_yellow,
            Colors.color_purple,
            Colors.color_aqua,
            Colors.color_orange,
            Colors.color_hot,
            Colors.color_mem,
            Colors.color_io,
        ]

    @staticmethod
    def _init_bg_color_gradient(palette: ColorPalettes, bg_color: str) -> tuple[str, str]:
        """Create the start and end colors for the SVG background gradient.

        :param palette: the selected palette to infer the default gradient.
        :param bg_color: a ``#RRGGBB`` literal, gradient keyword, or ``""``.

        :return: (gradient start color, gradient end color).
        """
        # Flat RGB hex uses one color as both gradient stops.
        if len(bg_color) == 7 and bg_color[0] == "#":
            return bg_color, bg_color
        # Named presets and palette-derived defaults.
        yellow_gradient = ("#eeeeee", "#eeeeb0")
        blue_gradient = ("#eeeeee", "#e0e0ff")
        green_gradient = ("#eef2ee", "#e0ffe0")
        grey_gradient = ("#f8f8f8", "#e8e8e8")
        # Infer gradient from ``palette`` when ``bg_color`` is empty.
        color_key = bg_color if bg_color else palette
        try:
            return {
                "yellow": yellow_gradient,
                "blue": blue_gradient,
                "green": green_gradient,
                "grey": grey_gradient,
                "gray": grey_gradient,
                ColorPalettes.HOT: yellow_gradient,
                ColorPalettes.MEM: green_gradient,
                ColorPalettes.IO: blue_gradient,
                ColorPalettes.WAKEUP: blue_gradient,
                ColorPalettes.CHAIN: blue_gradient,
                ColorPalettes.RED: grey_gradient,
                ColorPalettes.GREEN: grey_gradient,
                ColorPalettes.BLUE: grey_gradient,
                ColorPalettes.AQUA: grey_gradient,
                ColorPalettes.YELLOW: grey_gradient,
                ColorPalettes.PURPLE: grey_gradient,
                ColorPalettes.ORANGE: grey_gradient,
            }[color_key]
        except KeyError:
            if bg_color:
                print(
                    f"WARNING: Unrecognized --bgcolors option '{bg_color}'."
                    " Using a default yellow gradient.",
                    file=sys.stderr,
                )
        return yellow_gradient

    @staticmethod
    def _init_color_callable(
        color: ColorPalettes, color_functions: Sequence[ColoringFn]
    ) -> ColoringFn | ColoringCtxFn:
        """Resolve the selected palette to the corresponding coloring callable.

        :param color: the palette selected by the user.
        :param color_functions: an indexable collection of coloring functions.

        :return: either a plain staticmethod ``Callable[[str], str]``, or
                 a palette method needing ``self``. Note that despite their
                 different type, both callable types can be called using
                 ``self.fn()``.
        """
        color_map: dict[ColorPalettes, ColoringFn | ColoringCtxFn] = {
            ColorPalettes.RED: color_functions[Colors.PaletteIdx.RED],
            ColorPalettes.GREEN: color_functions[Colors.PaletteIdx.GREEN],
            ColorPalettes.BLUE: color_functions[Colors.PaletteIdx.BLUE],
            ColorPalettes.YELLOW: color_functions[Colors.PaletteIdx.YELLOW],
            ColorPalettes.PURPLE: color_functions[Colors.PaletteIdx.PURPLE],
            ColorPalettes.AQUA: color_functions[Colors.PaletteIdx.AQUA],
            ColorPalettes.ORANGE: color_functions[Colors.PaletteIdx.ORANGE],
            ColorPalettes.HOT: color_functions[Colors.PaletteIdx.HOT],
            ColorPalettes.MEM: color_functions[Colors.PaletteIdx.MEM],
            ColorPalettes.IO: color_functions[Colors.PaletteIdx.IO],
            ColorPalettes.JAVA: Colors.color_java,
            ColorPalettes.PERL: Colors.color_perl,
            ColorPalettes.JS: Colors.color_js,
            ColorPalettes.WAKEUP: color_functions[Colors.PaletteIdx.AQUA],
            ColorPalettes.CHAIN: Colors.color_chain,
        }
        try:
            return color_map[color]
        except KeyError:
            return Colors.color_unknown

    @staticmethod
    def _init_palette_cache(has_consistent_palette: bool) -> dict[str, str]:
        """Initialize the palette cache.

        If a consistent palette is requested and the palette file exists, it is
        used to populate the cache. Otherwise, the cache is initialized with
        two gray colors reserved for delimiter frames.

        :param has_consistent_palette: populate the cache with the contents of
               the ``palette.map`` file.

        :return: an initialized color cache.
        """
        palette_map: dict[str, str] = {}
        if has_consistent_palette and Path.exists(Path(Colors.PaletteFileName)):
            try:
                with open(Colors.PaletteFileName, "r+") as f:
                    # Optimize dot access.
                    str_split = str.split

                    for line in f:
                        name, color = str_split(line, "->", 1)
                        palette_map[name] = color
            except IOError as e:
                print(
                    f"ERROR: Can't open file {Colors.PaletteFileName}: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)
            except ValueError:
                print(
                    f"ERROR: Invalid palette {Colors.PaletteFileName}",
                    file=sys.stderr,
                )
                sys.exit(1)
        # Delimiter frames use fixed grays.
        palette_map["--"] = Colors.RGBvdgrey
        palette_map["-"] = Colors.RGBdgrey
        return palette_map

    def store_palette(self) -> None:
        """Save the color cache to a file if consistent palette is enabled."""
        if self.consistent_palette_flag:
            with open(self.PaletteFileName, "w") as f:
                for name, color in self.palette_map.items():
                    f.write(f"{name}->{color}\n")

    @staticmethod
    def name_hash(name: str) -> float:
        """A pseudorandom scalar in the range ``[0, 1)`` derived from ``name``.

        :param name: the frame name to hash.

        :return: a scalar hash used in mixing RGB color for deterministic
                 palettes.
        """
        # Weight early characters more so colors stay stable across graphs.
        vector = 0.0
        weight = 1.0
        max_val = 1.0
        mod = 10
        # Strip optional leading module names before hashing (Perl-style names).
        name = Colors.NameHashModuleSkip.sub("", name)
        for c in name:
            i = ord(c) % mod
            vector += (i / (mod - 1)) * weight
            max_val += 1.0 * weight
            weight *= 0.70
            mod += 1
            if mod > 12:
                break
        return 1.0 - vector / max_val

    # Here are all the solid-palette callables for each coloring mode.
    # We deliberately omit docstrings as there is a lot of self-explanatory
    # functions.
    @staticmethod
    def color_hot_hash(name: str) -> str:
        rb_adjust = Colors.name_hash(name[::-1])
        return (
            f"rgb({205 + int(50 * rb_adjust)},"
            f"{int(230 * Colors.name_hash(name))},"
            f"{int(55 * rb_adjust)})"
        )

    @staticmethod
    def color_hot_random(_: str) -> str:
        val1 = random.random()
        val2 = random.random()
        val3 = random.random()
        return f"rgb({205 + int(50 * val3)},{int(230 * val1)},{int(55 * val2)})"

    @staticmethod
    def color_hot(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        return f"rgb({205 + int(50 * value)},{int(230 * value)},{int(55 * value)})"

    @staticmethod
    def color_mem_hash(name: str) -> str:
        return (
            "rgb(0,"
            f"{190 + int(50 * Colors.name_hash(name[::-1]))},"
            f"{int(210 * Colors.name_hash(name))})"
        )

    @staticmethod
    def color_mem_random(_: str) -> str:
        val1 = random.random()
        val2 = random.random()
        return f"rgb(0,{190 + int(50 * val2)},{int(210 * val1)})"

    @staticmethod
    def color_mem(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        return f"rgb(0,{190 + int(50 * value)},{int(210 * value)})"

    @staticmethod
    def color_io_hash(name: str) -> str:
        red_green = 80 + int(60 * Colors.name_hash(name))
        return (
            f"rgb({red_green}," f"{red_green}," f"{190 + int(55 * Colors.name_hash(name[::-1]))})"
        )

    @staticmethod
    def color_io_random(_: str) -> str:
        red_green = 80 + int(60 * random.random())
        return f"rgb({red_green},{red_green},{190 + int(55 * random.random())})"

    @staticmethod
    def color_io(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        red_green = 80 + int(60 * value)
        return f"rgb({red_green},{red_green},{190 + int(55 * value)})"

    @staticmethod
    def color_red_hash(name: str) -> str:
        value = Colors.name_hash(name)
        green_blue = 50 + int(80 * value)
        return f"rgb({200 + int(55 * value)},{green_blue},{green_blue})"

    @staticmethod
    def color_red_random(_: str) -> str:
        value = random.random()
        green_blue = 50 + int(80 * value)
        return f"rgb({200 + int(55 * value)},{green_blue},{green_blue})"

    @staticmethod
    def color_red(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        green_blue = 50 + int(80 * value)
        return f"rgb({200 + int(55 * value)},{green_blue},{green_blue})"

    @staticmethod
    def color_green_hash(name: str) -> str:
        value = Colors.name_hash(name)
        red_blue = 50 + int(60 * value)
        return f"rgb({red_blue},{200 + int(55 * value)},{red_blue})"

    @staticmethod
    def color_green_random(_: str) -> str:
        value = random.random()
        red_blue = 50 + int(60 * value)
        return f"rgb({red_blue},{200 + int(55 * value)},{red_blue})"

    @staticmethod
    def color_green(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        red_blue = 50 + int(60 * value)
        return f"rgb({red_blue},{200 + int(55 * value)},{red_blue})"

    @staticmethod
    def color_blue_hash(name: str) -> str:
        value = Colors.name_hash(name)
        red_green = 80 + int(60 * value)
        return f"rgb({red_green},{red_green},{205 + int(50 * value)})"

    @staticmethod
    def color_blue_random(_: str) -> str:
        value = random.random()
        red_green = 80 + int(60 * value)
        return f"rgb({red_green},{red_green},{205 + int(50 * value)})"

    @staticmethod
    def color_blue(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        red_green = 80 + int(60 * value)
        return f"rgb({red_green},{red_green},{205 + int(50 * value)})"

    @staticmethod
    def color_yellow_hash(name: str) -> str:
        value = Colors.name_hash(name)
        red_green = 175 + int(55 * value)
        return f"rgb({red_green},{red_green},{50 + int(20 * value)})"

    @staticmethod
    def color_yellow_random(_: str) -> str:
        value = random.random()
        red_green = 175 + int(55 * value)
        return f"rgb({red_green},{red_green},{50 + int(20 * value)})"

    @staticmethod
    def color_yellow(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        red_green = 175 + int(55 * value)
        return f"rgb({red_green},{red_green},{50 + int(20 * value)})"

    @staticmethod
    def color_purple_hash(name: str) -> str:
        value = Colors.name_hash(name)
        red_blue = 190 + int(65 * value)
        return f"rgb({red_blue},{80 + int(60 * value)},{red_blue})"

    @staticmethod
    def color_purple_random(_: str) -> str:
        value = random.random()
        red_blue = 190 + int(65 * value)
        return f"rgb({red_blue},{80 + int(60 * value)},{red_blue})"

    @staticmethod
    def color_purple(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        red_blue = 190 + int(65 * value)
        return f"rgb({red_blue},{80 + int(60 * value)},{red_blue})"

    @staticmethod
    def color_aqua_hash(name: str) -> str:
        value = Colors.name_hash(name)
        green_blue = 165 + int(55 * value)
        return f"rgb({50 + int(60 * value)},{green_blue},{green_blue})"

    @staticmethod
    def color_aqua_random(_: str) -> str:
        value = random.random()
        green_blue = 165 + int(55 * value)
        return f"rgb({50 + int(60 * value)},{green_blue},{green_blue})"

    @staticmethod
    def color_aqua(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        value = random.random()
        green_blue = 165 + int(55 * value)
        return f"rgb({50 + int(60 * value)},{green_blue},{green_blue})"

    @staticmethod
    def color_orange_hash(name: str) -> str:
        red_green_coeff = int(65 * Colors.name_hash(name))
        return f"rgb({190 + red_green_coeff},{90 + red_green_coeff},0)"

    @staticmethod
    def color_orange_random(_: str) -> str:
        red_green_coeff = int(65 * random.random())
        return f"rgb({190 + red_green_coeff},{90 + red_green_coeff},0)"

    @staticmethod
    def color_orange(name: str) -> str:
        random.seed(sum(ord(c) for c in name))
        red_green_coeff = int(65 * random.random())
        return f"rgb({190 + red_green_coeff},{90 + red_green_coeff},0)"

    @staticmethod
    def color_unknown(_: str) -> str:
        return "rgb(0,0,0)"

    def color_java(self, name: str) -> str:
        """Color a frame related to Java programs.

        This method handles both annotations (_[j], _[i], ...; which should be
        accurate) and input that lacks any annotations. When annotations
        are missing, we fall back to heuristics and match on java|org|com, etc.

        :param name: a Java-ish frame name with optional ``_[kij]`` suffixes.

        :return: an RGB color string for the given ``name``.
        """
        if name.endswith("_[j]"):  # JIT.
            color_palette = Colors.PaletteIdx.GREEN
        elif name.endswith("_[i]"):  # Inline.
            color_palette = Colors.PaletteIdx.AQUA
        elif ":::" in name or self.JavaRegex.search(name):  # Likely Java.
            color_palette = Colors.PaletteIdx.GREEN
        elif "::" in name:  # C++.
            color_palette = Colors.PaletteIdx.YELLOW
        elif name.endswith("_[k]"):  # Kernel.
            color_palette = Colors.PaletteIdx.ORANGE
        else:  # System.
            color_palette = Colors.PaletteIdx.RED
        return self.color_functions[color_palette](name)

    def color_perl(self, name: str) -> str:
        """Color a frame related to Perl programs.

        :param name: a Perl-ish frame name with an optional ``_[k]`` suffix.

        :return: an RGB color string for the given ``name``.
        """
        if "::" in name:  # C++.
            color_palette = Colors.PaletteIdx.YELLOW
        elif self.PerlRegex.search(name):  # Perl.
            color_palette = Colors.PaletteIdx.GREEN
        elif name.endswith("_[k]"):  # Kernel.
            color_palette = Colors.PaletteIdx.ORANGE
        else:  # System.
            color_palette = Colors.PaletteIdx.RED
        return self.color_functions[color_palette](name)

    def color_js(self, name: str) -> str:
        """Color a frame related to JavaScript programs.

        This method handles both annotations (_[j], _[i], ...; which should be
        accurate) and input that lacks any annotations. When annotations are
        missing, we fall back to heuristics and match on "/" with a ".js", etc.

        :param name: a JS-ish frame name with an optional ``_[jk]`` suffix.

        :return: an RGB color string for the given ``name``.
        """
        if name.endswith("_[j]"):  # JIT.
            if "/" in name:
                color_palette = Colors.PaletteIdx.GREEN  # Source file path.
            else:
                color_palette = Colors.PaletteIdx.AQUA  # Built-in.
        elif "::" in name:  # C++.
            color_palette = Colors.PaletteIdx.YELLOW
        elif self.JSRegex.search(name):  # Script path with extension.
            color_palette = Colors.PaletteIdx.GREEN
        elif ":" in name:  # Built-in label with colon.
            color_palette = Colors.PaletteIdx.AQUA
        elif name == " ":  # A missing symbol placeholder.
            color_palette = Colors.PaletteIdx.GREEN
        elif name.endswith("_[k]"):  # Kernel.
            color_palette = Colors.PaletteIdx.ORANGE
        else:  # System.
            color_palette = Colors.PaletteIdx.RED
        return self.color_functions[color_palette](name)

    def color_chain(self, name: str) -> str:
        """Color an off-CPU frame.

        :param name: a frame name from an off-CPU profile.

        :return: an RGB color string for the given ``name``.
        """
        if "_[w]" in name:  # A waker frame.
            return self.color_functions[Colors.PaletteIdx.AQUA](name)
        # An off-CPU stack frame.
        return self.color_functions[Colors.PaletteIdx.BLUE](name)

    @staticmethod
    def color_scale(delta: float, max_delta: float) -> str:
        """Color a frame using a red/blue color scale.

        This method is used to color frames in differential flame graphs.

        :param delta: a delta value in the interval ``[-max_delta, max_delta]``.
        :param max_delta: the largest delta observed in the pair of profiles.

        :return: an RGB color string for the given ``delta`` value.
        """
        r, g, b = 255, 255, 255
        if delta > 0:
            g = b = int(210 * (max_delta - delta) / max_delta)
        elif delta < 0:
            r = g = int(210 * (max_delta + delta) / max_delta)
        return f"rgb({r},{g},{b})"

    def _getitem_cached(self, name: str) -> str:
        """Use cache to obtain/store frame color.

        Do not use this directly, it is one of two __getitem__ variants that
        are chosen programmatically during runtime.

        :param name: the frame name to color.

        :return: a (possibly cached) RGB color string for the given ``name``.
        """
        try:
            return self.palette_map[name]
        except KeyError:
            # Known mypy issue: https://github.com/python/mypy/issues/17438.
            new_color = self.color_fn(name)  # type: ignore
            self.palette_map[name] = new_color
            return new_color

    def _getitem_random(self, name: str) -> str:
        """Compute a new random color for the frame name.

        Do not use this directly, it is one of two __getitem__ variants that
        are chosen programmatically during runtime.

        :param name: the frame name to color.

        :return: a new RGB color string for the given ``name``.
        """
        # Handle the delimiter frames.
        if name == "--":
            return Colors.RGBvdgrey
        if name == "-":
            return Colors.RGBdgrey
        # Known mypy issue: https://github.com/python/mypy/issues/17438.
        return self.color_fn(name)  # type: ignore


#### SECTION: SVG UTILITIES
# A collection of helper functions related to constructing the flame graph SVG.
# Strings are accumulated in a list rather than concatenated to avoid costly
# string concatenations.


def create_error_svg(settings: Settings) -> str:
    """Return a minimal SVG that reports missing or invalid folded profile.

    :param settings: rendering and processing options.

    :return: an SVG document string containing an error message.
    """
    image_height = int(settings.font_size * 5)
    # Here we concatenate the strings directly as they are quite short.
    return (
        create_svg_header(
            settings.image_width,
            image_height,
            settings.encoding,
            settings.notes_text,
        )
        + create_svg_text(
            None,
            int(settings.image_width / 2),
            settings.font_size * 2,
            "ERROR: No valid input provided to flamegraph.py.",
        )
        + "</svg>\n"
    )


def create_svg_without_frames(
    settings: Settings, geometry: Geometry, colors: Colors, is_diff: bool
) -> list[str]:
    """Build the SVG header, JS/CSS components, and canvas.

    The resulting string is not a valid SVG document as it is missing the
    terminating markup. It also contains no frames.

    :param settings: rendering and processing options.
    :param geometry: rendering geometry for the SVG layout.
    :param colors: coloring options for the SVG.
    :param is_diff: ``True`` if we are generating a difference graph SVG.

    :return: a collection of strings representing the incomplete SVG.
    """
    return [
        create_svg_header(
            geometry.image_width,
            geometry.image_height,
            settings.encoding,
            settings.notes_text,
        ),
        create_svg_js_css(
            settings, colors.bg_color_1, colors.bg_color_2, geometry.title_size, is_diff
        ),
        (
            f'<rect x="0" y="0" width="{settings.image_width}"'
            f' height="{geometry.image_height}" fill="url(#background)" />\n'
        ),
        create_svg_text(
            "title",
            int(settings.image_width / 2),
            settings.font_size * 2,
            settings.title,
        ),
        (
            create_svg_text(
                "subtitle",
                int(settings.image_width / 2),
                settings.font_size * 4,
                settings.subtitle,
            )
            if settings.subtitle
            else ""
        ),
        create_svg_text(
            "unzoom",
            Geometry.XPad1,
            settings.font_size * 2,
            "Reset Zoom",
            'class="hide"',
        ),
        create_svg_text(
            "excToggle",
            settings.image_width - Geometry.XPad1 - 220,
            settings.font_size * 2,
            "Show exclusive",
        ),
        create_svg_text(
            "search",
            settings.image_width - Geometry.XPad1 - 100,
            settings.font_size * 2,
            "Search",
        ),
        create_svg_text(
            "ignorecase",
            settings.image_width - Geometry.XPad1 - 16,
            settings.font_size * 2,
            "ic",
        ),
        create_svg_text(
            "nameTypeLabel",
            Geometry.XPad1 + 70,
            geometry.image_height - (geometry.y_pad_2 * 2 / 3) - 2,
            settings.name_type,
            'text-anchor="end" font-weight="bold"',
        ),
        create_svg_text(
            "inclusiveLabel",
            Geometry.XPad1 + 70,
            geometry.image_height - (geometry.y_pad_2 / 3) - 3,
            "Inclusive:",
            'text-anchor="end" font-weight="bold"',
        ),
        create_svg_text(
            "exclusiveLabel",
            Geometry.XPad1 + 70,
            geometry.image_height - 4,
            "Exclusive:",
            'text-anchor="end" font-weight="bold"',
        ),
        create_svg_text(
            "detailsName",
            Geometry.XPad1 + 75,
            geometry.image_height - (geometry.y_pad_2 * 2 / 3) - 2,
            " ",
            'font-style="italic"',
        ),
        create_svg_text(
            "detailsIncl",
            Geometry.XPad1 + 75,
            geometry.image_height - (geometry.y_pad_2 / 3) - 3,
            " ",
        ),
        create_svg_text(
            "detailsExcl",
            Geometry.XPad1 + 75,
            geometry.image_height - 4,
            " ",
        ),
        create_svg_text(
            "matchedHoverLabel",
            settings.image_width / 2 - 50,
            geometry.image_height - (geometry.y_pad_2 * 2 / 3) - 2,
            "Matched (mouseover):",
            'font-weight="bold"',
        ),
        create_svg_text(
            "matchedHoverCount",
            settings.image_width / 2 + 90,
            geometry.image_height - (geometry.y_pad_2 * 2 / 3) - 2,
            " ",
        ),
        create_svg_text(
            "matchedHoverIncl",
            settings.image_width / 2 - 50,
            geometry.image_height - (geometry.y_pad_2 / 3) - 3,
            " ",
        ),
        create_svg_text(
            "matchedHoverExcl",
            settings.image_width / 2 - 50,
            geometry.image_height - 4,
            " ",
        ),
        create_svg_text(
            "matchedSearchLabel",
            settings.image_width - 60 - geometry.x_pad_2,
            geometry.image_height - (geometry.y_pad_2 * 2 / 3) - 2,
            "Matched (search):",
            'font-weight="bold"',
        ),
        create_svg_text(
            "matchedSearchCount",
            settings.image_width - 90,
            geometry.image_height - (geometry.y_pad_2 * 2 / 3) - 2,
            " ",
        ),
        create_svg_text(
            "matchedSearchIncl",
            settings.image_width - 60 - geometry.x_pad_2,
            geometry.image_height - (geometry.y_pad_2 / 3) - 3,
            " ",
        ),
        create_svg_text(
            "matchedSearchExcl",
            settings.image_width - 60 - geometry.x_pad_2,
            geometry.image_height - 4,
            " ",
        ),
    ]


def create_svg_header(img_width: int, img_height: int, encoding: str | None, notes: str) -> str:
    """Create an SVG header string.

    :param img_width: the SVG width.
    :param img_height: the SVG height.
    :param encoding: optional XML encoding.
    :param notes: optional debugging notes to embed into the SVG document.

    :return: an SVG header string.
    """
    enc_attr = f' encoding="{encoding}"' if encoding else ""
    return f"""<?xml version="1.0"{enc_attr} standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg version="1.1" width="{img_width}" height="{img_height}" onload="init(evt)" viewBox="0 0 {img_width} {img_height}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<!-- Flame graph stack visualization. See https://github.com/brendangregg/FlameGraph for latest version, and http://www.brendangregg.com/flamegraphs.html for examples. -->
<!-- NOTES: {notes} -->
"""


def create_svg_text(id_attr: str | None, x: float, y: float, str_val: str, extra: str = "") -> str:
    """Create an SVG ``<text>`` element.

    :param id_attr: an optional DOM ``id`` attribute.
    :param x: an anchor X-coordinate.
    :param y: an anchor Y-coordinate.
    :param str_val: the content of the ``<text>`` element.
    :param extra: additional ``<text>`` attributes.

    :return: a single ``<text>...</text>`` fragment.
    """
    id_str = f'id="{id_attr}"' if id_attr else ""
    return f'<text {id_str} x="{x:.2f}" y="{y:.2f}" {extra}>{str_val}</text>\n'


def create_svg_js_css(
    settings: Settings, bg_color_1: str, bg_color_2: str, title_size: int, is_diff: bool
) -> str:
    """Create an SVG stylesheet and JS scripts.

    The scripts implement operations such as zoom/unzoom, search, hover, etc.

    :param settings: rendering and processing options.
    :param bg_color_1: gradient start color (top of the canvas).
    :param bg_color_2: gradient end color (bottom of the canvas).
    :param title_size: the title element font size.
    :param is_diff: ``True`` if we are generating a difference graph SVG.

    :return: an SVG stylesheet and JS scripts.
    """
    return f"""<defs>
    <linearGradient id="background" y1="0" y2="1" x1="0" x2="0" >
        <stop stop-color="{bg_color_1}" offset="5%" />
        <stop stop-color="{bg_color_2}" offset="95%" />
    </linearGradient>
</defs>
<style type="text/css">
    text {{ font-family:{settings.font_type}; font-size:{settings.font_size}px; fill:{Colors.RGBblack}; }}
    #search, #ignorecase, #excToggle {{ opacity:0.5; cursor:pointer; }}
    #search:hover, #search.show, #ignorecase:hover, #ignorecase.show, #excToggle:hover {{ opacity:1; }}
    #subtitle {{ text-anchor:middle; font-color:{Colors.RGBvdgrey}; }}
    #title {{ text-anchor:middle; font-size:{title_size}px}}
    #unzoom {{ cursor:pointer; }}
    #frames > *:hover {{ stroke:black; stroke-width:0.5; cursor:pointer; }}
    .hide {{ display:none; }}
    .parent {{ opacity:0.5; }}
</style>
<script type="text/ecmascript">
<![CDATA[
    "use strict";
    var searchbtn, unzoombtn, svg, searching, currentSearchTerm, hoverSearchTerm, ignorecase, ignorecaseBtn;
    var matchedHoverLabel, matchedHoverCount, matchedHoverIncl, matchedHoverExcl;
    var matchedSearchLabel, matchedSearchCount, matchedSearchIncl, matchedSearchExcl;
    var nameTypeLabel, inclusiveLabel, exclusiveLabel;
    var detailsName, detailsExcl, detailsIncl;
    var exclusiveMode;
    var isDiff = {'true' if is_diff else 'false'};
    function init(evt) {{
        nameTypeLabel = document.getElementById("nameTypeLabel");
        inclusiveLabel = document.getElementById("inclusiveLabel");
        exclusiveLabel = document.getElementById("exclusiveLabel");
        matchedHoverLabel = document.getElementById("matchedHoverLabel");
        matchedSearchLabel = document.getElementById("matchedSearchLabel");
        detailsName = document.getElementById("detailsName").firstChild;
        detailsExcl = document.getElementById("detailsExcl").firstChild;
        detailsIncl = document.getElementById("detailsIncl").firstChild;
        matchedHoverCount = document.getElementById("matchedHoverCount").firstChild;
        matchedHoverIncl = document.getElementById("matchedHoverIncl").firstChild;
        matchedHoverExcl = document.getElementById("matchedHoverExcl").firstChild;
        matchedSearchCount = document.getElementById("matchedSearchCount").firstChild;
        matchedSearchIncl = document.getElementById("matchedSearchIncl").firstChild;
        matchedSearchExcl = document.getElementById("matchedSearchExcl").firstChild;
        searchbtn = document.getElementById("search");
        ignorecaseBtn = document.getElementById("ignorecase");
        unzoombtn = document.getElementById("unzoom");
        svg = document.getElementsByTagName("svg")[0];
        searching = 0;
        currentSearchTerm = null;
        hoverSearchTerm = null;
        exclusiveMode = false;

        nameTypeLabel.classList.add("hide");
        inclusiveLabel.classList.add("hide");
        exclusiveLabel.classList.add("hide");
        matchedHoverLabel.classList.add("hide");
        matchedSearchLabel.classList.add("hide");
    }}

    // event listeners
    window.addEventListener("click", function(e) {{
        var target = find_group(e.target);
        if (target) {{
            if (target.nodeName == "a") {{
                if (e.ctrlKey === false) return;
                e.preventDefault();
            }}
            if (target.classList.contains("parent")) unzoom(true);
            zoom(target);
            if (!document.querySelector('.parent')) {{
                unzoombtn.classList.add("hide");
                return;
            }}
        }}
        else if (e.target.id == "unzoom") clearzoom();
        else if (e.target.id == "search") search_prompt();
        else if (e.target.id == "ignorecase") toggle_ignorecase();
        else if (e.target.id == "excToggle") toggleExclusive();
    }}, false)

    // mouse-over for info
    // show
    window.addEventListener("mouseover", function(e) {{
        var target = find_group(e.target);
        if (!target) return;

        nameTypeLabel.classList.remove("hide");
        inclusiveLabel.classList.remove("hide");
        exclusiveLabel.classList.remove("hide");

        var components = g_to_text(target).split('\\n', 3);
        // This removes the "Incl.: " and "Excl.: " substrings.
        var incl = components[1].slice(7);
        var excl = components[2].slice(7);

        detailsName.nodeValue = components[0];
        detailsIncl.nodeValue = incl;
        detailsExcl.nodeValue = excl;
    }}, false)

    // clear
    window.addEventListener("mouseout", function(e) {{
        var target = find_group(e.target);
        if (!target) return;

        nameTypeLabel.classList.add("hide");
        if (!searching) {{
            inclusiveLabel.classList.add("hide");
            exclusiveLabel.classList.add("hide");
        }}

        detailsName.nodeValue = ' ';
        detailsIncl.nodeValue = ' ';
        detailsExcl.nodeValue = ' ';
    }}, false)

    // functions
    function find_child(node, selector) {{
        var children = node.querySelectorAll(selector);
        if (children.length) return children[0];
    }}
    function find_group(node) {{
        var parent = node.parentElement;
        if (!parent) return;
        if (parent.id == "frames") return node;
        return find_group(parent);
    }}
    function orig_save(e, attr, val) {{
        if (e.attributes["_orig_" + attr] != undefined) return;
        if (e.attributes[attr] == undefined) return;
        if (val == undefined) val = e.attributes[attr].value;
        e.setAttribute("_orig_" + attr, val);
    }}
    function orig_load(e, attr) {{
        if (e.attributes["_orig_"+attr] == undefined) return;
        e.attributes[attr].value = e.attributes["_orig_" + attr].value;
        e.removeAttribute("_orig_"+attr);
    }}
    function g_to_text(e) {{
        var text = find_child(e, "title").firstChild.nodeValue;
        return (text)
    }}
    function g_to_func(e) {{
        var func = g_to_text(e);
        // if there's any manipulation we want to do to the function
        // name before it's searched, do it here before returning.
        return (func);
    }}
    function update_text(e) {{
        var r = find_child(e, "rect");
        var t = find_child(e, "text");
        var w = parseFloat(r.attributes.width.value) -3;
        var txt = find_child(e, "title").textContent.split('\\n', 1)[0];
        t.attributes.x.value = parseFloat(r.attributes.x.value) + 3;

        // Smaller than this size won't fit anything
        if (w < 2 * {settings.font_size} * {settings.font_width}) {{
            t.textContent = "";
            return;
        }}

        t.textContent = txt;
        var sl = t.getSubStringLength(0, txt.length);
        // check if only whitespace or if we can fit the entire string into width w
        if (/^ *$/.test(txt) || sl < w)
            return;

        // this isn't perfect, but gives a good starting point
        // and avoids calling getSubStringLength too often
        var start = Math.floor((w/sl) * txt.length);
        for (var x = start; x > 0; x = x-2) {{
            if (t.getSubStringLength(0, x + 2) <= w) {{
                t.textContent = txt.substring(0, x) + "..";
                return;
            }}
        }}
        t.textContent = "";
    }}
    function formatWithSuffix(num) {{
        const suffixes = ['', 'K', 'M', 'G', 'T', 'P', 'E'];
        var i = 0;

        while (num >= 1000 && i < suffixes.length - 1) {{
            num /= 1000;
            i++;
        }}

        // Format to max 3 decimal places, trimming trailing zeroes
        var formatted = num.toFixed(3).replace(/\\.?0+$/, '');

        return formatted + suffixes[i];
    }}

    function parseFormattedSuffix(str) {{
        const units = {{ '': 1, K: 1e3, M: 1e6, G: 1e9, T: 1e12, P: 1e15, E: 1e18 }};
        const inclMatch = str.match(/Incl\\.: ([\\d.]+)([KMGTPE]?) .*/);
        const exclMatch = str.match(/Excl\\.: ([\\d.]+)([KMGTPE]?) .*/);
        return {{
            incl: parseFloat(inclMatch[1]) * (units[inclMatch[2].toUpperCase()] || 1),
            excl: parseFloat(exclMatch[1]) * (units[exclMatch[2].toUpperCase()] || 1)
        }};
    }}

    // zoom
    function zoom_reset(e) {{
        if (e.attributes != undefined) {{
            orig_load(e, "x");
            orig_load(e, "width");
        }}
        if (e.childNodes == undefined) return;
        for (var i = 0, c = e.childNodes; i < c.length; i++) {{
            zoom_reset(c[i]);
        }}
    }}
    function zoom_child(e, x, ratio) {{
        if (e.attributes != undefined) {{
            if (e.attributes.x != undefined) {{
                orig_save(e, "x");
                e.attributes.x.value = (parseFloat(e.attributes.x.value) - x - {Geometry.XPad1}) * ratio + {Geometry.XPad1};
                if (e.tagName == "text")
                    e.attributes.x.value = find_child(e.parentNode, "rect[x]").attributes.x.value + 3;
            }}
            if (e.attributes.width != undefined) {{
                orig_save(e, "width");
                e.attributes.width.value = parseFloat(e.attributes.width.value) * ratio;
            }}
        }}

        if (e.childNodes == undefined) return;
        for (var i = 0, c = e.childNodes; i < c.length; i++) {{
            zoom_child(c[i], x - {Geometry.XPad1}, ratio);
        }}
    }}
    function zoom_parent(e, ratio) {{
        if (e.attributes) {{
            if (e.attributes.x != undefined) {{
                orig_save(e, "x");
                e.attributes.x.value = {Geometry.XPad1};
            }}
            if (e.attributes.width != undefined) {{
                orig_save(e, "width");
                if (ratio) {{
                    // This parent node needs to be scaled instead of spanning
                    // the entire width (e.g., overlay rectangles).
                    e.attributes.width.value = parseFloat(e.attributes.width.value) * ratio;
                }} else {{
                    e.attributes.width.value = parseInt(svg.width.baseVal.value) - ({Geometry.XPad1} * 2);
                }}
            }}
        }}
        if (e.childNodes == undefined) return;

        // We are scaling a group with an overlay rectangle. All the elements
        // within that group should span the entire width *except* the overlay,
        // which needs to be scaled.
        if (e.nodeName === "g" && exclusiveMode && !isDiff) {{
            var {{ rect, overlay }} = getGroupRectangles(e);
            const overlay_ratio = (svg.width.baseVal.value - 2 * {Geometry.XPad1}) / rect.getAttribute("width");
            for (var i = 0, c = e.childNodes; i < c.length; i++) {{
                if (c[i] === overlay) {{
                    zoom_parent(c[i], overlay_ratio);
                }} else {{
                    zoom_parent(c[i], null);
                }}
            }}
            return;
        }}
        // We are scaling some other element.
        for (var i = 0, c = e.childNodes; i < c.length; i++) {{
            zoom_parent(c[i], null);
        }}
    }}
    function zoom(node) {{
        var attr = find_child(node, "rect").attributes;
        var width = parseFloat(attr.width.value);
        var xmin = parseFloat(attr.x.value);
        var xmax = parseFloat(xmin + width);
        var ymin = parseFloat(attr.y.value);
        var ratio = (svg.width.baseVal.value - 2 * {Geometry.XPad1}) / width;

        // XXX: Workaround for JavaScript float issues (fix me)
        var fudge = 0.0001;

        unzoombtn.classList.remove("hide");

        var el = document.getElementById("frames").children;
        for (var i = 0; i < el.length; i++) {{
            var e = el[i];
            var a = find_child(e, "rect").attributes;
            var ex = parseFloat(a.x.value);
            var ew = parseFloat(a.width.value);
            var upstack;
            // Is it an ancestor
            if ({1 if settings.inverted else 0} == 0) {{
                upstack = parseFloat(a.y.value) > ymin;
            }} else {{
                upstack = parseFloat(a.y.value) < ymin;
            }}
            if (upstack) {{
                // Direct ancestor
                if (ex <= xmin && (ex+ew+fudge) >= xmax) {{
                    e.classList.add("parent");
                    zoom_parent(e, null);
                    update_text(e);
                }}
                // not in current path
                else
                    e.classList.add("hide");
            }}
            // Children maybe
            else {{
                // no common path
                if (ex < xmin || ex + fudge >= xmax) {{
                    e.classList.add("hide");
                }}
                else {{
                    zoom_child(e, xmin, ratio);
                    update_text(e);
                }}
            }}
        }}
        search();
    }}
    function unzoom(dont_update_text) {{
        unzoombtn.classList.add("hide");
        var el = document.getElementById("frames").children;
        for(var i = 0; i < el.length; i++) {{
            el[i].classList.remove("parent");
            el[i].classList.remove("hide");
            zoom_reset(el[i]);
            if(!dont_update_text) update_text(el[i]);
        }}
        search();
    }}
    function clearzoom() {{
        unzoom();
    }}

    // search
    function toggle_ignorecase() {{
        ignorecase = !ignorecase;
        if (ignorecase) {{
            ignorecaseBtn.classList.add("show");
        }} else {{
            ignorecaseBtn.classList.remove("show");
        }}
        reset_search();
        search();
    }}
    function reset_search() {{
        var el = document.getElementById("frames").children;
        for (var i = 0; i < el.length; i++) {{
            var {{ rect, overlay }} = getGroupRectangles(el[i]);
            if (overlay) {{
                orig_load(overlay, "fill");
                if (!isDiff) {{
                    rect.setAttribute("fill", "white");
                }} else {{
                    orig_load(rect, "fill");
                }}
            }} else {{
                orig_load(rect, "fill");
            }}
        }}
        searching = 0;
        currentSearchTerm = null;
        searchbtn.classList.remove("show");
        searchbtn.firstChild.nodeValue = "Search"

        matchedSearchLabel.classList.add("hide");
        inclusiveLabel.classList.add("hide");
        exclusiveLabel.classList.add("hide");
        matchedSearchCount.nodeValue = "";
        matchedSearchIncl.nodeValue = "";
        matchedSearchExcl.nodeValue = "";

        if (isDiff) {{
            updateExclusiveView();
        }}
    }}

    function reset_search_hover() {{
        var el = document.getElementById("frames").children;
        var re = new RegExp(currentSearchTerm, ignorecase ? 'i' : '');
        for (var i = 0; i < el.length; i++) {{
            var func = g_to_func(el[i]);
            var {{ rect, overlay }} = getGroupRectangles(el[i]);
            if (rect.getAttribute("fill") != "{Colors.RGBhover}" && (!overlay || overlay.getAttribute("fill") != "{Colors.RGBhover}")) continue;

            if (func.match(re)) {{
                if (isDiff) {{
                    if (overlay) {{
                        overlay.attributes.fill.value = "{Colors.RGBsearch}";
                    }} else {{
                        rect.attributes.fill.value = "{Colors.RGBsearch}";
                    }}
                }} else {{
                    rect.attributes.fill.value = "{Colors.RGBsearch}";
                    if (overlay) {{
                        overlay.attributes.fill.value = "{Colors.RGBsearchOverlay}";
                    }}
                }}
            }} else {{
                if (overlay) {{
                    orig_load(overlay, "fill");
                    if (!isDiff) {{
                        rect.setAttribute("fill", "white");
                    }}
                }} else {{
                    orig_load(rect, "fill");
                }}
            }}
        }}
        hoverSearchTerm = null;
        if (!searching) {{
            inclusiveLabel.classList.add("hide");
            exclusiveLabel.classList.add("hide");
        }}
        matchedHoverLabel.classList.add("hide");
        matchedHoverCount.nodeValue = "";
        matchedHoverIncl.nodeValue = "";
        matchedHoverExcl.nodeValue = "";
    }}

    function search_prompt() {{
        if (!searching) {{
            var term = prompt("Enter a search term (regexp " +
                "allowed, eg: ^ext4_)"
                + (ignorecase ? ", ignoring case" : "")
                + "\\nPress Ctrl-i to toggle case sensitivity", "");
            if (term != null) search(term);
        }} else {{
            reset_search();
        }}
    }}
    function search(term) {{
        if (term) currentSearchTerm = term;
        var re = new RegExp(currentSearchTerm, ignorecase ? 'i' : '');

        var res = find_frames(re, false);
        if (!searching)
            return;
        searchbtn.classList.add("show");
        searchbtn.firstChild.nodeValue = "Reset Search";

        // display matched percent
        var matched = calculate_matched(res.matches, res.maxwidth);
        matchedSearchLabel.classList.remove("hide");
        inclusiveLabel.classList.remove("hide");
        exclusiveLabel.classList.remove("hide");
        matchedSearchCount.nodeValue = matched.count;
        matchedSearchIncl.nodeValue = matched.totalInclSamples + " {settings.count_name}, " + matched.pct + "%";
        matchedSearchExcl.nodeValue = matched.totalExclSamples + " {settings.count_name}, " + matched.pct_excl + "%";
    }}
    function search_hover(term) {{
        if (term) hoverSearchTerm = term;

        var res = find_frames(term, true);

        // display matched percent
        var matched = calculate_matched(res.matches, res.maxwidth);
        inclusiveLabel.classList.remove("hide");
        exclusiveLabel.classList.remove("hide");
        matchedHoverLabel.classList.remove("hide");
        matchedHoverCount.nodeValue = matched.count;
        matchedHoverIncl.nodeValue = matched.totalInclSamples + " {settings.count_name}, " + matched.pct + "%";
        matchedHoverExcl.nodeValue = matched.totalExclSamples + " {settings.count_name}, " + matched.pct_excl + "%";
    }}
    // The func_expr may be either a regex or a simple string
    function find_frames(func_expr, is_hover) {{
        var el = document.getElementById("frames").children;
        var matches = new Object();
        var maxwidth = 0;
        for (var i = 0; i < el.length; i++) {{
            var e = el[i];
            var func = g_to_func(e);
            var {{ rect, overlay }} = getGroupRectangles(e);
            if (func == null || rect == null)
                continue;

            // Save max width. Only works as we have a root frame
            var w = parseFloat(rect.attributes.width.value);
            if (w > maxwidth)
                maxwidth = w;

            // Skip nodes that were hidden due to zoom.
            if (el[i].classList.contains("hide")) continue;

            if ((is_hover && func.startsWith(func_expr)) || (!is_hover && func.match(func_expr))) {{
                // highlight
                var x = parseFloat(rect.attributes.x.value);
                if (overlay) {{
                    orig_save(overlay, "fill");
                    if (isDiff) {{
                        overlay.attributes.fill.value = is_hover ? "{Colors.RGBhover}" : "{Colors.RGBsearch}";
                    }} else {{
                        rect.attributes.fill.value = is_hover ? "{Colors.RGBhover}" : "{Colors.RGBsearch}";
                        overlay.attributes.fill.value = is_hover ? "{Colors.RGBhoverOverlay}" : "{Colors.RGBsearchOverlay}";
                    }}
                }} else {{
                    orig_save(rect, "fill");
                    rect.attributes.fill.value = is_hover ? "{Colors.RGBhover}" : "{Colors.RGBsearch}";
                }}

                // remember matches
                const {{ incl, excl }} = parseFormattedSuffix(func);
                if (matches[x] == undefined) {{
                    matches[x] = [];
                }}
                var w_excl = w * parseFloat(el[i].getAttribute("data-e") || "0") / 100;
                matches[x].push([w, w_excl, incl, excl]);
                if (!is_hover) {{
                    searching = 1;
                }}
            }}
        }}
        return {{ maxwidth: maxwidth, matches: matches }};
    }}
    function calculate_matched(matches, maxwidth) {{
        // calculate absolute and percent matched, excluding vertical overlap
        var matchCount = 0;
        var inclCount = 0;
        var exclCount = 0;
        var totalInclSamples = 0;
        var totalExclSamples = 0;
        var lastx = -1;
        var lastw = 0;
        var keys = Array();
        for (k in matches) {{
            if (matches.hasOwnProperty(k))
                keys.push(k);
        }}
        // sort the matched frames by their x location
        // ascending, then width descending
        keys.sort(function(a, b){{
            return a - b;
        }});
        // Step through frames saving only the biggest bottom-up frames
        // thanks to the sort order. This relies on the tree property
        // where children are always smaller than their parents.
        var fudge = 0.0001;	// JavaScript floating point
        for (var k in keys) {{
            var x = parseFloat(keys[k]);
            matchCount += matches[keys[k]].length;
            var parent = matches[keys[k]][0];
            for (var frameIdx in matches[keys[k]]) {{
                var [width, width_excl, incl, excl] = matches[keys[k]][frameIdx];
                if (width > parent[0]) parent = [width, width_excl, incl, excl];
                totalExclSamples += excl;
                exclCount += width_excl;
            }}
            if (x >= lastx + lastw - fudge) {{
                inclCount += parent[0];
                totalInclSamples += parent[2];
                lastx = x;
                lastw = parent[0];
            }}
        }}
        // compute matched percent
        var pct = 100 * inclCount / maxwidth;
        var pct_excl = 100 * exclCount / maxwidth;
        if (pct != 100) pct = pct.toFixed(2)
        if (pct_excl != 100) pct_excl = pct_excl.toFixed(2)
        return {{
            pct: pct,
            pct_excl: pct_excl,
            totalInclSamples: formatWithSuffix(totalInclSamples),
            totalExclSamples: formatWithSuffix(totalExclSamples),
            count: matchCount
        }};
    }}

    // exclusive/inclusive toggle
    function toggleExclusive() {{
        exclusiveMode = !exclusiveMode;
        var excToggleBtn = document.getElementById("excToggle");
        if (exclusiveMode) {{
            excToggleBtn.firstChild.nodeValue = "Show inclusive"
            updateExclusiveView();
        }} else {{
            excToggleBtn.firstChild.nodeValue = "Show exclusive"
            removeExclusiveView();
        }}
    }}

    function getGroupRectangles(group) {{
        var rects = group.getElementsByTagName("rect");
        if (!rects) {{
            return {{ rect: null, overlay: null }};
        }}
        return {{ rect: rects.item(0), overlay: rects.item(1) }}
    }}

    function removeExclusiveView() {{
        // Here we want to iterate over all frames since the graph may be
        // zoomed and unzooming it later might show the leftover overlay rects.
        var frames = document.getElementById("frames").children;
        for (var i = 0; i < frames.length; i++) {{
            var g = frames[i];
            var {{ rect, overlay }} = getGroupRectangles(g);
            if (!overlay) continue;

            if (!isDiff) {{
                rect.setAttribute("fill", overlay.getAttribute("fill"));
                if (rect.getAttribute("fill") == "{Colors.RGBsearchOverlay}") {{
                    rect.setAttribute("fill", "{Colors.RGBsearch}");
                }}
            }}
            overlay.remove();
        }}
    }}

    function updateExclusiveView() {{
        if (!exclusiveMode) return;

        var frames = document.getElementById("frames").children;
        for (var i = 0; i < frames.length; i++) {{
            var g = frames[i];
            var {{ rect, overlay }} = getGroupRectangles(g);

            // We might need to first create the overlay rectangle.
            if (!overlay) {{
                overlay = rect.cloneNode(false);
                g.insertBefore(overlay, rect.nextSibling);
            }}

            if (isDiff) {{
                // Now adjust the color. The exclusive diff color is stored in
                // the group's "data-ed" attr.
                const excDeltaColor = g.getAttribute("data-ed") || "white";
                overlay.setAttribute("fill", excDeltaColor);
                if (rect.getAttribute("fill") == "{Colors.RGBsearch}") {{
                    orig_save(overlay, "fill");
                    overlay.setAttribute("fill", "{Colors.RGBsearch}");
                }}
            }} else {{
                // Now adjust the geometry. The exclusive consumption relative
                // to the width of the frame is stored in the group's "data-e"
                // attribute.
                const excRelative = parseFloat(g.getAttribute("data-e") || "0");
                const rectWidth = parseFloat(rect.getAttribute("width"));
                const overlayWidth = (rectWidth * excRelative / 100);
                overlay.setAttribute("width", overlayWidth);
                // The frame may be zoomed: adjust _orig_width if needed.
                var unzoomed_width = overlay.getAttribute("_orig_width");
                if (unzoomed_width) {{
                    overlay.setAttribute("_orig_width", unzoomed_width * excRelative / 100);
                }}
                if (rect.getAttribute("fill") == "{Colors.RGBsearch}") {{
                    overlay.setAttribute("fill", "{Colors.RGBsearchOverlay}");
                }} else {{
                    rect.setAttribute("fill", "white");
                }}
            }}
        }}
    }}
]]>
</script>
    """


#### SECTION: FILE PARSING
# To parse a folded file, use the 'parse_folded_profile' function which selects
# the correct parsing function based on the input parameters and folded file
# content (diff or not). The "private" parsing functions (with a leading
# underscore) are specialized for concrete folded profile types and are not
# expected to be used directly.
#
# Note that the parsing loop is one of the two hot loops in the program.
# To optimize it as much as possible, we crafted specialized parsing functions
# for each of the four input variants (diff/no-diff data and normal/reverse
# stacks) to avoid unnecessary inner branches and function calls.


class FoldedData:
    """Parsed non-differential folded profile.

    The ``data`` are intentionally stored as an Iterable to facilitate
    compatible interface with lazy parsers.

    :ivar data: an iterable of parsed ``(stack, count)`` rows.
    :ivar total: the sum of all counts.
    :ivar is_diff: always ``False`` for static typing discrimination.
    """

    __slots__ = "data", "total", "is_diff"

    def __init__(self, data: Iterable[tuple[str, float]], total: float) -> None:
        """Initialize an object.

        :param data: an iterable of ``(stack, count)`` rows.
        :param total: the sum of all counts.
        """
        self.data: Iterable[tuple[str, float]] = data
        self.total: float = total
        self.is_diff: Literal[False] = False


class FoldedDiffData:
    """Parsed differential folded profile.

    The ``data`` are intentionally stored as an Iterable to facilitate
    compatible interface with lazy parsers, e.g., the lazy parser in
    difffolded.py.

    See: https://www.brendangregg.com/blog/2014-11-09/differential-flame-graphs.html

    :ivar data: an iterable of ``(stack, baseline count, target count)`` rows.
    :ivar total: the sum of target counts (corresponds to how the Perl script
          interprets the 'total' consumption in differential folded profiles).
    :ivar is_diff: always ``True`` for static typing discrimination.
    """

    __slots__ = "data", "total", "is_diff"

    def __init__(self, data: Iterable[tuple[str, float, float]], total: float) -> None:
        """Initialize an object.

        :param data: an iterable of ``(stack, baseline count, target count)``.
        :param total: the sum of all counts.
        """
        self.data: Iterable[tuple[str, float, float]] = data
        self.total: float = total
        self.is_diff: Literal[True] = True


class InputTextFile:
    """A helper context manager for reading from a file or stdin correctly.

    There is no easy built-in way to read from both an external file that
    needs to be opened and closed, and the standard input which is already
    opened and should not be closed. This simple wrapper handles both cases
    and exposes interface to interact with both input types identically.

    Note that this wrapper works only for text files in read mode.
    """

    def __init__(self, input_file: Path | None, mode: OpenTextModeReading) -> None:
        """Initialize the CM object.

        :param input_file: a path to the input file, or ``None`` for stdin.
        :param mode: a read-only file opening mode.
        """
        # We cannot simply assign the grids as it would not propagate outside the object.
        self.input_file: Path | None = input_file
        self.mode: OpenTextModeReading = mode
        self.handle: TextIO = sys.stdin

    def __enter__(self) -> TextIO:
        """Opens the input file if it is supplied.

        :return: a handle to the opened file or stdin.
        """
        if self.input_file is not None:
            self.handle = open(self.input_file, self.mode)
        return self.handle

    def __exit__(
        self,
        _: Type[BaseException] | None,
        __: BaseException | None,
        ___: TracebackType | None,
    ) -> None:
        """Closes the input file but not the stdin.

        Any unhandled exceptions should be propagated outside the CM.

        :param _: the type of the exception that occurred, if any
        :param __: the actual exception object, if any
        :param ___: the traceback of the error, if any
        """
        if self.input_file is not None:
            self.handle.close()


def parse_folded_profile(
    input_file: Path | None, is_flame_chart: bool, is_stack_reverse: bool
) -> FoldedData | FoldedDiffData:
    """Parse a folded profile file.

    This is the top-level parsing function which determines the type of the
    folded profile and selects the appropriate optimized parsing function for
    the type, i.e., (non-)differential, forward or reversed stacks.

    :param input_file: a path to the folded profile, or ``None`` for stdin.
    :param is_flame_chart: we are drawing a flame chart; the parsing functions
           should preserve the order of the records instead of sorting them as
           in the case of flame graphs.
    :param is_stack_reverse: the stacks in the folded profile are in the
           callee-to-caller (instead of caller-to-callee) order.

    :return: the parsed (differential) folded profile.
    """
    result: FoldedData | FoldedDiffData
    ignored: int = 0
    with InputTextFile(input_file, "r") as input_handle:
        # Peek column count from the first line.
        # We sadly cannot use seek(0) as we might be working with the stdin, so
        # we need to pass that line for processing to the specialized functions.
        first_line = input_handle.readline()
        _, *counts = first_line.split()
        is_diff = len(counts) == 2
        # Select differential vs single-column and reversed-stack parsers.
        parse_variants: dict[
            tuple[bool, bool],
            Callable[[TextIO, str, bool], tuple[FoldedData, int]]
            | Callable[[TextIO, str, bool], tuple[FoldedDiffData, int]],
        ] = {
            (False, False): _parse_folded,
            (False, True): _parse_reverse_folded,
            (True, False): _parse_differential_folded,
            (True, True): _parse_reverse_differential_folded,
        }
        parse_fn = parse_variants[is_diff, is_stack_reverse]
        result, ignored = parse_fn(input_handle, first_line, is_flame_chart)
    # Report possible input format violations.
    if ignored:
        print(
            f"WARNING: Ignored {ignored} lines with invalid format",
            file=sys.stderr,
        )
    return result


def validate_profile_total(profile: FoldedData | FoldedDiffData, settings: Settings) -> int:
    """Validate the sum of all counts and the ``--total`` option.

    Returns a possibly updated ``--total`` value.

    :param profile: a parsed folded profile.
    :param settings: rendering and processing options.

    :return: the possibly adjusted ``--total`` value.
    """
    if profile.total == 0:
        print("ERROR: No stack counts found", file=sys.stderr)
        print(create_error_svg(settings))
        sys.exit(2)

    if settings.count_name == "samples":
        # Warn only while the default ``samples`` label is still in use.
        if profile.total < 100:
            print(
                f"WARNING: Stack count is low ({profile.total}). Did something" " go wrong?",
                file=sys.stderr,
            )

    if 0 < settings.total < profile.total:
        if settings.total / profile.total > 0.02:
            # Warn only if the difference is significant.
            print(
                f"WARNING: Specified --total {settings.total} is less than"
                f" actual total {profile.total}. Ignoring the --total"
                " value.",
                file=sys.stderr,
            )
        return int(profile.total)
    return settings.total


def _parse_folded(
    input_handle: TextIO, first_line: str, is_flame_chart: bool
) -> tuple[FoldedData, int]:
    """Parse a standard (non-differential) folded profile.

    :param input_handle: a file handle containing a folded profile.
    :param first_line: an already read line used to determine the profile type.
    :param is_flame_chart: we are drawing a flame chart; the order of the
           records should be preserved.

    :return: a pair ``(FoldedData, ignored_line_count)``.
    """
    data: list[tuple[str, float]] = []
    total: float = 0.0
    ignored: int = 0

    # Optimize dot access.
    str_rsplit = str.rsplit
    list_append = list.append

    # This is a bit of a hack to not duplicate the processing code for both the
    # already read line and the file handle.
    for source in ([first_line], input_handle):
        for line in source:
            try:
                # Using ``rsplit(..., maxsplit=1)`` is faster because the count
                # is at the end of line.
                stack, count_str = str_rsplit(line, maxsplit=1)
                count = float(count_str)
                total += count
                list_append(data, (stack, count))
            except ValueError:
                ignored += 1

    # Lexicographic stack order unless we are generating a flame chart.
    if not is_flame_chart:
        data.sort(key=itemgetter(0))
    return FoldedData(data, total), ignored


def _parse_reverse_folded(
    input_handle: TextIO, first_line: str, is_flame_chart: bool
) -> tuple[FoldedData, int]:
    """Parse a standard (non-differential) folded profile with reversed frames.

    The parse function reverses the frames in the stacks such that they are in
    a unified caller-to-callee order.

    :param input_handle: a file handle containing a folded profile.
    :param first_line: an already read line used to determine the profile type.
    :param is_flame_chart: we are drawing a flame chart; the order of the
           records should be preserved.

    :return: a pair ``(FoldedData, ignored_line_count)``.
    """
    data: list[tuple[str, float]] = []
    total: float = 0.0
    ignored: int = 0

    # Optimize dot access.
    str_rsplit = str.rsplit
    str_split = str.split
    str_join = str.join
    list_append = list.append

    for source in ([first_line], input_handle):
        for line in source:
            try:
                stack, count_str = str_rsplit(line, maxsplit=1)
                count = float(count_str)
                total += count
                # TODO: We can defer the reversal until the nodes processing when
                #  generating flame charts since we do not have to sort the stacks.
                list_append(data, (str_join(";", reversed(str_split(stack, ";"))), count))
            except ValueError:
                ignored += 1

    if not is_flame_chart:
        data.sort(key=itemgetter(0))
    return FoldedData(data, total), ignored


def _parse_differential_folded(
    input_handle: TextIO, first_line: str, is_flame_chart: bool
) -> tuple[FoldedDiffData, int]:
    """Parse a differential folded profile.

    :param input_handle: a file handle containing a diff folded profile.
    :param first_line: an already read line used to determine the profile type.
    :param is_flame_chart: we are drawing a flame chart; the order of the
           records should be preserved.

    :return: ``(FoldedDiffData, ignored_line_count)``.
    """
    data: list[tuple[str, float, float]] = []
    total: float = 0.0
    ignored: int = 0

    # Optimize dot access.
    str_rsplit = str.rsplit
    list_append = list.append

    for source in ([first_line], input_handle):
        for line in source:
            try:
                stack, count_str, count2_str = str_rsplit(line, maxsplit=2)
                count = float(count_str)
                count2 = float(count2_str)
                total += count2
                list_append(data, (stack, count, count2))
            except ValueError:
                ignored += 1

    if not is_flame_chart:
        data.sort(key=itemgetter(0))
    return FoldedDiffData(data, total), ignored


def _parse_reverse_differential_folded(
    input_handle: TextIO, first_line: str, is_flame_chart: bool
) -> tuple[FoldedDiffData, int]:
    """Parse a differential folded profile with reversed frames.

    The parse function reverses the frames in the stacks such that they are in
    a unified caller-to-callee order.

    :param input_handle: a file handle containing a folded diff profile.
    :param first_line: an already read line used to determine the profile type.
    :param is_flame_chart: we are drawing a flame chart; the order of the
           records should be preserved.

    :return: a pair ``(FoldedDiffData, ignored_line_count)``.
    """
    data: list[tuple[str, float, float]] = []
    total: float = 0.0
    ignored: int = 0

    # Optimize dot access.
    str_rsplit = str.rsplit
    str_spl = str.split
    str_join = str.join
    list_append = list.append

    for source in ([first_line], input_handle):
        for line in source:
            try:
                stack, count_str, count2_str = str_rsplit(line, maxsplit=2)
                count = float(count_str)
                count2 = float(count2_str)
                total += count2
                # TODO: We can defer the reversal until the nodes processing when
                #  generating flame charts since we do not have to sort the stacks.
                list_append(
                    data,
                    (str_join(";", reversed(str_spl(stack, ";"))), count, count2),
                )
            except ValueError:
                ignored += 1

    if not is_flame_chart:
        data.sort(key=itemgetter(0))
    return FoldedDiffData(data, total), ignored


#### SECTION: STACKS PROCESSING
# To process (parsed) folded data, use the 'process_stacks' function which
# selects the correct processing function based on the folded data type (diff
# or not) and flamegraph type (CPU or off-CPU chain graphs). The "private"
# processing functions (with a leading underscore) are not expected to be used
# directly.
#
# The processing loop is the second hot loop in the program. To optimize it as
# much as possible, we crafted a specialized processing function for each of
# the four variants and manually inlined the 'flow' helper function found in
# the original Perl script. This leads to some code duplication but improves
# performance.
#
# Notable implementation changes compared to the Perl version:
#
# - The resulting processed nodes are stored in a sequential data structure
#   (list) instead of a dictionary. An associative structure is unnecessarily
#   expensive given that the data are later processed sequentially, anyway.
#
# - The min_width filtering is done during the processing instead of postponing
#   it to a second pass through the data. This allows us to skip processing of
#   potentially long stacks that would be discarded later.
#
# - The resulting nodes do not contain the artificial root node.
#
# - We do not pop from the 'tmp' dictionary as the number of records is
#   generally quite low (should roughly correspond to the number of frames in
#   the resulting flamegraph) and removing the elements incurs a small
#   performance penalty.


class ProcessedNodes:
    """Stores a sequence of nodes representing non-differential graph frames.

    The sequence contains only nodes that satisfy the 'min_width' threshold and
    should be thus drawn in the flame graph.

    :ivar nodes: a sequence of ``(name, depth, end_time, start_time,
          exclusive_time)`` records.
    :ivar max_trace: the length of the longest trace after filtering.
    :ivar is_diff: always ``False`` for static typing discrimination.
    """

    __slots__ = "nodes", "max_trace", "is_diff"

    def __init__(
        self, nodes: Sequence[tuple[str, int, float, float, float]], max_trace: int
    ) -> None:
        """Initialize an object.

        :param nodes: a ``(name, depth, end_time, start_time, exclusive_time)``
               sequence.
        :param max_trace: the length of the longest trace after filtering.
        """
        self.nodes: Sequence[tuple[str, int, float, float, float]] = nodes
        self.max_trace: int = max_trace
        self.is_diff: Literal[False] = False


class ProcessedDiffNodes:
    """Stores a sequence of nodes representing differential graph frames.

    :ivar nodes: a sequence of ``(name, depth, end_time, start_time,
          exclusive_time, inclusive_delta, exclusive_delta)`` records.
    :ivar max_trace: the length of the longest trace after filtering.
    :ivar max_delta_excl: the maximum observed delta between the baseline and
          target *exclusive* counts of a stack (used for scaling differential
          hues). Note that compared to ``max_trace`,` this maximum ignores the
          ``min_width`` filtering to stay consistent with the original Perl
          script.
    :ivar max_delta_incl: the maximum observed delta between the baseline and
          target *inclusive* counts (see ``max_delta_excl``).
    :ivar is_diff: always ``True`` for static typing discrimination.
    """

    __slots__ = "nodes", "max_trace", "max_delta_excl", "max_delta_incl", "is_diff"

    def __init__(
        self,
        nodes: Sequence[tuple[str, int, float, float, float, float, float]],
        max_trace: int,
        max_delta_excl: float,
        max_delta_incl: float,
    ) -> None:
        """Initialize an object.

        :param nodes: a ``(name, depth, end_time, start_time, exclusive_time,
               inclusive_delta, exclusive_delta)`` sequence.
        :param max_trace: the length of the longest trace after filtering.
        :param max_delta_excl: the maximum observed delta between the baseline
               and target *exclusive* counts of a stack (used for scaling
               differential hues).
        :param max_delta_excl: the maximum observed delta between the baseline
               and target *inclusive* counts of a stack (used for scaling
               differential hues).
        """
        self.nodes: Sequence[tuple[str, int, float, float, float, float, float]] = nodes
        self.max_trace: int = max_trace
        self.max_delta_excl: float = max_delta_excl
        self.max_delta_incl: float = max_delta_incl
        self.is_diff: Literal[True] = True


def process_stacks(
    profile: FoldedData | FoldedDiffData, settings: Settings
) -> tuple[ProcessedNodes | ProcessedDiffNodes, Geometry]:
    """Processes folded stacks into drawable frames.

    This is the top-level processing function which selects the appropriate
    optimized processing function for the stacks type. Also note that the
    resulting nodes are already filtered w.r.t. the ``min_width`` parameter.

    :param profile: a parsed folded profile (single or differential).
    :param settings: rendering and processing options.

    :return: the processed nodes and a matching ``Geometry`` instance.
    """
    # Compute the width threshold so stacks can be filtered during traversal.
    total = max(settings.total, profile.total)
    width_per_count_unit = (settings.image_width - 2 * Geometry.XPad1) / total
    if settings.min_width_relative:
        min_width_threshold: float = settings.min_width_value * total / 100
    else:
        min_width_threshold = settings.min_width_value / width_per_count_unit
    # Dispatch to the correct specialized function by profile type. The explicit
    # branches (in contrast to a dictionary dispatch, e.g., in the
    # ``parse_folded_profile``) preserve narrowed types for mypy.
    nodes: ProcessedNodes | ProcessedDiffNodes
    if profile.is_diff:
        if settings.colors == ColorPalettes.CHAIN:
            nodes = _process_differential_waker_stacks(profile, min_width_threshold)
        else:
            nodes = _process_differential_stacks(profile, min_width_threshold)
    else:
        if settings.colors == ColorPalettes.CHAIN:
            nodes = _process_waker_stacks(profile, min_width_threshold)
        else:
            nodes = _process_stacks(profile, min_width_threshold)
    # Create a geometry object that computes many parameters for rendering
    # the SVG.
    geometry = Geometry(
        settings,
        profile.total,
        width_per_count_unit,
        nodes.max_trace,
    )
    return nodes, geometry


def _process_stacks(profile: FoldedData, min_width: float) -> ProcessedNodes:
    """Processes non-differential non-waker folded stacks into drawable frames.

    :param profile: a parsed folded profile.
    :param min_width: a filtering threshold.

    :return: processed nodes that should be drawn as frames.
    """
    prev_stack: list[str] = []
    time: float = 0.0
    max_trace: int = 0
    nodes: list[tuple[str, int, float, float, float]] = []
    tmp: dict[tuple[str, int], tuple[float, float]] = {}

    # Optimize dot access.
    str_split = str.split
    list_append = list.append

    for stack, count in profile.data:
        this_stack = str_split(stack, ";")
        # -- BEGIN: inlined 'flow'.
        prev_stack_len, this_stack_len = len(prev_stack), len(this_stack)
        max_common_len = min(prev_stack_len, this_stack_len)
        len_same = 0
        # Consecutive stacks usually share a common initial sub-sequences of
        # frames. We must skip these frames now as they will be processed later.
        while len_same < max_common_len and prev_stack[len_same] == this_stack[len_same]:
            len_same += 1

        # First process the remaining differing frames in the old stack and
        # create the actual nodes that should be drawn.
        for depth in range(len_same, prev_stack_len):
            stime, exc_time = tmp[(prev_stack[depth], depth)]
            if (time - stime) < min_width:
                # All the callee nodes must have lower or equal time consumption
                # than (time - stime), and thus will fail the check as well.
                break
            list_append(nodes, (prev_stack[depth], depth, time, stime, exc_time))
            max_trace = max(depth, max_trace)

        # The remaining differing frames in the current stack must be stored
        # for processing in the next iteration.
        # The exclusive time belongs to the leaf frame of this stack.
        for depth in range(len_same, this_stack_len - 1):
            tmp[(this_stack[depth], depth)] = (time, 0.0)
        if this_stack_len > len_same:
            tmp[(this_stack[-1], this_stack_len - 1)] = (time, count)
        # -- END: inlined 'flow'.
        prev_stack = this_stack
        time += count

    # Finish processing the last stack.
    for idx, frame in enumerate(prev_stack):
        stime, exc_time = tmp[(frame, idx)]
        if (time - stime) < min_width:
            break
        list_append(nodes, (frame, idx, time, stime, exc_time))
        max_trace = max(idx, max_trace)
    return ProcessedNodes(nodes, max_trace)


def _process_waker_stacks(profile: FoldedData, min_width: float) -> ProcessedNodes:
    """Processes non-differential waker folded stacks into drawable frames.

    See: https://www.brendangregg.com/FlameGraphs/offcpuflamegraphs.html#Chain

    :param profile: a parsed folded profile.
    :param min_width: a filtering threshold.

    :return: processed nodes that should be drawn as frames.
    """
    prev_stack: list[str] = []
    time: float = 0.0
    max_trace: int = 0
    nodes: list[tuple[str, int, float, float, float]] = []
    tmp: dict[tuple[str, int], tuple[float, float]] = {}

    # Optimize dot access.
    str_split = str.split
    list_append = list.append

    # See ``_process_stacks`` for the shared unwinding logic.
    for stack, count in profile.data:
        this_stack = str_split(stack, ";")
        prev_stack_len, this_stack_len = len(prev_stack), len(this_stack)
        # Annotate frames after ``--`` with ``_[w]`` for coloring purposes.
        try:
            waker_start = this_stack.index("--") + 1
            for depth in range(waker_start + 1, this_stack_len):
                if this_stack[depth] != "--":
                    this_stack[depth] += "_[w]"
        except ValueError:
            pass
        # -- BEGIN: inlined 'flow'.
        max_common_len = min(prev_stack_len, this_stack_len)
        len_same = 0
        while len_same < max_common_len and prev_stack[len_same] == this_stack[len_same]:
            len_same += 1

        for depth in range(len_same, prev_stack_len):
            stime, exc_time = tmp[(prev_stack[depth], depth)]
            if (time - stime) < min_width:
                break
            list_append(nodes, (prev_stack[depth], depth, time, stime, exc_time))
            max_trace = max(depth, max_trace)

        # The exclusive time belongs to the leaf frame of this stack.
        for depth in range(len_same, this_stack_len - 1):
            tmp[(this_stack[depth], depth)] = (time, 0.0)
        if this_stack_len > len_same:
            tmp[(this_stack[-1], this_stack_len - 1)] = (time, count)
        # -- END: inlined 'flow'.
        prev_stack = this_stack
        time += count

    for idx, frame in enumerate(prev_stack):
        stime, exc_time = tmp[(frame, idx)]
        if (time - stime) < min_width:
            break
        list_append(nodes, (frame, idx, time, stime, exc_time))
        max_trace = max(idx, max_trace)
    return ProcessedNodes(nodes, max_trace)


def _process_differential_stacks(profile: FoldedDiffData, min_width: float) -> ProcessedDiffNodes:
    """Processes differential non-waker folded stacks into drawable frames.

    :param profile: a parsed folded profile.
    :param min_width: a filtering threshold.

    :return: processed nodes that should be drawn as frames.
    """
    prev_stack: list[str] = []
    time_target: float = 0.0
    time_base: float = 0.0
    max_trace: int = 0
    max_delta_excl: float = 1.0
    max_delta_incl: float = 1.0
    nodes: list[tuple[str, int, float, float, float, float, float]] = []
    tmp: dict[tuple[str, int], tuple[float, float, float, float]] = {}

    # Optimize dot access.
    str_split = str.split
    list_append = list.append

    # See ``_process_stacks`` for the shared unwinding logic.
    for stack, count_base, count_target in profile.data:
        this_stack = str_split(stack, ";")
        prev_stack_len, this_stack_len = len(prev_stack), len(this_stack)
        delta = count_target - count_base
        max_delta_excl = max(max_delta_excl, abs(delta))
        # -- BEGIN: inlined 'flow'.
        max_common_len = min(prev_stack_len, this_stack_len)
        len_same = 0
        while len_same < max_common_len and prev_stack[len_same] == this_stack[len_same]:
            len_same += 1

        for depth in range(len_same, prev_stack_len):
            stime_tar, stime_base, excl_time, excl_delta = tmp[(prev_stack[depth], depth)]
            inclusive_target: float = time_target - stime_tar
            incl_delta = inclusive_target - (time_base - stime_base)
            max_delta_incl = max(max_delta_incl, abs(incl_delta))
            if inclusive_target < min_width:
                break
            list_append(
                nodes,
                (
                    prev_stack[depth],
                    depth,
                    time_target,
                    stime_tar,
                    excl_time,
                    incl_delta,
                    excl_delta,
                ),
            )
            max_trace = max(depth, max_trace)

        # The delta and exclusive time belong to the leaf frame of this stack.
        for depth in range(len_same, this_stack_len - 1):
            tmp[(this_stack[depth], depth)] = (time_target, time_base, 0.0, 0.0)
        if this_stack_len > len_same:
            tmp[(this_stack[-1], this_stack_len - 1)] = (
                time_target,
                time_base,
                count_target,
                delta,
            )
        # -- END: inlined 'flow'.
        prev_stack = this_stack
        time_target += count_target
        time_base += count_base

    for idx, frame in enumerate(prev_stack):
        stime_tar, stime_base, excl_time, excl_delta = tmp[(frame, idx)]
        inclusive_target = time_target - stime_tar
        incl_delta = inclusive_target - (time_base - stime_base)
        max_delta_incl = max(max_delta_incl, abs(incl_delta))
        if inclusive_target < min_width:
            break
        list_append(nodes, (frame, idx, time_target, stime_tar, excl_time, incl_delta, excl_delta))
        max_trace = max(idx, max_trace)

    return ProcessedDiffNodes(nodes, max_trace, max_delta_excl, max_delta_incl)


def _process_differential_waker_stacks(
    profile: FoldedDiffData, min_width: float
) -> ProcessedDiffNodes:
    """Processes differential waker folded stacks into drawable frames.

    See: https://www.brendangregg.com/FlameGraphs/offcpuflamegraphs.html#Chain

    :param profile: a parsed folded profile.
    :param min_width: a filtering threshold.

    :return: processed nodes that should be drawn as frames.
    """
    prev_stack: list[str] = []
    time_target: float = 0.0
    time_base: float = 0.0
    max_trace: int = 0
    max_delta_excl: float = 1.0
    max_delta_incl: float = 1.0
    nodes: list[tuple[str, int, float, float, float, float, float]] = []
    tmp: dict[tuple[str, int], tuple[float, float, float, float]] = {}

    # Optimize dot access.
    str_split = str.split
    list_append = list.append

    # See ``_process_stacks`` for the shared unwinding logic.
    # See ``_process_differential_stacks`` for handling deltas.
    for stack, count_base, count_target in profile.data:
        this_stack = str_split(stack, ";")
        prev_stack_len, this_stack_len = len(prev_stack), len(this_stack)
        # Annotate frames after ``--`` with ``_[w]`` for coloring purposes.
        try:
            waker_start = this_stack.index("--") + 1
            for depth in range(waker_start + 1, this_stack_len):
                if this_stack[depth] != "--":
                    this_stack[depth] += "_[w]"
        except ValueError:
            pass
        delta = count_target - count_base
        max_delta_excl = max(max_delta_excl, abs(delta))
        # -- BEGIN: inlined 'flow'.
        max_common_len = min(prev_stack_len, this_stack_len)
        len_same = 0
        while len_same < max_common_len and prev_stack[len_same] == this_stack[len_same]:
            len_same += 1

        for depth in range(len_same, prev_stack_len):
            stime_tar, stime_base, excl_time, excl_delta = tmp[(prev_stack[depth], depth)]
            inclusive_target: float = time_target - stime_tar
            incl_delta = inclusive_target - (time_base - stime_base)
            max_delta_incl = max(max_delta_incl, abs(incl_delta))
            if inclusive_target < min_width:
                break
            list_append(
                nodes,
                (
                    prev_stack[depth],
                    depth,
                    time_target,
                    stime_tar,
                    excl_time,
                    incl_delta,
                    excl_delta,
                ),
            )
            max_trace = max(depth, max_trace)

        # The delta and exclusive time belong to the leaf frame of this stack.
        for depth in range(len_same, this_stack_len - 1):
            tmp[(this_stack[depth], depth)] = (time_target, time_base, 0.0, 0.0)
        if this_stack_len > len_same:
            tmp[(this_stack[-1], this_stack_len - 1)] = (
                time_target,
                time_base,
                count_target,
                delta,
            )
        # -- END: inlined 'flow'.
        prev_stack = this_stack
        time_target += count_target
        time_base += count_base

    for idx, frame in enumerate(prev_stack):
        stime_tar, stime_base, excl_time, excl_delta = tmp[(frame, idx)]
        inclusive_target = time_target - stime_tar
        incl_delta = inclusive_target - (time_base - stime_base)
        max_delta_incl = max(max_delta_incl, abs(incl_delta))
        if inclusive_target < min_width:
            break
        list_append(nodes, (frame, idx, time_target, stime_tar, excl_time, incl_delta, excl_delta))
        max_trace = max(idx, max_trace)

    return ProcessedDiffNodes(nodes, max_trace, max_delta_excl, max_delta_incl)


#### SECTION: FRAMES CONSTRUCTION
# To transform the processed nodes into flame graph frames, use the
# 'construct_frames' function which selects the correct specialized function
# based on the data type (diff or not) and the presence or absence of a
# name-attribute file.
#
# Constructing the frames is *usually* not a hot spot since the nodes have
# already been pre-filtered in the previous step. However, this depends on the
# 'min_width' parameter which might have been set such that (almost) no
# filtering was done. In such cases, the frames construction could become a new
# hot loop. As a precaution, we optimized the construction as well by providing
# optimized variants that attempt to remove as many unnecessary branches and
# user function calls as possible. This leads to some code duplication but
# improves performance in case of insufficient filtering.


def construct_frames(
    nodes: ProcessedNodes | ProcessedDiffNodes,
    geometry: Geometry,
    settings: Settings,
    colors: Colors,
) -> list[str]:
    """Translates the processed nodes into SVG ``<g>`` or ``<a>`` frames.

    This function creates the initial root frame and then calls the appropriate
    function to generate the nested frames, which is optimized for the
    particular input type, i.e., (non-)differential profile with(out) custom
    name attributes.

    :param nodes: graph nodes obtained from ``process_stacks``.
    :param geometry: rendering geometry for the SVG layout.
    :param settings: rendering and processing options.
    :param colors: coloring options for the SVG.

    :return: a list of SVG frame strings forming the flame graph content.
    """
    frames: list[str] = ['<g id="frames">\n']
    # Create the auxiliary full-width root frame.
    frames += _construct_root_frame(
        nodes, geometry, settings, colors, settings.root_node, geometry.total, 0
    )
    # Optionally create a sub-root frame when ``--total`` was specified.
    if settings.total:
        frames += _construct_root_frame(
            nodes, geometry, settings, colors, settings.sub_root_node, geometry.profile_total, 1
        )

    # Dispatch to the correct specialized function. Similarly to the
    # ``process_stacks`` function, we intentionally keep the explicit
    # branches (in contrast to a dictionary dispatch, e.g., in the
    # ``parse_folded_profile``) to preserve narrowed types for mypy.
    if nodes.is_diff:
        if settings.name_attr.attr_cache:
            _construct_node_diff_frames_with_attrs(nodes, frames, geometry, settings, colors)
        else:
            _construct_node_diff_frames(nodes, frames, geometry, settings, colors)
    else:
        if settings.name_attr.attr_cache:
            _construct_node_frames_with_attrs(nodes, frames, geometry, settings, colors)
        else:
            _construct_node_frames(nodes, frames, geometry, settings, colors)

    frames.append("</g>")
    return frames


def _construct_root_frame(
    nodes: ProcessedNodes | ProcessedDiffNodes,
    geometry: Geometry,
    settings: Settings,
    colors: Colors,
    root_name: str,
    root_total: float,
    root_depth: Literal[0, 1],
) -> list[str]:
    """Construct a root or sub-root frame.

    :param nodes: graph nodes obtained from ``process_stacks``.
    :param geometry: rendering geometry for the SVG layout.
    :param settings: rendering and processing options.
    :param colors: coloring options for the SVG.
    :param root_name: the name of the (sub-)root frame.
    :param root_total: the width of the (sub-)root frame given as count.
    :param root_depth: determines the root frame type (0 = root, 1 = subroot).

    :return: a collection of SVG elements forming a (sub-)root frame.
    """
    frames: list[str] = []
    x1 = Geometry.XPad1
    x2 = Geometry.XPad1 + root_total * geometry.width_per_count_unit
    y1 = geometry.y1_table[root_depth]
    y2 = geometry.y2_table[root_depth]

    samples = int(root_total * settings.factor)
    samples_txt = _format_with_suffix(samples)
    pct = (100 * samples) / geometry.total_factor
    root_name = f"[[ {root_name} ]]"
    info = f"{root_name}&#010;Incl.: {samples_txt} {settings.count_name}, {pct:.2f}%&#010;Excl.: 0 {settings.count_name}, 0.00%"

    if nodes.is_diff:
        color_val = colors.color_scale(0.0, nodes.max_delta_excl)
    else:
        color_val = colors[""]

    chars = int((x2 - x1) / geometry.char_space)
    text = ""  # Show no text in too narrow frames.
    if chars >= 3:  # Enough room for one visible character plus an ellipsis.
        text = root_name[:chars]
        if chars < len(root_name):
            # Truncate with a two-character ellipsis when the label is too long.
            text = text[:-2] + ".."

    frame_rectangle = (
        f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{x2 - x1:.1f}"'
        f' height="{y2 - y1:.1f}" fill="{color_val}" rx="2" ry="2" />\n'
    )
    frame_text = f'<text x="{x1 + 3:.2f}" y="{3 + (y1 + y2) / 2:.2f}">{text}</text>\n'
    frame_begin, frame_end = settings.name_attr.get_frame("", info)
    frames.append(f"{frame_begin.format('')}{frame_rectangle}{frame_text}{frame_end}")
    return frames


def _construct_node_frames(
    nodes: ProcessedNodes,
    frames: list[str],
    geometry: Geometry,
    settings: Settings,
    colors: Colors,
) -> None:
    """Construct frames without name attributes from non-differential nodes.

    The nodes are appended to the ``frames`` input list, which may already
    contain some frames (e.g., the root frame).

    :param nodes: graph nodes obtained from ``process_stacks``.
    :param frames[in,out]: a (non-empty) list of frames to append new frames to.
    :param geometry: rendering geometry for the SVG layout.
    :param settings: rendering and processing options.
    :param colors: coloring options for the SVG.
    """
    suffixes: list[str] = ["", "K", "M", "G", "T", "P", "E"]
    suffix_regex: re.Pattern[str] = re.compile(r"_\[[kwij]]$")

    # Optimize dot access.
    str_translate = str.translate
    list_append = list.append
    re_sub = re.sub
    x_pad_1: int = Geometry.XPad1
    width_per_count_unit: float = geometry.width_per_count_unit
    y1_table: list[int] = geometry.y1_table
    y2_table: list[int] = geometry.y2_table
    total_factor: float = geometry.total_factor
    char_space: float = geometry.char_space
    factor: float = settings.factor
    count_name: str = settings.count_name
    translation_table: dict[int, str] = Settings.TranslationTable

    # Determine the number of root frames.
    root_frames = 2 if settings.total else 1
    for func, depth, etime, stime, exc_time in nodes.nodes:
        x1 = x_pad_1 + stime * width_per_count_unit
        x2 = x_pad_1 + etime * width_per_count_unit
        y1 = y1_table[depth + root_frames]
        y2 = y2_table[depth + root_frames]

        samples = int((etime - stime) * factor)
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        samples_copy: float = samples
        while samples_copy >= 1000.0 and step < len(suffixes) - 1:
            samples_copy /= 1000.0
            step += 1
        samples_txt = f"{samples_copy:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        exc_time_fmt: float = exc_time
        while exc_time_fmt >= 1000.0 and step < len(suffixes) - 1:
            exc_time_fmt /= 1000.0
            step += 1
        exc_samples_txt = f"{exc_time_fmt:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.

        pct = (100 * samples) / total_factor
        exc_pct = (100 * exc_time) / total_factor
        # Strip stack annotations and SVG-breaking characters.
        escaped_func = re_sub(suffix_regex, "", str_translate(func, translation_table))
        info = f"{escaped_func}&#010;Incl.: {samples_txt} {count_name}, {pct:.2f}%&#010;Excl.: {exc_samples_txt} {count_name}, {exc_pct:.2f}%"
        color_val = colors[func]

        chars = int((x2 - x1) / char_space)
        text = ""
        if chars >= 3:
            text = escaped_func[:chars]
            if chars < len(escaped_func):
                text = text[:-2] + ".."

        frame_rectangle = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{round(x2, 1) - round(x1, 1):.1f}"'
            f' height="{y2 - y1:.1f}" fill="{color_val}" rx="2" ry="2" />\n'
        )
        frame_text = f'<text x="{x1 + 3:.2f}"' f' y="{3 + (y1 + y2) / 2:.2f}">{text}</text>\n'
        exc_width_ratio = (exc_time * factor) / samples * 100
        list_append(
            frames,
            f"<g data-e={exc_width_ratio}>\n<title>{info}</title>\n{frame_rectangle}{frame_text}</g>\n",
        )


def _construct_node_frames_with_attrs(
    nodes: ProcessedNodes,
    frames: list[str],
    geometry: Geometry,
    settings: Settings,
    colors: Colors,
) -> None:
    """Construct frames with custom name attributes from non-differential nodes.

    The nodes are appended to the ``frames`` input list, which may already
    contain some frames (e.g., the root frame).

    :param nodes: graph nodes obtained from ``process_stacks``.
    :param frames[in,out]: a (non-empty) list of frames to append new frames to.
    :param geometry: rendering geometry for the SVG layout.
    :param settings: rendering and processing options.
    :param colors: coloring options for the SVG.
    """
    suffixes: list[str] = ["", "K", "M", "G", "T", "P", "E"]
    suffix_regex: re.Pattern[str] = re.compile(r"_\[[kwij]]$")

    # Optimize dot access.
    str_translate = str.translate
    list_append = list.append
    re_sub = re.sub
    x_pad_1: int = Geometry.XPad1
    width_per_count_unit: float = geometry.width_per_count_unit
    y1_table: list[int] = geometry.y1_table
    y2_table: list[int] = geometry.y2_table
    total_factor: float = geometry.total_factor
    char_space: float = geometry.char_space
    factor: float = settings.factor
    count_name: str = settings.count_name
    name_attr_cache = settings.name_attr.attr_cache
    translation_table: dict[int, str] = Settings.TranslationTable

    root_frames = 2 if settings.total else 1
    for func, depth, etime, stime, exc_time in nodes.nodes:
        x1 = x_pad_1 + stime * width_per_count_unit
        x2 = x_pad_1 + etime * width_per_count_unit
        y1 = y1_table[depth + root_frames]
        y2 = y2_table[depth + root_frames]

        samples = int((etime - stime) * factor)
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        samples_copy: float = samples
        while samples_copy >= 1000.0 and step < len(suffixes) - 1:
            samples_copy /= 1000.0
            step += 1
        samples_txt = f"{samples_copy:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        exc_time_fmt: float = exc_time
        while exc_time_fmt >= 1000.0 and step < len(suffixes) - 1:
            exc_time_fmt /= 1000.0
            step += 1
        exc_samples_txt = f"{exc_time_fmt:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.

        pct = (100 * samples) / total_factor
        exc_pct = (100 * exc_time) / total_factor
        # Strip stack annotations and SVG-breaking characters.
        escaped_func = re_sub(suffix_regex, "", str_translate(func, translation_table))
        info = f"{escaped_func}&#010;Incl.: {samples_txt} {count_name}, {pct:.2f}%&#010;Excl.: {exc_samples_txt} {count_name}, {exc_pct:.2f}%"
        color_val = colors[func]

        chars = int((x2 - x1) / char_space)
        text = ""
        if chars >= 3:
            text = escaped_func[:chars]
            if chars < len(escaped_func):
                text = text[:-2] + ".."

        frame_rectangle = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{round(x2, 1) - round(x1, 1):.1f}"'
            f' height="{y2 - y1:.1f}" fill="{color_val}" rx="2" ry="2" />\n'
        )
        frame_text = f'<text x="{x1 + 3:.2f}"' f' y="{3 + (y1 + y2) / 2:.2f}">{text}</text>\n'
        # -- BEGIN: inlined 'settings.name_attr.get_frame'.
        try:
            frame_begin, frame_end = name_attr_cache[func]
        except KeyError:
            frame_begin, frame_end = ("<g {}>\n<title>", "</g>\n")
        # -- END: inlined 'settings.name_attr.get_frame'.
        exc_width_ratio = (exc_time * factor) / samples * 100
        list_append(
            frames,
            f"{frame_begin.format(f'data-e={exc_width_ratio}')}{info}</title>\n{frame_rectangle}"
            f"{frame_text}{frame_end}",
        )


def _construct_node_diff_frames(
    nodes: ProcessedDiffNodes,
    frames: list[str],
    geometry: Geometry,
    settings: Settings,
    colors: Colors,
) -> None:
    """Construct frames without name attributes from differential nodes.

    The nodes are appended to the ``frames`` input list, which may already
    contain some frames (e.g., the root frame).

    :param nodes: graph nodes obtained from ``process_stacks``.
    :param frames[in,out]: a (non-empty) list of frames to append new frames to.
    :param geometry: rendering geometry for the SVG layout.
    :param settings: rendering and processing options.
    :param colors: coloring options for the SVG.
    """
    suffixes: list[str] = ["", "K", "M", "G", "T", "P", "E"]
    suffix_regex: re.Pattern[str] = re.compile(r"_\[[kwij]]$")

    # Optimize dot access.
    str_translate = str.translate
    list_append = list.append
    re_sub = re.sub
    color_scale = colors.color_scale
    x_pad_1: int = Geometry.XPad1
    width_per_count_unit: float = geometry.width_per_count_unit
    y1_table: list[int] = geometry.y1_table
    y2_table: list[int] = geometry.y2_table
    total_factor: float = geometry.total_factor
    char_space: float = geometry.char_space
    factor: float = settings.factor
    count_name: str = settings.count_name
    translation_table: dict[int, str] = Settings.TranslationTable
    max_delta_incl: float = nodes.max_delta_incl
    max_delta_excl: float = nodes.max_delta_excl

    negate_coeff: int = -1 if settings.negate else 1
    root_frames = 2 if settings.total else 1
    for func, depth, etime, stime, exc_time, delta_incl, delta_excl in nodes.nodes:
        x1 = x_pad_1 + stime * width_per_count_unit
        x2 = x_pad_1 + etime * width_per_count_unit
        y1 = y1_table[depth + root_frames]
        y2 = y2_table[depth + root_frames]

        samples = int((etime - stime) * factor)
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        samples_copy: float = samples
        while samples_copy >= 1000.0 and step < len(suffixes) - 1:
            samples_copy /= 1000.0
            step += 1
        samples_txt = f"{samples_copy:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        exc_time_fmt: float = exc_time
        while exc_time_fmt >= 1000.0 and step < len(suffixes) - 1:
            exc_time_fmt /= 1000.0
            step += 1
        exc_samples_txt = f"{exc_time_fmt:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.

        pct = (100 * samples) / total_factor
        exc_pct = (100 * exc_time) / total_factor
        # Strip stack annotations and SVG-breaking characters.
        escaped_func = re_sub(suffix_regex, "", str_translate(func, translation_table))
        d_incl = delta_incl * negate_coeff
        d_excl = delta_excl * negate_coeff
        info = f"{escaped_func}&#010;Incl.: {samples_txt} {count_name}, {pct:.2f}%; {(100 * d_incl) / total_factor:+.2f}%&#010;Excl.: {exc_samples_txt} {count_name}, {exc_pct:.2f}%; {(100 * d_excl) / total_factor:+.2f}%"

        chars = int((x2 - x1) / char_space)
        text = ""
        if chars >= 3:
            text = escaped_func[:chars]
            if chars < len(escaped_func):
                text = text[:-2] + ".."

        frame_rectangle = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{round(x2, 1) - round(x1, 1):.1f}"'
            f' height="{y2 - y1:.1f}" fill="{color_scale(d_incl, max_delta_incl)}" rx="2"'
            ' ry="2" />\n'
        )
        frame_text = f'<text x="{x1 + 3:.2f}"' f' y="{3 + (y1 + y2) / 2:.2f}">{text}</text>\n'
        exc_width_ratio = (exc_time * factor) / samples * 100
        list_append(
            frames,
            f"<g data-e={exc_width_ratio} data-ed={color_scale(d_excl, max_delta_excl)}>\n<title>{info}</title>\n{frame_rectangle}{frame_text}</g>\n",
        )


def _construct_node_diff_frames_with_attrs(
    nodes: ProcessedDiffNodes,
    frames: list[str],
    geometry: Geometry,
    settings: Settings,
    colors: Colors,
) -> None:
    """Construct frames with custom name attributes from differential nodes.

    The nodes are appended to the ``frames`` input list, which may already
    contain some frames (e.g., the root frame).

    :param nodes: graph nodes obtained from ``process_stacks``.
    :param frames[in,out]: a (non-empty) list of frames to append new frames to.
    :param geometry: rendering geometry for the SVG layout.
    :param settings: rendering and processing options.
    :param colors: coloring options for the SVG.
    """
    suffixes: list[str] = ["", "K", "M", "G", "T", "P", "E"]
    suffix_regex: re.Pattern[str] = re.compile(r"_\[[kwij]]$")

    # Optimize dot access.
    str_translate = str.translate
    list_append = list.append
    re_sub = re.sub
    color_scale = colors.color_scale
    x_pad_1: int = Geometry.XPad1
    width_per_count_unit: float = geometry.width_per_count_unit
    y1_table: list[int] = geometry.y1_table
    y2_table: list[int] = geometry.y2_table
    total_factor: float = geometry.total_factor
    char_space: float = geometry.char_space
    factor: float = settings.factor
    count_name: str = settings.count_name
    translation_table: dict[int, str] = Settings.TranslationTable
    name_attr_cache = settings.name_attr.attr_cache
    max_delta_incl: float = nodes.max_delta_incl
    max_delta_excl: float = nodes.max_delta_excl

    negate_coeff: int = -1 if settings.negate else 1
    root_frames = 2 if settings.total else 1
    for func, depth, etime, stime, exc_time, delta_incl, delta_excl in nodes.nodes:
        x1 = x_pad_1 + stime * width_per_count_unit
        x2 = x_pad_1 + etime * width_per_count_unit
        y1 = y1_table[depth + root_frames]
        y2 = y2_table[depth + root_frames]

        samples = int((etime - stime) * factor)
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        samples_copy: float = samples
        while samples_copy >= 1000.0 and step < len(suffixes) - 1:
            samples_copy /= 1000.0
            step += 1
        samples_txt = f"{samples_copy:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.
        # -- BEGIN: inlined '_format_with_suffix'.
        step = 0
        exc_time_fmt: float = exc_time
        while exc_time_fmt >= 1000.0 and step < len(suffixes) - 1:
            exc_time_fmt /= 1000.0
            step += 1
        exc_samples_txt = f"{exc_time_fmt:.3f}".rstrip("0").rstrip(".") + suffixes[step]
        # -- END: inlined '_format_with_suffix'.

        pct = (100 * samples) / total_factor
        exc_pct = (100 * exc_time) / total_factor
        # Strip stack annotations and SVG-breaking characters.
        escaped_func = re_sub(suffix_regex, "", str_translate(func, translation_table))
        d_incl = delta_incl * negate_coeff
        d_excl = delta_excl * negate_coeff
        info = f"{escaped_func}&#010;Incl.: {samples_txt} {count_name}, {pct:.2f}%; {(100 * d_incl) / total_factor:+.2f}%&#010;Excl.: {exc_samples_txt} {count_name}, {exc_pct:.2f}%; {(100 * d_excl) / total_factor:+.2f}%"

        chars = int((x2 - x1) / char_space)
        text = ""
        if chars >= 3:
            text = escaped_func[:chars]
            if chars < len(escaped_func):
                text = text[:-2] + ".."

        frame_rectangle = (
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{round(x2, 1) - round(x1, 1):.1f}"'
            f' height="{y2 - y1:.1f}" fill="{color_scale(d_incl, max_delta_incl)}" rx="2"'
            ' ry="2" />\n'
        )
        frame_text = f'<text x="{x1 + 3:.2f}"' f' y="{3 + (y1 + y2) / 2:.2f}">{text}</text>\n'
        # -- BEGIN: inlined 'settings.name_attr.get_frame'.
        try:
            frame_begin, frame_end = name_attr_cache[func]
        except KeyError:
            frame_begin, frame_end = ("<g {}>\n<title>", "</g>\n")
        # -- END: inlined 'settings.name_attr.get_frame'.
        exc_width_ratio = (exc_time * factor) / samples * 100
        list_append(
            frames,
            f"{frame_begin.format(f'data-e={exc_width_ratio} data-ed={color_scale(d_excl, max_delta_excl)}')}{info}</title>\n{frame_rectangle}"
            f"{frame_text}{frame_end}",
        )


def _format_with_suffix(num: float) -> str:
    """Format a number with SI suffixes (``K``, ``M``, ...).

    :param num: a number to format.

    :return: a number with an optional SI suffix.
    """
    suffixes = ["", "K", "M", "G", "T", "P", "E"]
    i = 0
    while num >= 1000.0 and i < len(suffixes) - 1:
        num /= 1000.0
        i += 1
    # Format to at most three decimal places, trimming trailing zeros.
    formatted = f"{num:.3f}".rstrip("0").rstrip(".")
    return formatted + suffixes[i]


### SECTION: TOP-LEVEL FUNCTIONS
# CLI and programmatic (``create_flame_graph``) entrypoints + helper functions.


@overload
def create_flame_graph(
    profile: Path | FoldedData | FoldedDiffData,
    *,
    bgcolors: str = ...,
    colors: ColorPalettes = ...,
    countname: str = ...,
    cp: bool = ...,
    encoding: str = ...,
    factor: float = ...,
    flamechart: bool = ...,
    fontsize: float = ...,
    fonttype: str = ...,
    fontwidth: float = ...,
    hash: bool = ...,
    height: int = ...,
    inverted: bool = ...,
    maxtrace: int = ...,
    minwidth: str = ...,
    nametype: str = ...,
    nameattr: str = ...,
    negate: bool = ...,
    notes: str = ...,
    outfile: None = ...,
    random: bool = ...,
    reverse: bool = ...,
    rootnode: str = ...,
    subrootnode: str = ...,
    subtitle: str = ...,
    total: int = ...,
    title: str = ...,
    width: int = ...,
    **_: Any,
) -> str: ...


@overload
def create_flame_graph(
    profile: Path | FoldedData | FoldedDiffData,
    *,
    bgcolors: str = ...,
    colors: ColorPalettes = ...,
    countname: str = ...,
    cp: bool = ...,
    encoding: str = ...,
    factor: float = ...,
    flamechart: bool = ...,
    fontsize: float = ...,
    fonttype: str = ...,
    fontwidth: float = ...,
    hash: bool = ...,
    height: int = ...,
    inverted: bool = ...,
    maxtrace: int = ...,
    minwidth: str = ...,
    nametype: str = ...,
    nameattr: str = ...,
    negate: bool = ...,
    notes: str = ...,
    outfile: str = ...,
    random: bool = ...,
    reverse: bool = ...,
    rootnode: str = ...,
    subrootnode: str = ...,
    subtitle: str = ...,
    total: int = ...,
    title: str = ...,
    width: int = ...,
    **_: Any,
) -> str: ...


def create_flame_graph(
    profile: Path | FoldedData | FoldedDiffData,
    *,
    bgcolors: str = Settings.DefaultBgColors,
    colors: ColorPalettes = Settings.DefaultColors,
    countname: str = Settings.DefaultCountName,
    cp: bool = Settings.DefaultPaletteFlag,
    encoding: str = Settings.DefaultEncoding,
    factor: float = Settings.DefaultFactor,
    flamechart: bool = Settings.DefaultFlameChartFlag,
    fontsize: float = Settings.DefaultFontSize,
    fonttype: str = Settings.DefaultFontType,
    fontwidth: float = Settings.DefaultFontWidth,
    hash: bool = Settings.DefaultHashFlag,
    height: int = Settings.DefaultFrameHeight,
    inverted: bool = Settings.DefaultInvertedFlag,
    maxtrace: int = Settings.DefaultMaxTrace,
    minwidth: str = Settings.DefaultMinWidth,
    nametype: str = Settings.DefaultNameType,
    nameattr: str = Settings.DefaultNameAttrFile,
    negate: bool = Settings.DefaultNegateFlag,
    notes: str = Settings.DefaultNotesText,
    outfile: str | None = None,
    random: bool = Settings.DefaultRandomFlag,
    reverse: bool = Settings.DefaultStackReverseFlag,
    rootnode: str = Settings.DefaultRootNode,
    subrootnode: str = Settings.DefaultSubRootNode,
    subtitle: str = Settings.DefaultSubtitle,
    total: int = Settings.DefaultTotal,
    title: str = Settings.DefaultTitle,
    width: int = Settings.DefaultImageWidth,
    **_: Any,
) -> str | None:
    """Renders an SVG from the provided profile.

    The input profile can either be an (already parsed) in-memory profile, or
    a path to a file containing a folded profile that will be parsed.

    Based on the ``outfile`` parameter, the created SVG can be written to
    a file or returned directly:
     - if ``outfile`` is ``None``, then the SVG is returned as a string;
     - if ``outfile`` is either an empty string or ``stdout``, then the SVG
       is written to the standard output; otherwise
     - the SVG is written to the ``outfile``.

    :param profile: a path to the input profile, or already parsed folded data.
    :param bgcolors: the background color (gradient). Supports:
           - named gradients (``yellow``, ``blue``, ``green``, ``grey``,
             and ``gray``),
           - hex colors in the ``#RRGGBB`` format (will result in a flat
             color, not a gradient), or
           - ``""`` for a palette-derived default gradient.
    :param colors: the color palette for SVG frames.
    :param countname: the counts name (e.g. ``samples``, ``cycles``).
    :param encoding: a specific encoding to use in the XML declaration.
    :param factor: a multiplier applied to parsed counts.
    :param flamechart: draw a flame chart instead (sorts by time, does not
           merge stacks).
    :param fontsize: SVG text font size (px).
    :param fonttype: CSS ``font-family`` name for SVG text.
    :param fontwidth: average character width relative to ``font_size``.
    :param height: the height of each frame (px).
    :param hash: color frames using a deterministic hash function.
    :param inverted: draw an icicle chart instead (deepest frames at top).
    :param maxtrace: overrides the computation of the canvas height.
           The height is determined by the maximum trace depth (after
           filtering the data using ``minwidth``). This option may be used
           to align two SVGs with possibly different data side-by-side.
    :param minwidth: specifies the minimum width of displayed frames.
           Narrower frames will be discarded. May be specified either as
           a fixed pixel width, e.g., ``0.5``, or relative to the actual
           total (not the user-supplied ``--total``) count, e.g., ``0.1%``.
    :param nameattr: a path to the name-attribute file
           (see ``NameAttributes``).
    :param nametype: the name of the frames in stacks
          (e.g., ``Function:``, ``Basic Block:``).
    :param negate: flip the differential red/blue hues when ``True``.
    :param notes: addition notes to embedd into the SVG comment header.
    :param outfile: store the flamegraph in a file or write it to the standard
           output instead of returning it as a string.
    :param cp: use consistent palette that loads and stores stable colors
           via a ``palette.map`` file.
    :param random: use randomized frame colors within the selected palette.
           Note that even frames with identical names will have their
           colors chosen randomly.
    :param reverse: the stacks in the folded profile are in the
           callee-to-caller (instead of caller-to-callee) order.
    :param rootnode: the label on the synthetic root frame.
    :param subrootnode: the label on the synthetic sub-root frame used when
           '--total' is supplied. The sub-root allows to scale (zoom) the
           rendered frames when the root node is much wider than the data.
    :param subtitle: optional second title line below the main title.
    :param total: overrides the sum of all counts, which causes the root
           node to be wider (suitable for comparing two profiles
           side-by-side). Must be higher or equal than the actual sum.
    :param title: the graph title.
    :param width: the width of the SVG canvas (px).

    :return: the SVG content unless an output file was specified.

    Extra keyword arguments are ignored so that dictionaries with possibly
    additional keys may be unpacked directly when calling the function.
    """
    settings: Settings = Settings(
        Path(),
        bgcolors=bgcolors,
        colors=colors,
        countname=countname,
        cp=cp,
        encoding=encoding,
        factor=factor,
        flamechart=flamechart,
        fontsize=fontsize,
        fonttype=fonttype,
        fontwidth=fontwidth,
        hash=hash,
        height=height,
        inverted=inverted,
        maxtrace=maxtrace,
        minwidth=minwidth,
        nametype=nametype,
        nameattr=nameattr,
        negate=negate,
        notes=notes,
        random=random,
        reverse=reverse,
        rootnode=rootnode,
        subrootnode=subrootnode,
        subtitle=subtitle,
        total=total,
        title=title,
        width=width,
    )
    svg_header, svg_frames = _build_flame_graph(profile, settings)
    # We write the SVG to a file (including stdout) if specified.
    # Otherwise, we join the SVG fragments into a single string and return it.
    if outfile is not None:
        write_flame_graph(outfile, svg_header, svg_frames)
        return None
    return "".join(svg_header + svg_frames)


def initialize_cli_options(cli_parser: argparse.ArgumentParser) -> None:
    """Initializes the CLI options that may be reused by composite scripts.

    When importing the flamegraph.py script by other Python scripts, it might
    be helpful to extend their CLI options with the options and arguments used
    by this script.

    Note that the ``infile`` positional parameter is skipped.

    :param cli_parser: a CLI parser to extend.
    """
    cli_parser.add_argument(
        "--bgcolors",
        type=str,
        default=Settings.DefaultBgColors,
        help=(
            "Set color for the background. Pre-defined gradient choices are"
            " yellow, blue, green, grey, and gray. Flat colors may be specified"
            "as '#rrggbb' (default: selected automatically w.r.t. --colors)."
        ),
    )
    cli_parser.add_argument(
        "--colors",
        type=ColorPalettes,
        default=Settings.DefaultColors.value,
        choices=ColorPalettes.supported(),
        help="Set color palette for frames (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--countname",
        type=str,
        default=Settings.DefaultCountName,
        help="The count type label (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--cp",
        action="store_true",
        help=(
            "Frame colors use consistent palette from the"
            f" {Colors.PaletteFileName} file (default: False)."
        ),
    )
    cli_parser.add_argument(
        "--encoding",
        type=str,
        default=Settings.DefaultEncoding,
        help="The xml encoding (default: omitted).",
    )
    cli_parser.add_argument(
        "--factor",
        type=float,
        default=Settings.DefaultFactor,
        help="A factor to scale the counts by (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--flamechart",
        action="store_true",
        help=(
            "Generate flame chart which sorts by time and does not merge"
            " stacks (default: False)."
        ),
    )
    cli_parser.add_argument(
        "--fontsize",
        type=float,
        default=Settings.DefaultFontSize,
        help="The font size (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--fonttype",
        type=str,
        default=Settings.DefaultFontType,
        help="The font type (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--fontwidth",
        type=float,
        default=Settings.DefaultFontWidth,
        help=("The average font width relative to font size" " (default: %(default)s)."),
    )
    cli_parser.add_argument(
        "--hash",
        action="store_true",
        help=("Frame colors are generated using function name hash" " (default: False)."),
    )
    cli_parser.add_argument(
        "--height",
        type=int,
        default=Settings.DefaultFrameHeight,
        help="The height of each frame (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--inverted",
        action="store_true",
        help="Generate icicle graph (default: False).",
    )
    cli_parser.add_argument(
        "--maxtrace",
        type=int,
        default=Settings.DefaultMaxTrace,
        help=(
            "The maximal seen height of a trace used to compute the offsets"
            " and image height; this may be used to align two flamegraphs"
            " (default: computed automatically)."
        ),
    )
    cli_parser.add_argument(
        "--minwidth",
        type=str,
        default=Settings.DefaultMinWidth,
        help=(
            "Omit cheap functions. Width in (fractions of) pixels or"
            " percentage of time, e.g., '0.5%%'"
            " (default: %(default)s pixels)."
        ),
    )
    cli_parser.add_argument(
        "--nameattr",
        type=str,
        default=Settings.DefaultNameAttrFile,
        help=(
            "A path to file holding function attributes, e.g., id, class, or"
            " href (default: ignored)."
        ),
    )
    cli_parser.add_argument(
        "--nametype",
        type=str,
        default=Settings.DefaultNameType,
        help="The name type label (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--negate",
        action="store_true",
        help=("Switch differential hues when generating diff flamegraphs" " (default: False)."),
    )
    cli_parser.add_argument(
        "--notes",
        type=str,
        default=Settings.DefaultNotesText,
        help="Add debugging notes to the SVG (default: omitted).",
    )
    cli_parser.add_argument(
        "--outfile",
        type=str,
        default=Settings.DefaultOutFile,
        help=(
            "Specify the SVG output file. If unspecified, the SVG is printed"
            " to the standard output (default: %(default)s)."
        ),
    )
    cli_parser.add_argument(
        "--random",
        action="store_true",
        help="Frame colors are generated randomly (default: False).",
    )
    cli_parser.add_argument(
        "--reverse",
        action="store_true",
        help=(
            "Indicates whether stack traces in the input file are reversed;"
            " note that this introduces a performance penalty"
            " (default: False)."
        ),
    )
    cli_parser.add_argument(
        "--rootnode",
        type=str,
        default=Settings.DefaultRootNode,
        help="Set the name of the root node (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--subrootnode",
        type=str,
        default=Settings.DefaultSubRootNode,
        help="Set the name of the sub root node to use when '--total' is specified (default: %(default)s).",
    )
    cli_parser.add_argument(
        "--subtitle",
        type=str,
        default=Settings.DefaultSubtitle,
        help="A subtitle of the image (default: omitted).",
    )
    cli_parser.add_argument(
        "--title",
        type=str,
        default=Settings.DefaultTitle,
        help="The title of the image (default: generated automatically).",
    )
    cli_parser.add_argument(
        "--total",
        type=int,
        default=Settings.DefaultTotal,
        help=(
            "Override the sum of the total counts; the value must be larger"
            " or equal than the actual sum (default: ignored)."
        ),
    )
    cli_parser.add_argument(
        "--width",
        type=int,
        default=Settings.DefaultImageWidth,
        help="The width of the image (default: %(default)s).",
    )


def _build_flame_graph(
    profile: Path | FoldedData | FoldedDiffData, settings: Settings
) -> tuple[list[str], list[str]]:
    """Build the flame graph SVG.

    A convenience wrapper over (optional) profile parsing, validation, stack
    processing and SVG rendering.

    :param profile: a path to the input profile, or already parsed folded data.
    :param settings: rendering and processing options.

    :return: a tuple of SVG header and SVG frames.
    """
    # If a path was given, we need to parse the profile first. Otherwise, we
    # were given an already parsed profile.
    if isinstance(profile, Path):
        parsed_profile = parse_folded_profile(
            profile, settings.flame_chart_flag, settings.stack_reverse_flag
        )
    else:
        parsed_profile = profile
    settings.total = validate_profile_total(parsed_profile, settings)
    colors: Colors = Colors(
        settings.colors,
        settings.bg_colors,
        settings.consistent_palette_flag,
        settings.hash_flag,
        settings.random_flag,
    )
    nodes, geometry = process_stacks(parsed_profile, settings)

    # Construct the SVG.
    svg_setup = create_svg_without_frames(settings, geometry, colors, nodes.is_diff)
    svg_frames: list[str] = construct_frames(nodes, geometry, settings, colors)
    svg_frames.append("</svg>\n")
    colors.store_palette()
    return svg_setup, svg_frames


def write_flame_graph(outfile: str, *svg_fragments: Iterable[str]) -> None:
    """Write the SVG content to a file or standard output.

    :param outfile: ``""``, ``stdout``, or a path to the output file.
    :param svg_fragments: SVG contents (stored as possibly multiple collections
           of strings).
    """
    # This could be made more elegant using nullcontext from contextlib,
    # however, it would result in an unnecessary import.
    if outfile in ("", "stdout"):
        # Write the flamegraph to the stdout.
        for fragment in svg_fragments:
            sys.stdout.writelines(fragment)
    else:
        # Write the flamegraph to an output file.
        with open(outfile, "w+") as out_handle:
            for fragment in svg_fragments:
                out_handle.writelines(fragment)


if __name__ == "__main__":
    # Creates a flamegraph SVG using CLI.
    # Based on the ``outfile`` option, the flame graph will be written to
    # either the standard output or the specified output file.
    _cli_parser = argparse.ArgumentParser(
        description="Generate flame graph SVG.",
        usage="%(prog)s [options] infile > outfile.svg",
    )
    _cli_parser.add_argument(
        "infile",
        type=Path,
        nargs="?",
        default=None,
        metavar="infile",
        help="The input folded stack file.",
    )
    initialize_cli_options(_cli_parser)

    _args = _cli_parser.parse_args()
    _settings: Settings = Settings(**vars(_args))
    _profile = parse_folded_profile(
        _settings.infile,
        _settings.flame_chart_flag,
        _settings.stack_reverse_flag,
    )
    write_flame_graph(_settings.outfile, *_build_flame_graph(_profile, _settings))
