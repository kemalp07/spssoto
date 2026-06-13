import { renderApaCell, renderApaNoteHtml, splitApaTitle } from '../../lib/apaTable';
import type { AnalysisResult } from '../../types';

interface ApaTableProps {
  result: AnalysisResult;
}

export function ApaTable({ result }: ApaTableProps) {
  if (!result.headers || !result.rows) return null;
  const { num, caption } = splitApaTitle(result.title);

  return (
    <>
      <div className="apaTableHeading">
        <div className="apaTableNumber">{renderApaCell(num)}</div>
        {caption ? (
          <div className="apaTableCaption">{renderApaCell(caption)}</div>
        ) : null}
      </div>
      <div className="apaTableWrap">
        <table className="apaTable">
          <thead>
            <tr>
              {result.headers.map((h) => (
                <th key={String(h)} dangerouslySetInnerHTML={{ __html: renderApaCell(h) }} />
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, ri) => (
              <tr key={ri}>
                {row.map((c, ci) => (
                  <td key={ci} dangerouslySetInnerHTML={{ __html: renderApaCell(c) }} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {result.note ? (
          <div dangerouslySetInnerHTML={{ __html: renderApaNoteHtml(result.note) }} />
        ) : null}
      </div>
    </>
  );
}
