import talib
import pandas


class RSI:
    def __init__(self, df: pandas.DataFrame, duration: int) -> None:
        self._df = df
        self._duration = duration
        self._rsi = talib.RSI(df['Close'], timeperiod=duration)

    @property
    def df(self) -> pandas.DataFrame:
        return self._df

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def rsi(self) -> pandas.Series:
        return self._rsi
