# Tarama 9

Bu repo tek bir otomatik tarama calistirir.

Telegram raporlari StockMarketLab baslikli PNG tablo olarak gonderilir. Cok sayida sinyal geldiginde liste 30'lu gorsel sayfalara bolunur.

GitHub Actions manuel calistirmada `timeframes` alanindan tek zaman dilimi ya da `all` secilebilir:

- all
- 15m
- 1H
- 4H
- 1D
- 1W
- 1M

Telegram ayarlari GitHub Actions secrets/variables uzerinden okunur:

- TG_BOT_TOKEN
- TG_CHAT_ID
- TG_THREAD_ID
- TV_USERNAME
- TV_PASSWORD
- TV_CHART_ID

Planli calisma GitHub Actions ile yapilir. Manuel calistirma icin Actions sekmesindeki workflow kullanilabilir.