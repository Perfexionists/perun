from . import parser as parser
from . import postprocess as postprocess

from .parser import (
    parse_resources_from_stream as parse_resources_from_stream,
    parse_events_from_stream as parse_events_from_stream,
)

from .postprocess import postprocess_folded_records as postprocess_folded_records
