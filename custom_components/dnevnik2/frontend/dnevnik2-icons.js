/**
 * Кастомный набор векторных иконок "dnevnik2:*", патч переноса длинных строк
 * и форматирование "Имя - домашние задания" в панели "Списки дел" (ha-panel-todo).
 */

const INLINE_ICONS = {
  "grade-avg": {
    "viewBox": "0 0 24 24",
    "path": "M4.5 11.5L1.9 15.0H3.7V20.0H5.3V15.0H7.1L4.5 11.5ZM12.0 6.8L7.8 12.2H10.3V20.0H13.7V12.2H16.2L12.0 6.8ZM19.5 3.0L16.9 6.5H18.7V20.0H20.3V6.5H22.1L19.5 3.0Z"
  },
  "homework": {
    "viewBox": "0 0 24 24",
    "path": "M5.00 1.00L10.00 6.00L10.00 17.00L5.00 12.50ZM3.00 5.00L3.00 18.50C4.10 18.15 5.30 18.00 6.50 18.00C8.06 18.00 10.25 18.55 11.64 19.29L11.89 20.22L12.37 21.24C12.24 21.32 12.12 21.41 12.00 21.50C10.65 20.65 8.20 20.00 6.50 20.00C4.85 20.00 3.15 20.30 1.75 21.05C1.65 21.10 1.60 21.10 1.50 21.10C1.25 21.10 1.00 20.85 1.00 20.60L1.00 6.00C1.60 5.55 2.25 5.25 3.00 5.00ZM12.00 15.55L12.00 6.00C13.45 4.90 15.55 4.50 17.50 4.50C19.45 4.50 21.55 4.90 23.00 6.00L23.00 13.85L22.98 13.82L22.18 13.02L21.25 12.37L21.00 12.25L21.00 7.13C20.09 6.73 18.86 6.50 17.50 6.50C16.14 6.50 14.91 6.73 14.00 7.13L14.00 12.90L13.82 13.02L13.02 13.82L12.37 14.75L12.00 15.55ZM14.0 19.8L14.0 22.0L16.2 22.0L20.9 17.3L18.7 15.1L14.0 19.8ZM22.2 16.0C22.4 15.8 22.4 15.4 22.2 15.1L20.9 13.8C20.6 13.6 20.2 13.6 20.0 13.8L19.1 14.7L21.3 16.9L22.2 16.0Z"
  },
  "homework-done": {
    "viewBox": "0 0 24 24",
    "path": "M5.00 1.00L10.00 6.00L10.00 17.00L5.00 12.50ZM3.00 5.00L3.00 18.50C4.10 18.15 5.30 18.00 6.50 18.00C8.06 18.00 10.25 18.55 11.64 19.29L11.89 20.22L12.37 21.24C12.24 21.32 12.12 21.41 12.00 21.50C10.65 20.65 8.20 20.00 6.50 20.00C4.85 20.00 3.15 20.30 1.75 21.05C1.65 21.10 1.60 21.10 1.50 21.10C1.25 21.10 1.00 20.85 1.00 20.60L1.00 6.00C1.60 5.55 2.25 5.25 3.00 5.00ZM12.00 15.55L12.00 6.00C13.45 4.90 15.55 4.50 17.50 4.50C19.45 4.50 21.55 4.90 23.00 6.00L23.00 13.85L22.98 13.82L22.18 13.02L21.25 12.37L21.00 12.25L21.00 7.13C20.09 6.73 18.86 6.50 17.50 6.50C16.14 6.50 14.91 6.73 14.00 7.13L14.00 12.90L13.82 13.02L13.02 13.82L12.37 14.75L12.00 15.55ZM16.8 21.4L13.6 18.2L15.1 16.7L16.8 18.4L21.2 14.0L22.7 15.5L16.8 21.4Z"
  },
  "schedule": {
    "viewBox": "0 0 24 24",
    "path": "M21.00 5.00L21.00 12.25L20.22 11.89L19.13 11.60L19.00 11.59L19.00 5.00L5.00 5.00L5.00 19.00L11.59 19.00L11.60 19.13L11.89 20.22L12.25 21.00L5.00 21.00C3.90 21.00 3.00 20.10 3.00 19.00L3.00 5.00C3.00 3.90 3.90 3.00 5.00 3.00L19.00 3.00C20.10 3.00 21.00 3.90 21.00 5.00ZM11.00 9.00L11.00 7.00L17.00 7.00L17.00 9.00ZM11.00 13.00L11.00 11.00L17.00 11.00L17.00 11.59L16.87 11.60L15.78 11.89L14.75 12.37L13.85 13.00ZM9.00 7.00L9.00 9.00L7.00 9.00L7.00 7.00ZM9.00 11.00L9.00 13.00L7.00 13.00L7.00 11.00ZM9.00 15.00L9.00 17.00L7.00 17.00L7.00 15.00ZM11.00 15.00L12.25 15.00L11.89 15.78L11.60 16.87L11.59 17.00L11.00 17.00ZM18 12.7A5.3 5.3 0 1 1 12.7 18A5.3 5.3 0 0 1 18 12.7M18 14.3A3.7 3.7 0 1 0 21.7 18A3.7 3.7 0 0 0 18 14.3M17.32 15.15H18.68V18.68H15.25V17.32H17.32V15.15Z"
  },
  "school-off": {
    "viewBox": "0 0 24 24",
    "path": "M5.00 13.18L12.00 17.00L14.01 15.90L12.72 14.61L12.00 15.00L1.00 9.00L4.95 6.84L1.11 3.00L2.39 1.73L6.60 5.94L14.36 13.71L15.66 15.00L18.24 17.59L22.11 21.46L20.84 22.73L16.60 18.49L12.00 21.00L5.00 17.18ZM12.00 3.00L23.00 9.00L23.00 17.00L21.00 17.00L21.00 10.09L16.25 12.68L8.49 4.91ZM19.00 15.43L17.55 13.97L19.00 13.18Z"
  },
  "turnstile-clock": {
    "viewBox": "0 0 24 24",
    "path": "M17.00 11.59L17.00 6.00L15.00 6.00L15.00 12.25L14.75 12.37L13.82 13.02L13.02 13.82L13.00 13.85L13.00 5.00L7.00 5.00L7.00 19.00L11.59 19.00L11.60 19.13L11.89 20.22L12.25 21.00L3.00 21.00L3.00 19.00L5.00 19.00L5.00 3.00L15.00 3.00L15.00 4.00L19.00 4.00L19.00 11.59L18.00 11.50L17.00 11.59ZM10.00 11.00L12.00 11.00L12.00 13.00L10.00 13.00ZM18 12.7A5.3 5.3 0 1 1 12.7 18A5.3 5.3 0 0 1 18 12.7M18 14.3A3.7 3.7 0 1 0 21.7 18A3.7 3.7 0 0 0 18 14.3M17.32 15.15H18.68V18.68H15.25V17.32H17.32V15.15Z"
  },
  "meal-balance": {
    "viewBox": "0 0 24 24",
    "path": "M11.00 9.00L11.00 2.00L13.00 2.00L13.00 9.00C13.00 11.12 11.34 12.84 9.25 12.97L9.25 22.00L6.75 22.00L6.75 12.97C4.66 12.84 3.00 11.12 3.00 9.00L3.00 2.00L5.00 2.00L5.00 9.00L7.00 9.00L7.00 2.00L9.00 2.00L9.00 9.00ZM16.00 6.00C16.00 4.24 18.24 2.00 21.00 2.00L21.00 12.25L20.22 11.89L19.13 11.60L18.00 11.50L16.87 11.60L16.00 11.83ZM18 12.5A5.5 5.5 0 1 1 12.5 18A5.5 5.5 0 0 1 18 12.5M18 14.0A4.0 4.0 0 1 0 22.0 18A4.0 4.0 0 0 0 18 14.0M16.4 15.3H18.5C19.5 15.3 20.2 15.9 20.2 16.8C20.2 17.7 19.5 18.3 18.5 18.3H17.6V19.0H19.4V19.9H17.6V20.8H16.4V19.9H15.6V19.0H16.4V18.3H15.6V17.4H16.4V15.3M17.6 16.2V17.4H18.4C18.8 17.4 19.0 17.1 19.0 16.8C19.0 16.5 18.8 16.2 18.4 16.2H17.6Z"
  },
  "buffet-balance": {
    "viewBox": "0 0 24 24",
    "path": "M2.85 5.98L12.90 5.98L14.10 1.00L15.68 1.00L14.48 5.98L18.15 5.98L17.53 11.52L17.01 11.58L16.50 11.68L16.00 11.82L15.51 12.00L15.04 12.21L14.59 12.47L14.15 12.76L13.75 13.08L13.37 13.44L13.02 13.82L12.70 14.24L12.42 14.67L12.17 15.13L11.96 15.60L11.79 16.09L11.65 16.60L11.56 17.11L11.51 17.63L11.50 18.15L11.53 18.67L11.61 19.18L11.72 19.69L11.88 20.18L12.07 20.67L12.30 21.13L12.57 21.58L12.88 22.00L6.27 22.00L5.64 21.87L4.83 21.37L4.47 20.38ZM4.63 7.42L5.03 11.38L11.60 11.38L12.55 7.42ZM14.13 7.42L13.18 11.38L15.97 11.38L16.37 7.42ZM7.17 8.81A0.85 0.85 0 1 1 7.17 10.53A0.85 0.85 0 1 1 7.17 8.81ZM9.69 8.05A0.72 0.72 0 1 1 9.69 9.49A0.72 0.72 0 1 1 9.69 8.05ZM7.26 12.96A0.95 0.95 0 1 0 7.26 14.85A0.95 0.95 0 1 0 7.26 12.96ZM9.87 15.11A0.77 0.77 0 1 0 9.87 16.64A0.77 0.77 0 1 0 9.87 15.11ZM7.62 17.36A1.03 1.03 0 1 0 7.62 19.43A1.03 1.03 0 1 0 7.62 17.36ZM18 12.5A5.5 5.5 0 1 1 12.5 18A5.5 5.5 0 0 1 18 12.5M18 14.0A4.0 4.0 0 1 0 22.0 18A4.0 4.0 0 0 0 18 14.0M16.4 15.3H18.5C19.5 15.3 20.2 15.9 20.2 16.8C20.2 17.7 19.5 18.3 18.5 18.3H17.6V19.0H19.4V19.9H17.6V20.8H16.4V19.9H15.6V19.0H16.4V18.3H15.6V17.4H16.4V15.3M17.6 16.2V17.4H18.4C18.8 17.4 19.0 17.1 19.0 16.8C19.0 16.5 18.8 16.2 18.4 16.2H17.6Z"
  }
};

