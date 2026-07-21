# ============================================================
# NÜKLEER ENERJİ BÜLTENİ — SİSTEM PROMPT DOSYASI (v1.0)
# ============================================================
# Bu dosya sistemin BEYNİ ve REFERANS BELGESİDİR.
# Kodda karşılıkları:
#   BÖLÜM 1 (sorgular)       → config.py  → SORGULAR
#   BÖLÜM 2 (taksonomi)      → config.py  → KATEGORILER / OLGUNLUK
#   BÖLÜM 3 (LLM promptları) → prompts.py → TRIYAJ_PROMPT / YAZIM_PROMPT
#   BÖLÜM 4 (kaynaklar)      → config.py  → KAYNAK_TIER1/TIER2/...
#   BÖLÜM 5 (onay akışı)     → db.py / review_app / publish.py
#   BÖLÜM 6-8 (şema, ayar)   → config.py  → AYARLAR
#
# Buradaki bir şeyi değiştirdiğinde İLGİLİ KOD DOSYASINI DA GÜNCELLE.
#
# Yarı iletken bülteninden (orcaneker/yari-iletkenler-bulteni) farkları:
#   1. ONAY KATMANI: taslak → hakem incelemesi → onay → yayın
#   2. Neon Postgres (taslak/onay durumu) + Resend (e-posta)
#   3. Derin olayların TAMAMI yazılır → hakem takası için yedek havuz
#   4. Sağlayıcı-bağımsız LLM katmanı (anthropic:/openai: önekleri)
#   5. Açık temalı "kurumsal dosya" tasarımı (Çerenkov mavisi)
# ============================================================


# ============================================================
# BÖLÜM 0 — MİMARİ
# ============================================================
#
# CRON 1 — Pazar 12:00 TSİ (Render Cron, UTC "0 9 * * 0")
#   pipeline.py
#   ↓ EXA SEARCH — 12 sorgu × ek sorgu varyasyonları
#   ↓ NORMALİZASYON — UTM/AMP temizliği, başlık hash, görülmüş URL elemesi
#   ↓ AŞAMA 1 — triyaj modeli (ucuz): olay kümeleme, eleme, puanlama
#   ↓ AŞAMA 2 — yazım modeli (kaliteli): 14 derin olayın TAMAMI tam haber
#     (8-10 "one_cikan" + kalanı "yedek") + radar + brief
#   ↓ TASLAK → Neon'a kaydet (status=review)
#   ↓ Resend → hakemlere davet e-postası (magic link)
#
# İNCELEME — Render Web Service (FastAPI, sürekli)
#   Hakem linke tıklar → taslağı görür
#   · Haberi çıkar → yedek havuzundan birini yerine koy (takas)
#   · Radar maddesi çıkarabilir
#   · "Onayla ve Yayınla" → status=approved  (TEK ONAY YETERLİ)
#   · Onay Pazartesi 08:00 TSİ'den SONRA gelirse yayın ANINDA tetiklenir
#
# CRON 2 — Pazartesi 08:00 TSİ (Render Cron, UTC "0 5 * * 1")
#   publish.py
#   · status=approved → nihai JSON kur (takaslar uygulanmış) → arşiv +
#     state + RSS + ElevenLabs sesli özet → docs/ → GitHub push → Pages
#   · status=review   → Resend hatırlatma e-postası; YAYIN YAPILMAZ
#     (otomatik yayın YOK — onay gelene dek bekler)
#   · Çalışma raporu e-postası (Resend)


