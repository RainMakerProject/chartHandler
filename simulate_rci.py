from typing import Optional, Literal, Tuple

import os
import dataclasses
import pandas
import numpy

from chart_handler.signal.rci import RCI, RCIBasic


@dataclasses.dataclass
class Profit:
    chart: Optional[str]
    entry: Literal['long', 'short']
    profit: float
    won_ratio: float
    won_count: int
    trade_count: int
    duration_long: int
    level_long: int
    duration_short: int
    level_short: int


def _simulate(rci_long: RCIBasic, rci_short: RCIBasic, is_long_first: bool) -> Profit:
    entry = 'long' if is_long_first else 'short'
    p = Profit(None, entry, 0.0, 0.0, 0, 0, rci_long.rci.duration, rci_long.level, rci_short.rci.duration,
               rci_short.level)
    has_position = False
    entry_price = numpy.nan

    rci1 = rci_long if is_long_first else rci_short
    rci2 = rci_short if is_long_first else rci_long

    for i, price in enumerate(rci1.speculation):
        if not has_position:
            if price is not numpy.nan:
                has_position = True
                entry_price = price

        elif rci2.speculation[i] is not numpy.nan:
            profit = rci2.speculation[i] - entry_price if is_long_first else entry_price - rci2.speculation[i]
            p.profit += profit
            p.won_count += 1 if profit > 0 else 0
            p.trade_count += 1
            p.won_ratio = p.won_count / p.trade_count
            has_position = False
            entry_price = numpy.nan

    return p


def simulate(rci_long: RCIBasic, rci_short: RCIBasic) -> Tuple[Profit, Profit]:
    long = _simulate(rci_long, rci_short, True)
    short = _simulate(rci_long, rci_short, False)

    return long, short


def perform(df: pandas.DataFrame, chart_name: str) -> pandas.DataFrame:
    duration_range = range(9, 100)
    levels = [70, 75, 80, 85, 90, 95]
    rcis = {d: RCI(df, d) for d in duration_range}
    basics = {}
    for duration, rci in rcis.items():
        basics[duration] = {}
        for level in levels:
            basics[duration][level] = RCIBasic(rci, level)
            basics[duration][-level] = RCIBasic(rci, -level)

    profits = []
    for level_long in [-level for level in levels]:
        for level_short in levels:
            for duration_long in duration_range:
                for duration_short in duration_range:
                    p1, p2 = simulate(basics[duration_long][level_long], basics[duration_short][level_short])
                    p1.chart = chart_name
                    p2.chart = chart_name
                    profits.append(p1)
                    profits.append(p2)

    return pandas.DataFrame(profits)


if __name__ == '__main__':
    duration = '2021-11-05T19:00:00_2021-11-10T18:00:00'
    profits = pandas.DataFrame()

    for file in os.listdir(f'csv/{duration}'):
        name, _ = tuple(file.split('.'))
        df = pandas.read_csv(f'csv/{duration}/{file}', index_col='Date', parse_dates=True)
        profits = pandas.concat([profits, perform(df, name)]).reset_index(drop=True)

    with open(f'{duration}_rci.csv', 'w') as f:
        f.write(profits.to_csv())
