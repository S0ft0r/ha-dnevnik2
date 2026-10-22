"""Константы интеграции Электронный дневник СПб (dnevnik2.petersburgedu.ru)."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "dnevnik2"
BASE_URL: Final = "https://dnevnik2.petersburgedu.ru"
LOGIN_PAGE_URL: Final = "https://dnevnik2.petersburgedu.ru/login"
REFERER_URL: Final = "https://dnevnik2.petersburgedu.ru/schedule"

SESSION_COOKIE: Final = "X-JWT-Token"
USER_AGENT: Final = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Проверенные эндпоинты API
EP_ESIA_LOGIN_URL: Final = "/api/journal/esa/login-url"
EP_CURRENT_USER: Final = "/api/journal/user/get-current-user"
EP_RELATED_CHILDREN: Final = "/api/journal/person/related-child-list"
EP_CLAIM_LIST: Final = "/api/journal/claim/list"
EP_GROUP_PERIODS: Final = "/api/group/group/get-list-period"
EP_STUDIED_SUBJECTS: Final = "/api/journal/subject/list-studied"
EP_TEACHERS_LIST: Final = "/api/journal/teacher/list"
EP_ESTIMATE_TABLE: Final = "/api/journal/estimate/table"
EP_LESSONS_LIST: Final = "/api/journal/lesson/list-by-education"
EP_SCHEDULE_LIST: Final = "/api/journal/schedule/list-by-education"
EP_ACS_LIST: Final = "/api/journal/acs/list"
EP_MEAL_ACCOUNTS: Final = "/fps/api/netrika/mobile/v1/accounts/"
EP_MEAL_FPS_LIST: Final = "/api/journal/fps/list"

# Специальные коды посещаемости в таблице оценок (/api/journal/estimate/table)
ABSENCE_CODE: Final = "30000"
LATE_CODE: Final = "30001"

# События шины Home Assistant (hass.bus)
EVENT_NEW_GRADE: Final = "dnevnik2_new_grade"
EVENT_TURNSTILE: Final = "dnevnik2_turnstile"

# Ключи конфигурации (ConfigEntry.data и ConfigEntry.options)
CONF_TOKEN: Final = "token"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_HOMEWORK_MODE: Final = "homework_mode"
CONF_LESSONS_MODE: Final = "lessons_mode"

OUTPUT_MODE_SENSOR: Final = "sensor"
OUTPUT_MODE_TODO: Final = "todo"
OUTPUT_MODES: Final = [OUTPUT_MODE_TODO, OUTPUT_MODE_SENSOR]

DEFAULT_HOMEWORK_MODE: Final = OUTPUT_MODE_TODO
DEFAULT_LESSONS_MODE: Final = OUTPUT_MODE_SENSOR

DEFAULT_SCAN_INTERVAL_MIN: Final = 15
MIN_SCAN_INTERVAL_MIN: Final = 5
MAX_SCAN_INTERVAL_MIN: Final = 180
KEEP_ALIVE_INTERVAL_MIN: Final = 4

PAGE_LIMIT: Final = "500"
MARKS_LIMIT: Final = "1000"
REQUEST_TIMEOUT_SEC: Final = 20
