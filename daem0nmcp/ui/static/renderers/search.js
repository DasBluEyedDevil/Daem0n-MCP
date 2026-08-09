(function (ui) {
  "use strict";
  const p = ui.primitives;
  const categories = Object.freeze(["decisions", "warnings", "patterns", "learnings"]);
  const categoryNames = Object.freeze({ decisions: "decision", warnings: "warning", patterns: "pattern", learnings: "learning" });
  const categoryClasses = Object.freeze({ decision: "daemon-badge daemon-badge--decision", warning: "daemon-badge daemon-badge--warning", pattern: "daemon-badge daemon-badge--pattern", learning: "daemon-badge daemon-badge--learning" });

  function record(value) {
    const item = p.object(value);
    const relevance = p.ratio(item.relevance, p.ratio(item.score));
    return {
      id: p.safeId(item.id),
      content: p.text(item.content, 16384),
      relevance,
      semantic_match: p.ratio(item.semantic_match, relevance),
      recency_weight: p.ratio(item.recency_weight, 1),
      created_at: p.date(item.created_at),
      tags: p.list(item.tags, 32).filter(value => typeof value === "string").map(value => p.text(value, 128)),
      worked: p.optionalBoolean(item.worked),
    };
  }

  function normalize(data) {
    const result = { topic: p.text(data.topic) };
    let shown = 0;
    for (const category of categories) {
      result[category] = p.list(data[category], 100).map(record);
      shown += result[category].length;
    }
    result.total_count = p.count(data.total_count, shown);
    result.offset = p.count(data.offset);
    result.limit = p.integer(data.limit, 1, 100, 10);
    result.has_more = typeof data.has_more === "boolean" ? data.has_more : false;
    return result;
  }

  function appendHighlighted(parent, content, topic) {
    const words = topic.split(/\s+/).filter(word => word.length > 2);
    if (!words.length) {
      parent.append(document.createTextNode(content));
      return;
    }
    const lowered = content.toLocaleLowerCase();
    let cursor = 0;
    while (cursor < content.length) {
      let bestIndex = -1;
      let bestLength = 0;
      for (const word of words) {
        const index = lowered.indexOf(word.toLocaleLowerCase(), cursor);
        if (index >= 0 && (bestIndex < 0 || index < bestIndex)) {
          bestIndex = index;
          bestLength = word.length;
        }
      }
      if (bestIndex < 0) {
        parent.append(document.createTextNode(content.slice(cursor)));
        break;
      }
      parent.append(document.createTextNode(content.slice(cursor, bestIndex)));
      const mark = ui.element("mark", "result-card__mark", content.slice(bestIndex, bestIndex + bestLength));
      parent.append(mark);
      cursor = bestIndex + bestLength;
    }
  }

  function percentage(value) { return Math.round(value * 100) + "%"; }

  function renderCard(item, category, topic) {
    const card = ui.element("article", "daemon-card result-card result-card--" + category);
    const header = ui.element("header", "result-card__header");
    header.append(
      ui.element("span", categoryClasses[category], category),
      ui.element("span", "daemon-score__value", item.relevance.toFixed(2))
    );
    const meter = ui.element("meter", "daemon-score-meter");
    meter.min = 0;
    meter.max = 1;
    meter.value = item.relevance;
    const content = ui.element("p", "result-card__content");
    appendHighlighted(content, item.content, topic);
    const details = ui.element("details", "daemon-score-breakdown");
    details.append(
      ui.element("summary", "daemon-score-summary", "Score breakdown"),
      ui.element("p", "daemon-score-component", "Semantic match: " + percentage(item.semantic_match)),
      ui.element("p", "daemon-score-component", "Recency weight: " + percentage(item.recency_weight)),
      ui.element("p", "daemon-score-component", "Final relevance: " + percentage(item.relevance))
    );
    const meta = ui.element("footer", "result-card__meta");
    if (item.created_at) meta.append(ui.element("time", "result-card__date", item.created_at));
    for (const tag of item.tags) meta.append(ui.element("span", "result-card__tag", tag));
    if (category === "decision") {
      const outcome = item.worked === true ? "Success" : item.worked === false ? "Failed" : "Pending";
      const outcomeClass = item.worked === true ? "daemon-badge daemon-badge--success" : item.worked === false ? "daemon-badge daemon-badge--error" : "daemon-badge";
      meta.append(ui.element("span", outcomeClass, outcome));
      if (item.worked === null && item.id !== null) {
        const button = ui.element("button", "daemon-btn daemon-btn--small daemon-btn--secondary", "Record Outcome");
        button.type = "button";
        button.addEventListener("click", function () {
          ui.sendHost(ui.actions.recordOutcome.method, { tool: ui.actions.recordOutcome.tool, args: { memory_id: item.id } });
        });
        meta.append(button);
      }
    }
    card.append(header, meter, content, details, meta);
    return card;
  }

  function render(data, mount) {
    const header = ui.element("header", "daemon-app-header");
    header.append(
      ui.element("div", "daemon-heading-group", undefined),
      ui.refreshButton()
    );
    header.firstChild.append(
      ui.element("h1", "daemon-app-title", data.topic ? "Search: " + data.topic : "Search Results"),
      ui.element("p", "daemon-muted", "Showing " + data.total_count + " result(s)")
    );
    const select = ui.element("select", "daemon-select");
    select.id = "category-filter";
    const choices = [["all", "All Categories"], ["decision", "Decisions"], ["warning", "Warnings"], ["pattern", "Patterns"], ["learning", "Learnings"]];
    for (const choice of choices) {
      const option = ui.element("option", "", choice[1]);
      option.value = choice[0];
      select.append(option);
    }
    const grid = ui.element("section", "search-results");
    let cards = 0;
    for (const listName of categories) {
      const category = categoryNames[listName];
      for (const item of data[listName]) {
        grid.append(renderCard(item, category, data.topic));
        cards += 1;
      }
    }
    if (!cards) grid.append(ui.element("p", "daemon-empty", "No results found."));
    select.addEventListener("change", function () {
      const wanted = select.value;
      const nodes = grid.querySelectorAll(".result-card");
      for (const node of nodes) {
        node.hidden = wanted !== "all" && !node.classList.contains("result-card--" + wanted);
      }
    });
    const content = [header, select, grid];
    if (data.has_more || data.offset > 0) {
      const pager = ui.element("nav", "daemon-pagination");
      const previous = ui.element("button", "daemon-pagination__btn", "Previous");
      const next = ui.element("button", "daemon-pagination__btn", "Next");
      previous.disabled = data.offset === 0;
      next.disabled = !data.has_more;
      previous.addEventListener("click", function () { ui.sendHost(ui.actions.pagination.method, { offset: Math.max(0, data.offset - data.limit), limit: data.limit }); });
      next.addEventListener("click", function () { ui.sendHost(ui.actions.pagination.method, { offset: Math.min(Number.MAX_SAFE_INTEGER, data.offset + data.limit), limit: data.limit }); });
      pager.append(previous, ui.element("span", "daemon-pagination__info", "Offset " + data.offset), next);
      content.push(pager);
    }
    mount.replaceChildren(...content);
  }

  ui.register("search", normalize, render);
})(globalThis.Daem0nUI);
