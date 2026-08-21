"use strict";

const AI_SETTINGS_KEY = "hot-list-ai-settings";
const AI_TIMEOUT_MS = 10 * 60 * 1000;
const DAY_SCOPE_VALUE = "day";
const GLOBAL_TOPIC_LIMIT = 120;
const PLATFORM_TOPIC_LIMIT = 40;
const DEFAULT_AI_FOCUS = "识别跨平台共同热点、各平台差异、热度共振、潜在趋势信号及值得持续关注的事件，并明确区分榜单事实与分析判断。";

const state = {
  snapshots: [],
  selectedDate: "",
  selectedHour: "",
  snapshotRequestId: 0,
  controller: null,
  resultSignature: "",
};

const elements = {
  form: document.getElementById("ai-analysis-form"),
  date: document.getElementById("date-filter"),
  hour: document.getElementById("hour-filter"),
  snapshotSummary: document.getElementById("snapshot-summary"),
  snapshotLoading: document.getElementById("snapshot-loading"),
  snapshotError: document.getElementById("snapshot-error"),
  platformAll: document.getElementById("ai-platform-all"),
  platformOptions: document.getElementById("ai-platform-options"),
  focus: document.getElementById("ai-focus"),
  apiUrl: document.getElementById("ai-api-url"),
  apiKey: document.getElementById("ai-api-key"),
  model: document.getElementById("ai-model"),
  analyzeButton: document.getElementById("ai-analyze-button"),
  cancelButton: document.getElementById("ai-cancel-button"),
  loading: document.getElementById("ai-loading"),
  error: document.getElementById("ai-error"),
  resultStale: document.getElementById("ai-result-stale"),
  result: document.getElementById("ai-result"),
};

const missingElements = Object.entries(elements).filter(([, element]) => !element);
if (missingElements.length > 0) {
  throw new Error(`AI 分析页面缺少必要 DOM 节点：${missingElements.map(([name]) => name).join(", ")}`);
}

const PLATFORM_NAMES = {
  baidu: "百度",
  bilibili: "哔哩哔哩",
  douyin: "抖音",
  toutiao: "今日头条",
  weibo: "微博",
  zhihu: "知乎",
};

function platformName(platform) {
  return PLATFORM_NAMES[platform] || platform;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `HTTP ${response.status} ${response.statusText}`.trim());
  }

  return response.json();
}

function normalizeSnapshot(result) {
  return {
    platform: String(result?.platform || "unknown"),
    snapshot_hour: String(result?.snapshot_hour || ""),
    collected_at: String(result?.collected_at || ""),
    items: Array.isArray(result?.items) ? result.items : [],
  };
}

function loadAiSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(AI_SETTINGS_KEY) || "{}");
    elements.apiUrl.value = typeof saved.apiUrl === "string" ? saved.apiUrl : "";
    elements.apiKey.value = typeof saved.apiKey === "string" ? saved.apiKey : "";
    elements.model.value = typeof saved.model === "string" ? saved.model : "";
  } catch {
    elements.apiUrl.value = "";
    elements.apiKey.value = "";
    elements.model.value = "";
  }
}

function saveAiSettings() {
  localStorage.setItem(AI_SETTINGS_KEY, JSON.stringify({
    apiUrl: elements.apiUrl.value.trim(),
    apiKey: elements.apiKey.value.trim(),
    model: elements.model.value.trim(),
  }));
}

function selectedAiPlatforms() {
  return Array.from(elements.platformOptions.querySelectorAll('input[type="checkbox"]:checked'))
    .map((input) => input.value);
}

function syncAllPlatformControl() {
  const controls = Array.from(elements.platformOptions.querySelectorAll('input[type="checkbox"]'));
  const selectedCount = controls.filter((control) => control.checked).length;
  elements.platformAll.checked = controls.length > 0 && selectedCount === controls.length;
  elements.platformAll.indeterminate = selectedCount > 0 && selectedCount < controls.length;
}

