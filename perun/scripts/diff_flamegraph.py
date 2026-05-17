#!/usr/bin/env python3

"""A helper script for creating differential flamegraphs directly.

The script connects the interfaces of the difffolded.py and flamegraph.py
scripts such that there is no need to transfer the data through OS pipes.
The script also leverages the difffolded lazy parsing when possible.
"""

from __future__ import annotations

import argparse
from typing import overload, Any

import perun.scripts.difffolded as diff
import perun.scripts.flamegraph as fg


@overload
def create_diff_flame_graph(
    baseline: str,
    target: str,
    *,
    bgcolors: str = ...,
    colors: fg.ColorPalettes = ...,
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
    rootnode: str = ...,
    reverse: bool = ...,
    subtitle: str = ...,
    total: int = ...,
    title: str = ...,
    width: int = ...,
    **_: Any,
) -> str: ...


@overload
def create_diff_flame_graph(
    baseline: str,
    target: str,
    *,
    bgcolors: str = ...,
    colors: fg.ColorPalettes = ...,
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
    rootnode: str = ...,
    reverse: bool = ...,
    subtitle: str = ...,
    total: int = ...,
    title: str = ...,
    width: int = ...,
    **_: Any,
) -> str: ...


def create_diff_flame_graph(
    baseline: str,
    target: str,
    *,
    bgcolors: str = fg.Settings.DefaultBgColors,
    colors: fg.ColorPalettes = fg.Settings.DefaultColors,
    countname: str = fg.Settings.DefaultCountName,
    cp: bool = fg.Settings.DefaultPaletteFlag,
    encoding: str = fg.Settings.DefaultEncoding,
    factor: float = fg.Settings.DefaultFactor,
    flamechart: bool = fg.Settings.DefaultFlameChartFlag,
    fontsize: float = fg.Settings.DefaultFontSize,
    fonttype: str = fg.Settings.DefaultFontType,
    fontwidth: float = fg.Settings.DefaultFontWidth,
    hash: bool = fg.Settings.DefaultHashFlag,
    height: int = fg.Settings.DefaultFrameHeight,
    inverted: bool = fg.Settings.DefaultInvertedFlag,
    maxtrace: int = fg.Settings.DefaultMaxTrace,
    minwidth: str = fg.Settings.DefaultMinWidth,
    nametype: str = fg.Settings.DefaultNameType,
    nameattr: str = fg.Settings.DefaultNameAttrFile,
    negate: bool = fg.Settings.DefaultNegateFlag,
    normalize: bool = False,
    notes: str = fg.Settings.DefaultNotesText,
    outfile: str | None = None,
    random: bool = fg.Settings.DefaultRandomFlag,
    rootnode: str = fg.Settings.DefaultRootNode,
    reverse: bool = fg.Settings.DefaultStackReverseFlag,
    striphex: bool = False,
    subtitle: str = fg.Settings.DefaultSubtitle,
    total: int = fg.Settings.DefaultTotal,
    title: str = fg.Settings.DefaultTitle,
    width: int = fg.Settings.DefaultImageWidth,
    **_: Any,
) -> str | None:
    """Renders a differential flame graph from the baseline and target profiles.

    This function can also be used as a programmatic API.

    :param baseline: a path to the baseline folded profile.
    :param target: a path to the target folded profile.
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
           a fixed pixel width (e.g., ``0.5``) or relative to the total
           count (e.g., ``0.1%``).
    :param nameattr: a path to the name-attribute file
           (see ``NameAttributes``).
    :param nametype: the name of the frames in stacks
          (e.g., ``Function:``, ``Basic Block:``).
    :param negate: flip the differential red/blue hues when ``True``.
    :param normalize: normalize the baseline sample counts using the formula
           (baseline_count * target_sum / baseline_sum).
    :param notes: addition notes to embedd into the SVG comment header.
    :param outfile: store the flamegraph in a file or write it to the standard
           output instead of returning it as a string.
    :param cp: use consistent palette that loads and stores stable colors
           via a ``palette.map`` file.
    :param random: use randomized frame colors within the selected palette.
           Note that even frames with identical names will have their
           colors chosen randomly.
    :param rootnode: the label on the synthetic root frame.
    :param reverse: the stacks in the folded profile are in the
           callee-to-caller (instead of caller-to-callee) order.
    :param striphex: strip hex addresses in the stacks, e.g., replace
           '0x1234abc' with '0x...'.
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
    diff_result: diff.FoldedDiff | diff.FoldedDiffLazy
    if not normalize and flamechart:
        # When normalization is disabled and we are creating a flame chart, we
        # must use the eager API to obtain the correct ``target_sum`` value.
        diff_result = diff.diff_folded(
            baseline,
            target,
            striphex=striphex,
            normalize=normalize,
            sort_stacks=not flamechart,
        )
        # We need to translate the dictionary to an iterable of tuples.
    else:
        # Otherwise, we can use the (potentially) more efficient lazy API.
        diff_result = diff.diff_folded_lazy(
            baseline,
            target,
            striphex=striphex,
            normalize=normalize,
            sort_stacks=not flamechart,
        )
    profile = fg.FoldedDiffData(diff_result.data, diff_result.target_sum)
    return fg.create_flame_graph(
        profile,
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
        outfile=outfile,
        random=random,
        rootnode=rootnode,
        reverse=reverse,
        subtitle=subtitle,
        total=total,
        title=title,
        width=width,
    )


if __name__ == "__main__":
    # CLI entrypoint.
    _cli_parser = argparse.ArgumentParser(
        description="Generate a differential flame graph SVG.",
        usage="%(prog)s [options] baseline target > diff_flame_graph.svg",
    )

    diff.initialize_cli_options(_cli_parser)
    fg.initialize_cli_options(_cli_parser)
    _args = _cli_parser.parse_args()
    create_diff_flame_graph(**vars(_args))
