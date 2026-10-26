def fact(start: str | None, end: str, val: float, filed: str) -> dict:
    row = {"end": end, "val": val, "filed": filed}
    if start is not None:
        row["start"] = start
    return row


def companyfacts(items: dict[str, list[dict]], taxonomy: str = "us-gaap", unit: str = "USD") -> dict:
    """Build the SEC companyfacts shape from {tag: [fact rows]}."""
    return {"facts": {taxonomy: {tag: {"units": {unit: rows}} for tag, rows in items.items()}}}
