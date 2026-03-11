"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useModal } from "@/lib/hooks";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  variant?: "panel" | "workspace" | "inspector" | "fullscreen";
  showCloseButton?: boolean;
  title?: string;
  subtitle?: string;
  headerActions?: React.ReactNode;
  closeOnEscape?: boolean;
  closeOnBackdrop?: boolean;
}

interface WorkspaceModalShellProps {
  sidebar?: React.ReactNode;
  toolbar?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  sidebarClassName?: string;
  contentClassName?: string;
}

const variantClasses = {
  panel: "max-w-3xl min-h-[28rem]",
  workspace: "max-w-6xl h-[88vh]",
  inspector: "max-w-[88vw] h-[90vh]",
  fullscreen: "max-w-[92vw] h-[92vh]",
};

export function Modal({
  isOpen,
  onClose,
  children,
  variant = "panel",
  showCloseButton = true,
  title,
  subtitle,
  headerActions,
  closeOnEscape = true,
  closeOnBackdrop = true,
}: ModalProps) {
  const { handleBackdropClick } = useModal({
    isOpen,
    onClose,
    closeOnEscape,
    closeOnBackdrop,
  });

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs"
          onClick={handleBackdropClick}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className={`flex max-h-[94vh] w-full ${variantClasses[variant]} flex-col overflow-hidden rounded-3xl border border-white/20 bg-white shadow-2xl`}
            onClick={(e) => e.stopPropagation()}
          >
            {(title || showCloseButton || headerActions) && (
              <div className="flex items-center justify-between border-b border-slate-100 bg-linear-to-r from-slate-50 to-white px-6 py-4">
                <div>
                  {title && (
                    <h2 className="text-xl font-semibold text-ink">{title}</h2>
                  )}
                  {subtitle && (
                    <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {headerActions}
                  {showCloseButton && (
                    <button
                      type="button"
                      onClick={onClose}
                      className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        className="h-5 w-5"
                      >
                        <path d="M18 6L6 18M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            )}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function WorkspaceModalShell({
  sidebar,
  toolbar,
  children,
  footer,
  sidebarClassName = "w-72",
  contentClassName = "px-6 py-5",
}: WorkspaceModalShellProps) {
  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      {sidebar ? (
        <aside className={`flex shrink-0 flex-col border-r border-slate-100 bg-slate-50/50 ${sidebarClassName}`}>
          {sidebar}
        </aside>
      ) : null}
      <div className="min-w-0 flex-1 overflow-hidden bg-white">
        {toolbar ? <div className="border-b border-slate-100 bg-slate-50/60 px-6 py-3">{toolbar}</div> : null}
        <div className={`h-full overflow-auto ${contentClassName}`}>{children}</div>
        {footer ? <div className="border-t border-slate-100 bg-white px-6 py-3">{footer}</div> : null}
      </div>
    </div>
  );
}
