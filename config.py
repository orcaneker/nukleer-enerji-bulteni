# -*- coding: utf-8 -*-
"""
NÜKLEER ENERJİ BÜLTENİ — YAPILANDIRMA
======================================
Sorgular, kategori taksonomisi, kaynak katmanları ve ayarlar burada.
pipeline.py / publish.py / review_app bunları okur.
Yeni sorgu/kaynak eklemek için sadece bu dosyayı düzenle.
"""

# ============================================================
# GENEL AYARLAR
# ============================================================
AYARLAR = {
    # Takvim: taslak Pazar 12:00 TSİ hazırlanır, yayın Pazartesi 08:00 TSİ.
    # Render cron (UTC): taslak "0 9 * * 0" · yayın "0 5 * * 1"
    "taslak_gunu": "pazar",
    "yayim_gunu": "pazartesi",
    "yayim_saati_tsi": 8,            # yayın eşiği (geç onay kontrolünde kullanılır)

    "pencere_gun": 7,                # birincil tarama penceresi
    "pencere_genis_gun": 14,         # yetersiz sonuçta genişletilir
    # NOT: Türkiye için ayrı geniş pencere KULLANILMIYOR (21 gün denendi,
    # bir sonraki sayıda aynı haberin tekrarlanması riski doğurdu — hakem
    # kararıyla tüm sorgular 7 günlük pencerede).

    # Bülten hacim hedefleri
    "manset": 1,
    "brief_madde": 5,                # "Bu Hafta 60 Saniyede"
    "one_cikan_min": 8,
    "one_cikan_max": 10,
    "radar_min": 18,
    "radar_max": 30,

    # LLM — sağlayıcı öneki zorunlu: "anthropic:..." veya "openai:..."
    "model_triyaj": "anthropic:claude-haiku-4-5-20251001",
    "model_yazim": "anthropic:claude-sonnet-5",
    # NOT: temperature parametresi BİLEREK gönderilmiyor (model uyumsuzluk deneyimi).

    # OpenAI reasoning modelleri (gpt-5.6 ailesi) için akıl yürütme seviyesi:
    # none | low | medium | high | xhigh | max
    # Anthropic modellerinde yok sayılır. REASONING_EFFORT ortam değişkeni
    # bu ayarı ezer (deneme yaparken pratik).
    "reasoning_effort": "medium",
    "triyaj_batch": 40,              # tek seferde triyaja giden aday sayısı
    "max_tokens_triyaj": 8000,
    "max_tokens_yazim": 48000,       # 14 haberin TAMAMI yazıldığı için GENİŞ olmalı.
                                     # ⚠ Düşük tutulursa çıktı JSON tamamlanmadan kesilir.
    # Akıl yürüten modellerde (gpt-5.x, Sonnet 5, Opus 4.7+, Fable 5) "düşünme"
    # token'ları da BU bütçeden düşer — görünür metne kalan pay azalır ve JSON
    # ortadan kesilebilir. Bu modeller 128K çıktı desteklediği için rahat pay
    # bırakıldı — kullanılmayan bütçe ücretlendirilmez.
    "max_tokens_yazim_reasoning": 96000,
    "derin_olay_sayisi": 14,         # tam metinle yazıma giden olay — HEPSİ haber olur
    "toplam_olay_sayisi": 40,        # geri kalanı radar adayı (başlık+link)

    # Exa
    "exa_sonuc_sayisi": 20,          # sorgu başına
    "exa_metin_karakter": 4000,      # çekilen makale metni
    "exa_triyaj_karakter": 700,      # triyaja giden kısa parça (ucuz)
    "yazim_birincil_karakter": 3500, # birincil kaynak derin okunur
    "yazim_destek_karakter": 800,    # destekleyici sadece fark için
    "exa_tip": "auto",

    # Site
    # ⚠ docs/CNAME dosyasıyla AYNI alan adı olmalı. Farklı kalırsa RSS
    # bağlantıları yanlış adrese çıkar ve publish.py canlı state'i
    # (data/state/seen_events.json) okuyamayıp sayı sayacını sıfırlar.
    "site_url": "https://nukleer-enerji-bulteni.site",
    "cikti_dizini": "docs",          # GitHub Pages sadece / veya /docs kabul eder

    # Sayı numarası: None → otomatik artar (yayınlanan son sayı + 1).
    # Sayaç canlı sitedeki data/state/seen_events.json → issue_no alanında
    # yaşar; publish.py her yayında oraya yazar. Arşiv ve state sıfırlandığı
    # için (bkz. docs/data) ilk gerçek çalıştırma otomatik olarak Sayı 1 olur.
    # Test amacıyla numarayı dondurmak istersen sabit bir sayı ver — ama
    # YAYINA GEÇERKEN None'a geri al, aksi halde her sayı aynı numarayı
    # alır ve arşivde mükerrer görünür.
    "sayi_no_sabit": None,
}

