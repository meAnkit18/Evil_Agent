import React from "react";

interface Props {
  toolName: string;
  args: unknown;
  description: string;
  onAllow: () => void;
  onDeny: () => void;
}

export function PermissionOverlay({ toolName, onAllow, onDeny }: Props) {
  return (
    <div className="permission-overlay">
      <div className="permission-dialog">
        <div className="permission-dialog__icon">⚠</div>
        <div className="permission-dialog__title">Permission Required</div>
        <div className="permission-dialog__body">
          Agent wants to run{" "}
          <span className="permission-dialog__tool">{toolName}</span>
        </div>
        <div className="permission-dialog__actions">
          <button className="permission-btn permission-btn--deny" onClick={onDeny}>
            Deny
          </button>
          <button className="permission-btn permission-btn--allow" onClick={onAllow}>
            Allow
          </button>
        </div>
      </div>
    </div>
  );
}
