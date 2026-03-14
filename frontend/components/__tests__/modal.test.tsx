import { render, screen, fireEvent } from "@testing-library/react";
import { Modal, WorkspaceModalShell } from "@/components/modal";

// Mock framer-motion
jest.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, style, onClick }: { children: React.ReactNode; className?: string; style?: React.CSSProperties; onClick?: () => void }) => (
      <div className={className} style={style} onClick={onClick}>
        {children}
      </div>
    ),
    span: ({ children, className, style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) => (
      <span className={className} style={style}>
        {children}
      </span>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock useModal hook
jest.mock("@/lib/hooks", () => ({
  useModal: ({ onClose, closeOnBackdrop }: { onClose: () => void; closeOnBackdrop: boolean }) => ({
    handleBackdropClick: closeOnBackdrop ? onClose : () => {},
  }),
}));

describe("Modal", () => {
  const onClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders children when open", () => {
    render(
      <Modal isOpen onClose={onClose}>
        <div>Modal Content</div>
      </Modal>
    );

    expect(screen.getByText("Modal Content")).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(
      <Modal isOpen={false} onClose={onClose}>
        <div>Modal Content</div>
      </Modal>
    );

    expect(screen.queryByText("Modal Content")).not.toBeInTheDocument();
  });

  it("renders title when provided", () => {
    render(
      <Modal isOpen onClose={onClose} title="Test Modal">
        <div>Content</div>
      </Modal>
    );

    expect(screen.getByText("Test Modal")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(
      <Modal isOpen onClose={onClose} subtitle="Modal description">
        <div>Content</div>
      </Modal>
    );

    expect(screen.getByText("Modal description")).toBeInTheDocument();
  });

  it("renders close button by default", () => {
    render(
      <Modal isOpen onClose={onClose}>
        <div>Content</div>
      </Modal>
    );

    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("hides close button when showCloseButton is false", () => {
    render(
      <Modal isOpen onClose={onClose} showCloseButton={false}>
        <div>Content</div>
      </Modal>
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", () => {
    const handleClose = jest.fn();
    render(
      <Modal isOpen onClose={handleClose}>
        <div>Content</div>
      </Modal>
    );

    fireEvent.click(screen.getByRole("button"));

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("renders header actions when provided", () => {
    render(
      <Modal isOpen onClose={onClose} headerActions={<button type="button">Action</button>}>
        <div>Content</div>
      </Modal>
    );

    expect(screen.getByText("Action")).toBeInTheDocument();
  });
});

describe("WorkspaceModalShell", () => {
  it("renders children", () => {
    render(<WorkspaceModalShell>Content</WorkspaceModalShell>);

    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("renders sidebar when provided", () => {
    render(<WorkspaceModalShell sidebar={<div>Sidebar</div>}>Content</WorkspaceModalShell>);

    expect(screen.getByText("Sidebar")).toBeInTheDocument();
  });

  it("renders toolbar when provided", () => {
    render(<WorkspaceModalShell toolbar={<div>Toolbar</div>}>Content</WorkspaceModalShell>);

    expect(screen.getByText("Toolbar")).toBeInTheDocument();
  });

  it("renders footer when provided", () => {
    render(<WorkspaceModalShell footer={<div>Footer</div>}>Content</WorkspaceModalShell>);

    expect(screen.getByText("Footer")).toBeInTheDocument();
  });
});
