# Security Quick Scan

## Findings
1. High - Unsafe default could place live orders if misconfigured.
- Fix: Added `DRY_RUN=true` as default and enforced preview-only execution in executor.

2. High - No policy guard for unauthorized pairs or excessive leverage.
- Fix: Added `ALLOWED_PAIRS` policy and `MAX_LEVERAGE` enforcement.

3. Medium - Invalid stop-loss geometry could create dangerous orders.
- Fix: Added signal validation to enforce SL position relative to entry and direction.

4. Medium - Manual edit command could set unbounded leverage.
- Fix: Added leverage clamp in approval edit flow.

## Hardening Checklist
- [x] Safe defaults in `.env.example`
- [x] Risk policy validation in executor
- [x] Approval edit constraints
- [ ] Add secrets manager for production (follow-up)
- [ ] Add signed command auth for approval chat (follow-up)
