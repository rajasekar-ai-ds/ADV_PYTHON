"""Bill calculation: pure functions, no database, so they are easy to test."""
from decimal import Decimal


def energy_charge(units, slabs):
    """Slab-wise (telescopic) charge.

    slabs: list of dicts with from_unit, to_unit (None = no upper limit),
    rate_per_unit, sorted by from_unit. Each unit is charged at the rate of
    the slab it falls in. Example with slabs 1-100 @ 0, 101-200 @ 2.35:
    150 units -> 100 * 0 + 50 * 2.35 = 117.50
    """
    total = Decimal("0")
    breakdown = []
    for s in slabs:
        start = s["from_unit"]
        end = s["to_unit"] if s["to_unit"] is not None else units
        if units < start:
            break
        units_in_slab = min(units, end) - start + 1
        if units_in_slab <= 0:
            continue
        amount = Decimal(units_in_slab) * Decimal(str(s["rate_per_unit"]))
        total += amount
        breakdown.append({
            "range": f"{start}-{s['to_unit'] if s['to_unit'] is not None else 'above'}",
            "units": units_in_slab,
            "rate": Decimal(str(s["rate_per_unit"])),
            "amount": amount,
        })
    return total.quantize(Decimal("0.01")), breakdown
