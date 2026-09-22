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
llm.py               Sağlayıcı soyutlama (openrouter:… / anthropic:… / openai:…)
pipeline.py          CRON 1 (Pazar 13:00 TSİ): tarama → taslak → Neon → davet
publish.py           CRON 2 (Pazartesi 08:00 TSİ): yayın veya hatırlatma
db.py                Neon Postgres şeması + CRUD + hakem yönetimi
emails.py            Resend şablonları (davet, hatırlatma, yayın, rapor)
review_app/          FastAPI inceleme servisi (magic link, takas, onay)
site/                Bülten sayfaları (index + arşiv) — "kontrol odası" tasarımı
docs/                GitHub Pages çıktısı (publish.py üretir)
assets/              Hero videosu ve posterleri (hero-loop.mp4, hero*.avif/webp)
render.yaml          Render blueprint: 2 cron + 1 web service
sistem-prompt-nukleer.md   Sistemin beyni/referans belgesi
```

## Kurulum

### 1. GitHub deposu
Bu depo `orcaneker/nukleer-enerji-bulteni`.
GitHub → Settings → Pages → Source: **main / docs** seçin.

Özel alan adı: **`nukleer-enerji-bulteni.site`** (Namecheap).
`docs/CNAME` ve `config.py → AYARLAR["site_url"]` bu adla eşleşir — **ikisi
birden** değişmeli, yoksa RSS bağlantıları yanlış adrese çıkar ve `publish.py`
canlı `seen_events.json`'ı okuyamayıp sayı sayacını sıfırlar.

DNS kayıtları (Namecheap → Domain List → Manage → **Advanced DNS**):

| Tip | Host | Değer | Amaç |
|---|---|---|---|
| A | `@` | `185.199.108.153` | GitHub Pages |
| A | `@` | `185.199.109.153` | GitHub Pages |
| A | `@` | `185.199.110.153` | GitHub Pages |
| A | `@` | `185.199.111.153` | GitHub Pages |
| CNAME | `www` | `orcaneker.github.io.` | www → apex |
| MX | `send` | Resend'in verdiği (öncelik 10) | e-posta geri bildirimi |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` | SPF |
| TXT | `resend._domainkey` | Resend'in verdiği `p=…` | DKIM |

⚠ Namecheap'in hazır gelen **`CNAME www → parkingpage.cash…`** ve
**`URL Redirect @ → http://www…`** kayıtları SİLİNMELİ; durdukları sürece
Pages çalışmaz.

Son adım: GitHub → Settings → Pages → **Custom domain** alanına
`nukleer-enerji-bulteni.site` yazıp kaydedin; sertifika çıkınca
**Enforce HTTPS**'i işaretleyin.

⚠ `docs/CNAME` dosyasını silmeyin. `publish.py → deploy()` hedefteki `docs/`
klasörünü silip yerelin kopyasını koyuyor; dosya yerelde yoksa push depodaki
CNAME'i de siler ve alan adı düşer.

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
| `OPENROUTER_API_KEY` | ✅ (cron 1) | openrouter.ai/settings/keys — `sk-or-v1-…`; anahtara kredi limiti koyun |
| `ANTHROPIC_API_KEY` | — | yedek: `config.py`'de `anthropic:` modeline dönülürse |
| `OPENAI_API_KEY` | — | sadece `openai:` modeli denenirse |
| `DATABASE_URL` | ✅ (hepsi) | Neon |
| `RESEND_API_KEY` | ✅ (hepsi) | resend.com |
| `MAIL_FROM` | ⚠ | `Nükleer Enerji Bülteni <bulten@nukleer-enerji-bulteni.site>` — boş bırakılırsa `onboarding@resend.dev` kullanılır ve **yalnızca hesap sahibine** gönderilir |
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

⚠ `MAIL_FROM`'daki alan adı o Resend hesabında **doğrulanmamışsa** gönderim
403 ile reddedilir (`domain is not verified`). Bu koşuyu DÜŞÜRMEZ: taslak
davetlerden önce Neon'a yazıldığı için üretilen iş korunur, yalnızca hakemler
linki alamaz. Ayarı düzelttikten sonra pipeline'ı baştan çalıştırmayın —
ücret öder ve taslağı ezersiniz. Bunun yerine:

```bash
python pipeline.py --davet-yinele
```

Bekleyen taslağı Neon'dan okuyup davetleri yeniden gönderir; Exa/LLM
çalışmaz. Ulaşamadığı hakemin linkini log'a basar, elle iletebilirsiniz.

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

1. **Pazar 13:00 TSİ** — cron 1 taslağı üretir, Neon'a `review` durumuyla
   yazar, üç hakeme kişisel inceleme linki e-postalanır.

   ⚠ Bu saat diğer iki bültenle çakışmayacak şekilde seçildi (biyoekonomi
   12:00, yarı iletken 12:30). Üçü de aynı Anthropic/Exa anahtarını
   kullanıyor ve hız limitleri anahtar başına işliyor — gerekçe
   `render.yaml` başındaki notta.
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

