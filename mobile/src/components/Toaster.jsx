// Tiny toast notification system. Use the hook:
//
//   const toast = useToaster();
//   toast.show('Saved', 'ok'); toast.show('Failed', 'err');
//
// And mount <Toaster /> once near the root of the page.

import { createContext, useCallback, useContext, useRef, useState } from 'react';

const ToastContext = createContext(null);

export function ToasterProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  const show = useCallback((message, kind = 'info', duration = 2500) => {
    const id = ++counter.current;
    setToasts((arr) => [...arr, { id, message, kind }]);
    setTimeout(() => {
      setToasts((arr) => arr.filter((t) => t.id !== id));
    }, duration);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="toaster">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>{t.message}</div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToaster() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Allow use without provider (no-op) so component dev is forgiving.
    return { show: (m) => console.log('[toast]', m) };
  }
  return ctx;
}
