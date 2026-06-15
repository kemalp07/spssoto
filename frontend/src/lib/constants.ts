import type { WizardStepId } from '../types';

export const STEPS: WizardStepId[] = [
  'upload',
  'anket',
  'etikkurul',
  'oneri',
  'variables',
  'plan',
  'results',
  'review',
];

export const STEP_LABELS: Record<WizardStepId, string> = {
  upload: 'Dosya',
  anket: 'Anket',
  etikkurul: 'Etik Kurul',
  oneri: 'Analiz Önerisi',
  variables: 'Değişkenler',
  plan: 'Plan',
  results: 'Sonuçlar',
  review: 'Gözden Geçir',
};

export const STEP_ICONS: Record<WizardStepId, string> = {
  upload: '📁',
  anket: '📋',
  etikkurul: '📄',
  oneri: '💡',
  variables: '🔢',
  plan: '📊',
  results: '✅',
  review: '🔍',
};

export const EXCLUDE_PATTERNS = [
  /^(anket_no|id|no|sira|num|serial)$/i,
  /^[a-z]+_\d+(_ters)?$/i,
  /^[A-Z]+_\d+(_T)?$/,
  /_\d+$/,
  /^LG10/i,
  /^LOG/i,
  /^SQRT/i,
  /^ln/i,
];

export const GROUPING_PATTERNS = [
  /cinsiyet/i, /gender/i, /sex\b/i,
  /bolum/i, /department/i, /faculty/i, /fakulte/i,
  /medeni/i, /marital/i,
  /egitim/i, /education/i,
  /gelir/i, /income/i,
  /meslek/i, /occupation/i, /job\b/i,
  /sigara/i, /tobacco/i, /smoking/i,
  /alkol/i, /alcohol/i,
  /ilac/i, /medication/i,
  /kronik/i, /chronic/i,
  /bölge/i, /bolge/i, /region/i,
  /okul/i, /school/i,
  /sinif\b/i, /class\b/i,
];

export const OUTCOME_CAT_PATTERNS = [
  /kategori/i, /category/i,
  /_grup(u)?$/i, /_group$/i,
  /_binary$/i, /_sinif$/i, /_class$/i,
  /_risk$/i, /_durum$/i, /_status$/i,
  /_level$/i, /_seviye$/i,
];

export const OUTCOME_CONT_PATTERNS = [
  /_toplam$/i, /_total$/i, /_sum$/i,
  /_puan$/i, /_score$/i, /_skor$/i,
  /_ortalama$/i, /_mean$/i, /_avg$/i,
  /_endeks$/i, /_index$/i,
];

export const ITEM_COL_PATTERN = /^[a-zA-Z]+_\d+(_ters|_T)?$/i;
