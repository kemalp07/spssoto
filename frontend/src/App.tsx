import { Header } from './components/layout/Header';
import { ToastStack } from './components/layout/Toast';
import { WizardShell } from './components/wizard/WizardShell';

export default function App() {
  return (
    <>
      <Header />
      <main id="main-content">
        <WizardShell />
      </main>
      <ToastStack />
    </>
  );
}
