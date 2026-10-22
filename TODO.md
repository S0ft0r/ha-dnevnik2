# План разработки интеграции «Электронный дневник СПб» (`ha-dnevnik2`)

Отдельный проект интеграции Home Assistant для портала **«Петербургское образование. Электронный дневник»** (`https://dnevnik2.petersburgedu.ru`, мобильный пакет `ru.spb.iac.dnevnikspb_new`).

---

## 1. Результаты предварительного исследования (22/10/2026)

### 1.1. Авторизация через ЕСИА (Госуслуги) и жизненный цикл сессии
С 1 августа 2025 года вход в сервис осуществляется через ЕСИА (`esia.gosuslugi.ru`). Прямое подключение Home Assistant к ЕСИА по OIDC невозможно (закрытый контур Минцифры, ГОСТ-сертификаты, антибот/2FA), но **сессия самого дневника полностью отделена от ЕСИА после момента входа**:

1. **Получение стартовой ссылки ЕСИА:**
   * Запрос: `GET https://dnevnik2.petersburgedu.ru/api/journal/esa/login-url`
   * Заголовки: `X-Requested-With: XMLHttpRequest`, `Accept: application/json, text/plain, */*`
   * Ответ: JSON с полем `data.url` (или `url`), ведущим на шлюз авторизации Санкт-Петербурга (`esa.petersburgedu.ru` → `esia.gosuslugi.ru`).
2. **Выдача токена после входа в браузере:**
   * После успешного входа через Госуслуги шлюз перенаправляет браузер обратно на `https://dnevnik2.petersburgedu.ru/...` и передаёт JWT-токен (`eyJ...`):
     * в query-параметре финального редиректа `?x-access-token=eyJ...` (или `?token=eyJ...`);
     * в cookie **`X-JWT-Token`** (домен `dnevnik2.petersburgedu.ru`, путь `/`);
     * в `localStorage` (`token` / `jwt` / `X-JWT-Token`).
3. **Автоматическое («скользящее») продление сессии:**
   * Все запросы к API выполняются с передачей cookie `Cookie: X-JWT-Token=<token>` (и дублирующего заголовка `X-JWT-Token: <token>`).
   * На обычные `GET`-запросы чтения данных бэкенд возвращает свежий заголовок **`Set-Cookie: X-JWT-Token=eyJ...`**.
   * При сохранении обновлённого токена в `ConfigEntry.data` (`hass.config_entries.async_update_entry`) на каждом цикле опроса `DataUpdateCoordinator` сессия живёт **бессрочно без повторного входа через Госуслуги**.
4. **Признаки истечения сессии (для запуска `async_step_reauth`):**
   * Коды ответа `HTTP 401` / `HTTP 403`;
   * Ответ `HTTP 200` с `text/html` (страница логина) вместо JSON-конверта `{"data": ...}`.

---

### 1.2. Сетевые требования и заголовки запросов
* **Гео-фильтрация:** Сеть Смольного (`46.243.177.102` / `46.243.177.103`) отбрасывает пакеты с зарубежных IP-адресов (таймаут соединения). Запросы с сервера Home Assistant должны идти напрямую с российского IP-адреса.
* **IPv4 и TLS:** Рекомендуется приоритет IPv4 и учёт сертификатов НУЦ Минцифры (при необходимости).
* **Обязательные заголовки для API `https://dnevnik2.petersburgedu.ru`:**
  * `User-Agent`: стандартный браузерный (`Mozilla/5.0 ... Chrome/124.0.0.0 Safari/537.36`)
  * `Accept`: `application/json, text/plain, */*`
  * `X-Requested-With`: `XMLHttpRequest`
  * `Referer`: `https://dnevnik2.petersburgedu.ru/schedule`
  * `Cookie`: `X-JWT-Token=<eyJ...>`
  * `X-JWT-Token`: `<eyJ...>`
* **Важно для HTTP-клиента:** Не использовать общий автоматический `CookieJar` сессии `aiohttp` без фильтрации, так как сервер может присылать несколько `Set-Cookie: X-JWT-Token` для разных `Path`. Токен явно извлекается из заголовков `Set-Cookie` / `response.cookies` и передаётся в заголовке запроса.

---

### 1.3. Карта проверенных эндпоинтов API (`https://dnevnik2.petersburgedu.ru`)

