from typing import List

import mplfinance as mpf
import pandas
import numpy
from scipy.stats import rankdata

RCI_LIST = List[float]


class RCI:
    def __init__(
            self, df: pandas.DataFrame,
            duration_long: int = 21, level_long: int = -70,
            duration_short: int = 33, level_short: int = 90,
    ) -> None:

        self.df = df
        self.duration_long = duration_long
        self.duration_short = duration_short
        self.level_long = level_long
        self.level_short = level_short

        self.rci_long = self.calculate(duration_long)
        self.rci_short = self.calculate(duration_short)
        self.timing_long = self.determine_timing(self.rci_long, level_long)
        self.timing_short = self.determine_timing(self.rci_short, level_short)

    def determine_timing(self, rci: RCI_LIST, level: int) -> List[float]:
        timing = [numpy.nan] * len(rci)
        is_under_level = False

        for i, n in enumerate(rci):
            if not is_under_level and n < level:
                is_under_level = True
                continue

            if is_under_level and n >= level:
                is_under_level = False
                timing[i] = self.df['Close'][i]

        return timing

    def calculate(self, duration: int) -> RCI_LIST:
        rci_list = [numpy.nan] * (duration - 1)
        closes = self.df['Close']

        nb_close = len(closes)
        for i in range(nb_close):
            if i + duration > nb_close:
                break

            y = closes[i:i + duration]
            x_rank = numpy.arange(len(y))
            y_rank = rankdata(y, method='ordinal') - 1
            sum_diff = sum((x_rank - y_rank) ** 2)
            rci = (1 - ((6 * sum_diff) / (duration ** 3 - duration))) * 100
            rci_list.append(rci)

        return rci_list

    def plot(self, **kwargs) -> None:
        aps = [
            mpf.make_addplot(self.timing_short, color='c', type='scatter', markersize=200, marker='v'),
            mpf.make_addplot(self.timing_long, color='r', type='scatter', markersize=200, marker='^'),

            mpf.make_addplot([self.level_short] * len(self.rci_short), color='black', linestyle='dotted', panel=1),
            mpf.make_addplot(self.rci_short, color='c', ylabel=f'RCI{self.duration_short}', panel=1, secondary_y=False),

            mpf.make_addplot([self.level_long] * len(self.rci_long), color='black', linestyle='dotted', panel=2),
            mpf.make_addplot(self.rci_long, color='r', ylabel=f'RCI{self.duration_long}', panel=2, secondary_y=False),
        ]
        mpf.plot(self.df, **{**{
            'type': 'candle',
            'addplot': aps,
            'show_nontrading': True,
        }, **kwargs})
