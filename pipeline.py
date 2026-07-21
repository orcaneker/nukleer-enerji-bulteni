# -*- coding: utf-8 -*-
"""
NÜKLEER ENERJİ BÜLTENİ — TASLAK PIPELINE (CRON 1 — Pazar 12:00 TSİ)
====================================================================
Akış:
  1. Durum (state) yükle       → canlı siteden (Render diski geçici)
  2. Exa ile tara              → 12 sorgu × ek sorgular
  3. Normalize + dedup         → URL temizliği, görülmüş olay elemesi
  4. Aşama 1: triyaj modeli    → olay kümeleme, eleme, puanlama
  5. Aşama 2: yazım modeli     → 14 derin olayın TAMAMI tam haber
                                  (one_cikan + yedek) + radar + brief
  6. Doğrula + görsel bağla    → taslak JSON
  7. Neon'a kaydet (review)    → Resend ile hakemlere davet
  8. Çalışma raporu e-postası

Çalıştırma:
  python pipeline.py                    # tam akış
  python pipeline.py --dry-run          # DB/e-posta yok; taslak_preview.json üretir
  python pipeline.py --mock             # Exa/LLM yok; sahte taslakla DB+davet testi
  python pipeline.py --mock --dry-run   # tamamen çevrimdışı test
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

from config import (
    AYARLAR, KATEGORILER, SORGULAR, OLGUNLUK,
    KAYNAK_TIER1, KAYNAK_TIER2, KAYNAK_AKADEMIK, KAYNAK_TURKIYE, KAYNAK_DISLA,
    KAYNAK_ODEME_DUVARI, ODEME_DUVARI_IZLERI, ODEME_DUVARI_MIN_KARAKTER,
    TEYIT, DURAK_KELIMELER,
)
import prompts
import llm

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
REVIEW_BASE_URL = os.environ.get("REVIEW_BASE_URL", "").rstrip("/")
RAPOR_ALICI = os.environ.get("RAPOR_ALICI", "")

EXA_URL = "https://api.exa.ai/search"
SITE_URL = AYARLAR["site_url"].rstrip("/")

LOG = []
YASAKLI_DOMAINLER = set()   # Exa'nın lisans nedeniyle reddettiği alan adları


def log(msg):
    satir = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(satir, flush=True)
    LOG.append(satir)


llm.set_logger(log)


# ============================================================
# YARDIMCILAR (yarı iletken bülteninden kanıtlanmış)
# ============================================================
IZLEME_PARAMLARI = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source",
    "__twitter_impression", "amp", "s", "spm",
}


def url_normalize(url: str) -> str:
    """UTM/AMP/mobil varyantları temizle → deduplikasyonun temeli."""
    try:
        p = urlparse(url.strip())
        netloc = p.netloc.lower()
        for on_ek in ("www.", "m.", "amp."):
            if netloc.startswith(on_ek):
                netloc = netloc[len(on_ek):]
        path = re.sub(r"/amp/?$", "", p.path).rstrip("/") or "/"
        q = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in IZLEME_PARAMLARI]
        return urlunparse(("https", netloc, path, "", urlencode(q), ""))
    except Exception:
        return url


GORSEL_RED_IZLERI = (
    "/logo", "-logo", "_logo", "logo.", "favicon", "placeholder",
    "og-default", "og_default", "default-image", "1x1", "/pixel",
    "spacer", "amp-logo", "site-logo", "header-logo", "publisher-logo",
)


def gorsel_gecerli(u):
    """Yalnızca KESİN logo/placeholder işaretlerini ele; kararsızsa KORU."""
    if not u or not isinstance(u, str):
        return False
    if not u.lower().startswith("http"):
        return False
    ul = u.lower().split("?")[0]
    if ul.endswith(".svg"):
        return False
    if any(x in ul for x in GORSEL_RED_IZLERI):
        return False
    return True


def gorsel_sec(r):
    """Exa sonucundan gerçek haber görseli çıkar; şüpheliyse None."""
    ex = r.get("extras") or {}
    for u in (ex.get("imageLinks") or []):
        if gorsel_gecerli(u):
            return u
    if gorsel_gecerli(r.get("image")):
        return r["image"]
    return None


def domain_of(url: str) -> str:
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = s.replace("ı", "i").replace("İ", "i").replace("ğ", "g").replace("ş", "s")
    s = s.replace("ö", "o").replace("ü", "u").replace("ç", "c")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:70] or "olay"


def temizle(metin):
    """Kontrol karakterlerini ayıkla — JSON parse hatalarının başlıca sebebi."""
    if not isinstance(metin, str):
        return metin
    metin = metin.replace(chr(160), " ").replace(chr(8203), "")
    return "".join(c for c in metin if c == "\n" or c == "\t" or ord(c) >= 32)


def odeme_duvarli(domain: str, metin: str) -> bool:
    if any(domain.endswith(d) for d in KAYNAK_ODEME_DUVARI):
        return True
    m = (metin or "").lower()
    if any(iz in m for iz in ODEME_DUVARI_IZLERI):
        return True
    if len(metin or "") < ODEME_DUVARI_MIN_KARAKTER:
        return True
    return False


def kaynak_tier(domain: str) -> int:
    if any(domain.endswith(d) for d in KAYNAK_TIER1):
        return 1
    if any(domain.endswith(d) for d in KAYNAK_TIER2 + KAYNAK_TURKIYE):
        return 2
    if any(domain.endswith(d) for d in KAYNAK_AKADEMIK):
        return 2
    return 3


def iso_hafta(d: datetime):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def json_ayikla(metin):
    """Model ```json bloğu veya önsöz eklerse kurtar.

    LLM'ler uzun JSON'da ara sıra kaçışsız tırnak / eksik virgül üretir
    (haber metinlerinde alıntı geçince tipik). Katı parse başarısızsa
    json_repair ile onarılır — bu kütüphane tam bu iş için yazılmıştır.
    """
    metin = temizle(metin).strip()
    metin = re.sub(r"^```(?:json)?\s*", "", metin)
    metin = re.sub(r"\s*```$", "", metin)
    bas, son = metin.find("{"), metin.rfind("}")
    if bas == -1 or son == -1:
        raise ValueError("JSON bulunamadı")
    govde = metin[bas:son + 1]
    try:
        return json.loads(govde)
    except json.JSONDecodeError as e:
        log(f"  ⚠ JSON hatalı ({e}) — json_repair ile onarılıyor")
        from json_repair import repair_json
        onarik = repair_json(govde, return_objects=True)
        if isinstance(onarik, dict) and onarik:
            return onarik
        raise


