# ============================================================
# NÜKLEER ENERJİ BÜLTENİ — SİSTEM PROMPT DOSYASI (v2.0)
# ============================================================
# Bu dosya sistemin BEYNİ ve REFERANS BELGESİDİR.
# Kodda karşılıkları:
#   BÖLÜM 1 (sorgular)       → config.py  → SORGULAR
#   BÖLÜM 2 (taksonomi)      → config.py  → KATEGORILER / OLGUNLUK
#   BÖLÜM 3 (LLM promptları) → prompts.py → TRIYAJ_PROMPT / YAZIM_PROMPT
#   BÖLÜM 4 (kaynaklar)      → config.py  → KAYNAK_TIER1/TIER2/...
#   BÖLÜM 5 (onay akışı)     → db.py / review_app / publish.py
#   BÖLÜM 6-7 (ayar, şema)   → config.py  → AYARLAR
#   BÖLÜM 8 (tasarım)        → site/index.html + site/arsiv.html
#
# Buradaki bir şeyi değiştirdiğinde İLGİLİ KOD DOSYASINI DA GÜNCELLE.
#
# Yarı iletken bülteninden (orcaneker/yari-iletkenler-bulteni) uyarlanmıştır;
# alan bilgisi (kategoriler, kaynaklar, sorgular, promptlar) bu deponun v1
# sürümünden taşındı. v1'den (Perplexity + Netlify) farkları:
#   1. ARAMA: Perplexity yerine Exa AI (semantik + domain filtreli)
#   2. İKİ AŞAMA: triyaj (Haiku) → yazım (Sonnet) — eskiden tek çağrı
#   3. ONAY KATMANI: taslak → hakem incelemesi → onay → yayın
#   4. Neon Postgres (taslak/onay durumu) + Resend (e-posta)
#   5. Cron GitHub Actions yerine Render; yayın Netlify yerine GitHub Pages
#   6. Radar + "Bu Hafta 60 Saniyede" + ElevenLabs sesli özet + yedek havuz
#   7. Yazım modeli Sonnet 4.6 → Sonnet 5 (adaptif düşünme, geniş çıktı bütçesi)
#   8. Tamamen yeni ön yüz: "Kontrol Odası + Çerenkov" (bkz. BÖLÜM 8)
# ============================================================


# ============================================================
# BÖLÜM 0 — MİMARİ
# ============================================================
#
# CRON 1 — Pazar 13:00 TSİ (Render Cron, UTC "0 10 * * 0")
#   ⚠ Saat, diğer iki bültenle aynı API anahtarını paylaştığı için
#     kaydırıldı: biyoekonomi 12:00 · yarı iletken 12:30 · nükleer 13:00
#   pipeline.py
#   ↓ EXA SEARCH — 12 sorgu × ek sorgu varyasyonları
#   ↓ NORMALİZASYON — UTM/AMP temizliği, başlık hash, görülmüş URL elemesi
#   ↓ DETERMİNİSTİK TARİH FİLTRESİ — pencere dışı/tarihsiz aday LLM'e gitmeden elenir
#   ↓ AŞAMA 1 — triyaj modeli (Haiku): olay kümeleme, eleme, puanlama
#   ↓ AŞAMA 2 — yazım modeli (Sonnet): 14 derin olayın TAMAMI tam haber
#     (8-10 "one_cikan" + kalanı "yedek") + radar + brief
#   ↓ TASLAK → Neon'a kaydet (status=review)
#   ↓ Resend → üç hakeme davet e-postası (magic link)
#
# İNCELEME — Render Web Service (FastAPI, sürekli)
#   Hakem linke tıklar → taslağı görür
#   · Haberi çıkar → yedek havuzundan birini yerine koy (takas)
#   · Yedeği doğrudan bültene al / manşeti değiştir / radar maddesi çıkar
#   · "Onayla ve Yayınla" → status=approved  (TEK ONAY YETERLİ)
#   · Onay Pazartesi 08:00 TSİ'den SONRA gelirse yayın ANINDA tetiklenir
#
# CRON 2 — Pazartesi 08:00 TSİ (Render Cron, UTC "0 5 * * 1")
#   publish.py
#   · status=approved → nihai JSON kur (takaslar uygulanmış) → arşiv +
#     state + RSS + ElevenLabs sesli özet → docs/ → GitHub push → Pages
#   · status=review   → Resend hatırlatma e-postası; YAYIN YAPILMAZ
#     (otomatik yayın YOK — onay gelene dek bekler)
#   · Çalışma raporu e-postası (Resend → RAPOR_ALICI)


