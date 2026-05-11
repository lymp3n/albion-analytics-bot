import { PropsWithChildren } from "react";

type PreviewModalProps = PropsWithChildren<{
  open: boolean;
  title: string;
  onClose: () => void;
}>;

export function PreviewModal({ open, title, onClose, children }: PreviewModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-shell border border-white/15 bg-[#15151d]/90 p-5 backdrop-blur-xl2"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xl font-medium">{title}</h3>
          <button className="rounded-xl bg-white/10 px-3 py-2 text-sm" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