| Назначение | Метод и путь | Параметры запроса | Примечания по ответу |
| :--- | :--- | :--- | :--- |
| **Ссылка входа ЕСИА** | `GET /api/journal/esa/login-url` | — | `data.url` / `url` |
| **Текущий профиль** | `GET /api/journal/user/get-current-user` | — | Данные аккаунта родителя/ученика |
| **Список детей и `education_id`** | `GET /api/journal/person/related-child-list` | `p_page=1` | `data.items[]` → карточка ученика и массив `educations[].education_id`, `group_id`, школа |
| **Данные заявления / школы** | `GET /api/journal/claim/list` | `p_list_mode=owner_only` | `data.items[]` → `child_fio`, `institution_name` |
| **Учебные периоды (четверти/триместры)** | `GET /api/group/group/get-list-period` | `p_limit=500`, `p_page=1`, `p_group_ids[]=<group_id>` | Даты начала/окончания четвертей и полугодий |
| **Изучаемые предметы** | `GET /api/journal/subject/list-studied` | `p_limit=500`, `p_page=1`, `p_groups[]=<group_id>`, `p_periods[]=<period_id>` | Справочник предметов класса |
| **Учителя** | `GET /api/journal/teacher/list` | `p_page=1`, `p_limit=500`, `p_educations[]=<education_id>` | ФИО преподавателей и привязка к предметам |
| **Оценки и пропуски за период** | `GET /api/journal/estimate/table` | `p_educations[]=<education_id>`, `p_date_from=<DD.MM.YYYY>`, `p_date_to=<DD.MM.YYYY>`, `p_limit=100`, `p_page=1` | В одном списке приходят оценки и коды посещаемости: `30000` = пропуск («Н»), `30001` = опоздание («О»), замечания («!») |
| **Уроки и домашние задания** | `GET /api/journal/lesson/list-by-education` | `p_page=1`, `p_limit=100`, `p_educations[]=<education_id>`, `p_datetime_from=<DD.MM.YYYY 00:00:00>`, `p_datetime_to=<DD.MM.YYYY 23:59:59>` | Проведённые уроки, темы и массив домашних заданий (`tasks`) |
| **Расписание уроков** | `GET /api/journal/schedule/list-by-education` | `p_page=1`, `p_limit=500`, `p_educations[]=<education_id>`, `p_datetime_from=<DD.MM.YYYY>`, `p_datetime_to=<DD.MM.YYYY>` | Расписание по дням (даты без времени `DD.MM.YYYY`) |
| **Турникет (вход/выход из школы)** | `GET /api/journal/acs/list` | `p_limit=30`, `p_page=1`, `p_education=<education_id>` | События СКУД (время прохода и направление вход/выход) |
| **Школьное питание (баланс)** | `GET /fps/api/netrika/mobile/v1/accounts/` *(или `/api/journal/fps/list`)* | `p_education=<education_id>` | Баланс лицевого счёта питания (горячее питание / буфет) |

---

