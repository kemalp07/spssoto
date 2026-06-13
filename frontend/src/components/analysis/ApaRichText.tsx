import { Fragment, type ReactNode } from 'react';

type OpenTag = 'em' | 'strong';

const INLINE_TAG_RE = /<\/?(?:em|strong)>|<[^>]+>/gi;

function parseApaInline(raw: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let key = 0;
  const open: OpenTag[] = [];

  const wrap = (content: ReactNode): ReactNode => {
    let node = content;
    for (let i = open.length - 1; i >= 0; i -= 1) {
      const tag = open[i];
      node = tag === 'em'
        ? <em key={`w-${key}-${i}`}>{node}</em>
        : <strong key={`w-${key}-${i}`}>{node}</strong>;
    }
    return node;
  };

  const pushText = (text: string) => {
    if (!text) return;
    nodes.push(<Fragment key={key++}>{wrap(text)}</Fragment>);
  };

  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const re = new RegExp(INLINE_TAG_RE.source, INLINE_TAG_RE.flags);

  while ((match = re.exec(raw)) !== null) {
    pushText(raw.slice(lastIndex, match.index));
    const tag = match[0].toLowerCase();
    if (tag === '<em>') open.push('em');
    else if (tag === '</em>' && open[open.length - 1] === 'em') open.pop();
    else if (tag === '<strong>') open.push('strong');
    else if (tag === '</strong>' && open[open.length - 1] === 'strong') open.pop();
    lastIndex = re.lastIndex;
  }
  pushText(raw.slice(lastIndex));

  return nodes.length ? nodes : [raw];
}

export function ApaRichText({ value }: { value: unknown }) {
  return <>{parseApaInline(String(value ?? ''))}</>;
}

export function ApaNote({ note }: { note: unknown }) {
  if (note == null || note === '') return null;
  const raw = String(note);
  const notTr = raw.match(/^Not\.\s*(.*)$/is);
  if (notTr) {
    return (
      <div className="apaNote">
        <span className="noteLabel">Not.</span>{' '}
        <ApaRichText value={notTr[1]} />
      </div>
    );
  }
  const noteEn = raw.match(/^Note\.\s*(.*)$/is);
  if (noteEn) {
    return (
      <div className="apaNote">
        <span className="noteLabel">Note.</span>{' '}
        <ApaRichText value={noteEn[1]} />
      </div>
    );
  }
  return (
    <div className="apaNote">
      <ApaRichText value={raw} />
    </div>
  );
}
