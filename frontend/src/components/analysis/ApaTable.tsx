import { ApaNote, ApaRichText } from './ApaRichText';
import { splitApaTitle } from '../../lib/apaTable';
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
        <div className="apaTableNumber">
          <ApaRichText value={num} />
        </div>
        {caption ? (
          <div className="apaTableCaption">
            <ApaRichText value={caption} />
          </div>
        ) : null}
      </div>
      <div className="apaTableWrap">
        <table className="apaTable">
          <thead>
            <tr>
              {result.headers.map((h, i) => (
                <th key={`${String(h)}-${i}`}>
                  <ApaRichText value={h} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, ri) => (
              <tr key={ri}>
                {row.map((c, ci) => (
                  <td key={ci}>
                    <ApaRichText value={c} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {result.note ? <ApaNote note={result.note} /> : null}
      </div>
    </>
  );
}
