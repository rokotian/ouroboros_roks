"""Weekly RPL publication scheduler.

Schedules two recurring tasks for the owner chat (Moscow time):
- Friday 19:00-20:59 -> publish next RPL round fixtures.
- Sunday 20:00-21:59 -> publish current RPL standings table.

Window is 2 hours wide so that a brief Colab restart doesn't miss the slot.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict

from supervisor.queue import PENDING, RUNNING, enqueue_task, persist_queue_snapshot
from supervisor.state import load_state, save_state
from supervisor.telegram import send_with_budget

log = logging.getLogger(__name__)

MSK_TZ = datetime.timezone(datetime.timedelta(hours=3))
RPL_FIXTURES_SLOT = "rpl_fixtures_friday_1900"
RPL_STANDINGS_SLOT = "rpl_standings_sunday_2000"
RPL_PRIMARY_MATCHES_URL = "https://premierliga.ru/matches/"
RPL_PRIMARY_TABLE_URL = "https://premierliga.ru/tournament-table/"
RPL_FALLBACK_URL = "https://www.championat.com/football/_russiapl.html"


def _week_slot_id(now_msk: datetime.datetime, slot_name: str) -> str:
    iso_year, iso_week, _ = now_msk.isocalendar()
    return f"{slot_name}:{iso_year}-W{iso_week:02d}"


def _has_pending_or_running(slot_id: str) -> bool:
    for task in PENDING:
        if str(task.get("schedule_slot_id") or "") == slot_id:
            return True
    for meta in RUNNING.values():
        task = meta.get("task") if isinstance(meta, dict) else None
        if isinstance(task, dict) and str(task.get("schedule_slot_id") or "") == slot_id:
            return True
    return False


def _enqueue_weekly_publication(owner_chat_id: int, slot_id: str, text: str, announce: str) -> None:
    if _has_pending_or_running(slot_id):
        return

    task_id = uuid.uuid4().hex[:8]
    enqueue_task(
        {
            "id": task_id,
            "type": "task",
            "chat_id": int(owner_chat_id),
            "text": text,
            "schedule_slot_id": slot_id,
            "source": "rpl_weekly_scheduler",
        }
    )
    persist_queue_snapshot(reason=f"{slot_id}_enqueued")
    send_with_budget(int(owner_chat_id), announce.format(task_id=task_id))


def tick_rpl_scheduler() -> None:
    """Check time slots and enqueue weekly RPL publication tasks."""
    st: Dict[str, Any] = load_state()
    owner_chat_id = int(st.get("owner_chat_id") or 0)
    if not owner_chat_id:
        return

    now_msk = datetime.datetime.now(tz=MSK_TZ)

    # Friday 19:00-20:59 (Moscow): next round fixtures.
    # Window is 2 hours wide — a brief Colab restart won't miss the slot.
    if now_msk.weekday() == 4 and 19 <= now_msk.hour < 21:
        slot_id = _week_slot_id(now_msk, RPL_FIXTURES_SLOT)
        last_slot = str(st.get("rpl_last_fixtures_slot_id") or "")
        if last_slot != slot_id:
            _enqueue_weekly_publication(
                owner_chat_id=owner_chat_id,
                slot_id=slot_id,
                text=(
                    "Подготовь и опубликуй расписание следующего тура Российской Премьер-Лиги. "
                    "Используй инструмент get_rpl_fixtures чтобы получить актуальное расписание. "
                    "Отправь сообщение с полным списком пар, датой и временем каждого матча "
                    "(московское время) и отметь матч Локомотива если он есть."
                ),
                announce="📅 Запланирована публикация расписания очередного тура РПЛ (task {task_id}).",
            )
            st["rpl_last_fixtures_slot_id"] = slot_id
            save_state(st)
            log.info("RPL fixtures publication scheduled for slot %s", slot_id)

    # Sunday 20:00-21:59 (Moscow): standings table.
    # Window is 2 hours wide — a brief Colab restart won't miss the slot.
    if now_msk.weekday() == 6 and 20 <= now_msk.hour < 22:
        slot_id = _week_slot_id(now_msk, RPL_STANDINGS_SLOT)
        last_slot = str(st.get("rpl_last_standings_slot_id") or "")
        if last_slot != slot_id:
            _enqueue_weekly_publication(
                owner_chat_id=owner_chat_id,
                slot_id=slot_id,
                text=(
                    "Подготовь и опубликуй актуальную турнирную таблицу Российской Премьер-Лиги. "
                    "Используй инструмент get_rpl_standings чтобы получить таблицу. "
                    "Отправь компактную таблицу: место, команда, игры, очки."
                ),
                announce="📊 Запланирована публикация турнирной таблицы РПЛ (task {task_id}).",
            )
            st["rpl_last_standings_slot_id"] = slot_id
            save_state(st)
            log.info("RPL standings publication scheduled for slot %s", slot_id)
