import { describe, expect, it, beforeEach } from 'vitest';
import { useAppStore } from '../stores/useAppStore';

describe('recomputeAutoSkips', () => {
  beforeEach(() => {
    useAppStore.getState().reset();
  });

  it('prefills research topic and scale names without skipping wizard steps', () => {
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

    expect(wizard.autoSkippedSteps.size).toBe(0);
    expect(wizard.scaleNames).toBe('OYŞTÖ');
    expect(wizard.researchTopic).toContain('Cinsiyet');
  });
});
