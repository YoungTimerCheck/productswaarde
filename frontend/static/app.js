const API_BASE = "";
const DEFAULT_TIMEOUT_MS = 15000;

async function fetchJSON(path, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(API_BASE + path, { signal: controller.signal });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timeout);
  }
}

function isMarktplaatsUrl(value) {
  try {
    const url = new URL(value);
    return url.hostname.endsWith("marktplaats.nl") && url.pathname.startsWith("/v/");
  } catch {
    return false;
  }
}

function initHomeSearch() {
  const searchForm = document.getElementById("search-form");
  if (searchForm) {
    searchForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const q = document.getElementById("search-input").value.trim();
      if (q) window.location.href = `results.html?q=${encodeURIComponent(q)}`;
    });
  }

  const urlForm = document.getElementById("url-form");
  if (urlForm) {
    urlForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const url = document.getElementById("url-input").value.trim();
      const errorEl = document.getElementById("url-error");
      if (!isMarktplaatsUrl(url)) {
        if (errorEl) errorEl.classList.remove("hidden");
        return;
      }
      if (errorEl) errorEl.classList.add("hidden");
      window.location.href = `listing.html?url=${encodeURIComponent(url)}`;
    });
  }
}

async function loadLiveCounter() {
  const el = document.getElementById("live-counter");
  if (!el) return;
  try {
    const data = await fetchJSON("/api/categories");
    const total = data.categories.reduce((sum, c) => sum + c.active_listings, 0);
    el.innerHTML = `<span aria-hidden="true">📊</span><span><span class="font-bold text-emerald-600">${total.toLocaleString("nl-NL")}</span> advertenties gevolgd</span>`;
  } catch {
    el.classList.add("hidden");
  }
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function setMetaDescription(text) {
  let tag = document.querySelector('meta[name="description"]');
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute("name", "description");
    document.head.appendChild(tag);
  }
  tag.setAttribute("content", text);
}

