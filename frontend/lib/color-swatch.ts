const SWATCHES: Record<string, string> = {
  black: "#18181b",
  white: "#e4e4e7",
  "navy blue": "#1e3a5f",
  maroon: "#7f1d1d",
  "emerald green": "#047857",
  mustard: "#ca8a04",
  beige: "#d6c3a5",
  "powder blue": "#93c5fd",
  coral: "#f97366",
  olive: "#4d7c0f",
  lavender: "#c4b5fd",
  rust: "#c2410c",
};

export function swatchForColor(color: string): string {
  return SWATCHES[color] ?? "#a1a1aa";
}

export function formatInr(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}
