import type { Metadata, Viewport } from "next";
import "./globals.css";

const SITE_URL = "https://sahamflow.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Sahamflow — Analitik Saham IHSG untuk Trader Retail",
    template: "%s · Sahamflow",
  },
  description:
    "Platform analitik saham IHSG: deteksi market regime, screener teknikal, foreign flow, bandar detection, position sizer, dan backtest. Data, bukan rekomendasi.",
  keywords: [
    "saham IHSG", "analitik saham", "screener saham", "bandar detection",
    "foreign flow", "market regime", "trading saham Indonesia", "Bursa Efek Indonesia",
  ],
  applicationName: "Sahamflow",
  authors: [{ name: "Sahamflow" }],
  alternates: { canonical: SITE_URL },
  openGraph: {
    type: "website",
    locale: "id_ID",
    url: SITE_URL,
    siteName: "Sahamflow",
    title: "Sahamflow — Analitik Saham IHSG untuk Trader Retail",
    description:
      "Market regime, screener teknikal, foreign flow, bandar detection, position sizer & backtest untuk saham IHSG.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sahamflow — Analitik Saham IHSG",
    description: "Analitik kuantitatif saham IHSG untuk trader retail.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