# ============================================================
# FİYATLANDIRMA (USD / 1 milyon token) — maliyet TAHMİNİ için
# ⚠ Fiyatlar değişebilir; console.anthropic.com / platform.openai.com'dan doğrula.
# ============================================================
FIYAT = {
    "anthropic:claude-sonnet-4-6":         {"in": 3.00, "out": 15.00, "cache_w": 3.75, "cache_r": 0.30},
    "anthropic:claude-haiku-4-5-20251001": {"in": 1.00, "out":  5.00, "cache_w": 1.25, "cache_r": 0.10},
    "openai:gpt-5-mini":                   {"in": 0.25, "out":  2.00, "cache_w": 0.25, "cache_r": 0.025},
    "openai:gpt-5.1":                      {"in": 1.25, "out": 10.00, "cache_w": 1.25, "cache_r": 0.125},
    "openai:gpt-5.6-luna":                 {"in": 1.00, "out":  6.00, "cache_w": 1.25, "cache_r": 0.10},
    # ⚠ Sonnet 5 liste fiyatı 4.6 ile AYNI ($3/$15) ama 31 Ağustos 2026'ya kadar
    # tanıtım fiyatı $2/$10. Aşağıda LİSTE fiyatı yazılı — maliyet raporu böylece
    # olduğundan düşük görünmez.
    "anthropic:claude-sonnet-5":           {"in": 3.00, "out": 15.00, "cache_w": 3.75, "cache_r": 0.30},
}

# ============================================================
# EXA ARAMA FİYATI (USD) — maliyet TAHMİNİ için
# ⚠ exa.ai/pricing'den doğrula; değişebilir.
# Model: istek başına taban ücret İLK 10 SONUCU kapsar (sayfa içeriği dahil,
# Mart 2026 güncellemesi); 10'un üzerindeki her sonuç ayrıca ücretlenir.
# ============================================================
EXA_FIYAT = {
    "arama": 7.00 / 1000,      # $7 / 1.000 istek (ilk 10 sonuç dahil)
    "ek_sonuc": 1.00 / 1000,   # 10'un üzerindeki her sonuç için $1 / 1.000
}

# ============================================================
# KATEGORİ TAKSONOMİSİ (12)
# Kod → (Görünen ad, Öne Çıkanlar kota hedefi)
# ============================================================
KATEGORILER = {
    "politika":      {"ad": "Politika & Düzenleme",           "kota": 2},
    "buyuk-reaktor": {"ad": "Büyük Reaktör Projeleri",        "kota": 1},
    "smr":           {"ad": "SMR & Mikro Reaktörler",         "kota": 2},
    "yakit":         {"ad": "Uranyum & Yakıt Zinciri",        "kota": 1},
    "isletme":       {"ad": "İşletme & Filo",                 "kota": 1},
    "kurumsal-alim": {"ad": "Kurumsal Alım & Veri Merkezi",   "kota": 1},
    "fuzyon":        {"ad": "Füzyon",                         "kota": 0},
    "atik-sokum":    {"ad": "Atık & Söküm",                   "kota": 0},
    "teknoloji":     {"ad": "Teknoloji & Ar-Ge",              "kota": 1},
    "turkiye":       {"ad": "Türkiye",                        "kota": 1},
    "guvenlik":      {"ad": "Güvenlik & Emniyet",             "kota": 0},
    "rapor":         {"ad": "Rapor & Piyasa Verisi",          "kota": 1},
}

# ⚠ KOTA NEDEN VAR: SMR ve veri merkezi anlaşma haberleri akışı domine
# edebilir. Kota olmadan bültenin yarısı SMR duyurusu olur.

# Değer zinciri etiketleri (site navigasyonunun omurgası)
DEGER_ZINCIRI = [
    "uranyum", "donusum-zenginlestirme", "yakit-uretim",
    "reaktor-insa", "isletme", "atik-sokum", "uygulama",
]

