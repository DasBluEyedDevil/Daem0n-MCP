(function (root) {
  "use strict";

  const allowedApps = Object.freeze(["test", "search", "briefing", "covenant", "community", "graph"]);
  const registry = new Map();
  const MAX_SAFE = Number.MAX_SAFE_INTEGER;
  const idPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

  function text(value, limit = 256) {
    return typeof value === "string" ? value.slice(0, limit) : "";
  }

  function list(value, limit) {
    return Array.isArray(value) ? value.slice(0, limit) : [];
  }

  function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function count(value, fallback = 0) {
    return Number.isSafeInteger(value) ? Math.min(Math.max(value, 0), MAX_SAFE) : fallback;
  }

  function integer(value, minimum, maximum, fallback) {
    return Number.isSafeInteger(value) ? Math.min(Math.max(value, minimum), maximum) : fallback;
  }

  function ratio(value, fallback = 0) {
    if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
    const adjusted = value > 1 && value <= 100 ? value / 100 : value;
    return Math.min(Math.max(adjusted, 0), 1);
  }

  function safeId(value) {
    if (Number.isSafeInteger(value) && value > 0) return value;
    if (typeof value === "string" && idPattern.test(value)) return value;
    return null;
  }

  function idKey(value) {
    return typeof value + ":" + String(value);
  }

  function date(value) {
    const bounded = text(value);
    return bounded && Number.isFinite(Date.parse(bounded)) ? bounded : "";
  }

  function optionalBoolean(value) {
    return typeof value === "boolean" ? value : null;
  }

  function element(tagName, className, value) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  }

  function svgElement(tagName, className) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tagName);
    if (className) node.setAttribute("class", className);
    return node;
  }

  function sendHost(method, payload) {
    const messenger = root.SecureMessenger;
    if (!messenger) return;
    if (typeof messenger.send === "function") messenger.send(method, payload);
    else if (typeof messenger.notify === "function") messenger.notify(method, payload);
  }

  const actions = Object.freeze({
    recordOutcome: Object.freeze({ method: "tool_request", tool: "record_outcome" }),
    briefingFocus: Object.freeze({ method: "tool_request", tool: "recall" }),
    contextCheck: Object.freeze({ method: "tool_request", tool: "context_check" }),
    listCommunities: Object.freeze({ method: "tool_request", tool: "list_communities" }),
    graphFocus: Object.freeze({ method: "tool_request", tool: "get_graph" }),
    refresh: Object.freeze({ method: "tool_request", tool: "refresh_ui" }),
    pagination: Object.freeze({ method: "pagination" }),
  });

  function refreshButton() {
    const control = element("div", "daemon-refresh-control");
    const indicator = element("span", "daemon-update-badge", "New data available");
    indicator.hidden = true;
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-live", "polite");
    const button = element("button", "daemon-btn daemon-btn--secondary daemon-refresh", "Refresh");
    button.type = "button";
    const messenger = root.SecureMessenger;
    if (messenger && typeof messenger.on === "function") {
      messenger.on("data_updated", function () {
        indicator.hidden = false;
        indicator.classList.add("daemon-update-badge--visible");
      });
    }
    button.addEventListener("click", function () {
      indicator.hidden = true;
      indicator.classList.remove("daemon-update-badge--visible");
      button.disabled = true;
      button.textContent = "Refreshing…";
      sendHost(actions.refresh.method, { tool: actions.refresh.tool });
    });
    control.append(indicator, button);
    return control;
  }

  function register(appId, normalizer, renderer) {
    if (!allowedApps.includes(appId) || registry.has(appId)) throw new Error("invalid app registration");
    registry.set(appId, Object.freeze({ normalizer, renderer }));
    if (typeof document !== "undefined") bootstrap();
  }

  function normalize(appId, data) {
    const entry = registry.get(appId);
    if (!entry) throw new Error("unknown app");
    return entry.normalizer(object(data));
  }

  function bootstrap() {
    const appId = document.documentElement.getAttribute("data-daem0n-app");
    const entry = registry.get(appId);
    if (!entry) return;
    const blocks = document.querySelectorAll("#app-data");
    const mount = document.getElementById("app");
    if (blocks.length !== 1 || !mount) return;
    let parsed;
    try {
      parsed = JSON.parse(blocks[0].textContent);
    } catch (_error) {
      mount.replaceChildren(element("p", "daemon-error", "Unable to render this view."));
      return;
    }
    mount.replaceChildren();
    entry.renderer(entry.normalizer(object(parsed)), mount);
  }

  root.Daem0nUI = Object.freeze({
    actions,
    appIds: function () { return registry.keys(); },
    bootstrap,
    element,
    idKey,
    normalize,
    primitives: Object.freeze({ count, date, integer, list, object, optionalBoolean, ratio, safeId, text }),
    refreshButton,
    register,
    sendHost,
    svgElement,
  });
})(globalThis);
