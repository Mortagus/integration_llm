const form = document.querySelector("#chat-form");
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

function addMessage(content, kind, label) {
  const message = document.createElement("article");
  message.className = `message ${kind}`;

  if (label) {
    const messageLabel = document.createElement("span");
    messageLabel.className = "message-label";
    messageLabel.textContent = label;
    message.append(messageLabel);
  }

  const paragraph = document.createElement("p");
  paragraph.textContent = content;
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
    if (result?.status === "SUCCEEDED") {
      return result.message || "Le créneau a bien été réservé.";
    }
    return result?.message || "La réservation n’a pas abouti.";
  }

  return "Action terminée.";
}

function handleAgentEvent(eventName, payload, state) {
  if (eventName === "text") {
    if (!state.assistantMessage) {
      state.assistantMessage = addMessage("", "assistant-message", "ASSISTANT RH");
    }
    state.assistantMessage.paragraph.textContent += payload.text ?? "";
    scrollConversationToBottom();
    return;
  }

  if (eventName === "tool_call") {
    const label = toolLabels[payload.name] ?? `Exécution de ${payload.name}…`;
    const activities = state.activities.get(payload.name) ?? [];
    activities.push(addMessage(label, "activity-message").message);
    state.activities.set(payload.name, activities);
    return;
  }

  if (eventName === "tool_result") {
    const activity = state.activities.get(payload.name)?.shift();
    if (activity) {
      activity.querySelector("p").textContent = displayToolResult(
        payload.name,
        payload.result,
      );
      activity.dataset.state =
        payload.result?.error || payload.result?.status === "UNAVAILABLE"
          ? "error"
          : "success";
    }
    return;
  }

  if (eventName === "error") {
    addMessage(payload.message ?? "Une erreur est survenue.", "activity-message error-message");
    return;
  }

  if (eventName === "done" && payload.status === "error") {
    state.status = "error";
  } else if (eventName === "done") {
    state.status = payload.status;
  }
}

function dispatchSseFrame(frame, state) {
  let eventName = "message";
  const dataLines = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) return;

  try {
    handleAgentEvent(eventName, JSON.parse(dataLines.join("\n")), state);
  } catch {
    addMessage("Le serveur a envoyé un événement illisible.", "activity-message error-message");
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

    let frameBoundary = buffer.indexOf("\n\n");
    while (frameBoundary !== -1) {
      const frame = buffer.slice(0, frameBoundary);
      buffer = buffer.slice(frameBoundary + 2);
      dispatchSseFrame(frame, state);
      frameBoundary = buffer.indexOf("\n\n");
    }

    finished = done;
  }

  if (buffer.trim()) dispatchSseFrame(buffer, state);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const userPrompt = promptInput.value.trim();
  if (!userPrompt) return;

  addMessage(userPrompt, "user-message");
  promptInput.value = "";
  promptInput.focus();
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
      const body = await response.text();
      throw new Error(body || `Erreur HTTP ${response.status}`);
    }

    await readSseStream(response, state);
    if (state.status === "completed" && state.assistantMessage) {
      conversationHistory.push(
        { role: "user", content: userPrompt },
        { role: "assistant", content: state.assistantMessage.paragraph.textContent },
      );
    }
  } catch (error) {
    addMessage(
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
    form.requestSubmit();
  }
});
