from typing import List, Dict

import dataclasses
from datetime import datetime

import joblib
import pandas
import numpy
import mplfinance as mpf

from bitflyer import ProductCode, Candlestick
from chart_handler.chart import Chart
from chart_handler.signal.trend import ADXDMI
from chart_handler.signal.rci import RCI, RCIBasic
from chart_handler.signal.rsi import RSI

rcis = {}
basics = {}
trends = {}


def get_rci(df: pandas.DataFrame, duration: int) -> RCI:
    if duration not in rcis:
        rcis[duration] = RCI(df, duration)
    return rcis[duration]


def get_basic(df: pandas.DataFrame, duration: int, level: int) -> RCIBasic:
    if level not in basics:
        basics[level] = {}
    if duration not in basics[level]:
        basics[level][duration] = RCIBasic(get_rci(df, duration), level)
    return basics[level][duration]


def get_trend(df: pandas.DataFrame, duration: int) -> ADXDMI:
    if duration not in trends:
        trends[duration] = ADXDMI(df, duration)
    return trends[duration]


@dataclasses.dataclass
class Profit:
    trend_chart_duration: int
    trade_chart_duration: int

    entry_rci_duration: int
    entry_rci_level: int
    exit_rci_duration: int
    exit_rci_level: int
    adx_threshold: int
    di_threshold: int

    won_sum: float = 0.0
    lost_sum: float = 0.0
    trade_count: int = 0
    won_count: int = 0

    @property
    def profit(self) -> float:
        return self.won_sum + self.lost_sum

    @property
    def profit_average(self) -> float:
        return self.profit / (self.trade_count or 1)

    @property
    def won_average(self) -> float:
        return self.won_sum / (self.won_count or 1)

    @property
    def lost_average(self) -> float:
        return self.lost_sum / ((self.trade_count - self.won_count) or 1)

    @property
    def won_ratio(self) -> float:
        return self.won_count / (self.trade_count or 1)

    def to_dict(self):
        return {
            'trend_chart_duration': self.trend_chart_duration,
            'trade_chart_duration': self.trade_chart_duration,
            'entry_rci_duration': self.entry_rci_duration,
            'entry_rci_level': self.entry_rci_level,
            'exit_rci_duration': self.exit_rci_duration,
            'exit_rci_level': self.exit_rci_level,
            'adx_threshold': self.adx_threshold,
            'di_threshold': self.di_threshold,
            'won_sum': self.won_sum,
            'lost_sum': self.lost_sum,
            'trade_count': self.trade_count,
            'won_count': self.won_count,
            'profit': self.profit,
            'profit_average': self.profit_average,
            'won_average': self.won_average,
            'lost_average': self.lost_average,
            'won_ratio': self.won_ratio,
        }


class Simulator:
    def __init__(
            self, trend_df: pandas.DataFrame, trade_df: pandas.DataFrame,
            u_long_duration: int, u_long_level: int, u_short_duration: int, u_short_level: int,
            d_long_duration: int, d_long_level: int, d_short_duration: int, d_short_level: int,
            adx_threshold: int, dip_threshold: int, dim_threshold: int,
    ) -> None:
        self.trend = get_trend(trend_df, 14)

        self.uptrend = (
            get_basic(trade_df, u_long_duration, u_long_level),
            get_basic(trade_df, u_short_duration, u_short_level),
        )
        self.downtrend = (
            get_basic(trade_df, d_long_duration, d_long_level),
            get_basic(trade_df, d_short_duration, d_short_level),
        )
        self.trade_df = trade_df

        self.adx_threshold = adx_threshold
        self.dip_threshold = dip_threshold
        self.dim_threshold = dim_threshold

    def run(self, p: Profit) -> None:
        history = {}
        results = {}
        profit = 0
        longs: List[int] = []
        shorts: List[int] = []
        limit = 1

        for dt in self.trade_df.index:
            result = 0

            if longs and shorts:
                raise RuntimeError('Both!!!!!!!!!!!!1')

            if longs and (price := self.uptrend[1].speculation.get(dt)):
                result += price * len(longs) - sum(longs)
                longs.clear()
            elif shorts and (price := self.downtrend[0].speculation.get(dt)):
                result += sum(shorts) - price * len(shorts)
                shorts.clear()

            if result != 0:
                p.trade_count += 1
                if result > 0:
                    p.won_count += 1
                    p.won_sum += result
                else:
                    p.lost_sum += result

                results[dt] = result
                profit += result
                result = 0

            history[dt] = profit

            adx = self.trend.adx[self.trend.adx.index <= dt].tail(1)
            trend_dt = adx.index[0]
            if adx.empty or numpy.isnan(adx[0]) or adx[0] < self.adx_threshold:
                continue

            dip = self.trend.dip[trend_dt]
            dim = self.trend.dim[trend_dt]
            if dip >= self.dip_threshold and dim >= self.dim_threshold or dip <= self.dip_threshold and dim <= self.dim_threshold:
                continue

            if dip >= self.dip_threshold:
                if shorts:
                    result += sum(shorts) - self.trade_df['Close'][dt] * len(shorts)
                    shorts.clear()
                elif (price := self.uptrend[0].speculation.get(dt)) and len(longs) < limit:
                    longs.append(price)
            elif dim >= self.dim_threshold:
                if longs:
                    result += self.trade_df['Close'][dt] * len(longs) - sum(longs)
                    longs.clear()
                elif (price := self.downtrend[1].speculation.get(dt)) and len(shorts) < limit:
                    shorts.append(price)

            if result != 0:
                result = result + (results.get(dt) or 0)
                results[dt] = result
                profit += result

                p.trade_count += 1
                if result > 0:
                    p.won_count += 1
                    p.won_sum += result
                else:
                    p.lost_sum += result

            history[dt] = profit

    def plot(self, **kwargs) -> None:
        aps = [
            mpf.make_addplot(self.history * 1, panel=1, secondary_y=False)
        ]
        mpf.plot(self.trade_df, **{**{
            'type': 'candle',
            'addplot': aps,
            'show_nontrading': True,
        }, **kwargs})