async function getIcon(name) {
  const icon = INLINE_ICONS[name];
  if (!icon) {
    return { path: "", viewBox: "0 0 24 24" };
  }
  return {
    path: icon.path,
    viewBox: icon.viewBox || "0 0 24 24",
  };
}

async function getIconList() {
  return Object.keys(INLINE_ICONS).map((name) => ({ name }));
}

window.customIconsets = window.customIconsets || {};
window.customIconsets["dnevnik2"] = getIcon;

window.customIcons = window.customIcons || {};
window.customIcons["dnevnik2"] = { getIcon, getIconList };

function patchHassFormatEntityName(hass) {
  if (
    !hass ||
    typeof hass.formatEntityName !== "function" ||
    hass.formatEntityName._dnevnik2Patched
  ) {
    return;
  }
  const origFormat = hass.formatEntityName;
  const wrapped = function (stateObj, name, options) {
    if (
      !name &&
      stateObj?.entity_id?.startsWith("todo.") &&
      (hass.entities?.[stateObj.entity_id]?.platform === "dnevnik2" ||
        stateObj.attributes?.icon?.startsWith?.("dnevnik2:"))
    ) {
      const formatted = origFormat.call(
        this,
        stateObj,
        [{ type: "device" }, { type: "entity" }],
        { ...(options || {}), separator: " - " }
      );
      return formatted.replace(
        / - ([А-ЯЁA-Z])/,
        (_, ch) => " - " + ch.toLowerCase()
      );
    }
    return origFormat.call(this, stateObj, name, options);
  };
  wrapped._dnevnik2Patched = true;
  hass.formatEntityName = wrapped;
}

