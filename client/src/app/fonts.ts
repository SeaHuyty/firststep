// Self-hosted at build time by next/font, so the browser never calls Google (the Google Fonts
// API is blocked in mainland China, where the final is held). Choices: docs/standards/ui-spec.md.
import { Bricolage_Grotesque, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

export const plexSans = IBM_Plex_Sans({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  variable: "--font-plex",
  display: "swap",
});

export const bricolage = Bricolage_Grotesque({
  weight: "600",
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
});

export const plexMono = IBM_Plex_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-plex-mono",
  display: "swap",
});