- [ ] Namecheap'te DNS kayıtlarını girin (yukarıdaki tablo), park kayıtlarını silin
- [ ] GitHub → Pages → Custom domain + Enforce HTTPS
- [ ] Resend'de alan adını doğrulayın, `MAIL_FROM`'u güncelleyin
- [ ] Nükleer için **ayrı** bir Neon projesi açın (`issues.hafta` UNIQUE —
      başka bir bültenin veritabanı paylaşılırsa aynı haftada çakışır)
- [ ] `db.py --seed` ile üç hakemi ekleyin
- [ ] `python emails.py --test` ile üçünün de e-posta aldığını doğrulayın
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
- **Hero videosu**: `assets/hero-loop.mp4` — mavi saatte bir sahil nükleer
  santrali; dört konteynman kubbesi sağda, sol yarı karanlık deniz ve
  gökyüzü (başlık oraya oturuyor). 1280×548, 6,5 sn, 659 KB, sessiz.
  Seedance 2.0 ile 8 sn üretildi, sonra **çapraz geçişle** döngülendi:
  son 1,5 sn ilk 1,5 sn ile harmanlanıyor.

  ⚠ **Ping-pong (ileri + ters) DENENDİ ve BAŞARISIZ oldu** — dosya adı bir
  süre `-pingpong` idi. İki sorunu vardı: dönüş noktasında deniz geriye
  akıyordu, ayrıca döngü dikişi normal kare geçişinin 10,5 katıydı. Çapraz
  geçişte hareket tek yönlü kalıyor ve dikiş 3,2 kata iniyor. Sert kesmeyi
  de ölçtük: 11,6 kat, en kötüsü. Kamera sabitleme (vidstab) denendi,
  yeniden örnekleme gürültüsü eklediği için vazgeçildi.

  Kodlama **crf 21 + gradfun**. Daha yüksek crf denemeyin: crf 30'da karanlık
  gradyanlar bantlaşıyor (SSIM bunu göstermiyor, göz gösteriyor).

  Değiştirirseniz `assets/hero.avif|webp` (masaüstü) ve
  `assets/hero-mobile.avif|webp` (mobil) posterlerini **döngünün ilk
  karesinden** üretin — farklı bir kare kullanılırsa video görünür olduğu an
  zıplama olur. `site/index.html`'deki `width/height` değerlerini de yeni
  en-boy oranına göre güncelleyin.

  Video **mobilde ve hareket azaltma modunda hiç indirilmez**; o durumda
  poster görünür.

- **Hero'da parçacık katmanı YOK.** Bir zamanlar canvas ile çizilen
  "havuz kabarcıkları" vardı; gerçek video gelince kaldırıldı — videonun
  kendi deniz hareketiyle çakışıyordu. Geri eklemeyin.
- **Kapasite metriği**: Yarı iletken bülteninden farklı olarak burada
  `capacity_mwe` bir SAYIDIR (serbest metin değil) — MWe homojen bir birim
  olduğu için `publish.py` haftanın toplam kapasitesini hesaplar ve site
  bunu üst durum şeridinde `Σ … MWe` olarak gösterir.
- Ayar noktaları: hacim `config.py → AYARLAR`, kota `KATEGORILER[...]["kota"]`,
  kaynak `KAYNAK_TIER1/TIER2/TURKIYE`, sorgu `SORGULAR`.

### OpenRouter geçidi

LLM çağrıları OpenRouter'ın **Anthropic-uyumlu** ucundan (`/api/v1/messages`)
geçer; OpenAI formatındaki `/chat/completions` kullanılmaz. İstek gövdesi
(system bloğu, `cache_control`, `output_config.effort`) ve akış olayları
Anthropic şemasında kalır. Modeller değişmedi: triyaj Haiku 4.5, yazım Sonnet 5.

* Model adı org öneki + noktalı sürüm: `anthropic/claude-haiku-4.5`.
  Tarihli kimlikler (`…-20251001`) OpenRouter'da yoktur → 404.
* Sağlayıcı `config.py` → `openrouter_saglayici` ile seçilir. Kurumsal
  hesapta Anthropic'in kendi ucu filtrelenmiş durumda; istekleri Amazon
  Bedrock karşılıyor. `OPENROUTER_SAGLAYICI` ortam değişkeni ezer.
* Bağlantı testi (bülteni etkilemez, ~$0.06):
  `python denemeler/araclar/openrouter_testi.py`
* Kurum ağı TLS'i araya giriyorsa (CERTIFICATE_VERIFY_FAILED):
  `python denemeler/araclar/ca_paketi_olustur.py`
