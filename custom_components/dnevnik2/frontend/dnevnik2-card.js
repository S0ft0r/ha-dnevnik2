/**
 * Кастомная карточка Lovelace для интеграции "Электронный дневник СПб" (dnevnik2).
 * Поддерживает 5 режимов в визуальном редакторе:
 *  - "full": Полная карточка учащегося (шапка + плитки питания/оценок + вкладки Уроки / Задания на дом / Табель)
 *  - "summary": Компактная сводка (только шапка со статусом в школе и 3 плитки: Питание, Оценки сегодня, Ср. балл)
 *  - "grades": Только табель оценок (средние баллы за период и итоговые оценки по четвертям/полугодиям/году)
 *  - "lessons": Только расписание уроков (с переключателем Сегодня / Следующий учебный день и подсветкой текущего урока)
 *  - "homework": Только задания на дом (с чекбоксами синхронизации Todo, фильтром Актуальные / Все и файлами)
 */

const CARD_TYPE = "dnevnik2-card";
const CARD_VERSION = "0.1.30";

const SVG_ICONS = {
  gradeAvg:
    "M4.5 11.5L1.9 15.0H3.7V20.0H5.3V15.0H7.1L4.5 11.5ZM12.0 6.8L7.8 12.2H10.3V20.0H13.7V12.2H16.2L12.0 6.8ZM19.5 3.0L16.9 6.5H18.7V20.0H20.3V6.5H22.1L19.5 3.0Z",
  homework:
    "M5.00 1.00L10.00 6.00L10.00 17.00L5.00 12.50ZM3.00 5.00L3.00 18.50C4.10 18.15 5.30 18.00 6.50 18.00C8.06 18.00 10.25 18.55 11.64 19.29L11.89 20.22L12.37 21.24C12.24 21.32 12.12 21.41 12.00 21.50C10.65 20.65 8.20 20.00 6.50 20.00C4.85 20.00 3.15 20.30 1.75 21.05C1.65 21.10 1.60 21.10 1.50 21.10C1.25 21.10 1.00 20.85 1.00 20.60L1.00 6.00C1.60 5.55 2.25 5.25 3.00 5.00ZM12.00 15.55L12.00 6.00C13.45 4.90 15.55 4.50 17.50 4.50C19.45 4.50 21.55 4.90 23.00 6.00L23.00 13.85L22.98 13.82L22.18 13.02L21.25 12.37L21.00 12.25L21.00 7.13C20.09 6.73 18.86 6.50 17.50 6.50C16.14 6.50 14.91 6.73 14.00 7.13L14.00 12.90L13.82 13.02L13.02 13.82L12.37 14.75L12.00 15.55ZM14.0 19.8L14.0 22.0L16.2 22.0L20.9 17.3L18.7 15.1L14.0 19.8ZM22.2 16.0C22.4 15.8 22.4 15.4 22.2 15.1L20.9 13.8C20.6 13.6 20.2 13.6 20.0 13.8L19.1 14.7L21.3 16.9L22.2 16.0Z",
  schedule:
    "M21.00 5.00L21.00 12.25L20.22 11.89L19.13 11.60L19.00 11.59L19.00 5.00L5.00 5.00L5.00 19.00L11.59 19.00L11.60 19.13L11.89 20.22L12.25 21.00L5.00 21.00C3.90 21.00 3.00 20.10 3.00 19.00L3.00 5.00C3.00 3.90 3.90 3.00 5.00 3.00L19.00 3.00C20.10 3.00 21.00 3.90 21.00 5.00ZM11.00 9.00L11.00 7.00L17.00 7.00L17.00 9.00ZM11.00 13.00L11.00 11.00L17.00 11.00L17.00 11.59L16.87 11.60L15.78 11.89L14.75 12.37L13.85 13.00ZM9.00 7.00L9.00 9.00L7.00 9.00L7.00 7.00ZM9.00 11.00L9.00 13.00L7.00 13.00L7.00 11.00ZM9.00 15.00L9.00 17.00L7.00 17.00L7.00 15.00ZM11.00 15.00L12.25 15.00L11.89 15.78L11.60 16.87L11.59 17.00L11.00 17.00ZM18 12.7A5.3 5.3 0 1 1 12.7 18A5.3 5.3 0 0 1 18 12.7M18 14.3A3.7 3.7 0 1 0 21.7 18A3.7 3.7 0 0 0 18 14.3M17.32 15.15H18.68V18.68H15.25V17.32H17.32V15.15Z",
  turnstile:
    "M17.00 11.59L17.00 6.00L15.00 6.00L15.00 12.25L14.75 12.37L13.82 13.02L13.02 13.82L13.00 13.85L13.00 5.00L7.00 5.00L7.00 19.00L11.59 19.00L11.60 19.13L11.89 20.22L12.25 21.00L3.00 21.00L3.00 19.00L5.00 19.00L5.00 3.00L15.00 3.00L15.00 4.00L19.00 4.00L19.00 11.59L18.00 11.50L17.00 11.59ZM10.00 11.00L12.00 11.00L12.00 13.00L10.00 13.00ZM18 12.7A5.3 5.3 0 1 1 12.7 18A5.3 5.3 0 0 1 18 12.7M18 14.3A3.7 3.7 0 1 0 21.7 18A3.7 3.7 0 0 0 18 14.3M17.32 15.15H18.68V18.68H15.25V17.32H17.32V15.15Z",
  meal: "M11.00 9.00L11.00 2.00L13.00 2.00L13.00 9.00C13.00 11.12 11.34 12.84 9.25 12.97L9.25 22.00L6.75 22.00L6.75 12.97C4.66 12.84 3.00 11.12 3.00 9.00L3.00 2.00L5.00 2.00L5.00 9.00L7.00 9.00L7.00 2.00L9.00 2.00L9.00 9.00ZM16.00 6.00C16.00 4.24 18.24 2.00 21.00 2.00L21.00 12.25L20.22 11.89L19.13 11.60L18.00 11.50L16.87 11.60L16.00 11.83ZM18 12.5A5.5 5.5 0 1 1 12.5 18A5.5 5.5 0 0 1 18 12.5M18 14.0A4.0 4.0 0 1 0 22.0 18A4.0 4.0 0 0 0 18 14.0M16.4 15.3H18.5C19.5 15.3 20.2 15.9 20.2 16.8C20.2 17.7 19.5 18.3 18.5 18.3H17.6V19.0H19.4V19.9H17.6V20.8H16.4V19.9H15.6V19.0H16.4V18.3H15.6V17.4H16.4V15.3M17.6 16.2V17.4H18.4C18.8 17.4 19.0 17.1 19.0 16.8C19.0 16.5 18.8 16.2 18.4 16.2H17.6Z",
};

function renderSvg(pathData) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${pathData}"/></svg>`;
}

