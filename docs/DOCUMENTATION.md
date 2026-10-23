# Полная документация интеграции «Электронный дневник СПб» (`dnevnik2`)

Подробное руководство по настройке, возможностям, создаваемым сущностям, событиям и автоматизациям интеграции портала **«Петербургское образование. Электронный дневник»** (`https://dnevnik2.petersburgedu.ru`) для **Home Assistant**.

**На главную:** [README.md](../README.md)  
**История изменений:** [CHANGELOG.md](../CHANGELOG.md)

---

## Основные возможности (подробно)

1. **Двухшаговый мастер подключения через Госуслуги (ЕСИА):**
   * **Шаг 1 (`Авторизация`):** интеграция автоматически запрашивает актуальную ссылку входа ЕСИА (`GET /api/journal/esa/login-url`), выводит пошаговую инструкцию и определяет, открыта ли настройка с компьютера или из мобильного приложения Home Assistant Companion. Достаточно один раз войти в браузере и вставить cookie `X-JWT-Token` (`eyJ...`).
   * **Шаг 2 (`Параметры интеграции`):** сразу после проверки токена отображает список найденных в профиле учащихся с классами (например, `Иван (5а), Мария (11б)`) и позволяет выбрать название интеграции, формат вывода домашних заданий и расписания уроков (`Список дел (To-do)` или `Сенсор с текстовым атрибутом`), лимит низкого баланса питания и интервал опроса.
2. **Модульная архитектура устройств (Основное устройство + Подустройство на каждого учащегося):**
   * **Основное устройство (`Личный кабинет родителя`):** агрегирует статус профиля (`sensor.account_status`), диагностику сессии (`sensor.connection_status`), настройку порога баланса питания (`number.balance_limit`) и кнопку принудительного обновления данных (`button.refresh`).
   * **Подустройство учащегося (`{Имя}`, модель `Учащийся`):** создаётся автоматически для каждого привязанного учащегося (даже если ученик один) и автоматически наследует комнату/пространство (`area_id`) основного устройства.
3. **Пользовательские иконки интеграции (`dnevnik2:*`) и перенос длинных названий:**
   * Встроенный модуль `frontend/dnevnik2-icons.js` регистрирует векторные иконки `dnevnik2:*`, убирает однострочное обрезание (`text-overflow: ellipsis`) и ограничение в 3 строки (`line-clamp: 3`) для описаний домашних заданий в карточках списков дел Home Assistant, а также формирует лаконичные заголовки списков дел (`Имя - домашние задания`, `Имя - расписание уроков`) в боковой панели «Списки дел».

---

## Настройка интеграции

