"""A plain-language valuation verdict: undervalued, fairly valued or overvalued.

The yardstick is the Graham Number, the highest price that still passes both
of Graham's Chapter 14 limits (P/E 15 on 3-year average earnings and P/B 1.5).
It is deliberately conservative: many good modern companies come out as
"overvalued" by it. The verdict says "by Graham's standard" wherever shown.
"""

from __future__ import annotations

from dataclasses import dataclass

from .graham import Valuation

# Price within +/-15% of the Graham Number counts as fairly valued.
UNDERVALUED_BELOW = 0.85
OVERVALUED_ABOVE = 1.15

UNDER, FAIR, OVER, UNKNOWN = "undervalued", "fair", "overvalued", "unknown"

LABELS = {
    UNDER: "Undervalued",
    FAIR: "Fairly valued",
    OVER: "Overvalued",
    UNKNOWN: "Can't value",
}


@dataclass
class Verdict:
    code: str
    label: str
    ratio: float | None  # price / Graham Number
    explanation: str


def verdict(v: Valuation) -> Verdict:
    if v.price is None or v.graham_number is None:
        return Verdict(UNKNOWN, LABELS[UNKNOWN], None,
                       "Needs positive average earnings and positive book value. Graham would call it speculative.")
    ratio = v.price / v.graham_number
    if ratio <= UNDERVALUED_BELOW:
        code = UNDER
        text = f"Price is {(1 - ratio) * 100:.0f}% below the Graham Number."
    elif ratio >= OVERVALUED_ABOVE:
        code = OVER
        text = (f"Price is {ratio:.1f} times the Graham Number." if ratio >= 2
                else f"Price is {(ratio - 1) * 100:.0f}% above the Graham Number.")
    else:
        code = FAIR
        text = f"Price is within {abs(ratio - 1) * 100:.0f}% of the Graham Number."
    return Verdict(code, LABELS[code], ratio, text)
