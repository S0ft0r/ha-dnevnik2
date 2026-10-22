"""Асинхронный HTTP-клиент для API Электронного дневника СПб (dnevnik2.petersburgedu.ru)."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from datetime import date
import json
import re
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

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
_SET_COOKIE_JWT_RE = re.compile(
    r"X-JWT-Token\s*=\s*(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
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


def decode_jwt_payload(token: str | None) -> dict[str, Any]:
    """Декодирует JSON-payload JWT-токена без проверки подписи."""
    if not token:
        return {}
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def jwt_user_identity(payload: dict[str, Any]) -> str:
    """Извлекает идентификатор пользователя из современного ЕСИА (eid/esaid) или старого (userId) JWT."""
    for key in ("eid", "esaid", "userId", "user_id", "sub", "id"):
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def jwt_esk(token: str | None) -> str:
    """Извлекает ключ SSO-сессии ЕСИА (esk -> sso-key) из payload JWT-токена."""
    payload = decode_jwt_payload(token)
    esk = payload.get("esk")
    return str(esk).strip() if esk else ""


def redact_jwt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Маскирует идентификаторы пользователя и SSO-ключ в декодированном JWT-payload для диагностики."""
    safe: dict[str, Any] = {}
    for key, val in payload.items():
        if key.lower() in (
            "userid",
            "user_id",
            "eid",
            "esaid",
            "esk",
            "sub",
            "id",
            "lastid",
            "last_id",
            "email",
            "phone",
            "snils",
        ):
            safe[key] = "***" if val is not None else None
        else:
            safe[key] = val
    exp = int(payload.get("exp") or 0)
    iat = int(payload.get("iat") or 0)
    if exp > 0 and iat > 0:
        safe["ttl_seconds"] = exp - iat
    safe["has_esk"] = bool(payload.get("esk"))
    return safe


def jwt_exp_iat(token: str | None) -> tuple[int, int]:
    """Декодирует поля времени активности (lastActivity/exp, iat) из payload JWT-токена."""
    data = decode_jwt_payload(token)
    if not data:
        return (0, 0)
    ts = int(
        data.get("lastActivity")
        or data.get("last_activity")
        or data.get("exp")
        or 0
    )
    iat = int(data.get("iat") or 0)
    return (ts, iat)


def clear_petersburgedu_cookies(session: ClientSession | None) -> None:
    """Полностью удаляет все cookie petersburgedu.ru из CookieJar сессии aiohttp."""
    if session is None:
        return
    jar = getattr(session, "cookie_jar", None)
    if jar is None:
        return
    if hasattr(jar, "clear_domain"):
        for dom in (
            "petersburgedu.ru",
            ".petersburgedu.ru",
            "dnevnik2.petersburgedu.ru",
            ".dnevnik2.petersburgedu.ru",
            "esa.petersburgedu.ru",
            ".esa.petersburgedu.ru",
        ):
            try:
                jar.clear_domain(dom)
            except Exception:
                pass
    if hasattr(jar, "clear"):
        try:
            jar.clear(
                lambda m: "petersburgedu" in str(m.get("domain", "")).lower()
                or getattr(m, "key", "") in (SESSION_COOKIE, "sso-key")
            )
        except Exception:
            pass


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


_ROTATION_SAFE_PATHS: frozenset[str] = frozenset(
    {
        EP_RELATED_CHILDREN,
        EP_CURRENT_USER,
        EP_GROUP_PERIODS,
        EP_STUDIED_SUBJECTS,
        EP_TEACHERS_LIST,
        EP_ESTIMATE_TABLE,
        EP_LESSONS_LIST,
        EP_SCHEDULE_LIST,
        EP_ACS_LIST,
    }
)


