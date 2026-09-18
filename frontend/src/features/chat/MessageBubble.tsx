import { Bot, FileText, LockKeyhole } from "lucide-react";
import type { Message } from "../../types";
import { MarkdownContent } from "./MarkdownContent";

type Citation = NonNullable<Message["citations"]>[number];

function SourceDisclosure({ citations }: { citations: Citation[] }) {
  const uniqueCitations = citations.filter((citation, index, sourceList) => sourceList.findIndex(
    (item) => item.document_id === citation.document_id && item.chunk_id === citation.chunk_id,
  ) === index);

  if (!uniqueCitations.length) return null;

  return <details className="citation-disclosure">
    <summary><FileText size={13} /> Sources <span className="citation-count">{uniqueCitations.length}</span></summary>
    <div className="citation-details" role="list" aria-label="Sources used for this answer">
      {uniqueCitations.map((citation, index) => <div className="citation-detail" key={`${citation.document_id}:${citation.chunk_id}`} role="listitem">
        <span className="citation-index">{index + 1}</span>
        <span className="citation-detail-copy"><strong>{citation.document_title}</strong><small>Relevant passage · {citation.score.toFixed(2)} match</small><code>{citation.chunk_id}</code></span>
      </div>)}
    </div>
  </details>;
}

function StreamingIndicator() {
  return <span className="streaming-indicator" aria-label="Generating response"><span /><span /><span /></span>;
}

export function MessageBubble({ message, avatar = "ME" }: { message: Message; avatar?: string }) {
  if (message.role === "user") return <div className="message-row user-row"><div className="user-bubble">{message.content}</div><div className="profile-avatar message-avatar">{avatar}</div></div>;
  return <div className="message-row"><div className="assistant-avatar"><Bot size={16} /></div><div className="assistant-message">
    {message.content ? <MarkdownContent content={message.content} /> : message.streaming ? <StreamingIndicator /> : null}
    {message.streaming && message.content && <span className="streaming-cursor" aria-hidden="true" />}
    {!message.streaming && message.mode === "grounded" && <div className="message-meta"><SourceDisclosure citations={message.citations ?? []} /></div>}
    {!message.streaming && message.mode === "refused" && <div className="message-meta"><span className="refused-label"><LockKeyhole size={12} /> Needs authorized evidence</span></div>}
  </div></div>;
}