function formatEUR(value) {
  if (value === null || value === undefined) return null;
  return new Intl.NumberFormat("nl-NL", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

function dealScoreClasses(dealScore) {
  if (!dealScore) return "bg-gray-100 text-gray-600 border-gray-200";
  if (dealScore.includes("Goede deal")) return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (dealScore.includes("Te duur")) return "bg-red-50 text-red-600 border-red-200";
  return "bg-amber-50 text-amber-700 border-amber-200";
}

// A median from a mismatched keyword/category (e.g. a car part matched against a whole
// car's median, or a roofing strip against a full solar-panel-system median) produces a
// technically-computed but meaningless comparison. Treat more than a 10x gap either way
// as "not really the same product" and refuse to present it as a scored comparison.
function hasReliableMedian(price, median) {
  return Boolean(price && median && price <= median * 10 && median <= price * 10);
}

function listingCardHTML(listing) {
  const flags = [];
  if (listing.negotiation_tip) {
    flags.push(
      `<span class="inline-flex items-center gap-1 text-xs font-medium text-orange-600 bg-orange-50 border border-orange-200 rounded-full px-2 py-1">💬 Onderhandelen mogelijk</span>`
    );
  }
  if (listing.scam_warning) {
    flags.push(
      `<span class="inline-flex items-center gap-1 text-xs font-medium text-red-600 bg-red-50 border border-red-200 rounded-full px-2 py-1">⚠️ Wees alert</span>`
    );
  }
  if (listing.bidding) {
    flags.push(
      `<span class="inline-flex items-center gap-1 text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 rounded-full px-2 py-1">🔨 ${escapeHTML(listing.price_type_label || "Bieden")}</span>`
    );
  }

  const image = listing.image_url
    ? `<img src="${escapeHTML(listing.image_url)}" alt="${escapeHTML(listing.title)}" class="h-40 w-full object-cover rounded-t-xl bg-gray-100" loading="lazy" />`
    : `<div class="h-40 w-full rounded-t-xl bg-gray-100 flex items-center justify-center text-gray-400 text-sm">Geen foto</div>`;

  const priceLabel = listing.price ? formatEUR(listing.price) : listing.price_type_label || "Prijs onbekend";
  const daysLabel = listing.days_listed === 0 ? "Vandaag geplaatst" : `${listing.days_listed}d geleden geplaatst`;

  return `
    <div class="bg-white border border-gray-200 shadow-sm rounded-xl overflow-hidden hover:shadow-md hover:border-emerald-300 transition flex flex-col">
      ${image}
      <div class="p-4 flex flex-col gap-2 flex-1">
        <h3 class="font-semibold text-gray-900 text-sm leading-snug line-clamp-2 min-h-[2.5rem]">${escapeHTML(listing.title)}</h3>
        <div class="flex items-center justify-between gap-2">
          <span class="text-lg font-bold text-gray-900">${priceLabel}</span>
          ${listing.deal_score && hasReliableMedian(listing.price, listing.median_price) ? `<span class="text-xs font-semibold border rounded-full px-2 py-1 whitespace-nowrap ${dealScoreClasses(listing.deal_score)}">${listing.deal_score}</span>` : ""}
        </div>
        <div class="text-xs text-gray-500 flex flex-wrap gap-x-3 gap-y-1">
          ${listing.condition ? `<span>${escapeHTML(listing.condition)}</span>` : ""}
          ${listing.location ? `<span>📍 ${escapeHTML(listing.location)}</span>` : ""}
          <span>${daysLabel}</span>
        </div>
        ${flags.length ? `<div class="flex flex-wrap gap-1.5">${flags.join("")}</div>` : ""}
        <a href="${escapeHTML(listing.url)}" target="_blank" rel="noopener" class="mt-auto pt-2 text-center text-sm font-semibold text-emerald-600 hover:text-emerald-700">
          Bekijk op Marktplaats →
        </a>
      </div>
    </div>`;
}

function priceRangeBarHTML(p25, median, p75) {
  if (!p25 || !median || !p75) return "";
  const max = p75 * 1.3;
  const pct = (value) => Math.min(100, (value / max) * 100);
  return `
    <div class="relative h-3 rounded-full bg-gray-100">
      <div class="absolute inset-y-0 rounded-full bg-emerald-100" style="left:${pct(p25)}%; right:${100 - pct(p75)}%;"></div>
      <div class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-4 w-1 rounded-full bg-emerald-600" style="left:${pct(median)}%;"></div>
    </div>
    <div class="mt-1 flex justify-between text-xs text-gray-500">
      <span>${formatEUR(p25)}</span>
      <span class="font-semibold text-emerald-700">Mediaan: ${formatEUR(median)}</span>
      <span>${formatEUR(p75)}</span>
    </div>`;
}

async function initResultsPage() {
  const root = document.getElementById("results-root");
  if (!root) return;

  const keyword = (getQueryParam("q") || "").trim();
  const searchInput = document.getElementById("search-input");
  if (searchInput) searchInput.value = keyword;

  const loadingEl = document.getElementById("results-loading");
  const errorEl = document.getElementById("results-error");
  const contentEl = document.getElementById("results-content");

  if (!keyword) {
    loadingEl.classList.add("hidden");
    errorEl.textContent = "Geen zoekopdracht opgegeven.";
    errorEl.classList.remove("hidden");
    return;
  }

  document.getElementById("results-keyword").textContent = keyword;
  document.title = `${keyword} prijs Marktplaats | Productswaarde`;
  setMetaDescription(`Wat is een eerlijke prijs voor ${keyword} op Marktplaats? Bekijk de gemiddelde prijs en actuele aanbiedingen.`);

  let data;
  try {
    data = await fetchJSON(`/api/search?q=${encodeURIComponent(keyword)}`);
  } catch {
    data = { source: "error", message: "Zoekopdracht tijdelijk niet beschikbaar. Probeer het over enkele minuten opnieuw." };
  }

  loadingEl.classList.add("hidden");

  if (data.source === "error") {
    errorEl.textContent = data.message;
    errorEl.classList.remove("hidden");
    return;
  }

  contentEl.classList.remove("hidden");

  const alertLink = document.getElementById("alert-cta");
  if (alertLink) alertLink.href = `alerts.html?keyword=${encodeURIComponent(keyword)}`;

  document.getElementById("results-listings").innerHTML = data.listings.map(listingCardHTML).join("");

  if (data.source === "live") {
    document.getElementById("results-live-notice").classList.remove("hidden");
    return;
  }

  document.getElementById("results-stats-section").classList.remove("hidden");
  renderDatabaseStats(data.stats);
  await renderPriceHistory(keyword);
}

function renderDatabaseStats(stats) {
  document.getElementById("stat-avg-price").textContent = formatEUR(stats.avg_price) || "–";
  document.getElementById("stat-active-listings").textContent = stats.active_listings.toLocaleString("nl-NL");
  document.getElementById("price-range-bar").innerHTML = priceRangeBarHTML(stats.p25_price, stats.median_price, stats.p75_price);
}

async function renderPriceHistory(keyword) {
  let data;
  try {
    data = await fetchJSON(`/api/stats/${encodeURIComponent(keyword)}`);
  } catch {
    return;
  }

  const history = data.price_history || [];
  const trendEl = document.getElementById("stat-trend");
  const bestMomentEl = document.getElementById("best-moment");

  if (history.length < 2) {
    trendEl.textContent = "–";
    bestMomentEl.className = "bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-600";
    bestMomentEl.textContent = "We volgen deze prijs nog maar net. Kom over een paar dagen terug voor een prijstrend.";
    return;
  }

  const first = history[0].median_price;
  const last = history[history.length - 1].median_price;
  const change = ((last - first) / first) * 100;

  trendEl.textContent = `${change > 0 ? "↑" : change < 0 ? "↓" : "→"} ${Math.abs(change).toFixed(1)}%`;
  trendEl.className = `text-xl font-bold ${change < 0 ? "text-emerald-600" : change > 0 ? "text-orange-500" : "text-gray-500"}`;

  if (change < -2) {
    bestMomentEl.className = "bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-700 font-medium";
    bestMomentEl.textContent = "📉 Prijzen dalen — mogelijk een goed moment om te kopen.";
  } else if (change > 2) {
    bestMomentEl.className = "bg-orange-50 border border-orange-200 rounded-xl p-4 text-sm text-orange-600 font-medium";
    bestMomentEl.textContent = "📈 Prijzen stijgen — wachten kan lonen.";
  } else {
    bestMomentEl.className = "bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-600";
    bestMomentEl.textContent = "Prijzen zijn de laatste tijd stabiel.";
  }

  const canvas = document.getElementById("price-chart");
  if (canvas && window.Chart) {
    document.getElementById("price-chart-section").classList.remove("hidden");
    new Chart(canvas, {
      type: "line",
      data: {
        labels: history.map((h) => h.date),
        datasets: [
          {
            label: "Mediaanprijs",
            data: history.map((h) => h.median_price),
            borderColor: "#059669",
            backgroundColor: "rgba(5, 150, 105, 0.1)",
            tension: 0.3,
            fill: true,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { callback: (v) => `€${v}` } },
        },
      },
    });
  }
}

function factItem(label, value) {
  if (!value) return "";
  return `<div><div class="text-xs text-gray-500">${escapeHTML(label)}</div><div class="mt-0.5 font-medium text-gray-900">${escapeHTML(value)}</div></div>`;
}

function comparisonBarHTML(price, median, dealScore) {
  if (!price || !median) return "";
  const max = Math.max(price, median) * 1.3;
  const pricePct = Math.min(100, (price / max) * 100);
  const medianPct = Math.min(100, (median / max) * 100);
  const barColor = dealScore && dealScore.includes("Goede deal")
    ? "bg-emerald-500"
    : dealScore && dealScore.includes("Te duur")
      ? "bg-red-500"
      : "bg-amber-500";
  return `
    <div class="relative h-3 rounded-full bg-gray-100">
      <div class="absolute inset-y-0 left-0 rounded-full ${barColor}" style="width:${pricePct}%;"></div>
      <div class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-5 w-1 rounded-full bg-gray-700" style="left:${medianPct}%;"></div>
    </div>
    <div class="mt-2 flex justify-between text-xs text-gray-500">
      <span>Deze advertentie: <strong class="text-gray-900">${formatEUR(price)}</strong></span>
      <span>Marktmediaan: <strong class="text-gray-900">${formatEUR(median)}</strong></span>
    </div>`;
}

function warningFlagsHTML(listing) {
  const items = [];
  if (listing.negotiation_tip) {
    items.push(`
      <div class="flex items-start gap-3 bg-orange-50 border border-orange-200 rounded-xl p-4">
        <span class="text-xl" aria-hidden="true">💬</span>
        <div>
          <div class="font-semibold text-orange-700">Onderhandelen mogelijk</div>
          <div class="text-sm text-orange-600 mt-0.5">Deze advertentie staat al ${listing.days_listed} dagen online. Een bod onder de vraagprijs is het proberen waard.</div>
        </div>
      </div>`);
  }
  if (listing.scam_warning) {
    items.push(`
      <div class="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-4">
        <span class="text-xl" aria-hidden="true">⚠️</span>
        <div>
          <div class="font-semibold text-red-600">Wees alert</div>
          <div class="text-sm text-red-600 mt-0.5">De prijs ligt opvallend ver onder de marktprijs. Wees extra voorzichtig en betaal nooit vooraf via een onbekende betaalmethode.</div>
        </div>
      </div>`);
  }
  if (listing.bidding) {
    items.push(`
      <div class="flex items-start gap-3 bg-gray-50 border border-gray-200 rounded-xl p-4">
        <span class="text-xl" aria-hidden="true">🔨</span>
        <div>
          <div class="font-semibold text-gray-700">${escapeHTML(listing.price_type_label || "Bieden")}</div>
          <div class="text-sm text-gray-600 mt-0.5">De uiteindelijke prijs kan hoger uitvallen dan het getoonde bedrag.</div>
        </div>
      </div>`);
  }
  if (!items.length) {
    items.push(`
      <div class="flex items-start gap-3 bg-emerald-50 border border-emerald-200 rounded-xl p-4">
        <span class="text-xl" aria-hidden="true">✅</span>
        <div class="text-sm text-emerald-700 font-medium">Geen waarschuwingen gevonden voor deze advertentie.</div>
      </div>`);
  }
  return items.join("");
}

function guessKeywordFromTitle(title) {
  const words = (title.match(/[A-Za-z0-9]+/g) || []).slice(0, 3);
  return words.join(" ").toLowerCase();
}

async function loadSimilarListings(listing) {
  const section = document.getElementById("similar-listings-section");
  const container = document.getElementById("similar-listings");
  const keywordGuess = guessKeywordFromTitle(listing.title || "");
  if (!keywordGuess) return;

  try {
    const data = await fetchJSON(`/api/search?q=${encodeURIComponent(keywordGuess)}`);
    if (data.source === "error") return;
    const similar = data.listings
      .filter((item) => item.marktplaats_id !== listing.marktplaats_id)
      .slice(0, 5);
    if (!similar.length) return;
    container.innerHTML = similar.map(listingCardHTML).join("");
    section.classList.remove("hidden");
  } catch {
    // Similar listings are a nice-to-have; skip silently if this fails.
  }
}

function renderListingDetail(listing) {
  document.title = `${listing.title || "Advertentie"} | Productswaarde`;

  const imageWrap = document.getElementById("listing-image-wrap");
  imageWrap.innerHTML = listing.image_url
    ? `<img src="${escapeHTML(listing.image_url)}" alt="${escapeHTML(listing.title)}" class="h-72 sm:h-96 w-full object-cover rounded-xl bg-gray-100" />`
    : `<div class="h-72 sm:h-96 w-full rounded-xl bg-gray-100 flex items-center justify-center text-gray-400">Geen foto beschikbaar</div>`;

  document.getElementById("listing-title").textContent = listing.title || "Advertentie";
  document.getElementById("listing-price").textContent = listing.price
    ? formatEUR(listing.price)
    : listing.price_type_label || "Prijs onbekend";

  const reliableMedian = hasReliableMedian(listing.price, listing.median_price);

  const badge = document.getElementById("listing-deal-badge");
  if (reliableMedian && listing.deal_score) {
    badge.textContent = listing.deal_score;
    badge.className = `inline-flex text-base sm:text-lg font-bold border rounded-full px-4 py-2 ${dealScoreClasses(listing.deal_score)}`;
  } else {
    badge.classList.add("hidden");
  }

  const discountEl = document.getElementById("listing-discount");
  if (!reliableMedian) {
    discountEl.textContent = listing.median_price
      ? "Onvoldoende data voor eerlijke vergelijking."
      : "Nog niet genoeg marktdata om te vergelijken.";
  } else if (typeof listing.discount_percent === "number") {
    const pct = Math.abs(listing.discount_percent).toFixed(1);
    if (listing.discount_percent > 0.5) discountEl.textContent = `${pct}% onder de mediaanprijs voor dit product`;
    else if (listing.discount_percent < -0.5) discountEl.textContent = `${pct}% boven de mediaanprijs voor dit product`;
    else discountEl.textContent = "Ongeveer gelijk aan de mediaanprijs";
  } else {
    discountEl.textContent = "Nog niet genoeg marktdata om te vergelijken.";
  }

  document.getElementById("listing-comparison-bar").innerHTML = reliableMedian
    ? comparisonBarHTML(listing.price, listing.median_price, listing.deal_score)
    : `<p class="text-sm text-gray-500">Onvoldoende data voor eerlijke vergelijking — deze advertentie lijkt niet goed te matchen met de vergeleken zoekterm.</p>`;

  document.getElementById("listing-facts").innerHTML = [
    factItem("Conditie", listing.condition),
    factItem("Verkoper", listing.seller_type === "bedrijf" ? "Bedrijf" : "Particulier"),
    factItem("Geplaatst", listing.days_listed === 0 ? "Vandaag" : `${listing.days_listed} dagen geleden`),
    factItem("Locatie", listing.location),
    factItem("Prijstype", listing.price_type_label),
    factItem("Categorie", listing.category_name),
  ].join("");

  document.getElementById("listing-warnings").innerHTML = warningFlagsHTML(listing);

  const cta = document.getElementById("listing-cta");
  cta.href = listing.url;

  injectListingJsonLd(listing);
}

function schemaCondition(condition) {
  const c = (condition || "").toLowerCase();
  if (c === "nieuw") return "https://schema.org/NewCondition";
  if (c.includes("refurbished")) return "https://schema.org/RefurbishedCondition";
  if (c.includes("defect") || c.includes("beschadigd")) return "https://schema.org/DamagedCondition";
  return "https://schema.org/UsedCondition";
}

function injectListingJsonLd(listing) {
  document.getElementById("listing-jsonld")?.remove();

  const data = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: listing.title,
    ...(listing.image_url ? { image: [listing.image_url] } : {}),
    ...(listing.condition ? { itemCondition: schemaCondition(listing.condition) } : {}),
    offers: {
      "@type": "Offer",
      url: listing.url,
      priceCurrency: "EUR",
      price: listing.price ?? 0,
      availability: "https://schema.org/InStock",
    },
  };

  const script = document.createElement("script");
  script.type = "application/ld+json";
  script.id = "listing-jsonld";
  script.textContent = JSON.stringify(data);
  document.head.appendChild(script);
}

async function initListingPage() {
  const root = document.getElementById("listing-root");
  if (!root) return;

  const url = getQueryParam("url");
  const loadingEl = document.getElementById("listing-loading");
  const errorEl = document.getElementById("listing-error");
  const contentEl = document.getElementById("listing-content");

  if (!url) {
    loadingEl.classList.add("hidden");
    errorEl.textContent = "Geen advertentielink opgegeven. Plak een Marktplaats-link op de homepage.";
    errorEl.classList.remove("hidden");
    return;
  }

  let listing;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}/api/listing?url=${encodeURIComponent(url)}`, { signal: controller.signal });
    const body = await res.json();
    if (!res.ok) {
      loadingEl.classList.add("hidden");
      errorEl.textContent = body.detail || "Kon deze advertentie niet analyseren.";
      errorEl.classList.remove("hidden");
      return;
    }
    listing = body.listing;
  } catch (err) {
    loadingEl.classList.add("hidden");
    errorEl.textContent = err.name === "AbortError"
      ? "Dit duurt langer dan verwacht. Probeer het over enkele minuten opnieuw."
      : "Zoekopdracht tijdelijk niet beschikbaar. Probeer het over enkele minuten opnieuw.";
    errorEl.classList.remove("hidden");
    return;
  } finally {
    clearTimeout(timeout);
  }

  loadingEl.classList.add("hidden");
  contentEl.classList.remove("hidden");
  renderListingDetail(listing);
  loadSimilarListings(listing);
}

function timeAgoLabel(isoString) {
  if (!isoString) return "onbekend";
  const diffMin = Math.round((Date.now() - new Date(isoString).getTime()) / 60000);
  if (diffMin < 1) return "zojuist";
  if (diffMin < 60) return `${diffMin} minuten geleden`;
  const diffHours = Math.round(diffMin / 60);
  if (diffHours < 24) return `${diffHours} uur geleden`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} ${diffDays === 1 ? "dag" : "dagen"} geleden`;
}

