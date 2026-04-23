from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


CoordinateInput = int | float | Fraction


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _coerce_fraction(value: CoordinateInput, field_name: str) -> Fraction:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    raise TypeError(f"{field_name} must be an int, float, or Fraction.")


def _normalize_half_step(value: CoordinateInput, field_name: str) -> int:
    fraction = _coerce_fraction(value, field_name)
    doubled = fraction * 2

    if doubled.denominator != 1:
        raise ValueError(f"{field_name} must be integer or half-integer.")

    return doubled.numerator


@dataclass(frozen=True, slots=True)
class CenterSpec:
    """A galaxy center stored on a doubled integer lattice."""

    id: str
    row_coord2: int
    col_coord2: int

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Center id must be non-empty.")
        if not _is_plain_int(self.row_coord2) or not _is_plain_int(self.col_coord2):
            raise TypeError("Doubled center coordinates must be integers.")

    @classmethod
    def from_coordinates(
        cls,
        id: str,
        row_coord: CoordinateInput,
        col_coord: CoordinateInput,
    ) -> "CenterSpec":

        return cls(
            id=id,
            row_coord2=_normalize_half_step(row_coord, "row_coord"),
            col_coord2=_normalize_half_step(col_coord, "col_coord"),
        )

    @property
    def row_coord(self) -> Fraction:

        return Fraction(self.row_coord2, 2)

    @property
    def col_coord(self) -> Fraction:

        return Fraction(self.col_coord2, 2)


__all__ = ["CenterSpec", "CoordinateInput"]
