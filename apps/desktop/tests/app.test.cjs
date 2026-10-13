const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync(join(__dirname, "../web/app.js"), "utf8");

// A minimal DOM lets us exercise the shipped handlers without a browser bundle.
// This checks command dispatch and UI state; it is not a WebKit integration test.
function client(invoke) {
  const elements = new Map();
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) {
        elements.set(selector, {
          value: "",
          textContent: "",
          disabled: false,
          hidden: true,
          dataset: {},
          listeners: {},
          addEventListener(name, handler) { this.listeners[name] = handler; },
        });
      }
      return elements.get(selector);
    },
  };
  runInNewContext(source, {
    document,
    window: invoke ? { __TAURI__: { core: { invoke } } } : {},
  });
  return {
    element: (id) => document.querySelector(`#${id}`),
    click: (id) => document.querySelector(`#${id}`).listeners.click(),
  };
}

function session() {
  return {
    projectId: "telysta:project:test",
    historySha256: "history-digest",
    stateHashes: { full: "state-digest" },
    status: "open",
    indexStatus: { kind: "current" },
    summary: {
      languageId: "telysta:language:test",
      asOfYear: 12,
      phonemeCount: 20,
      lexemeCount: 30,
      morphemeCount: 4,
      constructionCount: 5,
      eventCount: 6,
    },
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("opens, refreshes and closes through Rust commands, without creating state", async () => {
  const calls = [];
  const ui = client(async (command, args) => {
    calls.push([command, JSON.parse(JSON.stringify(args))]);
    return { data: session() };
  });
  assert.equal(ui.element("refresh-project").disabled, true);
  ui.element("project-root").value = "  /languages/test  ";
  await ui.click("open-project");
  assert.equal(ui.element("session").hidden, false);
  assert.equal(ui.element("language-id").textContent, session().summary.languageId);
  assert.equal(ui.element("state-hash").textContent, "state-digest");
  assert.equal(ui.element("open-project").disabled, true);
  await ui.click("open-project");
  await ui.click("refresh-project");
  await ui.click("close-project");
  assert.deepEqual(calls, [
    ["open_project", { projectRoot: "/languages/test" }],
    ["refresh_project", { projectId: session().projectId }],
    ["close_project", { projectId: session().projectId }],
  ]);
  assert.equal(ui.element("session").hidden, true);
  assert.equal(ui.element("open-project").disabled, false);
  assert.equal(ui.element("close-project").disabled, true);
});

test("session commands cannot overlap and resurrect a closed session", async () => {
  const pending = deferred();
  const calls = [];
  const ui = client(async (command) => {
    calls.push(command);
    return command === "close_project" ? pending.promise : { data: session() };
  });
  ui.element("project-root").value = "/languages/test";
  await ui.click("open-project");
  const closing = ui.click("close-project");
  assert.equal(ui.element("refresh-project").disabled, true);
  await ui.click("refresh-project");
  await ui.click("close-project");
  await ui.click("open-project");
  pending.resolve({ data: session() });
  await closing;
  assert.deepEqual(calls, ["open_project", "close_project"]);
  assert.equal(ui.element("session").hidden, true);
});

test("failed open restores controls and displays backend text safely", async () => {
  const failure = "<img src=x onerror=alert(1)> invalid project";
  const ui = client(async () => { throw { code: "storage", message: failure }; });
  ui.element("project-root").value = "/languages/test";
  await ui.click("open-project");
  assert.equal(ui.element("status").textContent, failure);
  assert.equal(ui.element("status").dataset.kind, "error");
  assert.equal(ui.element("open-project").disabled, false);
  assert.equal(ui.element("project-root").disabled, false);
  assert.equal(ui.element("refresh-project").disabled, true);
});

test("failed refresh or close retains the existing session for retry", async () => {
  const ui = client(async (command) => {
    if (command !== "open_project") throw "project is locked";
    return { data: session() };
  });
  ui.element("project-root").value = "/languages/test";
  await ui.click("open-project");
  for (const button of ["refresh-project", "close-project"]) {
    await ui.click(button);
    assert.equal(ui.element("status").dataset.kind, "error");
    assert.equal(ui.element("session").hidden, false);
    assert.equal(ui.element("close-project").disabled, false);
    assert.equal(ui.element("open-project").disabled, true);
  }
});

test("empty paths and missing desktop runtime are explicit failures", async () => {
  let calls = 0;
  const ui = client(async () => { calls += 1; });
  ui.element("project-root").value = "  ";
  await ui.click("open-project");
  assert.equal(calls, 0);
  assert.equal(ui.element("status").dataset.kind, "error");
  const browser = client();
  browser.element("project-root").value = "/languages/test";
  await browser.click("open-project");
  assert.match(browser.element("status").textContent, /desktop runtime/);
  assert.equal(browser.element("open-project").disabled, false);
});

test("blueprint validation preserves Rust diagnostics and never promises generation", async () => {
  const report = { readyForCompilation: false, diagnostics: [{ code: "planned" }] };
  const ui = client(async (command, args) => {
    assert.equal(command, "validate_blueprint");
    assert.equal(JSON.parse(args.blueprintJson).schemaVersion, "telysta-language-blueprint.v2");
    return { data: report };
  });
  await ui.click("validate-blueprint");
  assert.deepEqual(JSON.parse(ui.element("blueprint-report").textContent), report);
  assert.match(ui.element("status").textContent, /cannot be compiled/);
  assert.equal(ui.element("status").dataset.kind, "info");
  assert.equal(ui.element("blueprint-report").hidden, false);
  assert.equal(ui.element("validate-blueprint").disabled, false);
});

test("blueprint input reaches Rust as original text without numeric or duplicate-key rewriting", async () => {
  const calls = [];
  const ui = client(async (command, args) => {
    calls.push([command, args]);
    return { data: { readyForCompilation: false, diagnostics: [] } };
  });
  const texts = [
    '{"value":9007199254740993,"label":"月读 é"}',
    '{"candidateCount":8.0000000000000001}',
    '{"schemaVersion":"old","schemaVersion":"new"}',
  ];
  for (const text of texts) {
    ui.element("blueprint-json").value = text;
    await ui.click("validate-blueprint");
    const [command, args] = calls.at(-1);
    assert.equal(command, "validate_blueprint");
    assert.deepEqual(Object.keys(args), ["blueprintJson"]);
    assert.equal(args.blueprintJson, text);
  }
});

test("invalid JSON is rejected before invoking Rust, with no stale report", async () => {
  let calls = 0;
  const ui = client(async () => { calls += 1; });
  ui.element("blueprint-json").value = "{";
  ui.element("blueprint-report").hidden = false;
  await ui.click("validate-blueprint");
  assert.equal(calls, 0);
  assert.equal(ui.element("status").dataset.kind, "error");
  assert.equal(ui.element("blueprint-report").hidden, true);
  assert.equal(ui.element("validate-blueprint").disabled, false);
});

test("editing invalidates diagnostics and discards late responses for older text", async () => {
  for (const outcome of ["success", "failure"]) {
    const pending = deferred();
    const ui = client(() => pending.promise);
    const validation = ui.click("validate-blueprint");
    ui.element("blueprint-json").value = '{"schemaVersion":"edited"}';
    ui.element("blueprint-json").listeners.input();
    assert.equal(ui.element("blueprint-report").hidden, true);
    if (outcome === "success") pending.resolve({ data: { readyForCompilation: false } });
    else pending.reject("old input was invalid");
    await validation;
    assert.equal(ui.element("blueprint-report").hidden, true);
    assert.match(ui.element("status").textContent, /Blueprint edited/);
    assert.equal(ui.element("validate-blueprint").disabled, false);
  }
  const ui = client(async () => ({ data: { readyForCompilation: false } }));
  await ui.click("validate-blueprint");
  assert.equal(ui.element("blueprint-report").hidden, false);
  ui.element("blueprint-json").listeners.input();
  assert.equal(ui.element("blueprint-report").hidden, true);
});