function renderDealFilters(categories) {
  const container = document.getElementById("deals-filters");
  const activeClasses = ["bg-emerald-600", "text-white"];
  const inactiveClasses = ["bg-white", "text-gray-700", "border", "border-gray-200", "hover:border-emerald-300"];

  const buttonHTML = (category, label, active) =>
    `<button type="button" data-category="${escapeHTML(category)}" class="px-4 py-2 rounded-full text-sm font-semibold transition ${(active ? activeClasses : inactiveClasses).join(" ")}">${escapeHTML(label)}</button>`;

  container.innerHTML = [buttonHTML("all", "Alle", true)]
    .concat(categories.map((c) => buttonHTML(c, c, false)))
    .join("");

  container.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-category]");
    if (!btn) return;
    container.querySelectorAll("button").forEach((b) => {
      b.className = `px-4 py-2 rounded-full text-sm font-semibold transition ${inactiveClasses.join(" ")}`;
    });
    btn.className = `px-4 py-2 rounded-full text-sm font-semibold transition ${activeClasses.join(" ")}`;

    applyDealsFilter(btn.dataset.category);
  });
}

let allDeals = [];

function applyDealsFilter(category) {
  const filtered = category === "all" ? allDeals : allDeals.filter((d) => d.category_group === category);
  document.getElementById("deals-grid").innerHTML = filtered.map(listingCardHTML).join("");
  document.getElementById("deals-empty-filtered").classList.toggle("hidden", filtered.length > 0);
}

