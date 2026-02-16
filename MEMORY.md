# Local Memory

## Guardrails
- Her yeni taskta önce zorluk (`kolay/orta/zor`) ve efor (`low/medium/high`) belirt.
- Task tamamlandığında `TASKS.md`, `LOG.md` ve `CHANGELOG.md` birlikte güncellensin.
- Plan değişiklikleri master kaynak olarak `trading_bot_plan.md` üzerinden yönetilsin.

## Lessons Learned
- Markdown dosyaları okunurken encoding bozulursa `UTF8` ile yeniden okunmalı.
- `pytest` çalıştırmadan önce `requirements.txt` bağımlılıkları kurulu olmalı; aksi halde koleksiyon hataları (missing module) yanlış negatif üretir.
- PowerShell içinde async çok satırlı Python denemeleri için `python -c` yerine herestring ile `python -` kullanılmalı; sözdizimi hatası riskini düşürür.
- `scripts/` altından çalışan Python dosyalarında `src` importları için proje kökü `sys.path` bootstrap'i eklenmeli veya `python -m` yaklaşımı kullanılmalı.
