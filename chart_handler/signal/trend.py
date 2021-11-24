import talib
import pandas
import mplfinance as mpf


class ADXDMI:
    def __init__(self, df: pandas.DataFrame, duration: int = 14) -> None:
        self._df = df
        self._duration = duration
        self.__args = (self.df['High'], self.df['Low'], self.df['Close'], self.duration)

        self._adx = self._calculate_adx()
        self._dip = None
        self._dim = None

    @property
    def df(self) -> pandas.DataFrame:
        return self._df

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def adx(self) -> pandas.Series:
        return self._adx

    @property
    def dip(self) -> pandas.Series:
        if self._dip is None:
            self._dip = talib.PLUS_DI(*self.__args)
        return self._dip

    @property
    def dim(self) -> pandas.Series:
        if self._dim is None:
            self._dim = talib.MINUS_DI(*self.__args)
        return self._dim

    def _calculate_adx(self) -> pandas.Series:
        return talib.ADX(*self.__args)

    def plot(self, **kwargs) -> None:
        aps = [
            mpf.make_addplot(self.adx, color='black', panel=1, secondary_y=False, ylabel=f'DI, ADX ({self.duration})'),
            mpf.make_addplot(self.dip, color='orange', panel=1),
            mpf.make_addplot(self.dim, color='c', panel=1),

            mpf.make_addplot([20] * len(self.adx), color='gray', panel=1, linestyle='dotted'),
            mpf.make_addplot([30] * len(self.adx), color='gray', panel=1, linestyle='dotted'),
        ]
        mpf.plot(self.df, **{**{
            'type': 'candle',
            'addplot': aps,
            'show_nontrading': True,
        }, **kwargs})