async function initDealsPage() {
  const root = document.getElementById("deals-root");
  if (!root) return;

  const loadingEl = document.getElementById("deals-loading");
  const errorEl = document.getElementById("deals-error");
  const contentEl = document.getElementById("deals-content");

  let data;
  try {
    data = await fetchJSON("/api/deals?limit=40");
  } catch {
    loadingEl.classList.add("hidden");
    errorEl.textContent = "Deals konden niet worden geladen. Probeer het later opnieuw.";
    errorEl.classList.remove("hidden");
    return;
  }

  loadingEl.classList.add("hidden");
  contentEl.classList.remove("hidden");
  document.getElementById("deals-updated").textContent = `Bijgewerkt ${timeAgoLabel(data.updated_at)}`;

  // Same reliability guard as the listing-detail page: a "Goede deal" score built on a
  // median from a mismatched product (different category matched under the same keyword)
  // isn't a real deal, so it's excluded rather than shown with a misleading badge.
  allDeals = (data.deals || []).filter((d) => hasReliableMedian(d.price, d.median_price));

  if (!allDeals.length) {
    document.getElementById("deals-empty").classList.remove("hidden");
    return;
  }

  const categories = [...new Set(allDeals.map((d) => d.category_group).filter(Boolean))].sort();
  renderDealFilters(categories);
  applyDealsFilter("all");
}