# ============================================================
# BÖLÜM 1 — EXA ARAMA SORGULARI (12)
# ============================================================
# config.py → SORGULAR. Kısa semantik sorgu + ayrı parametreler
# (tarih, domain, konum). Uzun doğal dil komutu yazılmaz.
#
#   politika       nükleer politika, düzenleme, jeopolitik, AB taksonomi
#   buyuk-reaktor  yeni büyük santral projeleri (EPR/AP1000/APR1400/VVER)
#   smr            SMR & mikro reaktörler: tasarım onayı, sipariş, saha
#   yakit          uranyum, dönüşüm, zenginleştirme, HALEU, yakıt üretimi
#   isletme        uzatma, güç artırımı, yeniden başlatma, performans
#   kurumsal-alim  veri merkezi / hiperölçekli PPA, endüstriyel ısı
#   fuzyon         füzyon kilometre taşları ve yatırımlar
#   atik-sokum     atık depolama, nihai depo, söküm, yeniden işleme
#   teknoloji      Gen-IV, malzeme, TRISO, araştırma reaktörleri
#   turkiye        Akkuyu, Sinop, NDK, TENMAK (21 günlük geniş pencere)
#   guvenlik       nükleer güvenlik/emniyet olayları, INES, IAEA misyonları
#   rapor          IAEA/IEA/WNA piyasa verisi ve raporlar
#
# ⚠ SİVİL nükleer enerji odaklıyız. Nükleer silah/askeri program haberleri
#   triyajda reddedilir (enerji sektörünü etkileyen yaptırım/ihracat
#   kontrolü politikaları HARİÇ).


# ============================================================
# BÖLÜM 2 — TAKSONOMİ
# ============================================================
# 12 kategori (config.py → KATEGORILER, kota = Öne Çıkanlar çeşitlilik hedefi):
#   politika 2 · smr 2 · buyuk-reaktor 1 · yakit 1 · isletme 1 ·
#   kurumsal-alim 1 · teknoloji 1 · turkiye 1 · rapor 1 ·
#   fuzyon 0 · atik-sokum 0 · guvenlik 0   (0 = kota yok, puanla girer)
#
# ⚠ KOTA NEDEN VAR: SMR duyuruları ve hiperölçekli PPA haberleri akışı
#   domine eder. Kota olmadan bültenin yarısı SMR basın bülteni olur.
#
# OLGUNLUK ÖLÇEĞİ (nükleere özgü — en kritik sinyal/gürültü filtresi):
#   research → design_cert → site_permit → licensed → announced → funded
#   → construction → commissioning → grid_connection → operational
#   (+ delayed / cancelled)
# "Niyet mektubu" ile "şebekeye bağlı reaktör" arasında 10+ yıl vardır.
# Yazımda fiili aşama açıkça belirtilir: "anlaşma imzalandı" ≠
# "lisans alındı" ≠ "inşaat başladı" ≠ "ticari işletmeye geçti".
#
# DEĞER ZİNCİRİ ETİKETLERİ (site navigasyonu):
#   uranyum · donusum-zenginlestirme · yakit-uretim · reaktor-insa ·
#   isletme · atik-sokum · uygulama


# ============================================================
# BÖLÜM 3 — LLM TALİMATLARI (prompts.py)
# ============================================================
# AŞAMA 1 (triyaj): olay kümeleme → eleme → sınıflandırma → olgunluk →
# puanlama (1-10). Öncelik merdiveni:
#   [10] Türkiye'yi doğrudan etkileyen (Akkuyu, Sinop, NDK, yakıt tedariki)
#   [9]  Büyük düzenleyici karar (lisans, tasarım onayı, mevzuat)
#   [8]  Büyük yatırım/FID >1 mlr USD, yeni reaktör kararı, büyük PPA
#   [7]  Yakıt zinciri kırılması (uranyum/zenginleştirme/HALEU)
#   [6]  Proje kilometre taşı (ilk beton, kritiklik, şebeke bağlantısı)
#   [5]  Doğrulanmış sektör verisi (IAEA/IEA/WNA)
#   [4]  Ortaklık, orta ölçekli anlaşma
#   [1-3] Rutin/tekrar
#
# AŞAMA 2 (yazım): Türkçe, kurumsal ton, ANALİZ YOK (neden_onemli=null),
# rakam sadakati (MWe, ton U3O8, SWU, %, USD), kaynak durumu anlatma
# yasağı, söylenti kısıtı. Teknik terim ilk geçişte parantezli:
# "küçük modüler reaktör (SMR)", "nihai yatırım kararı (FID)",
# "yüksek oranda zenginleştirilmiş düşük seviyeli uranyum (HALEU)".
#
# ⚠ ONAY KATMANI GEREĞİ: 14 derin olayın TAMAMI tam haber yazılır.
#   Model "secim" alanıyla one_cikan/yedek önerir; son karar hakemde.


