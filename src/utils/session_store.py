import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config import settings
from src.models import ChatHistory, PaperContext


@dataclass
class SessionSnapshot:
    session_id: str
    topic: str
    current_phase: str
    current_section_index: int
    paper_context: PaperContext
    chat_history: ChatHistory
    recent_success_turn: int
    recent_error: str | None
    last_completed_pdf: str | None = None


class SessionStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.DATA_DIR / "sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session_id(self) -> str:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid4().hex[:8]
        session_dir = self.session_dir(session_id)
        (session_dir / "turns").mkdir(parents=True, exist_ok=True)
        (session_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        return session_id

    def session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def load_snapshot(self, session_id: str) -> SessionSnapshot:
        session_file = self.session_dir(session_id) / "session.json"
        if not session_file.exists():
            raise FileNotFoundError(f"未找到可恢复会话: {session_id}")
        data = json.loads(session_file.read_text(encoding="utf-8"))
        recent_success_turn = data.get("recent_success_turn")
        if recent_success_turn is None:
            recent_success_turn = self._recover_recent_success_turn(session_id)
        elif not isinstance(recent_success_turn, int) or recent_success_turn < 0:
            recent_success_turn = 0

        return SessionSnapshot(
            session_id=data["session_id"],
            topic=data.get("topic", ""),
            current_phase=data.get("current_phase", "PLANNING"),
            current_section_index=data.get("current_section_index", 0),
            paper_context=PaperContext.model_validate(data.get("paper_context", {})),
            chat_history=ChatHistory.model_validate(
                data.get("chat_history", {"messages": []})
            ),
            recent_success_turn=recent_success_turn,
            recent_error=data.get("recent_error"),
            last_completed_pdf=data.get("last_completed_pdf"),
        )

    def _recover_recent_success_turn(self, session_id: str) -> int:
        turns_dir = self.session_dir(session_id) / "turns"
        if not turns_dir.exists():
            return 0

        recent_success_turn = 0
        for turn_file in sorted(turns_dir.glob("*.json")):
            try:
                turn_data = json.loads(turn_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if turn_data.get("checkpoint_type") != "success":
                continue
            value = turn_data.get("recent_success_turn", 0)
            if isinstance(value, int) and value > recent_success_turn:
                recent_success_turn = value
        return recent_success_turn

    def save_snapshot(
        self,
        *,
        session_id: str,
        topic: str,
        current_phase: str,
        current_section_index: int,
        paper_context: PaperContext,
        chat_history: ChatHistory,
        recent_success_turn: int,
        recent_error: str | None,
        checkpoint_type: str,
        label: str,
        last_completed_pdf: str | None = None,
        output_preview: str | None = None,
    ) -> None:
        session_dir = self.session_dir(session_id)
        turns_dir = session_dir / "turns"
        artifacts_dir = session_dir / "artifacts"
        turns_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat()
        session_payload: dict[str, Any] = {
            "session_id": session_id,
            "topic": topic,
            "current_phase": current_phase,
            "current_section_index": current_section_index,
            "paper_context": paper_context.model_dump(mode="json"),
            "chat_history": chat_history.model_dump(mode="json"),
            "recent_success_turn": recent_success_turn,
            "recent_error": recent_error,
            "last_completed_pdf": last_completed_pdf,
            "checkpoint_type": checkpoint_type,
            "label": label,
            "updated_at": now,
            "completed": paper_context.status.name == "FINISHED",
        }
        (session_dir / "session.json").write_text(
            json.dumps(session_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        turn_index = len(list(turns_dir.glob("*.json"))) + 1
        turn_payload = {
            **session_payload,
            "output_preview": (output_preview or "")[:3000],
            "created_at": now,
        }
        (turns_dir / f"{turn_index:04d}_{checkpoint_type}_{label}.json").write_text(
            json.dumps(turn_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_recent_recoverable(self, limit: int = 5) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for session_file in self.base_dir.glob("*/session.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("completed"):
                continue
            records.append(data)
        records.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return records[:limit]
