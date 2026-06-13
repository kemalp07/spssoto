import { useAppStore, type AppState } from '../stores/useAppStore';

/**
 * Read the latest Zustand snapshot outside React render/subscriptions.
 *
 * Use in async handlers, callbacks, and module-level helpers where a hook
 * closure would be stale. This is intentionally non-reactive: components
 * will not re-render when only getAppState() is used.
 *
 * In components, prefer `useAppStore(selector)` so UI stays in sync with state.
 */
export function getAppState(): AppState {
  return useAppStore.getState();
}
