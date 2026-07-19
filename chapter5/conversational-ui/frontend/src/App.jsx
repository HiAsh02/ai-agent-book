import { useState } from "react";

// ===========================================================================
// Basic chatbot interface.
// This is a minimal React application that can be "customized via natural language":
//   - UI text such as title copy and button labels are written here (the Agent can modify the copy as needed);
//   - Styles such as colors, fonts, and layout are centralized in theme.css (the Agent can modify the styles as needed).
// When the user says in the conversation "change the send button to blue / switch to a monospace font / change the title to XXX",
// the Agent will locate and modify these source files, and Vite HMR will make the changes take effect immediately.
// ===========================================================================

// UI copy (modify here when the Agent customizes the "copy" requirement)
const HEADER_TITLE = "Smart Assistant";
const HEADER_SUBTITLE = "How can I help you?";
const SEND_BUTTON_LABEL = "Send";

export default function App() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hello! I am your smart assistant, always at your service." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await resp.json();
      setMessages((m) => [...m, { role: "assistant", text: data.reply }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "(Backend not connected, this is a local placeholder reply)" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="header-title">{HEADER_TITLE}</h1>
        <p className="header-subtitle">{HEADER_SUBTITLE}</p>
      </header>

      <main className="chat-window">
        {messages.map((m, i) => (
          <div key={i} className={`bubble bubble-${m.role}`}>
            {m.text}
          </div>
        ))}
        {loading && <div className="bubble bubble-assistant">思考中…</div>}
      </main>

      <footer className="composer">
        <input
          className="composer-input"
          value={input}
          placeholder="Enter message…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button className="send-button" onClick={handleSend}>
          {SEND_BUTTON_LABEL}
        </button>
      </footer>
    </div>
  );
}