function renderPlatformOptions() {
  const previouslySelected = new Set(selectedAiPlatforms());
  const availablePlatforms = [...new Set(state.snapshots.map((snapshot) => snapshot.platform))];
  const controls = availablePlatforms.map((platform) => {
    const label = document.createElement("label");
    label.className = "platform-option";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "ai-platform";
    input.value = platform;
    input.checked = previouslySelected.size === 0 || previouslySelected.has(platform);
    input.addEventListener("change", () => {
      syncAllPlatformControl();
      markResultStale();
    });

    const text = document.createElement("span");
    text.textContent = platformName(platform);
    label.append(input, text);
    return label;
  });

  elements.platformOptions.replaceChildren(...controls);
  syncAllPlatformControl();
}

function currentResultSignature() {
  return JSON.stringify({
    date: state.selectedDate,
    hour: state.selectedHour,
    platforms: selectedAiPlatforms().sort(),
    focus: elements.focus.value.trim(),
  });
}

function markResultStale() {
  elements.resultStale.hidden = !state.resultSignature || state.resultSignature === currentResultSignature();
}

function renderSnapshotSummary() {
  if (!state.selectedDate) {
    elements.snapshotSummary.textContent = "暂无可用快照";
    return;
  }

  const platforms = new Set(state.snapshots.map((snapshot) => snapshot.platform));
  const rawItemCount = state.snapshots.reduce(
    (total, snapshot) => total + snapshot.items.length,
    0,
  );

  if (state.selectedHour === DAY_SCOPE_VALUE) {
    const coveredHours = new Set(
      state.snapshots
        .map((snapshot) => String(snapshot.snapshot_hour || "").slice(11, 13))
        .filter(Boolean),
    );
    const aggregation = aggregateDayTopics(state.snapshots);
    const truncationText = aggregation.truncated
      ? `，按上限提交 ${aggregation.topics.length} 个主题`
      : "，未触发主题上限";
    elements.snapshotSummary.textContent = `${state.selectedDate} 全天，覆盖 ${coveredHours.size} 个实际小时、${platforms.size} 个平台、${rawItemCount} 条原始条目，去重后 ${aggregation.deduplicatedTopicCount} 个主题${truncationText}`;
    return;
  }

  elements.snapshotSummary.textContent = `${state.selectedDate} ${state.selectedHour}:00 精确快照，${platforms.size} 个平台，${rawItemCount} 条热榜`;
}

async function loadHours(preferredHour = "") {
  if (!state.selectedDate) {
    state.selectedHour = "";
    elements.hour.replaceChildren();
    return;
  }

  const requestedDate = state.selectedDate;
  const payload = await requestJson(`/api/history/hours?date=${encodeURIComponent(requestedDate)}`);
  if (requestedDate !== state.selectedDate) return;

  const hours = Array.isArray(payload.hours) ? payload.hours.map(String) : [];
  const options = [
    new Option("全天（汇总当日全部可用快照）", DAY_SCOPE_VALUE),
    ...hours.map((hour) => new Option(`${hour}:00（精确快照）`, hour)),
  ];
  elements.hour.replaceChildren(...options);
  const preferredValue = String(preferredHour);
  state.selectedHour = preferredValue === DAY_SCOPE_VALUE || hours.includes(preferredValue)
    ? preferredValue
    : DAY_SCOPE_VALUE;
  elements.hour.value = state.selectedHour;
}

async function loadAiSnapshot() {
  const requestId = ++state.snapshotRequestId;
  const requestedDate = state.selectedDate;
  const requestedHour = state.selectedHour;

  elements.snapshotError.hidden = true;
  elements.snapshotLoading.hidden = false;

  if (!requestedDate) {
    state.snapshots = [];
    renderPlatformOptions();
    renderSnapshotSummary();
    elements.snapshotLoading.hidden = true;
    return;
  }

  try {
    const params = new URLSearchParams({ date: requestedDate });
    if (requestedHour === DAY_SCOPE_VALUE) {
      params.set("scope", DAY_SCOPE_VALUE);
    } else if (requestedHour) {
      params.set("hour", requestedHour);
    }
    const payload = await requestJson(`/api/history/hot?${params}`);
    if (requestId !== state.snapshotRequestId) return;

    state.snapshots = (payload.results || []).map(normalizeSnapshot);
    renderPlatformOptions();
    renderSnapshotSummary();
    markResultStale();
  } catch (error) {
    if (requestId !== state.snapshotRequestId) return;
    state.snapshots = [];
    renderPlatformOptions();
    renderSnapshotSummary();
    elements.snapshotError.textContent = `全平台快照加载失败：${errorMessage(error)}`;
    elements.snapshotError.hidden = false;
  } finally {
    if (requestId === state.snapshotRequestId) {
      elements.snapshotLoading.hidden = true;
    }
  }
}