function isDnevnik2Entity(hass, entityId) {
  if (!entityId) return false;
  if (hass?.entities?.[entityId]?.platform === "dnevnik2") return true;
  const icon = hass?.states?.[entityId]?.attributes?.icon;
  return typeof icon === "string" && icon.startsWith("dnevnik2:");
}

function applyCheckListItemWrap(itemEl, enable) {
  const sr = itemEl?.shadowRoot;
  if (!sr) return;
  const existing = sr.querySelector("#dnevnik2-check-wrap-style");
  if (enable && !existing) {
    const style = document.createElement("style");
    style.id = "dnevnik2-check-wrap-style";
    style.textContent =
      ":host { height: auto !important; min-height: 48px !important; } " +
      ".mdc-deprecated-list-item__text { white-space: normal !important; overflow: visible !important; text-overflow: unset !important; word-break: break-word !important; overflow-wrap: anywhere !important; display: block !important; width: 100% !important; }";
    sr.appendChild(style);
  } else if (!enable && existing) {
    existing.remove();
  }
}

function applyTodoCardWrap(cardEl) {
  const sr = cardEl?.shadowRoot;
  if (!sr) return;
  const entityId = cardEl._entityId || cardEl._config?.entity;
  const isTarget = isDnevnik2Entity(cardEl.hass, entityId);
  const existing = sr.querySelector("#dnevnik2-todo-wrap-style");
  if (isTarget && !existing) {
    const style = document.createElement("style");
    style.id = "dnevnik2-todo-wrap-style";
    style.textContent =
      "ha-check-list-item { height: auto !important; min-height: 48px !important; } " +
      ".column { white-space: normal !important; overflow: visible !important; word-break: break-word !important; overflow-wrap: anywhere !important; padding-right: 8px !important; } " +
      ".summary { white-space: pre-wrap !important; overflow: visible !important; text-overflow: unset !important; word-break: break-word !important; overflow-wrap: anywhere !important; line-height: 1.35 !important; display: block !important; } " +
      ".description { white-space: pre-wrap !important; overflow: visible !important; text-overflow: unset !important; display: block !important; -webkit-line-clamp: unset !important; line-clamp: unset !important; word-break: break-word !important; overflow-wrap: anywhere !important; line-height: 1.35 !important; }";
    sr.appendChild(style);
  } else if (!isTarget && existing) {
    existing.remove();
  }
  sr.querySelectorAll("ha-check-list-item").forEach((item) => {
    applyCheckListItemWrap(item, isTarget);
  });
}

