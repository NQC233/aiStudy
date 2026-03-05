export function normalizeBlockDisplayText(raw) {
    if (!raw) {
        return '';
    }
    let text = raw;
    text = text.replace(/```[\s\S]*?```/g, (matched) => matched.replace(/```/g, '').trim());
    text = text.replace(/`([^`]+)`/g, '$1');
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '$1');
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1');
    text = text.replace(/<[^>]+>/g, ' ');
    text = text.replace(/^#{1,6}\s+/gm, '');
    text = text.replace(/^\s*>\s?/gm, '');
    text = text.replace(/^\s*[-*+]\s+/gm, '');
    text = text.replace(/^\s*\d+\.\s+/gm, '');
    text = text.replace(/[*_~]/g, '');
    text = text.replace(/\|/g, ' ');
    text = text.replace(/&nbsp;/g, ' ');
    text = text.replace(/&amp;/g, '&');
    text = text.replace(/&lt;/g, '<');
    text = text.replace(/&gt;/g, '>');
    text = text.replace(/&quot;/g, '"');
    text = text.replace(/&#39;/g, "'");
    text = text.replace(/[ \t]+/g, ' ');
    text = text.replace(/\n{3,}/g, '\n\n');
    return text.trim();
}
