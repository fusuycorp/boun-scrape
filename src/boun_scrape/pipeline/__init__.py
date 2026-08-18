"""Data processing, delta calculation, and export pipeline."""

# NB: only `delta` is imported eagerly here. `exporter` imports `storage.repository`,
# while `repository` imports pipeline.delta — eagerly bundling exporter at package
# init made storage<->pipeline a cyclic import graph that broke isolated module/tests
# loads (fire + import_order dependent). All callers import from the submodules directly.
from boun_scrape.pipeline.delta import (
    compute_course_hash,
    compute_deltas,
    course_slot_to_dict,
    course_to_dict,
)

__all__ = [
    "compute_course_hash",
    "compute_deltas",
    "course_slot_to_dict",
    "course_to_dict",
]
