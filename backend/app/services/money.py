"""Indian-style rupee formatting for server-generated text (₹1,42,000; paise only when non-zero)."""

from decimal import ROUND_HALF_UP, Decimal


def group_indian(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join(pairs) + "," + tail


def inr(value: object, paise: bool | None = None) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    rupees, cents = f"{abs(amount):.2f}".split(".")
    show_paise = paise if paise is not None else cents != "00"
    return f"{sign}₹{group_indian(rupees)}" + (f".{cents}" if show_paise else "")


def pct(value: object) -> str:
    """10.000 -> '10%', 2.500 -> '2.5%'."""
    text = f"{Decimal(str(value)).normalize():f}"
    return f"{text}%"
