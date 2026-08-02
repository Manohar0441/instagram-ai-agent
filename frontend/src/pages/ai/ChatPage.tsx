import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { chat } from "../../api/ai";
import { PageHeader } from "../../components/layout/PageHeader";
import { Markdown } from "../../components/Markdown";
import { ApiErrorState } from "../../components/QueryState";
import { Badge, Button } from "../../components/ui";

interface Turn {
  id: string;
  role: "user" | "agent";
  text: string;
  at: Date;
  toolsUsed?: string[];
  intent?: string;
}

const SUGGESTIONS = [
  "How did my account perform this week?",
  "Which post got the most engagement last month?",
  "How many followers did I gain?",
  "When should I be posting?",
  "Compare this month with last month",
  "What should I post next?",
];

/** "get_account_performance" -> "account performance" */
function toolLabel(name: string): string {
  return name.replace(/^get_/, "").replace(/_/g, " ");
}

function formatTime(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard is unavailable over plain http on some browsers; failing
      // silently is better than an error toast for a convenience action.
    }
  }

  return (
    <Button variant="quiet" small onClick={handleCopy} aria-label="Copy response">
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

export function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  // Kept so "Regenerate" can re-send the question that produced the last
  // answer, rather than whatever is currently typed in the box.
  const lastQuestion = useRef<string | null>(null);

  const ask = useMutation({
    mutationFn: chat,
    onSuccess: (response) => {
      setTurns((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "agent",
          text: response.response,
          at: new Date(),
          toolsUsed: response.tools_used,
          intent: response.intent,
        },
      ]);
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, ask.isPending]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || ask.isPending) return;

      lastQuestion.current = trimmed;
      setTurns((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", text: trimmed, at: new Date() },
      ]);
      setMessage("");
      ask.mutate(trimmed);
    },
    [ask],
  );

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send(message);
  }

  function regenerate() {
    const question = lastQuestion.current;
    if (!question || ask.isPending) return;

    // Drop the previous answer so the new one replaces it rather than
    // appearing as a second reply to the same question.
    setTurns((current) => {
      const lastAgent = current.map((turn) => turn.role).lastIndexOf("agent");
      return lastAgent === -1 ? current : current.filter((_, i) => i !== lastAgent);
    });
    ask.mutate(question);
  }

  const isEmpty = turns.length === 0 && !ask.isPending;
  const lastTurn = turns[turns.length - 1];
  const canRegenerate = !ask.isPending && lastTurn?.role === "agent";

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Ask"
        description="Ask about your analytics in plain English. Every figure comes from your own stored data — the model writes the words, not the numbers."
      />

      <div className="chat">
        <div className="chat__thread" role="log" aria-live="polite">
          {isEmpty && (
            <motion.div
              className="chat__intro"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <span className="eyebrow">Try asking</span>
              <div className="chat__suggestions">
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
            </motion.div>
          )}

          <AnimatePresence initial={false}>
            {turns.map((turn) => (
              <motion.div
                key={turn.id}
                className={`chat__turn chat__turn--${turn.role}`}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="chat__meta">
                  <span className="chat__role">
                    {turn.role === "user" ? "You" : "Instalysis"}
                  </span>
                  <time className="chat__time" dateTime={turn.at.toISOString()}>
                    {formatTime(turn.at)}
                  </time>
                </div>

                <div className="chat__bubble">
                  {turn.role === "agent" ? (
                    <Markdown>{turn.text}</Markdown>
                  ) : (
                    <p className="chat__text">{turn.text}</p>
                  )}
                </div>

                {turn.role === "agent" && (
                  <div className="chat__actions">
                    {turn.toolsUsed && turn.toolsUsed.length > 0 && (
                      <span className="chat__tools">
                        Read from {turn.toolsUsed.map(toolLabel).join(", ")}
                      </span>
                    )}
                    {turn.intent === "out_of_scope" && (
                      <Badge>Outside my scope</Badge>
                    )}
                    <span className="chat__actions-spacer" />
                    <CopyButton text={turn.text} />
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {ask.isPending && (
            <motion.div
              className="chat__turn chat__turn--agent"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="chat__meta">
                <span className="chat__role">Instalysis</span>
              </div>
              <div className="chat__bubble">
                <span className="typing" aria-label="Thinking">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </motion.div>
          )}

          <div ref={endRef} />
        </div>

        {ask.isError && (
          <div className="chat__error">
            <ApiErrorState error={ask.error} />
          </div>
        )}

        <form className="chat__composer" onSubmit={handleSubmit}>
          <label className="visually-hidden" htmlFor="chat-message">
            Your question
          </label>
          <input
            id="chat-message"
            ref={inputRef}
            className="chat__input"
            value={message}
            maxLength={2000}
            placeholder="Ask about your analytics…"
            autoComplete="off"
            onChange={(event) => setMessage(event.target.value)}
          />
          {canRegenerate && (
            <Button type="button" variant="quiet" small onClick={regenerate}>
              Regenerate
            </Button>
          )}
          <Button
            type="submit"
            variant="primary"
            disabled={!message.trim()}
            loading={ask.isPending}
          >
            Send
          </Button>
        </form>
      </div>
    </>
  );
}
