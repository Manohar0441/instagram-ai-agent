import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { chat } from "../../api/ai";
import { PageHeader } from "../../components/layout/PageHeader";
import { ApiErrorState } from "../../components/QueryState";
import { Button } from "../../components/ui";
import "./ai.css";

interface Turn {
  role: "user" | "agent";
  text: string;
  toolsUsed?: string[];
}

const SUGGESTIONS = [
  "How did my account perform this week?",
  "Which post got the most engagement last month?",
  "When should I be posting?",
];

/** "get_account_performance" -> "account performance" */
function toolLabel(name: string): string {
  return name.replace(/^get_/, "").replace(/_/g, " ");
}

export function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: chat,
    onSuccess: (response) => {
      setTurns((current) => [
        ...current,
        {
          role: "agent",
          text: response.response,
          toolsUsed: response.tools_used,
        },
      ]);
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, ask.isPending]);

  function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || ask.isPending) return;

    setTurns((current) => [...current, { role: "user", text: trimmed }]);
    setMessage("");
    ask.mutate(trimmed);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send(message);
  }

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Ask"
        description="Ask about your analytics in plain English. Every figure in an answer is read from your own stored data, never invented."
      />

      <div className="chat">
        {turns.length === 0 && !ask.isPending && (
          <div className="chat__suggestions stack">
            <span className="eyebrow">Try asking</span>
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="chat__suggestion"
                onClick={() => send(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <div className="chat__thread">
          {turns.map((turn, index) => (
            <div className={`chat__turn chat__turn--${turn.role}`} key={index}>
              <span className="chat__role">
                {turn.role === "user" ? "You" : "Instalysis"}
              </span>
              {/* Rendered as a text node, never as HTML — model output is
                  untrusted, and the token lives in localStorage. */}
              <p className="chat__text">{turn.text}</p>
              {turn.toolsUsed && turn.toolsUsed.length > 0 && (
                <span className="chat__tools">
                  Read from {turn.toolsUsed.map(toolLabel).join(", ")}
                </span>
              )}
            </div>
          ))}

          {ask.isPending && (
            <div className="chat__turn chat__turn--agent">
              <span className="chat__role">Instalysis</span>
              <p className="chat__text muted">Thinking…</p>
            </div>
          )}

          <div ref={endRef} />
        </div>

        {ask.isError && <ApiErrorState error={ask.error} />}

        <form className="chat__composer" onSubmit={handleSubmit}>
          <label className="visually-hidden" htmlFor="chat-message">
            Your question
          </label>
          <input
            id="chat-message"
            className="field__input"
            value={message}
            maxLength={2000}
            placeholder="Ask about your analytics…"
            autoComplete="off"
            onChange={(event) => setMessage(event.target.value)}
          />
          <Button type="submit" variant="primary" disabled={!message.trim()} loading={ask.isPending}>
            Send
          </Button>
        </form>
      </div>
    </>
  );
}