# ============================================================
# BÖLÜM 1 — EXA ARAMA SORGULARI (12)
# ============================================================
# config.py → SORGULAR. Kısa semantik sorgu + ayrı parametreler
# (tarih, domain, konum). Uzun doğal dil komutu YAZILMAZ.
#
#   politika        mevzuat, lisanslama, Euratom, taksonomi, jeopolitik
#   buyuk-reaktor   yeni inşa, FID, EPR/AP1000/APR1400/VVER kilometre taşları
#   smr             SMR & mikro reaktör: tasarım onayı, sipariş, saha seçimi
#   yakit           uranyum madenciliği, dönüşüm, zenginleştirme, HALEU, yakıt üretimi
#   isletme         ömür uzatma, lisans yenileme, yeniden başlatma, kapasite faktörü
#   kurumsal-alim   veri merkezi PPA'ları, hyperscaler anlaşmaları, endüstriyel ısı
#   fuzyon          tokamak/stellarator kilometre taşı, yatırım turu, ITER
#   atik-sokum      kullanılmış yakıt deposu, ara depolama, söküm, yeniden işleme
#   teknoloji       Gen-IV, ergimiş tuz, sodyum soğutmalı hızlı reaktör, TRISO, izotop
#   turkiye         Akkuyu, Sinop, NDK, TENMAK (Türkçe + userLocation=tr)
#   guvenlik        INES olayları, IAEA denetimi, Zaporijya
#   rapor           IAEA/IEA/WNA kapasite tahmini, uranyum piyasası verisi
#
# Tarih penceresi: birincil 7 gün; <40 aday kalırsa 14 güne genişler.
# ⚠ Türkiye için AYRI geniş pencere KULLANILMIYOR. 21 gün denendi; bir
# sonraki sayıda aynı haberin tekrarlanması riskini doğurduğu için hakem
# kararıyla geri alındı. Türkiye sorgusu yalnızca userLocation="tr" ile
# yerel sonuç ağırlığı alır.


# ============================================================
# BÖLÜM 2 — KATEGORİ TAKSONOMİSİ (12) ve KOTALAR
# ============================================================
# config.py → KATEGORILER. "kota" = Öne Çıkanlar'da hedef sayı (katı değil).
# Kota olmadan SMR duyuruları ve veri merkezi anlaşmaları akışı domine eder.
#
#   politika (2) · smr (2) · buyuk-reaktor (1) · yakit (1) · isletme (1) ·
#   kurumsal-alim (1) · fuzyon (0) · atik-sokum (0) · teknoloji (1) ·
#   turkiye (1) · guvenlik (0) · rapor (1)
#
# OLGUNLUK (config.py → OLGUNLUK) — proje olaylarında ZORUNLU:
#   research → design_cert → site_permit → licensed → announced → funded →
#   construction → commissioning → grid_connection → operational
#   (+ ölçek dışı: delayed / cancelled)
# "Anlaşma imzalandı" ile "şebekeye bağlandı" arasında 10+ yıl var — bu
# sektörün en büyük sinyal-gürültü sorunudur, aşama net belirtilir.
# ⚠ Bu ölçek sitede GÖRSEL olarak çizilir (bkz. BÖLÜM 8). Sıra değişirse
# site/index.html → OLG_SIRA da değişmeli.
#
# DEĞER ZİNCİRİ (config.py → DEGER_ZINCIRI):
#   uranyum → donusum-zenginlestirme → yakit-uretim → reaktor-insa →
#   isletme → atik-sokum → uygulama


# ============================================================
# BÖLÜM 3 — LLM PROMPTLARI
# ============================================================
# prompts.py → TRIYAJ_PROMPT (Haiku) + YAZIM_PROMPT (Sonnet).
#
# TRİYAJ: sınıflandırır, YORUM YAPMAZ. Olay kümeler (aynı gelişmenin farklı
#   haberleri = 1 olay), eler (tarih dışı, söylenti, SEO, hisse yorumu,
#   nükleer SİLAH / askerî program), 1-10 puanlar.
# YAZIM: Türkçeleştirir, SOMUT VERİYİ (tutar, MWe kapasite, reaktör tipi,
#   zenginlik oranı, SWU, takvim, saha, program) eksiksiz çıkarır.
#   ANALİZ/YORUM YASAK. Kaynağın durumunu ASLA anlatmaz. Derin olayların
#   TAMAMINI yazar (hakem takası için) — İKİ MUTLAK KURAL: kaynakta
#   olmayanı ekleme, sayısal verileri eksiksiz/birebir koru.
#   ⚠ MWe (elektrik) ile MWt (termal) ASLA karıştırılmaz.