# ============================================================
# 1) STATE — canlı siteden
# ============================================================
def state_yukle():
    yol = f"{SITE_URL}/data/state/seen_events.json"
    try:
        r = requests.get(yol, timeout=20)
        if r.status_code == 200:
            s = r.json()
            log(f"State yüklendi: {len(s.get('events', []))} olay, "
                f"{len(s.get('urls', []))} URL")
            return s
    except Exception as e:
        log(f"State çekilemedi ({e}) — sıfırdan başlıyor")
    return {"issue_no": 0, "events": [], "urls": []}


# ============================================================
# 2) EXA TARAMA
# ============================================================
def domain_listesi(setler):
    m = {"tier1": KAYNAK_TIER1, "tier2": KAYNAK_TIER2,
         "akademik": KAYNAK_AKADEMIK, "turkiye": KAYNAK_TURKIYE}
    out = []
    for s in setler:
        out += m.get(s, [])
    return [d for d in dict.fromkeys(out) if d not in YASAKLI_DOMAINLER]


def exa_ara(sorgu, dom_dahil, bas_tarih, bit_tarih, sonuc, konum=None, ek_disla=None):
    payload = {
        "query": sorgu,
        "type": AYARLAR["exa_tip"],
        "category": "news",
        "numResults": sonuc,
        "startPublishedDate": bas_tarih,
        "endPublishedDate": bit_tarih,
        "excludeDomains": KAYNAK_DISLA + list(ek_disla or []),
        "contents": {
            "text": {"maxCharacters": AYARLAR["exa_metin_karakter"]},
            "highlights": {"maxCharacters": 1000, "query": sorgu},
            "extras": {"imageLinks": 2},   # görsel için AÇIKÇA istenmeli
        },
    }
    if dom_dahil:
        payload["includeDomains"] = dom_dahil
    if konum:
        payload["userLocation"] = konum

    for deneme in range(3):
        try:
            r = requests.post(
                EXA_URL,
                headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
                json=payload, timeout=60,
            )
            if r.status_code == 200:
                return r.json().get("results", [])

            # 403 "domains are not available" → Exa bazı alan adlarını lisans
            # nedeniyle kabul etmiyor. Ayıkla ve tekrar dene (kendini onarma).
            if r.status_code == 403 and "not available" in r.text:
                yasakli = re.findall(r"([a-z0-9.-]+\.[a-z]{2,})",
                                     r.text.split("not available:")[-1])
                yeni = [d for d in payload.get("includeDomains", []) if d not in yasakli]
                if yasakli and yeni != payload.get("includeDomains"):
                    for d in yasakli:
                        YASAKLI_DOMAINLER.add(d)
                    payload["includeDomains"] = yeni
                    log(f"  Exa yasaklı alan adı ayıklandı: {', '.join(yasakli)}")
                    continue

            log(f"  Exa {r.status_code}: {r.text[:160]}")
        except Exception as e:
            log(f"  Exa hata ({deneme+1}/3): {e}")
        time.sleep(3 * (deneme + 1))
    return []