# ============================================================
# BÖLÜM 4 — KAYNAK KATMANLARI (config.py)
# ============================================================
# TIER 1 (birincil): IAEA, NRC, DOE, OECD-NEA, WNA, AB kurumları, ONR,
#   ulusal düzenleyiciler + şirket newsroom'ları (Westinghouse, EDF,
#   Framatome, Rosatom, KHNP, GE Vernova; NuScale, X-energy, TerraPower,
#   Oklo, Kairos, Rolls-Royce SMR, Holtec; Cameco, Urenco, Orano,
#   Kazatomprom, Centrus; ITER, CFS, Helion...)
# TIER 2: World Nuclear News, NEI Magazine, NucNet, ANS, POWER Mag,
#   Utility Dive, Montel, DataCenterDynamics...
# TÜRKİYE: enerji.gov.tr, ndk.gov.tr, tenmak.gov.tr, akkuyunpp.com,
#   resmigazete.gov.tr, AA, Dünya, Ekonomim, BloombergHT, EnerjiGünlüğü...
# ⚠ reuters/bloomberg Exa includeDomains'e EKLENMEZ (403) — dolaylı gelir.
# ÖDEME DUVARI: FT, WSJ, Nikkei, Economist, S&P, WoodMac, BNEF... —
#   dışlanmaz ama birincil olamaz; tek kaynaksa Radar'a düşer;
#   teyit aramasıyla erişilebilir kaynak bulunursa "bildirildi" diliyle yazılır.
# DIŞLA: sosyal medya, ham PR dağıtım, SEO pazar araştırması siteleri.


# ============================================================
# BÖLÜM 5 — ONAY AKIŞI VE VERİ MODELİ (Neon Postgres)
# ============================================================
# issues:
#   id · hafta (2026-W30) · sayi_no · status (review→approved→published)
#   draft_json   ← pipeline çıktısı (tüm haberler + secim alanları)
#   final_json   ← yayın anında kurulan nihai bülten
#   approved_by · approved_at · published_at · rapor (çalışma istatistikleri)
# reviewers:
#   id · ad · email · token (magic link: {REVIEW_BASE_URL}/r/{token}) · aktif
# events_log:
#   issue_id · reviewer · eylem (goruntuledi/takas/radar_cikar/onay/yayin) · detay · ts
#
# KURALLAR:
#   · TEK hakem onayı yeterli (istenirse ileride çoğunluk/tam onaya çevrilir)
#   · Otomatik yayın YOK — onay gelmeden bülten çıkmaz
#   · Pazartesi 08:00'de onay yoksa: hatırlatma e-postası, bekleme
#   · Onay 08:00'den önce geldiyse yayın CRON 2'ye bırakılır (08:00'de çıkar)
#   · Onay 08:00'den sonra geldiyse review_app yayını ANINDA tetikler
#   · Takas: one_cikan ↔ yedek yer değiştirir; içerik zaten yazılı olduğu
#     için LLM'e dönülmez. Brief maddesi çıkarılan habere ref veriyorsa
#     ref=null yapılır (metin korunur).


