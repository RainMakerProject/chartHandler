from typing import Tuple, Literal, Optional

import dataclasses
import logging

from bitflyer import BitFlyer, ChildOrderRequest, ProductCode, Candlestick
from chart_handler.chart import Chart
from chart_handler.signal import ADXDMI, RCI

logger = logging.getLogger(__name__)

ADX_DURATION = 14


@dataclasses.dataclass
class Speculation:
    _entry_level: int
    _exit_level: int

    entry: bool = False
    exit: bool = False

    _entry_is_under_level: bool = False
    _exit_is_under_level: bool = False

    def _determine(self, rci: float, is_entry: bool) -> None:
        level = self._entry_level if is_entry else self._exit_level
        is_under_level = self._entry_is_under_level if is_entry else self._exit_is_under_level

        k = 1 if level < 0 else -1
        rci *= k
        level *= k

        if not is_under_level and rci < level:
            if is_entry:
                self._entry_is_under_level = True
            else:
                self._exit_is_under_level = True
            return

        if is_under_level and rci > level:
            if is_entry:
                self._entry_is_under_level = False
                self.entry = True
            else:
                self._exit_is_under_level = False
                self.exit = True

    def determine(self, entry_rci: float, exit_rci: float) -> None:
        self.entry = False
        self._determine(entry_rci, True)
        self.exit = False
        self._determine(exit_rci, False)


class AdxRci:
    """
    Long term candlestick: ADX, DIP, DIM
    Short term candlestick: RCI

    Trade condition:
    - Prerequisites:
        - Never hold more than one position at a time
    - Take a long position when:
        - ADX and DIP are above the threshold
        - RCI for entry is above the level after once it has been bellow the level
    - Close the long position when:
        - Meets either following condition
            - RCI for exit is bellow the level after once it has been above the level
            - Turning into a downtrend
    - Take a short position when:
        - ADX and DIM are above the threshold
        - RCI for entry is bellow the level after once it has been above the level
    - Close the short position when:
        - Meets either following condition
            - RCI for exit is above the level after once it has been bellow the level
            - Turning into a uptrend
    """
    def __init__(
            self, api_key: str, api_secret: str,
            product_code: ProductCode, trend_candle: Candlestick, trade_candle: Candlestick,
            entry_rci_duration: int, entry_rci_level: int, exit_rci_duration: int, exit_rci_level: int,
            adx_threshold: int, di_threshold: int, trade_size: float,
    ) -> None:

        self.product_code = product_code
        self.trade_size = trade_size
        self.bitflyer_client = BitFlyer(api_key, api_secret)

        num_candles = max(entry_rci_duration, exit_rci_duration) + 1
        self.trend_chart = Chart(product_code, trend_candle, auto_following=False, max_num_of_candles=ADX_DURATION * 2)
        self.trade_chart = Chart(product_code, trade_candle, auto_following=False, max_num_of_candles=num_candles)

        self.entry_rci_duration, self.entry_rci_level, self.exit_rci_duration, self.exit_rci_level = (
            entry_rci_duration, entry_rci_level, exit_rci_duration, exit_rci_level,
        )
        self.adx_threshold, self.di_threshold = adx_threshold, di_threshold
        self.uptrend = Speculation(entry_rci_level * -1, exit_rci_level)
        self.downtrend = Speculation(entry_rci_level, exit_rci_level * -1)

        self._position: Optional[Literal['LONG', 'SHORT']] = None

    def trade(self) -> None:
        self._update_speculations()

        # Normally closing a position using RCI signal
        if self._position is not None:
            if self._position == 'LONG':
                closing_side, speculation = 'SELL', self.uptrend
            else:  # self.position == 'SHORT'
                closing_side, speculation = 'BUY', self.downtrend

            if speculation.exit:
                self._close_position(closing_side)

        adxdmi = self._get_adxdmi()

        adx = adxdmi.adx.tail(1)[-1]
        dip, dim = adxdmi.dip.tail(1)[-1], adxdmi.dim.tail(1)[-1]  # TODO: Move
        logger.info(f' +++> ADX: {"{:.3f}".format(adx)}, DIP: {"{:.3f}".format(dip)}, DIM: {"{:.3f}".format(dim)}')  # TODO: Remove
        if adx < self.adx_threshold:
            return

        if dip >= self.di_threshold and dim >= self.di_threshold or dip <= self.di_threshold and dim <= self.di_threshold:
            return

        if dip >= self.di_threshold:
            opening_side, speculation = 'BUY', self.uptrend
        elif dim >= self.di_threshold:
            opening_side, speculation = 'SELL', self.downtrend
        else:
            return

        # Close the holding short position if in a uptrend or,
        # Close the holding long position if in a downtrend
        if self._position is not None and (self._position == 'SHORT' if opening_side == 'BUY' else 'LONG'):
            self._close_position(opening_side)
        # Acquire a new position if the condition to open a new one
        elif speculation.entry:
            self._open_position(opening_side)

    def _open_position(self, side: Literal['BUY', 'SELL']) -> None:
        if self._position:
            raise RuntimeError('Active position exists')
        self._trade_position(side)
        self._position = 'LONG' if side == 'BUY' else 'SHORT'
        logger.info(f'Opened a {self._position} position')

    def _close_position(self, side: Literal['BUY', 'SELL']) -> None:
        if self._position is None:
            raise RuntimeError('No position to close')
        self._trade_position(side)
        logger.info(f'Closed a {self._position} position')
        self._position = None

    def _trade_position(self, side: Literal['BUY', 'SELL']) -> None:
        # self.bitflyer_client.send_child_order(ChildOrderRequest(
        #     self.product_code, 'MARKET', side, self.trade_size,
        # ))
        logger.info(f'Traded a position: price: {self.trade_chart.df["Close"].tail(1)[-1]}, side: {side}, size: {self.trade_size}')

    def _get_adxdmi(self) -> ADXDMI:
        self.trend_chart.follow_up_to_current()
        return ADXDMI(self.trend_chart.df, ADX_DURATION)

    def _get_rcis(self) -> Tuple[RCI, RCI]:
        self.trade_chart.follow_up_to_current()
        return (
            RCI(self.trade_chart.df, self.entry_rci_duration),
            RCI(self.trade_chart.df, self.exit_rci_duration),
        )

    def _update_speculations(self) -> None:
        entry_rci, exit_rci = self._get_rcis()
        entry_val = entry_rci.rci.tail(1)[-1]
        exit_val = exit_rci.rci.tail(1)[-1]
        self.uptrend.determine(entry_val, exit_val)
        self.downtrend.determine(entry_val, exit_val)
        logger.info(
            ' ===> '
            f'Entry: RCI: {"{:.3f}".format(entry_val)}, up: {self.uptrend.entry}, down: {self.downtrend.entry}, '
            f'Exit: RCI: {"{:.3f}".format(exit_val)}, up: {self.uptrend.exit}, down: {self.downtrend.exit}, '
        )  # TODO: Remove