[![Добавить интеграцию в Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dnevnik2)

1. Нажмите кнопку выше или перейдите в **Настройки → Устройства и службы → Добавить интеграцию** и выберите **Электронный дневник СПб**.
2. **Шаг 1 из 2:** откройте предложенную ссылку входа через Госуслуги (ЕСИА) в браузере на компьютере, после входа нажмите `F12` (или `Ctrl+Shift+I`) → вкладка `Application` (`Приложение`) → `Cookies` → `https://dnevnik2.petersburgedu.ru`, скопируйте значение `X-JWT-Token` (`eyJ...`) и вставьте в поле.
3. **Шаг 2 из 2:** проверьте список найденных учащихся и выберите формат вывода домашних заданий и расписания уроков (`Список дел (To-do)` или `Сенсор с текстовым атрибутом`).

---

## Создаваемые сущности

### На основном устройстве аккаунта
| Сущность | Платформа | Иконка | Описание |
| :--- | :---: | :--- | :--- |
| **Учащихся в профиле** (`account_status`) | `sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/mdi-school.svg" width="22" height="22" align="absmiddle"> `mdi:school` | Количество привязанных учащихся и их список в атрибутах |
| **Лимит баланса питания** (`balance_limit`) | `number` *(Конфигурация)* | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-meal-balance.svg" width="22" height="22" align="absmiddle"> `dnevnik2:meal-balance` | Настраиваемый порог (`₽`), ниже которого на любом из сенсоров («Столовая» или «Буфет») генерируется событие `dnevnik2_low_balance` |
| **Обновить данные** (`refresh`) | `button` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/mdi-database-sync.svg" width="22" height="22" align="absmiddle"> `mdi:database-sync` | Внеочередной опрос API дневника |
| **Статус сессии** (`connection_status`) | `sensor` *(Диагностика)* | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/mdi-cloud-check-outline.svg" width="22" height="22" align="absmiddle"> `mdi:cloud-check-outline` | Состояние сессии и портала (`Активна`, `Сбой портала (5xx)`, `Таймаут соединения`, `Токен истёк`) + параметры JWT-токена и история обновлений в атрибутах |

### На подустройстве каждого учащегося
| Сущность | Платформа | Иконка | Описание |
| :--- | :---: | :--- | :--- |
| **Средний балл** (`average_grade`) | `sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-grade-avg.svg" width="22" height="22" align="absmiddle"> `dnevnik2:grade-avg` | Средний балл за текущий учебный период (четверть/триместр/полугодие) + название и даты периода (`period_name`, `period_start`, `period_end`, `period_days_left`), средние баллы по предметам (`subject_averages`), итоговые оценки (`final_grades`), число оценок, пропусков (`30000`) и опозданий (`30001`) в атрибутах |
| **Последняя оценка** (`last_grade`) | `sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/mdi-numeric-5-box-outline.svg" width="22" height="22" align="absmiddle"> `mdi:numeric-{1..5}-box-outline` | Последняя полученная оценка (предмет, дата, тип работы, комментарий) + все оценки за сегодня (`today_count`, `today_text`, `today_grades`) в атрибутах |
| **Домашние задания** (`homework`) | `todo` или `sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-homework.svg" width="22" height="22" align="absmiddle"> `dnevnik2:homework`<br><img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-homework-done.svg" width="22" height="22" align="absmiddle"> `dnevnik2:homework-done` | По выбору в настройках: интерактивный список дел (`todo`), где в заголовке выводится предмет (`summary`), а в описании (`description`) — текст задания и кликабельные ссылки `📎 [Имя файла](...)` на прикреплённые учителем файлы (скачиваются через встроенный прокси `/api/dnevnik2/file/...`), **или** числовой `sensor` с атрибутами `text` / `uncompleted_text` / `tasks[].files[]` |
| **Расписание уроков / Уроков сегодня** (`lessons_today`) | `todo` или `sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-schedule.svg" width="22" height="22" align="absmiddle"> `dnevnik2:schedule` | По выбору в настройках: интерактивный список дел (`todo`) с временем, кабинетами и учителями **или** числовой `sensor` с готовым многострочным атрибутом `text` |
| **Календарь уроков** (`schedule`) | `calendar` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-schedule.svg" width="22" height="22" align="absmiddle"> `dnevnik2:schedule` | Календарь расписания уроков учащегося с номером урока, предметом, кабинетом (`location`), учителем и домашним заданием (`description`) — создаётся при включённой опции «Создавать календарь уроков» |
| **Последний проход через турникет** (`turnstile_last`) | `sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-turnstile-clock.svg" width="22" height="22" align="absmiddle"> `dnevnik2:turnstile-clock` | Время последнего события СКУД школы и журнал последних проходов |
| **В школе** (`at_school`) | `binary_sensor` | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/mdi-school.svg" width="22" height="22" align="absmiddle"> `mdi:school`<br><img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-school-off.svg" width="22" height="22" align="absmiddle"> `dnevnik2:school-off` | Индикатор нахождения в здании школы по данным турникета СКУД |
| **Столовая** (`meal_hot_balance`) | `sensor` *(Диагностика)* | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-meal-balance.svg" width="22" height="22" align="absmiddle"> `dnevnik2:meal-balance` | Остаток средств на лицевом счёте столовой / горячего питания (`₽`) |
| **Буфет** (`meal_buffet_balance`) | `sensor` *(Диагностика)* | <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/docs/icons/dnevnik2-buffet-balance.svg" width="22" height="22" align="absmiddle"> `dnevnik2:buffet-balance` | Остаток средств на лицевом счёте буфета (`₽`, иконка стакана с монетой рубля) |

---

## События (Events) и автоматизации уведомлений

При каждом обновлении данных интеграция сравнивает предыдущее и новое состояние по каждому учащемуся и отправляет события в шину Home Assistant (`hass.bus`):

### 1. Событие `dnevnik2_new_grade` — новая оценка
Поля `trigger.event.data`:
* `first_name` (`Александр`), `short_name` (`Иванов А.`), `full_name`, `device_id`, `education_id`
* `value` (`5`, `4`, `3`, `2`), `subject` (`Математика`), `date` (`23.10.2026`)
* `work_type` (`Контрольная работа`), `comment` (`Молодец, без ошибок`), `average_grade` (`4.62`)

### 2. Событие `dnevnik2_turnstile` — проход через турникет школы
Поля `trigger.event.data`:
* `first_name` (`Александр`), `short_name` (`Иванов А.`), `device_id`, `education_id`
* `at_school` (`true` — зашёл в школу, `false` — вышел из школы)
* `direction` (`input` / `output`), `datetime` (`23.10.2026 08:17:42`)

### 3. Событие `dnevnik2_low_balance` — снижение баланса Столовой или Буфета ниже лимита
Формируется автоматически, когда остаток на **любом** из двух сенсоров (`Столовая` или `Буфет`) опускается ниже порога `balance_limit` (настраивается в `ConfigFlow` и через сущность `number.*_balance_limit` на основном устройстве):
* `first_name` (`Александр`), `short_name` (`Иванов А.`), `device_id`, `education_id`
* `account` (`hot` или `buffet`), `account_name` (`Столовая` или `Буфет`)
* `balance` (`140.0`), `limit` (`200`), `hot_balance`, `buffet_balance`

### 4. Готовые текстовые атрибуты на `todo.*` и `sensor.*`
Независимо от того, какой формат выбран в настройках (`Список дел (To-do)` или `Сенсор с текстовым атрибутом`), у сущностей домашних заданий и уроков формируются готовые строковые атрибуты:
* `uncompleted_text` — многострочный список **только невыполненных** домашних заданий (обновляется мгновенно при снятии/установке галочек в Todo);
* `text` — многострочный список всех заданий или уроков на сегодня;
* `first_name` — имя учащегося (`Александр`).

### Готовый проект автоматизации (Blueprint)

В репозитории доступен готовый проект автоматизации (Blueprint) — [**`blueprint/ha_notifications.yaml`**](../blueprint/ha_notifications.yaml), который включает в себя:
* уведомления о новых оценках с раздельными шаблонами текста для хороших (`4–5`) и низких (`2–3`) оценок;
* уведомления о входе и выходе учащегося через турникет школы;
* вечернее напоминание о невыполненных домашних заданиях (работает и с `todo.*`, и с `sensor.*`);
* оповещение о снижении баланса школьного питания ниже заданного порога.

[![Импортировать проект в Home Assistant](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FS0ft0r%2Fha-dnevnik2%2Fblob%2Fmain%2Fblueprint%2Fha_notifications.yaml)

**Как подключить проект вручную:**
1. Скопируйте файл [`blueprint/ha_notifications.yaml`](../blueprint/ha_notifications.yaml) в папку `config/blueprints/automation/dnevnik2/` вашего Home Assistant (или в разделе **Настройки → Автоматизации и сцены → Проекты → Импортировать проект** укажите ссылку `https://github.com/S0ft0r/ha-dnevnik2/blob/main/blueprint/ha_notifications.yaml`).
2. Создайте автоматизацию на основе этого проекта, при необходимости отредактируйте тексты сообщений и укажите сервис отправки уведомлений, передав в него переменные `{{ notification_title }}` и `{{ notification_message }}`.

### Пример простой автоматизации без проекта (YAML)
```yaml
automation:
  - alias: "Дневник СПб: Уведомление о новой оценке"
    trigger:
      - platform: event
        event_type: dnevnik2_new_grade
    action:
      - action: persistent_notification.create
        data:
          title: "{{ trigger.event.data.first_name }}: {{ trigger.event.data.value }} по предмету {{ trigger.event.data.subject }}"
          message: >
            Тип работы: {{ trigger.event.data.work_type }}.
            {% if trigger.event.data.comment %}Комментарий: {{ trigger.event.data.comment }}.{% endif %}
            Средний балл: {{ trigger.event.data.average_grade }}.
```