function showAlertSuccess(keyword, maxPrice) {
  document.getElementById("alert-form-card").classList.add("hidden");
  const el = document.getElementById("alert-result");
  el.innerHTML = `
    <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-6 text-center">
      <div class="text-3xl" aria-hidden="true">✅</div>
      <h2 class="mt-2 text-lg font-bold text-emerald-700">Prijsalert aangemaakt</h2>
      <p class="mt-2 text-sm text-emerald-700">Je ontvangt een melding zodra er een advertentie verschijnt voor <strong>"${escapeHTML(keyword)}"</strong> onder <strong>${formatEUR(maxPrice)}</strong>.</p>
      <p class="mt-3 text-xs text-emerald-600">We hebben een bevestiging gestuurd naar je e-mailadres. Je kunt je op elk moment uitschrijven via de link in die e-mail.</p>
    </div>`;
  el.classList.remove("hidden");
}

function showAlertUpgradePrompt() {
  document.getElementById("alert-form-card").classList.add("hidden");
  const el = document.getElementById("alert-result");
  el.innerHTML = `
    <div class="bg-orange-50 border border-orange-200 rounded-xl p-6 text-center">
      <div class="text-3xl" aria-hidden="true">🔒</div>
      <h2 class="mt-2 text-lg font-bold text-orange-600">Je hebt het maximum van 2 gratis alerts bereikt</h2>
      <p class="mt-2 text-sm text-orange-600">Upgrade naar Pro (€2,99/maand) voor onbeperkte prijsalerts en meldingen binnen 1 uur in plaats van 4 uur.</p>
    </div>`;
  el.classList.remove("hidden");
}

