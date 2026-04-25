import React from "react";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  style?: React.CSSProperties;
}

export function Card({ children, className, onClick, style }: CardProps) {
  return (
    <div
      className={`uav-card${className ? ` ${className}` : ""}`}
      onClick={onClick}
      style={{
        background: "var(--ha-card-background)",
        borderRadius: "var(--ha-card-border-radius)",
        border: "1px solid var(--ha-card-border-color)",
        boxShadow: "var(--ha-card-box-shadow)",
        padding: "var(--ha-space-4)",
        color: "var(--primary-text-color)",
        fontFamily: "var(--ha-font-family-body)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
