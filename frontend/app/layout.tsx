import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartCam",
  description: "AI-powered smart security camera platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