def tara(pencere_gun):
    """Tüm sorguları çalıştır, ham adayları topla."""
    bugun = datetime.now(timezone.utc)
    bit = bugun.strftime("%Y-%m-%dT23:59:59Z")

    adaylar, hatali_sorgu = [], []
    gorulmus = set()

    for s in SORGULAR:
        gun = s.get("pencere_gun", pencere_gun)
        bas = (bugun - timedelta(days=gun)).strftime("%Y-%m-%dT00:00:00Z")
        doms = domain_listesi(s["domain_seti"])
        tum_sorgular = [s["sorgu"]] + s.get("ek_sorgular", [])

        bulunan = 0
        for q in tum_sorgular:
            sonuclar = exa_ara(
                q, doms, bas, bit,
                s.get("sonuc", AYARLAR["exa_sonuc_sayisi"]),
                s.get("kullanici_konumu"),
            )
            if not sonuclar:
                hatali_sorgu.append(f"{s['id']} :: {q[:40]}")
            for r in sonuclar:
                url = url_normalize(r.get("url", ""))
                if not url or url in gorulmus:
                    continue
                gorulmus.add(url)
                tam = temizle(r.get("text") or "")
                one = " … ".join(r.get("highlights") or [])
                adaylar.append({
                    "id": f"c{len(adaylar):04d}",
                    "title": temizle(r.get("title") or "")[:220],
                    "url": url,
                    "domain": domain_of(url),
                    "max_yas_gun": gun,   # bu sorgunun izin verdiği azami yaş (TR: 21)
                    "published_date": (r.get("publishedDate") or "")[:10] or None,
                    "author": r.get("author"),
                    "image": gorsel_sec(r),
                    "snippet": (temizle(one) or tam)[:AYARLAR["exa_triyaj_karakter"]],
                    "text": tam[:AYARLAR["exa_metin_karakter"]],
                    "paywall": odeme_duvarli(domain_of(url), tam),
                    "sorgu_id": s["id"],
                    "kategori_ipucu": s["kategori"],
                })
                bulunan += 1
        log(f"  {s['id']:<14} → {bulunan} sonuç")

    return adaylar, hatali_sorgu


# ============================================================
# 2.5) TEYİT ARAMASI — duvarlı olaya erişilebilir kaynak bul
# ============================================================
def _kelimeler(baslik):
    t = (baslik or "").lower()
    t = re.sub(r"[^a-z0-9çğıöşü\s]", " ", t)
    return {k for k in t.split() if len(k) >= 4 and k not in DURAK_KELIMELER}


def benzerlik(a, b):
    A, B = _kelimeler(a), _kelimeler(b)
    if not A or not B:
        return 0.0, 0
    ortak = A & B
    return len(ortak) / len(A | B), len(ortak)


def teyit_ara(olaylar, adaylar):
    """Tüm kaynakları duvarlı olan olaylar için erişilebilir kaynak ara.
    Bulunursa olay yazılabilir hale gelir ama 'ikinci_el' işaretlenir."""
    if not TEYIT.get("aktif"):
        return 0

    hedefler = [o for o in olaylar if o.get("sadece_radar")][:TEYIT["max_olay"]]
    if not hedefler:
        return 0

    log(f"Teyit araması — {len(hedefler)} duvarlı olay")
    bulunan = 0
    mevcut_urller = {a["url"] for a in adaylar}

    for o in hedefler:
        k0 = o["kaynaklar"][0]
        baslik = o.get("baslik_ozet") or k0["name"]

        try:
            d0 = datetime.strptime(k0.get("published_date") or "", "%Y-%m-%d")
        except Exception:
            d0 = datetime.now(timezone.utc).replace(tzinfo=None)
        tol = TEYIT["gun_toleransi"]
        bas = (d0 - timedelta(days=tol)).strftime("%Y-%m-%dT00:00:00Z")
        bit = (d0 + timedelta(days=tol)).strftime("%Y-%m-%dT23:59:59Z")

        sonuclar = exa_ara(baslik, None, bas, bit, TEYIT["sonuc"],
                           ek_disla=KAYNAK_ODEME_DUVARI)

        en_iyi, en_iyi_skor = None, 0.0
        for r in sonuclar:
            url = url_normalize(r.get("url", ""))
            metin = temizle(r.get("text") or "")
            if not url or len(metin) < TEYIT["min_metin"]:
                continue
            if odeme_duvarli(domain_of(url), metin):
                continue
            skor, ortak = benzerlik(baslik, r.get("title") or "")
            if skor < TEYIT["min_benzerlik"] or ortak < TEYIT["min_ortak_kelime"]:
                continue
            if skor > en_iyi_skor:
                en_iyi, en_iyi_skor = (r, url, metin), skor

        if not en_iyi:
            continue

        r, url, metin = en_iyi
        yeni = {
            "name": domain_of(url), "domain": domain_of(url), "url": url,
            "published_date": (r.get("publishedDate") or "")[:10] or None,
            "text": metin[:AYARLAR["exa_metin_karakter"]],
            "image": gorsel_sec(r),
            "tier": kaynak_tier(domain_of(url)),
            "paywall": False, "primary": True,
        }
        for k in o["kaynaklar"]:
            k["primary"] = False
        o["kaynaklar"].insert(0, yeni)
        o["sadece_radar"] = False
        o["ikinci_el"] = True
        bulunan += 1
        if url not in mevcut_urller:
            adaylar.append({
                "id": f"t{len(adaylar):04d}", "title": r.get("title") or "",
                "url": url, "domain": domain_of(url),
                "published_date": yeni["published_date"], "image": gorsel_sec(r),
                "snippet": metin[:AYARLAR["exa_triyaj_karakter"]], "text": yeni["text"],
                "paywall": False, "tier": yeni["tier"],
            })
        log(f"  ✓ teyit ({en_iyi_skor:.2f}): {domain_of(url)} ← {baslik[:50]}")

    log(f"Teyit: {bulunan}/{len(hedefler)} olay kurtarıldı")
    return bulunan


