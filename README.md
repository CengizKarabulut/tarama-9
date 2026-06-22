# Tarama 9 - 1M

Bu repo Aylik (1M) zaman dilimindeki tum otomatik taramalari calistirir.

Telegram raporlari StockMarketLab baslikli PNG tablo olarak gonderilir. Cok sayida sinyal geldiginde liste 30'lu gorsel sayfalara bolunur.

Ayni sembol birden fazla taramada cikarsa ayrica Coklu Tarama Ozeti olarak listelenir.

Bu repoda calisan sinyal kovasi listesi:

- T1 MACD Cross
- T2 H8
- T3 I9
- T4 EMA
- T5 RSI MACD
- T6 Yeni Tarama
- T7 Tam SMI/MACD
- T8 SMI/MACD
- T9 RSI

Telegram ayarlari GitHub Actions secrets/variables uzerinden okunur:

- TG_BOT_TOKEN
- TG_CHAT_ID
- TG_THREAD_ID
- TV_USERNAME
- TV_PASSWORD
- TV_CHART_ID

Planli calisma GitHub Actions ile yapilir. Manuel calistirma icin Actions sekmesindeki workflow kullanilabilir.
