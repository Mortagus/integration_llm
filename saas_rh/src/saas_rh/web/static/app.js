const views = [...document.querySelectorAll(".page-view")];
const backHomeButton = document.querySelector("#back-home");

function showView(viewName, updateLocation = true) {
  const selectedView = document.querySelector(`#view-${viewName}`);
  if (!selectedView) return;

  for (const view of views) view.hidden = view !== selectedView;
  backHomeButton.hidden = viewName === "home";

  if (updateLocation) {
    const nextHash = viewName === "home" ? "" : `#${viewName}`;
    if (window.location.hash !== nextHash) window.location.hash = nextHash;
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function syncViewFromLocation() {
  const requestedView = window.location.hash.slice(1) || "home";
  showView(requestedView, false);
}

document.querySelectorAll("[data-open-view]").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.openView));
});
document.querySelectorAll("[data-home]").forEach((button) => {
  button.addEventListener("click", () => showView("home"));
});
backHomeButton.addEventListener("click", () => showView("home"));
window.addEventListener("hashchange", syncViewFromLocation);
syncViewFromLocation();

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = typeof payload?.detail === "string"
      ? payload.detail
      : `La requête a échoué (HTTP ${response.status}).`;
    throw new Error(detail);
  }
  return payload;
}

function setFormBusy(form, isBusy, busyLabel, normalLabel) {
  const button = form.querySelector("button[type='submit']");
  if (!button) return;
  button.disabled = isBusy;
  button.querySelector("span").textContent = isBusy ? busyLabel : normalLabel;
}

function showInlineError(target, message) {
  target.textContent = message;
  target.hidden = !message;
}

function resetResult(target) {
  target.replaceChildren();
  target.className = "result-panel";
  target.hidden = true;
}

function showResultError(target, message) {
  target.replaceChildren();
  target.className = "result-panel result-error";
  target.append(createElement("p", "answer-copy", message));
  target.hidden = false;
}

function renderCandidateResult(result, target) {
  target.replaceChildren();
  target.className = "result-panel";
  target.hidden = false;

  target.append(createElement("h2", "result-title", "Synthèse du profil"));

  const summary = createElement("div", "candidate-summary");
  const facts = createElement("div", "candidate-facts");
  const score = createElement("div", "score-card");
  const scoreValue = Number(result.match_score);
  score.classList.add(
    scoreValue >= 80 ? "score-high" : scoreValue < 40 ? "score-low" : "score-mid",
  );
  const scoreInterpretation = scoreValue >= 80
    ? "FORTE ADÉQUATION"
    : scoreValue < 40
      ? "ADÉQUATION FAIBLE"
      : "À EXAMINER";
  score.append(
    createElement("span", "score-number", `${scoreValue}%`),
    createElement("span", "score-label", scoreInterpretation),
  );

  const factData = [
    [
      "Expérience pertinente",
      `${Number(result.years_of_experience).toLocaleString("fr-BE", { maximumFractionDigits: 1 })} ans`,
    ],
    ["Niveau d’études", result.education_level ?? "Non précisé"],
  ];
  for (const [label, value] of factData) {
    const fact = createElement("div", "fact-card");
    fact.append(createElement("span", "fact-label", label));
    fact.append(createElement("span", "fact-value", value));
    facts.append(fact);
  }
  summary.append(facts, score);
  target.append(summary);

  const skillsSection = createElement("section", "result-section");
  skillsSection.append(createElement("h3", "", "Compétences détectées"));
  const skills = createElement("div", "chip-list");
  for (const skill of result.skills ?? []) skills.append(createElement("span", "chip", skill));
  if (!result.skills?.length) skills.append(createElement("span", "empty-state", "Aucune compétence extraite."));
  skillsSection.append(skills);
  target.append(skillsSection);

  const warningsSection = createElement("section", "result-section");
  warningsSection.append(createElement("h3", "", "Points de vigilance"));
  if (result.warning_points?.length) {
    const warnings = createElement("ul", "warning-list");
    for (const warning of result.warning_points) warnings.append(createElement("li", "", warning));
    warningsSection.append(warnings);
  } else {
    warningsSection.append(createElement("p", "empty-state", "Aucun point de vigilance signalé."));
  }
  target.append(warningsSection);
}

const candidateForm = document.querySelector("#candidate-form");
const candidateMode = document.querySelector("#candidate-input-mode");
const candidateTextField = document.querySelector("#candidate-text-field");
const candidateFileField = document.querySelector("#candidate-file-field");
const candidateText = document.querySelector("#candidate-text");
const candidateFile = document.querySelector("#candidate-file");
const candidateError = document.querySelector("#candidate-error");
const candidateResult = document.querySelector("#candidate-result");