# ============================================================
# 3) DETERMİNİSTİK ELEME
# ============================================================
def on_eleme(adaylar, state):
    """Görülmüş URL + başlık tekrarı + TARİH DİSİPLİNİ.

    ⚠ Tarih filtresi DETERMİNİSTİKTİR ve LLM'e bırakılmaz: Exa'nın tarih
    parametreleri bazen eski/tarihsiz sonuç sızdırıyor (2025'ten kalma
    haberler görüldü). Yayın tarihi olmayan veya sorgusunun penceresinden
    (standart 7, Türkiye 21 gün) yaşlı her aday burada, LLM'e hiç
    gitmeden elenir. Haftalık bültenin tarih güvencesi bu satırlardır.
    """
    gorulmus_url = set(state.get("urls", []))
    bugun = datetime.now(timezone.utc).date()
    kalan, elenen, tarih_elenen = [], 0, 0
    baslik_hash = set()

    for a in adaylar:
        pd = a.get("published_date")
        if not pd:
            tarih_elenen += 1          # tarihi doğrulanamayan aday bültene giremez
            continue
        try:
            yas = (bugun - datetime.strptime(pd, "%Y-%m-%d").date()).days
        except ValueError:
            tarih_elenen += 1
            continue
        # +1 gün tolerans: saat dilimi farkları; negatif alt sınır: "gelecek
        # tarihli" bozuk veriyi de ele
        if yas > a.get("max_yas_gun", AYARLAR["pencere_gun"]) + 1 or yas < -1:
            tarih_elenen += 1
            continue
        if a["url"] in gorulmus_url:
            elenen += 1
            continue
        h = hashlib.md5(slugify(a["title"])[:50].encode()).hexdigest()
        if h in baslik_hash:
            elenen += 1
            continue
        baslik_hash.add(h)
        a["tier"] = kaynak_tier(a["domain"])
        kalan.append(a)

    log(f"Deterministik eleme: tarih dışı {tarih_elenen} + tekrar {elenen} elendi, "
        f"{len(kalan)} kaldı")
    return kalan, elenen + tarih_elenen


# ============================================================
# 4) AŞAMA 1 — TRİYAJ
# ============================================================
def triyaj(adaylar, bas, bit, state):
    onceki = [e.get("baslik_ozet", "") for e in state.get("events", [])]
    olaylar, reject = [], []
    B = AYARLAR["triyaj_batch"]

    # Sistem bloğu her partide AYNI → cache'lenir (Anthropic tarafında).
    sistem = prompts.TRIYAJ_PROMPT + prompts.onceki_olaylar_bloku(onceki)

    for i in range(0, len(adaylar), B):
        parti = adaylar[i:i + B]
        log(f"  Triyaj partisi {i//B + 1} ({len(parti)} aday)")
        try:
            cikti = llm.llm_cagri(
                AYARLAR["model_triyaj"], sistem,
                prompts.triyaj_kullanici_mesaji(parti, bas, bit),
                AYARLAR["max_tokens_triyaj"],
                cache=True,
            )
            d = json_ayikla(cikti)
            olaylar += d.get("events", [])
            reject += d.get("reject", [])
        except Exception as e:
            log(f"  ! Triyaj partisi başarısız: {e}")

    # Aynı event_key birden fazla partide çıkabilir → birleştir
    birlesik = {}
    for o in olaylar:
        k = o.get("event_key") or slugify(o.get("baslik_ozet", ""))
        if k in birlesik:
            birlesik[k]["supporting_ids"] = list(dict.fromkeys(
                birlesik[k].get("supporting_ids", []) + o.get("supporting_ids", [])
            ))
            birlesik[k]["puan"] = max(birlesik[k].get("puan", 0), o.get("puan", 0))
        else:
            o["event_key"] = k
            birlesik[k] = o

    sonuc = sorted(birlesik.values(), key=lambda x: x.get("puan", 0), reverse=True)
    log(f"Triyaj: {len(sonuc)} olay, {len(reject)} reddedildi")
    return sonuc, reject


