# Runbook

## 1. Local Setup
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## 2. Safe Smoke (No Telegram Needed)
```powershell
.\.venv\Scripts\python scripts/dry_run_smoke.py
```
Expected: output contains `status: ok` and `step: dry_run`.

## 3. Telegram Dry-Run UAT
1. Fill `.env`:
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID` (ör. `-100...` veya `channel_username`)
- `APPROVAL_CHAT_ID` (botun mesaj atacağı chat/user id, ör. `123456789`)
- Botu Telegram'da açıp `/start` gönder (aksi halde bot sana mesaj gönderemez)
- `DRY_RUN=true`
- `EXCHANGE_TESTNET=true`
- `ALLOWED_PAIRS=BTC/USDT,ETH/USDT`

Hybrid not:
- Kanal dinleme Telethon user session ile yapılır (kanala üye olan senin kullanıcı hesabın).
- BotFather botunun kanala ekli olması gerekmez; bot sadece onay/sonuç mesajlaşması için kullanılır.

2. Start bot:
```powershell
.\.venv\Scripts\python -m src.main
```

3. Send valid JSON signal to test channel:
```json
{"pair":"BTC/USDT","direction":"LONG","entry_zone":[50000,50100],"targets":[50500,51000],"stop_loss":49500,"leverage":5,"margin_mode":"isolated","order_type":"limit","confidence":0.8}
```

4. Bot chatinde onay ver:
- Tercih edilen: inline butonlar (`Approve`, `Reject`, `Market`, `5x`, `10x`)
- Fallback komutlar:
`/approve <message_id>`
`/reject <message_id> reason`
`/edit <message_id> leverage=10 margin_mode=cross order_type=market stop_loss=49400`

5. Verify:
- `logs/raw_messages.jsonl` updated.
- Approval result message received.
- Execution result message shows dry-run action.

## 4. Exit Criteria
- One approved signal produces dry-run execution result.
- One rejected signal produces reject message.
- One edited signal shows modified fields in execution summary.
