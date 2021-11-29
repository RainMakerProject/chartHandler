from typing import Callable

import threading
import time
import dataclasses
from datetime import datetime, timedelta

import mplfinance
import numpy
import pandas
from pandas.core.indexes.datetimes import DatetimeIndex

from bitflyer import ChartType, ProductCode, Candlestick
from .models import ChartTable


@dataclasses.dataclass
class Analyzer:
    name: str
    analyzer: Callable[[pandas.DataFrame], None]
    interval: float


class Chart:
    def __init__(
            self, product_code: ProductCode, candlestick: Candlestick,
            auto_following: bool = True, following_interval: float = 5.0,
            max_num_of_candles: int = numpy.inf,
            _from: datetime = datetime(1700, 1, 1), _to: datetime = datetime.utcnow(),
    ) -> None:

        self._lock = threading.Lock()
        self.__max_num_of_candles = max_num_of_candles
        self.chart_type: ChartType = getattr(ChartType, f'{product_code.name}_{candlestick.name}')

        condition = ChartTable.period_from.between(_from, _to)
        if isinstance(max_num_of_candles, int) and max_num_of_candles > 0:
            now = datetime.utcnow()
            _from = now - timedelta(seconds=(candlestick.value * max_num_of_candles))
            condition = ChartTable.period_from.between(_from, now)
        self.__df = ChartTable.query_as_data_frame(self.chart_type, condition)

        if auto_following:
            self.__start_thread(following_interval)

    def __start_thread(self, interval: float) -> None:
        def _continue_following() -> None:
            start_time = time.time()

            while True:
                _t = threading.Thread(target=self.follow_up_to_current)
                _t.start()
                _t.join()

                time_to_wait = ((start_time - time.time()) % interval) or interval
                time.sleep(time_to_wait)

        t = threading.Thread(target=_continue_following)
        t.start()

    @property
    def df(self) -> pandas.DataFrame:
        while self._lock.locked():
            pass
        return self.__df

    def follow_up_to_current(self) -> None:
        self._lock.acquire()

        last_index: DatetimeIndex = self.__df.tail(1).index  # noqa

        d = last_index.date[0]
        t = last_index.time[0]
        dt: datetime = datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, 1)

        newer_df = ChartTable.query_as_data_frame(
            self.chart_type,
            ChartTable.period_from.between(dt, datetime.utcnow()),
        )

        self.__df = self.__df.append(newer_df)

        if len(self.__df.index) > self.__max_num_of_candles:
            self.__df = self.__df.iloc[-self.__max_num_of_candles:, :]

        self._lock.release()

    def plot(self, **kwargs) -> None:
        mplfinance.plot(self.df, **{**{
            'title': self.chart_type.name,
            'type': 'candle',
            'volume': True,
            'show_nontrading': True,
        }, **kwargs})
