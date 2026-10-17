import type { Metadata } from "next";
import { bricolage, plexMono, plexSans } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "FirstStep",
  description: "A trustworthy first advisor for first-time investors. Educational simulation.",
  icons: { icon: "/brand/logo-mark.svg" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${plexSans.variable} ${bricolage.variable} ${plexMono.variable}`}>
      <body className="min-h-dvh bg-canvas text-ink antialiased">{children}</body>
    </html>
  );
}