# ============================================================
# BÖLÜM 6 — ÇIKTI ŞEMASI (docs/data/latest.json)
# ============================================================
# issue:   number · hafta · publication_date · coverage_start/end ·
#          window_days · audio {url, duration_sec, voice, generated_at} | null
# brief:   5 × {text, slug|null}
# metrics: aciklanan_yatirim_usd_milyon · toplam_kapasite_mwe ·
#          politika_gelismesi · kapsanan_ulke     ← koddan hesaplanır
# lead:    story (manşet)
# stories: 7-9 story (öne çıkanlar; manşet hariç)
# radar:   [{kume, maddeler[{title, source, url, date, category}]}]
#
# story: id · slug · title · excerpt · detail · neden_onemli(null) ·
#   category · subcategories · value_chain · maturity · companies ·
#   countries · technologies · capacity_mwe · investment{...} ·
#   published_date · event_date · source{name,url,type,tier,primary} ·
#   supporting_sources · image{url,credit,type} · score
#
# Slug ve metrikler MODELDEN İSTENMEZ — kod deterministik üretir.


# ============================================================
# BÖLÜM 7 — KALICI HAFIZA (STATE)
# ============================================================
# Render diski geçici → "görülmüş olaylar" canlı sitede yaşar:
#   pipeline.py başında  → GET {site_url}/data/state/seen_events.json
#   publish.py sonunda   → güncel state docs/ içine yazılır, push edilir
# İlk çalıştırmada 404 normaldir — sıfırdan başlar.
# Şema: issue_no · events[{baslik_ozet, hafta}] (son ~400) · urls[] (son ~3000)


# ============================================================
# BÖLÜM 8 — GENEL AYARLAR / ORTAM DEĞİŞKENLERİ
# ============================================================
# Takvim : taslak Pazar 12:00 TSİ (UTC 0 9 * * 0) ·
#          yayın Pazartesi 08:00 TSİ (UTC 0 5 * * 1)
# Modeller: anthropic:claude-haiku-4-5-20251001 (triyaj) ·
#           anthropic:claude-sonnet-4-6 (yazım)
#           OpenAI denemesi: OPENAI_API_KEY + "openai:gpt-5-mini" vb.
# temperature BİLEREK gönderilmez.
#
# Env: EXA_API_KEY · ANTHROPIC_API_KEY · OPENAI_API_KEY(ops) ·
#      DATABASE_URL (Neon) · RESEND_API_KEY · MAIL_FROM ·
#      GITHUB_REPO · GITHUB_TOKEN · GITHUB_BRANCH ·
#      REVIEW_BASE_URL · RAPOR_ALICI ·
#      ELEVENLABS_API_KEY(ops) · ELEVENLABS_VOICE_ID(ops)


# ============================================================
# BÖLÜM 9 — SESLİ BÜLTEN (ElevenLabs)
# ============================================================
# publish.py, ONAYLI nihai içerikten ses metni üretir:
#   giriş (sayı/tarih) + "Bu Hafta 60 Saniyede" 5 maddesi + kapanış.
# Parantez içi İngilizce terimler ayıklanır. eleven_multilingual_v2.
# Çıktı: docs/assets/audio/{hafta}.mp3 · issue.audio doldurulur.
# Anahtar yoksa/hata olursa bülten SESSİZ yayınlanır — akış kırılmaz.
# Taslak aşamasında TTS çağrısı YAPILMAZ (maliyet).


# ============================================================
# BÖLÜM 10 — v2 KANCALARI
# ============================================================
# 1. Editoryal analiz ("Neden önemli?") — şema alanı bugünden rezerve
# 2. Hero videosu (higgsfield.ai) — assets/video/hero.webm koyunca açılır,
#    çalışma zamanı bağımlılığı yok; hedef ≤1.5 MB, 6-8 sn, sessiz
# 3. Çoklu onay modu (çoğunluk / tam onay) — reviewers tablosu hazır
# 4. Hakem yorum alanı (haber bazında not bırakma)
# 5. Şirket/ülke sayfaları · reaktör projesi zaman çizelgesi ·
#    kapasite veri tabanı · e-posta aboneliği