### 1.4. Референсные открытые проекты
* **[ibcsz12/SPBplus-dnevnik](https://github.com/ibcsz12/SPBplus-dnevnik)** — лёгкий Android-клиент (2026): реализован прямой вход через `/api/journal/esa/login-url` и перехват `?x-access-token=eyJ...` / cookie `X-JWT-Token`, чтение расписания, ДЗ и оценок.
* **[lumenpearson/lessons](https://github.com/lumenpearson/lessons)** (`server/app/providers/petersburg/` и `docs/diaries/petersburg.md`) — асинхронный Python-клиент (октябрь 2026): детально описаны все 9 основных маршрутов, автообновление cookie `X-JWT-Token` на лету, коды пропусков (`30000`/`30001`) и защитный парсинг обёрнутых полей (`unwrap`).
* **[newtover/dnevnik](https://github.com/newtover/dnevnik)** и **[RomyxR/dnevnik2_spb_api](https://github.com/RomyxR/dnevnik2_spb_api)** — примеры структуры запросов и параметров пагинации.

---

## 2. Выполненные этапы (сегодня — 22/10/2026)

### ✅ [0.1.0] Базовый костяк интеграции (`22/10/2026`)
* [x] **Структура репозитория `/home/user/ha-dnevnik2/`:**
  * `.github/workflows/{validate.yml,release.yml}`, `scripts/validate.py`, `hacs.json`, `LICENSE`, `README.md`, `CHANGELOG.md` (документация ведётся только на русском языке).
* [x] **HTTP-клиент (`custom_components/dnevnik2/client.py`):**
  * Реализованы методы всех 11 проверенных эндпоинтов API, парсер `extract_jwt_token()` (чистый JWT / URL редиректа `?x-access-token=` / строка cookie) и автообновление `Set-Cookie: X-JWT-Token`.
* [x] **Мастер настройки и переавторизации (`config_flow.py`):**
  * `async_step_user` (с автоматическим получением ссылки ЕСИА), `async_step_reauth` / `async_step_reauth_confirm` и `OptionsFlow` (`scan_interval` + опциональная замена токена).
* [x] **Иерархия устройств (`__init__.py`, `manager.py`):**
  * Основное устройство аккаунта (`Личный кабинет родителя`) + отдельное подустройство для **каждого** ученика (даже если он один) с автоматическим наследованием комнаты (`area_id`).
* [x] **Сущности первого среза (`sensor.py`, `binary_sensor.py`, `button.py`, `diagnostics.py`):**
  * На основном устройстве: `sensor.account_status` и `button.refresh`.
  * На подустройстве ученика: `sensor.average_grade`, `sensor.last_grade`, `sensor.homework_tomorrow`, `sensor.lessons_today`, `sensor.turnstile_last`, `sensor.meal_balance` и `binary_sensor.at_school`.
* [x] **Локализация и фронтенд (`translations/{ru,en}.json`, `frontend/dnevnik2-icons.js`, `brand/*.png`):**
  * Ни одной захардкоженной кириллической строки в `.py` файлах, синхронизированные `ru.json`/`en.json`, брендовые иконки и кастомный иконсет `dnevnik2:*` с патчем переноса длинных названий в `hui-generic-entity-row`.

### ✅ [0.1.1] Брендинг, кастомные иконки `dnevnik2:*`, платформа `todo` и демо-режим (`22/10/2026`)
* [x] **Гибридный логотип (`brand/{icon,dark_icon}{,@2x}.png`):**
  * Раскрытая книга из знака мобильного приложения + полностью залитый белый кораблик с Алыми парусами из знака портала, отделённый от книги волной цвета фона (`#192C4F → #142442`).
* [x] **Выбор формата вывода ДЗ и расписания уроков (`todo` vs `sensor` с текстовым атрибутом):**
  * В `ConfigFlow` и `OptionsFlow` добавлены независимые селекторы `homework_mode` и `lessons_mode` (`Список дел (To-do)` / `Сенсор с текстовым атрибутом`).
  * При выборе `todo` создаются `todo.<ученик>_homework` и/или `todo.<ученик>_lessons_today` с локальным сохранением галочек в `Store`; при выборе `sensor` — `sensor.<ученик>_homework` и/или `sensor.<ученик>_lessons_today` с готовым многострочным атрибутом `text`.
  * При смене режима в `OptionsFlow` неактивные сущности автоматически вычищаются из `entity_registry`.
* [x] **События `dnevnik2_new_grade` / `dnevnik2_turnstile` и Blueprint уведомлений (`0.1.3`):**
  * Генерация событий в `hass.bus` при получении новой оценки и проходе турникета (без ложных срабатываний на старте HA; в демо-режиме стреляют по кнопке «Обновить данные»).
  * Единые атрибуты `uncompleted_text`, `text`, `first_name` на сущностях `todo.*` и `sensor.*`.
  * Готовый чертёж `/home/user/reference/dnevnik2_notifications.yaml` с настраиваемыми шаблонами текста под авторскую стилистику речи.
* [x] **Точное разделение `original_name` и `friendly_name` для списков дел (`0.1.4`–`0.1.6`):**
  * Подустройства учеников именуются по имени (`Александр`, `Мария`), на карточке ученика (`Управление`) выводится `Домашние задания` / `Расписание уроков`, а в боковой панели «Списки дел» (`friendly_name`) — `Александр - домашние задания` / `Александр - расписание уроков`.
* [x] **Кастомный векторный иконсет (`frontend/dnevnik2-icons.js`, `icons.json`):**
  * Скомпилированы и подключены `dnevnik2:grade-avg` (три стрелки слева направо по росту, средняя выделена по ширине), `dnevnik2:homework` / `dnevnik2:homework-done` (отзеркаленная `mdi:book-open-page-variant-outline` с круговой обрезкой вокруг карандаша/галочки в `(18, 18)`), `dnevnik2:schedule` (`mdi:list-box-outline` + часы в `(18, 18)`), `dnevnik2:school-off` (перечёркнутая по правилам MDI академическая шапочка), `dnevnik2:turnstile-clock` и `dnevnik2:meal-balance`.
  * Для `button.refresh` применена штатная `mdi:database-sync`, для `sensor.last_grade` — динамические `mdi:numeric-5-box-outline` .. `mdi:numeric-1-box-outline`.
* [x] **Демо-режим со случайными данными (`0.1.1`) и возврат боевой авторизации ЕСИА (`0.1.7`):**
  * После отладки на случайных данных демо-заглушка снята: возвращена боевая проверка `X-JWT-Token` / URL редиректа Госуслуг в `ConfigFlow` и опрос реальных маршрутов `dnevnik2.petersburgedu.ru` с хронологической сортировкой оценок (за 90 дней), уроков, ДЗ и проходов через турникет СКУД.

* [x] **Двухшаговый мастер настройки, фикс баланса питания и защита `X-JWT-Token` (`0.1.8`–`0.1.14`):**
  * Мастер `ConfigFlow` разделён на 2 шага (`Шаг 1 из 2 — Авторизация` только с полем `X-JWT-Token` и определением мобильного клиента `Home Assistant Companion` по `User-Agent`, `Шаг 2 из 2 — Параметры интеграции` с показом найденных учащихся и классов).
  * Добавлена принудительная инвалидация `hass.data["translation_flatten_cache"]` на лету без перезапуска Home Assistant.
  * Исправлен запрос баланса школьного питания (`POST /fps/api/netrika/mobile/v1/accounts/` с `RegId=<hash_uid>` + резерв `school.glolime.ru`).
  * Добавлена изоляция `session.cookie_jar` (`_clear_session_cookie_jar`) и защита исходного `X-JWT-Token` от перезаписи промежуточными `Set-Cookie`.
  * Термин «Обучающийся» заменён на «Учащийся», добавлена склейка пробела между цифрой и литерой класса (`11 б` → `11б`) и очищена папка `brand/` от чернового баннера `logo*.png`.

* [x] **Подготовка к публикации, разделение баланса («Столовая» и «Буфет»), лимит баланса и стабилизация сессии ЕСИА (`0.1.15`–`0.1.24`):**
  * Подготовлены валидатор `scripts/validate.py`, `.github/workflows/{validate.yml,release.yml}`, чертёж `blueprint/ha_notifications.yaml` и визуальные SVG-иконки в `docs/icons/*.svg` (`0.1.15`–`0.1.16`).
  * Добавлены многострочный перенос пунктов в карточках списков дел `ha-check-list-item` (`0.1.18`), ссылка «Скачать диагностику» на карточке каждого устройства (`0.1.20`) и атрибуты оценок за сегодня (`today_count`, `today_text`, `today_grades`) в `sensor.<учащийся>_last_grade` (`0.1.21`).
  * Баланс школьного питания разделён на два диагностических сенсора — `sensor.<учащийся>_meal_hot_balance` (**Столовая**, иконка `dnevnik2:meal-balance`) и `sensor.<учащийся>_meal_buffet_balance` (**Буфет**, иконка `dnevnik2:buffet-balance` со стаканом, пузырьками, трубочкой и монетой рубля), добавлены сущность порога `number.<аккаунт>_balance_limit` на основном устройстве и событие `dnevnik2_low_balance` (`0.1.22`–`0.1.23`).
  * По данным живой диагностики ЕСИА (`eid`, `esaid`, `esk`) добавлены передача `Cookie: X-JWT-Token=<token>; sso-key=<esk>`, `X-Requested-With: XMLHttpRequest`, `Connection: close`, принудительный `IPv4` (`family=socket.AF_INET`), автопересоздание HTTP-сессии при сбоях и бесшовное SSO-обновление через `esk` (`0.1.24`).

---

## 3. Бэклог следующих этапов

* [ ] **Состав сущностей на основном устройстве:**
  * Определить, какие ещё общие сущности и настройки вынести на основное устройство (`Личный кабинет родителя`): например, сводка непрочитанных объявлений школы (`/api/journal/announcement/list-open`) или выбор активного учебного периода (четверти/триместра).
* [ ] **Платформа `calendar`:**
  * Добавить сущность `calendar` расписания уроков учащегося.
* [ ] **Баннер для документации (`logo.png` / `dark_logo.png`):**
  * Вернуться к оформлению горизонтального баннера из 3 иконок (`Портал СПб + Приложение = Дневник СПб`) для `README.md`.