candidateMode.addEventListener("change", () => {
  const usePdf = candidateMode.value === "pdf";
  candidateTextField.hidden = usePdf;
  candidateFileField.hidden = !usePdf;
  candidateText.required = !usePdf;
  candidateFile.required = usePdf;
  showInlineError(candidateError, "");
  resetResult(candidateResult);
});

candidateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showInlineError(candidateError, "");
  resetResult(candidateResult);
  const data = new FormData();
  if (candidateMode.value === "pdf") {
    if (!candidateFile.files.length) {
      showInlineError(candidateError, "Choisissez un fichier PDF à analyser.");
      return;
    }
    data.set("cv_file", candidateFile.files[0]);
  } else {
    const text = candidateText.value.trim();
    if (!text) {
      showInlineError(candidateError, "Collez le texte du CV avant de lancer l’analyse.");
      return;
    }
    data.set("cv_text", text);
  }

  setFormBusy(candidateForm, true, "Analyse en cours", "Analyser le profil");
  try {
    const result = await requestJson("/api/candidates/parse", { method: "POST", body: data });
    renderCandidateResult(result, candidateResult);
  } catch (error) {
    showResultError(candidateResult, error.message);
  } finally {
    setFormBusy(candidateForm, false, "Analyse en cours", "Analyser le profil");
  }
});

const ragForm = document.querySelector("#rag-form");
const ragQuestion = document.querySelector("#rag-question");
const ragError = document.querySelector("#rag-error");
const ragResult = document.querySelector("#rag-result");

ragForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showInlineError(ragError, "");
  resetResult(ragResult);
  const question = ragQuestion.value.trim();
  if (!question) {
    showInlineError(ragError, "Saisissez une question avant de lancer la recherche.");
    return;
  }

  const data = new FormData();
  data.set("question", question);
  setFormBusy(ragForm, true, "Recherche en cours", "Rechercher dans les politiques");
  try {
    const result = await requestJson("/api/rag/ask", { method: "POST", body: data });
    ragResult.replaceChildren();
    ragResult.className = "result-panel";
    ragResult.hidden = false;
    ragResult.append(createElement("h2", "result-title", "Réponse de l’assistant"));
    ragResult.append(createElement("p", "answer-copy", result.content));

    const sources = createElement("section", "result-section");
    sources.append(createElement("h3", "", "Sources consultées"));
    if (result.sources?.length) {
      const sourceList = createElement("div", "source-list");
      for (const source of result.sources) {
        const card = createElement("article", "source-card");
        card.append(createElement("strong", "", source.title));
        card.append(createElement("p", "", source.excerpt));
        card.append(createElement("span", "source-id", source.id));
        sourceList.append(card);
      }
      sources.append(sourceList);
    } else {
      sources.append(createElement("p", "empty-state", "Aucune source n’a été renvoyée."));
    }
    ragResult.append(sources);
  } catch (error) {
    showResultError(ragResult, error.message);
  } finally {
    setFormBusy(ragForm, false, "Recherche en cours", "Rechercher dans les politiques");
  }
});

const scheduleForm = document.querySelector("#schedule-form");
const candidateId = document.querySelector("#candidate-id");
const interviewDate = document.querySelector("#interview-date");
const scheduleError = document.querySelector("#schedule-error");
const scheduleResult = document.querySelector("#schedule-result");

scheduleForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showInlineError(scheduleError, "");
  resetResult(scheduleResult);
  const id = Number(candidateId.value);
  const date = interviewDate.value;
  if (!Number.isInteger(id) || id < 1 || !date) {
    showInlineError(scheduleError, "Saisissez un identifiant candidat positif et une date.");
    return;
  }

  setFormBusy(scheduleForm, true, "Recherche en cours", "Voir les disponibilités");
  try {
    const params = new URLSearchParams({ candidate_id: String(id), date });
    const result = await requestJson(`/api/interviews/slots?${params}`);
    scheduleResult.replaceChildren();
    scheduleResult.className = "result-panel";
    scheduleResult.hidden = false;
    scheduleResult.append(createElement("h2", "result-title", `Disponibilités du ${date}`));
    if (result.available_slots?.length) {
      const slots = createElement("div", "slot-list");
      for (const slot of result.available_slots) slots.append(createElement("span", "slot-chip", slot));
      scheduleResult.append(slots);
    } else {
      scheduleResult.append(createElement("p", "empty-state", "Aucun créneau disponible à cette date."));
    }
  } catch (error) {
    showResultError(scheduleResult, error.message);
  } finally {
    setFormBusy(scheduleForm, false, "Recherche en cours", "Voir les disponibilités");
  }
});

