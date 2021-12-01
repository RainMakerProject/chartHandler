import time

from bitflyer import ProductCode, Candlestick
from trader.adx_rci import AdxRci

import logging

logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    trade_candlestick = Candlestick.ONE_MINUTE
    trader = AdxRci(
        '7APcoNivPCpTLNVcDHmYwo', 'Hk5F7T46xS81+YdbzbxR212S4HCmKOKlrmoeF/XLg1g=',
        ProductCode.FX_BTC_JPY, Candlestick.THIRTY_MINUTES, trade_candlestick,
        9, 80, 18, 80,  # 9, 85, 18, 90,
        10, 20,  # 20, 25,
        0.01,
    )

    while True:
        trader.trade()
        time.sleep(trade_candlestick.value)
