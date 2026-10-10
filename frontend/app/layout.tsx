import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "VastraAI — Find the pieces that feel like you", template: "%s | VastraAI" },
  description: "A thoughtful fashion search. Find clothing, footwear and accessories through a conversation that remembers your preferences.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
