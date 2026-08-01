# Nükleer Enerji Bülteni

Haftalık otomatik sivil nükleer enerji sektörü, teknoloji ve politika izleme
bülteni — **hakem onaylı yayın akışıyla**.

```
Exa → triyaj (Haiku) → yazım (Sonnet) → Neon taslak → hakem incelemesi (web)
                                            ↓ onay (tek hakem yeterli)
                         Pazartesi 08:00 → docs/ → GitHub Pages
```

Arama motoru **Exa AI**, triyaj **Claude Haiku 4.5**, yazım **Claude Sonnet 5**,
yayın öncesi **onay katmanı** (Neon + Resend + FastAPI inceleme arayüzü), tüm
derin olayların yazılması (**hakem takası için yedek havuz**), sağlayıcı-bağımsız
LLM katmanı, cron **Render**'da, yayın **GitHub Pages** üzerinden.

## Dosyalar

```
config.py            Sorgular (12), kategori taksonomisi (12), kaynaklar, ayarlar
prompts.py           LLM promptları — triyaj + yazım
llm.py               Sağlayıcı soyutlama (anthropic:… / openai:…)
pipeline.py          CRON 1 (Pazar 12:00 TSİ): tarama → taslak → Neon → davet
publish.py           CRON 2 (Pazartesi 08:00 TSİ): yayın veya hatırlatma
db.py                Neon Postgres şeması + CRUD + hakem yönetimi
emails.py            Resend şablonları (davet, hatırlatma, yayın, rapor)
review_app/          FastAPI inceleme servisi (magic link, takas, onay)
site/                Bülten sayfaları (index + arşiv) — "kontrol odası" tasarımı
docs/                GitHub Pages çıktısı (publish.py üretir)
assets/              Hero video/görselleri (hero-loop-pingpong.mp4, hero*.avif/webp)
render.yaml          Render blueprint: 2 cron + 1 web service
sistem-prompt-nukleer.md   Sistemin beyni/referans belgesi
```

## Kurulum

### 1. GitHub deposu
Bu depo `orcaneker/nukleer-enerji-bulteni`.
GitHub → Settings → Pages → Source: **main / docs** seçin.
Site adresi: `https://orcaneker.github.io/nukleer-enerji-bulteni`

**Özel alan adına geçiş** (`nukleer-enerji-bulteni.site` alındığında):

1. `docs/CNAME` dosyası oluşturun, içine **sadece** alan adını yazın:
   `nukleer-enerji-bulteni.site`
2. `config.py → AYARLAR["site_url"]` değerini
   `https://nukleer-enerji-bulteni.site` yapın.
3. Alan adı sağlayıcısında DNS kayıtları:
   - `A` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `www` için `CNAME` → `orcaneker.github.io`
4. GitHub → Settings → Pages → Custom domain alanına aynı adı girin,
   sertifika çıkınca **Enforce HTTPS** kutusunu işaretleyin.

⚠ `site_url` yalnızca RSS bağlantıları ve canlı `seen_events.json` okuması
için kullanılır; yanlış kalırsa sayı sayacı sıfırlanabilir.

### 2. Neon (veritabanı)
Neon projenizden bağlantı dizesini alın (`postgresql://...`), sonra:

```bash
python db.py --init                              # tabloları oluşturur
python db.py --seed "Ad Soyad" mail@ornek.com    # hakem ekler, linkini basar
python db.py --reviewers                         # hakemleri ve linklerini listeler
```

PowerShell'de bağlantı dizesi: `$env:DATABASE_URL="postgresql://..."`

**Üç yönetici (hakem)** `--seed` ile tek tek eklenir. Üçü de aynı taslağı
görür; **tek onay yayına yeter**, ilk onaylayan bülteni yayına alır.

### 3. Render
Repo'yu Render'a bağlayın — `render.yaml` otomatik algılanır (Blueprint).
Üç servis kurulur; ortak env grubuna (`nukleer-bulten-ortak`) anahtarları girin:

| Anahtar | Zorunlu | Not |
|---|---|---|
| `EXA_API_KEY` | ✅ (cron 1) | exa.ai |
| `ANTHROPIC_API_KEY` | ✅ (cron 1) | |
| `OPENAI_API_KEY` | — | sadece `openai:` modeli denenirse |
| `DATABASE_URL` | ✅ (hepsi) | Neon |
| `RESEND_API_KEY` | ✅ (hepsi) | resend.com |
| `MAIL_FROM` | — | vars. `onboarding@resend.dev`; alan adı doğrulayınca değiştirin |
| `GITHUB_REPO` | ✅ (cron 2 + web) | `orcaneker/nukleer-enerji-bulteni` |
| `GITHUB_TOKEN` | ✅ (cron 2 + web) | PAT — Contents: Read & Write |
| `REVIEW_BASE_URL` | ✅ (cron 1-2) | inceleme servisinin URL'i (ör. `https://nukleer-bulten-inceleme.onrender.com`) |
| `RAPOR_ALICI` | — | çalışma raporu e-postası |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | — | sesli bülten; yoksa sessiz yayınlanır |

⚠ `REVIEW_BASE_URL` için önce web servisini deploy edip URL'ini alın,
sonra cron'ların environment'ına yazın.

⚠ `MAIL_FROM` doğrulanmamış kaldığı sürece Resend **yalnızca hesap sahibine**
gönderir; diğer iki hakem daveti ALAMAZ. `python emails.py --test` ile
Pazar'ı beklemeden doğrulayın.

### 4. LLM modeli değiştirme (opsiyonel)
`config.py`:

```python
"model_triyaj": "anthropic:claude-haiku-4-5-20251001",   # vars.
"model_yazim":  "anthropic:claude-sonnet-5",             # vars.
# OpenAI denemesi: OPENAI_API_KEY tanımlayıp şunları yazın:
# "model_triyaj": "openai:gpt-5-mini",
# "model_yazim":  "openai:gpt-5.1",
```

Yeni model kullanırken `FIYAT` sözlüğüne fiyatını da ekleyin (maliyet raporu için).

## Haftalık akış

1. **Pazar 12:00 TSİ** — cron 1 taslağı üretir, Neon'a `review` durumuyla
   yazar, üç hakeme kişisel inceleme linki e-postalanır.
2. **İnceleme** — hakem linke tıklar: haberleri okur, beğenmediğini yedek
   havuzundan takas eder, radar maddesi çıkarabilir, manşeti değiştirebilir.
   **Tek onay yeterli.**
3. **Pazartesi 08:00 TSİ** — cron 2:
   - onaylıysa → nihai bülten + ElevenLabs sesli özet + GitHub push → yayın
   - onaysızsa → hatırlatma e-postası; **otomatik yayın yok**. Onay sonradan
     gelirse inceleme servisi yayını anında tetikler.

## Yerel test (API'siz)

```bash
pip install -r requirements.txt
python pipeline.py --mock --dry-run    # sahte taslak → taslak_preview.json
python publish.py --local-draft        # taslaktan docs/ üretir
python -m http.server 8080 -d docs     # http://localhost:8080 → siteyi gör
```

Gerçek anahtarlarla ama yayınsız: `python pipeline.py --dry-run`.
İnceleme arayüzü (DATABASE_URL gerekir):

```bash
python pipeline.py --mock              # sahte taslağı Neon'a yazar + davet dener
uvicorn review_app.main:app --port 8000
# tarayıcı: http://localhost:8000/r/<hakem-token>
```

## İlk yayın öncesi kontrol listesi

- [ ] `db.py --seed` ile üç hakemi ekleyin
- [ ] `python emails.py --test` ile üçünün de e-posta aldığını doğrulayın
- [ ] Hero videosunu `assets/hero-loop-pingpong.mp4` olarak değiştirin
      (aşağıdaki nota bakın)
- [ ] Render'da cron 1'i elle tetikleyip (Manual Run) daveti test edin
- [ ] İnceleme linkinden takas + onay akışını deneyin
- [ ] Cron 2'yi elle tetikleyip yayını doğrulayın

## Tasarım notu — "Kontrol Odası + Çerenkov"

Site iki katmanlı: gece karanlığındaki **kontrol odası** (hero + footer;
grafit zemin, havuzun Çerenkov mavisi, kontrol çubuğu kadmiyumu) ve gündüz
ışığındaki **vardiya defteri** (açık gövde, okunaklı uzun metin).

**İmza öğe: aşama göstergesi.** Nükleerde "anlaşma imzalandı" ile "şebekeye
bağlandı" arasında 10+ yıl var; sektörün en büyük sinyal-gürültü sorunu bu.
Her haberde projenin 10 kademeli ölçekteki yeri bir kontrol çubuğu göstergesi
olarak çiziliyor. Ölçek `config.py → OLGUNLUK` ile birebir aynı sıradadır —
**oraya yeni bir aşama eklerseniz `site/index.html → OLG_SIRA` ve `OLG`
sözlüklerini de güncelleyin**, yoksa gösterge o haberde boş kalır.
`delayed` / `cancelled` ölçeğin dışındadır; kırmızı "trip" durumu olarak çizilir.

Radar bölümü kayan kart değil, **sütunlara ayrılmış, alt alta akan kümelerdir**
(CSS çoklu kolon: mobilde 1, tablette 2, geniş ekranda 3 sütun). Öne Çıkanlar
ise sürüklenebilir "ekipman künyesi" plaka şeridi olarak kaldı; üstünde
kategori + MWe okuması, altında aşama göstergesi var, imleç üzerine gelince
plaka soldan sağa "enerjileniyor".

Tipografi: **Archivo** (geniş, kazıma künye başlıkları) + **Newsreader**
(gövde serifi) + **Martian Mono** (enstrüman etiketleri).

## Notlar

- **State canlı sitede yaşar** (`docs/data/state/seen_events.json`) çünkü
  Render cron diski her çalışmada sıfırlanır. İlk çalıştırmada 404 normaldir.
- **reuters/bloomberg** Exa `includeDomains`'e eklenemez (403) — dolaylı gelir.
- **Hero videosu**: `assets/hero-loop-pingpong.mp4` şu an **geçici** — kod
  üretimi, kusursuz döngülü 2 sn'lik bir "kullanılmış yakıt havuzu" klibi
  (38 KB). Gerçek tanıtım videosu geldiğinde aynı adla üzerine yazın;
  `assets/hero.avif|webp` (masaüstü) ve `assets/hero-mobile.avif|webp`
  (mobil) poster görsellerini de videodan alınmış bir kareyle değiştirin.
  Video **mobilde ve hareket azaltma modunda hiç indirilmez**; o durumda
  poster görünür.
- **Kapasite metriği**: Yarı iletken bülteninden farklı olarak burada
  `capacity_mwe` bir SAYIDIR (serbest metin değil) — MWe homojen bir birim
  olduğu için `publish.py` haftanın toplam kapasitesini hesaplar ve site
  bunu üst durum şeridinde `Σ … MWe` olarak gösterir.
- Ayar noktaları: hacim `config.py → AYARLAR`, kota `KATEGORILER[...]["kota"]`,
  kaynak `KAYNAK_TIER1/TIER2/TURKIYE`, sorgu `SORGULAR`.