class Dnevnik2Client:
    """Клиент работы с эндпоинтами dnevnik2.petersburgedu.ru и скользящим обновлением X-JWT-Token."""

    def __init__(
        self,
        session: ClientSession,
        token: str | None = None,
        fallback_token: str | None = None,
        on_token_refreshed: Callable[[str, str], None] | None = None,
    ) -> None:
        """Инициализация HTTP-клиента."""
        self._session = session
        self._token = extract_jwt_token(token) or (token or "").strip()
        fb_clean = (
            extract_jwt_token(fallback_token) or (fallback_token or "").strip()
        )
        self._fallback_token: str = fb_clean or self._token
        self._esk: str = jwt_esk(self._token) or jwt_esk(self._fallback_token)
        self._on_token_refreshed = on_token_refreshed
        self._timeout = ClientTimeout(total=REQUEST_TIMEOUT_SEC)
        self._rotations_verified: int = 0
        self._rotations_rejected: int = 0
        self._esia_refreshes_succeeded: int = 0
        self._esia_refreshes_attempted: int = 0
        self._in_esia_refresh: bool = False
        self._last_set_cookies_diag: list[dict[str, Any]] = []
        self._last_esia_refresh_diag: list[dict[str, Any]] = []
        self._last_auth_failure_diag: dict[str, Any] = {}

    @property
    def token(self) -> str:
        """Текущий JWT-токен."""
        return self._token

    @property
    def fallback_token(self) -> str:
        """Резервный проверенный JWT-токен."""
        return self._fallback_token

    @property
    def token_diagnostics(self) -> dict[str, Any]:
        """Обезличенная диагностика текущего JWT-токена, Set-Cookie и SSO-обновления ЕСИА."""
        return {
            "current_jwt_claims": redact_jwt_payload(
                decode_jwt_payload(self._token)
            ),
            "fallback_jwt_claims": redact_jwt_payload(
                decode_jwt_payload(self._fallback_token)
            ),
            "has_distinct_fallback": bool(
                self._fallback_token and self._fallback_token != self._token
            ),
            "has_esk_sso_key": bool(self._esk),
            "rotations_verified": self._rotations_verified,
            "rotations_rejected": self._rotations_rejected,
            "esia_refreshes_attempted": self._esia_refreshes_attempted,
            "esia_refreshes_succeeded": self._esia_refreshes_succeeded,
            "last_set_cookies": list(self._last_set_cookies_diag),
            "last_esia_refresh": list(self._last_esia_refresh_diag),
            "last_auth_failure": dict(self._last_auth_failure_diag),
        }

    def replace_session(self, session: ClientSession) -> None:
        """Заменяет HTTP-сессию клиента на свежую при сбросе пула соединений."""
        self._session = session

    def set_token(self, token: str) -> None:
        """Обновляет токен в памяти клиента."""
        cleaned = extract_jwt_token(token) or token.strip()
        self._token = cleaned
        if cleaned:
            self._fallback_token = cleaned
            esk = jwt_esk(cleaned)
            if esk:
                self._esk = esk

    def _headers(
        self, include_auth: bool = True, token_override: str | None = None
    ) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Charset": "UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/schedule",
            "Connection": "close",
        }
        tok = token_override if token_override is not None else self._token
        if include_auth and tok:
            esk = jwt_esk(tok) or self._esk
            headers["X-JWT-Token"] = tok
            if esk:
                headers["Cookie"] = f"{SESSION_COOKIE}={tok}; sso-key={esk}"
            else:
                headers["Cookie"] = f"{SESSION_COOKIE}={tok}"
        return headers

    def _clear_session_cookie_jar(self) -> None:
        """Очищает CookieJar сессии aiohttp (включая домен petersburgedu.ru без ведущей точки)."""
        clear_petersburgedu_cookies(self._session)

    def _is_valid_candidate_jwt(self, cand: str) -> bool:
        """Проверяет, что кандидат X-JWT-Token принадлежит тому же пользователю (eid/esaid/userId)."""
        if not cand or not cand.startswith("eyJ"):
            return False
        cur_payload = decode_jwt_payload(self._token)
        cand_payload = decode_jwt_payload(cand)
        if not cand_payload:
            return False
        cur_uid = jwt_user_identity(cur_payload)
        cand_uid = jwt_user_identity(cand_payload)
        if not cand_uid:
            return False
        if cur_uid and cand_uid != cur_uid:
            return False
        cur_ts, _ = jwt_exp_iat(self._token)
        cand_ts, _ = jwt_exp_iat(cand)
        return cur_ts == 0 or cand_ts == 0 or (cand_ts >= cur_ts)

    def _commit_new_token(self, chosen: str) -> bool:
        """Атомарно обновляет рабочий и резервный токены, сохраняя их в ConfigEntry."""
        if not chosen or chosen == self._token:
            return False
        if not self._is_valid_candidate_jwt(chosen):
            self._rotations_rejected += 1
            return False
        self._fallback_token = self._token
        self._token = chosen
        esk = jwt_esk(chosen)
        if esk:
            self._esk = esk
        self._rotations_verified += 1
        if self._on_token_refreshed is not None:
            self._on_token_refreshed(chosen, self._fallback_token)
        return True

    def _inspect_and_rotate_cookies(
        self, path: str, set_cookie_headers: list[str]
    ) -> None:
        """Извлекает ПОСЛЕДНИЙ валидный Set-Cookie: X-JWT-Token (при дублировании Path=/ и Path=/api побеждает последний)."""
        cur_payload = decode_jwt_payload(self._token)
        cur_user_id = jwt_user_identity(cur_payload)
        cur_ts, _ = jwt_exp_iat(self._token)

        diag_entries: list[dict[str, Any]] = []
        valid_candidates: list[str] = []

        for hdr in set_cookie_headers:
            first_part = hdr.split(";", 1)[0].strip()
            cookie_name = (
                first_part.split("=", 1)[0].strip()
                if "=" in first_part
                else first_part
            )
            cookie_val = (
                first_part.split("=", 1)[1].strip()
                if "=" in first_part
                else ""
            )
            path_val = ""
            domain_val = ""
            for attr in hdr.split(";")[1:]:
                kv = attr.strip().split("=", 1)
                if len(kv) == 2:
                    k_low = kv[0].strip().lower()
                    if k_low == "path":
                        path_val = kv[1].strip()
                    elif k_low == "domain":
                        domain_val = kv[1].strip()

            if cookie_name.lower() == "sso-key" and cookie_val:
                self._esk = cookie_val

            if cookie_name.lower() != SESSION_COOKIE.lower():
                diag_entries.append(
                    {
                        "endpoint": path,
                        "cookie_name": cookie_name,
                        "path": path_val,
                        "domain": domain_val,
                        "is_jwt": False,
                    }
                )
                continue

            match = _SET_COOKIE_JWT_RE.search(hdr)
            if not match:
                continue

            cand = match.group(1).strip()
            cand_payload = decode_jwt_payload(cand)
            cand_user_id = jwt_user_identity(cand_payload)
            cand_ts, _ = jwt_exp_iat(cand)
            same_as_cur = cand == self._token
            user_id_ok = bool(cand_user_id) and (
                (not cur_user_id) or (cand_user_id == cur_user_id)
            )
            ts_ok = cur_ts == 0 or cand_ts == 0 or (cand_ts >= cur_ts)

            diag_entries.append(
                {
                    "endpoint": path,
                    "cookie_name": cookie_name,
                    "path": path_val,
                    "domain": domain_val,
                    "is_jwt": True,
                    "same_as_current": same_as_cur,
                    "user_id_matches": user_id_ok,
                    "last_activity_ok": ts_ok,
                    "claims": redact_jwt_payload(cand_payload),
                }
            )

            if user_id_ok and ts_ok:
                valid_candidates.append(cand)
            else:
                self._rotations_rejected += 1

        if diag_entries:
            self._last_set_cookies_diag = diag_entries

        if not valid_candidates:
            return

        chosen = valid_candidates[-1]
        self._commit_new_token(chosen)

    async def async_refresh_via_esia_esk(self) -> bool:
        """Бесшовное обновление 8-минутного X-JWT-Token через SSO-ключ ЕСИА (esk -> sso-key)."""
        if self._in_esia_refresh:
            return False
        esk = jwt_esk(self._token) or self._esk
        if not esk:
            return False

        self._in_esia_refresh = True
        self._esia_refreshes_attempted += 1
        hops_diag: list[dict[str, Any]] = []
        found_tokens: list[str] = []

        hop_cookies: dict[str, str] = {"sso-key": esk}
        if self._token:
            hop_cookies[SESSION_COOKIE] = self._token

        def _cookie_header() -> str:
            return "; ".join(f"{k}={v}" for k, v in hop_cookies.items() if v)

        def _collect_set_cookies(hdrs: list[str]) -> list[str]:
            names: list[str] = []
            for h in hdrs:
                first_part = h.split(";", 1)[0].strip()
                if "=" not in first_part:
                    continue
                k, v = first_part.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if not k:
                    continue
                names.append(k)
                if v and v.lower() not in ("deleted", "null", "none"):
                    hop_cookies[k] = v
                if k.lower() == "sso-key" and v:
                    self._esk = v
                m = _SET_COOKIE_JWT_RE.search(h)
                if m:
                    cand = m.group(1).strip()
                    if self._is_valid_candidate_jwt(cand):
                        found_tokens.append(cand)
            return names

        try:
            self._clear_session_cookie_jar()
            login_api_url = f"{BASE_URL}{EP_ESIA_LOGIN_URL}"
            esa_url: str | None = None

            async with self._session.get(
                login_api_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{BASE_URL}/login",
                    "Cookie": _cookie_header(),
                },
                timeout=self._timeout,
                allow_redirects=False,
                ssl=False,
            ) as resp:
                sc_names = _collect_set_cookies(
                    list(resp.headers.getall("Set-Cookie", []))
                )
                self._clear_session_cookie_jar()
                loc = resp.headers.get("Location", "")
                if loc:
                    cand_loc = extract_jwt_token(loc)
                    if cand_loc and self._is_valid_candidate_jwt(cand_loc):
                        found_tokens.append(cand_loc)
                    esa_url = urljoin(login_api_url, loc)
                else:
                    try:
                        body_json = await resp.json(content_type=None)
                        if isinstance(body_json, dict):
                            inner = body_json.get("data")
                            if isinstance(inner, dict) and isinstance(
                                inner.get("url"), str
                            ):
                                esa_url = inner["url"]
                            elif isinstance(inner, str) and inner.startswith(
                                "http"
                            ):
                                esa_url = inner
                            elif isinstance(body_json.get("url"), str):
                                esa_url = body_json["url"]
                    except Exception:
                        pass

                hops_diag.append(
                    {
                        "hop": 0,
                        "host": "dnevnik2.petersburgedu.ru",
                        "path": EP_ESIA_LOGIN_URL,
                        "status": resp.status,
                        "set_cookies": sc_names,
                        "got_esa_url": bool(esa_url),
                    }
                )

            next_url = esa_url
            for hop_idx in range(1, 9):
                if not next_url:
                    break
                cand_from_url = extract_jwt_token(next_url)
                if cand_from_url and self._is_valid_candidate_jwt(
                    cand_from_url
                ):
                    found_tokens.append(cand_from_url)
                    hop_cookies[SESSION_COOKIE] = cand_from_url

                parsed_next = urlparse(next_url)
                async with self._session.get(
                    next_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,application/json,*/*",
                        "Referer": f"{BASE_URL}/",
                        "Cookie": _cookie_header(),
                    },
                    timeout=self._timeout,
                    allow_redirects=False,
                    ssl=False,
                ) as hop_resp:
                    sc_names = _collect_set_cookies(
                        list(hop_resp.headers.getall("Set-Cookie", []))
                    )
                    self._clear_session_cookie_jar()
                    loc = hop_resp.headers.get("Location", "")
                    loc_has_jwt = False
                    if loc:
                        cand_loc = extract_jwt_token(loc)
                        if cand_loc and self._is_valid_candidate_jwt(cand_loc):
                            found_tokens.append(cand_loc)
                            hop_cookies[SESSION_COOKIE] = cand_loc
                            loc_has_jwt = True

                    hops_diag.append(
                        {
                            "hop": hop_idx,
                            "host": parsed_next.netloc,
                            "path": parsed_next.path,
                            "status": hop_resp.status,
                            "set_cookies": sc_names,
                            "location_has_jwt": loc_has_jwt,
                        }
                    )

                    if hop_resp.status in (301, 302, 303, 307, 308) and loc:
                        next_url = urljoin(next_url, loc)
                        continue

                    if hop_resp.status == 200 and not found_tokens:
                        try:
                            text_body = await hop_resp.text()
                            cand_body = extract_jwt_token(text_body)
                            if cand_body and self._is_valid_candidate_jwt(
                                cand_body
                            ):
                                found_tokens.append(cand_body)
                        except Exception:
                            pass
                    break

            self._last_esia_refresh_diag = hops_diag

            for cand in reversed(found_tokens):
                if self._commit_new_token(cand):
                    self._esia_refreshes_succeeded += 1
                    return True
            return False
        except Exception as err:
            hops_diag.append({"error": str(err)})
            self._last_esia_refresh_diag = hops_diag
            return False
        finally:
            self._in_esia_refresh = False

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | list[tuple[str, str]] | None = None,
        *,
        include_auth: bool = True,
        _retried_fallback: bool = False,
        _retried_esia: bool = False,
    ) -> dict[str, Any]:
        """Выполняет GET-запрос к API дневника со скользящим и SSO-обновлением X-JWT-Token."""
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
                set_cookie_headers = list(
                    response.headers.getall("Set-Cookie", [])
                )
                self._clear_session_cookie_jar()

                if response.status in (301, 302, 303, 307, 308, 401, 403):
                    self._last_auth_failure_diag = {
                        "endpoint": path,
                        "status": response.status,
                        "location": response.headers.get("Location", ""),
                        "set_cookie_count": len(set_cookie_headers),
                        "timestamp": int(time.time()),
                    }
                    if set_cookie_headers:
                        self._inspect_and_rotate_cookies(
                            path, set_cookie_headers
                        )
                    if (
                        include_auth
                        and not _retried_esia
                        and await self.async_refresh_via_esia_esk()
                    ):
                        return await self._request(
                            path,
                            params=params,
                            include_auth=include_auth,
                            _retried_fallback=_retried_fallback,
                            _retried_esia=True,
                        )
                    if (
                        include_auth
                        and not _retried_fallback
                        and self._fallback_token
                        and self._fallback_token != self._token
                    ):
                        self._token = self._fallback_token
                        if self._on_token_refreshed is not None:
                            self._on_token_refreshed(
                                self._token, self._fallback_token
                            )
                        return await self._request(
                            path,
                            params=params,
                            include_auth=include_auth,
                            _retried_fallback=True,
                            _retried_esia=_retried_esia,
                        )
                    raise Dnevnik2AuthError(f"HTTP {response.status}")

                if response.status >= 500:
                    raise Dnevnik2ConnectionError(f"HTTP {response.status}")

                try:
                    payload = await response.json(content_type=None)
                except Exception as err:
                    if response.status == 200:
                        if (
                            include_auth
                            and not _retried_esia
                            and await self.async_refresh_via_esia_esk()
                        ):
                            return await self._request(
                                path,
                                params=params,
                                include_auth=include_auth,
                                _retried_fallback=_retried_fallback,
                                _retried_esia=True,
                            )
                        if (
                            include_auth
                            and not _retried_fallback
                            and self._fallback_token
                            and self._fallback_token != self._token
                        ):
                            self._token = self._fallback_token
                            if self._on_token_refreshed is not None:
                                self._on_token_refreshed(
                                    self._token, self._fallback_token
                                )
                            return await self._request(
                                path,
                                params=params,
                                include_auth=include_auth,
                                _retried_fallback=True,
                                _retried_esia=_retried_esia,
                            )
                        raise Dnevnik2AuthError(
                            "Non-JSON 200 response"
                        ) from err
                    raise Dnevnik2ConnectionError("Invalid response body") from err

                if response.status >= 400:
                    raise Dnevnik2ConnectionError(f"HTTP {response.status}")

                if not isinstance(payload, dict):
                    raise Dnevnik2ConnectionError("Unexpected JSON payload root")

                data = payload.get("data")
                if (
                    include_auth
                    and path in _ROTATION_SAFE_PATHS
                    and set_cookie_headers
                    and isinstance(data, (dict, list))
                ):
                    self._inspect_and_rotate_cookies(path, set_cookie_headers)

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

    async def async_keep_alive(self) -> bool:
        """Фоновый пинг сессии (раз в 4 мин.) и SSO-продление 8-минутного X-JWT-Token через esk."""
        prev_tok = self._token
        try:
            await self._request(EP_RELATED_CHILDREN, params={"p_page": "1"})
            if self._token == prev_tok:
                await self.async_refresh_via_esia_esk()
            return True
        except Dnevnik2Error:
            return await self.async_refresh_via_esia_esk()

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