function initAlertsPage() {
  const form = document.getElementById("alert-form");
  if (!form) return;

  const keywordInput = document.getElementById("alert-keyword");
  const prefill = getQueryParam("keyword");
  if (prefill) keywordInput.value = prefill;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const submitBtn = document.getElementById("alert-submit");
    const errorEl = document.getElementById("alert-form-error");
    errorEl.classList.add("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "Bezig...";

    const keyword = keywordInput.value.trim();
    const maxPrice = parseFloat(document.getElementById("alert-max-price").value);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
    try {
      const res = await fetch(`${API_BASE}/api/alerts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword,
          max_price: maxPrice,
          email: document.getElementById("alert-email").value.trim(),
        }),
        signal: controller.signal,
      });
      const body = await res.json().catch(() => ({}));

      if (res.status === 403) {
        showAlertUpgradePrompt();
        return;
      }
      if (!res.ok) {
        errorEl.textContent = body.detail || "Er ging iets mis. Probeer het later opnieuw.";
        errorEl.classList.remove("hidden");
        return;
      }
      showAlertSuccess(keyword, maxPrice);
    } catch (err) {
      errorEl.textContent = err.name === "AbortError"
        ? "Dit duurt langer dan verwacht. Probeer het later opnieuw."
        : "Er ging iets mis. Probeer het later opnieuw.";
      errorEl.classList.remove("hidden");
    } finally {
      clearTimeout(timeout);
      submitBtn.disabled = false;
      submitBtn.textContent = "Maak alert aan";
    }
  });
}

// Maps the homepage's simplified category slugs to Marktplaats' real top-level group
// names (from analyzer.py's TOP_LEVEL_CATEGORIES) so /api/categories and /api/deals
// results can be filtered per landing page.
const CATEGORY_SLUGS = {
  smartphones: { label: "Smartphones", icon: "📱", groups: ["Telecommunicatie"] },
  laptops: { label: "Laptops", icon: "💻", groups: ["Computers en Software"] },
  fietsen: { label: "Fietsen", icon: "🚲", groups: ["Fietsen en Brommers"] },
  gaming: { label: "Gaming", icon: "🎮", groups: ["Spelcomputers en Games"] },
  cameras: { label: "Camera's", icon: "📷", groups: ["Audio, Tv en Foto"] },
  meubels: { label: "Meubels", icon: "🛋️", groups: ["Huis en Inrichting"] },
  kleding: { label: "Kleding", icon: "👕", groups: ["Kleding | Dames", "Kleding | Heren"] },
  autos: { label: "Auto's", icon: "🚗", groups: ["Auto's"] },
};

async function initCategoryPage() {
  const root = document.getElementById("category-root");
  if (!root) return;

  const slug = (getQueryParam("name") || "").toLowerCase();
  const meta = CATEGORY_SLUGS[slug];

  const loadingEl = document.getElementById("category-loading");
  const notFoundEl = document.getElementById("category-not-found");
  const errorEl = document.getElementById("category-error");
  const contentEl = document.getElementById("category-content");

  if (!meta) {
    loadingEl.classList.add("hidden");
    notFoundEl.classList.remove("hidden");
    return;
  }

  document.getElementById("category-icon").textContent = meta.icon;
  document.getElementById("category-name").textContent = meta.label;
  document.title = `${meta.label} tweedehands prijzen | Productswaarde`;
  setMetaDescription(`Wat zijn eerlijke prijzen voor ${meta.label} op Marktplaats? Bekijk trends en actuele deals.`);

  let categoriesData, dealsData;
  try {
    [categoriesData, dealsData] = await Promise.all([
      fetchJSON("/api/categories"),
      fetchJSON("/api/deals?limit=60"),
    ]);
  } catch {
    loadingEl.classList.add("hidden");
    errorEl.classList.remove("hidden");
    return;
  }

  loadingEl.classList.add("hidden");
  contentEl.classList.remove("hidden");

  const matchingGroups = categoriesData.categories.filter((c) => meta.groups.includes(c.name));
  const activeListings = matchingGroups.reduce((sum, c) => sum + c.active_listings, 0);
  const keywords = [...new Set(matchingGroups.flatMap((c) => c.keywords))];

  document.getElementById("category-active-count").textContent = activeListings.toLocaleString("nl-NL");
  document.getElementById("category-keyword-count").textContent = keywords.length.toLocaleString("nl-NL");

  if (!keywords.length) {
    document.getElementById("category-empty").classList.remove("hidden");
    document.getElementById("category-keywords-section").classList.add("hidden");
    return;
  }

  const statsResults = await Promise.all(
    keywords.map((k) => fetchJSON(`/api/stats/${encodeURIComponent(k)}`).catch(() => null))
  );
  const keywordStats = statsResults.filter((s) => s && s.found);

  document.getElementById("category-keywords").innerHTML = keywordStats
    .map((s) => `
      <a href="results.html?q=${encodeURIComponent(s.keyword)}" class="bg-white border border-gray-200 shadow-sm rounded-xl p-4 hover:shadow-md hover:border-emerald-300 transition">
        <div class="font-semibold text-gray-900 text-sm">${escapeHTML(s.keyword)}</div>
        <div class="mt-1 text-lg font-bold text-emerald-600">${formatEUR(s.stats.median_price) || "–"}</div>
        <div class="text-xs text-gray-500">${s.stats.active_listings} advertenties</div>
      </a>`)
    .join("");

  const categoryDeals = dealsData.deals.filter((d) => meta.groups.includes(d.category_group));
  if (categoryDeals.length) {
    document.getElementById("category-deals").innerHTML = categoryDeals.slice(0, 6).map(listingCardHTML).join("");
    document.getElementById("category-deals-section").classList.remove("hidden");
  }

  const topKeyword = keywordStats
    .filter((s) => s.price_history && s.price_history.length >= 2)
    .sort((a, b) => b.stats.active_listings - a.stats.active_listings)[0];

  if (topKeyword && window.Chart) {
    document.getElementById("category-chart-section").classList.remove("hidden");
    document.getElementById("category-chart-caption").textContent = `Gebaseerd op prijstracking van "${topKeyword.keyword}"`;
    new Chart(document.getElementById("category-chart"), {
      type: "line",
      data: {
        labels: topKeyword.price_history.map((h) => h.date),
        datasets: [
          {
            label: "Mediaanprijs",
            data: topKeyword.price_history.map((h) => h.median_price),
            borderColor: "#059669",
            backgroundColor: "rgba(5, 150, 105, 0.1)",
            tension: 0.3,
            fill: true,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { ticks: { callback: (v) => `€${v}` } } },
      },
    });
  }
}

function initCookieBanner() {
  if (localStorage.getItem("cookieNoticeDismissed") === "true") return;

  const banner = document.createElement("div");
  banner.id = "cookie-banner";
  banner.className = "fixed inset-x-0 bottom-0 z-50 bg-white border-t border-gray-200 shadow-lg px-4 py-4 sm:px-6";
  banner.innerHTML = `
    <div class="max-w-6xl mx-auto flex flex-col sm:flex-row items-center gap-3 sm:gap-6">
      <p class="text-sm text-gray-600 flex-1">
        Deze website gebruikt cookies voor analytische doeleinden. Door verder te gaan ga je akkoord.
        <a href="privacy.html" class="text-emerald-600 hover:underline">Meer info</a>.
      </p>
      <button id="cookie-accept" type="button" class="shrink-0 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-700 transition-colors">
        Accepteren
      </button>
    </div>`;
  document.body.appendChild(banner);

  document.getElementById("cookie-accept").addEventListener("click", () => {
    localStorage.setItem("cookieNoticeDismissed", "true");
    banner.remove();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initHomeSearch();
  loadLiveCounter();
  initResultsPage();
  initListingPage();
  initDealsPage();
  initAlertsPage();
  initCategoryPage();
  initCookieBanner();
});