# ============================================================
# BÖLÜM 4 — KAYNAK KATMANLARI
# ============================================================
# config.py → KAYNAK_TIER1 (birincil: IAEA, OECD-NEA, NRC, ENSREG, ONR, ASNR,
#   DOE/INL/ORNL + reaktör tedarikçileri ve işletmeciler + SMR geliştiricileri
#   + yakıt zinciri şirketleri + füzyon girişimleri),
#   KAYNAK_TIER2 (World Nuclear News, NEI Magazine, NucNet, ANS, Power
#   Engineering, Utility Dive, Data Center Dynamics…), KAYNAK_AKADEMIK,
#   KAYNAK_TURKIYE (enerji.gov.tr, ndk.gov.tr, tenmak.gov.tr, akkuyunpp.com…).
# ÖDEME DUVARI: KAYNAK_ODEME_DUVARI'ndaki kaynaklar (FT, WSJ, Nikkei,
#   Energy Intelligence, Montel, S&P Global, Wood Mackenzie…) asla birincil
#   olmaz; tek kaynak duvarlıysa olay Radar'a düşer, teyit araması
#   erişilebilir kaynak bulmaya çalışır. DIŞLANANLAR: sosyal medya, PR wire,
#   SEO pazar araştırma siteleri (config.py → KAYNAK_DISLA).
# ⚠ reuters.com / bloomberg.com Exa includeDomains'e EKLENMEZ (403).


# ============================================================
# BÖLÜM 5 — ONAY AKIŞI
# ============================================================
# db.py (Neon) issue durumları: review → approved → published.
# ÜÇ hakem tanımlıdır; TEK onay yeterlidir. Onay Pazartesi 08:00'den
# önceyse cron 2 yayınlar; sonraysa inceleme servisi publish.yayinla()'yı
# anında çağırır.
# Hakem ekleme: python db.py --seed "Ad Soyad" mail@ornek.com


# ============================================================
# BÖLÜM 6 — GENEL AYARLAR (config.py → AYARLAR)
# ============================================================
#   haber (Öne Çıkanlar) : 8-10  ·  derin olay: 14  ·  radar: 18-30
#   pencere: 7 gün (yetersizse 14) ·  brief: 5 madde
#   yayım: Pazartesi 08:00 TSİ  ·  taslak: Pazar 13:00 TSİ
#   model_triyaj: anthropic:claude-haiku-4-5-20251001
#   model_yazim:  anthropic:claude-sonnet-5
#   site_url: https://orcaneker.github.io/nukleer-enerji-bulteni
#             (nukleer-enerji-bulteni.site alınınca güncellenecek —
#              adımlar README'de)
#
# sayi_no_sabit = None → sayı otomatik artar. Sayaç canlı sitedeki
# data/state/seen_events.json → issue_no alanında yaşar. Arşiv sıfırdan
# başladığı için ilk gerçek çalıştırma Sayı 1 olur.


# ============================================================
# BÖLÜM 7 — VERİ ŞEMASI (latest.json)
# ============================================================
# issue: number · hafta · publication_date · coverage_start/end ·
#        window_days · audio{url,duration_sec,voice,chars,generated_at}
# brief: [{text, slug|null}]  (5 madde)
# metrics: aciklanan_yatirim_usd_milyon · kapasite_mwe · proje_sayisi ·
#          politika_gelismesi · kapsanan_ulke
#   ⚠ kapasite_mwe: yarı iletkenden FARKLI olarak burada kapasite tek ve
#     homojen bir birimle (MWe) ifade edildiği için TOPLANABİLİR. Site bunu
#     üst durum şeridinde "Σ … MWe" olarak okur.
# lead / stories[]: id · slug · title · excerpt · detail · neden_onemli(null) ·
#   category · subcategories · value_chain · maturity · companies ·
#   countries · technologies · capacity_mwe(SAYI) · investment{...} ·
#   published_date · event_date · source{name,url,type,tier,primary} ·
#   supporting_sources[] · image{url,credit,type} · score
# radar: [{kume, maddeler:[{title,url,source,date,category}]}]


