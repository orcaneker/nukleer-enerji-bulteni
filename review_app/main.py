# -*- coding: utf-8 -*-
"""
NÜKLEER ENERJİ BÜLTENİ — İNCELEME SERVİSİ (Render Web Service)
===============================================================
Hakem, davet e-postasındaki kişisel linkle gelir:

    GET  /r/{token}                → inceleme arayüzü (HTML kabuk)
    GET  /api/{token}/draft        → taslak JSON + durum
    POST /api/{token}/swap         → {out_id, in_id} öne çıkan ↔ yedek takası
    POST /api/{token}/remove       → {id} haberi yedeğe indir (yerine koymadan)
    POST /api/{token}/lead         → {id} manşeti değiştir
    POST /api/{token}/radar-remove → {kume, url} radar maddesi çıkar
    POST /api/{token}/approve      → TEK onay yeterli → status=approved
                                     yayın saati geçtiyse ANINDA yayınla

Yerel çalıştırma:
    uvicorn review_app.main:app --reload --port 8000
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

# repo kökünü import yoluna ekle (uvicorn review_app.main:app kökten çalışır)
KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

import db                                      # noqa: E402
from config import AYARLAR, KATEGORILER        # noqa: E402

app = FastAPI(title="Nükleer Enerji Bülteni — İnceleme", docs_url=None, redoc_url=None)

SABLON = (Path(__file__).parent / "templates" / "review.html").read_text(encoding="utf-8")


def _hakem(token):
    h = db.hakem_token_ile(token)
    if not h:
        raise HTTPException(404, "Geçersiz veya pasif inceleme linki")
    return h


def _aktif_sayi():
    """İncelenecek sayı: önce review, yoksa approved (salt-okunur gösterim)."""
    sayi = db.issue_getir(status="review") or db.issue_getir(status="approved")
    if not sayi:
        raise HTTPException(404, "İncelenecek taslak yok")
    if isinstance(sayi["draft_json"], str):
        sayi["draft_json"] = json.loads(sayi["draft_json"])
    return sayi


def yayin_esigi(created_at):
    """Taslağın yayın anı: oluşturulmasını izleyen Pazartesi 08:00 TSİ
    (= 05:00 UTC). Taslak Pazar günü üretilir → ertesi gün."""
    d = created_at.astimezone(timezone.utc)
    gunler_kalan = (7 - d.weekday()) % 7 or 7      # bir SONRAKİ pazartesi
    pazartesi = (d + timedelta(days=gunler_kalan)).replace(
        hour=5, minute=0, second=0, microsecond=0)
    return pazartesi


@app.get("/")
def saglik():
    return {"servis": "nukleer-bulten-inceleme", "durum": "ok"}


@app.get("/r/{token}", response_class=HTMLResponse)
def inceleme_sayfasi(token: str):
    _hakem(token)   # geçersiz token'a HTML bile verme
    return SABLON.replace("__TOKEN__", token)


@app.get("/api/{token}/draft")
def taslak_getir(token: str):
    h = _hakem(token)
    sayi = _aktif_sayi()
    db.logla(sayi["id"], h["ad"], "goruntuledi")
    esik = yayin_esigi(sayi["created_at"])
    return {
        "hakem": h["ad"],
        "status": sayi["status"],
        "sayi_no": sayi["sayi_no"],
        "hafta": sayi["hafta"],
        "approved_by": sayi.get("approved_by"),
        "yayin_aninda": datetime.now(timezone.utc) >= esik,
        "yayin_esigi_utc": esik.isoformat(),
        "kategoriler": {k: v["ad"] for k, v in KATEGORILER.items()},
        "taslak": sayi["draft_json"],
    }


def _duzenlenebilir():
    sayi = _aktif_sayi()
    if sayi["status"] != "review":
        raise HTTPException(409, "Bu sayı onaylanmış — düzenlenemez")
    return sayi


@app.post("/api/{token}/swap")
async def takas(token: str, req: Request):
    h = _hakem(token)
    sayi = _duzenlenebilir()
    veri = await req.json()
    out_id, in_id = veri.get("out_id"), veri.get("in_id")

    taslak = sayi["draft_json"]
    stories = {s["id"]: s for s in taslak.get("stories", [])}
    cikan, giren = stories.get(out_id), stories.get(in_id)
    if not cikan or not giren:
        raise HTTPException(400, "Haber bulunamadı")
    if cikan.get("secim") != "one_cikan" or giren.get("secim") != "yedek":
        raise HTTPException(400, "Takas yönü geçersiz (öne çıkan ↔ yedek)")

    cikan["secim"], giren["secim"] = "yedek", "one_cikan"

    # çıkan haber manşetse: manşeti girene devret
    if taslak.get("lead_id") == out_id:
        taslak["lead_id"] = in_id
    # brief çıkan habere işaret ediyorsa ref'i kopar (metin kalır)
    for m in taslak.get("brief", []):
        if m.get("ref") == out_id:
            m["ref"] = None

    db.taslak_guncelle(sayi["id"], taslak)
    db.logla(sayi["id"], h["ad"], "takas", {"cikan": out_id, "giren": in_id})
    return {"ok": True}


@app.post("/api/{token}/remove")
async def cikar(token: str, req: Request):
    """Haberi yerine koymadan yedeğe indir (min sayının altına inilmez)."""
    h = _hakem(token)
    sayi = _duzenlenebilir()
    veri = await req.json()
    hid = veri.get("id")

    taslak = sayi["draft_json"]
    stories = taslak.get("stories", [])
    st = next((s for s in stories if s["id"] == hid), None)
    if not st or st.get("secim") != "one_cikan":
        raise HTTPException(400, "Haber bulunamadı veya zaten yedekte")
    secili = [s for s in stories if s.get("secim") == "one_cikan"]
    if len(secili) <= AYARLAR["one_cikan_min"]:
        raise HTTPException(400,
            f"En az {AYARLAR['one_cikan_min']} haber kalmalı — "
            f"çıkarmak yerine yedekle takas yapın")
    if taslak.get("lead_id") == hid:
        raise HTTPException(400, "Manşet çıkarılamaz — önce başka manşet seçin")

    st["secim"] = "yedek"
    for m in taslak.get("brief", []):
        if m.get("ref") == hid:
            m["ref"] = None

    db.taslak_guncelle(sayi["id"], taslak)
    db.logla(sayi["id"], h["ad"], "cikar", {"id": hid})
    return {"ok": True}


@app.post("/api/{token}/lead")
async def manset(token: str, req: Request):
    h = _hakem(token)
    sayi = _duzenlenebilir()
    veri = await req.json()
    hid = veri.get("id")

    taslak = sayi["draft_json"]
    st = next((s for s in taslak.get("stories", []) if s["id"] == hid), None)
    if not st:
        raise HTTPException(400, "Haber bulunamadı")
    st["secim"] = "one_cikan"
    taslak["lead_id"] = hid

    db.taslak_guncelle(sayi["id"], taslak)
    db.logla(sayi["id"], h["ad"], "manset", {"id": hid})
    return {"ok": True}


@app.post("/api/{token}/radar-remove")
async def radar_cikar(token: str, req: Request):
    h = _hakem(token)
    sayi = _duzenlenebilir()
    veri = await req.json()
    kume, url = veri.get("kume"), veri.get("url")

    taslak = sayi["draft_json"]
    for k in taslak.get("radar", []):
        if k.get("kume") == kume:
            once = len(k.get("maddeler", []))
            k["maddeler"] = [m for m in k.get("maddeler", []) if m.get("url") != url]
            if len(k["maddeler"]) == once:
                raise HTTPException(400, "Radar maddesi bulunamadı")
            break
    else:
        raise HTTPException(400, "Küme bulunamadı")
    taslak["radar"] = [k for k in taslak["radar"] if k.get("maddeler")]

    db.taslak_guncelle(sayi["id"], taslak)
    db.logla(sayi["id"], h["ad"], "radar_cikar", {"kume": kume, "url": url})
    return {"ok": True}


@app.post("/api/{token}/approve")
async def onayla(token: str):
    """TEK onay yeterli. Yayın eşiği (Pazartesi 08:00 TSİ) geçtiyse
    bekletmeden ANINDA yayınla; geçmediyse Cron 2 yayınlar."""
    h = _hakem(token)
    sayi = _aktif_sayi()
    if sayi["status"] != "review":
        return {"ok": True, "durum": "zaten-onayli",
                "onaylayan": sayi.get("approved_by")}

    if not db.onayla(sayi["id"], h["ad"]):
        raise HTTPException(409, "Onay kaydedilemedi — sayfayı yenileyin")
    db.logla(sayi["id"], h["ad"], "onay")

    esik = yayin_esigi(sayi["created_at"])
    if datetime.now(timezone.utc) >= esik:
        # geç onay → anında yayın
        import publish
        sayi = db.issue_getir(issue_id=sayi["id"])
        if isinstance(sayi["draft_json"], str):
            sayi["draft_json"] = json.loads(sayi["draft_json"])
        try:
            url = publish.yayinla(sayi)
            return {"ok": True, "durum": "yayinlandi", "url": url}
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "ok": False, "durum": "onaylandi-yayin-hatasi", "hata": str(e)})

    return {"ok": True, "durum": "onaylandi",
            "yayin": "Pazartesi 08:00 TSİ'de otomatik yayınlanacak"}
