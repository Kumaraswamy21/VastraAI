import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Fashion Search",
  description:
    "Conversational shopping assistant for a fashion catalog. Describe an outfit and review ranked product links.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
