const invoke = window.__TAURI__?.core?.invoke;
const openButton = document.querySelector("#open-project");
const refreshButton = document.querySelector("#refresh-project");
const closeButton = document.querySelector("#close-project");
const validateBlueprintButton = document.querySelector("#validate-blueprint");
const rootInput = document.querySelector("#project-root");
const blueprintInput = document.querySelector("#blueprint-json");
const blueprintReport = document.querySelector("#blueprint-report");
const status = document.querySelector("#status");
const sessionPanel = document.querySelector("#session");
let currentProjectId = null;

const exampleBlueprint = {
  schemaVersion: "telysta-language-blueprint.v2",
  blueprintId: "telysta:blueprint:literary-proto-language",
  displayName: "Literary proto-language",
  historyScope: {
    originYear: 0,
    horizonYears: 2000,
    branching: "allowed",
    contact: "allowed",
  },
  generationPolicy: {
    candidateCount: 8,
    selection: "pareto_frontier",
  },
  evidence: {
    "telysta:evidence:inventory-size-prior": {
      id: "telysta:evidence:inventory-size-prior",
      class: "empiricalPrior",
      note: "A soft inventory-size prior; never a universal law.",
      citation: null,
      dataReferences: [],
    },
    "telysta:evidence:literary-preference": {
      id: "telysta:evidence:literary-preference",
      class: "creativePreference",
      note: "User requests a contrast-rich literary register.",
      citation: null,
      dataReferences: [],
    },
  },
  intents: {
    "telysta:intent:inventory-size-prior": {
      id: "telysta:intent:inventory-size-prior",
      featureId: "telysta:feature:consonant-inventory-size",
      desiredValue: { kind: "integer_range", minimum: 18, maximum: 28 },
      control: { kind: "preferred", strengthBasisPoints: 6500 },
      priorityBasisPoints: 6500,
      evidenceIds: ["telysta:evidence:inventory-size-prior"],
      explanation: "Prefer a medium consonant inventory as an empirical prior.",
    },
    "telysta:intent:literary-cluster-preference": {
      id: "telysta:intent:literary-cluster-preference",
      featureId: "telysta:feature:cluster-tolerance",
      desiredValue: { kind: "category", value: "medium" },
      control: { kind: "preferred", strengthBasisPoints: 8000 },
      priorityBasisPoints: 8000,
      evidenceIds: ["telysta:evidence:literary-preference"],
      explanation: "Favor moderate clusters without treating an aesthetic choice as evidence.",
    },
  },
};

blueprintInput.value = JSON.stringify(exampleBlueprint, null, 2);

function showStatus(message, kind = "info") {
  status.textContent = message;
  status.dataset.kind = kind;
}

function showError(error) {
  const message =
    typeof error === "string"
      ? error
      : error?.message || error?.code || JSON.stringify(error);
  showStatus(message, "error");
}

function write(id, value) {
  document.querySelector(`#${id}`).textContent = value;
}

function renderSession(session) {
  currentProjectId = session.projectId;
  sessionPanel.hidden = false;
  write("project-id", session.projectId);
  write("language-id", session.summary.languageId);
  write("as-of", `year ${session.summary.asOfYear}`);
  write("history-hash", session.historySha256);
  write("state-hash", session.stateHashes.full);
  write(
    "storage-status",
    `${session.status}; derived index ${session.indexStatus.kind}`
  );
  write("phoneme-count", session.summary.phonemeCount);
  write("lexeme-count", session.summary.lexemeCount);
  write("morpheme-count", session.summary.morphemeCount);
  write("construction-count", session.summary.constructionCount);
  write("event-count", session.summary.eventCount);
}

async function requireInvoke() {
  if (!invoke) {
    throw new Error("This workspace must be opened by the Telysta desktop runtime.");
  }
  return invoke;
}

openButton.addEventListener("click", async () => {
  const projectRoot = rootInput.value.trim();
  if (!projectRoot) {
    showStatus("Enter the directory that contains project.json.", "error");
    return;
  }
  openButton.disabled = true;
  showStatus("Opening and validating project…");
  try {
    const response = await (await requireInvoke())("open_project", { projectRoot });
    renderSession(response.data);
    showStatus("Project opened from its authoritative history.", "success");
  } catch (error) {
    showError(error);
  } finally {
    openButton.disabled = false;
  }
});

refreshButton.addEventListener("click", async () => {
  if (!currentProjectId) return;
  try {
    const response = await (await requireInvoke())("refresh_project", {
      projectId: currentProjectId,
    });
    renderSession(response.data);
    showStatus("Project state refreshed and revalidated.", "success");
  } catch (error) {
    showError(error);
  }
});

closeButton.addEventListener("click", async () => {
  if (!currentProjectId) return;
  try {
    await (await requireInvoke())("close_project", { projectId: currentProjectId });
    currentProjectId = null;
    sessionPanel.hidden = true;
    showStatus("Project session closed.", "success");
  } catch (error) {
    showError(error);
  }
});

validateBlueprintButton.addEventListener("click", async () => {
  validateBlueprintButton.disabled = true;
  blueprintReport.hidden = true;
  try {
    const blueprint = JSON.parse(blueprintInput.value);
    const response = await (await requireInvoke())("validate_blueprint", { blueprint });
    blueprintReport.textContent = JSON.stringify(response.data, null, 2);
    blueprintReport.hidden = false;
    if (response.data.readyForCompilation) {
      showStatus("Blueprint is valid and supported by the current compiler.", "success");
    } else {
      showStatus(
        "Blueprint structure is valid; review diagnostics before generation.",
        "info"
      );
    }
  } catch (error) {
    showError(error);
  } finally {
    validateBlueprintButton.disabled = false;
  }
});
