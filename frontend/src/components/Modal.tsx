import { useEffect, useId, useRef, type ReactNode } from "react";

export function Modal({ title, children, onClose, busy = false, className = "" }: {
  title: string; children: ReactNode; onClose: () => void; busy?: boolean; className?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    const previousOverflow = document.body.style.overflow;
    element?.showModal();
    document.body.style.overflow = "hidden";
    return () => { element?.close(); document.body.style.overflow = previousOverflow; };
  }, []);
  return <dialog ref={dialog} className={`modal ${className}`} aria-labelledby={titleId}
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    <header className="modal-header"><div><p className="eyebrow">GARDIROP DETAYLARI</p><h2 id={titleId}>{title}</h2></div><button type="button" className="icon-button" aria-label="Kapat" disabled={busy} onClick={onClose}>×</button></header>
    {children}
  </dialog>;
}