def olaylari_zenginlestir(olaylar, adaylar):
    """Olaylara kaynak metinlerini bağla + birincil kaynak onarımı.
    Tüm kaynaklar duvarlıysa 'sadece_radar' işaretlenir."""
    idx = {a["id"]: a for a in adaylar}
    zengin, degistirilen, radara_dusen = [], 0, 0

    for o in olaylar:
        pid = o.get("primary_id")
        ids = list(dict.fromkeys(([pid] if pid else []) + (o.get("supporting_ids") or [])))
        kaynaklar = []
        for aid in ids:
            a = idx.get(aid)
            if not a:
                continue
            kaynaklar.append({
                "name": a["domain"], "domain": a["domain"], "url": a["url"],
                "published_date": a["published_date"],
                "text": a.get("text") or a["snippet"],
                "image": a.get("image"), "tier": a["tier"],
                "paywall": a.get("paywall", False), "primary": False,
            })
        if not kaynaklar:
            continue

        acik = [k for k in kaynaklar if not k["paywall"]]
        if acik:
            en_iyi = min(acik, key=lambda k: (k["tier"], -len(k.get("text") or "")))
            if kaynaklar[0] is not en_iyi:
                degistirilen += 1
            kaynaklar.remove(en_iyi)
            kaynaklar.insert(0, en_iyi)
            kaynaklar[0]["primary"] = True
            o["sadece_radar"] = False
        else:
            kaynaklar[0]["primary"] = True
            o["sadece_radar"] = True
            radara_dusen += 1

        o["kaynaklar"] = kaynaklar
        zengin.append(o)

    log(f"Birincil kaynak onarıldı: {degistirilen} olay · "
        f"Sadece-radar (tüm kaynaklar duvarlı): {radara_dusen} olay")
    return zengin


# ============================================================
# 5) AŞAMA 2 — YAZIM
# ============================================================
def yaz(derin, radar_havuz, sayi_no, bas, bit, pencere):
    """json_repair'e rağmen geçersiz çıktı gelirse yazımı BİR kez daha dene —
    haftalık cron tek bozuk üretim yüzünden boş geçmesin."""
    son_hata = None
    for deneme in range(2):
        if deneme:
            log("  ⚠ Yazım çıktısı kurtarılamadı — yazım yeniden deneniyor (2/2)")
        try:
            cikti = llm.llm_cagri(
                AYARLAR["model_yazim"], prompts.YAZIM_PROMPT,
                prompts.yazim_kullanici_mesaji(derin, radar_havuz, sayi_no, bas, bit, pencere),
                AYARLAR["max_tokens_yazim"],
                stream=True,     # uzun çıktı — zaman aşımını önler
            )
            return json_ayikla(cikti)
        except (ValueError, json.JSONDecodeError) as e:
            son_hata = e
    raise son_hata


# ============================================================
# 6) DOĞRULAMA — taslak düzeyinde
# ============================================================
ESLESME = {
    # Model bazen değer zinciri etiketini kategori sanıyor — sessizce onar.
    "uranyum": "yakit", "donusum-zenginlestirme": "yakit", "yakit-uretim": "yakit",
    "reaktor-insa": "buyuk-reaktor", "uygulama": "teknoloji",
    "duzenleme": "politika", "jeopolitik": "politika", "mevzuat": "politika",
    "piyasa": "rapor", "akademik": "teknoloji", "arastirma": "teknoloji",
    "veri-merkezi": "kurumsal-alim", "ppa": "kurumsal-alim",
    "atik": "atik-sokum", "sokum": "atik-sokum",
}


def dogrula_taslak(b):
    """Şema doğrulama + slug üretimi. Metrikler yayında (nihai seçim
    üzerinden) hesaplanır — burada değil."""
    hatalar = []
    stories = b.get("stories") or []
    if len(stories) < 8:
        hatalar.append(f"stories az ({len(stories)})")
    if len(b.get("brief") or []) != 5:
        hatalar.append("brief 5 madde değil")
    if not b.get("lead_id"):
        # manşet belirtilmemişse en yüksek puanlı one_cikan haberi seç
        secili = [s for s in stories if s.get("secim") == "one_cikan"] or stories
        if secili:
            b["lead_id"] = max(secili, key=lambda s: s.get("score") or 0).get("id")
            hatalar.append("lead_id yoktu — puanla seçildi")

    # --- slug üretimi (benzersiz) ---
    gorulen = set()
    for st in stories:
        sl = slugify(st.get("title", ""))
        temel, i = sl, 2
        while sl in gorulen:
            sl = f"{temel}-{i}"
            i += 1
        gorulen.add(sl)
        st["slug"] = sl
        st["neden_onemli"] = None          # analiz katmanı şimdilik kapalı
        if st.get("secim") not in ("one_cikan", "yedek"):
            st["secim"] = "yedek"
            hatalar.append(f"'{(st.get('title') or '?')[:30]}' → secim onarıldı")

    # --- alan kontrolü + kategori onarımı ---
    for st in stories:
        for alan in ("title", "excerpt", "detail", "category", "source"):
            if not st.get(alan):
                hatalar.append(f"'{(st.get('title') or '?')[:30]}' → {alan} eksik")
        c = st.get("category")
        if c not in KATEGORILER:
            yeni_c = ESLESME.get(c)
            if not yeni_c:
                vc = (st.get("value_chain") or [None])[0]
                yeni_c = ESLESME.get(vc, "rapor")
            st["category"] = yeni_c
            hatalar.append(f"kategori onarıldı: '{c}' → '{yeni_c}'")
        m = st.get("maturity")
        if m and m not in OLGUNLUK:
            st["maturity"] = None
            hatalar.append(f"olgunluk onarıldı: '{m}' → null")

    # --- manşetin one_cikan olduğundan emin ol ---
    lead = next((s for s in stories if s.get("id") == b.get("lead_id")), None)
    if lead and lead.get("secim") != "one_cikan":
        lead["secim"] = "one_cikan"

    # --- öne çıkan sayısını 8-10 aralığına çek ---
    secili = [s for s in stories if s.get("secim") == "one_cikan"]
    if len(secili) > AYARLAR["one_cikan_max"]:
        fazla = sorted((s for s in secili if s.get("id") != b.get("lead_id")),
                       key=lambda s: s.get("score") or 0)
        for s in fazla[:len(secili) - AYARLAR["one_cikan_max"]]:
            s["secim"] = "yedek"
            hatalar.append(f"öne çıkan fazlaydı → yedeğe: {s.get('slug')}")
    elif len(secili) < AYARLAR["one_cikan_min"]:
        yedekler = sorted((s for s in stories if s.get("secim") == "yedek"),
                          key=lambda s: -(s.get("score") or 0))
        for s in yedekler[:AYARLAR["one_cikan_min"] - len(secili)]:
            s["secim"] = "one_cikan"
            hatalar.append(f"öne çıkan azdı → seçildi: {s.get('slug')}")

    # --- brief: metin + ref (id) — slug çevirisi yayında yapılır ---
    yeni_brief = []
    for m in (b.get("brief") or []):
        if isinstance(m, str):
            yeni_brief.append({"text": m, "ref": None})
        else:
            yeni_brief.append({"text": m.get("text", ""), "ref": m.get("ref")})
    b["brief"] = yeni_brief
    return hatalar


