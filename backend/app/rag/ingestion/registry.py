"""入库登记表：记录每个源文件的处理状态，避免重复入库、支持变更 reindex。

存为 knowledge_base/index/registry.json，key 是源文件路径（或文件名）。
字段：source_file / checksum / case_id / status / indexed_at / error_message。

判重逻辑：同一 source_file + 相同 checksum 且 status=indexed -> 跳过；
checksum 变化 -> 允许 reindex（should_ingest 返回 True）。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
REGISTRY_PATH = _KB_DIR / "index" / "registry.json"

STATUS_PENDING = "pending"
STATUS_INDEXED = "indexed"
STATUS_FAILED = "failed"


@dataclass
class RegistryEntry:
    source_file: str
    checksum: str | None = None
    case_id: str | None = None
    status: str = STATUS_PENDING
    indexed_at: str | None = None
    error_message: str | None = None


class Registry:
    def __init__(self, path: Path | str = REGISTRY_PATH) -> None:
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _key(source_file: str) -> str:
        return str(source_file)

    def get(self, source_file: str) -> RegistryEntry | None:
        raw = self._data.get(self._key(source_file))
        return RegistryEntry(**raw) if raw else None

    def should_ingest(self, source_file: str, checksum: str | None) -> bool:
        """需要入库返回 True。已成功入库且 checksum 未变 -> False（跳过）。"""
        entry = self.get(source_file)
        if entry is None:
            return True
        if entry.status != STATUS_INDEXED:
            return True  # 上次失败/未完成，重试
        # 已入库：checksum 变了才 reindex
        if checksum is not None and entry.checksum != checksum:
            return True
        return False

    def mark(
        self,
        source_file: str,
        *,
        status: str,
        checksum: str | None = None,
        case_id: str | None = None,
        error_message: str | None = None,
        indexed_at: str | None = None,
    ) -> RegistryEntry:
        entry = RegistryEntry(
            source_file=str(source_file),
            checksum=checksum,
            case_id=case_id,
            status=status,
            indexed_at=indexed_at,
            error_message=error_message,
        )
        self._data[self._key(source_file)] = asdict(entry)
        self._save()
        return entry

    def all_entries(self) -> list[RegistryEntry]:
        return [RegistryEntry(**v) for v in self._data.values()]
