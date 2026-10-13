"use strict";

// Ephemeral product-research notes, never a Blueprint or LanguageState schema.
const QUESTIONS = {
  speaker: { label: "说话者", choices: { speaker: "说话者本人", quoted: "引述中的说话者" } },
  referent: { label: "指称", choices: { known: "双方已经提到的人", new: "第一次提到的人" } },
  number: { label: "参与者数量", choices: { one: "一位", many: "多位" } },
  source: { label: "信息来源", choices: { seen: "亲眼看见", reported: "听别人说" } },
  time: { label: "时间", choices: { yesterday: "昨天", past: "过去某时" } },
  completion: { label: "完成情况", choices: { complete: "已经到达对岸", ongoing: "只看见正在过河" } },
  polarity: { label: "肯定或否定", choices: { positive: "确实看见了", negative: "没有看见" } },
  speechAct: { label: "言语行为", choices: { inform: "告诉对方一件事", ask: "询问是否发生" } },
};
const CONCEPTS = {
  analytic: "清晰的词间关系（方案概念 A）",
  layered: "丰富的词内结构（方案概念 B）",
};

function text(input, key, maximum) {
  const value = input[key] ?? "";
  if (typeof value !== "string" || value.length > maximum) {
    throw new Error(`${key} 的输入格式或长度不正确。`);
  }
  return value;
}

function buildDraft(input) {
  const brief = text(input, "brief", 5000);
  if (!brief.trim()) throw new Error("请先描述您的创作需求。");
  const concept = text(input, "concept", 30);
  if (concept && !Object.hasOwn(CONCEPTS, concept)) throw new Error("未知的方案概念。");
  const gaps = [];
  const answers = Object.entries(QUESTIONS).map(([key, question]) => {
    const choice = text(input, key, 30);
    if (choice !== "" && choice !== "unknown" && !Object.hasOwn(question.choices, choice)) {
      throw new Error(`未知的意图选择：${question.label}。`);
    }
    const confirmed = Object.hasOwn(question.choices, choice);
    if (!confirmed) gaps.push(`${question.label}尚未确认；本原型不推断答案。`);
    return { key, label: question.label, choice, confirmed, description: confirmed ? question.choices[choice] : "尚未确认" };
  });
  if (!concept) gaps.push("尚未选择方案概念。没有生成或比较真实候选语言。");
  if (input.number === "many") gaps.push("多人选择与练习句的单数“他”不同；需要作者确认新的表达。");
  if (input.source === "reported") gaps.push("“听别人说”与练习句的“看见”需要澄清；尚未判断意义等价。");
  if (input.polarity === "negative") gaps.push("否定选择改变了练习句的意思；需要作者确认新的表达。");
  if (input.speechAct === "ask") gaps.push("询问选择改变了练习句的言语行为；需要作者确认新的表达。");
  if (input.time === "past") gaps.push("“过去某时”比“昨天”宽泛；不自动视为意义等价。");
  const canon = text(input, "canon", 10000);
  const canonItems = canon.split(/\r?\n/).filter((line) => line.trim());
  const canonCount = canonItems.length;
  if (canonCount < 3 || canonCount > 5) gaps.push("尚未完成 3–5 条真实创作材料的形成性任务；不记为作者研究成功。");
  const canonIntents = text(input, "canonIntents", 10000);
  const linkedIntents = [];
  const intentLines = canonIntents.split(/\r?\n/).filter((line) => line.trim());
  for (const [index, line] of intentLines.entries()) {
    const match = line.match(/^\s*([1-9]\d?)\s*\|\s*(\S.*)$/);
    const itemNumber = match ? Number(match[1]) : 0;
    if (itemNumber < 1 || itemNumber > canonCount) {
      gaps.push(`创作意图第 ${index + 1} 行未关联有效材料；请用“材料序号 | 意图”记录。`);
    } else {
      linkedIntents.push({ itemNumber, canonItem: canonItems[itemNumber - 1], intention: match[2] });
    }
  }
  if (linkedIntents.length < 5 || linkedIntents.length > 10) {
    gaps.push("尚未记录 5–10 项与自有材料关联的创作意图；固定例句的八项选择不计入此任务。");
  }
  return {
    schemaVersion: "telysta-formative-draft.v1",
    journeyRef: "FormativeJourney.r0b",
    researchOnly: true,
    languageName: text(input, "languageName", 120),
    brief,
    canon,
    canonCount,
    canonIntents,
    linkedIntents,
    exercise: "我昨天看见他过河。",
    answers,
    concept: concept ? CONCEPTS[concept] : "未选择",
    alternative: text(input, "alternative", 1000),
    feedback: text(input, "feedback", 5000),
    gaps,
  };
}