# ============================================================
# 6.5) GÖRSEL BAĞLAMA
# ============================================================
def og_gorsel_cek(url):
    """Son çare: makalenin OG görselini HTML'den çek."""
    try:
        r = requests.get(url, timeout=12, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BultenBot/1.0)"})
        if r.status_code != 200:
            return None
        html = r.text[:120000]
        for kalip in (
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        ):
            m = re.search(kalip, html, re.I)
            if m and gorsel_gecerli(m.group(1)):
                return m.group(1)
    except Exception:
        pass
    return None


def gorselleri_bagla(taslak, adaylar, olaylar=None):
    """TÜM haberlere (yedekler dahil) görsel bağla — takas sonrası da görsel olsun."""
    idx = {}
    for a in adaylar:
        if a.get("image"):
            idx[a["url"]] = {"url": a["image"], "credit": a["domain"], "type": "og"}

    olay_gorsel = {}
    for o in (olaylar or []):
        g = next((k.get("image") for k in o.get("kaynaklar", []) if k.get("image")), None)
        if g:
            for k in o.get("kaynaklar", []):
                olay_gorsel[url_normalize(k["url"])] = {
                    "url": g, "credit": k["domain"], "type": "og"}

    stories = taslak.get("stories") or []
    bagli, kaynaksiz = 0, 0
    for st in stories:
        urller = [(st.get("source") or {}).get("url")]
        urller += [k.get("url") for k in (st.get("supporting_sources") or [])]
        urller = [url_normalize(u) for u in urller if u]

        g = next((idx[u] for u in urller if u in idx), None) \
            or next((olay_gorsel[u] for u in urller if u in olay_gorsel), None)
        if g:
            st["image"] = g
            bagli += 1
        else:
            st["image"] = {"url": None, "credit": None, "type": None}
            kaynaksiz += 1

    # Son çare: görselsiz ÖNE ÇIKAN haberler için OG etiketi çek (≤6 istek)
    cekilen = 0
    for st in stories:
        if st.get("secim") != "one_cikan" or (st.get("image") or {}).get("url") or cekilen >= 6:
            continue
        u = (st.get("source") or {}).get("url")
        og = og_gorsel_cek(u) if u else None
        if og:
            st["image"] = {"url": og, "credit": (st.get("source") or {}).get("name"),
                           "type": "og-fetch"}
            bagli += 1; kaynaksiz -= 1; cekilen += 1

    log(f"Görsel bağlandı: {bagli} haber (OG çekilen: {cekilen}) · görselsiz: {kaynaksiz}")
    return bagli