# ============================================================
# OLGUNLUK ÖLÇEĞİ — nükleer projeler için
# "Niyet mektubu" ile "şebekeye bağlı reaktör" arasında uçurum var;
# nükleerde bu fark yarı iletkenden bile büyüktür (10+ yıllık projeler).
#
# ⚠ SIRA ANLAMLIDIR: site (site/index.html → OLG) bu ölçeği bir "aşama
# göstergesi" olarak çizer — bültenin imza görsel öğesi budur. Yeni bir
# aşama eklersen SİTEDEKİ KARŞILIĞINI DA GÜNCELLE, yoksa gösterge o
# haberde boş kalır. delayed/cancelled ölçeğin DIŞINDADIR: sıralı değil,
# durum bildirir; site onları ayrı rozet olarak gösterir.
# ============================================================
OLGUNLUK = [
    "research",           # araştırma/kavramsal tasarım
    "design_cert",        # tasarım sertifikasyonu süreci
    "site_permit",        # saha izni / ÇED
    "licensed",           # inşaat/işletme lisansı alındı
    "announced",          # niyet/anlaşma duyuruldu
    "funded",             # finansman kapandı / nihai yatırım kararı (FID)
    "construction",       # ilk beton / inşaat sürüyor
    "commissioning",      # devreye alma / ilk kritiklik
    "grid_connection",    # şebekeye bağlandı
    "operational",        # ticari işletmede
    "delayed",
    "cancelled",
]

# ============================================================
# KAYNAK KATMANLARI
# tier 1 = birincil (resmî kurum, şirket newsroom)
# tier 2 = güvenilir haber ajansı / sektör basını
# ============================================================
KAYNAK_TIER1 = [
    # Uluslararası kuruluşlar
    "iaea.org", "oecd-nea.org", "world-nuclear.org", "wano.info",
    "iea.org", "worldbank.org",
    # ABD
    "nrc.gov", "energy.gov", "nnsa.energy.gov", "inl.gov", "ornl.gov",
    "federalregister.gov", "nei.org",
    # Avrupa
    "ec.europa.eu", "ensreg.eu", "euratom-supply.ec.europa.eu",
    "foratom.org", "onr.org.uk", "asnr.fr", "gov.uk",
    # Asya vd.
    "meti.go.jp", "nra.go.jp", "kins.re.kr", "khnp.co.kr", "jaea.go.jp",
    "caea.gov.cn", "aec.gov.tw", "dae.gov.in",
    # Şirket newsroom — reaktör tedarikçileri & işletmeciler
    "westinghousenuclear.com", "edf.fr", "edfenergy.com", "framatome.com",
    "rosatom.ru", "gevernova.com", "ansaldonucleare.it", "candu.com",
    "kepco.co.kr", "cgnpc.com.cn", "cnnc.com.cn",
    "constellationenergy.com", "duke-energy.com", "southerncompany.com",
    "vattenfall.com", "fortum.com", "cez.cz", "pge.pl",
    # SMR / ileri reaktör
    "nuscalepower.com", "x-energy.com", "terrapower.com", "oklo.com",
    "kairospower.com", "rolls-royce-smr.com", "gehnuclear.com",
    "holtecinternational.com", "newcleo.com", "moltexenergy.com",
    "last-energy.com", "radiantnuclear.com",
    # Yakıt zinciri
    "cameco.com", "urenco.com", "orano.group", "kazatomprom.kz",
    "centrusenergy.com", "globallaserenrichment.com", "westinghousefuel.com",
    "uec.com", "nexgenenergy.ca", "paladinenergy.com.au",
    # Füzyon
    "iter.org", "cfs.energy", "tokamakenergy.com", "helionenergy.com",
    "type1energy.com", "proximafusion.com",
]

# ⚠ reuters.com ve bloomberg.com Exa'nın includeDomains filtresinde KABUL
# EDİLMİYOR (lisans kısıtı, 403 döner). Listeye EKLEME — filtresiz aramalarda
# ve diğer sitelerin alıntılarında dolaylı olarak yakalanıyor.
KAYNAK_TIER2 = [
    "world-nuclear-news.org", "neimagazine.com", "nucnet.org",
    "ans.org", "powermag.com", "power-eng.com", "modernpowersystems.com",
    "utilitydive.com", "montelnews.com", "energyintel.com",
    "spectrum.ieee.org", "theregister.com", "cnbc.com",
    "ft.com", "asia.nikkei.com", "wsj.com",
    "world-energy.org", "energy-storage.news", "datacenterdynamics.com",
    "canarymedia.com", "heatmap.news",
]

KAYNAK_AKADEMIK = [
    "nature.com", "science.org", "arxiv.org", "ieeexplore.ieee.org",
    "sciencedirect.com", "iopscience.iop.org", "tandfonline.com",
]

KAYNAK_TURKIYE = [
    "enerji.gov.tr", "ndk.gov.tr", "tenmak.gov.tr", "taek.gov.tr",
    "sanayi.gov.tr", "ticaret.gov.tr", "sbb.gov.tr", "resmigazete.gov.tr",
    "akkuyunpp.com", "epdk.gov.tr", "teias.gov.tr", "emo.org.tr",
    "aa.com.tr", "dunya.com", "ekonomim.com", "bloomberght.com",
    "enerjigunlugu.net", "enerjiportali.com", "yesilekonomi.com",
]

