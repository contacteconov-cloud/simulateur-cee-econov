"""
Simulateur CEE — ECONOV'
Version 2 — Refonte complete LP moderne
Charte : #61d690 (vert) · #126332 (vert fonce) · #000 · #fff
Typo : Montserrat
"""

import streamlit as st
import anthropic
import base64
import json
import re
import pdfplumber
import io

# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────

def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# DONNEES FICHES
# ─────────────────────────────────────────────────────────────────────────────

FICHES = {
    "BAR-EN-101": {
        "label": "Isolation combles perdus / rampants",
        "code": "BAR-EN-101",
        "secteur": "Residentiel individuel",
        "emoji": "🏠",
        "abrogation": "01/05/2027",
        "mentions_cee": [
            "Marque et reference de l'isolant",
            "Resistance thermique R >= 7 m2K/W (combles perdus) ou R >= 6 (rampants)",
            "Surface isolee en m2",
            "Type de combles (perdus ou rampants)",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "surface",
            "facteurs": {"H1": 1700, "H2": 1400, "H3": 920},
            "prix_ref": {"classique": 7.3, "precarite": 12.5},
            "rappel": "R minimum : 7 m2K/W (combles perdus), 6 m2K/W (rampants)",
        },
    },
    "BAR-EN-102": {
        "label": "Isolation des murs (ITI / ITE)",
        "code": "BAR-EN-102",
        "secteur": "Residentiel individuel",
        "emoji": "🏠",
        "abrogation": "01/05/2027",
        "mentions_cee": [
            "Marque et reference de l'isolant",
            "Resistance thermique R >= 3,7 m2K/W",
            "Surface isolee en m2",
            "Type de pose : ITI (interieur) ou ITE (exterieur)",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "surface",
            "facteurs": {"H1": 1600, "H2": 1300, "H3": 880},
            "prix_ref": {"classique": 7.0, "precarite": 12.0},
            "rappel": "R minimum : 3,7 m2K/W",
        },
    },
    "BAR-EN-103": {
        "label": "Isolation planchers bas",
        "code": "BAR-EN-103",
        "secteur": "Residentiel individuel",
        "emoji": "🏠",
        "abrogation": "01/05/2027",
        "mentions_cee": [
            "Marque et reference de l'isolant",
            "Resistance thermique R >= 3 m2K/W",
            "Surface isolee en m2",
            "Type de plancher : sous-sol / vide sanitaire / passage ouvert",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "surface",
            "facteurs": {"H1": 1100, "H2": 890, "H3": 590},
            "prix_ref": {"classique": 7.0, "precarite": 12.5},
            "rappel": "R minimum : 3 m2K/W",
        },
    },
    "BAR-TH-171": {
        "label": "Pompe a chaleur air/eau",
        "code": "BAR-TH-171",
        "secteur": "Residentiel individuel",
        "emoji": "🏠",
        "abrogation": None,
        "mentions_cee": [
            "Marque et reference de la PAC",
            "Etas >= 126% (BT) ou Etas >= 111% (MHT)",
            "Application : chauffage seul ou chauffage + ECS",
            "Type d'emetteurs (planchers / radiateurs / ventilo-convecteurs)",
            "Zone climatique (H1 / H2 / H3)",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire (bon pour accord) + date",
            "Mention Coup de Pouce Chauffage si applicable",
        ],
        "calcul": {
            "type": "pac_residentiel",
            "montants_base": {
                "Maison individuelle|Chauffage":       [90900, 109200],
                "Maison individuelle|Chauffage + ECS": [90900, 109200],
                "Appartement|Chauffage":               [48700, 58900],
                "Appartement|Chauffage + ECS":         [48700, 58900],
            },
            "coeff_zone": {"H1": 1.2, "H2": 1.0, "H3": 0.7},
            "coeff_surface_maison": [(0, 0.5), (70, 0.7), (90, 1.0)],
            "coeff_surface_appart": [(0, 0.5), (35, 0.7), (60, 1.0)],
            "facteur_cdp": 5,
            "prix_ref": {"classique": 7.4, "precarite": 11.7},
            "rappel": "Etas >= 126% (BT) ou >= 111% (MHT). Coup de Pouce x5 si remplacement chaudiere fioul/gaz/charbon.",
        },
    },
    "BAR-TH-179": {
        "label": "PAC collective <= 400 kW",
        "code": "BAR-TH-179",
        "secteur": "Residentiel collectif",
        "emoji": "🏢",
        "abrogation": None,
        "mentions_cee": [
            "Puissance PAC <= 400 kW",
            "Marque et reference de la PAC",
            "Etas ou COP selon puissance",
            "Nombre de logements desservis",
            "Resultat etude prealable (facteur R batiment)",
            "SIRET et numero RGE",
            "Adresse complete",
            "Signature beneficiaire + date",
        ],
        "calcul": {"type": "nc", "rappel": "Contactez Econov' pour le calcul precis BAR-TH-179."},
    },
    "BAT-TH-163": {
        "label": "PAC air/eau — Tertiaire",
        "code": "BAT-TH-163",
        "secteur": "Tertiaire",
        "emoji": "🏗️",
        "abrogation": None,
        "mentions_cee": [
            "Marque et reference de la PAC",
            "Puissance (<=400 kW => Etas ; >400 kW => COP)",
            "Etas >= 111% si <= 400 kW",
            "Resultat etude prealable (facteur R)",
            "SIRET et numero RGE",
            "Adresse complete",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "pac_tertiaire",
            "bareme_lte400": {
                "111%-126%": {"H1": 1100, "H2": 900, "H3": 600},
                "126%-175%": {"H1": 1200, "H2": 1000, "H3": 700},
                "175%+":     {"H1": 1300, "H2": 1000, "H3": 700},
            },
            "bareme_gt400": {
                "4-5": {"H1": 1200, "H2": 1000, "H3": 700},
                "5+":  {"H1": 1300, "H2": 1000, "H3": 700},
            },
            "facteur_secteur": {
                "Bureaux": 1.2, "Enseignement": 0.8,
                "Hotellerie / Restauration": 0.7, "Sante": 1.1,
                "Commerces": 0.9, "Autres": 0.7,
            },
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "Etas >= 111% (<=400 kW) ou COP >= 3,4 (>400 kW).",
        },
    },
    "BAT-TH-134": {
        "label": "Regulation HP flottante sur froid",
        "code": "BAT-TH-134",
        "secteur": "Tertiaire",
        "emoji": "🏗️",
        "abrogation": None,
        "mentions_cee": [
            "Designation du groupe froid concerne",
            "Puissance electrique nominale (kW)",
            "Marque/reference systeme de regulation",
            "SIRET et numero RGE",
            "Adresse des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "puissance_froid",
            "facteurs": {
                "Autres applications — Condensation air": {"H1": 19100, "H2": 15700, "H3": 10400},
                "Autres applications — Condensation eau":  {"H1": 9000,  "H2": 7400,  "H3": 4900},
                "Froid commercial":                        {"H1": 35100, "H2": 28800, "H3": 19100},
            },
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "Puissance nominale prouvee par la plaque signaletique obligatoire.",
        },
    },
    "BAT-TH-139": {
        "label": "Recuperation chaleur sur groupe froid",
        "code": "BAT-TH-139",
        "secteur": "Tertiaire",
        "emoji": "🏗️",
        "abrogation": None,
        "mentions_cee": [
            "Puissance du compresseur (kW)",
            "Preuve de concomitance des besoins froid/chaud",
            "Historique de fonctionnement >= 24h si existant",
            "SIRET et numero RGE",
            "Adresse des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "recuperation_froid",
            "facteurs_secteur": {
                "Sport / Loisir / Culture": 17100,
                "Hotellerie / Restauration": 21800,
                "Sante": 21800,
                "Commerces": 26200,
                "Enseignement": 30400,
                "Entrepots frigorifiques": 39600,
                "Data Centers": 39600,
                "Autres": 13800,
            },
            "coeff_chauffage": {"H1": 0.63, "H2": 0.59, "H3": 0.50},
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "Precup max = 2,9 x Pcomp. Concomitance obligatoire.",
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CALCUL PRIME
# ─────────────────────────────────────────────────────────────────────────────

def calculer_prime(fiche_id, params, prix_cee):
    calcul = FICHES[fiche_id]["calcul"]
    ctype  = calcul["type"]
    zone   = params.get("zone", "H1")

    if ctype == "surface":
        s = params.get("surface", 0)
        f = calcul["facteurs"].get(zone, 0)
        g = s * f
        return {
            "prime": round(g / 1000 * prix_cee, 2),
            "gisement_mwh": round(g / 1000, 2),
            "detail": f"{s} m2 x {f} kWhc/m2 (zone {zone})",
        }

    elif ctype == "pac_residentiel":
        tl  = params.get("type_logement", "Maison individuelle")
        us  = params.get("usage_pac", "Chauffage")
        eta = params.get("etas", 130)
        s   = params.get("surface", 100)
        cdp = params.get("cdp", False)
        cle = f"{tl}|{us}"
        mb  = calcul["montants_base"].get(cle, [90900, 109200])
        base = mb[1 if eta >= 140 else 0]
        cz   = calcul["coeff_zone"].get(zone, 1.0)
        seuils = calcul["coeff_surface_maison"] if "Maison" in tl else calcul["coeff_surface_appart"]
        cs = seuils[0][1]
        for seuil, c in seuils:
            if s >= seuil:
                cs = c
        fc = calcul["facteur_cdp"] if cdp else 1
        g  = base * cz * fc
        return {
            "prime": round(g / 1000 * prix_cee, 2),
            "gisement_mwh": round(g / 1000, 2),
            "detail": f"Base {base} kWhc x zone {cz} x CdP x{fc}",
            "cdp": cdp,
        }

    elif ctype == "pac_tertiaire":
        pui = params.get("puissance_pac", 200)
        ec  = params.get("etas_ou_cop", 130)
        s   = params.get("surface", 500)
        sec = params.get("secteur_activite", "Bureaux")
        fr  = params.get("facteur_r", 1.0)
        if pui <= 400:
            if ec >= 175:   b = "175%+"
            elif ec >= 126: b = "126%-175%"
            else:           b = "111%-126%"
            kwh = calcul["bareme_lte400"][b].get(zone, 0)
        else:
            kwh = calcul["bareme_gt400"]["5+" if ec >= 5 else "4-5"].get(zone, 0)
        fs = calcul["facteur_secteur"].get(sec, 0.7)
        g  = kwh * fs * fr * s
        return {
            "prime": round(g / 1000 * prix_cee, 2),
            "gisement_mwh": round(g / 1000, 2),
            "detail": f"{kwh} kWhc/m2 x {fs} x R{fr} x {s} m2",
        }

    elif ctype == "puissance_froid":
        app = params.get("application", list(calcul["facteurs"].keys())[0])
        p   = params.get("puissance_kw", 0)
        f   = calcul["facteurs"].get(app, {}).get(zone, 0)
        g   = p * f
        return {
            "prime": round(g / 1000 * prix_cee, 2),
            "gisement_mwh": round(g / 1000, 2),
            "detail": f"{p} kW x {f} kWhc/kW (zone {zone})",
        }

    elif ctype == "recuperation_froid":
        sec  = params.get("secteur_activite", "Autres")
        pc   = params.get("p_compresseur", 0)
        pecs = params.get("p_ecs", 0)
        pch  = params.get("p_chauffage", 0)
        cc   = calcul["coeff_chauffage"].get(zone, 0.5)
        f    = calcul["facteurs_secteur"].get(sec, 13800)
        cap  = 2.9 * pc
        er   = min(pecs, cap)
        cr   = min(pch, max(0, cap - er))
        g    = er * f + cr * f * cc
        return {
            "prime": round(g / 1000 * prix_cee, 2),
            "gisement_mwh": round(g / 1000, 2),
            "detail": f"ECS {round(er * f)} + Ch. {round(cr * f * cc)} kWhc",
            "p_cap": round(cap, 1),
        }

    return {"prime": 0, "gisement_mwh": 0, "detail": "Calcul non disponible"}


# ─────────────────────────────────────────────────────────────────────────────
# FORMULAIRE PARAMETRES (sans st.form — calcul live)
# ─────────────────────────────────────────────────────────────────────────────

def formulaire_params(fiche_id):
    calcul = FICHES[fiche_id]["calcul"]
    ctype  = calcul.get("type", "nc")

    if ctype == "nc":
        st.info("Contactez Econov' pour la simulation de cette fiche.")
        return {}, 7.0

    c1, c2, c3 = st.columns(3)
    with c1:
        zone = st.selectbox("Zone climatique", ["H1", "H2", "H3"], key="p_zone")
    with c2:
        profil = st.selectbox("Profil client", ["Classique", "Precarite"], key="p_profil")
    bk = "precarite" if profil == "Precarite" else "classique"
    with c3:
        prix_ref = float(calcul.get("prix_ref", {}).get(bk, 7.0))
        prix_cee = st.number_input(
            "Prix CEE (EUR/MWhc)",
            value=prix_ref,
            step=0.1,
            min_value=1.0,
            max_value=30.0,
            key="p_prix",
        )

    params = {"zone": zone}

    if ctype == "surface":
        st.markdown('<div style="height:.6rem"></div>', unsafe_allow_html=True)
        params["surface"] = st.number_input(
            "Surface isolee (m2)", value=100.0, min_value=1.0, step=5.0, key="p_surf"
        )

    elif ctype == "pac_residentiel":
        st.markdown('<div style="height:.6rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["type_logement"] = st.selectbox(
                "Type de logement", ["Maison individuelle", "Appartement"], key="p_tl"
            )
            params["surface"] = st.number_input(
                "Surface (m2)", value=100.0, min_value=10.0, step=5.0, key="p_surf"
            )
        with cb:
            params["usage_pac"] = st.selectbox(
                "Usage PAC", ["Chauffage", "Chauffage + ECS"], key="p_usage"
            )
            params["etas"] = st.number_input(
                "Etas (%)", value=130, min_value=100, max_value=250, key="p_etas"
            )
        params["cdp"] = st.checkbox(
            "Remplacement chaudiere fioul / gaz / charbon — Coup de Pouce x5",
            key="p_cdp",
        )

    elif ctype == "pac_tertiaire":
        st.markdown('<div style="height:.6rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["puissance_pac"] = st.number_input(
                "Puissance PAC (kW)", value=200.0, min_value=1.0, key="p_ppac"
            )
            params["etas_ou_cop"] = st.number_input(
                "Etas (%) ou COP", value=130.0, min_value=0.0, key="p_ec"
            )
        with cb:
            params["surface"] = st.number_input(
                "Surface chauffee (m2)", value=500.0, step=10.0, key="p_surf"
            )
            params["facteur_r"] = st.slider(
                "Facteur R (part PAC)", 0.0, 1.0, 1.0, 0.05, key="p_fr"
            )
        params["secteur_activite"] = st.selectbox(
            "Secteur d'activite",
            list(calcul["facteur_secteur"].keys()),
            key="p_sa_tert",
        )

    elif ctype == "puissance_froid":
        st.markdown('<div style="height:.6rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["application"] = st.selectbox(
                "Application", list(calcul["facteurs"].keys()), key="p_app"
            )
        with cb:
            params["puissance_kw"] = st.number_input(
                "Puissance electrique nominale (kW)", value=10.0, step=0.5, key="p_pkw"
            )

    elif ctype == "recuperation_froid":
        params["secteur_activite"] = st.selectbox(
            "Secteur", list(calcul["facteurs_secteur"].keys()), key="p_sa_recup"
        )
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        ca, cb, cc = st.columns(3)
        with ca:
            params["p_compresseur"] = st.number_input(
                "P comp. (kW)", value=15.0, step=1.0, key="p_pc"
            )
        with cb:
            params["p_ecs"] = st.number_input(
                "P recup ECS (kW)", value=0.0, step=0.5, key="p_pe"
            )
        with cc:
            params["p_chauffage"] = st.number_input(
                "P recup Ch. (kW)", value=0.0, step=0.5, key="p_pch"
            )

    return params, prix_cee


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE DOCUMENT
# ─────────────────────────────────────────────────────────────────────────────

def encode_file(fb, fn):
    ext = fn.lower().split(".")[-1]
    b64 = base64.standard_b64encode(fb).decode()
    m   = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp",
    }
    return m.get(ext), b64


def analyze_document(api_key, fb, fn, fiche_id):
    client = anthropic.Anthropic(api_key=api_key)
    fiche  = FICHES[fiche_id]
    ms     = "\n".join(f"- {m}" for m in fiche["mentions_cee"])
    system = (
        f"Expert CEE France. Analyse le document pour {fiche_id} ({fiche['label']}).\n"
        f"Mentions CEE a verifier :\n{ms}\n"
        "Pour chaque mention : present (bool), valeur (string ou null), conforme (bool), commentaire.\n"
        "Extrait : type_document, nom_beneficiaire, adresse_travaux, siret_entreprise, "
        "rge_ok (bool), signature_benef (bool), date_document, resume_global.\n"
        "Score_cee (0-100), blocages_cee (liste), points_attention (liste). JSON uniquement."
    )
    mt, b64 = encode_file(fb, fn)
    try:
        if mt == "application/pdf":
            content = [
                {"type": "document", "source": {"type": "base64", "media_type": mt, "data": b64}},
                {"type": "text", "text": "Analyse."},
            ]
        elif mt:
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                {"type": "text", "text": "Analyse."},
            ]
        else:
            try:
                with pdfplumber.open(io.BytesIO(fb)) as pdf:
                    txt = "\n".join(p.extract_text() or "" for p in pdf.pages)[:8000]
            except Exception:
                txt = ""
            content = [{"type": "text", "text": f"Texte :\n{txt}\nAnalyse."}]

        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        raw = re.sub(r"^```json\s*|\s*```$", "", resp.content[0].text.strip())
        return json.loads(raw)
    except Exception as e:
        return {
            "type_document": "inconnu",
            "resume_global": f"Erreur : {e}",
            "mentions_cee": [],
            "score_cee": 0,
            "blocages_cee": [str(e)],
            "points_attention": [],
        }


# ─────────────────────────────────────────────────────────────────────────────
# CSS — DESIGN LP V2
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
#MainMenu, footer, header, .stDeployButton { visibility: hidden !important; display: none !important; }
.stApp { background: #f4f7f4 !important; }
.main .block-container {
    max-width: 940px !important;
    padding: 0 0 4rem !important;
    margin: 0 auto !important;
}

/* ━━━━━━━━ HERO ━━━━━━━━ */
.hero {
    background: linear-gradient(145deg, #082e17 0%, #126332 55%, #0f5529 100%);
    padding: 4rem 3rem 5.5rem;
    text-align: center;
    border-radius: 0 0 56px 56px;
    box-shadow: 0 28px 70px rgba(8,40,20,0.28);
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    width: 600px; height: 600px;
    top: -250px; right: -180px;
    background: radial-gradient(circle, rgba(97,214,144,0.13) 0%, transparent 65%);
    pointer-events: none;
}
.hero::after {
    content: '';
    position: absolute;
    width: 300px; height: 300px;
    bottom: -120px; left: -60px;
    background: radial-gradient(circle, rgba(97,214,144,0.07) 0%, transparent 65%);
    pointer-events: none;
}
.hero-logo {
    font-size: 1rem;
    font-weight: 900;
    letter-spacing: 6px;
    color: #fff;
    margin-bottom: 2.75rem;
    position: relative;
    z-index: 1;
    text-transform: uppercase;
}
.hero-logo span { color: #61d690; }
.hero h1 {
    font-size: 3.4rem;
    font-weight: 900;
    color: #fff;
    margin: 0 0 1.1rem;
    line-height: 1.08;
    position: relative;
    z-index: 1;
    letter-spacing: -1px;
}
.hero h1 em {
    font-style: italic;
    color: #61d690;
}
.hero-sub {
    font-size: 1.05rem;
    color: rgba(255,255,255,0.6);
    margin: 0 auto 2.75rem;
    max-width: 460px;
    font-weight: 500;
    position: relative;
    z-index: 1;
    line-height: 1.6;
}
.hero-chips {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: center;
    position: relative;
    z-index: 1;
}
.hchip {
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.16);
    color: rgba(255,255,255,0.8);
    font-size: 0.74rem;
    font-weight: 600;
    padding: 7px 18px;
    border-radius: 30px;
    letter-spacing: 0.3px;
}
.hchip strong { color: #61d690; font-weight: 900; }

/* ━━━━━━━━ STEPS BAR ━━━━━━━━ */
.steps-bar {
    background: #fff;
    border-bottom: 1px solid #e3eae3;
    padding: 0 2.5rem;
    position: relative;
}
.steps-row {
    max-width: 540px;
    margin: 0 auto;
    display: flex;
    align-items: stretch;
    position: relative;
}
.steps-row::before {
    content: '';
    position: absolute;
    top: 50%; left: 20%; right: 20%;
    height: 2px;
    background: #e3eae3;
    transform: translateY(-50%);
    z-index: 0;
}
.step {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 1.3rem 0.5rem;
    gap: 0.45rem;
    position: relative;
    z-index: 1;
}
.step-num {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: #e3eae3;
    color: #bbb;
    font-size: 0.85rem;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    position: relative;
    z-index: 1;
}
.step-num.active {
    background: #61d690;
    color: #000;
    box-shadow: 0 0 0 5px rgba(97,214,144,0.22);
}
.step-num.done {
    background: #126332;
    color: #fff;
}
.step-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #c0c8c0;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    text-align: center;
    white-space: nowrap;
}
.step-label.active { color: #126332; }
.step-label.done   { color: #126332; }

/* ━━━━━━━━ BODY ━━━━━━━━ */
.body {
    padding: 2.75rem 2.75rem 4rem;
}

/* ━━━━━━━━ SECTION HEADER ━━━━━━━━ */
.section-header { margin-bottom: 2rem; }
.section-header h2 {
    font-size: 1.55rem;
    font-weight: 800;
    color: #0a0a0a;
    margin: 0 0 0.35rem;
    line-height: 1.2;
    letter-spacing: -0.3px;
}
.section-header p {
    font-size: 0.9rem;
    color: #777;
    margin: 0;
    font-weight: 500;
}

/* ━━━━━━━━ FICHE HEADER (step 2) ━━━━━━━━ */
.fiche-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 1.25rem;
    margin-bottom: 1.75rem;
    border-bottom: 1.5px solid #e3eae3;
    flex-wrap: wrap;
}
.fiche-badge {
    background: #126332;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 800;
    padding: 5px 11px;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
.fiche-name {
    font-size: 1rem;
    font-weight: 700;
    color: #111;
}
.fiche-secteur {
    margin-left: auto;
    font-size: 0.7rem;
    font-weight: 600;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* ━━━━━━━━ FORM BOX ━━━━━━━━ */
.form-box {
    background: #fff;
    border: 1.5px solid #dde8dd;
    border-radius: 20px;
    padding: 1.75rem 1.75rem 2rem;
}
.form-box-title {
    font-size: 0.69rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.8px;
    color: #126332;
    margin-bottom: 1.3rem;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* ━━━━━━━━ PRIME CARD ━━━━━━━━ */
.prime-card {
    background: #000;
    border-radius: 22px;
    padding: 2rem 1.75rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.prime-card::before {
    content: '';
    position: absolute;
    top: -70px; right: -70px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(97,214,144,0.2) 0%, transparent 60%);
    pointer-events: none;
}
.prime-card::after {
    content: '';
    position: absolute;
    bottom: -50px; left: -30px;
    width: 180px; height: 180px;
    background: radial-gradient(circle, rgba(97,214,144,0.08) 0%, transparent 60%);
    pointer-events: none;
}
.prime-eyebrow {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #61d690;
    margin-bottom: 0.65rem;
    position: relative;
    z-index: 1;
}
.prime-amount {
    font-size: 3.5rem;
    font-weight: 900;
    color: #fff;
    line-height: 1;
    position: relative;
    z-index: 1;
    letter-spacing: -2px;
}
.prime-lg .prime-amount {
    font-size: 4.6rem;
    letter-spacing: -3px;
}
.prime-currency {
    font-size: 1.7rem !important;
    color: #61d690 !important;
    vertical-align: super !important;
    margin-right: 3px !important;
    letter-spacing: 0 !important;
    font-weight: 900 !important;
}
.prime-cents {
    font-size: 1.7rem;
    color: rgba(255,255,255,0.3);
    letter-spacing: 0;
    font-weight: 700;
}
.prime-mwh {
    font-size: 0.78rem;
    color: rgba(255,255,255,0.3);
    margin-top: 0.65rem;
    position: relative;
    z-index: 1;
}
.prime-formula {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.2);
    margin-top: 0.3rem;
    position: relative;
    z-index: 1;
}
.cdp-tag {
    display: inline-block;
    background: #61d690;
    color: #000;
    font-size: 0.7rem;
    font-weight: 800;
    padding: 5px 14px;
    border-radius: 30px;
    margin-top: 1.1rem;
    position: relative;
    z-index: 1;
    letter-spacing: 0.3px;
}

/* ━━━━━━━━ RAPPEL NOTE ━━━━━━━━ */
.rappel-note {
    font-size: 0.78rem;
    color: #4a6652;
    background: #eef7f1;
    border: 1px solid #c8e0d0;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-top: 0.75rem;
    font-weight: 500;
    line-height: 1.55;
}

/* ━━━━━━━━ MENTIONS SUMMARY ━━━━━━━━ */
.mentions-box {
    background: #fff;
    border: 1.5px solid #dde8dd;
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin-top: 0.75rem;
}
.mentions-box-title {
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #126332;
    margin-bottom: 0.75rem;
}
.mentions-count {
    font-size: 2rem;
    font-weight: 900;
    color: #111;
    line-height: 1;
}
.mentions-sub {
    font-size: 0.75rem;
    color: #999;
    margin-top: 0.25rem;
    font-weight: 500;
}

/* ━━━━━━━━ UPLOAD SECTION ━━━━━━━━ */
.upload-wrap {
    background: #fff;
    border: 2px dashed #c5dcca;
    border-radius: 18px;
    padding: 1.5rem 1.75rem;
    margin-top: 1.75rem;
}
.upload-label {
    font-size: 0.88rem;
    font-weight: 700;
    color: #111;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.opt-badge {
    font-size: 0.62rem;
    font-weight: 800;
    background: #e8f5ed;
    color: #126332;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.upload-hint {
    font-size: 0.78rem;
    color: #aaa;
    margin-bottom: 0.75rem;
    font-weight: 500;
}

/* ━━━━━━━━ HINT BOX ━━━━━━━━ */
.hint-box {
    text-align: center;
    padding: 1.25rem 1.5rem;
    background: #f1f8f3;
    border: 1.5px dashed #b5d4bc;
    border-radius: 14px;
    color: #555;
    font-size: 0.88rem;
    font-weight: 600;
    margin-top: 1.5rem;
    line-height: 1.6;
}

/* ━━━━━━━━ RESULTS ━━━━━━━━ */
.results-top {
    padding-bottom: 1.1rem;
    margin-bottom: 0.5rem;
}
.results-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ━━━━━━━━ SCORE CARD ━━━━━━━━ */
.score-card {
    border-radius: 18px;
    padding: 1.75rem 1.5rem;
    text-align: center;
    margin-bottom: 1rem;
}
.score-card.pass { background: linear-gradient(135deg,#ecfdf5,#d1fae5); border: 2px solid #a7f3d0; }
.score-card.warn { background: linear-gradient(135deg,#fffbeb,#fef3c7); border: 2px solid #fde68a; }
.score-card.fail { background: linear-gradient(135deg,#fef2f2,#fee2e2); border: 2px solid #fecaca; }
.score-num {
    font-size: 3.2rem;
    font-weight: 900;
    line-height: 1;
}
.score-num small { font-size: 1.1rem; color: #aaa; font-weight: 700; }
.score-card.pass .score-num { color: #126332; }
.score-card.warn .score-num { color: #d97706; }
.score-card.fail .score-num { color: #dc2626; }
.score-verdict {
    font-size: 0.84rem;
    font-weight: 700;
    color: #374151;
    margin-top: 0.4rem;
}

/* ━━━━━━━━ INFOS BOX ━━━━━━━━ */
.infos-box {
    background: #f8faf8;
    border: 1.5px solid #dde8dd;
    border-radius: 14px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
}
.info-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 7px 0;
    border-bottom: 1px solid #edf2ed;
    font-size: 0.83rem;
    gap: 8px;
}
.info-row:last-child { border-bottom: none; }
.info-k { color: #999; font-weight: 600; white-space: nowrap; }
.info-v { color: #111; font-weight: 700; text-align: right; word-break: break-word; }

/* ━━━━━━━━ CHECKLIST ━━━━━━━━ */
.checklist {
    background: #fff;
    border: 1.5px solid #dde8dd;
    border-radius: 18px;
    padding: 1.5rem 1.75rem;
    margin-top: 1.75rem;
}
.checklist-title {
    font-size: 0.69rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #126332;
    margin-bottom: 1.1rem;
    padding-bottom: 0.9rem;
    border-bottom: 1.5px solid #eaf2ea;
}
.check-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid #f3f4f3;
    font-size: 0.85rem;
}
.check-row:last-child { border-bottom: none; }
.check-icon { font-size: 0.95rem; flex-shrink: 0; margin-top: 2px; }
.check-text { color: #111; line-height: 1.45; }
.check-val { color: #126332; font-weight: 700; margin-left: 5px; }
.check-comment { font-size: 0.74rem; color: #aaa; margin-top: 2px; }

/* ━━━━━━━━ ADD DOC HINT ━━━━━━━━ */
.doc-hint {
    background: #f1f8f3;
    border: 1.5px solid #c5dcca;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    font-size: 0.87rem;
    color: #374151;
    margin: 1.75rem 0;
    line-height: 1.55;
}

/* ━━━━━━━━ MESSAGE ━━━━━━━━ */
.msg-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 1.75rem 0 0.6rem;
    font-size: 0.69rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #126332;
}

/* ━━━━━━━━ FOOTER ━━━━━━━━ */
.footer {
    text-align: center;
    padding: 2.5rem 0 1.5rem;
    font-size: 0.74rem;
    color: #c5cec5;
    font-weight: 500;
    letter-spacing: 0.2px;
}
.footer strong { color: #126332; font-weight: 700; }

/* ━━━━━━━━ BUTTONS ━━━━━━━━ */
.stButton > button {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    font-size: 0.88rem !important;
    transition: all 0.2s ease !important;
    white-space: pre-wrap !important;
    letter-spacing: 0.1px !important;
    min-height: 48px !important;
    line-height: 1.4 !important;
}
.stButton > button[kind="secondary"] {
    background: #fff !important;
    border: 1.5px solid #d5e3d5 !important;
    color: #374151 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #61d690 !important;
    background: #f5fcf7 !important;
    box-shadow: 0 4px 16px rgba(97,214,144,0.2) !important;
    transform: translateY(-1px) !important;
    color: #111 !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #126332 0%, #0c4b26 100%) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 4px 18px rgba(18,99,50,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(18,99,50,0.42) !important;
}

/* ━━━━━━━━ TABS ━━━━━━━━ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    background: transparent !important;
    border-bottom: 2px solid #e3eae3 !important;
    margin-bottom: 1.75rem !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    padding: 0.85rem 1.5rem !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    color: #999 !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
    transition: all 0.2s !important;
    letter-spacing: 0.1px !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #126332 !important; background: #f5fcf7 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #126332 !important;
    border-bottom-color: #61d690 !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }
.stTabs [data-baseweb="tab-panel"]     { padding: 0 !important; }

/* ━━━━━━━━ INPUTS ━━━━━━━━ */
div[data-baseweb="select"] > div {
    border-radius: 10px !important;
    border-color: #d5e3d5 !important;
    background: #fafcfa !important;
    font-family: 'Montserrat', sans-serif !important;
}
div[data-baseweb="input"] > div,
div[data-baseweb="number-input"] {
    border-radius: 10px !important;
    border-color: #d5e3d5 !important;
    background: #fafcfa !important;
}
div[data-baseweb="input"] > div > input,
div[data-baseweb="number-input"] input {
    font-family: 'Montserrat', sans-serif !important;
    font-size: 0.9rem !important;
    background: transparent !important;
}
label[data-testid="stWidgetLabel"] p {
    font-family: 'Montserrat', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 800 !important;
    color: #374151 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
    margin-bottom: 0.3rem !important;
}
.stCheckbox label p {
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    color: #374151 !important;
}
.stSlider label p {
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
    font-size: 0.72rem !important;
    font-weight: 800 !important;
}
.stAlert { border-radius: 12px !important; }
details > summary {
    font-family: 'Montserrat', sans-serif !important;
    font-size: 0.84rem !important;
    font-weight: 700 !important;
    color: #126332 !important;
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# HTML COMPOSANTS
# ─────────────────────────────────────────────────────────────────────────────

def render_hero():
    st.markdown("""
<div class="hero">
  <div class="hero-logo"><span>ECO</span>NOV'</div>
  <h1>Calculez votre <em>prime CEE</em><br>en 30 secondes</h1>
  <p class="hero-sub">Simulateur gratuit pour les professionnels de la renovation energetique</p>
  <div class="hero-chips">
    <div class="hchip"><strong>8</strong> fiches CEE</div>
    <div class="hchip"><strong>3</strong> secteurs</div>
    <div class="hchip">Verification <strong>IA</strong> de documents</div>
    <div class="hchip">Acces <strong>libre</strong></div>
  </div>
</div>
""", unsafe_allow_html=True)


def render_steps(current):
    steps = ["Votre operation", "Parametres", "Resultats"]
    items = []
    for i, label in enumerate(steps, 1):
        if i < current:
            ncls, lcls, nd = "done", "done", "✓"
        elif i == current:
            ncls, lcls, nd = "active", "active", str(i)
        else:
            ncls, lcls, nd = "", "", str(i)
        items.append(
            f'<div class="step">'
            f'<div class="step-num {ncls}">{nd}</div>'
            f'<span class="step-label {lcls}">{label}</span>'
            f'</div>'
        )
    st.markdown(
        f'<div class="steps-bar"><div class="steps-row">{"".join(items)}</div></div>',
        unsafe_allow_html=True,
    )


def prime_card_html(pr, large=False):
    amount   = pr.get("prime", 0)
    gis      = pr.get("gisement_mwh", 0)
    detail   = pr.get("detail", "")
    cdp      = pr.get("cdp", False)
    int_part = f"{int(amount):,}".replace(",", "\u202f")
    dec_part = f"{amount:.2f}".split(".")[1]
    size_cls = "prime-lg" if large else ""
    cdp_html = '<div class="cdp-tag">&#9889; Coup de Pouce x5 inclus</div>' if cdp else ""
    return (
        f'<div class="prime-card {size_cls}">'
        f'<div class="prime-eyebrow">Prime CEE estimee</div>'
        f'<div class="prime-amount"><sup class="prime-currency">&#8364;</sup>'
        f'{int_part}<span class="prime-cents">,{dec_part}</span></div>'
        f'<div class="prime-mwh">{gis} MWhc cumac</div>'
        f'<div class="prime-formula">{detail}</div>'
        f'{cdp_html}'
        f'</div>'
    )


def score_card_html(score):
    if score >= 80:
        cls, verdict = "pass", "✅ Document conforme"
    elif score >= 50:
        cls, verdict = "warn", "⚠️ Points a corriger"
    else:
        cls, verdict = "fail", "❌ Document non conforme"
    return (
        f'<div class="score-card {cls}">'
        f'<div class="score-num">{score}<small>/100</small></div>'
        f'<div class="score-verdict">{verdict}</div>'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    "step":            1,
    "fiche_id":        None,
    "prime_result":    None,
    "result":          None,
    "uploaded_bytes":  None,
    "uploaded_name":   None,
    "analysis_done":   False,
}


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Simulateur CEE — Econov'",
        page_icon="🌿",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    render_hero()
    render_steps(st.session_state.step)
    api_key = get_api_key()

    st.markdown('<div class="body">', unsafe_allow_html=True)

    # ───────────────────────────────────────────
    # ETAPE 1 — CHOIX DE LA FICHE
    # ───────────────────────────────────────────
    if st.session_state.step == 1:
        st.markdown("""
<div class="section-header">
  <h2>Quelle operation souhaitez-vous simuler ?</h2>
  <p>Selectionnez la fiche CEE correspondant aux travaux realises.</p>
</div>
""", unsafe_allow_html=True)

        from collections import defaultdict
        secteurs = defaultdict(list)
        for fid, f in FICHES.items():
            secteurs[f["secteur"]].append(fid)

        tab_labels = list(secteurs.keys())
        tabs = st.tabs(tab_labels)

        for tab, secteur in zip(tabs, tab_labels):
            with tab:
                fids = secteurs[secteur]
                cols = st.columns(2, gap="medium")
                for i, fid in enumerate(fids):
                    f  = FICHES[fid]
                    ab = f.get("abrogation")
                    selected = st.session_state.fiche_id == fid
                    icon  = "✓  " if selected else ""
                    ab_lbl = f"\n⚠ Abroge le {ab[:7]}" if ab else ""
                    btn_lbl = f"{icon}{f['code']}\n{f['label']}{ab_lbl}"
                    with cols[i % 2]:
                        if st.button(
                            btn_lbl,
                            key=f"btn_{fid}",
                            use_container_width=True,
                            type="primary" if selected else "secondary",
                        ):
                            # Efface l'etat du formulaire de la fiche precedente
                            for k in list(st.session_state.keys()):
                                if k.startswith("p_"):
                                    del st.session_state[k]
                            st.session_state.fiche_id    = fid
                            st.session_state.result      = None
                            st.session_state.prime_result = None
                            st.session_state.analysis_done = False
                            st.rerun()

        st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)

        if st.session_state.fiche_id:
            f = FICHES[st.session_state.fiche_id]
            st.success(f"**{f['code']} — {f['label']}** selectionne")
            st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
            if st.button("Calculer ma prime  →", type="primary", use_container_width=True):
                st.session_state.step = 2
                st.rerun()
        else:
            st.markdown("""
<div class="hint-box">
  👆 Cliquez sur une operation pour commencer la simulation
</div>
""", unsafe_allow_html=True)

    # ───────────────────────────────────────────
    # ETAPE 2 — PARAMETRES + UPLOAD
    # ───────────────────────────────────────────
    elif st.session_state.step == 2:
        fiche_id = st.session_state.fiche_id
        f  = FICHES[fiche_id]
        ab = f.get("abrogation")

        st.markdown(
            f'<div class="fiche-header">'
            f'<span class="fiche-badge">{f["code"]}</span>'
            f'<span class="fiche-name">{f["label"]}</span>'
            f'<span class="fiche-secteur">{f["secteur"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if ab:
            st.warning(f"⚠️ Cette fiche sera abrogee le **{ab}** — verifiez la date d'engagement.")

        # Mise en page 2 colonnes
        col_left, col_right = st.columns([6, 4], gap="large")

        with col_left:
            st.markdown('<div class="form-box">', unsafe_allow_html=True)
            st.markdown(
                '<div class="form-box-title">📐 Parametres de l\'operation</div>',
                unsafe_allow_html=True,
            )
            params, prix_cee = formulaire_params(fiche_id)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_right:
            if params and FICHES[fiche_id]["calcul"].get("type") != "nc":
                prime_live = calculer_prime(fiche_id, params, prix_cee)
                st.markdown(prime_card_html(prime_live, large=False), unsafe_allow_html=True)

                rappel = f["calcul"].get("rappel", "")
                if rappel:
                    st.markdown(
                        f'<div class="rappel-note">&#8505;&#65039; {rappel}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                prime_live = {}

            # Resume mentions CEE
            n_mentions = len(f["mentions_cee"])
            st.markdown(
                f'<div class="mentions-box">'
                f'<div class="mentions-box-title">📋 Mentions CEE requises</div>'
                f'<div class="mentions-count">{n_mentions}</div>'
                f'<div class="mentions-sub">mentions sur le document</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Voir la liste des mentions"):
                for m in f["mentions_cee"]:
                    st.write(f"→ {m}")

        # Zone upload (pleine largeur)
        st.markdown("""
<div class="upload-wrap">
  <div class="upload-label">📄 Verifier un document <span class="opt-badge">Optionnel</span></div>
  <div class="upload-hint">Deposez un devis, facture ou AH pour verification IA de conformite CEE</div>
</div>
""", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "",
            type=["pdf", "jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )
        if uploaded:
            st.caption(f"✓ **{uploaded.name}** · {uploaded.size // 1024} Ko")

        # CTA
        st.markdown('<div style="height:1.25rem"></div>', unsafe_allow_html=True)
        col_back, col_go = st.columns([3, 7], gap="medium")
        with col_back:
            if st.button("← Retour", use_container_width=True):
                st.session_state.step = 1
                st.rerun()
        with col_go:
            if st.button("Voir mes resultats  →", type="primary", use_container_width=True):
                # Sauvegarde de l'etat pour l'etape 3
                final_prime = calculer_prime(fiche_id, params, prix_cee) if params else {}
                st.session_state.prime_result = final_prime
                if uploaded:
                    st.session_state.uploaded_bytes = uploaded.read()
                    st.session_state.uploaded_name  = uploaded.name
                    st.session_state.analysis_done  = False
                else:
                    st.session_state.uploaded_bytes = None
                    st.session_state.uploaded_name  = None
                st.session_state.result = None
                st.session_state.step   = 3
                st.rerun()

    # ───────────────────────────────────────────
    # ETAPE 3 — RESULTATS
    # ───────────────────────────────────────────
    elif st.session_state.step == 3:
        fiche_id     = st.session_state.fiche_id
        f            = FICHES[fiche_id]
        prime_result = st.session_state.prime_result or {}

        # Analyse IA (une seule fois)
        if (
            st.session_state.uploaded_bytes
            and not st.session_state.analysis_done
            and api_key
        ):
            with st.spinner("Analyse IA du document en cours (10-30 s)…"):
                result = analyze_document(
                    api_key,
                    st.session_state.uploaded_bytes,
                    st.session_state.uploaded_name,
                    fiche_id,
                )
            st.session_state.result        = result
            st.session_state.analysis_done = True
            st.rerun()
        elif st.session_state.uploaded_bytes and not api_key:
            st.error("Cle API non configuree — analyse impossible.")
            st.session_state.uploaded_bytes = None

        result = st.session_state.result

        # En-tete resultats
        st.markdown(
            f'<div class="results-top"><div class="results-label">{f["code"]} — {f["label"]}</div></div>',
            unsafe_allow_html=True,
        )

        # Carte prime (pleine largeur)
        if prime_result.get("prime", 0) > 0:
            st.markdown(prime_card_html(prime_result, large=True), unsafe_allow_html=True)
            rappel = f["calcul"].get("rappel", "")
            if rappel:
                st.caption(f"ℹ️ {rappel}")
            if prime_result.get("p_cap"):
                st.caption(f"Cap reglementaire Precup max : {prime_result['p_cap']} kW")

        # Analyse document
        if result:
            score    = result.get("score_cee", 0)
            mentions = result.get("mentions_cee", [])
            blocages = result.get("blocages_cee", [])
            attentions = result.get("points_attention", [])
            n_ok     = sum(1 for m in mentions if m.get("present"))

            st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)

            col_score, col_infos = st.columns([4, 6], gap="large")

            with col_score:
                st.markdown(score_card_html(score), unsafe_allow_html=True)
                st.metric("Mentions presentes", f"{n_ok}/{len(mentions)}")
                st.metric("Points bloquants", len(blocages))

            with col_infos:
                infos = {k: v for k, v in {
                    "Beneficiaire": result.get("nom_beneficiaire"),
                    "Adresse":      result.get("adresse_travaux"),
                    "SIRET":        result.get("siret_entreprise"),
                    "Date":         result.get("date_document"),
                    "RGE":    "OK" if result.get("rge_ok") else ("Absent" if result.get("rge_ok") is not None else None),
                    "Signature": "Presente" if result.get("signature_benef") else ("Absente" if result.get("signature_benef") is not None else None),
                }.items() if v}

                if infos:
                    rows = "".join(
                        f'<div class="info-row">'
                        f'<span class="info-k">{k}</span>'
                        f'<span class="info-v">{v}</span>'
                        f'</div>'
                        for k, v in infos.items()
                    )
                    st.markdown(f'<div class="infos-box">{rows}</div>', unsafe_allow_html=True)

                if result.get("resume_global"):
                    st.info(result["resume_global"])

            # Checklist mentions
            if mentions:
                rows_html = ""
                for m in mentions:
                    present  = m.get("present", False)
                    conforme = m.get("conforme")
                    icon = "✅" if (present and conforme is not False) else ("⚠️" if present else "❌")
                    val_html  = f'<span class="check-val">→ {m["valeur"]}</span>' if m.get("valeur") else ""
                    comm_html = f'<div class="check-comment">{m["commentaire"]}</div>' if m.get("commentaire") else ""
                    rows_html += (
                        f'<div class="check-row">'
                        f'<span class="check-icon">{icon}</span>'
                        f'<div><div class="check-text">{m.get("mention","")}{val_html}</div>{comm_html}</div>'
                        f'</div>'
                    )
                st.markdown(
                    f'<div class="checklist">'
                    f'<div class="checklist-title">Details des mentions CEE — {f["code"]}</div>'
                    f'{rows_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            for b in blocages:
                st.error(f"🔴 {b}")
            for a in attentions:
                st.warning(f"🟠 {a}")

        elif prime_result.get("prime", 0) > 0:
            st.markdown("""
<div class="doc-hint">
  💡 <strong>Astuce :</strong> Ajoutez un document a l'etape precedente pour verifier
  sa conformite CEE par analyse IA — devis, facture ou attestation sur l'honneur.
</div>
""", unsafe_allow_html=True)

        # Message a envoyer
        if result or prime_result.get("prime", 0) > 0:
            parts = []
            if prime_result.get("prime", 0) > 0:
                parts += [
                    f"Prime CEE estimee ({f['code']}) : {prime_result['prime']:,.2f} EUR",
                    f"Gisement : {prime_result['gisement_mwh']} MWhc cumac",
                    "",
                ]
            if result:
                sc = result.get("score_cee", 0)
                parts.append(f"Score de conformite document : {sc}/100")
                for b in result.get("blocages_cee", []):
                    parts.append(f"  BLOQUANT : {b}")
                for a in result.get("points_attention", []):
                    parts.append(f"  A corriger : {a}")
                parts.append("")
            parts += [
                "Merci de corriger les points signales avant depot du dossier complet.",
                "— Econov'",
            ]

            st.markdown(
                '<div class="msg-header">💬 Message a envoyer a l\'installateur</div>',
                unsafe_allow_html=True,
            )
            st.text_area("", "\n".join(parts), height=160, label_visibility="collapsed")

        # Boutons de navigation
        st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)
        col_back, col_new = st.columns(2, gap="medium")
        with col_back:
            if st.button("← Modifier les parametres", use_container_width=True):
                st.session_state.step          = 2
                st.session_state.result        = None
                st.session_state.analysis_done = False
                st.rerun()
        with col_new:
            if st.button("Nouvelle simulation  →", type="primary", use_container_width=True):
                # Remet tout a zero
                for k in list(st.session_state.keys()):
                    if k.startswith("p_") or k in DEFAULTS:
                        if k in st.session_state:
                            del st.session_state[k]
                for k, v in DEFAULTS.items():
                    st.session_state[k] = v
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # close .body

    # Footer
    st.markdown("""
<div class="footer">
  Simulateur CEE &bull; <strong>Econov'</strong> &bull;
  Resultats indicatifs, non contractuels &bull; Analyse IA par Claude (Anthropic)
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