# ============================================================
# MOCK — API'siz test taslağı
# ============================================================
def mock_taslak(sayi_no, bas, bit, pencere):
    def st(i, secim, kat, baslik):
        return {
            "id": f"event_{i:03d}", "secim": secim,
            "title": baslik,
            "excerpt": f"Örnek özet {i}: anlaşma 2,4 milyar dolar değerinde, "
                       f"kapasite 470 MWe. Bu bir test metnidir, gerçek haber değildir.",
            "detail": ("Bu bir TEST haberidir; gerçek bir gelişmeyi yansıtmaz.\n\n"
                       "İkinci paragraf: proje kapsamında 470 MWe kapasiteli iki "
                       "reaktör planlanıyor, toplam yatırım 2,4 milyar dolar.\n\n"
                       "Üçüncü paragraf: takvim paylaşılmadı."),
            "neden_onemli": None, "category": kat, "subcategories": [],
            "value_chain": ["reaktor-insa"], "maturity": "announced",
            "companies": ["Örnek A.Ş."], "countries": ["USA"],
            "technologies": ["PWR"], "capacity_mwe": 470,
            "investment": {"amount_original": 2.4, "currency": "USD",
                           "amount_usd_million": 2400,
                           "public_support_usd_million": None},
            "published_date": bit, "event_date": bit,
            "source": {"name": "example.org", "url": f"https://example.org/haber-{i}",
                       "type": "trade_press", "tier": 2, "primary": True},
            "supporting_sources": [],
            "image": {"url": None, "credit": None, "type": None},
            "score": 9 - (i % 5),
        }

    katlar = ["politika", "smr", "buyuk-reaktor", "yakit", "isletme",
              "kurumsal-alim", "teknoloji", "turkiye", "rapor"]
    stories = [st(i + 1, "one_cikan", katlar[i % len(katlar)],
                  f"[TEST] Öne çıkan haber {i+1}: örnek nükleer gelişme")
               for i in range(9)]
    stories += [st(i + 10, "yedek", katlar[i % len(katlar)],
                   f"[TEST] Yedek haber {i+10}: takas için bekleyen gelişme")
                for i in range(5)]
    return {
        "brief": [{"text": f"[TEST] 60 saniyede madde {i+1} — örnek gelişme özeti.",
                   "ref": stories[i]["id"] if i < 3 else None} for i in range(5)],
        "lead_id": "event_001",
        "stories": stories,
        "radar": [
            {"kume": "Uranyum tedariki",
             "maddeler": [{"title": f"[TEST] Radar maddesi {i+1}",
                           "source": "WNN", "url": f"https://example.org/radar-{i}",
                           "date": bit, "category": "yakit"} for i in range(4)]},
            {"kume": "SMR lisanslama",
             "maddeler": [{"title": f"[TEST] Radar maddesi {i+5}",
                           "source": "NucNet", "url": f"https://example.org/radar-{i+4}",
                           "date": bit, "category": "smr"} for i in range(4)]},
        ],
    }