function normalizeTopicTitle(value) {
  return String(value || "")
    .normalize("NFKC")
    .trim()
    .replace(/\s+/gu, " ")
    .replace(/^[\p{P}\p{S}]+|[\p{P}\p{S}]+$/gu, "")
    .trim()
    .toLocaleLowerCase("zh-CN");
}

function parseNumericHotValue(value) {
  if (value === undefined || value === null) return null;
  const normalized = String(value).replace(/,/g, "");
  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function aggregateDayTopics(snapshots) {
  const topicsByKey = new Map();
  let rawItemCount = 0;

  const orderedSnapshots = [...snapshots].sort((left, right) => {
    const timeOrder = String(left.snapshot_hour).localeCompare(String(right.snapshot_hour));
    return timeOrder || String(left.platform).localeCompare(String(right.platform));
  });

  orderedSnapshots.forEach((snapshot) => {
    const snapshotHour = String(snapshot.snapshot_hour || "");
    snapshot.items.forEach((item, index) => {
      rawItemCount += 1;
      const originalTitle = String(item?.title || "").trim();
      const topicKey = normalizeTopicTitle(originalTitle);
      if (!topicKey) return;

      const rankValue = Number(item?.rank);
      const rank = Number.isFinite(rankValue) && rankValue > 0 ? rankValue : index + 1;
      const hotValue = parseNumericHotValue(item?.hot_value);
      let topic = topicsByKey.get(topicKey);

      if (!topic) {
        topic = {
          key: topicKey,
          title: originalTitle,
          platforms: new Set(),
          hours: new Set(),
          occurrences: 0,
          bestRank: rank,
          firstSeen: snapshotHour,
          lastSeen: snapshotHour,
          peakHotValue: hotValue,
        };
        topicsByKey.set(topicKey, topic);
      }

      topic.platforms.add(snapshot.platform);
      topic.hours.add(snapshotHour);
      topic.occurrences += 1;
      topic.bestRank = Math.min(topic.bestRank, rank);
      topic.firstSeen = topic.firstSeen && topic.firstSeen < snapshotHour
        ? topic.firstSeen
        : snapshotHour;
      topic.lastSeen = topic.lastSeen && topic.lastSeen > snapshotHour
        ? topic.lastSeen
        : snapshotHour;
      if (hotValue !== null) {
        topic.peakHotValue = topic.peakHotValue === null
          ? hotValue
          : Math.max(topic.peakHotValue, hotValue);
      }
    });
  });

  const compareTopics = (left, right) => (
    right.platforms.size - left.platforms.size
    || right.occurrences - left.occurrences
    || left.bestRank - right.bestRank
    || (right.peakHotValue ?? -Infinity) - (left.peakHotValue ?? -Infinity)
    || left.key.localeCompare(right.key, "zh-CN")
  );

  const sortedTopics = [...topicsByKey.values()].sort(compareTopics);
  const perPlatformCounts = new Map();
  const selectedTopics = [];

  for (const topic of sortedTopics) {
    if (selectedTopics.length >= GLOBAL_TOPIC_LIMIT) break;
    const platforms = [...topic.platforms].sort();
    const hasPlatformCapacity = platforms.some(
      (platform) => (perPlatformCounts.get(platform) || 0) < PLATFORM_TOPIC_LIMIT,
    );
    if (!hasPlatformCapacity) continue;

    selectedTopics.push(topic);
    platforms.forEach((platform) => {
      perPlatformCounts.set(platform, (perPlatformCounts.get(platform) || 0) + 1);
    });
  }

  return {
    rawItemCount,
    deduplicatedTopicCount: sortedTopics.length,
    topics: selectedTopics,
    truncated: selectedTopics.length < sortedTopics.length,
  };
}

function buildSnapshotPrompt(snapshots, focus) {
  const snapshotText = snapshots.map((snapshot) => {
    const items = snapshot.items.map((item) => {
      const rank = item?.rank ?? "-";
      const title = String(item?.title || "未命名热搜");
      const hotValue = item?.hot_value === undefined || item.hot_value === null
        ? ""
        : `，热度 ${item.hot_value}`;
      return `${rank}. ${title}${hotValue}`;
    }).join("\n");
    return `【${platformName(snapshot.platform)}】\n${items || "无榜单条目"}`;
  }).join("\n\n");

  return [
    "请基于以下单个小时的历史热榜精确快照进行中文分析。",
    `快照时间：${state.selectedDate} ${state.selectedHour}:00`,
    `重点分析方向：${focus || DEFAULT_AI_FOCUS}`,
    "请覆盖跨平台热度、共振话题、平台差异、趋势信号、风险与不确定性。不要虚构榜单中不存在的事实。",
    "",
    snapshotText,
  ].join("\n");
}

function buildDayPrompt(snapshots, focus) {
  const aggregation = aggregateDayTopics(snapshots);
  const coveredHours = [...new Set(
    snapshots.map((snapshot) => String(snapshot.snapshot_hour || "").slice(11, 13)),
  )].filter(Boolean).sort();
  const topicText = aggregation.topics.map((topic, index) => {
    const peak = topic.peakHotValue === null ? "无可用热度" : topic.peakHotValue;
    return [
      `${index + 1}. ${topic.title}`,
      `平台：${[...topic.platforms].sort().map(platformName).join("、")}`,
      `出现小时：${[...topic.hours].sort().map((value) => value.slice(11, 13)).join("、")}`,
      `出现次数：${topic.occurrences}`,
      `最佳名次：${topic.bestRank}`,
      `首次出现：${topic.firstSeen}`,
      `最后出现：${topic.lastSeen}`,
      `热度峰值：${peak}`,
    ].join("；");
  }).join("\n");

  return [
    `请对 ${state.selectedDate} 本地时区内00:00至23:59:59的24小时热榜进行全天聚合分析。`,
    `实际覆盖小时：${coveredHours.length} 个（${coveredHours.join("、") || "无"}），缺失小时表示没有可用快照。`,
    `原始条目：${aggregation.rawItemCount} 条；去重主题：${aggregation.deduplicatedTopicCount} 个；提交主题：${aggregation.topics.length} 个。`,
    aggregation.truncated
      ? `已按确定性优先级截断，全局最多 ${GLOBAL_TOPIC_LIMIT} 个主题、每个平台最多 ${PLATFORM_TOPIC_LIMIT} 个主题。`
      : "未触发主题数量上限。",
    `重点分析方向：${focus || DEFAULT_AI_FOCUS}`,
    "请重点分析热点持续时间、升温或降温信号、跨平台扩散路径、首次和最后出现时间、重复出现频次，以及因快照缺失、标题归一化和热度口径不同造成的不确定性。必须区分榜单事实、合理推断和不确定信息，不得虚构。",
    "",
    topicText || "当天没有可分析的聚合主题。",
  ].join("\n");
}

function buildPrompt(snapshots, focus) {
  return state.selectedHour === DAY_SCOPE_VALUE
    ? buildDayPrompt(snapshots, focus)
    : buildSnapshotPrompt(snapshots, focus);
}

function normalizeApiUrl(value) {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/chat/completions") ? trimmed : `${trimmed}/chat/completions`;
}

function renderResult(content) {
  const heading = document.createElement("h3");
  heading.className = "ai-result__title";
  heading.textContent = "分析结果";

  const body = document.createElement("pre");
  body.className = "ai-result__content";
  body.textContent = content;

  elements.result.replaceChildren(heading, body);
  elements.result.hidden = false;
}

async function runAiAnalysis(event) {
  event.preventDefault();
  elements.error.hidden = true;

  const platforms = selectedAiPlatforms();
  if (platforms.length === 0) {
    elements.error.textContent = "请至少选择一个有快照的平台。";
    elements.error.hidden = false;
    return;
  }

  const apiUrl = elements.apiUrl.value.trim();
  const apiKey = elements.apiKey.value.trim();
  const model = elements.model.value.trim();
  if (!apiUrl || !apiKey || !model) {
    elements.error.textContent = "请完整填写 API 地址、API Key 和模型名。";
    elements.error.hidden = false;
    return;
  }

  const snapshots = state.snapshots.filter((snapshot) => platforms.includes(snapshot.platform));
  if (snapshots.length === 0) {
    elements.error.textContent = "所选平台在当前时间没有可分析的快照。";
    elements.error.hidden = false;
    return;
  }

  saveAiSettings();
  state.controller?.abort("superseded");
  const controller = new AbortController();
  state.controller = controller;
  const timeoutId = setTimeout(() => controller.abort("timeout"), AI_TIMEOUT_MS);

  elements.loading.hidden = false;
  elements.analyzeButton.disabled = true;
  elements.cancelButton.disabled = false;
  elements.result.setAttribute("aria-busy", "true");

  try {
    const payload = await requestJson(normalizeApiUrl(apiUrl), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages: [
          {
            role: "system",
            content: "你是严谨的跨平台热榜分析助手。必须区分榜单事实、合理推断和不确定信息。",
          },
          {
            role: "user",
            content: buildPrompt(snapshots, elements.focus.value.trim()),
          },
        ],
      }),
      signal: controller.signal,
    });

    const content = payload?.choices?.[0]?.message?.content;
    if (typeof content !== "string" || !content.trim()) {
      throw new Error("API 未返回可用的分析内容");
    }

    renderResult(content.trim());
    state.resultSignature = currentResultSignature();
    elements.resultStale.hidden = true;
  } catch (error) {
    const timedOut = controller.signal.aborted && controller.signal.reason === "timeout";
    const cancelled = controller.signal.aborted && controller.signal.reason === "cancelled";
    const superseded = controller.signal.aborted && controller.signal.reason === "superseded";

    if (!superseded) {
      elements.error.textContent = timedOut
        ? "AI 分析请求已超时，请检查 API 地址、网络或稍后重试。"
        : cancelled
          ? "AI 分析已取消。"
          : `AI 分析失败：${errorMessage(error)}`;
      elements.error.hidden = false;
    }
  } finally {
    clearTimeout(timeoutId);
    if (state.controller === controller) {
      state.controller = null;
      elements.loading.hidden = true;
      elements.analyzeButton.disabled = false;
      elements.cancelButton.disabled = true;
      elements.result.setAttribute("aria-busy", "false");
    }
  }
}