function escapeHtml(raw) {
  if (raw === null || raw === undefined) return "";
  return String(raw)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function gradeColorClass(val) {
  const num = Number(val);
  if (!Number.isFinite(num)) return "";
  if (num >= 4.5) return "g-5";
  if (num >= 3.5) return "g-4";
  if (num >= 2.5) return "g-3";
  return "g-2";
}

function computeSubjectHint(avg) {
  const num = Number(avg);
  if (!Number.isFinite(num)) return "";
  if (num >= 4.4 && num < 4.5) return "спорная между 4 и 5";
  if (num >= 3.4 && num < 3.65) return "риск тройки";
  if (num < 2.65) return "риск двойки";
  return "";
}

function shortenPeriodHeader(name, index, totalSubPeriods) {
  const raw = String(name || "").trim();
  const low = raw.toLowerCase();
  const romans = ["I", "II", "III", "IV", "V", "VI"];
  if (low.includes("полугод")) {
    const numMatch = low.match(/([12])/);
    const r = numMatch ? romans[Number(numMatch[1]) - 1] : romans[index] || raw;
    return `${r} п/г`;
  }
  if (
    low.includes("четверт") ||
    low.includes("триместр") ||
    low.includes("модул")
  ) {
    const numMatch = low.match(/([1-6])/);
    if (numMatch) return romans[Number(numMatch[1]) - 1] || numMatch[1];
    return romans[index] || raw.slice(0, 4);
  }
  if (totalSubPeriods >= 3 && index < romans.length) {
    return romans[index];
  }
  return raw.length > 6 ? raw.slice(0, 6) : raw;
}

function parseTimeMinutes(hhmm) {
  const m = String(hhmm || "")
    .trim()
    .match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]);
}

function extractTimeShort(raw) {
  const str = String(raw || "").trim();
  if (!str) return "";
  const m = str.match(/(\d{2}:\d{2})/);
  return m ? m[1] : str;
}

function findDefaultAverageGradeEntity(hass) {
  if (!hass || !hass.states) return "";
  const ids = Object.keys(hass.states);
  for (const id of ids) {
    if (
      id.startsWith("sensor.") &&
      id.endsWith("_average_grade") &&
      (hass.entities?.[id]?.platform === "dnevnik2" ||
        hass.states[id]?.attributes?.subject_averages !== undefined)
    ) {
      return id;
    }
  }
  for (const id of ids) {
    if (
      id.startsWith("sensor.") &&
      hass.states[id]?.attributes?.subject_averages !== undefined
    ) {
      return id;
    }
  }
  return "";
}