const chatForm = document.querySelector("#chat-form");
const promptInput = document.querySelector("#user-prompt");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const conversationHistory = [];

const toolLabels = {
  search_interview_slots: "Recherche des créneaux disponibles…",
  reserve_interview_slot: "Réservation du créneau…",
};

function scrollConversationToBottom() {
  conversation.scrollTop = conversation.scrollHeight;
}

function addChatMessage(content, kind, label) {
  const message = createElement("article", `message ${kind}`);
  if (label) message.append(createElement("span", "message-label", label));
  const paragraph = createElement("p", "", content);
  message.append(paragraph);
  conversation.append(message);
  scrollConversationToBottom();
  return { message, paragraph };
}

function displayToolResult(name, result) {
  if (result?.error) return result.error;
  if (name === "search_interview_slots") {
    const slots = result?.available_slots ?? [];
    return slots.length
      ? `Créneaux trouvés : ${slots.join(", ")}.`
      : "Aucun créneau disponible pour cette date.";
  }
  if (name === "reserve_interview_slot") {
    if (result?.status === "SUCCEEDED") return result.message || "Le créneau a bien été réservé.";
    return result?.message || "La réservation n’a pas abouti.";
  }
  return "Action terminée.";
}

function handleAgentEvent(eventName, payload, state) {
  if (eventName === "text") {
    if (!state.assistantMessage) {
      state.assistantMessage = addChatMessage("", "assistant-message", "ASSISTANT RH");
    }
    state.assistantMessage.paragraph.textContent += payload.text ?? "";
    scrollConversationToBottom();
  } else if (eventName === "tool_call") {
    const label = toolLabels[payload.name] ?? `Exécution de ${payload.name}…`;
    const activities = state.activities.get(payload.name) ?? [];
    activities.push(addChatMessage(label, "activity-message").message);
    state.activities.set(payload.name, activities);
  } else if (eventName === "tool_result") {
    const activity = state.activities.get(payload.name)?.shift();
    if (activity) {
      activity.querySelector("p").textContent = displayToolResult(payload.name, payload.result);
      activity.dataset.state = payload.result?.error || payload.result?.status === "UNAVAILABLE"
        ? "error"
        : "success";
    }
  } else if (eventName === "error") {
    addChatMessage(payload.message ?? "Une erreur est survenue.", "activity-message error-message");
  } else if (eventName === "done") {
    state.status = payload.status;
  }
}

function dispatchSseFrame(frame, state) {
  let eventName = "message";
  const dataLines = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return;
  try {
    handleAgentEvent(eventName, JSON.parse(dataLines.join("\n")), state);
  } catch {
    addChatMessage("Le serveur a envoyé un événement illisible.", "activity-message error-message");
  }
}

async function readSseStream(response, state) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  while (!finished) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replaceAll("\r\n", "\n").replaceAll("\r", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatchSseFrame(buffer.slice(0, boundary), state);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    finished = done;
  }
  if (buffer.trim()) dispatchSseFrame(buffer, state);
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userPrompt = promptInput.value.trim();
  if (!userPrompt) return;

  addChatMessage(userPrompt, "user-message");
  promptInput.value = "";
  sendButton.disabled = true;
  sendButton.querySelector("span").textContent = "En cours";
  const state = { assistantMessage: null, activities: new Map(), status: null };

  try {
    const formData = new FormData();
    formData.set("user_prompt", userPrompt);
    formData.set("conversation_history_json", JSON.stringify(conversationHistory));
    const response = await fetch("/api/agent/chat", {
      method: "POST",
      body: formData,
      headers: { Accept: "text/event-stream" },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail ?? `La requête a échoué (HTTP ${response.status}).`);
    }

    await readSseStream(response, state);
    if (state.status === "completed" && state.assistantMessage) {
      conversationHistory.push(
        { role: "user", content: userPrompt },
        { role: "assistant", content: state.assistantMessage.paragraph.textContent },
      );
    }
  } catch (error) {
    addChatMessage(
      error instanceof Error ? error.message : "Impossible de joindre le serveur.",
      "activity-message error-message",
    );
  } finally {
    sendButton.disabled = false;
    sendButton.querySelector("span").textContent = "Envoyer";
    scrollConversationToBottom();
  }
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
