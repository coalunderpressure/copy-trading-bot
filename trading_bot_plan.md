# Telegram Trading Userbot - Master Plan

Bu dosya, önceki iki plan dokümanının birleştirilmiş ve tutarlı halidir.
Hedef, sadece userbot mimarisi ile çalışan yarı-otonom bir trading bot oluşturmaktır.

## 1. Proje Özeti
Sistem, hedef Telegram kanalındaki sinyalleri dinler, AI ile yapılandırılmış veriye çevirir, kullanıcıdan onay alır ve CCXT üzerinden emri borsaya iletir.

Temel prensip: Otomasyon + İnsan Onayı (Human-in-the-Loop).

## 2. Mimari (Userbot-Only)
1. Listener: Telethon userbot ile kanal dinleme.
2. Parser: Metin/görsel sinyali AI ile strict JSON formatına dönüştürme.
3. Approval Layer: Userbot üzerinden kullanıcıya özet gönderme ve onay alma.
4. Executor: CCXT ile emir, TP/SL ve risk yönetimi.
5. State Store: İşlem durumu ve logların yerel kalıcılığı (SQLite).

Akış:
`[Telegram Channel] -> [Telethon Listener] -> [AI Parser] -> [Userbot Approval] -> [CCXT Executor]`

## 3. Teknoloji Yığını
- Python 3.11+
- Telethon
- CCXT
- OpenAI veya Gemini API
- python-dotenv
- SQLite (başlangıçta)

## 4. Veri Sözleşmesi (Parser Çıktısı)
```json
{
  "pair": "BTC/USDT",
  "direction": "LONG",
  "entry_zone": [45000, 45500],
  "targets": [46000, 47000, 48000],
  "stop_loss": 44000,
  "leverage": 10,
  "margin_mode": "isolated",
  "order_type": "limit",
  "confidence": 0.82
}
```

## 5. Fazlar ve Deliverable'lar

### Faz 1 - Temel Altyapı ve Listener
- Python proje iskeleti ve ayarlar.
- Telethon oturumu, hedef kanal filtreleme, mesaj toplama.
- Medya indirme ve ham event loglama.

### Faz 2 - Parser ve Doğrulama
- AI istemcisi entegrasyonu.
- Strict JSON parser + şema doğrulama.
- Hatalı/eksik sinyal için güvenli fallback.

### Faz 3 - Userbot Onay Akışı
- Gelen sinyali okunabilir trade özetine çevirme.
- Onay, iptal, düzenleme komutları.
- Onaylanmış sinyali executor kuyruğuna taşıma.

### Faz 4 - Executor ve Risk Kontrolleri
- Market/Limit emir açma.
- Kaldıraç ve margin modu ayarlama.
- TP/SL ve çoklu TP emirleri.
- Pozisyon başına risk limiti ve bakiye korumaları.

### Faz 5 - Test, Hardening, Deployment
- Unit + entegrasyon testleri.
- Retry, timeout, idempotency ve hata senaryoları.
- Paper trading modu ve küçük bakiye canlı test.
- VPS servisleştirme (`systemd` veya Docker).

## 6. Scope Dışı (Bu Sprint)
- Tam otomatik onaysız işlem.
- Çoklu borsa orkestrasyonu.
- Web dashboard.

## 7. Başlangıç Komutları
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python -m src.main
```

## 8. Takip Dosyaları
- Görevler: `TASKS.md`
- Agent atamaları: `AGENTS.md`
- Süreç logu: `LOG.md`
- Değişiklik kaydı: `CHANGELOG.md`
- Öğrenimler: `MEMORY.md`