def simulate():
    print(f'Start: {datetime.now()}')

    kwargs = {'_from': datetime(1700, 1, 1), '_to': datetime(2021, 11, 30)}
    charts = {
        60: Chart(ProductCode.FX_BTC_JPY, Candlestick.ONE_HOUR, **kwargs),
        30: Chart(ProductCode.FX_BTC_JPY, Candlestick.THIRTY_MINUTES, **kwargs),
        # 15: Chart(ProductCode.FX_BTC_JPY, Candlestick.FIFTEEN_MINUTES, **kwargs),
        5: Chart(ProductCode.FX_BTC_JPY, Candlestick.FIVE_MINUTES, **kwargs),
        1: Chart(ProductCode.FX_BTC_JPY, Candlestick.ONE_MINUTE, **kwargs),
    }

    for trade_minutes in [1, 5]:
        rcis.clear()
        basics.clear()
        trade_chart = charts[trade_minutes]

        for trend_minutes in [30, 60]:
            print(f'{datetime.now()}: Trade: {trade_minutes}, Trend: {trend_minutes}')
            trends.clear()
            trend_chart = charts[trend_minutes]

            def perform(s: Simulator, p: Profit, _adx: int, di: int, entry_d: int, exit_d: int, entry_l: int,
                        exit_l: int) -> Dict:
                print(
                    f'{datetime.now()}: Trade: {trade_minutes}, Trend: {trend_minutes}, '
                    f'ADX: {_adx}, DI: {di}, '
                    f'ENTRY: D: {entry_d}, L: {entry_l}, EXIT: D: {exit_d}, L: {exit_l}'
                )
                s.run(p)
                return p.to_dict()

            profits = joblib.Parallel(n_jobs=-1)(
                joblib.delayed(perform)(
                    Simulator(
                        trend_chart.df, trade_chart.df,
                        entry_d, -entry_l, exit_d, exit_l,
                        exit_d, -exit_l, entry_d, entry_l,
                        _adx, di, di,
                    ),
                    Profit(
                        trend_minutes, trade_minutes,
                        entry_d, entry_l, exit_d, exit_l,
                        _adx, di,
                    ),
                    _adx,
                    di,
                    entry_d,
                    exit_d,
                    entry_l,
                    exit_l,
                )
                for exit_l in [80, 85, 90, 95]
                for entry_l in [80, 85, 90, 95]
                for exit_d in [9, 13, 18, 21, 26, 34, 45]  # 5, 8, 22, 42, 52, 55, 75, 89]
                for entry_d in [9, 13, 18, 21, 26, 34, 45]  # 5, 8, 22, 42, 52, 55, 75, 89]
                for di in [20, 25, 30]
                for _adx in [20, 25, 30]
            )

            print(profits)

            with open(f'simulate_trend_rci_{trade_minutes}_{trend_minutes}.csv', 'w') as f:
                f.write(pandas.DataFrame(profits).to_csv())

    print(f'End: {datetime.now()}')


if __name__ == '__main__':
    simulate()
