const pairSelect = document.getElementById("pairSelect");
const queryForm = document.getElementById("queryForm");
const endpointOutput = document.getElementById("endpointOutput");
const resultsBody = document.getElementById("resultsBody");
const resultsMeta = document.getElementById("resultsMeta");
const statusCard = document.getElementById("statusCard");
const useAllPairsButton = document.getElementById("useAllPairs");
const downloadCsvButton = document.getElementById("downloadCsv");
const pairFeedback = document.getElementById("pairFeedback");
const granularitySelect = document.getElementById("granularity");
const rangeModeSelect = document.getElementById("rangeMode");
const yearsGroup = document.getElementById("yearsGroup");
const startDateGroup = document.getElementById("startDateGroup");
const endDateGroup = document.getElementById("endDateGroup");
const rangeHint = document.getElementById("rangeHint");
const previewButton = queryForm.querySelector('button[type="submit"]');
const copyEndpointButton = document.getElementById("copyEndpoint");
const copyFeedback = document.getElementById("copyFeedback");
let allGranularityChoices = [];
let seedSupportedGranularities = ["1d"];

function getCurrentGranularityChoice() {
  return allGranularityChoices.find((choice) => choice.key === granularitySelect.value) || null;
}

function updateRangeConstraints() {
  const yearsInput = document.getElementById("years");
  const currentChoice = getCurrentGranularityChoice();
  const maxRangeDays = currentChoice?.max_range_days || 3650;
  const maxYears = Math.max(1, Math.floor(maxRangeDays / 365));

  Array.from(yearsInput.options).forEach((option) => {
    const yearValue = Number(option.value);
    option.disabled = yearValue > maxYears;
    option.hidden = yearValue > maxYears;
  });

  if (Number(yearsInput.value) > maxYears) {
    yearsInput.value = String(maxYears);
  }

  return { maxRangeDays, maxYears, choiceLabel: currentChoice?.label || "Selected granularity" };
}

function syncRangeModeUI() {
  const rangeMode = rangeModeSelect.value;
  const isQuick = rangeMode === "quick";
  const startDateInput = document.getElementById("startDate");
  const endDateInput = document.getElementById("endDate");
  const yearsInput = document.getElementById("years");
  const { maxRangeDays, maxYears, choiceLabel } = updateRangeConstraints();
  yearsGroup.hidden = !isQuick;
  startDateGroup.hidden = isQuick;
  endDateGroup.hidden = isQuick;
  yearsGroup.style.display = isQuick ? "flex" : "none";
  startDateGroup.style.display = isQuick ? "none" : "flex";
  endDateGroup.style.display = isQuick ? "none" : "flex";
  yearsInput.disabled = !isQuick;
  startDateInput.disabled = isQuick;
  endDateInput.disabled = isQuick;
  if (isQuick) {
    startDateInput.value = "";
    endDateInput.value = "";
  }
  rangeHint.textContent = isQuick
    ? `Quick Range uses the selected number of years and sets the end date to today. ${choiceLabel} allows up to ${maxYears} year(s) (${maxRangeDays} days).`
    : `Custom Range uses your exact start and end dates and overrides the years selection. ${choiceLabel} allows up to ${maxRangeDays} days.`;
}

function renderGranularityOptions() {
  const sourceMode = document.getElementById("sourceMode").value;
  const supportedKeys =
    sourceMode === "seed"
      ? new Set(seedSupportedGranularities)
      : new Set(allGranularityChoices.map((choice) => choice.key));
  const currentValue = granularitySelect.value;

  granularitySelect.innerHTML = "";
  allGranularityChoices
    .filter((choice) => supportedKeys.has(choice.key))
    .forEach((choice) => {
      const option = document.createElement("option");
      option.value = choice.key;
      option.textContent =
        sourceMode === "live" && choice.max_range_days
          ? `${choice.label} (max ${choice.max_range_days} days)`
          : choice.label;
      if (choice.key === currentValue || (!currentValue && choice.key === "1d")) {
        option.selected = true;
      }
      granularitySelect.appendChild(option);
    });
}

async function loadPairs() {
  const sourceMode = document.getElementById("sourceMode").value;
  const response = await fetch(`/api/pairs?source=${encodeURIComponent(sourceMode)}`);
  const pairs = await response.json();

  pairSelect.innerHTML = "";
  for (const item of pairs) {
    const option = document.createElement("option");
    option.value = item.pair;
    option.textContent = `${item.pair} | ${item.pair_name}`;
    pairSelect.appendChild(option);
  }
  updatePairFeedback();
}

async function loadStatus() {
  const response = await fetch("/api/status");
  const status = await response.json();
  allGranularityChoices = status.granularity_choices || [];
  seedSupportedGranularities = status.seed_supported_granularities || ["1d"];
  renderGranularityOptions();
  syncRangeModeUI();
  statusCard.innerHTML = `
    <strong>Status:</strong> ${status.status}<br />
    <strong>Source:</strong> ${status.source}<br />
    <strong>Supported Pairs:</strong> ${status.supported_pairs}<br />
    <strong>Latest Refresh:</strong> ${status.latest_successful_refresh || "N/A"}<br />
    <strong>Last Job:</strong> ${status.latest_job_status || "N/A"}<br />
    <strong>Provider Mode:</strong> ${status.provider_mode}<br />
    <strong>Recommended for Power BI:</strong> ${(status.power_bi_recommended_granularities || []).join(", ")}<br />
    <strong>Provider Note:</strong> ${status.provider_message}
  `;
}

