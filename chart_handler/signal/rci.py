from typing import List

import mplfinance as mpf
import pandas
import numpy
from scipy.stats import rankdata

RCI_LIST = List[float]


class RCI:
    def __init__(self, df: pandas.DataFrame, duration: int) -> None:
        self._df = df
        self._duration = duration
        self._rci = self._calculate(duration)

    @property
    def df(self) -> pandas.DataFrame:
        return self._df

    @property
    def rci(self) -> RCI_LIST:
        return self._rci

    @property
    def duration(self) -> int:
        return self._duration

    def _calculate(self, duration: int) -> RCI_LIST:
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


class RCIBasic:
    def __init__(self, rci: RCI, level: int) -> None:
        if level == 0:
            raise RuntimeError('0 cannot be applied as level')
        self._rci = rci
        self._level = level
        self._speculation = self._determine_speculation(rci.rci, level)

    @property
    def rci(self) -> RCI:
        return self._rci

    @property
    def level(self) -> int:
        return self._level

    @property
    def speculation(self):
        return self._speculation

    def _determine_speculation(self, rci: RCI_LIST, level: int) -> List[float]:
        speculation = [numpy.nan] * len(rci)
        is_under_level = False
        k = 1 if level < 0 else -1
        level *= k

        for i, n in enumerate(rci):
            n *= k
            if not is_under_level and n < level:
                is_under_level = True
                continue

            if is_under_level and n > level:
                is_under_level = False
                speculation[i] = self.rci.df['Close'][i]

        return speculation


def plot(long: RCIBasic, short: RCIBasic, **kwargs) -> None:
    aps = [
        mpf.make_addplot(short.speculation, color='c', type='scatter', markersize=200, marker='v'),
        mpf.make_addplot(long.speculation, color='r', type='scatter', markersize=200, marker='^'),

        mpf.make_addplot([short.level] * len(short.rci.rci), color='black', linestyle='dotted', panel=1),
        mpf.make_addplot(short.rci.rci, color='c', ylabel=f'RCI{short.rci.duration}', panel=1, secondary_y=False),

        mpf.make_addplot([long.level] * len(long.rci.rci), color='black', linestyle='dotted', panel=2),
        mpf.make_addplot(long.rci.rci, color='r', ylabel=f'RCI{long.rci.duration}', panel=2, secondary_y=False),
    ]
    mpf.plot(long.rci.df, **{**{
        'type': 'candle',
        'addplot': aps,
        'show_nontrading': True,
    }, **kwargs})
