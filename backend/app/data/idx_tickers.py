"""IDX listed companies — static snapshot untuk search & lookup.

IDX punya ~900 emiten. Daftar di bawah berisi ~250 nama yang paling banyak
dicari oleh trader retail (LQ45 + IDX80 + bluechip lain + saham aktif).
Bukan exhaustive — saham di luar list ini masih bisa diakses lewat backend
via ticker langsung. Search di sini berfungsi sebagai autocomplete-friendly UI.

Update list ini saat ada IPO besar atau rebalance LQ45.
"""

from __future__ import annotations

IDX_TICKERS: list[dict] = [
    # ===== BANKING =====
    {"ticker": "BBCA", "name": "Bank Central Asia", "sector": "Banking"},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia", "sector": "Banking"},
    {"ticker": "BMRI", "name": "Bank Mandiri", "sector": "Banking"},
    {"ticker": "BBNI", "name": "Bank Negara Indonesia", "sector": "Banking"},
    {"ticker": "BRIS", "name": "Bank Syariah Indonesia", "sector": "Banking"},
    {"ticker": "ARTO", "name": "Bank Jago", "sector": "Banking"},
    {"ticker": "BBTN", "name": "Bank Tabungan Negara", "sector": "Banking"},
    {"ticker": "BJBR", "name": "Bank Jabar Banten", "sector": "Banking"},
    {"ticker": "BJTM", "name": "Bank Jatim", "sector": "Banking"},
    {"ticker": "NISP", "name": "Bank OCBC NISP", "sector": "Banking"},
    {"ticker": "BNGA", "name": "Bank CIMB Niaga", "sector": "Banking"},
    {"ticker": "BTPS", "name": "Bank BTPN Syariah", "sector": "Banking"},
    {"ticker": "BBHI", "name": "Bank Allo Indonesia", "sector": "Banking"},
    {"ticker": "BANK", "name": "Bank Aladin Syariah", "sector": "Banking"},
    {"ticker": "AMAR", "name": "Bank Amar Indonesia", "sector": "Banking"},
    {"ticker": "NOBU", "name": "Bank Nationalnobu", "sector": "Banking"},
    {"ticker": "AGRO", "name": "Bank Raya Indonesia", "sector": "Banking"},

    # ===== ENERGY / COMMODITIES =====
    {"ticker": "BREN", "name": "Barito Renewables Energy", "sector": "Energy"},
    {"ticker": "CUAN", "name": "Petrindo Jaya Kreasi", "sector": "Energy"},
    {"ticker": "MEDC", "name": "Medco Energi", "sector": "Energy"},
    {"ticker": "ADRO", "name": "Adaro Energy", "sector": "Energy"},
    {"ticker": "ADMR", "name": "Adaro Minerals", "sector": "Energy"},
    {"ticker": "PTBA", "name": "Bukit Asam", "sector": "Energy"},
    {"ticker": "ITMG", "name": "Indo Tambangraya Megah", "sector": "Energy"},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara", "sector": "Energy"},
    {"ticker": "HRUM", "name": "Harum Energy", "sector": "Energy"},
    {"ticker": "BUMI", "name": "Bumi Resources", "sector": "Energy"},
    {"ticker": "INDY", "name": "Indika Energy", "sector": "Energy"},
    {"ticker": "DOID", "name": "Delta Dunia Makmur", "sector": "Energy"},
    {"ticker": "ENRG", "name": "Energi Mega Persada", "sector": "Energy"},
    {"ticker": "ELSA", "name": "Elnusa", "sector": "Energy"},
    {"ticker": "DEWA", "name": "Darma Henwa", "sector": "Energy"},

    # ===== BASIC MATERIALS / MINING =====
    {"ticker": "AMMN", "name": "Amman Mineral Internasional", "sector": "Mining"},
    {"ticker": "MDKA", "name": "Merdeka Copper Gold", "sector": "Mining"},
    {"ticker": "MBMA", "name": "Merdeka Battery Materials", "sector": "Mining"},
    {"ticker": "ANTM", "name": "Aneka Tambang", "sector": "Mining"},
    {"ticker": "INCO", "name": "Vale Indonesia", "sector": "Mining"},
    {"ticker": "TINS", "name": "Timah", "sector": "Mining"},
    {"ticker": "PSAB", "name": "J Resources Asia Pasifik", "sector": "Mining"},
    {"ticker": "ARCI", "name": "Archi Indonesia", "sector": "Mining"},
    {"ticker": "BRMS", "name": "Bumi Resources Minerals", "sector": "Mining"},
    {"ticker": "NCKL", "name": "Trimegah Bangun Persada", "sector": "Mining"},
    {"ticker": "ESSA", "name": "Surya Esa Perkasa", "sector": "Basic Materials"},
    {"ticker": "TPIA", "name": "Chandra Asri Petrochemical", "sector": "Basic Materials"},
    {"ticker": "BRPT", "name": "Barito Pacific", "sector": "Basic Materials"},
    {"ticker": "INTP", "name": "Indocement Tunggal Prakarsa", "sector": "Basic Materials"},
    {"ticker": "SMGR", "name": "Semen Indonesia", "sector": "Basic Materials"},
    {"ticker": "INKP", "name": "Indah Kiat Pulp & Paper", "sector": "Basic Materials"},
    {"ticker": "TKIM", "name": "Pabrik Kertas Tjiwi Kimia", "sector": "Basic Materials"},

    # ===== CONSUMER STAPLES =====
    {"ticker": "INDF", "name": "Indofood Sukses Makmur", "sector": "Consumer Staples"},
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur", "sector": "Consumer Staples"},
    {"ticker": "UNVR", "name": "Unilever Indonesia", "sector": "Consumer Staples"},
    {"ticker": "MYOR", "name": "Mayora Indah", "sector": "Consumer Staples"},
    {"ticker": "GGRM", "name": "Gudang Garam", "sector": "Consumer Staples"},
    {"ticker": "HMSP", "name": "HM Sampoerna", "sector": "Consumer Staples"},
    {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia", "sector": "Consumer Staples"},
    {"ticker": "JPFA", "name": "Japfa Comfeed Indonesia", "sector": "Consumer Staples"},
    {"ticker": "MAIN", "name": "Malindo Feedmill", "sector": "Consumer Staples"},
    {"ticker": "KLBF", "name": "Kalbe Farma", "sector": "Healthcare"},
    {"ticker": "KAEF", "name": "Kimia Farma", "sector": "Healthcare"},
    {"ticker": "INAF", "name": "Indofarma", "sector": "Healthcare"},
    {"ticker": "SIDO", "name": "Industri Jamu Sido Muncul", "sector": "Healthcare"},
    {"ticker": "TSPC", "name": "Tempo Scan Pacific", "sector": "Healthcare"},
    {"ticker": "PYFA", "name": "Pyridam Farma", "sector": "Healthcare"},
    {"ticker": "MIKA", "name": "Mitra Keluarga Karyasehat", "sector": "Healthcare"},
    {"ticker": "HEAL", "name": "Medikaloka Hermina", "sector": "Healthcare"},
    {"ticker": "SILO", "name": "Siloam International Hospitals", "sector": "Healthcare"},
    {"ticker": "AALI", "name": "Astra Agro Lestari", "sector": "Plantation"},
    {"ticker": "LSIP", "name": "PP London Sumatra Indonesia", "sector": "Plantation"},
    {"ticker": "SIMP", "name": "Salim Ivomas Pratama", "sector": "Plantation"},
    {"ticker": "SGRO", "name": "Sampoerna Agro", "sector": "Plantation"},
    {"ticker": "TBLA", "name": "Tunas Baru Lampung", "sector": "Plantation"},
    {"ticker": "DSNG", "name": "Dharma Satya Nusantara", "sector": "Plantation"},

    # ===== CONSUMER CYCLICAL =====
    {"ticker": "ASII", "name": "Astra International", "sector": "Automotive"},
    {"ticker": "AUTO", "name": "Astra Otoparts", "sector": "Automotive"},
    {"ticker": "MAPI", "name": "Mitra Adiperkasa", "sector": "Retail"},
    {"ticker": "MAPA", "name": "MAP Aktif Adiperkasa", "sector": "Retail"},
    {"ticker": "ACES", "name": "Ace Hardware Indonesia", "sector": "Retail"},
    {"ticker": "AMRT", "name": "Sumber Alfaria Trijaya (Alfamart)", "sector": "Retail"},
    {"ticker": "RALS", "name": "Ramayana Lestari Sentosa", "sector": "Retail"},
    {"ticker": "ERAA", "name": "Erajaya Swasembada", "sector": "Retail"},
    {"ticker": "LPPF", "name": "Matahari Department Store", "sector": "Retail"},
    {"ticker": "MIDI", "name": "Midi Utama Indonesia", "sector": "Retail"},

    # ===== INFRASTRUCTURE / TELECOM =====
    {"ticker": "TLKM", "name": "Telkom Indonesia", "sector": "Telecom"},
    {"ticker": "ISAT", "name": "Indosat", "sector": "Telecom"},
    {"ticker": "EXCL", "name": "XL Axiata", "sector": "Telecom"},
    {"ticker": "FREN", "name": "Smartfren Telecom", "sector": "Telecom"},
    {"ticker": "TOWR", "name": "Sarana Menara Nusantara", "sector": "Tower"},
    {"ticker": "TBIG", "name": "Tower Bersama Infrastructure", "sector": "Tower"},
    {"ticker": "MTEL", "name": "Dayamitra Telekomunikasi", "sector": "Tower"},
    {"ticker": "JSMR", "name": "Jasa Marga", "sector": "Infrastructure"},
    {"ticker": "WIKA", "name": "Wijaya Karya", "sector": "Construction"},
    {"ticker": "WSKT", "name": "Waskita Karya", "sector": "Construction"},
    {"ticker": "PTPP", "name": "PP (Persero)", "sector": "Construction"},
    {"ticker": "ADHI", "name": "Adhi Karya", "sector": "Construction"},
    {"ticker": "WTON", "name": "Wijaya Karya Beton", "sector": "Construction"},
    {"ticker": "ACST", "name": "Acset Indonusa", "sector": "Construction"},
    {"ticker": "TOTL", "name": "Total Bangun Persada", "sector": "Construction"},

    # ===== PROPERTY =====
    {"ticker": "PANI", "name": "Pantai Indah Kapuk Dua", "sector": "Property"},
    {"ticker": "CTRA", "name": "Ciputra Development", "sector": "Property"},
    {"ticker": "PWON", "name": "Pakuwon Jati", "sector": "Property"},
    {"ticker": "SMRA", "name": "Summarecon Agung", "sector": "Property"},
    {"ticker": "BSDE", "name": "Bumi Serpong Damai", "sector": "Property"},
    {"ticker": "LPKR", "name": "Lippo Karawaci", "sector": "Property"},
    {"ticker": "DILD", "name": "Intiland Development", "sector": "Property"},
    {"ticker": "ASRI", "name": "Alam Sutera Realty", "sector": "Property"},
    {"ticker": "APLN", "name": "Agung Podomoro Land", "sector": "Property"},
    {"ticker": "PPRO", "name": "PP Properti", "sector": "Property"},
    {"ticker": "MTLA", "name": "Metropolitan Land", "sector": "Property"},
    {"ticker": "MDLN", "name": "Modernland Realty", "sector": "Property"},

    # ===== TECH / DIGITAL =====
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia", "sector": "Technology"},
    {"ticker": "BUKA", "name": "Bukalapak.com", "sector": "Technology"},
    {"ticker": "EMTK", "name": "Elang Mahkota Teknologi", "sector": "Technology"},
    {"ticker": "DCII", "name": "DCI Indonesia", "sector": "Technology"},
    {"ticker": "MTDL", "name": "Metrodata Electronics", "sector": "Technology"},
    {"ticker": "DIVA", "name": "Distribusi Voucher Nusantara", "sector": "Technology"},
    {"ticker": "MCAS", "name": "M Cash Integrasi", "sector": "Technology"},
    {"ticker": "EDGE", "name": "Indointernet", "sector": "Technology"},
    {"ticker": "WIFI", "name": "Solusi Sinergi Digital", "sector": "Technology"},

    # ===== INVESTMENT / CONGLOMERATE =====
    {"ticker": "SRTG", "name": "Saratoga Investama Sedaya", "sector": "Investment"},
    {"ticker": "BNBR", "name": "Bakrie & Brothers", "sector": "Investment"},
    {"ticker": "BHIT", "name": "MNC Asia Holding", "sector": "Investment"},
    {"ticker": "MNCN", "name": "Media Nusantara Citra", "sector": "Media"},
    {"ticker": "SCMA", "name": "Surya Citra Media", "sector": "Media"},
    {"ticker": "VIVA", "name": "Visi Media Asia", "sector": "Media"},
    {"ticker": "FILM", "name": "MD Pictures", "sector": "Media"},

    # ===== TRANSPORT / LOGISTICS =====
    {"ticker": "GIAA", "name": "Garuda Indonesia", "sector": "Transport"},
    {"ticker": "SMDR", "name": "Samudera Indonesia", "sector": "Transport"},
    {"ticker": "TPMA", "name": "Trans Power Marine", "sector": "Transport"},
    {"ticker": "BIRD", "name": "Blue Bird", "sector": "Transport"},
    {"ticker": "ASSA", "name": "Adi Sarana Armada", "sector": "Transport"},

    # ===== UTILITIES / FINANCE =====
    {"ticker": "POWR", "name": "Cikarang Listrindo", "sector": "Utilities"},
    {"ticker": "PJAA", "name": "Pembangunan Jaya Ancol", "sector": "Tourism"},
    {"ticker": "PNLF", "name": "Panin Financial", "sector": "Finance"},
    {"ticker": "ADMF", "name": "Adira Dinamika Multi Finance", "sector": "Finance"},
    {"ticker": "BFIN", "name": "BFI Finance Indonesia", "sector": "Finance"},
    {"ticker": "CFIN", "name": "Clipan Finance Indonesia", "sector": "Finance"},
    {"ticker": "WOMF", "name": "Wahana Ottomitra Multiartha", "sector": "Finance"},

    # ===== INSURANCE =====
    {"ticker": "AMAG", "name": "Asuransi Multi Artha Guna", "sector": "Insurance"},
    {"ticker": "ASBI", "name": "Asuransi Bintang", "sector": "Insurance"},
    {"ticker": "ABDA", "name": "Asuransi Bina Dana Arta", "sector": "Insurance"},

    # Additional active names
    {"ticker": "WEHA", "name": "WEHA Transportasi Indonesia", "sector": "Transport"},
    {"ticker": "GIAA", "name": "Garuda Indonesia", "sector": "Transport"},
    {"ticker": "BRPT", "name": "Barito Pacific", "sector": "Basic Materials"},
    {"ticker": "KRYA", "name": "Bangun Karya Perkasa Jaya", "sector": "Construction"},
    {"ticker": "BEST", "name": "Bekasi Fajar Industrial Estate", "sector": "Property"},
    {"ticker": "DMAS", "name": "Puradelta Lestari", "sector": "Property"},
]


def search(query: str, limit: int = 20) -> list[dict]:
    """Substring + prefix match across ticker and name. Returns scored list."""
    q = (query or "").upper().strip()
    if not q:
        return []
    results: list[tuple[int, dict]] = []
    for item in IDX_TICKERS:
        t = item["ticker"]
        n = item["name"].upper()
        if t == q:
            score = 0
        elif t.startswith(q):
            score = 1
        elif q in t:
            score = 2
        elif n.startswith(q):
            score = 3
        elif q in n:
            score = 4
        else:
            continue
        results.append((score, item))
    results.sort(key=lambda x: (x[0], x[1]["ticker"]))
    return [r[1] for r in results[:limit]]
