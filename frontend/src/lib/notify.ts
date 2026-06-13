import { getAppState } from './storeAccess';
import type { ToastMessage } from '../types';

export function notify(text: string, type: ToastMessage['type'] = 'info'): void {
  getAppState().showToast(text, type);
}

export function notifyError(text: string): void {
  notify(text, 'error');
}

export function notifySuccess(text: string): void {
  notify(text, 'success');
}
