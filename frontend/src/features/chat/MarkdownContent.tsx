import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

const citationMarker = /\[doc:[^\]\s]+\s+chunk:[^\]\s]+\]/g;
const unfinishedCitationMarker = /\[doc:[^\]\r\n]*$/i;

export function stripCitationMarkers(content: string): string {
  return content
    .replace(citationMarker, "")
    .replace(unfinishedCitationMarker, "")
    .replace(/[ \t]+([,.;:!?])/g, "$1")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n");
}

export function MarkdownContent({ content }: { content: string }) {
  const markdown = stripCitationMarkers(content).replace(/^[ \t]{0,3}#{1,6}[ \t]*$/gm, "");
  return (
    <div className="assistant-content">
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {markdown}
      </Markdown>
    </div>
  );
}
