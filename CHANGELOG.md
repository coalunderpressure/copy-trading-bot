# Changelog

## 2026-02-15
- Plan dokümanları konsolide edildi: `trading_bot_plan.md` master plan olarak güncellendi.
- `telegram-trading-bot-implementation-roadmap.md` birleşim notu dosyasına dönüştürüldü.
- Süreç dosyaları eklendi: `AGENTS.md`, `TASKS.md`, `LOG.md`, `MEMORY.md`.
- Proje iskeleti eklendi: `requirements.txt`, `.env.example`, `src/*`.
- Telethon listener event hattı ve ham mesaj loglama iskeleti eklendi.
- Parser için strict JSON schema doğrulaması eklendi (`src/parser.py`, `jsonschema` bağımlılığı).
- Global çalışma protokolü güncellendi: `C:\Users\ceyca\.codex\CODEX.md` ve `C:\Users\ceyca\.codex\MEMORY.md`.
- Userbot onay komutları eklendi: `/approve`, `/reject`, `/edit` (`src/approvals.py`, `src/main.py`).
- Executor akışı eklendi: market/limit entry, TP/SL girişimleri, action logları (`src/executor.py`).
- Güvenli varsayılanlar eklendi: `DRY_RUN`, `MAX_LEVERAGE`, `ALLOWED_PAIRS` (`src/config.py`, `.env.example`).
- Test artefaktları eklendi: `INTEGRATION_TEST_PLAN.md`, `tests/test_parser.py`, `tests/test_approvals.py`.
- Güvenlik tarama raporu eklendi: `SECURITY_REVIEW.md`.
- Lokal sanal ortam oluşturuldu ve bağımlılıklar yüklendi (`.venv`, `pip install -r requirements.txt`).
- Testler çalıştırıldı: `.venv\\Scripts\\python -m pytest -q` sonucu `4 passed`.
- `DRY_RUN` executor doğrulaması örnek sinyal ile başarıyla çalıştırıldı.
- Otomatik smoke script eklendi ve doğrulandı: `scripts/dry_run_smoke.py`.
- Telegram dry-run UAT adımları dokümante edildi: `RUNBOOK.md`.
