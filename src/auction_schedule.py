from dataclasses import dataclass


@dataclass(frozen=True)
class AuctionResult:
    month: int
    bid_amount: float
    dividend: float
    prize_money: float


AUCTION_SCHEDULE = {
    1: AuctionResult(1, 150000, 5000, 350000),
    2: AuctionResult(2, 25000, 0, 475000),
    3: AuctionResult(3, 150000, 5000, 350000),
    4: AuctionResult(4, 150000, 5000, 350000),
    5: AuctionResult(5, 143000, 4720, 357000),
    6: AuctionResult(6, 135999, 4439, 364001),
    7: AuctionResult(7, 129000, 4160, 371000),
    8: AuctionResult(8, 122000, 3880, 378000),
    9: AuctionResult(9, 115000, 3600, 385000),
    10: AuctionResult(10, 108000, 3320, 392000),
    11: AuctionResult(11, 101000, 3040, 399000),
    12: AuctionResult(12, 94000, 2760, 406000),
    13: AuctionResult(13, 87000, 2480, 413000),
    14: AuctionResult(14, 83500, 2340, 416500),
    15: AuctionResult(15, 80000, 2200, 420000),
    16: AuctionResult(16, 74750, 1990, 425250),
    17: AuctionResult(17, 69500, 1780, 430500),
    18: AuctionResult(18, 64250, 1570, 435750),
    19: AuctionResult(19, 59000, 1360, 441000),
    20: AuctionResult(20, 53750, 1150, 446250),
    21: AuctionResult(21, 45000, 800, 455000),
    22: AuctionResult(22, 39750, 590, 460250),
    23: AuctionResult(23, 34500, 380, 465500),
    24: AuctionResult(24, 25000, 0, 475000),
    25: AuctionResult(25, 25000, 0, 475000),
}


def get_auction_result(
    month: int,
    schedule: dict[int, AuctionResult] | None = None,
) -> AuctionResult:
    """
    Return the auction result for a given month.

    Defaults to the built-in demo schedule. Pass ``schedule`` to use
    another one, such as a schedule built from historical data by
    src.reference_curve.
    """

    table = AUCTION_SCHEDULE if schedule is None else schedule

    if month not in table:
        raise ValueError(
            f"Invalid auction month: {month}. "
            f"Expected a month between 1 and {len(table)}."
        )

    return table[month]