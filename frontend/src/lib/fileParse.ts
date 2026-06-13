import { normalizeDecimalValue } from './formatting';
import { inferMissingCodesFromRows, missingCodesRecordFromInferred } from './missingCodes';
import type { DataRow, FileType, ReadFileResponse } from '../types';

export function normalizeDataDecimals(data: DataRow[], columns: string[]): DataRow[] {
  return data.map((row) => {
    const out = { ...row };
    columns.forEach((col) => {
      if (out[col] !== undefined && out[col] !== null && out[col] !== '') {
        out[col] = normalizeDecimalValue(out[col]) as string | number;
      }
    });
    return out;
  });
}

export function fileTypeFromName(name: string): FileType | null {
  const lower = name.toLowerCase();
  if (lower.endsWith('.sav')) return 'sav';
  if (lower.endsWith('.xlsx')) return 'xlsx';
  if (lower.endsWith('.xls')) return 'xls';
  if (lower.endsWith('.csv')) return 'csv';
  return null;
}

export function parseSpreadsheetFile(file: File): Promise<ReadFileResponse> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Dosya okunamadı'));
    reader.onload = (e) => {
      void (async () => {
        try {
          const XLSX = await import('xlsx');
          const binary = e.target?.result;
          if (typeof binary !== 'string') {
            reject(new Error('Dosya okunamadı'));
            return;
          }

          let wb: import('xlsx').WorkBook;
          if (file.name.toLowerCase().endsWith('.csv')) {
            wb = XLSX.read(binary, { type: 'binary', FS: ';' });
            const wsTry = wb.Sheets[wb.SheetNames[0]];
            const jsonTry = XLSX.utils.sheet_to_json<DataRow>(wsTry, { defval: '', raw: false });
            if (jsonTry.length > 0 && Object.keys(jsonTry[0]).length === 1) {
              wb = XLSX.read(binary, { type: 'binary', FS: ',' });
            }
          } else {
            wb = XLSX.read(binary, { type: 'binary' });
          }

          const ws = wb.Sheets[wb.SheetNames[0]];
          const json = XLSX.utils.sheet_to_json<DataRow>(ws, { defval: '', raw: false });
          if (!json.length) {
            reject(new Error('Dosya boş görünüyor'));
            return;
          }

          const columns = Object.keys(json[0]);
          const inferred = inferMissingCodesFromRows(json);
          const data = normalizeDataDecimals(json, columns);

          resolve({
            data,
            columns,
            labels: {},
            value_labels: {},
            variable_measure: {},
            missing_codes: missingCodesRecordFromInferred(inferred),
            global_missing_code: inferred.global,
            labels_found: 0,
            source: file.name.toLowerCase().endsWith('.csv') ? 'csv' : 'excel',
            row_count: data.length,
          });
        } catch (err) {
          reject(err instanceof Error ? err : new Error('Dosya okunamadı'));
        }
      })();
    };
    reader.readAsBinaryString(file);
  });
}

export function suggestedScaleNamesFromColumns(columns: string[]): string {
  const prefixes = columns
    .filter((c) => /_TOPLAM$/i.test(c))
    .map((c) => c.split('_')[0].toUpperCase());
  return prefixes.length ? [...new Set(prefixes)].join(', ') : '';
}
