import { describe, expect, it, beforeEach } from 'vitest';
import { useAppStore } from '../stores/useAppStore';

describe('recomputeAutoSkips', () => {
  beforeEach(() => {
    useAppStore.getState().reset();
  });

  it('marks scales and topic skipped with high-confidence detection + etik hypotheses', () => {
    useAppStore.setState((s) => ({
      scales: {
        ...s.scales,
        detected: [{ name: 'OYŞTÖ', source: 'registry' }],
        registryMeta: {
          ...s.scales.registryMeta,
          registry_matched: [{ id: 'oysto', confidence: 'high', name: 'OYŞTÖ' }],
        },
      },
      documents: {
        ...s.documents,
        context: {
          etik_kurul: {
            hypotheses: ['Cinsiyet ile OYS arasında fark vardır.'],
          },
        },
      },
    }));

    useAppStore.getState().recomputeAutoSkips();
    const { wizard } = useAppStore.getState();

    expect(wizard.autoSkippedSteps.has('scales')).toBe(true);
    expect(wizard.autoSkippedSteps.has('topic')).toBe(true);
    expect(wizard.scaleNames).toBe('OYŞTÖ');
    expect(wizard.researchTopic).toContain('Cinsiyet');
  });

  it('does not skip topic without etik kurul', () => {
    useAppStore.getState().recomputeAutoSkips();
    expect(useAppStore.getState().wizard.autoSkippedSteps.has('topic')).toBe(false);
  });
});