# ============================================================
# BÖLÜM 8 — SİTE TASARIMI: "KONTROL ODASI + ÇERENKOV"
# ============================================================
# site/index.html + arsiv.html. Biyoekonomi (yeşil/toprak "biyofilm") ve
# yarı iletken (bakır/kehribar "fab temiz odası") bültenlerinden YAPI olarak
# da ayrışır — yalnızca palet değişikliği değildir.
#
# PALET (konudan türetildi):
#   grafit #15171B / #1B1E24   — moderatör, kontrol odası karanlığı
#   Çerenkov #7C9CFF (koyu üstünde) · #2846C4 (kağıt üstünde, AA 6.3:1)
#   kadmiyum #E0A93B (koyu) · #7E5A0C (kağıt, AA 5.1:1) — kontrol çubuğu
#   kağıt #E8E9E6 / plaka #F5F6F3 — boyalı beton grisi, KREM DEĞİL
#   sıcak #B03A2E — ertelendi/iptal
#
# TİPOGRAFİ: Archivo (geniş/expanded, kazıma künye başlıkları) +
#   Newsreader (gövde serifi) + Martian Mono (enstrüman etiketleri).
#   Fraunces bilinçli olarak KULLANILMADI — o diğer iki bültenin dili.
#
# YAPI:
#   durum şeridi → sticky masthead → koyu hero (ping-pong video + havuz
#   parıltısı + yükselen kabarcık tuvali) → açık gövde (60 Saniyede →
#   Manşet → Öne Çıkanlar plaka şeridi → Radar sütunları → arşiv bandı)
#   → modal → koyu footer
#
# İMZA ÖĞE — AŞAMA GÖSTERGESİ:
#   Her haberde projenin 10 kademeli olgunluk ölçeğindeki yeri bir kontrol
#   çubuğu göstergesi olarak çizilir; geçilen kademeler dolu, bulunulan
#   kademe yükseltilmiş ve parlak. Görünür alana girince soldan sağa dolar.
#   delayed/cancelled ölçeğin DIŞINDADIR → kırmızı "trip" durumu.
#   ⚠ site/index.html → OLG_SIRA, config.py → OLGUNLUK ile BİREBİR aynı
#   sırada olmalı. Yeni aşama eklenirse ikisi birden güncellenir.
#
# RADAR: Kayan kart DEĞİL — CSS çoklu kolon ile sütunlara ayrılmış, alt alta
#   akan kümeler (mobil 1 / tablet 2 / geniş 3 sütun). Her küme bir vardiya
#   defteri sayfası: mono başlık bandı + madde sayısı + kaynak·tarih satırları.
#
# ÖNE ÇIKANLAR: Sürüklenebilir plaka şeridi. Her plaka bir "ekipman künyesi":
#   üstte kategori + MWe okuması, ortada başlık/özet, altında aşama göstergesi
#   ve kaynak·tarih. İmleç üzerine gelince üst kenar soldan sağa Çerenkov'a
#   döner (enerjilendirme). Şerit altındaki gösterge kart ilerleme çubuğu
#   değil, "çubuk konum göstergesi" + "3–5 / 9" okuması.
#
# HERO: assets/hero-loop-pingpong.mp4 (sessiz, 1280×548, 16 sn) +
#   hero*.avif/webp poster. Mavi saatte sahil nükleer santrali: dört
#   konteynman kubbesi sağ yarıda, sol yarı karanlık deniz/gökyüzü —
#   başlık tam oraya oturduğu için kompozisyon böyle seçildi.
#   Seedance 2.0 ile 8 sn üretilip ileri+ters birleştirilerek döngülendi.
#   ⚠ Hareket yalnızca su ve ışıkla sınırlı: ping-pong'da ters oynadığı
#   için yön belirten hareket (yükselen duman, geçen araç) bozulur.
#   Video mobilde ve hareket azaltma modunda HİÇ indirilmez.
#
# ERİŞİLEBİLİRLİK TABANI: mobil uyumlu, görünür klavye odağı, modalda odak
#   tuzağı, prefers-reduced-motion'da tüm animasyon kapalı, aşama göstergesi
#   ekran okuyucuya "Proje aşaması: inşaat — 10 kademeden 7." diye okunur.
