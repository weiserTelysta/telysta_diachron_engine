const assert = require("node:assert/strict");
const test = require("node:test");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { buildDraft, toMarkdown } = require("./app.js");

function input() {
  return {
    brief: "用于一个故事的语言。",
    canon: "河口城\n过河\n守卫",
    canonIntents: "1 | 这里是一座河口城\n1 | 城名保持不变\n2 | 请求对方过河\n2 | 时间尚未确定\n3 | 指一位守卫",
    concept: "analytic",
    speaker: "speaker", referent: "known", number: "one", source: "seen",
    time: "yesterday", completion: "complete", polarity: "positive", speechAct: "inform",
  };
}

test("manual confirmations produce only research notes, without inferred answers", () => {
  const full = buildDraft(input());
  assert.equal(full.researchOnly, true);
  assert.equal(full.answers.filter((answer) => answer.confirmed).length, 8);
  assert.equal(full.canonCount, 3);
  assert.equal(full.gaps.length, 0);
  const pending = buildDraft({ brief: "一个构想", source: "unknown" });
  assert.equal(pending.answers.filter((answer) => answer.confirmed).length, 0);
  assert.equal(pending.gaps.length, 11);
  assert.match(toMarkdown(pending), /不是语言手册/);
  assert.match(toMarkdown(pending), /没有生成语言/);
});

test("changed intention is explicitly unresolved instead of treated as equivalent", () => {
  const draft = buildDraft({ ...input(), source: "reported", time: "past", polarity: "negative", speechAct: "ask" });
  assert.equal(draft.gaps.length, 4);
  assert.match(draft.gaps.join("\n"), /需要澄清/);
  assert.match(draft.gaps.join("\n"), /不自动视为意义等价/);
});

test("plural participants cannot silently confirm the singular exercise", () => {
  const draft = buildDraft({ ...input(), number: "many" });
  assert.equal(draft.exercise, "我昨天看见他过河。");
  assert.match(draft.gaps.join("\n"), /多人.*单数/);
  assert.match(toMarkdown(draft), /多人.*单数/);
});

test("fixed exercise selections cannot replace intentions linked to the authors material", () => {
  const unlinked = buildDraft({ ...input(), canon: "别关城门\n明日把船给祭司\n愿河神保佑你", canonIntents: "" });
  assert.equal(unlinked.answers.filter((answer) => answer.confirmed).length, 8);
  assert.match(unlinked.gaps.join("\n"), /固定例句的八项选择不计入/);
  const linked = buildDraft(input());
  assert.equal(linked.linkedIntents[2].canonItem, "过河");
  assert.equal(linked.linkedIntents[2].intention, "请求对方过河");
  assert.match(toMarkdown(linked), /不表示意义已分析/);
  const invalid = buildDraft({ ...input(), canonIntents: "4 | 不存在的材料\n不是关联笔记" });
  assert.equal(invalid.linkedIntents.length, 0);
  assert.match(invalid.gaps.join("\n"), /第 1 行未关联有效材料/);
  const changed = buildDraft({ ...input(), canon: "新城\n新的对白\n新的名字" });
  assert.equal(changed.linkedIntents[2].canonItem, "新的对白");
});

test("unknown choices, blank briefs and oversize content fail closed", () => {
  for (const changed of [{ brief: " " }, { source: "oracle" }, { concept: "universal" }, { feedback: "x".repeat(5001) }]) {
    assert.throws(() => buildDraft({ ...input(), ...changed }));
  }
});

test("export preserves canon Unicode and wraps hostile Markdown in literal fences", () => {
  const canon = "<script>alert(1)</script>\n````\n# pretend approval\nŋ a\u0301";
  const draft = buildDraft({ ...input(), canon });
  const markdown = toMarkdown(draft);
  assert.equal(draft.canon, canon);
  assert.ok(markdown.includes(`\n\`\`\`\`\`text\n${canon}\n\`\`\`\`\`\n`));
  assert.match(markdown, /telysta-formative-draft.v1/);
});

test("prototype has no production bridge, remote assets or silent persistence", () => {
  const js = readFileSync(join(__dirname, "app.js"), "utf8");
  const html = readFileSync(join(__dirname, "index.html"), "utf8");
  assert.doesNotMatch(js, /__TAURI__|localStorage|sessionStorage|fetch\(|XMLHttpRequest|innerHTML/);
  assert.match(html, /connect-src 'none'/);
  assert.doesNotMatch(html, /(?:src|href)="https?:/);
  assert.match(html, /这里不会生成语言/);
});
