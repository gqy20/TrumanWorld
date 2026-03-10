"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useModal } from "@/lib/hooks";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  size?: "md" | "lg" | "xl" | "2xl" | "full";
  showCloseButton?: boolean;
  title?: string;
  subtitle?: string;
  closeOnEscape?: boolean;
  closeOnBackdrop?: boolean;
}

const sizeClasses = {
  md: "max-w-3xl",
  lg: "max-w-4xl",
  xl: "max-w-5xl",
  "2xl": "max-w-6xl",
  full: "max-w-[90vw]",
};

export function Modal({
  isOpen,
  onClose,
  children,
  size = "lg",
  showCloseButton = true,
  title,
  subtitle,
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
            className={`flex max-h-[90vh] w-full ${sizeClasses[size]} flex-col overflow-hidden rounded-3xl border border-white/20 bg-white shadow-2xl`}
            onClick={(e) => e.stopPropagation()}
          >
            {(title || showCloseButton) && (
              <div className="flex items-center justify-between border-b border-slate-100 bg-linear-to-r from-slate-50 to-white px-6 py-4">
                <div>
                  {title && (
                    <h2 className="text-xl font-semibold text-ink">{title}</h2>
                  )}
                  {subtitle && (
                    <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>
                  )}
                </div>
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
            )}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
