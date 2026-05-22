// Static showcase data ported verbatim from prototype-dashboard.html. Used as the
// baseline so the dashboard always renders the full approved design; live API data
// is overlaid on top when the backend has it.

export interface StockMeta {
  name: string;
  price: number;
  per: string;
  perC: string;
  pbv: string;
  pbvC: string;
  roe: string;
  der: string;
  rev: string;
  nm: string;
  mcap: string;
  earn: string;
  qlty: string;
  sent: number;
  sentL: string;
  flags: [string, string, string][];
}

export const STOCKS: Record<string, StockMeta> = {
  BREN: { name: "Barito Renewables", price: 9825, per: "42.8×", perC: "am", pbv: "8.4×", pbvC: "am", roe: "19.6%", der: "0.42×", rev: "+28.4%", nm: "22.1%", mcap: "1,287T", earn: "12 Jun", qlty: "7.2", sent: 72, sentL: "Greed · Cautiously Bullish", flags: [["ok", "Auditor stabil", "KAP PwC sejak 2019"], ["ok", "Going concern aman", "cashflow positif 12 kuartal"], ["w", "Valuasi premium", "PER 42.8× vs sektor energy 18.4×"], ["w", "Related party", "14.2% revenue ke afiliasi (wajar)"]] },
  PANI: { name: "Pantai Indah Kapuk", price: 14725, per: "31.2×", perC: "am", pbv: "5.1×", pbvC: "", roe: "16.8%", der: "0.61×", rev: "+19.2%", nm: "18.4%", mcap: "742T", earn: "18 Jun", qlty: "6.8", sent: 68, sentL: "Greed · Bullish", flags: [["ok", "Auditor stabil", "tanpa pergantian 4 tahun"], ["ok", "Likuiditas sehat", "current ratio 2.1×"], ["w", "Valuasi tinggi", "PBV di atas rata-rata properti"], ["w", "Insider selling", "direksi jual 0.3% Mei 2026"]] },
  CUAN: { name: "Petrindo Jaya Kreasi", price: 8150, per: "28.4×", perC: "am", pbv: "6.2×", pbvC: "am", roe: "21.4%", der: "0.38×", rev: "+34.1%", nm: "24.8%", mcap: "612T", earn: "09 Jun", qlty: "7.0", sent: 64, sentL: "Greed · Moderate", flags: [["ok", "Growth kuat", "revenue +34% YoY"], ["ok", "Margin sehat", "net margin 24.8%"], ["w", "Konsentrasi bisnis", "85% revenue dari batu bara"], ["w", "Volatilitas tinggi", "beta 1.8 vs IHSG"]] },
  AMMN: { name: "Amman Mineral", price: 11400, per: "38.6×", perC: "am", pbv: "7.1×", pbvC: "am", roe: "17.2%", der: "0.55×", rev: "+22.6%", nm: "20.1%", mcap: "826T", earn: "15 Jun", qlty: "7.4", sent: 61, sentL: "Greed · Moderate", flags: [["ok", "Cadangan tambang besar", "reserve life 20+ tahun"], ["ok", "Auditor Big 4", "EY sejak IPO"], ["w", "Capex tinggi", "ekspansi smelter ongoing"], ["w", "Harga komoditas", "sensitif harga tembaga global"]] },
  BBCA: { name: "Bank Central Asia", price: 10475, per: "24.1×", perC: "", pbv: "4.8×", pbvC: "", roe: "21.8%", der: "—", rev: "+11.4%", nm: "42.6%", mcap: "1,291T", earn: "24 Jul", qlty: "9.2", sent: 58, sentL: "Neutral · Stable", flags: [["ok", "Bank terbaik IDX", "ROE 21.8% konsisten"], ["ok", "NPL rendah", "rasio kredit macet 1.8%"], ["ok", "Likuiditas kuat", "CASA ratio 82%"], ["ok", "Track record bersih", "tanpa red flag material"]] },
  MDKA: { name: "Merdeka Copper Gold", price: 2470, per: "—", perC: "dn", pbv: "3.2×", pbvC: "", roe: "-4.2%", der: "1.24×", rev: "+8.1%", nm: "-2.4%", mcap: "248T", earn: "20 Jun", qlty: "6.2", sent: 38, sentL: "Fear · Bearish", flags: [["ok", "Aset tambang strategis", "nikel + emas + tembaga"], ["w", "Rugi bersih", "net margin negatif Q1"], ["w", "Utang tinggi", "DER 1.24× di atas sektor"], ["w", "Distribusi terdeteksi", "smart money keluar"]] },
  SRTG: { name: "Saratoga Investama", price: 1860, per: "12.4×", perC: "up", pbv: "0.9×", pbvC: "up", roe: "8.4%", der: "0.32×", rev: "-4.2%", nm: "14.1%", mcap: "186T", earn: "26 Jun", qlty: "5.8", sent: 32, sentL: "Fear · Bearish", flags: [["ok", "Valuasi murah", "PBV di bawah 1.0×"], ["w", "Revenue turun", "-4.2% YoY"], ["w", "NAV discount", "diskon ke nilai aset melebar"], ["w", "Markdown phase", "tekanan jual institusi"]] },
};

export const IHSG_30D = [7245, 7218, 7256, 7289, 7234, 7198, 7212, 7187, 7203, 7245, 7278, 7312, 7298, 7334, 7367, 7345, 7378, 7401, 7389, 7423, 7445, 7412, 7398, 7425, 7456, 7472, 7445, 7398, 7421, 7428];

export const EQUITY = [100, 104, 108, 112, 109, 115, 121, 118, 124, 128, 132, 138, 142, 138, 134, 141, 148, 154, 158, 152, 148, 156, 162, 168, 172, 178, 184, 178, 172, 165, 170, 178, 185, 192, 198, 204, 210, 216, 222, 218, 224, 232, 240, 248, 256, 264, 278, 287.4];
export const BENCHMARK = [100, 101, 102, 99, 96, 98, 100, 97, 99, 101, 103, 105, 107, 108, 105, 102, 104, 107, 110, 108, 106, 109, 111, 114, 116, 118, 120, 117, 115, 113, 116, 118, 119, 121, 122, 124, 125, 124, 126, 123, 121, 122, 124, 122, 120, 122, 124, 124.8];
