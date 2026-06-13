import { describe, expect, it } from 'vitest';
import {
  scalesFromDetection,
  shouldSkipScalesStep,
  shouldSkipTopicStep,
  topicFromEtikKurul,
} from './wizardSkip';

describe('wizardSkip', () => {
  it('skips scales with high registry match', () => {
    expect(shouldSkipScalesStep(
      [{ id: 'oysto', confidence: 'high' }],
      [{ name: 'OYŞTÖ' }],
    )).toBe(true);
  });

  it('shows scales without high match', () => {
    expect(shouldSkipScalesStep(
      [{ id: 'oysto', confidence: 'medium' }],
      [{ name: 'OYŞTÖ' }],
    )).toBe(false);
  });

  it('skips topic when etik has hypotheses', () => {
    const etik = { hypotheses: ['H1: fark vardır'] };
    expect(shouldSkipTopicStep(etik)).toBe(true);
    expect(topicFromEtikKurul(etik)).toContain('H1');
  });

  it('prefills scale names from detection', () => {
    expect(scalesFromDetection([
      { name: 'OYŞTÖ' },
      { name: 'GYA' },
    ])).toBe('OYŞTÖ, GYA');
  });
});