function getSelectedPairs() {
  return Array.from(pairSelect.selectedOptions).map((option) => option.value);
}

function updatePairFeedback() {
  const selectedCount = getSelectedPairs().length;
  const totalCount = pairSelect.options.length;

  if (selectedCount === 0) {
    pairFeedback.textContent = "All USD pairs will be used.";
    useAllPairsButton.textContent = "Use All USD Pairs";
    useAllPairsButton.classList.remove("success");
    return;
  }

  if (selectedCount === totalCount) {
    pairFeedback.textContent = `All ${totalCount} USD pairs selected.`;
    useAllPairsButton.textContent = "All USD Pairs Selected";
    useAllPairsButton.classList.add("success");
    return;
  }

  pairFeedback.textContent = `${selectedCount} of ${totalCount} pairs selected.`;
  useAllPairsButton.textContent = "Use All USD Pairs";
  useAllPairsButton.classList.remove("success");
}

function buildQueryParams() {
  const params = new URLSearchParams();
  const years = document.getElementById("years").value;
  const startDate = document.getElementById("startDate").value;
  const endDate = document.getElementById("endDate").value;
  const granularity = document.getElementById("granularity").value;
  const offerSide = document.getElementById("offerSide").value;
  const sourceMode = document.getElementById("sourceMode").value;
  const rangeMode = document.getElementById("rangeMode").value;
  const selectedPairs = getSelectedPairs();

  if (rangeMode === "custom") {
    params.set("start_date", startDate);
    params.set("end_date", endDate);
  } else {
    params.set("years", years);
  }

  params.set("granularity", granularity);
  params.set("offer_side", offerSide);
  params.set("source", sourceMode);

  return { params, selectedPairs };
}

function buildEndpoint(format = "json") {
  const { params, selectedPairs } = buildQueryParams();
  params.set("format", format);

  if (selectedPairs.length === 0) {
    return `/api/forex/usd-pairs?${params.toString()}`;
  }

  params.set("symbols", selectedPairs.join(","));
  return `/api/forex/pairs?${params.toString()}`;
}

function updateEndpointPreview() {
  const absoluteUrl = `${window.location.origin}${buildEndpoint("csv")}`;
  endpointOutput.value = absoluteUrl;
}

async function previewData(event) {
  event.preventDefault();
  updateEndpointPreview();
  resultsBody.innerHTML = "";
  resultsMeta.textContent = "Loading preview...";
  previewButton.disabled = true;
  previewButton.textContent = "Loading...";

  try {
    const response = await fetch(buildEndpoint("json"));
    const payload = await response.json();
    if (!response.ok) {
      resultsMeta.textContent = payload.error || "Request failed.";
      return;
    }
    const rows = payload.data || [];

    resultsMeta.textContent = `Rows returned: ${payload.meta?.row_count || 0}. Showing first 50 rows.`;

    rows.slice(0, 50).forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.pair}</td>
        <td>${row.timestamp_utc}</td>
        <td>${row.bid_close ?? ""}</td>
        <td>${row.ask_close ?? ""}</td>
        <td>${row.spread ?? ""}</td>
        <td>${row.granularity}</td>
      `;
      resultsBody.appendChild(tr);
    });
  } catch (error) {
    resultsMeta.textContent = "Preview request failed.";
  } finally {
    previewButton.disabled = false;
    previewButton.textContent = "Preview Data";
  }
}

function clearPairSelection() {
  Array.from(pairSelect.options).forEach((option) => {
    option.selected = true;
  });
  updatePairFeedback();
  updateEndpointPreview();
}

function downloadCsv() {
  updateEndpointPreview();
  window.open(buildEndpoint("csv"), "_blank");
}

async function copyEndpoint() {
  updateEndpointPreview();
  try {
    await navigator.clipboard.writeText(endpointOutput.value);
    copyFeedback.textContent = "API URL copied to clipboard.";
    copyEndpointButton.classList.add("success");
  } catch (error) {
    copyFeedback.textContent = "Copy failed. Please copy the URL manually.";
    copyEndpointButton.classList.remove("success");
  }
}

queryForm.addEventListener("submit", previewData);
useAllPairsButton.addEventListener("click", clearPairSelection);
downloadCsvButton.addEventListener("click", downloadCsv);
copyEndpointButton.addEventListener("click", copyEndpoint);
pairSelect.addEventListener("change", updateEndpointPreview);
pairSelect.addEventListener("change", updatePairFeedback);
document.getElementById("years").addEventListener("change", updateEndpointPreview);
document.getElementById("startDate").addEventListener("change", updateEndpointPreview);
document.getElementById("endDate").addEventListener("change", updateEndpointPreview);
document.getElementById("granularity").addEventListener("change", () => {
  syncRangeModeUI();
  updateEndpointPreview();
});
document.getElementById("offerSide").addEventListener("change", updateEndpointPreview);
document.getElementById("rangeMode").addEventListener("change", () => {
  syncRangeModeUI();
  updateEndpointPreview();
});
document.getElementById("sourceMode").addEventListener("change", async () => {
  renderGranularityOptions();
  syncRangeModeUI();
  await loadPairs();
  updateEndpointPreview();
});

syncRangeModeUI();
Promise.all([loadPairs(), loadStatus()]).then(updateEndpointPreview);