# ============================================================
# ÖDEME DUVARLI KAYNAKLAR
# ------------------------------------------------------------
# Bu kaynaklar DIŞLANMAZ — haber değerleri yüksek, çoğu zaman bir
# gelişmeyi ilk onlar veriyor. Ama Exa yalnızca teaser paragrafını
# görebiliyor. Bu yüzden:
#   · asla BİRİNCİL kaynak olmazlar (erişilebilir kaynak varsa o birincil olur)
#   · tek kaynak onlarsa olay YAZILMAZ, RADAR'a düşer (başlık + link yeterli)
# Böylece "ödeme duvarı arkasında, detaylandırılmadı" gibi içi boş
# cümleler bülten metnine hiç girmez.
# ============================================================
KAYNAK_ODEME_DUVARI = [
    "ft.com", "wsj.com", "asia.nikkei.com", "economist.com",
    "energyintel.com", "montelnews.com", "theinformation.com",
    "spglobal.com", "woodmac.com", "bnef.com",
]

# Metinde bunlardan biri geçiyorsa → ödeme duvarı (alan adına bakmaksızın)
ODEME_DUVARI_IZLERI = [
    "subscribe to read", "subscribers only", "members only",
    "sign in to continue", "log in to read", "register to continue",
    "this content is for", "paywall", "premium content",
    "abone olun", "üyelere özel", "içeriğin tamamını okumak",
]
ODEME_DUVARI_MIN_KARAKTER = 500   # bundan kısa metin → içi boş, duvarlı say

# ── TEYİT ARAMASI (corroboration search) ──────────────────
# Tüm kaynakları ödeme duvarlı olan bir olayı doğrudan çöpe atmıyoruz.
# Energy Intelligence / Montel gibi kaynakların haberleri genellikle saatler
# içinde açık sitelerde (World Nuclear News, NucNet, Power Engineering…)
# yankılanır. Olayın başlığıyla İKİNCİ bir Exa araması yapıp erişilebilir
# bir kaynak bulmaya çalışıyoruz. Bulursak olay yazılabilir hale gelir.
# ⚠ Bulunan kaynak ikinci elden aktarımdır → "bildirildi" diliyle yazılır.
TEYIT = {
    "aktif": True,
    "max_olay": 12,          # en yüksek puanlı N duvarlı olay için ara (maliyet sınırı)
    "sonuc": 6,              # arama başına sonuç
    "min_benzerlik": 0.20,   # başlık örtüşme eşiği (Jaccard)
    "min_ortak_kelime": 2,   # en az bu kadar anlamlı kelime ortak olmalı
    "min_metin": 700,        # teyit kaynağının metni bundan uzun olmalı
    "gun_toleransi": 3,      # olay tarihinden ± bu kadar gün
}

# Başlık karşılaştırmasında yok sayılacak kelimeler
DURAK_KELIMELER = {
    "the", "and", "for", "with", "from", "that", "this", "will", "have", "has",
    "into", "over", "amid", "says", "said", "new", "its", "not", "but", "are",
    "was", "were", "been", "more", "than", "after", "before", "report", "reports",
    "reportedly", "according", "sources", "source", "nuclear", "reactor",
    "power", "plant", "energy",
    "ile", "için", "olarak", "yeni", "bir", "bu", "de", "da", "ve",
}

# Asla kullanılmayacak / sponsorlu-SEO ağırlıklı kaynaklar
KAYNAK_DISLA = [
    "linkedin.com", "facebook.com", "x.com", "twitter.com", "reddit.com",
    "medium.com", "quora.com", "youtube.com", "pinterest.com",
    "prnewswire.com", "globenewswire.com", "businesswire.com",  # ham PR dağıtım
    "marketresearchfuture.com", "marketsandmarkets.com",
    "researchandmarkets.com", "verifiedmarketresearch.com",
    "grandviewresearch.com", "fortunebusinessinsights.com",
    "openpr.com", "einpresswire.com", "issuewire.com",
]

