import { useId, useRef, useState } from 'react';

const DEFAULT_ACCEPT = '.sav,.xlsx,.xls,.csv';
const DEFAULT_FORMATS = ['.sav', '.xlsx', '.xls', '.csv'];

interface FileDropZoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
  loading?: boolean;
  uploaded?: boolean;
  fileName?: string;
  fileMeta?: string;
  onReset?: () => void;
  title?: string;
  subtitle?: string;
  icon?: string;
  accept?: string;
  formats?: string[];
}

export function FileDropZone({
  onFile,
  disabled = false,
  loading = false,
  uploaded = false,
  fileName,
  fileMeta,
  onReset,
  title = 'Veri dosyanızı sürükleyin',
  subtitle = 'SPSS (.sav), Excel veya CSV dosyanızı sürükleyin — veya tıklayarak seçin',
  icon = '📁',
  accept = DEFAULT_ACCEPT,
  formats = DEFAULT_FORMATS,
}: FileDropZoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const pickFile = () => {
    if (!disabled && !loading && !uploaded) inputRef.current?.click();
  };

  const handleFile = (file: File | undefined) => {
    if (!file || disabled || loading) return;
    onFile(file);
  };

  const zoneClass = [
    'uploadZone',
    dragOver ? 'uploadZoneDrag' : '',
    uploaded ? 'uploadZoneUploaded' : '',
    loading ? 'uploadZoneLoading' : '',
  ].filter(Boolean).join(' ');

  return (
    <div>
      <div
        className={zoneClass}
        role="button"
        tabIndex={uploaded || loading ? -1 : 0}
        aria-label={uploaded ? `Yüklü dosya: ${fileName}` : title}
        aria-busy={loading}
        onClick={pickFile}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !uploaded && !loading) {
            e.preventDefault();
            pickFile();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !uploaded && !loading) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!uploaded && !loading) handleFile(e.dataTransfer.files[0]);
        }}
      >
        {loading ? (
          <>
            <div className="uploadZoneIcon" aria-hidden>⏳</div>
            <h2 className="uploadZoneTitle">Dosya okunuyor...</h2>
            <p>{fileName ?? 'Lütfen bekleyin'}</p>
          </>
        ) : uploaded && fileName ? (
          <>
            <div className="uploadZoneIcon" aria-hidden>✅</div>
            <div className="uploadFileName">{fileName}</div>
            {fileMeta ? <div className="uploadFileMeta">{fileMeta}</div> : null}
            {onReset ? (
              <button
                type="button"
                className="uploadResetLink"
                onClick={(e) => {
                  e.stopPropagation();
                  onReset();
                }}
              >
                Farklı dosya yükle
              </button>
            ) : null}
          </>
        ) : (
          <>
            <div className="uploadZoneIcon" aria-hidden>{icon}</div>
            <h2 className="uploadZoneTitle">{title}</h2>
            <p>{subtitle}</p>
            <div className="formatBadges">
              {formats.map((fmt) => (
                <span key={fmt} className="formatBadge">{fmt}</span>
              ))}
            </div>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        className="visuallyHidden"
        aria-hidden
        tabIndex={-1}
        onChange={(e) => {
          handleFile(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </div>
  );
}
