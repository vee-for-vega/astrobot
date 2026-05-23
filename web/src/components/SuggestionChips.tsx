type Props = {
  suggestions: string[];
  onPick: (s: string) => void;
};

export default function SuggestionChips({ suggestions, onPick }: Props) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {suggestions.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onPick(s)}
          className="rounded-full border border-neutral-300 bg-white px-3 py-1 text-xs text-neutral-700 transition hover:border-neutral-500 hover:text-neutral-900"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
