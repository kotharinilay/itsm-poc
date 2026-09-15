"""Stage 1 placeholder so the suite is real and green from the first commit.

Its job is to prove CI actually collects and runs this package, rather than silently
discovering nothing and reporting success.
"""

from __future__ import annotations

import ragcore
from ragcore.config.composition import build_container


def test_package_imports() -> None:
    """The package imports and the composition root constructs."""
    assert ragcore.__doc__ is not None
    assert build_container() is not None
