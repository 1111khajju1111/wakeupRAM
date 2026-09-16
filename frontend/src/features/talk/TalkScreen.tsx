import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { conversationsApi } from "../../services/domainApi";
import type { Message } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

/**
 * Plain-text chat surface, wired to RAM Core (personality, memory, graceful
 * degradation). The phone-call experience (call timer, mic/speaker
 * controls, glyph visual, local recording) lives at CallScreen.tsx / the
 * /call route — this screen stays intentionally text-only rather than
 * merging the two, since a typed conversation and a voice call are
 * genuinely different interaction modes people reach for on purpose.
 */
export function TalkScreen() {
  const { t } = useTranslation();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const init = useCallback(async () => {
    setLoadState("loading");
    try {
      const existing = await conversationsApi.list();
      const conversation = existing[0] ?? (await conversationsApi.create());
      setConversationId(conversation.id);
      const history = await conversationsApi.listMessages(conversation.id);
      setMessages(history);
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void init();
  }, [init]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim() || !conversationId) return;

    const content = draft.trim();
    setDraft("");
    setIsSending(true);

    // Optimistic: show the user's line immediately rather than waiting on
    // the round trip, since the backend persists it first regardless.
    const optimisticId = `optimistic-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: optimisticId, role: "user", content, is_fallback: false, created_at: new Date().toISOString() },
    ]);

    try {
      const exchange = await conversationsApi.sendMessage(conversationId, content);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticId),
        exchange.user_message,
        exchange.assistant_message,
      ]);
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      setDraft(content); // give the user their text back so nothing is lost
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="talk-screen">
      <h1>{t("home.talkToRam")}</h1>

      {loadState === "loading" && <p className="empty-state">{t("common.loading")}</p>}

      {loadState === "error" && (
        <div className="empty-state empty-state--error">
          <p>{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void init()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {loadState === "loaded" && (
        <>
          <div className="talk-screen__messages" ref={scrollRef}>
            {messages.length === 0 && <p className="empty-state">{t("talk.sayToStart")}</p>}
            {messages.map((message) => (
              <div
                key={message.id}
                className={`talk-bubble talk-bubble--${message.role} ${
                  message.is_fallback ? "talk-bubble--fallback" : ""
                }`}
              >
                {message.content}
              </div>
            ))}
          </div>

          <form onSubmit={handleSend} className="talk-screen__composer">
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("talk.composerPlaceholder")}
              disabled={isSending}
            />
            <button type="submit" disabled={isSending || !draft.trim()}>
              {isSending ? "…" : t("talk.send")}
            </button>
          </form>
        </>
      )}
    </main>
  );
}
