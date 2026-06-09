import React, { useRef, useEffect } from "react";

interface Props {
  onSubmit: (text: string) => void;
  disabled: boolean;
}

export function PromptBar({ onSubmit, disabled }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const handleGlobalKey = (e: KeyboardEvent) => {
      // Focus prompt on any printable key (when not already focused)
      if (
        document.activeElement !== textareaRef.current &&
        e.key.length === 1 &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey
      ) {
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleGlobalKey);
    return () => window.removeEventListener("keydown", handleGlobalKey);
  }, []);

  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const submit = () => {
    const el = textareaRef.current;
    if (!el) return;
    const text = el.value.trim();
    if (!text || disabled) return;
    el.value = "";
    el.style.height = "auto";
    onSubmit(text);
  };

  return (
    <div className="prompt-bar">
      <textarea
        ref={textareaRef}
        className="prompt-input"
        placeholder="Give an instruction to the agent..."
        rows={1}
        spellCheck={false}
        autoComplete="off"
        disabled={disabled}
        onInput={autoGrow}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <span className="prompt-hint">↵ Enter</span>
    </div>
  );
}
