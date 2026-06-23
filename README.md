# Aylik Bot (1M)

Bu repo Aylik (1M) zaman dilimindeki otomatik sinyal kontrollerini calistirir.

Telegram raporlari StockMarketLab baslikli PNG tablo olarak gonderilir. Cok sayida sinyal geldiginde liste 30'lu gorsel sayfalara bolunur.

Ayni sembol birden fazla sinyal kodunda cikarsa ayrica Coklu Sinyal Ozeti olarak listelenir.

## Sinyal Kodlari

- `M-1`: MACD Pozitif Kesisim. MACD sinyal cizgisini yukari keser ve MACD pozitif bolgede kalir.
- `S-M-1`: SMI/MACD Momentum. SMI yukari kesisim ve MACD histogram pozitif momentum kosullarini arar.
- `S-M-V-1`: SMI/MACD Guclu Onay. S-M-1 kosullarina MA200 ustu fiyat ve guclu hacim onayi ekler.
- `E-V-1`: EMA Trend + Hacim. Kisa EMA yapisi uzun EMA yapisinin ustundedir ve hacim trendi destekler.
- `R-M-V-1`: RSI + MACD + Hacim. RSI guclenirken MACD yukari kesisim ve hacim artisi birlikte olusur.
- `A-M-V-1`: SMA + MACD + Hacim. SMA 5/8/21 dizilimi, MACD pozitifligi, RSI araligi ve hacim onayini birlestirir.
- `S-M-V-2`: SMI/MACD Full. SMI/MACD al sinyaline MA200 ustu fiyat ve hacim filtresi ekler.
- `S-M-2`: SMI/MACD Erken. SMI ve MACD momentum kesisimlerini temel alan erken sinyaldir.
- `R-V-1`: RSI Momentum. RSI guc bolgesine gecisi ve yukselis momentumunu izler.

Telegram ayarlari GitHub Actions secrets/variables uzerinden okunur:

- TG_BOT_TOKEN
- TG_CHAT_ID
- TG_THREAD_ID
- TV_USERNAME
- TV_PASSWORD
- TV_CHART_ID

Planli calisma GitHub Actions ile yapilir. Manuel calistirma icin Actions sekmesindeki workflow kullanilabilir.
