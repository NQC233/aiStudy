import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';
import texmath from 'markdown-it-texmath';
import katex from 'katex';

const markdownEngine = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
});

markdownEngine.use(texmath, {
  engine: katex,
  delimiters: 'dollars',
  katexOptions: {
    throwOnError: false,
    strict: 'ignore',
  },
});

export function renderMarkdownToSafeHtml(raw: string | null | undefined): string {
  if (!raw || !raw.trim()) {
    return '<p>当前块没有可展示文本。</p>';
  }

  const rendered = markdownEngine.render(raw);
  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
  });
}
