import { useEffect, useRef, useState } from "react";

type Props = {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
};

export default function PromptInput({
  onSubmit,
  disabled = false,
  placeholder = "Type your question",
  autoFocus = true,
}: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    setValue("");
    onSubmit(text);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="rounded-xl border border-neutral-300 bg-white p-3 shadow-sm focus-within:border-neutral-500">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        rows={3}
        className="block w-full resize-none bg-transparent text-base text-neutral-900 placeholder:text-neutral-400 focus:outline-none disabled:opacity-50"
      />
      <div className="mt-2 flex items-center justify-between text-xs text-neutral-400">
        <span>Press Enter to send · Shift+Enter for newline</span>
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="rounded-md border border-neutral-300 bg-neutral-900 px-3 py-1 text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          Send
        </button>
      </div>
    </div>
  );
}
