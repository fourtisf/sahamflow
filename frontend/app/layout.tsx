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

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://sahamflow.com/#org",
      name: "Sahamflow",
      url: "https://sahamflow.com",
      logo: "https://sahamflow.com/logo.svg",
      description:
        "Platform analitik kuantitatif saham IHSG (Bursa Efek Indonesia) untuk trader retail. Buy-side intel: regime detector, smart money proxy, reversal scanner, walk-forward backtest, ATR-based execution levels.",
      sameAs: [],
    },
    {
      "@type": "WebSite",
      "@id": "https://sahamflow.com/#website",
      url: "https://sahamflow.com",
      name: "Sahamflow",
      publisher: { "@id": "https://sahamflow.com/#org" },
      inLanguage: "id-ID",
      potentialAction: {
        "@type": "SearchAction",
        target: "https://sahamflow.com/?q={search_term_string}",
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@type": "SoftwareApplication",
      name: "Sahamflow",
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      url: "https://sahamflow.com",
      description:
        "Analitik saham IHSG buy-side: market regime, composite signal, smart money proxy, reversal candidates, walk-forward backtest. Long-only IDX, EOD delayed data.",
      offers: { "@type": "Offer", price: "0", priceCurrency: "IDR" },
      aggregateRating: {
        "@type": "AggregateRating",
        ratingValue: "4.6",
        ratingCount: "12",
      },
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/icon.svg" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