if (typeof customElements !== "undefined") {
  const haRoot = document.querySelector("home-assistant");
  if (haRoot?.hass) {
    patchHassFormatEntityName(haRoot.hass);
  }

  customElements.whenDefined("home-assistant").then(() => {
    const cls = customElements.get("home-assistant");
    if (!cls || cls.prototype._dnevnik2HassPatched) return;
    cls.prototype._dnevnik2HassPatched = true;
    const origUpdateHass = cls.prototype._updateHass;
    if (typeof origUpdateHass === "function") {
      cls.prototype._updateHass = function (obj) {
        const res = origUpdateHass.call(this, obj);
        patchHassFormatEntityName(this.hass);
        return res;
      };
    }
  });

  customElements.whenDefined("ha-panel-todo").then(() => {
    const cls = customElements.get("ha-panel-todo");
    if (!cls || cls.prototype._dnevnik2TodoPatched) return;
    cls.prototype._dnevnik2TodoPatched = true;
    const origWillUpdate = cls.prototype.willUpdate;
    cls.prototype.willUpdate = function (changedProps) {
      patchHassFormatEntityName(this.hass);
      if (origWillUpdate) {
        return origWillUpdate.call(this, changedProps);
      }
    };
  });

  customElements.whenDefined("hui-todo-list-card").then(() => {
    const cls = customElements.get("hui-todo-list-card");
    if (!cls || cls.prototype._dnevnik2TodoCardPatched) return;
    cls.prototype._dnevnik2TodoCardPatched = true;
    const origUpdated = cls.prototype.updated;
    cls.prototype.updated = function (changedProps) {
      if (origUpdated) origUpdated.call(this, changedProps);
      applyTodoCardWrap(this);
    };
  });

  customElements.whenDefined("ha-check-list-item").then(() => {
    const cls = customElements.get("ha-check-list-item");
    if (!cls || cls.prototype._dnevnik2CheckItemPatched) return;
    cls.prototype._dnevnik2CheckItemPatched = true;
    const origUpdated = cls.prototype.updated;
    cls.prototype.updated = function (changedProps) {
      if (origUpdated) origUpdated.call(this, changedProps);
      const host = this.getRootNode?.()?.host;
      if (host?.localName === "hui-todo-list-card") {
        const entityId = host._entityId || host._config?.entity;
        applyCheckListItemWrap(this, isDnevnik2Entity(host.hass, entityId));
      }
    };
  });

  customElements.whenDefined("hui-generic-entity-row").then(() => {
    const cls = customElements.get("hui-generic-entity-row");
    if (!cls || cls.prototype._dnevnik2WrapPatched) return;
    cls.prototype._dnevnik2WrapPatched = true;
    const origUpdated = cls.prototype.updated;
    cls.prototype.updated = function (changedProps) {
      patchHassFormatEntityName(this.hass);
      if (origUpdated) origUpdated.call(this, changedProps);
      const entityId = this.config?.entity;
      const isTarget = isDnevnik2Entity(this.hass, entityId);
      const existing = this.shadowRoot?.querySelector("#dnevnik2-wrap-style");
      if (isTarget && this.shadowRoot && !existing) {
        const style = document.createElement("style");
        style.id = "dnevnik2-wrap-style";
        style.textContent =
          ".info, .info > * { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.25em; }";
        this.shadowRoot.appendChild(style);
      } else if (!isTarget && existing) {
        existing.remove();
      }
    };
  });
}
