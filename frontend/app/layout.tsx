import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "SmartCam", template: "%s · SmartCam" },
  description: "AI-powered smart security camera platform",
  applicationName: "SmartCam",
  appleWebApp: { capable: true, title: "SmartCam", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#0b0e14",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
