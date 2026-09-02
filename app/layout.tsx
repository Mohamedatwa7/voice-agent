import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Athyor — Expressive voice AI",
  description:
    "Athyor turns text into expressive speech — laughter, sighs and whispers included — and can clone a voice from a ten-second clip.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans bg-black`}>{children}</body>
    </html>
  );
}
