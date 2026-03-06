"""Line splitting, merging, and structural processing."""
from .line_splitter import TooltipLineSplitter, group_by_y
from .mabinogi_tooltip_splitter import MabinogiTooltipSplitter
from .line_processing import (
    group_by_distance,
    merge_group_bounds,
    trim_outlier_tail,
    promote_grey_by_prefix,
    determine_enchant_slots,
    merge_continuations,
    count_effects_per_header,
)
from .line_merge import detect_gap_outlier