async function initialize() {
  loadAiSettings();
  elements.snapshotLoading.hidden = false;

  try {
    const payload = await requestJson("/api/history/dates");
    const dates = Array.isArray(payload.dates) ? payload.dates.map(String) : [];
    elements.date.replaceChildren(...dates.map((date) => new Option(date, date)));
    state.selectedDate = dates[0] || "";
    elements.date.value = state.selectedDate;

    if (state.selectedDate) {
      await loadHours();
      await loadAiSnapshot();
    } else {
      state.snapshots = [];
      renderPlatformOptions();
      renderSnapshotSummary();
      elements.snapshotLoading.hidden = true;
    }
  } catch (error) {
    elements.snapshotLoading.hidden = true;
    elements.snapshotError.textContent = `AI 分析页面初始化失败：${errorMessage(error)}`;
    elements.snapshotError.hidden = false;
  }
}

elements.platformAll.addEventListener("change", () => {
  const checked = elements.platformAll.checked;
  elements.platformOptions.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    input.checked = checked;
  });
  syncAllPlatformControl();
  markResultStale();
});

elements.date.addEventListener("change", async () => {
  state.selectedDate = elements.date.value;
  state.snapshotRequestId += 1;
  markResultStale();
  try {
    await loadHours();
    await loadAiSnapshot();
  } catch (error) {
    elements.snapshotLoading.hidden = true;
    elements.snapshotError.textContent = `小时或快照加载失败：${errorMessage(error)}`;
    elements.snapshotError.hidden = false;
  }
});

elements.hour.addEventListener("change", () => {
  state.selectedHour = elements.hour.value;
  markResultStale();
  void loadAiSnapshot();
});

elements.focus.addEventListener("input", markResultStale);
elements.form.addEventListener("submit", runAiAnalysis);
elements.cancelButton.addEventListener("click", () => state.controller?.abort("cancelled"));

void initialize();
