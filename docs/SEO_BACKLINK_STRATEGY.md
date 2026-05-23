# Sahamflow — SEO & Backlink Strategy

> Realita: backlink **tidak bisa di-coding**, harus dari situs lain. Dokumen ini
> menjabarkan target konkret + template outreach + langkah teknis SEO yang
> sudah/akan diaktifkan supaya situs *layak* dapat backlink.

---

## 0. Yang sudah aktif di kode (technical SEO)

| Item | Status |
|---|---|
| `robots.txt` (allow all + sitemap link) | ✅ `/robots.txt` |
| `sitemap.xml` auto-generated | ✅ `/sitemap.xml` |
| Meta title + description + keywords | ✅ Bahasa Indonesia + EN keywords |
| Open Graph + Twitter card | ✅ Dynamic 1200×630 PNG via `app/opengraph-image.tsx` |
| Canonical URL | ✅ `metadataBase + alternates.canonical` |
| Structured data JSON-LD | ✅ Organization + WebSite + SoftwareApplication schema |
| Favicon (SVG) | ✅ `/icon.svg` |
| HTTPS + HSTS | ✅ via certbot |
| Mobile responsive | ✅ inherits prototype responsive CSS |
| Page speed | ⚠️ first-load 165 KB JS (OK), lazy-fetch per-stock 3-5s (could be faster) |

**Verifikasi setelah deploy:**
- Buka https://search.google.com/test/rich-results → input `https://sahamflow.com` → harus muncul Organization + WebSite + SoftwareApplication
- Buka https://www.opengraph.xyz/ → preview OG card-mu (gold gradient, mark, tagline)

---

## 1. Daftar TARGET BACKLINK (prioritas tinggi → rendah)

### Tier A — Submit langsung (cepat, gratis, 1-2 hari)

| Direktori | URL submit | Effort | DA |
|---|---|---|---|
| Product Hunt | https://www.producthunt.com/products/new | 30 menit, perlu konten preview bagus | 91 |
| BetaList | https://betalist.com/submit | 15 menit | 73 |
| Indie Hackers | https://www.indiehackers.com/post | tulis launch story 200 kata | 76 |
| AlternativeTo | https://alternativeto.net/software/add/ | sebut sebagai alternative Stockbit/Bareksa Analytics | 86 |
| SaaSHub | https://www.saashub.com/submit-product | 20 menit | 64 |
| StartupBase | https://startupbase.io/submit | 10 menit | 56 |

### Tier B — Indonesian finance community (PALING RELEVAN)

| Channel | Cara | Effort |
|---|---|---|
| **Stockbit Komunitas** | Buat post tutorial pakai Sahamflow untuk analisa BBCA/BMRI, link ke sahamflow.com | 1-2 jam, harus value-first, NO spam |
| **r/IndonesianTraders / r/finansial** | AMA / case study post pakai data Sahamflow | 30 menit |
| **Kaskus Subforum Saham** | Tutorial post atau diskusi setup | 1 jam |
| **Forum Investor IDX** | https://www.investor.id/forum | 30 menit |
| **Bisnis.com Investor Community** | comment kontekstual + signature link | ongoing |
| **Twitter/X Indonesia trader** | Follow + reply value ke @desmondwira, @lukas_setia, @dolphin_investor, @rich_dad_ind, share insight Sahamflow | ongoing |

### Tier C — YouTuber/Blogger Outreach

| Target | Niche | Outreach angle |
|---|---|---|
| **Doddy Prayogo** (YouTube) | Trading saham | "Tool open analytics IDX, mau review?" |
| **Felicia Putri Tjiasaka** | Investor edukasi | Edukasi pakai Sahamflow regime detector |
| **Hipwee Finance** | Lifestyle finance | Listicle "5 tools analitik gratis IDX" |
| **DailySocial / Tech in Asia ID** | Startup tech | Press release launch |
| **Money.id, IDN Financials** | Finance news | Pitch story angle |

### Tier D — Backlink dari komunitas dev (sekalian portofolio)

- **GitHub README**: Sahamflow repo public dengan link ke sahamflow.com (DA 100)
- **Dev.to artikel**: "Building IDX stock analytics with FastAPI + Next.js" — tutorial pakai sahamflow sebagai case study
- **Hacker News Show HN**: post dengan link
- **r/SideProject** / **r/algotrading**: launch post

---

## 2. Template outreach (siap kirim)

### A. Email ke blogger/YouTuber

```
Subject: Tool analitik saham IDX gratis — boleh untuk review?

Halo {Nama},

Saya pengembang Sahamflow (https://sahamflow.com) — platform analitik
buy-side untuk saham IHSG, gratis. Fitur:

• Market regime detector (path-aware: Potential Accumulation, Markdown
  Capitulation, dll) — berbeda dari technical indicator biasa
• Smart money proxy (heuristik bandar+volume+range)
• Walk-forward backtest per saham dengan biaya IDX 0.6% included
• ATR-based execution levels per saham (entry/SL/TP otomatis)
• Reversal candidates scanner saat regime mendukung bottom-fishing

Mengingat audiens {channel}-mu kuat di {niche}, mungkin tool ini menarik
untuk di-feature. Aku siap kirim demo akses, tutorial bahan video, atau
diskusi langsung.

Tidak ada deal komersial — saya cuma mau dapat feedback dari trader
serius supaya tool ini bisa membantu lebih banyak retail.

Salam,
{Nama}
sahamflow.com
```

