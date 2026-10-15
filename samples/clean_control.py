def format_names(names):
    """Return non-empty names with surrounding whitespace removed."""
    return [name.strip() for name in names if name.strip()]


def total_prices(prices):
    """Return the sum of a sequence of prices."""
    return sum(prices)