# ============================================================
# ANA AKIŞ
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="DB ve e-posta yok; taslak_preview.json üretir")
    ap.add_argument("--mock", action="store_true",
                    help="Exa/LLM yok; sahte taslak üretir")
    args = ap.parse_args()

    if not args.mock and (not EXA_API_KEY or not os.environ.get("ANTHROPIC_API_KEY",
                          os.environ.get("OPENAI_API_KEY"))):
        sys.exit("HATA: EXA_API_KEY ve LLM anahtarı gerekli (veya --mock kullanın)")

    t0 = time.time()
    bugun = datetime.now(timezone.utc)
    log("═" * 46)
    log(f"NÜKLEER ENERJİ BÜLTENİ — TASLAK — {bugun.strftime('%Y-%m-%d')}")

    state = state_yukle()
    sayi_no = AYARLAR.get("sayi_no_sabit") or (state.get("issue_no", 0) + 1)
    hafta = iso_hafta(bugun)
    pencere = AYARLAR["pencere_gun"]
    kapsam_bas = (bugun - timedelta(days=pencere)).strftime("%Y-%m-%d")
    kapsam_bit = bugun.strftime("%Y-%m-%d")

    rapor = {"queries_run": 0, "results_found": 0, "dedup_removed": 0,
             "events_created": 0, "llm_rejected": 0, "written": 0,
             "radar_items": 0, "failed_queries": []}

    if args.mock:
        log("MOCK modu — Exa/LLM atlanıyor")
        b = mock_taslak(sayi_no, kapsam_bas, kapsam_bit, pencere)
        adaylar, olaylar = [], []
    else:
        # --- Tarama (7 gün → yetersizse 14 gün) ---
        log(f"Exa taraması ({pencere} gün)…")
        adaylar, hatali = tara(pencere)
        log(f"Ham sonuç: {len(adaylar)}")

        if len(adaylar) < 40:
            pencere = AYARLAR["pencere_genis_gun"]
            kapsam_bas = (bugun - timedelta(days=pencere)).strftime("%Y-%m-%d")
            log(f"Yetersiz — pencere {pencere} güne genişletiliyor")
            adaylar, hatali = tara(pencere)
            log(f"Ham sonuç: {len(adaylar)}")

        rapor["queries_run"] = sum(1 + len(s.get("ek_sorgular", [])) for s in SORGULAR)
        rapor["results_found"] = len(adaylar)
        rapor["failed_queries"] = hatali

        adaylar, elenen = on_eleme(adaylar, state)
        rapor["dedup_removed"] = elenen
        if not adaylar:
            sys.exit("HATA: eleme sonrası aday kalmadı")

        # --- Aşama 1: triyaj ---
        log("Aşama 1 — triyaj…")
        olaylar, reject = triyaj(adaylar, kapsam_bas, kapsam_bit, state)
        olaylar = olaylari_zenginlestir(olaylar, adaylar)
        teyit_ara(olaylar, adaylar)
        rapor["events_created"] = len(olaylar)
        rapor["llm_rejected"] = len(reject)

        # En yüksek puanlı D olay TAM METİNLE gider — HEPSİ haber yazılır.
        D = AYARLAR["derin_olay_sayisi"]
        T = AYARLAR["toplam_olay_sayisi"]
        yazilabilir = [o for o in olaylar if not o.get("sadece_radar")]
        duvarlilar = [o for o in olaylar if o.get("sadece_radar")]
        derin = yazilabilir[:D]
        radar_havuz = (yazilabilir[D:] + duvarlilar)[:T - D]
        log(f"Yazıma giden: {len(derin)} derin (tam metin) + {len(radar_havuz)} radar adayı")

        # --- Aşama 2: yazım ---
        log("Aşama 2 — yazım…")
        b = yaz(derin, radar_havuz, sayi_no, kapsam_bas, kapsam_bit, pencere)

    hatalar = dogrula_taslak(b)
    if hatalar:
        log(f"⚠ {len(hatalar)} şema uyarısı")
        for h in hatalar[:10]:
            log(f"  ! {h}")

    gorselleri_bagla(b, adaylar, olaylar)

    stories = b.get("stories") or []
    rapor["written"] = len(stories)
    rapor["radar_items"] = sum(len(k.get("maddeler", [])) for k in b.get("radar", []))

    taslak = {
        "issue": {
            "number": sayi_no,
            "hafta": hafta,
            "draft_date": bugun.strftime("%Y-%m-%d"),
            "coverage_start": kapsam_bas,
            "coverage_end": kapsam_bit,
            "window_days": pencere,
        },
        "brief": b.get("brief", []),
        "lead_id": b.get("lead_id"),
        "stories": stories,
        "radar": b.get("radar", []),
        "hatalar": hatalar,
    }

    mm, mt = llm.maliyet_raporu()
    rapor["maliyet_usd"] = round(mt, 3)

    lead = next((s for s in stories if s.get("id") == taslak["lead_id"]),
                stories[0] if stories else {})
    secili_sayi = sum(1 for s in stories if s.get("secim") == "one_cikan")

    if args.dry_run:
        with open("taslak_preview.json", "w", encoding="utf-8") as f:
            json.dump(taslak, f, ensure_ascii=False, indent=2)
        log("DRY RUN — DB/e-posta atlandı → taslak_preview.json yazıldı")
    else:
        import db
        import emails
        issue_id = db.taslak_kaydet(hafta, sayi_no, taslak, rapor)
        db.logla(issue_id, None, "taslak_olusturuldu",
                 {"stories": len(stories), "secili": secili_sayi})
        log(f"Taslak Neon'a kaydedildi (issue_id={issue_id})")

        # --- Hakemlere davet ---
        gonderilen = 0
        for h in db.hakemler():
            link = f"{REVIEW_BASE_URL}/r/{h['token']}" if REVIEW_BASE_URL else "(REVIEW_BASE_URL yok)"
            if emails.davet_gonder(h, link, sayi_no, hafta,
                                   lead.get("title", "?"), secili_sayi):
                gonderilen += 1
        log(f"Davet e-postası: {gonderilen} hakeme gönderildi")

        # --- Çalışma raporu ---
        if RAPOR_ALICI:
            govde = (
                f"Nükleer Enerji Bülteni — Sayı {sayi_no} Taslak Raporu\n"
                f"{'=' * 52}\n"
                f"Kapsam        : {kapsam_bas} — {kapsam_bit} ({pencere} gün)\n\n"
                f"Sorgu çalıştırıldı : {rapor['queries_run']}\n"
                f"Ham sonuç          : {rapor['results_found']}\n"
                f"Deterministik elenen: {rapor['dedup_removed']}\n"
                f"Olay oluşturuldu   : {rapor['events_created']}\n"
                f"LLM reddetti       : {rapor['llm_rejected']}\n"
                f"Yazılan haber      : {rapor['written']} ({secili_sayi} öne çıkan + "
                f"{rapor['written'] - secili_sayi} yedek)\n"
                f"Radar maddesi      : {rapor['radar_items']}\n\n"
                f"Exa'nın reddettiği alan adları: "
                f"{', '.join(sorted(YASAKLI_DOMAINLER)) or '(yok)'}\n\n"
                f"Başarısız sorgular : {len(rapor['failed_queries'])}\n"
                + "".join(f"  - {q}\n" for q in rapor["failed_queries"]) +
                f"\nŞema uyarıları     : {len(hatalar)}\n"
                + "".join(f"  ! {h}\n" for h in hatalar[:15]) +
                f"\nTOKEN VE MALİYET\n{mm}\n\n"
                f"Durum: İNCELEME BEKLİYOR — davet {gonderilen} hakeme gitti.\n"
                f"{'=' * 52}\nLOG:\n" + "\n".join(LOG[-40:])
            )
            emails.rapor_gonder(RAPOR_ALICI,
                                f"Nükleer Bülten — Sayı {sayi_no} taslak hazır", govde)

    log("TOKEN VE MALİYET")
    for satir in mm.split("\n"):
        log(satir)
    log(f"Tamamlandı — {time.time() - t0:.0f} sn · tahmini maliyet ${mt:.3f}")
    log("═" * 46)


if __name__ == "__main__":
    main()
