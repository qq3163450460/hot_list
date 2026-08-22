"use strict";

const state = {
  platforms: [],
  results: [],
  selectedPlatform: "all",
  selectedDate: "",
  selectedHour: "",
  loading: false,
  historyRequestId: 0,
  latestRequestId: 0,
};

const elements = {
  filters: document.getElementById("platform-filters"),
  platform: document.getElementById("platform-filter"),
  date: document.getElementById("date-filter"),
  hour: document.getElementById("hour-filter"),
  latest: document.getElementById("latest-button"),
  hotList: document.getElementById("hot-list"),
  loading: document.getElementById("loading-state"),
  empty: document.getElementById("empty-state"),
  error: document.getElementById("global-error"),
  count: document.getElementById("item-count"),
  snapshotAt: document.getElementById("snapshot-at"),
  collectedAt: document.getElementById("collected-at"),
};

const requiredElements = Object.entries(elements).filter(([, element]) => !element);
if (requiredElements.length > 0) {
  throw new Error(`首页缺少必要 DOM 节点：${requiredElements.map(([name]) => name).join(", ")}`);
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

async function requestJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function normalizeResult(result) {
  return {
    platform: String(result?.platform || "unknown"),
    snapshot_hour: String(result?.snapshot_hour || ""),
    collected_at: String(result?.collected_at || ""),
    items: Array.isArray(result?.items) ? result.items : [],
  };
}

function formatTime(value) {
  if (!value) return "暂无时间";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("zh-CN", { hour12: false });
}

function formatUnitValue(value) {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

function formatHotValue(value) {
  const text = nonEmptyText(value);
  if (!text) return "";
  const number = Number(text.replace(/[,，\s]/g, ""));
  if (!Number.isFinite(number) || number < 0) return text;
  if (number >= 1e8) return `${formatUnitValue(number / 1e8)}亿`;
  if (number >= 1e4) return `${formatUnitValue(number / 1e4)}万`;
  return String(Math.round(number));
}

function appendText(parent, tagName, className, value) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  node.textContent = value;
  parent.appendChild(node);
  return node;
}

function nonEmptyText(value) {
  if (typeof value !== "string" && typeof value !== "number") return "";
  return String(value).trim();
}

const TAG_SEPARATOR_PATTERN = /[,，、/／|｜;；]+/;
const MEANINGLESS_TAGS = new Set(["不", "无", "暂无", "未知", "null", "undefined", "none", "n/a", "na", "-"]);

function meaningfulTag(value) {
  const text = nonEmptyText(value);
  if (!text || /^\d+(?:\.\d+)?$/.test(text) || MEANINGLESS_TAGS.has(text.toLowerCase())) return "";
  return text;
}

// Snapshots collected before the spiders translated platform label codes still
// store English text (e.g. Toutiao/Zhihu "hot"/"new"). Normalize them at
// render time so legacy rows match the Chinese badges of fresh data.
const TAG_TEXT_BY_CODE = {
  depth: "深度",
  hot: "热",
  interpretation: "解读",
  new: "新",
  onsite: "现场",
  recentprogress: "进展",
  refuterumors: "辟谣",
};

function normalizeTagText(tag) {
  return TAG_TEXT_BY_CODE[tag.toLocaleLowerCase("zh-CN")] || tag;
}

function flattenTagValues(value) {
  if (Array.isArray(value)) return value.flatMap(flattenTagValues);
  const text = nonEmptyText(value);
  return text ? text.split(TAG_SEPARATOR_PATTERN) : [];
}

function collectItemTags(item, metadata) {
  const candidates = [
    item?.category,
    item?.label,
    item?.labels,
    item?.tags,
    metadata.hot_tag,
    metadata.hotTag,
    metadata.label,
    metadata.labels,
    metadata.tag,
    metadata.tags,
    metadata.hot_label,
    metadata.hotLabel,
    metadata.hot_label_mapping,
  ];
  const seen = new Set();
  const tags = [];
  candidates.flatMap(flattenTagValues).forEach((value) => {
    const tag = normalizeTagText(meaningfulTag(value));
    const key = tag.toLocaleLowerCase("zh-CN");
    if (!tag || seen.has(key)) return;
    seen.add(key);
    tags.push(tag);
  });
  return tags;
}

// Semantic badge colors instead of per-text hash colors: heat words share one
// warm tone, freshness words one cool tone, everything else stays neutral so
// long lists keep a calm, uniform look across platforms.
const TAG_STYLE_HEAT = ["#dc2626", "#fee2e2"];
const TAG_STYLE_FRESH = ["#047857", "#d1fae5"];
const TAG_STYLE_NEUTRAL = ["#526078", "#eef2f7"];
const HEAT_TAG_TEXTS = new Set(["热", "爆", "沸"]);
const FRESH_TAG_TEXTS = new Set(["新", "首发"]);

function tagStyleFor(text) {
  if (HEAT_TAG_TEXTS.has(text)) return TAG_STYLE_HEAT;
  if (FRESH_TAG_TEXTS.has(text)) return TAG_STYLE_FRESH;
  return TAG_STYLE_NEUTRAL;
}

function appendMetaChip(parent, value) {
  const text = meaningfulTag(value);
  if (!text) return null;
  const chip = appendText(parent, "span", "meta-chip", text);
  const [foreground, background] = tagStyleFor(text);
  chip.style.setProperty("--tag-color", foreground);
  chip.style.setProperty("--tag-background", background);
  return chip;
}

function appendLabelImageChip(parent, imageUrl, fallbackText, title) {
  const chip = document.createElement("span");
  chip.className = "meta-chip meta-chip--image";
  const [foreground, background] = tagStyleFor(fallbackText || "标签");
  chip.style.setProperty("--tag-color", foreground);
  chip.style.setProperty("--tag-background", background);

  const image = document.createElement("img");
  image.className = "hot-label-image";
  image.src = `/api/image-proxy?url=${encodeURIComponent(imageUrl)}`;
  image.alt = fallbackText;
  image.title = title;
  image.loading = "lazy";
  image.addEventListener("error", () => {
    chip.textContent = fallbackText;
  }, { once: true });
  chip.appendChild(image);
  parent.appendChild(chip);
  return chip;
}

function createItemImage(imageUrl, title, className = "hot-item__image") {
  const image = document.createElement("img");
  image.className = className;
  image.src = `/api/image-proxy?url=${encodeURIComponent(imageUrl)}`;
  image.alt = "";
  image.loading = "lazy";
  image.addEventListener("error", () => {
    const fallback = appendText(
      document.createDocumentFragment(),
      "span",
      "hot-item__image hot-item__image--fallback",
      "图"
    );
    fallback.setAttribute("aria-label", `${title}图片加载失败`);
    image.replaceWith(fallback);
  }, { once: true });
  return image;
}

function renderItem(item, platform) {
  const row = document.createElement("article");
  row.className = "hot-item";
  row.dataset.platform = platform;
  const isBaidu = platform === "baidu";
  const suppressImages = isBaidu || platform === "douyin" || platform === "zhihu";

  appendText(row, "span", "hot-item__rank", String(item?.rank ?? "-"));

  const content = document.createElement("div");
  content.className = "hot-item__content";

  const title = nonEmptyText(item?.title) || "未命名热搜";
  let titleNode;
  if (item?.url) {
    titleNode = document.createElement("a");
    titleNode.className = "hot-item__title";
    titleNode.href = String(item.url);
    titleNode.target = "_blank";
    titleNode.rel = "noopener noreferrer";
    titleNode.textContent = title;
  } else {
    titleNode = document.createElement("span");
    titleNode.className = "hot-item__title";
    titleNode.textContent = title;
  }
  titleNode.title = title;
  const titleRow = document.createElement("div");
  titleRow.className = "hot-item__title-row";
  titleRow.appendChild(titleNode);

  const metadata = item?.metadata && typeof item.metadata === "object" ? item.metadata : {};
  const primaryImageUrl = nonEmptyText(item?.image_url);
  const labelImageUrl = nonEmptyText(metadata.label_image_url);

  const titleAside = document.createElement("div");
  titleAside.className = "hot-item__title-aside";

  const meta = document.createElement("div");
  meta.className = "hot-item__meta";
  if (platform === "bilibili" && labelImageUrl) {
    appendLabelImageChip(
      meta,
      labelImageUrl,
      nonEmptyText(metadata.hot_label_mapping) || "标签",
      title
    );
  } else {
    collectItemTags(item, metadata).forEach((tag) => appendMetaChip(meta, tag));
  }
  if (meta.childNodes.length > 0) titleAside.appendChild(meta);

  if (item?.hot_value !== undefined && item.hot_value !== null && nonEmptyText(item.hot_value)) {
    const hotValue = document.createElement("span");
    hotValue.className = "hot-item__hot";
    appendText(hotValue, "span", "hot-item__hot-label", "热度");
    appendText(hotValue, "span", "hot-item__hot-value", formatHotValue(item.hot_value));
    titleAside.appendChild(hotValue);
  }
  if (titleAside.childNodes.length > 0) titleRow.appendChild(titleAside);
  content.appendChild(titleRow);

  const details = document.createElement("div");
  details.className = "hot-item__details";

  const imageCandidates = suppressImages ? [] : [
    primaryImageUrl && primaryImageUrl !== labelImageUrl ? primaryImageUrl : "",
    metadata.thumbnail,
    metadata.thumbnail_url,
    metadata.image,
    metadata.image_url,
    ...(Array.isArray(metadata.images) ? metadata.images : []),
    ...(Array.isArray(metadata.image_urls) ? metadata.image_urls : []),
    ...(Array.isArray(metadata.thumbnails) ? metadata.thumbnails : []),
  ];
  const imageUrls = [...new Set(imageCandidates.map(nonEmptyText).filter(Boolean))].slice(0, 3);
  if (imageUrls.length > 0) {
    const gallery = document.createElement("div");
    gallery.className = `hot-item__media hot-item__media--${imageUrls.length}`;
    imageUrls.forEach((imageUrl, index) => {
      const image = createItemImage(imageUrl, `${title} 图片 ${index + 1}`);
      image.alt = imageUrls.length > 1 ? `${title}的第 ${index + 1} 张缩略图` : `${title}的缩略图`;
      gallery.appendChild(image);
    });
    details.appendChild(gallery);
  }

  const description = nonEmptyText(
    item?.description ?? metadata.summary ?? metadata.abstract ?? metadata.description
  );
  if (description) {
    const summary = appendText(details, "p", "hot-item__description", description);
    summary.title = description;
  }

  if (details.childNodes.length > 0) content.appendChild(details);

  row.appendChild(content);
  return row;
}

function renderPlatform(result) {
  const panel = document.createElement("section");
  panel.className = "platform-card";
  panel.setAttribute("aria-label", `${platformName(result.platform)}热榜`);

  const header = document.createElement("header");
  header.className = "platform-card__header";
  appendText(header, "h2", "platform-card__title", platformName(result.platform));
  appendText(header, "span", "platform-card__count", `${result.items.length} 条`);
  panel.appendChild(header);

  const list = document.createElement("div");
  list.className = "platform-card__list";
  result.items.forEach((item) => list.appendChild(renderItem(item, result.platform)));
  panel.appendChild(list);
  return panel;
}

function render() {
  const results = state.results.filter((result) => (
    state.selectedPlatform === "all" || result.platform === state.selectedPlatform
  ));

  elements.hotList.replaceChildren(...results.map(renderPlatform));
  elements.hotList.classList.toggle("platform-grid--single", results.length === 1);

  const itemCount = results.reduce((total, result) => total + result.items.length, 0);
  elements.count.textContent = `${itemCount} 条热搜`;
  elements.snapshotAt.textContent = results[0]?.snapshot_hour
    ? `快照 ${formatTime(results[0].snapshot_hour)}`
    : "暂无快照";
  elements.collectedAt.textContent = results[0]?.collected_at
    ? `采集 ${formatTime(results[0].collected_at)}`
    : "暂无采集时间";
  elements.loading.hidden = !state.loading;
  elements.empty.hidden = state.loading || results.length > 0;
  elements.hotList.setAttribute("aria-busy", String(state.loading));
}

function renderPlatforms() {
  elements.platform.replaceChildren(new Option("全部平台", "all"));
  elements.filters.replaceChildren();

  const platforms = [{ platform: "all", enabled: true }, ...state.platforms];
  platforms.forEach((entry) => {
    if (entry.platform !== "all") {
      elements.platform.add(new Option(platformName(entry.platform), entry.platform));
    }

    const button = document.createElement("button");
    button.type = "button";
    button.dataset.platform = entry.platform;
    button.className = `filter-button${entry.platform === state.selectedPlatform ? " is-active" : ""}`;
    button.textContent = entry.platform === "all" ? "全部" : platformName(entry.platform);
    button.disabled = entry.enabled === false;
    button.setAttribute("aria-pressed", String(entry.platform === state.selectedPlatform));
    elements.filters.appendChild(button);
  });

  elements.platform.value = state.selectedPlatform;
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
  elements.hour.replaceChildren(...hours.map((hour) => new Option(`${hour}:00`, hour)));
  state.selectedHour = hours.includes(String(preferredHour)) ? String(preferredHour) : (hours[0] || "");
  elements.hour.value = state.selectedHour;
}

async function loadHistory() {
  if (!state.selectedDate) {
    state.results = [];
    render();
    return;
  }

  const requestId = ++state.historyRequestId;
  const requestedDate = state.selectedDate;
  const requestedHour = state.selectedHour;
  const requestedPlatform = state.selectedPlatform;
  state.loading = true;
  elements.error.hidden = true;
  render();

  try {
    const params = new URLSearchParams({ date: requestedDate });
    if (requestedHour) params.set("hour", requestedHour);
    if (requestedPlatform !== "all") params.set("platform", requestedPlatform);
    const payload = await requestJson(`/api/history/hot?${params}`);
    if (requestId !== state.historyRequestId) return;
    state.results = (payload.results || []).map(normalizeResult);
  } catch (error) {
    if (requestId !== state.historyRequestId) return;
    state.results = [];
    elements.error.textContent = `历史热榜加载失败：${error instanceof Error ? error.message : String(error)}`;
    elements.error.hidden = false;
  } finally {
    if (requestId === state.historyRequestId) {
      state.loading = false;
      render();
    }
  }
}

async function loadLatest() {
  const requestId = ++state.latestRequestId;
  elements.latest.disabled = true;
  elements.error.hidden = true;

  try {
    const payload = await requestJson("/api/history/latest");
    if (requestId !== state.latestRequestId) return;

    const latestResults = (payload.results || []).map(normalizeResult);
    const snapshotHour = latestResults.reduce((latest, result) => {
      const candidate = String(result.snapshot_hour || "");
      return candidate > latest ? candidate : latest;
    }, "");
    if (!snapshotHour) {
      state.results = latestResults;
      render();
      return;
    }

    state.selectedDate = snapshotHour.slice(0, 10);
    elements.date.value = state.selectedDate;
    await loadHours(snapshotHour.slice(11, 13));
    if (requestId !== state.latestRequestId) return;
    await loadHistory();
  } catch (error) {
    if (requestId !== state.latestRequestId) return;
    elements.error.textContent = `最新热榜加载失败：${error instanceof Error ? error.message : String(error)}`;
    elements.error.hidden = false;
  } finally {
    if (requestId === state.latestRequestId) elements.latest.disabled = false;
  }
}

async function initialize() {
  state.loading = true;
  render();

  try {
    const [platforms, dates] = await Promise.all([
      requestJson("/api/platforms"),
      requestJson("/api/history/dates"),
    ]);
    state.platforms = Array.isArray(platforms) ? platforms : [];
    renderPlatforms();

    const availableDates = Array.isArray(dates.dates) ? dates.dates.map(String) : [];
    elements.date.replaceChildren(...availableDates.map((value) => new Option(value, value)));
    state.selectedDate = availableDates[0] || "";
    elements.date.value = state.selectedDate;

    if (state.selectedDate) {
      await loadHours();
      await loadHistory();
    }
  } catch (error) {
    elements.error.textContent = `初始化失败：${error instanceof Error ? error.message : String(error)}`;
    elements.error.hidden = false;
  } finally {
    state.loading = false;
    render();
  }
}

elements.date.addEventListener("change", async () => {
  state.selectedDate = elements.date.value;
  await loadHours();
  await loadHistory();
});

elements.hour.addEventListener("change", () => {
  state.selectedHour = elements.hour.value;
  void loadHistory();
});

elements.platform.addEventListener("change", () => {
  state.selectedPlatform = elements.platform.value;
  renderPlatforms();
  void loadHistory();
});

elements.filters.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  const button = target.closest("button[data-platform]");
  if (!(button instanceof HTMLButtonElement) || button.disabled) return;
  state.selectedPlatform = button.dataset.platform || "all";
  renderPlatforms();
  void loadHistory();
});

elements.latest.addEventListener("click", () => void loadLatest());

void initialize();
