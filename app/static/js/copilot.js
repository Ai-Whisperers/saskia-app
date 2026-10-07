/* copilot.js — copiloto fase 0: fetch + render simple. */
"use strict";
function copilotBubble(role, text) {
  const log = document.getElementById("copilot-log");
  const div = document.createElement("div");
  div.className = "callout " + (role === "user" ? "callout-info" : "callout-success");
  div.style.whiteSpace = "pre-wrap";
  div.textContent = (role === "user" ? "Vos: " : "Copiloto: ") + text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
async function copilotAsk(q) {
  if (!q || !q.trim()) return;
  copilotBubble("user", q);
  document.getElementById("copilot-q").value = "";
  try {
    const r = await fetch("/copiloto/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await r.json();
    copilotBubble("bot", data.answer || data.error || "Sin respuesta");
  } catch (e) {
    copilotBubble("bot", "Error de conexión con el copiloto.");
  }
}
function copilotSubmit(ev) {
  ev.preventDefault();
  const input = document.getElementById("copilot-q");
  copilotAsk(input.value);
}
