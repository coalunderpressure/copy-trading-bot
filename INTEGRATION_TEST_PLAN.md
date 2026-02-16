# Integration Test Plan

## Scope
Modüller: `listener`, `parser`, `approvals`, `executor`, `main`.

## Environment
- Python 3.11
- Test exchange sandbox credentials
- Dedicated Telegram test channel + approval chat
- `.env.test` with isolated secrets

## Critical Flows
1. Channel message ingestion -> parser success -> approval reject.
2. Channel message ingestion -> parser success -> approval edit -> executor place orders.
3. Channel message ingestion -> parser fail -> no approval prompt.
4. Approval timeout -> no execution.
5. Executor failure on TP/SL but entry success -> action log contains partial failure.

## Scenario Matrix
1. Happy path limit order:
- Input: Valid JSON signal with `order_type=limit`.
- Expected: Entry + TP/SL attempts are logged, status `ok` or partial action errors.

2. Happy path market order:
- Input: Valid JSON signal with `order_type=market`.
- Expected: Entry sent as market, TP/SL attempts continue.

3. Invalid signal schema:
- Input: Missing `stop_loss` or invalid `direction`.
- Expected: Parser returns `None`, approval service not invoked.

4. Approval edit:
- Input: `/edit <id> leverage=10 margin_mode=cross`.
- Expected: Edited signal used by executor.

5. Approval timeout:
- Input: No command in timeout window.
- Expected: Decision rejected with `timeout` tag.

## Fixtures and Mocks
- Mock Telethon client methods: `send_message`, event registration.
- Mock CCXT exchange methods: `load_markets`, `create_order`, `set_leverage`, `set_margin_mode`.
- Use deterministic fake ticker response for amount calculation.

## Exit Criteria
- All critical flows executed at least once in CI.
- No unhandled exception in listener->parser->approval->executor chain.
- Timeout and invalid input paths verified.
