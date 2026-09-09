"""Perun is lightweight performance control system, a wrapper over existing version control systems

Perun is lightweight performance control system, which serves as a wrapper over existing version
control systems (mainly git). Perun serves as an additional layer and tracks performance profiles
corresponding to minor versions (e.g. commits) of the projects in order to preserve the history
and capture possible performance issues and have a bigger picture of the tool performance over
the greater span of the time.

Perun consists of set of collectors, that can be used to collect profiling data into a united
profile format. Such format can be further preprocessed with various filters and transformers
to obtain different profiles (like e.g. aggregated profiles). Moreover, Perun contains set of
visualizations.

Perun currently exists as CLI application, with GUI application being in development.
"""

from __future__ import annotations

import importlib.metadata

__version__ = importlib.metadata.version("perun-toolsuite")