function literal(value) {
  const runs = value.match(/`+/g) || [];
  const fence = "`".repeat(Math.max(3, ...runs.map((run) => run.length + 1)));
  return `${fence}text\n${value}\n${fence}`;
}

function toMarkdown(draft) {
  return [
    "# Telysta · 作者流程草稿",
    "",
    `格式：${draft.schemaVersion} · 任务：${draft.journeyRef}`,
    "",
    "> 仅供产品研究。不是语言手册、Blueprint、LanguageState、迁移输入或 Gate 证明。",
    "> 方案是未验证的创作偏好；没有生成语言、音频或历史。",
    "",
    "## 构想名称", literal(draft.languageName || "未命名构想"),
    "## 创作需求", literal(draft.brief),
    `## 原始创作材料（${draft.canonCount} 条非空行）`, literal(draft.canon),
    `## 关联创作意图（${draft.linkedIntents.length} 项）`, literal(draft.canonIntents),
    "关联仅校验材料序号存在；不表示意义已分析、意图已解决或研究任务已成功。",
    "## 固定练习场景", literal(draft.exercise),
    "## 固定例句的八项选择",
    ...draft.answers.map((answer) => `- ${answer.label}：${answer.description}`),
    "",
    `已确认 ${draft.answers.filter((answer) => answer.confirmed).length}/8 项。确认表示作者选择，不表示语言学验证。`,
    "",
    "## 方案概念", draft.concept,
    "## 未解决项", ...draft.gaps.map((gap) => `- ${gap}`),
    "- 目标语言的强制区别、词汇、语法、正字法、分析器与表达可行性尚未验证。",
    "- 读音需要受支持的 PronunciationPlan；历史解释需要规则、环境、来源和回放证据。",
    "## 替代工具与做法", literal(draft.alternative),
    "## 困惑、失败与转向条件", literal(draft.feedback),
    "",
    "本文只保存本次手动输入；没有自动跟踪用户行为或上传材料。",
    "",
  ].join("\n");
}

if (typeof module !== "undefined") module.exports = { buildDraft, toMarkdown };

if (typeof document !== "undefined") {
  const form = document.querySelector("#draft-form");
  const preview = document.querySelector("#preview");
  const status = document.querySelector("#status");
  const download = document.querySelector("#download");
  let currentMarkdown = null;

  function invalidateDraft() {
    if (currentMarkdown === null) return;
    currentMarkdown = null;
    download.disabled = true;
    preview.hidden = true;
    status.textContent = "输入已更改，请重新整理草稿后导出。";
  }
  form.addEventListener("input", invalidateDraft);
  form.addEventListener("change", invalidateDraft);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    invalidateDraft();
    try {
      const draft = buildDraft(Object.fromEntries(new FormData(form)));
      currentMarkdown = toMarkdown(draft);
      preview.textContent = currentMarkdown;
      preview.hidden = false;
      download.disabled = false;
      status.textContent = `已整理 ${draft.canonCount} 条材料，记录 ${draft.linkedIntents.length} 项关联意图，固定例句确认 ${draft.answers.filter((answer) => answer.confirmed).length}/8 项选择。仍需确认的内容已列入草稿；这不是意义验证或语言生成结果。`;
    } catch (error) {
      status.textContent = error.message;
    }
  });
  download.addEventListener("click", () => {
    if (currentMarkdown === null) return;
    const url = URL.createObjectURL(new Blob([currentMarkdown], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "telysta-formative-draft.md";
    document.body.append(link);
    link.click();
    link.remove();
    // Allow the browser to consume the download before releasing its blob.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}
