"""UI labels for the generated page."""
from __future__ import annotations

import re

_EN = {
    "toc": "Contents",
    "hotspots": "Hot spots",
    "status_ok": "OK",
    "status_change": "Needs change",
    "status_discuss": "Discuss",
    "comment_placeholder": "Comment",
    "author_placeholder": "Name (optional)",
    "add_comment": "Add",
    "close": "Close",
    "verdict": "Verdict",
    "vote_for": "For",
    "vote_against": "Against",
    "names_placeholder": "Names (optional)",
    "questions": "Open questions",
    "decision": "Decision",
    "actions": "Action items",
    "action_text": "Action",
    "action_owner": "Owner",
    "add_action": "Add action",
    "presenter": "Presenter mode",
    "next": "Next",
    "export_md": "Export Markdown",
    "save_json": "Save JSON",
    "load_json": "Load JSON",
    "reset": "Reset",
    "reset_confirm": "Press again to reset",
    "theme": "Theme",
}
_RU = {
    "toc": "Содержание",
    "hotspots": "Горячие точки",
    "status_ok": "Ок",
    "status_change": "Нужно изменить",
    "status_discuss": "Обсудить",
    "comment_placeholder": "Комментарий",
    "author_placeholder": "Имя (необязательно)",
    "add_comment": "Добавить",
    "close": "Закрыть",
    "verdict": "Вердикт",
    "vote_for": "За",
    "vote_against": "Против",
    "names_placeholder": "Имена (необязательно)",
    "questions": "Открытые вопросы",
    "decision": "Решение",
    "actions": "Задачи",
    "action_text": "Задача",
    "action_owner": "Ответственный",
    "add_action": "Добавить задачу",
    "presenter": "Режим презентации",
    "next": "Далее",
    "export_md": "Экспорт Markdown",
    "save_json": "Сохранить JSON",
    "load_json": "Загрузить JSON",
    "reset": "Сбросить",
    "reset_confirm": "Нажмите ещё раз для сброса",
    "theme": "Тема",
}
LABELS: dict[str, dict[str, str]] = {"ru": _RU, "en": _EN}
UI_CHOICES = ("auto", "ru", "en")

_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_ui(text: str) -> str:
    """`ru` when Cyrillic letters are the majority of all letters, else `en`."""
    cyr = len(_CYRILLIC.findall(text))
    lat = len(_LATIN.findall(text))
    return "ru" if cyr > lat else "en"
