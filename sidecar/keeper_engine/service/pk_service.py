"""PK 擂台状态机——用户两两对决，每一步持久化、可中途退出后恢复。

PK 池 = 该组「通过(kept) ∪ 救回(rescued)」的照片（由前端组装后传入）。PK 的产物是把每张
最终判为 kept / discarded，写回 ProjectPhoto.selection。四种结局（见 enumeration.PkOutcome）：

  - 二选一（pick_left/right）：胜者继续守擂，从 pool 取 1 张新图作下一对；败者淘汰。
  - 都选（keep_both）：两张都通过、收入 kept_aside 不再参与；下一对从 pool 取 2 张新图。
  - 都不选（drop_both）：两张都淘汰；下一对从 pool 取 2 张新图。

终止：pool 凑不出下一对且无守擂残留。守擂到最后剩 1 张 → 该张通过。都选/都不选后 pool 只剩
1 张 → 这张无对手、按通过收下。结束时一次性把结果写回 selection（PK 过程中只动 PkState，
不碰 selection；恢复只看 PkState——对应「pk 完后才更新通过/未通过区域」）。

state_json 结构：
  {"pool": [...], "current": [a, b]|null, "kept_aside": [...],
   "original_pool": [...], "history": [...prev states...], "done": bool}
"""

from __future__ import annotations

from ..enumeration.pk_outcome import PkOutcome
from ..enumeration.selection import Selection
from ..mapper.pk_state_mapper import PkStateMapper
from ..mapper.project_photo_mapper import ProjectPhotoMapper
from ..response.project_response import PkView


class PkService:
    """PK 进度的起、选、撤销；终止时把去留写回 ProjectPhoto。"""

    def __init__(self, photo_mapper: ProjectPhotoMapper, pk_mapper: PkStateMapper) -> None:
        self._photos = photo_mapper
        self._pk = pk_mapper

    def get_view(self, project_id: int, group_key: str) -> PkView | None:
        """返回当前 PK 视图；无进度返回 None。"""
        row = self._pk.get(project_id, group_key)
        return self._view(row.state_json) if row else None

    def start(self, project_id: int, group_key: str, pool: list[str], restart: bool) -> PkView:
        """开始或恢复 PK。有未完成进度且非 restart → 恢复；否则按 pool 重新开局。"""
        existing = self._pk.get(project_id, group_key)
        if existing and not existing.state_json.get("done") and not restart:
            return self._view(existing.state_json)

        queue = list(pool)
        state = {
            "pool": queue,
            "current": None,
            "kept_aside": [],
            "original_pool": list(pool),
            "history": [],
            "done": False,
        }
        self._setup_pair(state)  # 取首对；不足则直接收口
        if state["done"]:  # 池 0/1 张：开局即结束，立刻写回去留
            self._finalize(project_id, group_key, state)
        self._save(project_id, group_key, state)
        return self._view(state)

    def choose(self, project_id: int, group_key: str, outcome: PkOutcome) -> PkView:
        """对当前一对落一次选择，推进到下一对或结束。"""
        row = self._pk.get(project_id, group_key)
        if row is None:
            raise ValueError("PK 尚未开始")
        state = row.state_json
        if state.get("done") or not state.get("current"):
            return self._view(state)

        self._push_history(state)
        a, b = state["current"]

        if outcome == PkOutcome.PICK_LEFT:
            self._advance_winner(state, winner=a, loser=b)
        elif outcome == PkOutcome.PICK_RIGHT:
            self._advance_winner(state, winner=b, loser=a)
        elif outcome == PkOutcome.KEEP_BOTH:
            state["kept_aside"].extend([a, b])
            self._setup_pair(state)
        elif outcome == PkOutcome.DROP_BOTH:
            self._setup_pair(state)

        if state["done"]:
            self._finalize(project_id, group_key, state)
        self._save(project_id, group_key, state)
        return self._view(state)

    def undo(self, project_id: int, group_key: str) -> PkView:
        """撤销上一步（PK 进行中可用；DB 未写入故纯状态回滚）。"""
        row = self._pk.get(project_id, group_key)
        if row is None:
            raise ValueError("PK 尚未开始")
        state = row.state_json
        history = state.get("history") or []
        if not history:
            return self._view(state)
        prev = history.pop()
        prev["history"] = history
        self._save(project_id, group_key, prev)
        return self._view(prev)

    # ── 内部推进逻辑 ────────────────────────────────────────────────────────

    def _advance_winner(self, state: dict, winner: str, loser: str) -> None:
        """二选一：胜者守擂取下一张挑战者；pool 空则胜者通过、收口。"""
        if state["pool"]:
            state["current"] = [winner, state["pool"].pop(0)]
        else:
            state["kept_aside"].append(winner)
            state["current"] = None
            state["done"] = True

    def _setup_pair(self, state: dict) -> None:
        """从 pool 取两张作下一对；只剩 1 张则它无对手、按通过收下并收口；0 张则收口。"""
        pool = state["pool"]
        if len(pool) >= 2:
            state["current"] = [pool.pop(0), pool.pop(0)]
        elif len(pool) == 1:
            state["kept_aside"].append(pool.pop(0))
            state["current"] = None
            state["done"] = True
        else:
            state["current"] = None
            state["done"] = True

    def _finalize(self, project_id: int, group_key: str, state: dict) -> None:
        """PK 结束：kept_aside → kept，原 pool 里其余 → discarded，写回 selection。"""
        kept = set(state.get("kept_aside") or [])
        photos = self._photos.by_group(project_id, group_key)
        changed = []
        for p in photos:
            if p.workspace_path in state.get("original_pool", []):
                p.selection = Selection.KEPT.value if p.workspace_path in kept else Selection.DISCARDED.value
                changed.append(p)
        if changed:
            self._photos.update_many(changed)

    @staticmethod
    def _push_history(state: dict) -> None:
        """把当前状态（不含 history 自身）压入历史，供撤销。"""
        snapshot = {k: v for k, v in state.items() if k != "history"}
        # 深拷贝可变字段，避免后续 mutate 污染历史
        snapshot["pool"] = list(snapshot.get("pool") or [])
        snapshot["kept_aside"] = list(snapshot.get("kept_aside") or [])
        snapshot["current"] = list(snapshot["current"]) if snapshot.get("current") else None
        state.setdefault("history", []).append(snapshot)

    def _save(self, project_id: int, group_key: str, state: dict) -> None:
        self._pk.upsert(project_id, group_key, state)

    @staticmethod
    def _view(state: dict) -> PkView:
        return PkView(
            current=state.get("current"),
            pool_remaining=len(state.get("pool") or []),
            kept_aside=list(state.get("kept_aside") or []),
            done=bool(state.get("done")),
            can_undo=bool(state.get("history")),
        )