### B. Comment template (Stockbit / Reddit / Twitter)

```
Setuju, RSI 28 di [TICKER] di regime Potential Accumulation memang
classic setup. Aku biasa cek di Sahamflow (sahamflow.com) — reversal
scanner-nya kasih signature konkret: streak turun, gap closed, volume
thrust. Lumayan untuk validasi insting.
```

⚠️ **HANYA pakai kalau benar-benar kontekstual** — spam dropping link
akan dapat shadow-ban. Value first, link last.

### C. Press release angle

```
HEADLINE: Sahamflow Luncurkan Tool Analitik IHSG Open Buy-Side untuk Trader Retail

SUBHEAD: Platform gratis dengan regime detector, walk-forward backtest,
dan ATR-based execution levels — pertama untuk pasar IDX

ANGLE:
- Indonesia punya 7+ juta investor ritel (KSEI 2025), mayoritas trading
  tanpa tool kuantitatif yang serious.
- Sahamflow menyediakan analitik level institusi (regime modeling,
  walk-forward backtest dengan biaya transaksi nyata) secara gratis.
- Founder/dev: {Nama kamu}
- Open untuk feedback komunitas.
```

---

## 3. Strategi konten untuk dapat backlink organic (long-term)

### Blog content yang LINKABLE (orang akan link ini)

1. **"Studi: Hit rate setup Wyckoff Accumulation di LQ45 2020-2025"**
   — pakai walk-forward backtest Sahamflow, publish hasil dengan chart.
   Ini riset asli, akan di-link oleh forum saham.

2. **"Mengapa RSI 30 di IDX beda dengan US: data 5 tahun"**
   — analisa mean-reversion bias IDX vs US, dengan angka.

3. **"Daftar LQ45 rebalance: dampak ke broker summary 30 hari"**
   — event-driven analytics. High share value.

4. **"Compose your own quantitative IDX dashboard"**
   — tutorial, link Sahamflow API endpoints sebagai data source.

Buat **/blog** subdirectory di Sahamflow (`app/blog/[slug]/page.tsx`),
publish 1 artikel kuat per bulan. Setiap artikel = magnet backlink.

### Open data initiative

- Publish daily CSV ringkasan: regime + composite top-20 → bisa di-fork & di-cite
- GitHub repo public dengan data → developer akan link
- Kaggle dataset → researchers akan cite

---

## 4. Schedule realistis 90 hari

**Bulan 1 (akuisisi):**
- [ ] Submit ke Tier A (semua 6 direktori)
- [ ] Setup GitHub repo public dengan README → link sahamflow.com
- [ ] Post launch ke r/SideProject, r/algotrading
- [ ] Twitter thread: "Building Sahamflow" — 5 tweet, hari yang sama

**Bulan 2 (komunitas):**
- [ ] 4 post value di Stockbit Komunitas (1/minggu)
- [ ] Tulis 2 artikel blog (riset asli pakai Sahamflow data)
- [ ] Outreach 5 YouTuber/blogger trading IDX
- [ ] Dev.to artikel teknis

**Bulan 3 (PR + content):**
- [ ] Kirim press release ke 3 media tech ID (DailySocial, TechInAsia, KMag)
- [ ] Publish dataset di Kaggle
- [ ] 2 artikel blog lagi
- [ ] Apply ke "Tools of the Week" lists (Indie Hackers, Product Hunt)

---

## 5. Yang HARUS DIHINDARI (akan kena penalty Google)

- ❌ Beli backlink dari Fiverr / Seoclerks ("buy 5000 backlinks $5") — pasti spam, kena Penguin
- ❌ Link exchange skema "you link me I link you" massal
- ❌ Comment spam: drop link di komentar tanpa value
- ❌ Sub-domain spam (sahamflow.tk, sahamflow.ml dll)
- ❌ PBN (private blog network) — manipulatif
- ❌ Press release berbayar pricepertickel.com — low quality

**1 backlink berkualitas dari Stockbit Komunitas / DailySocial > 1000 backlink junk.**

---

## 6. Metrics yang akan dipantau

Setelah 90 hari, ukur via:
- **Google Search Console**: queries impression, average position, backlinks count
- **Ahrefs / Ubersuggest free tier**: domain rating, referring domains
- **Plausible / GA4**: organic search traffic, referral traffic per source

Target realistic 90 hari pertama:
- 20-30 referring domains
- 50-100 organic visits/hari
- Rank top-10 untuk "sahamflow", "analitik saham gratis", "regime detector IDX"

---

## 7. Status saat ini (baseline)

- Domain: sahamflow.com (live, HTTPS, age: hari ini)
- Backlinks: ~0 (baru launch)
- DA: belum terindeks
- Pages indexed: 1 (homepage)

Submit ke Google Search Console **hari ini juga**:
1. https://search.google.com/search-console
2. Verify ownership via DNS TXT atau HTML file
3. Submit sitemap: `https://sahamflow.com/sitemap.xml`
4. Request indexing untuk homepage

Bing Webmaster Tools juga (sering dilupakan, tapi 5% market share IDX):
1. https://www.bing.com/webmasters
2. Submit sitemap

---

**Bottom line:** backlink building = **marketing kerja keras manusia**, bukan code.
Tool sudah optimal secara technical SEO. Sisanya tergantung effort outreach kamu.
