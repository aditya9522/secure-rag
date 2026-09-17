import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { AlertTriangle, Database, Globe2, LockKeyhole, MessageSquare, MoreHorizontal, Plus, Send, Settings, ShieldCheck, Square, Users, X, Zap } from "lucide-react";
import { listConversations, listMessages, streamQueryWorkspace, type ConversationSummary, type QueryResponse } from "../../lib/api";
import type { Message } from "../../types";
import { ContextItem, SourceRow } from "../../components/ui/Rows";
import { MessageBubble } from "./MessageBubble";
import { formatRelativeDate } from "../../lib/date";

const greeting = (content: string): Message => ({ id: crypto.randomUUID(), role: "assistant", content, mode: "conversational" });
const conversationPageSize = 100;

export function ChatPage({ organization, identity, onNavigate }: { organization: string; identity: string; onNavigate: (view: "settings") => void }) {
  const [messages, setMessages] = useState<Message[]>([greeting("I’m your secure workspace assistant. Ask me about your organization’s connected knowledge, or just say hello to get started.")]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeConversation, setActiveConversation] = useState(0);
  const [conversationId, setConversationId] = useState<string>();
  const [remoteConversations, setRemoteConversations] = useState<ConversationSummary[]>([]);
  const [loadingMoreConversations, setLoadingMoreConversations] = useState(false);
  const [hasMoreConversations, setHasMoreConversations] = useState(false);
  const [error, setError] = useState("");
  const [contextOpen, setContextOpen] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const messageScrollRef = useRef<HTMLDivElement>(null);
  const menuSurfaceRef = useRef<HTMLDivElement>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const avatar = identity.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "ME";
  const conversations = remoteConversations.map((item) => ({ title: item.title, preview: "Saved workspace conversation", time: formatRelativeDate(item.updated_at, now), id: item.id }));
  const activeConversationRecord = remoteConversations[activeConversation];
  const citedSources = ([...messages].reverse().find((message) => message.role === "assistant" && message.citations?.length)?.citations ?? []).filter((source, index, sources) => sources.findIndex((item) => item.document_id === source.document_id) === index);
  async function loadConversations(append = false) {
    if (append) setLoadingMoreConversations(true);
    try {
      const page = await listConversations(conversationPageSize, append ? remoteConversations.length : 0);
      setRemoteConversations((current) => append ? [...current, ...page] : page);
      setHasMoreConversations(page.length === conversationPageSize);
      if (!append && page[0]) {
        setActiveConversation(0);
        setConversationId(page[0].id);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load conversation history.");
    } finally {
      if (append) setLoadingMoreConversations(false);
    }
  }
  useEffect(() => {
    if (!menuOpen) return;
    function dismissMenu(event: PointerEvent) {
      if (menuSurfaceRef.current && !menuSurfaceRef.current.contains(event.target as Node)) setMenuOpen(false);
    }
    function dismissOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("pointerdown", dismissMenu);
    document.addEventListener("keydown", dismissOnEscape);
    return () => {
      document.removeEventListener("pointerdown", dismissMenu);
      document.removeEventListener("keydown", dismissOnEscape);
    };
  }, [menuOpen]);
  useEffect(() => { if (!import.meta.env.VITE_API_BASE_URL) return; void loadConversations(); }, []);
  useEffect(() => {
    if (!conversationId) return;
    let active = true;
    void listMessages(conversationId).then((items) => {
      if (active) setMessages(items.map((item) => ({ id: item.id, role: item.role, content: item.content, createdAt: item.created_at, mode: item.mode, citations: item.citations })));
    }).catch((requestError) => {
      if (active) setError(requestError instanceof Error ? requestError.message : "Could not load this conversation.");
    });
    return () => { active = false; };
  }, [conversationId]);
  useEffect(() => { const scrollContainer = messageScrollRef.current; if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight; }, [messages, loading]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 60_000); return () => window.clearInterval(timer); }, []);
  useEffect(() => () => { streamAbortRef.current?.abort(); }, []);
  const cancelStream = () => { streamAbortRef.current?.abort(); streamAbortRef.current = null; };
  const newConversation = () => { cancelStream(); setConversationId(undefined); setActiveConversation(-1); setMessages([greeting("New conversation ready. What would you like to explore?")]); setError(""); setMenuOpen(false); };
  const selectConversation = (id: string, index: number) => { cancelStream(); setActiveConversation(index); setConversationId(id); setError(""); };
  async function submitMessage(event?: FormEvent | ReactKeyboardEvent) {
    event?.preventDefault();
    const query = input.trim();
    if (!query || loading) return;
    const assistantId = crypto.randomUUID();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setInput(""); setError(""); setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: query }, { id: assistantId, role: "assistant", content: "", mode: "conversational" }]); setLoading(true);
    try {
      const response: QueryResponse | null = await streamQueryWorkspace(query, conversationId, (content) => {
        setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: message.content + content, streaming: true } : message));
      }, controller.signal);
      if (response?.conversation_id) {
        setConversationId(response.conversation_id);
        void listConversations().then((items) => {
          setRemoteConversations(items);
          const activeIndex = items.findIndex((item) => item.id === response.conversation_id);
          if (activeIndex >= 0) setActiveConversation(activeIndex);
        }).catch(() => undefined);
      }
      const isGreeting = /^(hi+|hello+|hey+|thanks?|thank you|bye+|what can you help(?: me)?(?: with)?|how can you help(?: me)?|what are you doing)\b/i.test(query);
      const fallback = isGreeting ? { answer: "Hello! I’m ready to help you find answers in your authorized workspace data.", mode: "conversational" as const } : { answer: "Connect the API and sign in to retrieve answers from your organization knowledge base.", mode: "refused" as const };
      setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: response?.answer ?? fallback.answer, mode: response?.mode ?? fallback.mode, citations: response?.citations ?? [], streaming: false } : message));
    } catch (requestError) {
      if (controller.signal.aborted) {
        setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, streaming: false } : message));
        return;
      }
      setMessages((current) => current.filter((message) => message.id !== assistantId));
      setError(requestError instanceof Error ? requestError.message : "The assistant is temporarily unavailable.");
    } finally { if (streamAbortRef.current === controller) streamAbortRef.current = null; setLoading(false); }
  }
  return <div className={`chat-layout ${contextOpen ? "" : "chat-layout-context-closed"}`}><aside className="conversation-rail"><div className="conversation-head"><div><div className="eyebrow accent-eyebrow">Assistant</div><h2>Conversations</h2></div><button className="icon-button subtle" aria-label="New conversation" onClick={newConversation}><Plus size={17} /></button></div><button className="new-chat-button" onClick={newConversation}><Plus size={16} /> New conversation</button><div className="conversation-list">{conversations.map((conversation, index) => <button key={conversation.id ?? conversation.title} className={`conversation-item ${activeConversation === index ? "conversation-item-active" : ""}`} onClick={() => { if (conversation.id) selectConversation(conversation.id, index); }}><span className="conversation-icon"><MessageSquare size={15} /></span><span className="conversation-info"><strong>{conversation.title}</strong><small>{conversation.preview}</small></span><time>{conversation.time}</time></button>)}{!conversations.length && <div className="conversation-empty">No saved conversations yet.</div>}{hasMoreConversations && <button className="button button-secondary load-more-button" type="button" disabled={loadingMoreConversations} onClick={() => void loadConversations(true)}>{loadingMoreConversations ? "Loading…" : "Load more conversations"}</button>}</div><div className="rail-footer"><div className="usage-label"><span>Conversation history</span><strong>{remoteConversations.length}</strong></div><small>History is isolated to the current organization and signed-in user.</small></div></aside>
    <section className="chat-main"><div className="chat-header"><div><div className="eyebrow accent-eyebrow">Secure chat</div><h1>{conversations[activeConversation]?.title ?? "New conversation"}</h1></div><div className="chat-header-actions"><span className="secure-badge"><ShieldCheck size={14} /> Protected</span>{!contextOpen && <button className="button button-secondary context-toggle" onClick={() => setContextOpen(true)}><ShieldCheck size={14} /> Context</button>}<div className="chat-menu-wrap" ref={menuSurfaceRef}><button className="icon-button subtle" aria-label="Conversation options" aria-expanded={menuOpen} aria-haspopup="menu" aria-controls="conversation-menu" onClick={() => setMenuOpen(!menuOpen)}><MoreHorizontal size={18} /></button>{menuOpen && <div className="chat-menu" id="conversation-menu" role="menu"><button role="menuitem" onClick={newConversation}><Plus size={14} /> New conversation</button><button role="menuitem" onClick={() => { onNavigate("settings"); setMenuOpen(false); }}><Settings size={14} /> Privacy & security</button></div>}</div></div></div><div className="message-scroll" ref={messageScrollRef} aria-live="polite"><div className="date-divider"><span>{activeConversationRecord ? formatRelativeDate(activeConversationRecord.updated_at, now) : "Today"}</span></div>{messages.map((message) => <MessageBubble key={message.id} message={message} avatar={avatar} />)}{error && <div className="request-error" role="alert"><AlertTriangle size={16} />{error}</div>}{!messages.length && <div className="empty-state"><MessageSquare size={20} /><strong>No messages yet</strong><span>Start a conversation with an authorized workspace question.</span></div>}</div><div className="composer-wrap"><div className="suggestion-row"><button type="button" onClick={() => setInput("What can you help me with?")}>What can you help me with?</button><button type="button" onClick={() => setInput("Summarize our latest updates")}>Summarize latest updates</button></div><form className="composer" onSubmit={submitMessage}><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) void submitMessage(event); }} placeholder="Ask a question about your workspace…" rows={1} aria-label="Ask your workspace" /><button className={loading ? "stop-button" : "send-button"} type={loading ? "button" : "submit"} onClick={loading ? cancelStream : undefined} disabled={!loading && !input.trim()} aria-label={loading ? "Stop generating" : "Send question"}>{loading ? <Square size={15} fill="currentColor" /> : <Send size={18} />}</button></form><div className="composer-note"><LockKeyhole size={12} /> Answers are limited to sources you’re authorized to access <span>·</span> <button type="button" onClick={() => onNavigate("settings")}>Privacy & security</button></div></div></section>
    {contextOpen && <aside className="context-panel"><div className="context-title"><h3>Answer context</h3><button className="icon-button subtle" aria-label="Close context panel" onClick={() => setContextOpen(false)}><X size={16} /></button></div><div className="context-status"><div className="status-check"><ShieldCheck size={18} /></div><div><strong>Access verified</strong><span>Scoped to {organization}</span></div></div><ContextItem icon={Globe2} label="Organization" value={organization} /><ContextItem icon={Users} label="Your access" value="Current organization" /><ContextItem icon={Database} label="Sources searched" value="Authorized sources only" /><div className="context-divider" /><div className="context-tip"><Zap size={16} /><div><strong>Better answers</strong><p>Ask a specific question and I’ll cite the exact source documents used.</p></div></div><div className="source-preview"><div className="source-preview-head"><span>Sources in this answer</span></div>{citedSources.length ? citedSources.map((source) => <SourceRow key={source.document_id} title={source.document_title} type={`Cited · ${source.score.toFixed(2)} · ${source.chunk_id}`} />) : <div className="context-empty">Citations appear here when an answer is grounded in authorized sources.</div>}</div></aside>}
  </div>;
}