const CARD_STYLES = `
  :host {
    display: block;
    --grade-5-bg: rgba(46, 125, 50, 0.20);
    --grade-5-fg: #4caf50;
    --grade-5-border: rgba(76, 175, 80, 0.38);

    --grade-4-bg: rgba(2, 136, 209, 0.20);
    --grade-4-fg: #29b6f6;
    --grade-4-border: rgba(41, 182, 246, 0.38);

    --grade-3-bg: rgba(245, 124, 0, 0.20);
    --grade-3-fg: #ffa726;
    --grade-3-border: rgba(255, 167, 38, 0.38);

    --grade-2-bg: rgba(198, 40, 40, 0.22);
    --grade-2-fg: #ef5350;
    --grade-2-border: rgba(239, 83, 80, 0.42);

    --d2-chip-bg: rgba(127, 127, 127, 0.10);
    --d2-tile-bg: rgba(127, 127, 127, 0.06);
    --d2-row-hover: rgba(127, 127, 127, 0.05);
  }

  ha-card {
    overflow: hidden;
    color: var(--primary-text-color);
    background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
  }

  * {
    box-sizing: border-box;
  }

  .clickable {
    cursor: pointer;
  }

  /* Шапка отдельного режима (Табель / Уроки / Задания на дом) */
  .grades-only-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 15px 16px 12px 16px;
    gap: 12px;
  }
  .grades-only-header.with-divider {
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.16));
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }
  .header-icon {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(3, 169, 244, 0.15);
    color: var(--primary-color, #03a9f4);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .header-icon svg {
    width: 22px;
    height: 22px;
    fill: currentColor;
  }
  .header-titles {
    min-width: 0;
  }
  .header-title {
    font-size: 16px;
    font-weight: 600;
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .header-subtitle {
    font-size: 12px;
    color: var(--secondary-text-color);
    margin-top: 2px;
  }
  .total-avg-box {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    flex-shrink: 0;
  }
  .total-avg-value {
    font-size: 19px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 8px;
    line-height: 1.2;
  }
  .total-avg-caption {
    font-size: 10px;
    color: var(--secondary-text-color);
    margin-top: 3px;
  }

  .summary-strip {
    display: flex;
    gap: 8px;
    padding: 0 16px 12px 16px;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.18));
  }
  .summary-chip {
    font-size: 11px;
    color: var(--secondary-text-color);
    background: var(--d2-chip-bg);
    padding: 4px 9px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .summary-chip b {
    color: var(--primary-text-color);
    font-weight: 600;
  }

  /* Шапка учащегося (Полная карточка и Компактная сводка) */
  .student-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px 10px 16px;
    gap: 10px;
  }
  .student-avatar {
    position: relative;
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: rgba(3, 169, 244, 0.16);
    color: var(--primary-color, #03a9f4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    flex-shrink: 0;
    overflow: hidden;
  }
  .student-avatar img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 50%;
    z-index: 1;
  }
  .presence-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
  }
  .presence-pill svg {
    width: 15px;
    height: 15px;
    fill: currentColor;
  }
  .presence-in {
    background: var(--grade-5-bg);
    color: var(--grade-5-fg);
    border: 1px solid var(--grade-5-border);
  }
  .presence-out {
    background: var(--d2-chip-bg);
    color: var(--secondary-text-color);
    border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.18));
  }

  /* Плитки быстрых показателей */
  .kpi-grid {
    display: grid;
    grid-template-columns: 1.15fr 1.15fr 0.9fr;
    gap: 8px;
    padding: 2px 16px 14px 16px;
  }
  @media (max-width: 380px) {
    .kpi-grid {
      grid-template-columns: 1fr 1fr;
    }
    .kpi-grid .kpi-tile:last-child {
      grid-column: span 2;
    }
  }
  .kpi-tile {
    background: var(--d2-tile-bg);
    border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.16));
    border-radius: 10px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 4px;
    min-width: 0;
  }
  .kpi-tile.warn {
    border-color: var(--grade-3-border);
    background: var(--grade-3-bg);
  }
  .kpi-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
    font-size: 11px;
    color: var(--secondary-text-color);
  }
  .kpi-top svg {
    width: 15px;
    height: 15px;
    fill: currentColor;
    flex-shrink: 0;
  }
  .kpi-main {
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 5px;
    flex-wrap: wrap;
  }
  .kpi-sub {
    font-size: 10px;
    color: var(--secondary-text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Панель вкладок */
  .tabs-bar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.18));
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.18));
    background: var(--d2-tile-bg);
  }
  .tab-btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--secondary-text-color);
    padding: 10px 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-family: inherit;
  }
  .tab-btn svg {
    width: 16px;
    height: 16px;
    fill: currentColor;
  }
  .tab-btn.active {
    color: var(--primary-color, #03a9f4);
    border-bottom-color: var(--primary-color, #03a9f4);
    background: rgba(3, 169, 244, 0.06);
  }
  .tab-badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 999px;
    background: var(--d2-chip-bg);
    color: var(--primary-text-color);
  }
  .tab-btn.active .tab-badge {
    background: var(--primary-color, #03a9f4);
    color: #fff;
  }

  /* Подшапка внутри вкладки */
  .subbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.16));
    font-size: 11px;
    color: var(--secondary-text-color);
    flex-wrap: wrap;
  }
  .seg-group {
    display: inline-flex;
    background: var(--d2-chip-bg);
    padding: 2px;
    border-radius: 7px;
    gap: 2px;
  }
  .seg-btn {
    border: none;
    background: transparent;
    color: var(--secondary-text-color);
    padding: 3px 9px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
  }
  .seg-btn.active {
    background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    color: var(--primary-text-color);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  }

  /* Список уроков */
  .lesson-list {
    display: flex;
    flex-direction: column;
  }
  .lesson-row {
    display: grid;
    grid-template-columns: 26px 76px 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 9px 16px;
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.14));
    font-size: 13px;
  }
  .lesson-row:last-child {
    border-bottom: none;
  }
  .lesson-row.current {
    background: rgba(3, 169, 244, 0.08);
    border-left: 3px solid var(--primary-color, #03a9f4);
    padding-left: 13px;
  }
  .lesson-num {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    background: var(--d2-chip-bg);
    color: var(--secondary-text-color);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
  }
  .lesson-row.current .lesson-num {
    background: var(--primary-color, #03a9f4);
    color: #fff;
  }
  .lesson-time {
    font-size: 11px;
    color: var(--secondary-text-color);
    font-variant-numeric: tabular-nums;
    line-height: 1.25;
  }
  .lesson-time b {
    color: var(--primary-text-color);
    display: block;
    font-size: 12px;
  }
  .lesson-info {
    min-width: 0;
  }
  .lesson-subject {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .lesson-sub {
    font-size: 11px;
    color: var(--secondary-text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 1px;
  }
  .lesson-now-tag {
    color: var(--primary-color, #03a9f4);
    font-weight: 600;
  }
  .lesson-grades {
    display: flex;
    gap: 4px;
  }

  /* Задания на дом */
  .hw-list {
    display: flex;
    flex-direction: column;
  }
  .hw-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.14));
  }
  .hw-item:last-child {
    border-bottom: none;
  }
  .hw-check {
    width: 18px;
    height: 18px;
    margin-top: 2px;
    accent-color: var(--primary-color, #03a9f4);
    cursor: pointer;
    flex-shrink: 0;
  }
  .hw-body {
    flex: 1;
    min-width: 0;
  }
  .hw-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .hw-subject {
    font-size: 13px;
    font-weight: 600;
  }
  .hw-item.done .hw-subject,
  .hw-item.done .hw-text {
    text-decoration: line-through;
    color: var(--secondary-text-color);
  }
  .hw-date {
    font-size: 11px;
    color: var(--secondary-text-color);
    flex-shrink: 0;
  }
  .hw-text {
    font-size: 12px;
    color: var(--primary-text-color);
    margin-top: 3px;
    line-height: 1.35;
    word-break: break-word;
  }
  .hw-files {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }
  .hw-file-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--primary-color, #03a9f4);
    background: rgba(3, 169, 244, 0.12);
    padding: 3px 8px;
    border-radius: 6px;
    text-decoration: none;
  }

  /* Таблица оценок (Табель) */
  .grades-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .grades-table th {
    text-align: center;
    font-size: 11px;
    font-weight: 600;
    color: var(--secondary-text-color);
    padding: 8px 4px;
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.18));
    text-transform: uppercase;
  }
  .grades-table th.col-subject {
    text-align: left;
    padding-left: 16px;
  }
  .grades-table th.active-period {
    color: var(--primary-color, #03a9f4);
  }
  .grades-table td {
    padding: 7px 4px;
    border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.12));
    text-align: center;
    vertical-align: middle;
  }
  .grades-table tr:last-child td {
    border-bottom: none;
  }
  .grades-table tbody tr:hover {
    background: var(--d2-row-hover);
  }
  .td-subject {
    text-align: left !important;
    padding-left: 16px !important;
    max-width: 190px;
  }
  .subject-name {
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
  }
  .subject-hint {
    font-size: 10px;
    color: var(--grade-3-fg);
    display: block;
    margin-top: 1px;
  }

  /* Капсулы оценок */
  .avg-pill {
    display: inline-block;
    min-width: 38px;
    padding: 2px 6px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .final-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
  }
  .final-empty {
    color: var(--secondary-text-color);
    opacity: 0.4;
    font-size: 12px;
  }
  .g-5 {
    background: var(--grade-5-bg);
    color: var(--grade-5-fg);
    border: 1px solid var(--grade-5-border);
  }
  .g-4 {
    background: var(--grade-4-bg);
    color: var(--grade-4-fg);
    border: 1px solid var(--grade-4-border);
  }
  .g-3 {
    background: var(--grade-3-bg);
    color: var(--grade-3-fg);
    border: 1px solid var(--grade-3-border);
  }
  .g-2 {
    background: var(--grade-2-bg);
    color: var(--grade-2-fg);
    border: 1px solid var(--grade-2-border);
  }

  .empty-box {
    padding: 20px 16px;
    text-align: center;
    font-size: 13px;
    color: var(--secondary-text-color);
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 9px 16px;
    background: var(--d2-tile-bg);
    border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.14));
    font-size: 11px;
    color: var(--secondary-text-color);
  }
  .legend {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 4px;
  }
`;

