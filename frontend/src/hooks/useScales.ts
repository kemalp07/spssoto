import { useCallback } from 'react';
import { detectScalesInline, scaleMatchingInline } from '../lib/scaleApi';
import { useAppStore } from '../stores/useAppStore';

export function useScales() {
  const setScaleNames = useAppStore((s) => s.setScaleNames);
  const detected = useAppStore((s) => s.scales.detected);
  const registryMeta = useAppStore((s) => s.scales.registryMeta);
  const scaleNames = useAppStore((s) => s.wizard.scaleNames);

  const runDetectScalesEarly = useCallback(() => detectScalesInline(), []);
  const runScaleMatching = useCallback(() => scaleMatchingInline(), []);

  return {
    detected,
    registryMeta,
    scaleNames,
    isAutoSkipped: false,
    setScaleNames,
    runDetectScalesEarly,
    runScaleMatching,
  };
}
