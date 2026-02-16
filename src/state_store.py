import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.listener import IncomingMessage
from src.models import ApprovalDecision, TradeSignal


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SignalStateStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path.as_posix())
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def has_message(self, message_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM signal_events WHERE source_message_id = ? LIMIT 1",
            (message_id,),
        ).fetchone()
        return row is not None

    def record_incoming(self, msg: IncomingMessage) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO signal_events (
                source_message_id,
                source_chat_id,
                raw_text,
                media_path,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.message_id,
                msg.chat_id,
                msg.text,
                msg.media_path,
                "received",
                now,
                now,
            ),
        )
        self.conn.commit()

    def mark_parse_failed(self, message_id: int, reason: str) -> None:
        self._update(message_id, status="parse_failed", parse_error=reason)

    def mark_parsed(self, signal: TradeSignal) -> None:
        self._update(
            signal.source_message_id or 0,
            status="parsed",
            parsed_signal_json=json.dumps(asdict(signal), ensure_ascii=True),
        )

    def mark_rejected(self, message_id: int, decision: ApprovalDecision) -> None:
        self._update(
            message_id,
            status="rejected",
            approval_reason=decision.reason,
            decision_tags_json=json.dumps(decision.tags, ensure_ascii=True),
        )

    def mark_approved(self, message_id: int, decision: ApprovalDecision) -> None:
        edited = decision.edited_signal
        self._update(
            message_id,
            status="approved",
            approval_reason=decision.reason,
            decision_tags_json=json.dumps(decision.tags, ensure_ascii=True),
            approved_signal_json=(
                json.dumps(asdict(edited), ensure_ascii=True) if edited is not None else None
            ),
        )

    def mark_executed(self, message_id: int, execution_result: Dict[str, Any]) -> None:
        status = "executed" if execution_result.get("status") == "ok" else "execution_error"
        self._update(
            message_id,
            status=status,
            execution_result_json=json.dumps(execution_result, ensure_ascii=True),
        )

    def get_status(self, message_id: int) -> Optional[str]:
        row = self.conn.execute(
            "SELECT status FROM signal_events WHERE source_message_id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def _update(
        self,
        message_id: int,
        *,
        status: Optional[str] = None,
        parse_error: Optional[str] = None,
        parsed_signal_json: Optional[str] = None,
        approval_reason: Optional[str] = None,
        decision_tags_json: Optional[str] = None,
        approved_signal_json: Optional[str] = None,
        execution_result_json: Optional[str] = None,
    ) -> None:
        current = self.conn.execute(
            """
            SELECT
                parse_error,
                parsed_signal_json,
                approval_reason,
                decision_tags_json,
                approved_signal_json,
                execution_result_json
            FROM signal_events
            WHERE source_message_id = ?
            """,
            (message_id,),
        ).fetchone()
        if current is None:
            return

        next_parse_error = parse_error if parse_error is not None else current[0]
        next_parsed_signal_json = (
            parsed_signal_json if parsed_signal_json is not None else current[1]
        )
        next_approval_reason = approval_reason if approval_reason is not None else current[2]
        next_decision_tags_json = (
            decision_tags_json if decision_tags_json is not None else current[3]
        )
        next_approved_signal_json = (
            approved_signal_json if approved_signal_json is not None else current[4]
        )
        next_execution_result_json = (
            execution_result_json if execution_result_json is not None else current[5]
        )

        self.conn.execute(
            """
            UPDATE signal_events
            SET
                status = COALESCE(?, status),
                parse_error = ?,
                parsed_signal_json = ?,
                approval_reason = ?,
                decision_tags_json = ?,
                approved_signal_json = ?,
                execution_result_json = ?,
                updated_at = ?
            WHERE source_message_id = ?
            """,
            (
                status,
                next_parse_error,
                next_parsed_signal_json,
                next_approval_reason,
                next_decision_tags_json,
                next_approved_signal_json,
                next_execution_result_json,
                _utc_now(),
                message_id,
            ),
        )
        self.conn.commit()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_message_id INTEGER NOT NULL UNIQUE,
                source_chat_id INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                media_path TEXT,
                status TEXT NOT NULL,
                parse_error TEXT,
                parsed_signal_json TEXT,
                approval_reason TEXT,
                decision_tags_json TEXT,
                approved_signal_json TEXT,
                execution_result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()