# ============================================================
# EXA SORGULARI (12)
# ------------------------------------------------------------
# Exa'da uzun doğal dil komutu YAZILMAZ. Kısa semantik sorgu + ayrı
# parametreler (domain, tarih, kategori) kullanılır.
# 'ek_sorgular' aynı temanın farklı yüzlerini yakalar.
# 'domain_seti' → hangi kaynak katmanına öncelik verileceği.
# ============================================================
SORGULAR = [
    {
        "id": "politika",
        "kategori": "politika",
        "sorgu": "nuclear energy policy regulation and geopolitics",
        "ek_sorgular": [
            "nuclear power government policy legislation financing support",
            "IAEA NRC nuclear licensing regulatory decision",
            "nuclear export controls enrichment agreement geopolitics",
            "EU nuclear taxonomy state aid Euratom decision",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 25,
    },
    {
        "id": "buyuk-reaktor",
        "kategori": "buyuk-reaktor",
        "sorgu": "new large nuclear reactor construction project",
        "ek_sorgular": [
            "nuclear power plant final investment decision construction start",
            "EPR AP1000 APR1400 VVER new build project",
            "nuclear plant construction milestone first concrete grid connection",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 25,
    },
    {
        "id": "smr",
        "kategori": "smr",
        "sorgu": "small modular reactor SMR development and deployment",
        "ek_sorgular": [
            "SMR design certification license application approval",
            "microreactor advanced reactor demonstration deployment",
            "SMR order agreement utility customer site selection",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 25,
    },
    {
        "id": "yakit",
        "kategori": "yakit",
        "sorgu": "uranium mining enrichment and nuclear fuel supply",
        "ek_sorgular": [
            "uranium production mine restart supply agreement price",
            "HALEU enrichment capacity conversion facility investment",
            "nuclear fuel fabrication contract supply chain Russia dependence",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 20,
    },
    {
        "id": "isletme",
        "kategori": "isletme",
        "sorgu": "nuclear plant operation license extension and restart",
        "ek_sorgular": [
            "nuclear plant life extension license renewal uprate",
            "nuclear reactor restart decision shutdown recommissioning",
            "nuclear plant outage performance capacity factor record",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 20,
    },
    {
        "id": "kurumsal-alim",
        "kategori": "kurumsal-alim",
        "sorgu": "data center nuclear power purchase agreement",
        "ek_sorgular": [
            "hyperscaler nuclear PPA Microsoft Google Amazon Meta",
            "AI datacenter nuclear energy deal behind the meter",
            "industrial heat hydrogen nuclear offtake agreement",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 20,
    },
    {
        "id": "fuzyon",
        "kategori": "fuzyon",
        "sorgu": "fusion energy milestone and investment",
        "ek_sorgular": [
            "fusion pilot plant tokamak stellarator funding round",
            "ITER fusion ignition net energy gain progress",
        ],
        "domain_seti": ["tier1", "tier2", "akademik"],
        "sonuc": 15,
    },
    {
        "id": "atik-sokum",
        "kategori": "atik-sokum",
        "sorgu": "nuclear waste storage disposal and decommissioning",
        "ek_sorgular": [
            "spent fuel repository interim storage decision",
            "nuclear decommissioning contract reactor dismantling",
            "used fuel recycling reprocessing facility",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 15,
    },
    {
        "id": "teknoloji",
        "kategori": "teknoloji",
        "sorgu": "advanced nuclear reactor technology breakthrough",
        "ek_sorgular": [
            "Generation IV molten salt sodium fast reactor progress",
            "nuclear fuel material TRISO accident tolerant development",
            "nuclear research reactor isotope production technology",
        ],
        "domain_seti": ["tier1", "tier2", "akademik"],
        "sonuc": 15,
    },
    {
        "id": "turkiye",
        "kategori": "turkiye",
        "sorgu": "Türkiye nükleer enerji santral Akkuyu Sinop gelişme",
        "ek_sorgular": [
            "Turkey nuclear power plant Akkuyu Sinop SMR",
            "Nükleer Düzenleme Kurumu TENMAK nükleer lisans",
            "Türkiye nükleer yakıt uranyum enerji planı",
            "Turkey SMR small modular reactor agreement",
        ],
        "domain_seti": ["turkiye", "tier1", "tier2"],
        "sonuc": 25,
        "kullanici_konumu": "tr",
    },
    {
        "id": "guvenlik",
        "kategori": "guvenlik",
        "sorgu": "nuclear safety security incident and safeguards",
        "ek_sorgular": [
            "nuclear plant safety event INES incident report",
            "Zaporizhzhia nuclear safety IAEA mission",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 15,
    },
    {
        "id": "rapor",
        "kategori": "rapor",
        "sorgu": "nuclear energy market data and outlook report",
        "ek_sorgular": [
            "IAEA IEA WNA nuclear capacity forecast report",
            "uranium market outlook nuclear investment data",
        ],
        "domain_seti": ["tier1", "tier2"],
        "sonuc": 15,
    },
]
