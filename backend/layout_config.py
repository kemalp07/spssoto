"""Tablo düzeni yerelleştirme ve biçim ayarları."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LayoutConfig(BaseModel):
    locale: str = "tr"
    decimal_separator: str = ","
    leading_zero: bool = True
    title_style: Literal["tr_classic", "apa7"] = "tr_classic"
    merge_demographics: bool = True
    correlation_lower_triangle: bool = True
    merge_group_comparisons: bool = True
    suppress_normality_to_footnote: bool = True

    @classmethod
    def from_optional(cls, data: Optional[dict]) -> "LayoutConfig":
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


DEFAULT_LAYOUT_CONFIG = LayoutConfig()