class Dnevnik2Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._activeTab = "lessons";
    this._lessonDay = "today";
    this._hwFilter = "pending";
    this._optimisticDone = {};
    this._lastRenderSig = "";
  }

  static getStubConfig(hass) {
    return {
      entity: findDefaultAverageGradeEntity(hass),
      mode: "full",
      default_tab: "lessons",
      show_hints: true,
    };
  }

  static getConfigForm() {
    return {
      schema: [
        {
          name: "entity",
          required: true,
          selector: {
            entity: {
              domain: "sensor",
              integration: "dnevnik2",
            },
          },
        },
        {
          name: "mode",
          default: "full",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                {
                  value: "full",
                  label: "1. Полная карточка учащегося (шапка + плитки + вкладки)",
                },
                {
                  value: "summary",
                  label: "2. Компактная сводка (шапка + плитки питания и оценок)",
                },
                {
                  value: "grades",
                  label: "3. Только табель оценок",
                },
                {
                  value: "lessons",
                  label: "4. Только расписание уроков",
                },
                {
                  value: "homework",
                  label: "5. Только задания на дом",
                },
              ],
            },
          },
        },
        {
          name: "default_tab",
          default: "lessons",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "lessons", label: "Уроки" },
                { value: "homework", label: "Задания на дом" },
                { value: "grades", label: "Табель" },
              ],
            },
          },
        },
        {
          name: "title",
          selector: { text: {} },
        },
        {
          name: "show_hints",
          default: true,
          selector: { boolean: {} },
        },
      ],
      computeLabel: (schema) => {
        switch (schema.name) {
          case "entity":
            return "Учащийся (сенсор среднего балла)";
          case "mode":
            return "Вариант карточки (режим отображения)";
          case "default_tab":
            return "Вкладка по умолчанию (для полной карточки)";
          case "title":
            return "Свой заголовок (необязательно)";
          case "show_hints":
            return "Подсказки по спорным оценкам в табеле";
          default:
            return schema.name;
        }
      },
      computeHelper: (schema) => {
        if (schema.name === "entity") {
          return "Выберите sensor.<имя>_average_grade нужного учащегося — остальные сущности (уроки, задания на дом, турникет, столовая) карточка найдёт автоматически.";
        }
        return undefined;
      },
    };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Не задана конфигурация карточки");
    }
    this._config = {
      mode: "full",
      default_tab: "lessons",
      show_hints: true,
      ...config,
    };
    if (
      ["lessons", "homework", "grades"].includes(this._config.default_tab) &&
      !this._userSwitchedTab
    ) {
      this._activeTab = this._config.default_tab;
    }
    this._lastRenderSig = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const bundle = this._resolveStudentEntities();
    const sig = JSON.stringify({
      cfg: this._config,
      tab: this._activeTab,
      day: this._lessonDay,
      hwf: this._hwFilter,
      states: Object.values(bundle.ids)
        .filter(Boolean)
        .map((id) => {
          const st = hass?.states?.[id];
          return st ? `${id}:${st.state}:${st.last_updated}` : id;
        }),
    });
    if (sig !== this._lastRenderSig) {
      this._lastRenderSig = sig;
      this._render();
    }
  }

  getCardSize() {
    switch (this._config?.mode) {
      case "summary":
        return 3;
      case "lessons":
      case "homework":
        return 5;
      case "grades":
        return 6;
      default:
        return 8;
    }
  }

  _resolveStudentEntities() {
    const hass = this._hass;
    const avgId =
      this._config?.entity || findDefaultAverageGradeEntity(hass) || "";
    const ids = {
      average_grade: avgId,
      last_grade: "",
      at_school: "",
      turnstile_last: "",
      meal_hot: "",
      meal_buffet: "",
      homework: "",
      lessons: "",
    };
    if (!hass || !hass.states || !avgId) {
      return { ids, states: {} };
    }

    const regEntry = hass.entities?.[avgId];
    const deviceId = regEntry?.device_id;

    if (deviceId && hass.entities) {
      for (const [entId, meta] of Object.entries(hass.entities)) {
        if (meta.device_id !== deviceId) continue;
        if (entId.endsWith("_average_grade")) ids.average_grade = entId;
        else if (entId.endsWith("_last_grade")) ids.last_grade = entId;
        else if (entId.endsWith("_at_school")) ids.at_school = entId;
        else if (entId.endsWith("_turnstile_last")) ids.turnstile_last = entId;
        else if (entId.endsWith("_meal_hot_balance")) ids.meal_hot = entId;
        else if (entId.endsWith("_meal_buffet_balance")) ids.meal_buffet = entId;
        else if (entId.endsWith("_homework")) {
          if (!ids.homework || entId.startsWith("todo.")) ids.homework = entId;
        } else if (entId.endsWith("_lessons_today")) {
          if (!ids.lessons || entId.startsWith("sensor.")) ids.lessons = entId;
        }
      }
    }

    const prefix = avgId.startsWith("sensor.")
      ? avgId.slice("sensor.".length).replace(/_average_grade$/, "")
      : "";
    if (prefix) {
      if (!ids.last_grade && hass.states[`sensor.${prefix}_last_grade`]) {
        ids.last_grade = `sensor.${prefix}_last_grade`;
      }
      if (!ids.at_school && hass.states[`binary_sensor.${prefix}_at_school`]) {
        ids.at_school = `binary_sensor.${prefix}_at_school`;
      }
      if (
        !ids.turnstile_last &&
        hass.states[`sensor.${prefix}_turnstile_last`]
      ) {
        ids.turnstile_last = `sensor.${prefix}_turnstile_last`;
      }
      if (!ids.meal_hot && hass.states[`sensor.${prefix}_meal_hot_balance`]) {
        ids.meal_hot = `sensor.${prefix}_meal_hot_balance`;
      }
      if (
        !ids.meal_buffet &&
        hass.states[`sensor.${prefix}_meal_buffet_balance`]
      ) {
        ids.meal_buffet = `sensor.${prefix}_meal_buffet_balance`;
      }
      if (!ids.homework) {
        if (hass.states[`todo.${prefix}_homework`]) {
          ids.homework = `todo.${prefix}_homework`;
        } else if (hass.states[`sensor.${prefix}_homework`]) {
          ids.homework = `sensor.${prefix}_homework`;
        }
      }
      if (!ids.lessons) {
        if (hass.states[`sensor.${prefix}_lessons_today`]) {
          ids.lessons = `sensor.${prefix}_lessons_today`;
        } else if (hass.states[`todo.${prefix}_lessons_today`]) {
          ids.lessons = `todo.${prefix}_lessons_today`;
        }
      }
    }

    const states = {};
    for (const [k, entId] of Object.entries(ids)) {
      states[k] = entId ? hass.states[entId] || null : null;
    }
    return { ids, states };
  }

  _openMoreInfo(entityId) {
    if (!entityId) return;
    const ev = new CustomEvent("hass-more-info", {
      detail: { entityId },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(ev);
  }

  _toggleHomeworkItem(hwEntityId, uid, checked) {
    if (!uid) return;
    this._optimisticDone[uid] = checked;
    this._render();
    if (this._hass && hwEntityId && hwEntityId.startsWith("todo.")) {
      this._hass.callService(
        "todo",
        "update_item",
        {
          item: uid,
          status: checked ? "completed" : "needs_action",
        },
        { entity_id: hwEntityId }
      );
    }
  }

  _buildGradesTableHtml(avgState) {
    const attrs = avgState?.attributes || {};
    const subjAverages = attrs.subject_averages || {};
    const finalGrades = attrs.final_grades || {};
    const periodGrades = attrs.period_grades || {};
    const rawPeriods = Array.isArray(attrs.periods) ? attrs.periods : [];
    const showHints = this._config.show_hints !== false;

    const subPeriods = [];
    let yearPeriod = null;
    for (const p of rawPeriods) {
      const pName = String(p?.name || "").trim();
      if (!pName) continue;
      const low = pName.toLowerCase();
      if (low.includes("год") || low.includes("year") || low.includes("итог")) {
        yearPeriod = p;
      } else {
        subPeriods.push(p);
      }
    }

    const allSubjects = Array.from(
      new Set([
        ...Object.keys(subjAverages),
        ...Object.keys(finalGrades),
        ...Object.keys(periodGrades),
      ])
    ).sort((a, b) => a.localeCompare(b, "ru"));

    if (allSubjects.length === 0) {
      return `<div class="empty-box">Оценки за текущий период пока не выставлены</div>`;
    }

    const periodHeadersHtml = subPeriods
      .map((p, idx) => {
        const shortLbl = shortenPeriodHeader(p.name, idx, subPeriods.length);
        const isCur = Boolean(p.is_current);
        return `<th class="${isCur ? "active-period" : ""}" title="${escapeHtml(
          `${p.name} (${p.date_from || ""} – ${p.date_to || ""})`
        )}">${escapeHtml(shortLbl)}${isCur ? "•" : ""}</th>`;
      })
      .join("");

    const hasAnyFinal =
      subPeriods.length > 0 ||
      Object.keys(finalGrades).length > 0 ||
      Object.keys(periodGrades).length > 0;
    const yearHeaderHtml = hasAnyFinal
      ? `<th title="${escapeHtml(yearPeriod?.name || "Годовая оценка")}">Год</th>`
      : "";

    const rowsHtml = allSubjects
      .map((subj) => {
        const avgVal = subjAverages[subj];
        const hasAvg = typeof avgVal === "number" && Number.isFinite(avgVal);
        const avgCls = hasAvg ? gradeColorClass(avgVal) : "";
        const hint = hasAvg && showHints ? computeSubjectHint(avgVal) : "";
        const hintHtml = hint
          ? `<span class="subject-hint">${escapeHtml(hint)}</span>`
          : "";
        const avgCellHtml = hasAvg
          ? `<span class="avg-pill ${avgCls}">${avgVal.toFixed(2)}</span>`
          : `<span class="final-empty">—</span>`;

        const subjPeriodsMap = periodGrades[subj] || {};
        const subCellsHtml = subPeriods
          .map((p) => {
            let val = subjPeriodsMap[p.name];
            if (val === undefined && p.is_current && subPeriods.length === 0) {
              val = finalGrades[subj];
            }
            if (val === undefined || val === null) {
              return `<td><span class="final-empty">—</span></td>`;
            }
            return `<td><span class="final-badge ${gradeColorClass(
              val
            )}">${escapeHtml(val)}</span></td>`;
          })
          .join("");

        let yearCellHtml = "";
        if (hasAnyFinal) {
          const yearVal =
            (yearPeriod && subjPeriodsMap[yearPeriod.name]) ??
            subjPeriodsMap["Год"] ??
            subjPeriodsMap["Годовая"] ??
            (subPeriods.length === 0 ? finalGrades[subj] : undefined);
          yearCellHtml =
            yearVal !== undefined && yearVal !== null
              ? `<td><span class="final-badge ${gradeColorClass(
                  yearVal
                )}">${escapeHtml(yearVal)}</span></td>`
              : `<td><span class="final-empty">—</span></td>`;
        }

        return `
          <tr>
            <td class="td-subject">
              <span class="subject-name" title="${escapeHtml(subj)}">${escapeHtml(
          subj
        )}</span>
              ${hintHtml}
            </td>
            <td>${avgCellHtml}</td>
            ${subCellsHtml}
            ${yearCellHtml}
          </tr>
        `;
      })
      .join("");

    return `
      <table class="grades-table">
        <thead>
          <tr>
            <th class="col-subject">Предмет</th>
            <th title="Средний балл за текущий период">Ср.</th>
            ${periodHeadersHtml}
            ${yearHeaderHtml}
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    `;
  }

  _buildLessonsTabHtml(lessonsState) {
    const attrs = lessonsState?.attributes || {};
    const todayLessons = Array.isArray(attrs.lessons) ? attrs.lessons : [];
    const nextLessons = Array.isArray(attrs.lessons_next)
      ? attrs.lessons_next
      : [];
    const nextDateStr = String(attrs.next_date || "").trim();
    const nextBtnLabel = nextDateStr
      ? `След. (${nextDateStr.slice(0, 5)})`
      : "Завтра";

    const list =
      this._lessonDay === "tomorrow" ? nextLessons : todayLessons;

    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();

    const rowsHtml =
      list.length === 0
        ? `<div class="empty-box">На выбранный день уроков в расписании нет</div>`
        : list
            .map((l) => {
              const startMin = parseTimeMinutes(l.time_from);
              const endMin = parseTimeMinutes(l.time_to);
              const isCurrent =
                this._lessonDay === "today" &&
                startMin !== null &&
                endMin !== null &&
                nowMinutes >= startMin &&
                nowMinutes <= endMin;
              const leftMin = isCurrent ? Math.max(1, endMin - nowMinutes) : 0;

              const timeRange =
                l.time_from && l.time_to
                  ? `${l.time_from}–${l.time_to}`
                  : l.time_from || "—";
              const roomStr = l.room ? `каб. ${l.room}` : "";

              let subHtml = "";
              if (isCurrent) {
                subHtml = `<span class="lesson-now-tag">• идёт сейчас (осталось ${leftMin} мин.)</span>`;
              } else if (l.homework) {
                subHtml = `Задание: ${escapeHtml(l.homework)}`;
              } else if (l.teacher) {
                subHtml = escapeHtml(l.teacher);
              }

              const gradesArr = Array.isArray(l.grades) ? l.grades : [];
              const gradesHtml = gradesArr
                .map(
                  (g) =>
                    `<span class="final-badge ${gradeColorClass(
                      g
                    )}" title="Оценка за урок">${escapeHtml(g)}</span>`
                )
                .join("");

              return `
                <div class="lesson-row ${isCurrent ? "current" : ""}">
                  <div class="lesson-num">${escapeHtml(l.number || "•")}</div>
                  <div class="lesson-time">
                    <b>${escapeHtml(timeRange)}</b>
                    ${escapeHtml(roomStr)}
                  </div>
                  <div class="lesson-info">
                    <div class="lesson-subject" title="${escapeHtml(
                      l.subject
                    )}">${escapeHtml(l.subject)}</div>
                    ${
                      subHtml
                        ? `<div class="lesson-sub">${subHtml}</div>`
                        : ""
                    }
                  </div>
                  <div class="lesson-grades">${gradesHtml}</div>
                </div>
              `;
            })
            .join("");

    return `
      <div class="subbar">
        <span>${escapeHtml(
          this._lessonDay === "today"
            ? `Сегодня (${attrs.date || "расписание"})`
            : `Следующий учебный день (${nextDateStr || "расписание"})`
        )}</span>
        <div class="seg-group">
          <button class="seg-btn ${
            this._lessonDay === "today" ? "active" : ""
          }" data-action="lesson-day" data-day="today">
            Сегодня (${todayLessons.length})
          </button>
          <button class="seg-btn ${
            this._lessonDay === "tomorrow" ? "active" : ""
          }" data-action="lesson-day" data-day="tomorrow">
            ${escapeHtml(nextBtnLabel)} (${nextLessons.length})
          </button>
        </div>
      </div>
      <div class="lesson-list">${rowsHtml}</div>
    `;
  }

  _buildHomeworkTabHtml(hwState, hwEntityId) {
    const attrs = hwState?.attributes || {};
    const rawTasks = Array.isArray(attrs.tasks) ? attrs.tasks : [];
    const canToggle = Boolean(hwEntityId && hwEntityId.startsWith("todo."));

    const tasks = rawTasks.map((t, idx) => {
      const uid =
        t.uid || `${t.date || ""}_${t.subject || ""}_${idx}`;
      const isDone =
        uid in this._optimisticDone
          ? this._optimisticDone[uid]
          : Boolean(t.completed);
      return { ...t, _uid: uid, _done: isDone };
    });

    const pendingCount = tasks.filter((t) => !t._done).length;
    const filtered =
      this._hwFilter === "pending"
        ? tasks.filter((t) => !t._done)
        : tasks;

    const listHtml =
      filtered.length === 0
        ? `<div class="empty-box">${
            this._hwFilter === "pending"
              ? "Все задания на дом выполнены"
              : "Заданий на ближайшие дни нет"
          }</div>`
        : filtered
            .map((h) => {
              const files = Array.isArray(h.files) ? h.files : [];
              const filesHtml = files.length
                ? `<div class="hw-files">${files
                    .map((f) => {
                      const href = f.proxy_url || f.url || "#";
                      return `<a class="hw-file-link" href="${escapeHtml(
                        href
                      )}" target="_blank" rel="noopener">📎 ${escapeHtml(
                        f.name || "Файл"
                      )}</a>`;
                    })
                    .join("")}</div>`
                : "";

              const checkboxHtml = canToggle
                ? `<input type="checkbox" class="hw-check" data-action="toggle-hw" data-uid="${escapeHtml(
                    h._uid
                  )}" ${h._done ? "checked" : ""}>`
                : "";

              return `
                <div class="hw-item ${h._done ? "done" : ""}">
                  ${checkboxHtml}
                  <div class="hw-body">
                    <div class="hw-head">
                      <span class="hw-subject">${escapeHtml(h.subject)}</span>
                      <span class="hw-date">${escapeHtml(
                        h.date ? `на ${h.date.slice(0, 5)}` : ""
                      )}</span>
                    </div>
                    ${
                      h.task
                        ? `<div class="hw-text">${escapeHtml(h.task)}</div>`
                        : ""
                    }
                    ${filesHtml}
                  </div>
                </div>
              `;
            })
            .join("");

    return `
      <div class="subbar">
        <span>${
          canToggle
            ? "Отметка синхронизируется со списком Todo"
            : "Список заданий на дом"
        }</span>
        <div class="seg-group">
          <button class="seg-btn ${
            this._hwFilter === "pending" ? "active" : ""
          }" data-action="hw-filter" data-filter="pending">
            Актуальные (${pendingCount})
          </button>
          <button class="seg-btn ${
            this._hwFilter === "all" ? "active" : ""
          }" data-action="hw-filter" data-filter="all">
            Все (${tasks.length})
          </button>
        </div>
      </div>
      <div class="hw-list">${listHtml}</div>
    `;
  }

  _extractStudentIdentity(avgState) {
    const attrs = avgState?.attributes || {};
    let firstName = attrs.first_name || "";
    let groupName = attrs.group_name || "";
    const schoolName = attrs.institution_name || "";

    if (!firstName && this._hass && avgState?.entity_id) {
      const reg = this._hass.entities?.[avgState.entity_id];
      const dev = reg?.device_id ? this._hass.devices?.[reg.device_id] : null;
      if (dev?.name) {
        firstName = dev.name.replace(/^Дневник\s+/i, "").trim();
      }
      if (!groupName && dev?.model && dev.model.includes("—")) {
        groupName = dev.model.split("—").pop().trim();
      }
    }
    if (!firstName) {
      const fn = attrs.friendly_name || "";
      firstName = fn.split(" ")[0] || "Учащийся";
    }
    const displayTitle = groupName
      ? `${firstName} (${groupName})`
      : firstName;
    return { firstName, groupName, schoolName, displayTitle };
  }

  _buildTopStudentAndKpiHtml(
    ids,
    states,
    avgState,
    firstName,
    schoolName,
    headerTitle,
    periodSubtitleParts,
    totalAvgStr,
    totalAvgCls,
    periodName,
    daysLeft
  ) {
    const attrs = avgState.attributes || {};
    const atSchoolState = states.at_school;
    const turnstileLastState = states.turnstile_last;
    const isInSchool = atSchoolState?.state === "on";
    const lastTurnstileTime = extractTimeShort(
      turnstileLastState?.state || atSchoolState?.attributes?.last_event || ""
    );
    const presenceText = isInSchool
      ? `В школе${lastTurnstileTime ? ` • с ${lastTurnstileTime}` : ""}`
      : `Вне школы${lastTurnstileTime ? ` • ${lastTurnstileTime}` : ""}`;

    const hotRaw = Number(states.meal_hot?.state);
    const bufRaw = Number(states.meal_buffet?.state);
    const hasHot = Number.isFinite(hotRaw);
    const hasBuf = Number.isFinite(bufRaw);
    const balLimit = Number(attrs.balance_limit ?? 200);
    const isLowBal =
      balLimit > 0 &&
      ((hasHot && hotRaw < balLimit) || (hasBuf && bufRaw < balLimit));
    const hotStr = hasHot ? `${Math.round(hotRaw)} ₽` : "—";
    const bufStr = hasBuf ? `${Math.round(bufRaw)} ₽` : "—";

    const lastGradeState = states.last_grade;
    const lgAttrs = lastGradeState?.attributes || {};
    const todayGrades = Array.isArray(lgAttrs.today_grades)
      ? lgAttrs.today_grades
      : [];
    let gradesKpiMainHtml = "";
    let gradesKpiSub = "";
    if (todayGrades.length > 0) {
      gradesKpiMainHtml = todayGrades
        .slice(0, 4)
        .map(
          (g) =>
            `<span class="final-badge ${gradeColorClass(g.value)}">${escapeHtml(
              g.value
            )}</span>`
        )
        .join("");
      gradesKpiSub = todayGrades
        .map((g) => `${g.subject} (${g.value})`)
        .join(", ");
    } else if (
      lastGradeState?.state &&
      lastGradeState.state !== "unknown" &&
      lastGradeState.state !== "unavailable"
    ) {
      const valNum = lgAttrs.value || parseInt(lastGradeState.state, 10);
      gradesKpiMainHtml = valNum
        ? `<span class="final-badge ${gradeColorClass(valNum)}">${escapeHtml(
            valNum
          )}</span>`
        : `<span>${escapeHtml(lastGradeState.state)}</span>`;
      gradesKpiSub = lgAttrs.subject
        ? `Посл.: ${lgAttrs.subject}`
        : "Сегодня без новых";
    } else {
      gradesKpiMainHtml = `<span class="final-empty">Нет оценок</span>`;
      gradesKpiSub = "За сегодня";
    }

    const avatarLetter = (firstName || "У").slice(0, 1).toUpperCase();

    return `
      <div class="student-header">
        <div class="header-left">
          <div class="student-avatar">${escapeHtml(avatarLetter)}</div>
          <div class="header-titles">
            <div class="header-title">${escapeHtml(headerTitle)}</div>
            <div class="header-subtitle">${escapeHtml(
              schoolName || periodSubtitleParts.join(" • ")
            )}</div>
          </div>
        </div>
        <div class="presence-pill ${
          isInSchool ? "presence-in" : "presence-out"
        } clickable" data-more-info="${escapeHtml(
      ids.at_school || ids.turnstile_last
    )}">
          ${renderSvg(SVG_ICONS.turnstile)}
          <span>${escapeHtml(presenceText)}</span>
        </div>
      </div>

      <div class="kpi-grid">
        <div class="kpi-tile ${
          isLowBal ? "warn" : ""
        } clickable" data-more-info="${escapeHtml(
      ids.meal_hot || ids.meal_buffet
    )}">
          <div class="kpi-top">
            <span>Питание</span>
            ${renderSvg(SVG_ICONS.meal)}
          </div>
          <div class="kpi-main">
            <span>${escapeHtml(hotStr)}</span>
            <span style="color:var(--secondary-text-color);font-weight:400;">/</span>
            <span>${escapeHtml(bufStr)}</span>
          </div>
          <div class="kpi-sub">${escapeHtml(
            isLowBal ? `Ниже порога ${balLimit} ₽` : "Столовая / Буфет"
          )}</div>
        </div>

        <div class="kpi-tile clickable" data-more-info="${escapeHtml(
          ids.last_grade
        )}">
          <div class="kpi-top">
            <span>Оценки сегодня</span>
            <span class="tab-badge">${
              todayGrades.length > 0 ? `+${todayGrades.length}` : "0"
            }</span>
          </div>
          <div class="kpi-main">${gradesKpiMainHtml}</div>
          <div class="kpi-sub" title="${escapeHtml(
            gradesKpiSub
          )}">${escapeHtml(gradesKpiSub)}</div>
        </div>

        <div class="kpi-tile clickable" data-more-info="${escapeHtml(
          ids.average_grade
        )}">
          <div class="kpi-top">
            <span>Ср. балл</span>
            ${renderSvg(SVG_ICONS.gradeAvg)}
          </div>
          <div class="kpi-main">
            <span class="avg-pill ${totalAvgCls}">${escapeHtml(
      totalAvgStr
    )}</span>
          </div>
          <div class="kpi-sub">${escapeHtml(
            [periodName, daysLeft].filter(Boolean).join(" • ")
          )}</div>
        </div>
      </div>
    `;
  }

  _render() {
    if (!this.shadowRoot) return;
    const { ids, states } = this._resolveStudentEntities();
    const avgState = states.average_grade;

    if (!this._hass || !avgState) {
      this.shadowRoot.innerHTML = `
        <style>${CARD_STYLES}</style>
        <ha-card>
          <div class="empty-box">
            Выберите сенсор <b>sensor.&lt;учащийся&gt;_average_grade</b> в настройках карточки
          </div>
        </ha-card>
      `;
      return;
    }

    const attrs = avgState.attributes || {};
    const { firstName, schoolName, displayTitle } =
      this._extractStudentIdentity(avgState);

    const avgRaw = Number(avgState.state);
    const hasTotalAvg = Number.isFinite(avgRaw) && avgRaw > 0;
    const totalAvgStr = hasTotalAvg ? avgRaw.toFixed(2) : "—";
    const totalAvgCls = hasTotalAvg ? gradeColorClass(avgRaw) : "g-4";

    const periodName = attrs.period_name || "Текущий период";
    const periodDates =
      attrs.period_start && attrs.period_end
        ? `${attrs.period_start} – ${attrs.period_end}`
        : "";
    const daysLeft =
      typeof attrs.period_days_left === "number"
        ? `осталось ${attrs.period_days_left} дн.`
        : "";
    const periodSubtitleParts = [periodName, periodDates, daysLeft].filter(
      Boolean
    );

    const mode = this._config.mode || "full";

    // Счётчик актуальных заданий на дом
    const hwTasks = Array.isArray(states.homework?.attributes?.tasks)
      ? states.homework.attributes.tasks
      : [];
    const pendingHwCount = hwTasks.filter((t, idx) => {
      const uid = t.uid || `${t.date || ""}_${t.subject || ""}_${idx}`;
      return uid in this._optimisticDone
        ? !this._optimisticDone[uid]
        : !t.completed;
    }).length;

    // Режим 2: Компактная сводка (шапка + 3 плитки)
    if (mode === "summary") {
      const headerTitle = this._config.title || displayTitle;
      this.shadowRoot.innerHTML = `
        <style>${CARD_STYLES}</style>
        <ha-card>
          ${this._buildTopStudentAndKpiHtml(
            ids,
            states,
            avgState,
            firstName,
            schoolName,
            headerTitle,
            periodSubtitleParts,
            totalAvgStr,
            totalAvgCls,
            periodName,
            daysLeft
          )}
        </ha-card>
      `;
      this._bindEvents(ids);
      return;
    }

    // Режим 3: Только табель оценок
    if (mode === "grades") {
      const headerTitle =
        this._config.title || `${displayTitle} — Табель оценок`;
      this.shadowRoot.innerHTML = `
        <style>${CARD_STYLES}</style>
        <ha-card>
          <div class="grades-only-header clickable" data-more-info="${escapeHtml(
            ids.average_grade
          )}">
            <div class="header-left">
              <div class="header-icon">${renderSvg(SVG_ICONS.gradeAvg)}</div>
              <div class="header-titles">
                <div class="header-title">${escapeHtml(headerTitle)}</div>
                <div class="header-subtitle">${escapeHtml(
                  periodSubtitleParts.join(" • ")
                )}</div>
              </div>
            </div>
            <div class="total-avg-box">
              <div class="total-avg-value ${totalAvgCls}">${escapeHtml(
        totalAvgStr
      )}</div>
              <div class="total-avg-caption">общий ср. балл</div>
            </div>
          </div>

          <div class="summary-strip">
            <span class="summary-chip">Оценок за период: <b>${escapeHtml(
              attrs.grades_count ?? 0
            )}</b></span>
            <span class="summary-chip">Пропусков (Н): <b>${escapeHtml(
              attrs.absences_count ?? 0
            )}</b></span>
            <span class="summary-chip">Опозданий (О): <b>${escapeHtml(
              attrs.lates_count ?? 0
            )}</b></span>
          </div>

          ${this._buildGradesTableHtml(avgState)}

          <div class="card-footer">
            <div class="legend">
              <span><i class="legend-dot" style="background:var(--grade-5-fg)"></i>4.50+</span>
              <span><i class="legend-dot" style="background:var(--grade-4-fg)"></i>3.50–4.49</span>
              <span><i class="legend-dot" style="background:var(--grade-3-fg)"></i>2.50–3.49</span>
            </div>
            <span>• текущий период</span>
          </div>
        </ha-card>
      `;
      this._bindEvents(ids);
      return;
    }

    // Режим 4: Только расписание уроков
    if (mode === "lessons") {
      const headerTitle =
        this._config.title || `${displayTitle} — Расписание уроков`;
      this.shadowRoot.innerHTML = `
        <style>${CARD_STYLES}</style>
        <ha-card>
          <div class="grades-only-header with-divider clickable" data-more-info="${escapeHtml(
            ids.lessons || ids.average_grade
          )}">
            <div class="header-left">
              <div class="header-icon">${renderSvg(SVG_ICONS.schedule)}</div>
              <div class="header-titles">
                <div class="header-title">${escapeHtml(headerTitle)}</div>
                <div class="header-subtitle">${escapeHtml(
                  schoolName || periodName
                )}</div>
              </div>
            </div>
          </div>
          ${this._buildLessonsTabHtml(states.lessons)}
        </ha-card>
      `;
      this._bindEvents(ids);
      return;
    }

    // Режим 5: Только задания на дом
    if (mode === "homework") {
      const headerTitle =
        this._config.title || `${displayTitle} — Задания на дом`;
      this.shadowRoot.innerHTML = `
        <style>${CARD_STYLES}</style>
        <ha-card>
          <div class="grades-only-header with-divider clickable" data-more-info="${escapeHtml(
            ids.homework || ids.average_grade
          )}">
            <div class="header-left">
              <div class="header-icon">${renderSvg(SVG_ICONS.homework)}</div>
              <div class="header-titles">
                <div class="header-title">${escapeHtml(headerTitle)}</div>
                <div class="header-subtitle">${escapeHtml(
                  schoolName || periodName
                )}</div>
              </div>
            </div>
            <div class="total-avg-box">
              <div class="total-avg-value ${
                pendingHwCount > 0 ? "g-4" : "g-5"
              }">${escapeHtml(pendingHwCount)}</div>
              <div class="total-avg-caption">актуальных</div>
            </div>
          </div>
          ${this._buildHomeworkTabHtml(states.homework, ids.homework)}
        </ha-card>
      `;
      this._bindEvents(ids);
      return;
    }

    // Режим 1 (по умолчанию): Полная карточка учащегося
    const headerTitle = this._config.title || displayTitle;
    let tabBodyHtml = "";
    if (this._activeTab === "lessons") {
      tabBodyHtml = this._buildLessonsTabHtml(states.lessons);
    } else if (this._activeTab === "homework") {
      tabBodyHtml = this._buildHomeworkTabHtml(states.homework, ids.homework);
    } else {
      tabBodyHtml = `
        <div class="subbar">
          <span>${escapeHtml(
            [periodName, daysLeft].filter(Boolean).join(" • ")
          )}</span>
          <span>Оценок: <b>${escapeHtml(
            attrs.grades_count ?? 0
          )}</b> • Пропусков: <b>${escapeHtml(
        attrs.absences_count ?? 0
      )}</b> • Опозданий: <b>${escapeHtml(attrs.lates_count ?? 0)}</b></span>
        </div>
        ${this._buildGradesTableHtml(avgState)}
      `;
    }

    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLES}</style>
      <ha-card>
        ${this._buildTopStudentAndKpiHtml(
          ids,
          states,
          avgState,
          firstName,
          schoolName,
          headerTitle,
          periodSubtitleParts,
          totalAvgStr,
          totalAvgCls,
          periodName,
          daysLeft
        )}

        <div class="tabs-bar">
          <button class="tab-btn ${
            this._activeTab === "lessons" ? "active" : ""
          }" data-action="switch-tab" data-tab="lessons">
            ${renderSvg(SVG_ICONS.schedule)} Уроки
          </button>
          <button class="tab-btn ${
            this._activeTab === "homework" ? "active" : ""
          }" data-action="switch-tab" data-tab="homework">
            ${renderSvg(SVG_ICONS.homework)} Задания на дом
            <span class="tab-badge">${pendingHwCount}</span>
          </button>
          <button class="tab-btn ${
            this._activeTab === "grades" ? "active" : ""
          }" data-action="switch-tab" data-tab="grades">
            ${renderSvg(SVG_ICONS.gradeAvg)} Табель
          </button>
        </div>

        ${tabBodyHtml}
      </ha-card>
    `;

    this._bindEvents(ids);
  }

  _bindEvents(ids) {
    const root = this.shadowRoot;
    if (!root) return;

    root.querySelectorAll("[data-action='switch-tab']").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._userSwitchedTab = true;
        this._activeTab = btn.getAttribute("data-tab") || "lessons";
        this._lastRenderSig = "";
        this._render();
      });
    });

    root.querySelectorAll("[data-action='lesson-day']").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._lessonDay = btn.getAttribute("data-day") || "today";
        this._lastRenderSig = "";
        this._render();
      });
    });

    root.querySelectorAll("[data-action='hw-filter']").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._hwFilter = btn.getAttribute("data-filter") || "pending";
        this._lastRenderSig = "";
        this._render();
      });
    });

    root.querySelectorAll("[data-action='toggle-hw']").forEach((chk) => {
      chk.addEventListener("change", (ev) => {
        const uid = chk.getAttribute("data-uid");
        this._toggleHomeworkItem(ids.homework, uid, Boolean(ev.target.checked));
      });
    });

    root.querySelectorAll("[data-more-info]").forEach((el) => {
      el.addEventListener("click", () => {
        const entId = el.getAttribute("data-more-info");
        if (entId) this._openMoreInfo(entId);
      });
    });
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, Dnevnik2Card);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Электронный дневник СПб — Карточка учащегося / Табель",
    description:
      "5 вариантов отображения в одной карточке: полная карточка, компактная сводка, табель оценок, уроки или задания на дом",
    preview: true,
    documentationURL: "https://github.com/S0ft0r/ha-dnevnik2",
  });
}
