import Markdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ content }: { content: string }) {
  const markdown = content.replace(/^[ \t]{0,3}#{1,6}[ \t]*$/gm, "");
  return (
    <div className="assistant-content">
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {markdown}
      </Markdown>
    </div>
  );
}
