"""Асинхронный HTTP-клиент для API Электронного дневника СПб (dnevnik2.petersburgedu.ru)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from http.cookies import SimpleCookie
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import (
    BASE_URL,
    EP_ACS_LIST,
    EP_CLAIM_LIST,
    EP_CURRENT_USER,
    EP_ESIA_LOGIN_URL,
    EP_ESTIMATE_TABLE,
    EP_GROUP_PERIODS,
    EP_LESSONS_LIST,
    EP_MEAL_ACCOUNTS,
    EP_MEAL_FPS_LIST,
    EP_RELATED_CHILDREN,
    EP_SCHEDULE_LIST,
    EP_STUDIED_SUBJECTS,
    EP_TEACHERS_LIST,
    MARKS_LIMIT,
    PAGE_LIMIT,
    REFERER_URL,
    REQUEST_TIMEOUT_SEC,
    SESSION_COOKIE,
    USER_AGENT,
)

_JWT_RE = re.compile(r"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
_GROUP_SPACE_RE = re.compile(r"(\d+)\s+([^\W\d_])")
_GLOLIME_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def normalize_group_name(raw: str | None) -> str:
    """Удаляет пробел между номером класса и литерой (например, '11 б' -> '11б')."""
    if not raw:
        return ""
    cleaned = " ".join(str(raw).strip().split())
    return _GROUP_SPACE_RE.sub(r"\1\2", cleaned)


class Dnevnik2Error(Exception):
    """Базовое исключение клиента дневника."""


class Dnevnik2AuthError(Dnevnik2Error):
    """Сессия истекла или токен недействителен."""


class Dnevnik2ConnectionError(Dnevnik2Error):
    """Ошибка соединения или временный сбой сервера."""


def extract_jwt_token(raw_value: str | None) -> str | None:
    """Извлекает JWT-токен (eyJ...) из чистой строки, cookie или URL редиректа ЕСИА."""
    if not raw_value:
        return None
    cleaned = unquote(raw_value.strip().strip('"').strip("'"))
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        parsed = urlparse(cleaned)
        qs = parse_qs(parsed.query)
        for param in ("x-access-token", "token", "X-JWT-Token"):
            values = qs.get(param)
            if values and values[0].startswith("eyJ"):
                return values[0].strip()
    match = _JWT_RE.search(cleaned)
    if match:
        return match.group(1)
    return None


def format_date(dt: date) -> str:
    """Форматирует дату в DD.MM.YYYY для параметров API."""
    return dt.strftime("%d.%m.%Y")


def format_datetime_range(dt_from: date, dt_to: date) -> tuple[str, str]:
    """Форматирует диапазон дат с границами суток для /lesson/list-by-education."""
    return (
        f"{dt_from.strftime('%d.%m.%Y')} 00:00:00",
        f"{dt_to.strftime('%d.%m.%Y')} 23:59:59",
    )


def unwrap_scalar(value: Any) -> Any:
    """Разворачивает вложенный словарь одного уровня в скалярное значение."""
    if not isinstance(value, dict):
        return value
    for key in (
        "name",
        "title",
        "value",
        "text",
        "short_name",
        "fullname",
        "subject_name",
        "teacher_name",
        "office_name",
        "task_name",
        "id",
    ):
        inner = value.get(key)
        if isinstance(inner, bool):
            continue
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
        if isinstance(inner, (int, float)):
            return inner
    return None


class Dnevnik2Client:
    """Клиент работы с эндпоинтами dnevnik2.petersburgedu.ru и скользящим обновлением X-JWT-Token."""

    def __init__(
        self,
        session: ClientSession,
        token: str | None = None,
        on_token_refreshed: Callable[[str], None] | None = None,
    ) -> None:
        """Инициализация HTTP-клиента."""
        self._session = session
        self._token = extract_jwt_token(token) or (token or "").strip()
        self._on_token_refreshed = on_token_refreshed
        self._timeout = ClientTimeout(total=REQUEST_TIMEOUT_SEC)

    @property
    def token(self) -> str:
        """Текущий JWT-токен."""
        return self._token

    def set_token(self, token: str) -> None:
        """Обновляет токен в памяти клиента."""
        self._token = extract_jwt_token(token) or token.strip()

    def _headers(self, include_auth: bool = True) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": REFERER_URL,
        }
        if include_auth and self._token:
            headers[SESSION_COOKIE] = self._token
            headers["Cookie"] = f"{SESSION_COOKIE}={self._token}"
        return headers

    def _clear_session_cookie_jar(self) -> None:
        """Очищает общий CookieJar сессии aiohttp, чтобы не дублировать и не портить X-JWT-Token."""
        jar = getattr(self._session, "cookie_jar", None)
        if jar is not None and hasattr(jar, "clear_domain"):
            try:
                jar.clear_domain("dnevnik2.petersburgedu.ru")
                jar.clear_domain(".petersburgedu.ru")
            except Exception:
                pass

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | list[tuple[str, str]] | None = None,
        *,
        include_auth: bool = True,
    ) -> dict[str, Any]:
        """Выполняет GET-запрос к API дневника без конфликтов в общем CookieJar."""
        url = f"{BASE_URL}{path}"
        self._clear_session_cookie_jar()
        try:
            async with self._session.get(
                url,
                params=params,
                headers=self._headers(include_auth=include_auth),
                timeout=self._timeout,
                allow_redirects=False,
                ssl=False,
            ) as response:
                self._clear_session_cookie_jar()

                if response.status in (301, 302, 303, 307, 308, 401, 403):
                    raise Dnevnik2AuthError(f"HTTP {response.status}")

                if response.status >= 500:
                    raise Dnevnik2ConnectionError(f"HTTP {response.status}")

                try:
                    payload = await response.json(content_type=None)
                except Exception as err:
                    if response.status == 200:
                        raise Dnevnik2AuthError("Non-JSON 200 response") from err
                    raise Dnevnik2ConnectionError("Invalid response body") from err

                if response.status >= 400:
                    raise Dnevnik2ConnectionError(f"HTTP {response.status}")

                if not isinstance(payload, dict):
                    raise Dnevnik2ConnectionError("Unexpected JSON payload root")

                data = payload.get("data")
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {"items": data}
                return payload
        except Dnevnik2Error:
            raise
        except (ClientError, asyncio.TimeoutError, TimeoutError) as err:
            raise Dnevnik2ConnectionError(str(err)) from err

    @staticmethod
    def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
        items = data.get("items")
        if not isinstance(items, list):
            return []
        return [row for row in items if isinstance(row, dict)]

    # ------------------------------------------------------------------ #
    # Эндпоинты API                                                      #
    # ------------------------------------------------------------------ #

    async def async_get_esia_login_url(self) -> str | None:
        """Возвращает прямую ссылку входа через ЕСИА (/api/journal/esa/login-url)."""
        try:
            data = await self._request(EP_ESIA_LOGIN_URL, include_auth=False)
        except Dnevnik2Error:
            return None
        url = data.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
        return None

    async def async_get_current_user(self) -> dict[str, Any]:
        """Возвращает профиль текущего пользователя (/api/journal/user/get-current-user)."""
        return await self._request(EP_CURRENT_USER)

    async def async_get_children(self) -> list[dict[str, Any]]:
        """Список связанных детей и их обучений (/api/journal/person/related-child-list)."""
        data = await self._request(EP_RELATED_CHILDREN, params={"p_page": "1"})
        return self._items(data)

    async def async_validate_and_fetch_students(self) -> list[dict[str, Any]]:
        """Проверяет валидность X-JWT-Token и возвращает список профилей учащихся."""
        children_raw = await self.async_get_children()
        students: list[dict[str, Any]] = []
        seen_edu_ids: set[str] = set()

        for child in children_raw:
            surname = str(
                unwrap_scalar(child.get("surname"))
                or unwrap_scalar(child.get("last_name"))
                or unwrap_scalar(child.get("lastname"))
                or ""
            ).strip()
            firstname = str(
                unwrap_scalar(child.get("firstname"))
                or unwrap_scalar(child.get("first_name"))
                or unwrap_scalar(child.get("name"))
                or ""
            ).strip()
            middlename = str(
                unwrap_scalar(child.get("middlename"))
                or unwrap_scalar(child.get("middle_name"))
                or ""
            ).strip()
            full_name = " ".join(
                p for p in (surname, firstname, middlename) if p
            ).strip()
            first_name = firstname or (full_name.split()[0] if full_name else "")

            educations = child.get("educations")
            if isinstance(educations, list) and educations:
                for edu in educations:
                    if not isinstance(edu, dict):
                        continue
                    edu_id = str(
                        unwrap_scalar(edu.get("education_id"))
                        or unwrap_scalar(edu.get("id"))
                        or ""
                    ).strip()
                    if not edu_id or edu_id in seen_edu_ids:
                        continue
                    seen_edu_ids.add(edu_id)
                    group_name = normalize_group_name(
                        str(
                            unwrap_scalar(edu.get("group_name"))
                            or unwrap_scalar(edu.get("class_name"))
                            or unwrap_scalar(edu.get("classname"))
                            or ""
                        )
                    )
                    students.append(
                        {
                            "education_id": edu_id,
                            "first_name": first_name or edu_id,
                            "full_name": full_name or first_name or edu_id,
                            "group_name": group_name,
                        }
                    )
            else:
                edu_id = str(
                    unwrap_scalar(child.get("education_id"))
                    or unwrap_scalar(child.get("id"))
                    or ""
                ).strip()
                if edu_id and edu_id not in seen_edu_ids:
                    seen_edu_ids.add(edu_id)
                    group_name = normalize_group_name(
                        str(
                            unwrap_scalar(child.get("group_name"))
                            or unwrap_scalar(child.get("class_name"))
                            or ""
                        )
                    )
                    students.append(
                        {
                            "education_id": edu_id,
                            "first_name": first_name or edu_id,
                            "full_name": full_name or first_name or edu_id,
                            "group_name": group_name,
                        }
                    )

        return students

    async def async_get_claims(self) -> list[dict[str, Any]]:
        """Список заявлений с ФИО ребёнка и названием школы (/api/journal/claim/list)."""
        data = await self._request(
            EP_CLAIM_LIST, params={"p_list_mode": "owner_only"}
        )
        return self._items(data)

    async def async_get_periods(self, group_id: int | str) -> list[dict[str, Any]]:
        """Учебные периоды класса (/api/group/group/get-list-period)."""
        data = await self._request(
            EP_GROUP_PERIODS,
            params={
                "p_limit": PAGE_LIMIT,
                "p_page": "1",
                "p_group_ids[]": str(group_id),
            },
        )
        return self._items(data)

    async def async_get_subjects(
        self, group_id: int | str, period_id: int | str
    ) -> list[dict[str, Any]]:
        """Изучаемые предметы класса за учебный период (/api/journal/subject/list-studied)."""
        data = await self._request(
            EP_STUDIED_SUBJECTS,
            params={
                "p_limit": PAGE_LIMIT,
                "p_page": "1",
                "p_groups[]": str(group_id),
                "p_periods[]": str(period_id),
            },
        )
        return self._items(data)

    async def async_get_teachers(
        self, education_id: int | str
    ) -> list[dict[str, Any]]:
        """Список учителей ученика (/api/journal/teacher/list)."""
        data = await self._request(
            EP_TEACHERS_LIST,
            params={
                "p_page": "1",
                "p_limit": PAGE_LIMIT,
                "p_educations[]": str(education_id),
            },
        )
        return self._items(data)

    async def async_get_marks(
        self,
        education_id: int | str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Оценки и коды посещаемости за период (/api/journal/estimate/table)."""
        data = await self._request(
            EP_ESTIMATE_TABLE,
            params={
                "p_limit": MARKS_LIMIT,
                "p_page": "1",
                "p_date_from": format_date(date_from),
                "p_date_to": format_date(date_to),
                "p_educations[]": str(education_id),
            },
        )
        return self._items(data)

    async def async_get_lessons(
        self,
        education_id: int | str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Проведённые уроки и домашние задания (/api/journal/lesson/list-by-education)."""
        dt_from_str, dt_to_str = format_datetime_range(date_from, date_to)
        data = await self._request(
            EP_LESSONS_LIST,
            params={
                "p_limit": PAGE_LIMIT,
                "p_page": "1",
                "p_datetime_from": dt_from_str,
                "p_datetime_to": dt_to_str,
                "p_educations[]": str(education_id),
            },
        )
        return self._items(data)

    async def async_get_schedule(
        self,
        education_id: int | str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Расписание уроков (/api/journal/schedule/list-by-education)."""
        data = await self._request(
            EP_SCHEDULE_LIST,
            params={
                "p_limit": PAGE_LIMIT,
                "p_page": "1",
                "p_datetime_from": format_date(date_from),
                "p_datetime_to": format_date(date_to),
                "p_educations[]": str(education_id),
            },
        )
        return self._items(data)

    async def async_get_attendance(
        self, education_id: int | str, limit: int = 30
    ) -> list[dict[str, Any]]:
        """События прохода через турникет школы (/api/journal/acs/list)."""
        data = await self._request(
            EP_ACS_LIST,
            params={
                "p_limit": str(limit),
                "p_page": "1",
                "p_education": str(education_id),
            },
        )
        return self._items(data)

    async def async_get_meal_balance(
        self,
        education_id: int | str,
        hash_uid: str | None = None,
    ) -> dict[str, Any]:
        """Баланс школьного питания (POST /fps/api/netrika/mobile/v1/accounts/ с RegId=hash_uid или резерв Glolime)."""
        if hash_uid:
            try:
                post_url = f"{BASE_URL}{EP_MEAL_ACCOUNTS}"
                self._clear_session_cookie_jar()
                async with self._session.post(
                    post_url,
                    data={"RegId": str(hash_uid)},
                    headers=self._headers(include_auth=True),
                    timeout=self._timeout,
                    allow_redirects=False,
                    ssl=False,
                ) as response:
                    self._clear_session_cookie_jar()
                    if response.status == 200:
                        payload = await response.json(content_type=None)
                        if isinstance(payload, dict):
                            inner = payload.get("data")
                            if isinstance(inner, dict) and isinstance(
                                inner.get("accounts"), list
                            ):
                                return {"accounts": inner["accounts"]}
                            if isinstance(payload.get("accounts"), list):
                                return {"accounts": payload["accounts"]}
                            if isinstance(inner, list):
                                return {"accounts": inner}
                        elif isinstance(payload, list):
                            return {"accounts": payload}
            except Exception:
                pass

        try:
            fps_data = await self._request(
                EP_MEAL_FPS_LIST,
                params={
                    "p_limit": "20",
                    "p_page": "1",
                    "p_education": str(education_id),
                },
            )
        except Dnevnik2Error:
            return {}

        iframes = fps_data.get("iframe")
        if not isinstance(iframes, list):
            iframes = fps_data.get("items")
        if isinstance(iframes, list) and iframes:
            first_iframe = iframes[0]
            if isinstance(first_iframe, dict):
                frame_data = str(first_iframe.get("frameData") or "").strip().lstrip("?")
                if frame_data:
                    glolime_accounts = await self._fetch_glolime_accounts(frame_data)
                    if glolime_accounts:
                        return {"accounts": glolime_accounts}

        return fps_data

    async def _fetch_glolime_accounts(
        self, frame_data: str
    ) -> list[dict[str, Any]]:
        """Резервное чтение таблицы балансов school.glolime.ru по подписанному frameData."""
        url = f"https://school.glolime.ru/api/netrika/account/?{frame_data}"
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout,
                ssl=False,
            ) as response:
                if response.status != 200:
                    return []
                raw_bytes = await response.read()
        except Exception:
            return []

        try:
            html_text = raw_bytes.decode("windows-1251", errors="ignore")
        except Exception:
            html_text = raw_bytes.decode("utf-8", errors="ignore")

        accounts: list[dict[str, Any]] = []
        for idx, (col1, col2) in enumerate(_GLOLIME_ROW_RE.findall(html_text), start=1):
            name = _HTML_TAG_RE.sub("", col1).strip()
            val_str = _HTML_TAG_RE.sub("", col2).strip().replace(",", ".")
            if not name or not val_str:
                continue
            try:
                val_num = float(val_str.split()[0])
            except ValueError:
                continue
            accounts.append(
                {
                    "id": str(idx),
                    "accounttypename": name,
                    "sum": val_num,
                }
            )
        return accounts
