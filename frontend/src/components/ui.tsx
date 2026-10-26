import { useEffect, useRef, useId } from "react";
import type {
  ReactNode,
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  HTMLAttributes,
  Ref,
} from "react";
import {
  X,
  Check,
  LoaderCircle,
  CircleAlert,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import { initials, label } from "../api";

export function Button({
  children,
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button className={`button ${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function Avatar({
  name,
  small = false,
}: {
  name: string;
  small?: boolean;
}) {
  const colors = ["#eef2ff", "#e6f5f0", "#fff1f2", "#f3edff", "#edf5ff"];
  return (
    <span
      className={`avatar ${small ? "small" : ""}`}
      style={{ background: colors[name.charCodeAt(0) % colors.length] }}
    >
      {initials(name)}
    </span>
  );
}
export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value}`}>
      <span className="badge-dot" />
      {label(value)}
    </span>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={20} className="spin" /> Loading your workspace…
    </div>
  );
}
export function ErrorBox({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="error-box" role="alert">
      <CircleAlert size={18} />
      <span>{message}</span>
      {retry && <Button onClick={retry}>Try again</Button>}
    </div>
  );
}
export function Empty({
  title,
  text,
  children,
}: {
  title: string;
  text: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Sparkles size={24} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}
export function Modal({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => {
      dialog.close();
    };
  }, []);
  return (
    <dialog
      aria-labelledby={titleId}
      className={`modal ${wide ? "wide" : ""}`}
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            onClose();
        }
      }}
    >
      <div className="modal-heading">
        <div>
          <h2 id={titleId}>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function SectionHeading({
  title,
  right,
}: {
  title: string;
  right?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <h3>{title}</h3>
      {right}
    </div>
  );
}
export function FuturePage({
  name,
  description,
  icon,
}: {
  name: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <div className="future-page">
      <div className="future-icon">{icon}</div>
      <span className="eyebrow">A LITTLE FURTHER DOWN THE ROAD</span>
      <h1>{name}</h1>
      <p>{description}</p>
      <span className="future-badge">
        Planned for a future session <ArrowUpRight size={14} />
      </span>
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} />;
}
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} />;
}
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} />;
}
export function Card(props: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} />;
}
export function Table(props: HTMLAttributes<HTMLTableElement>) {
  return <table {...props} />;
}
export function Sidebar(
  props: HTMLAttributes<HTMLElement> & { ref?: Ref<HTMLElement> },
) {
  return <aside {...props} />;
}
export function Toast({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div className="toast" role="status">
      <span>
        <Check size={15} />
      </span>
      {message}
      <button
        className="icon-button"
        aria-label="Dismiss notification"
        onClick={onDismiss}
      >
        <X size={14} />
      </button>
    </div>
  );
}
export function Tabs({
  value,
  onChange,
  items,
  className = "settings-tabs",
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  items: { value: string; label: ReactNode }[];
  className?: string;
  label: string;
}) {
  return (
    <div className={className} role="group" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.value}
          aria-pressed={item.value === value}
          className={item.value === value ? "active selected" : ""}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
