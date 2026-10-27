"""
Simulateur CEE — ECONOV'
Interface refaite selon charte graphique Econov (vert #61d690 / #126332, noir, blanc)
Flux : Fiche -> Parametres + Prime -> (optionnel) Document -> Resultat
"""

import streamlit as st
import anthropic
import base64
import json
import re
import pdfplumber
import io

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return ""

# ──────────────────────────────────────────────────────────────────────────────
# DONNEES FICHES CEE
# ──────────────────────────────────────────────────────────────────────────────

FICHES = {
    "BAR-EN-101": {
        "label": "Isolation combles perdus / rampants",
        "code": "BAR-EN-101",
        "secteur": "Residentiel individuel",
        "icon": "🏠",
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
            "rappel": "R min. : 7 m2K/W en combles perdus, 6 m2K/W en rampants",
        },
    },
    "BAR-EN-102": {
        "label": "Isolation des murs (ITI/ITE)",
        "code": "BAR-EN-102",
        "secteur": "Residentiel individuel",
        "icon": "🏠",
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
            "rappel": "R min. : 3,7 m2K/W",
        },
    },
    "BAR-EN-103": {
        "label": "Isolation planchers bas",
        "code": "BAR-EN-103",
        "secteur": "Residentiel individuel",
        "icon": "🏠",
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
            "rappel": "R min. : 3 m2K/W",
        },
    },
    "BAR-TH-171": {
        "label": "PAC air/eau",
        "code": "BAR-TH-171",
        "secteur": "Residentiel individuel",
        "icon": "🏠",
        "abrogation": None,
        "mentions_cee": [
            "Marque et reference de la PAC",
            "Etas >= 126 % (BT) ou Etas >= 111 % (MHT)",
            "Application PAC : chauffage seul ou chauffage + ECS",
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
                "Maison individuelle|Chauffage": [90900, 109200],
                "Maison individuelle|Chauffage + ECS": [90900, 109200],
                "Appartement|Chauffage": [48700, 58900],
                "Appartement|Chauffage + ECS": [48700, 58900],
            },
            "coeff_zone": {"H1": 1.2, "H2": 1.0, "H3": 0.7},
            "coeff_surface_maison": [(0, 0.5), (70, 0.7), (90, 1.0)],
            "coeff_surface_appart": [(0, 0.5), (35, 0.7), (60, 1.0)],
            "facteur_cdp": 5,
            "prix_ref": {"classique": 7.4, "precarite": 11.7},
            "rappel": "Etas >= 126 % (BT) ou >= 111 % (MHT). CdP x5 si remplacement chaudiere fioul/gaz/charbon.",
        },
    },
    "BAR-TH-179": {
        "label": "PAC collective <= 400 kW",
        "code": "BAR-TH-179",
        "secteur": "Residentiel collectif",
        "icon": "🏢",
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
        "calcul": {
            "type": "nc",
            "rappel": "Simulation sur devis — contacter Econov pour le calcul precis.",
        },
    },
    "BAT-TH-163": {
        "label": "PAC air/eau tertiaire",
        "code": "BAT-TH-163",
        "secteur": "Tertiaire",
        "icon": "🏗️",
        "abrogation": None,
        "mentions_cee": [
            "Marque et reference de la PAC",
            "Puissance (<=400 kW => Etas ; >400 kW => COP)",
            "Etas >= 111 % si <= 400 kW",
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
            "rappel": "Etas >= 111 % (<=400 kW) ou COP >= 3,4 (>400 kW). Facteur R = part PAC/chaufferie.",
        },
    },
    "BAT-TH-134": {
        "label": "Regulation HP flottante sur froid",
        "code": "BAT-TH-134",
        "secteur": "Tertiaire",
        "icon": "🏗️",
        "abrogation": None,
        "mentions_cee": [
            "Designation du groupe froid concerne",
            "Puissance electrique nominale (kW) — plaque signaletique requise",
            "Marque/reference systeme de regulation",
            "SIRET et numero RGE",
            "Adresse des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "puissance_froid",
            "facteurs": {
                "Autres applications — Par rapport a l'atmosphere": {"H1": 19100, "H2": 15700, "H3": 10400},
                "Autres applications — Par rapport a l'eau":        {"H1": 9000,  "H2": 7400,  "H3": 4900},
                "Froid commercial":                                  {"H1": 35100, "H2": 28800, "H3": 19100},
            },
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "La puissance nominale doit etre prouvee par la plaque signaletique.",
        },
    },
    "BAT-TH-139": {
        "label": "Recuperation chaleur sur groupe froid",
        "code": "BAT-TH-139",
        "secteur": "Tertiaire",
        "icon": "🏗️",
        "abrogation": None,
        "mentions_cee": [
            "Puissance du compresseur (kW)",
            "Preuve de concomitance des besoins froid/chaud",
            "Historique de fonctionnement >= 24 h (si existant)",
            "SIRET et numero RGE",
            "Adresse des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "recuperation_froid",
            "facteurs_secteur": {
                "Sport / Loisir / Culture / Transport": 17100,
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

# ──────────────────────────────────────────────────────────────────────────────
# CALCUL PRIME
# ──────────────────────────────────────────────────────────────────────────────

def calculer_prime(fiche_id, params, prix_cee):
    calcul = FICHES[fiche_id]["calcul"]
    ctype = calcul["type"]
    zone = params.get("zone", "H1")

    if ctype == "surface":
        surface = params.get("surface", 0)
        facteur = calcul["facteurs"].get(zone, 0)
        gisement = surface * facteur
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 2),
            "prime": round((gisement / 1000) * prix_cee, 2),
            "detail": f"{surface} m² × {facteur} kWhc/m² (zone {zone})",
        }

    elif ctype == "pac_residentiel":
        type_log = params.get("type_logement", "Maison individuelle")
        usage    = params.get("usage_pac", "Chauffage")
        etas     = params.get("etas", 130)
        surface  = params.get("surface", 100)
        cdp      = params.get("remplacement_chaudiere", False)

        cle = f"{type_log}|{usage}"
        montants = calcul["montants_base"].get(cle, [90900, 109200])
        bande = 1 if etas >= 140 else 0
        base = montants[bande]
        coeff_z = calcul["coeff_zone"].get(zone, 1.0)
        seuils = calcul["coeff_surface_maison"] if "Maison" in type_log else calcul["coeff_surface_appart"]
        coeff_s = seuils[0][1]
        for seuil, c in seuils:
            if surface >= seuil:
                coeff_s = c
        facteur_cdp = calcul["facteur_cdp"] if cdp else 1
        gisement = base * coeff_z * facteur_cdp
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 2),
            "prime": round((gisement / 1000) * prix_cee, 2),
            "detail": f"Base {base} kWhc × zone {coeff_z} × CdP ×{facteur_cdp}",
            "cdp": cdp,
        }

    elif ctype == "pac_tertiaire":
        puissance   = params.get("puissance_pac", 200)
        etas_cop    = params.get("etas_ou_cop", 130)
        surface     = params.get("surface", 1000)
        secteur_act = params.get("secteur_activite", "Bureaux")
        facteur_r   = params.get("facteur_r", 1.0)
        if puissance <= 400:
            if etas_cop >= 175:   bande = "175%+"
            elif etas_cop >= 126: bande = "126%-175%"
            else:                 bande = "111%-126%"
            kwh_m2 = calcul["bareme_lte400"][bande].get(zone, 0)
        else:
            bande  = "5+" if etas_cop >= 5 else "4-5"
            kwh_m2 = calcul["bareme_gt400"][bande].get(zone, 0)
        fact_s   = calcul["facteur_secteur"].get(secteur_act, 0.7)
        gisement = kwh_m2 * fact_s * facteur_r * surface
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 2),
            "prime": round((gisement / 1000) * prix_cee, 2),
            "detail": f"{kwh_m2} kWhc/m² × secteur {fact_s} × R={facteur_r} × {surface} m²",
        }

    elif ctype == "puissance_froid":
        app      = params.get("application", list(calcul["facteurs"].keys())[0])
        puissance = params.get("puissance_kw", 0)
        facteur  = calcul["facteurs"].get(app, {}).get(zone, 0)
        gisement = puissance * facteur
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 2),
            "prime": round((gisement / 1000) * prix_cee, 2),
            "detail": f"{puissance} kW × {facteur} kWhc/kW ({zone})",
        }

    elif ctype == "recuperation_froid":
        secteur_act = params.get("secteur_activite", "Autres")
        p_comp      = params.get("p_compresseur", 0)
        p_ecs       = params.get("p_ecs", 0)
        p_ch        = params.get("p_chauffage", 0)
        coeff_ch    = calcul["coeff_chauffage"].get(zone, 0.5)
        facteur     = calcul["facteurs_secteur"].get(secteur_act, 13800)
        p_cap       = 2.9 * p_comp
        p_ecs_r     = min(p_ecs, p_cap)
        p_ch_r      = min(p_ch, max(0, p_cap - p_ecs_r))
        gisement    = p_ecs_r * facteur + p_ch_r * facteur * coeff_ch
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 2),
            "prime": round((gisement / 1000) * prix_cee, 2),
            "detail": f"ECS {round(p_ecs_r * facteur)} + Chauffage {round(p_ch_r * facteur * coeff_ch)} kWhc",
            "p_cap": round(p_cap, 1),
        }

    return {"gisement_kwh": 0, "gisement_mwh": 0, "prime": 0, "detail": "Calcul non disponible."}


def formulaire_calcul(fiche_id):
    """Retourne (params, prix_cee) depuis les widgets Streamlit."""
    calcul = FICHES[fiche_id]["calcul"]
    ctype  = calcul.get("type", "nc")
    params = {}

    if ctype == "nc":
        st.info("Simulation disponible sur devis — contactez Econov pour le calcul precis.")
        return {}, 7.0

    col1, col2, col3 = st.columns(3)

    with col1:
        params["zone"] = st.selectbox("Zone climatique", ["H1", "H2", "H3"], key="f_zone")
    with col2:
        benef_type = st.selectbox("Beneficiaire", ["Classique", "Precarite"], key="f_benef")
        bk = "precarite" if benef_type == "Precarite" else "classique"
    with col3:
        prix_ref = calcul["prix_ref"][bk]
        prix_cee = st.number_input("Prix CEE (EUR/MWhc)", value=float(prix_ref),
                                   step=0.1, min_value=1.0, max_value=30.0, key="f_prix")

    zone = params["zone"]

    if ctype == "surface":
        params["surface"] = st.number_input("Surface isolee (m²)", value=100.0,
                                             min_value=1.0, step=1.0, key="f_surf")

    elif ctype == "pac_residentiel":
        col_a, col_b = st.columns(2)
        with col_a:
            params["type_logement"] = st.selectbox("Type de logement",
                ["Maison individuelle", "Appartement"], key="f_typelog")
            params["surface"] = st.number_input("Surface (m²)", value=100.0,
                                                min_value=10.0, step=5.0, key="f_surf")
        with col_b:
            params["usage_pac"] = st.selectbox("Usage PAC",
                ["Chauffage", "Chauffage + ECS"], key="f_usage")
            params["etas"] = st.number_input("Etas (%)", value=130,
                                             min_value=100, max_value=250, key="f_etas")
        params["remplacement_chaudiere"] = st.checkbox(
            "Remplacement chaudiere fioul / gaz / charbon (Coup de Pouce x5)",
            key="f_cdp"
        )

    elif ctype == "pac_tertiaire":
        col_a, col_b = st.columns(2)
        with col_a:
            params["puissance_pac"] = st.number_input("Puissance PAC (kW)", value=200.0,
                                                       min_value=1.0, key="f_pui")
            params["etas_ou_cop"]   = st.number_input("Etas (%) si <=400 kW  /  COP si >400 kW",
                                                       value=130.0, min_value=0.0, step=1.0, key="f_etas")
        with col_b:
            params["surface"] = st.number_input("Surface chauffee (m²)", value=500.0,
                                                min_value=1.0, step=10.0, key="f_surf")
            params["facteur_r"] = st.slider("Facteur R (part PAC / chaufferie)", 0.0, 1.0, 1.0, 0.05, key="f_fr")
        params["secteur_activite"] = st.selectbox("Secteur d'activite",
            list(calcul["facteur_secteur"].keys()), key="f_sect")

    elif ctype == "puissance_froid":
        col_a, col_b = st.columns(2)
        with col_a:
            params["application"] = st.selectbox("Application / Condensation",
                list(calcul["facteurs"].keys()), key="f_app")
        with col_b:
            params["puissance_kw"] = st.number_input("Puissance electrique nominale (kW)",
                                                      value=10.0, min_value=0.1, step=0.5, key="f_pui")

    elif ctype == "recuperation_froid":
        params["secteur_activite"] = st.selectbox("Secteur d'activite",
            list(calcul["facteurs_secteur"].keys()), key="f_sect")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            params["p_compresseur"] = st.number_input("Puissance compresseur (kW)",
                                                       value=15.0, min_value=0.0, step=1.0, key="f_pcomp")
        with col_b:
            params["p_ecs"] = st.number_input("Puissance recup ECS (kW)",
                                               value=0.0, min_value=0.0, step=0.5, key="f_pecs")
        with col_c:
            params["p_chauffage"] = st.number_input("Puissance recup Chauffage (kW)",
                                                     value=0.0, min_value=0.0, step=0.5, key="f_pch")

    return params, prix_cee


# ──────────────────────────────────────────────────────────────────────────────
# ANALYSE DOCUMENT (Claude API)
# ──────────────────────────────────────────────────────────────────────────────

def encode_file(file_bytes, filename):
    ext = filename.lower().split(".")[-1]
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
    mapping = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
               "png": "image/png", "webp": "image/webp"}
    return mapping.get(ext), b64


def analyze_document(api_key, file_bytes, filename, fiche_id):
    client  = anthropic.Anthropic(api_key=api_key)
    fiche   = FICHES[fiche_id]
    mentions_str = "\n".join(f"- {m}" for m in fiche["mentions_cee"])

    system = f"""Expert CEE France. Tu analyses un document pour la fiche {fiche_id} ({fiche['label']}).

MENTIONS CEE OBLIGATOIRES a verifier :
{mentions_str}

Pour chaque mention : present (true/false), valeur trouvee si presente, conforme (true/false/null), commentaire si anomalie.
Extrais aussi : type_document, nom_beneficiaire, adresse_travaux, siret_entreprise, rge_ok (true/false/null), signature_benef (true/false/null), date_document, resume_global (1-2 phrases).
Score_cee (0-100), blocages_cee (liste strings), points_attention (liste strings).

Reponds en JSON uniquement :
{{
  "type_document":"devis|facture|ah|photos|autre",
  "nom_beneficiaire":null,"adresse_travaux":null,"siret_entreprise":null,
  "rge_ok":null,"signature_benef":null,"date_document":null,
  "resume_global":"...",
  "mentions_cee":[{{"mention":"...","present":true,"valeur":null,"conforme":null,"commentaire":""}}],
  "score_cee":75,
  "blocages_cee":[],
  "points_attention":[]
}}"""

    media_type, b64 = encode_file(file_bytes, filename)
    try:
        if media_type == "application/pdf":
            content = [
                {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "Analyse ce document."}
            ]
        elif media_type:
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "Analyse ce document."}
            ]
        else:
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    txt = "\n".join(p.extract_text() or "" for p in pdf.pages)[:8000]
            except Exception:
                txt = ""
            content = [{"type": "text", "text": f"Texte extrait :\n{txt}\n\nAnalyse."}]

        resp = client.messages.create(
            model="claude-opus-4-5", max_tokens=2000, system=system,
            messages=[{"role": "user", "content": content}]
        )
        raw = re.sub(r"^```json\s*", "", resp.content[0].text.strip())
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        return {"type_document": "inconnu", "resume_global": f"Erreur : {e}",
                "mentions_cee": [], "score_cee": 0, "blocages_cee": [str(e)], "points_attention": []}


# ──────────────────────────────────────────────────────────────────────────────
# CSS — CHARTE ECONOV
# Vert numerique : #61d690  |  Vert plante : #126332  |  Noir : #000  |  Blanc : #fff
# ──────────────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

*, html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif !important;
    box-sizing: border-box;
}
#MainMenu, footer, header { visibility: hidden; }

/* Fond global */
.stApp { background: #f7f9f7; }
.main .block-container {
    max-width: 820px !important;
    padding: 0 1.5rem 5rem !important;
    margin: 0 auto;
}

/* ── HEADER ── */
.eco-header {
    background: #000;
    padding: 1.25rem 2rem;
    border-radius: 0 0 20px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2rem;
}
.eco-logo {
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: 1px;
    color: #fff;
}
.eco-logo span { color: #61d690; }
.eco-header-sub {
    color: rgba(255,255,255,0.55);
    font-size: 0.8rem;
    font-weight: 500;
    letter-spacing: 0.5px;
}

/* ── PROGRESS BAR ── */
.eco-steps {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin-bottom: 2rem;
}
.eco-step {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #bbb;
}
.eco-step.active { color: #000; }
.eco-step.done { color: #126332; }
.eco-dot {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.78rem; font-weight: 700;
    background: #e5e5e5; color: #999;
    flex-shrink: 0;
}
.eco-dot.active { background: #61d690; color: #000; }
.eco-dot.done   { background: #126332; color: #fff; }
.eco-line { width: 40px; height: 2px; background: #e5e5e5; margin: 0 4px; }
.eco-line.done { background: #126332; }

/* ── CARDS ── */
.eco-card {
    background: #fff;
    border-radius: 16px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.25rem;
    border: 1.5px solid #e8f5ee;
    box-shadow: 0 2px 12px rgba(18,99,50,0.05);
}
.eco-card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #000;
    margin-bottom: 1.1rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.eco-card-title .eco-pill {
    background: #61d690;
    color: #000;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 20px;
    letter-spacing: 0.3px;
}

/* ── FICHE BUTTONS ── */
.fiche-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 0.5rem 0; }
.secteur-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #126332;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 1rem 0 0.4rem;
}

/* ── PRIME CARD ── */
.prime-card {
    background: linear-gradient(135deg, #126332, #1e8a48);
    border-radius: 16px;
    padding: 2rem;
    color: #fff;
    text-align: center;
    margin: 1.25rem 0;
    position: relative;
    overflow: hidden;
}
.prime-card::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 150px; height: 150px;
    background: rgba(97,214,144,0.15);
    border-radius: 50%;
}
.prime-card::after {
    content: '';
    position: absolute;
    bottom: -30px; left: -20px;
    width: 100px; height: 100px;
    background: rgba(97,214,144,0.10);
    border-radius: 50%;
}
.prime-montant {
    font-size: 3.2rem;
    font-weight: 800;
    color: #61d690;
    line-height: 1;
    position: relative;
    z-index: 1;
}
.prime-label {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.7);
    margin-top: 0.3rem;
    font-weight: 500;
}
.prime-gisement {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.55);
    margin-top: 0.2rem;
}
.prime-detail {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.45);
    margin-top: 0.5rem;
}
.prime-cdp {
    display: inline-block;
    background: #61d690;
    color: #000;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 12px;
    border-radius: 20px;
    margin-top: 0.75rem;
}

/* ── SCORE RESULT ── */
.score-block {
    border-radius: 14px;
    padding: 1.5rem;
    text-align: center;
    margin-bottom: 1.25rem;
}
.score-block.pass { background: #ecfdf5; border: 1.5px solid #a7f3d0; }
.score-block.warn { background: #fffbeb; border: 1.5px solid #fde68a; }
.score-block.fail { background: #fef2f2; border: 1.5px solid #fecaca; }
.score-num { font-size: 2.8rem; font-weight: 800; line-height: 1; }
.score-num.pass { color: #126332; }
.score-num.warn { color: #d97706; }
.score-num.fail { color: #dc2626; }
.score-lbl { font-size: 0.9rem; font-weight: 600; margin-top: 0.3rem; color: #374151; }

/* ── MENTION ITEMS ── */
.mention-row {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 9px 0; border-bottom: 1px solid #f0f0f0;
    font-size: 0.88rem; color: #111;
}
.mention-row:last-child { border-bottom: none; }
.mention-detail { font-size: 0.78rem; color: #888; margin-top: 2px; }

/* ── UPLOAD ZONE ── */
.upload-zone {
    background: #f7f9f7;
    border: 2px dashed #61d690;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    color: #555;
    font-size: 0.88rem;
    margin: 0.75rem 0;
}

/* ── MESSAGE BOX ── */
.msg-box {
    background: #f7f9f7;
    border: 1.5px solid #e8f5ee;
    border-left: 4px solid #61d690;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    font-size: 0.85rem;
    color: #111;
    white-space: pre-wrap;
    line-height: 1.7;
}

/* ── ABROGATION ── */
.abro-badge {
    background: #fef3c7;
    color: #92400e;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 2px 9px;
    border-radius: 20px;
    margin-left: 6px;
}

/* ── BOUTONS ── */
.stButton > button {
    border-radius: 10px !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"] {
    background: #126332 !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(18,99,50,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #0e4f28 !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
    border: 1.5px solid #126332 !important;
    color: #126332 !important;
    background: transparent !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #ecfdf5 !important;
}

/* Inputs */
.stSelectbox > div > div, .stNumberInput > div > div > input {
    border-radius: 8px !important;
    border-color: #d1e7d8 !important;
    font-family: 'Montserrat', sans-serif !important;
}
.stAlert { border-radius: 10px !important; }

/* Footer */
.eco-footer {
    text-align: center;
    color: #aaa;
    font-size: 0.75rem;
    padding: 2rem 0 1rem;
}
.eco-footer strong { color: #126332; }
</style>
"""

# ──────────────────────────────────────────────────────────────────────────────
# COMPOSANTS HTML
# ──────────────────────────────────────────────────────────────────────────────

def header_html():
    return """
<div class="eco-header">
    <div class="eco-logo"><span>ECO</span>NOV'</div>
    <div class="eco-header-sub">SIMULATEUR CEE &nbsp;&bull;&nbsp; CERTIFICATS D'ECONOMIES D'ENERGIE</div>
</div>
"""

def steps_html(current):
    labels = [("1", "Fiche CEE"), ("2", "Calcul"), ("3", "Resultat")]
    parts = []
    for i, (num, lbl) in enumerate(labels, 1):
        if i < current:
            cls_dot, cls_step, nd = "done", "done", "✓"
        elif i == current:
            cls_dot, cls_step, nd = "active", "active", num
        else:
            cls_dot, cls_step, nd = "", "", num
        parts.append(
            f'<div class="eco-step {cls_step}">'
            f'<div class="eco-dot {cls_dot}">{nd}</div>{lbl}</div>'
        )
        if i < len(labels):
            line_cls = "done" if i < current else ""
            parts.append(f'<div class="eco-line {line_cls}"></div>')
    return f'<div class="eco-steps">{"".join(parts)}</div>'


def prime_html(prime_result):
    prime = prime_result.get("prime", 0)
    gis   = prime_result.get("gisement_mwh", 0)
    det   = prime_result.get("detail", "")
    cdp   = prime_result.get("cdp", False)
    cdp_tag = '<div class="prime-cdp">Coup de Pouce Chauffage x5 inclus</div>' if cdp else ""
    return f"""
<div class="prime-card">
    <div class="prime-montant">{prime:,.0f} EUR</div>
    <div class="prime-label">Prime CEE estimee</div>
    <div class="prime-gisement">{gis} MWhc cumac</div>
    <div class="prime-detail">{det}</div>
    {cdp_tag}
</div>
"""

def score_html(score):
    if score >= 80:   cls, icon = "pass", "✅"
    elif score >= 50: cls, icon = "warn", "⚠️"
    else:             cls, icon = "fail", "❌"
    return f"""
<div class="score-block {cls}">
    <div class="score-num {cls}">{score}%</div>
    <div class="score-lbl">{icon} Conformite CEE du document</div>
</div>
"""


# ──────────────────────────────────────────────────────────────────────────────
# APP
# ──────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Simulateur CEE — Econov'",
        page_icon="🌿",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(header_html(), unsafe_allow_html=True)

    # State
    defaults = {"step": 1, "fiche_id": None, "result": None, "prime_result": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    st.markdown(steps_html(st.session_state.step), unsafe_allow_html=True)
    api_key = get_api_key()

    # ════════════════════════════════════════════
    # ETAPE 1 — Choix de la fiche
    # ════════════════════════════════════════════
    if st.session_state.step == 1:

        st.markdown('<div class="eco-card">', unsafe_allow_html=True)
        st.markdown('<div class="eco-card-title">Choisissez votre type d\'operation <span class="eco-pill">8 fiches disponibles</span></div>', unsafe_allow_html=True)

        secteurs = {}
        for fid, f in FICHES.items():
            secteurs.setdefault(f["secteur"], []).append(fid)

        for secteur, fids in secteurs.items():
            icon_s = FICHES[fids[0]]["icon"]
            st.markdown(f'<div class="secteur-label">{icon_s} {secteur}</div>', unsafe_allow_html=True)
            cols = st.columns(2)
            for i, fid in enumerate(fids):
                fiche = FICHES[fid]
                ab    = fiche.get("abrogation")
                selected = st.session_state.fiche_id == fid
                label = f"{'✓ ' if selected else ''}{fiche['code']} — {fiche['label']}"
                with cols[i % 2]:
                    if st.button(label, key=f"f_{fid}", use_container_width=True,
                                 type="primary" if selected else "secondary"):
                        st.session_state.fiche_id = fid
                        st.rerun()
                    if ab:
                        st.markdown(f'<div style="text-align:center;margin-top:-6px"><span class="abro-badge">Abrogee {ab}</span></div>',
                                    unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.fiche_id:
            fiche = FICHES[st.session_state.fiche_id]
            st.success(f"Operation selectionnee : **{fiche['code']} — {fiche['label']}**")
            st.markdown("")
            if st.button("Calculer ma prime  ➜", type="primary", use_container_width=True):
                st.session_state.step = 2
                st.rerun()
        else:
            st.markdown("")
            st.info("Selectionnez une operation pour continuer.")

    # ════════════════════════════════════════════
    # ETAPE 2 — Calcul + Upload
    # ════════════════════════════════════════════
    elif st.session_state.step == 2:

        fiche = FICHES[st.session_state.fiche_id]
        ab    = fiche.get("abrogation")

        st.markdown(f'<div class="eco-card"><div class="eco-card-title">{fiche["icon"]} {fiche["code"]} — {fiche["label"]}'
                    + (f' <span class="abro-badge">Abrogee {ab}</span>' if ab else '')
                    + '</div>', unsafe_allow_html=True)

        with st.form("form_simu"):
            st.markdown("**Parametres de l'operation**")
            params, prix_cee = formulaire_calcul(st.session_state.fiche_id)

            st.markdown("---")
            st.markdown("**Verifier un document** *(optionnel)*")
            st.caption("Deposez votre devis ou tout autre document du dossier pour en verifier la conformite CEE.")
            st.markdown('<div class="upload-zone">Glissez votre fichier ici (PDF · JPG · PNG)<br><small>1 fichier · 20 Mo max</small></div>',
                        unsafe_allow_html=True)
            uploaded = st.file_uploader("Doc", type=["pdf", "jpg", "jpeg", "png", "webp"],
                                        label_visibility="collapsed")

            with st.expander("Mentions CEE attendues sur ce document"):
                for m in fiche["mentions_cee"]:
                    st.write(f"• {m}")

            go = st.form_submit_button("Calculer + Verifier  ➜", type="primary", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if go:
            st.session_state.prime_result = calculer_prime(st.session_state.fiche_id, params, prix_cee)
            if uploaded and api_key:
                with st.spinner("Analyse du document en cours..."):
                    st.session_state.result = analyze_document(
                        api_key, uploaded.read(), uploaded.name, st.session_state.fiche_id
                    )
            elif uploaded and not api_key:
                st.error("API non configuree.")
                st.session_state.result = None
            else:
                st.session_state.result = None
            st.session_state.step = 3
            st.rerun()

        if st.button("← Retour"):
            st.session_state.step = 1
            st.rerun()

    # ════════════════════════════════════════════
    # ETAPE 3 — Resultats
    # ════════════════════════════════════════════
    elif st.session_state.step == 3:

        fiche        = FICHES[st.session_state.fiche_id]
        prime_result = st.session_state.prime_result or {}
        result       = st.session_state.result

        # ── Prime
        if prime_result.get("prime", 0) > 0:
            st.markdown(prime_html(prime_result), unsafe_allow_html=True)
            rappel = fiche["calcul"].get("rappel", "")
            if rappel:
                st.caption(f"ℹ️ {rappel}")

        # ── Analyse document
        if result:
            score = result.get("score_cee", 0)
            st.markdown(score_html(score), unsafe_allow_html=True)

            # Stats
            mentions = result.get("mentions_cee", [])
            n_ok  = sum(1 for m in mentions if m.get("present"))
            n_blk = len(result.get("blocages_cee", []))

            col1, col2, col3 = st.columns(3)
            col1.metric("Type", result.get("type_document", "?").capitalize())
            col2.metric("Mentions presentes", f"{n_ok} / {len(mentions)}")
            col3.metric("Points bloquants", n_blk)

            # Infos extraites
            infos = {
                "Beneficiaire": result.get("nom_beneficiaire"),
                "Adresse": result.get("adresse_travaux"),
                "SIRET": result.get("siret_entreprise"),
                "Date": result.get("date_document"),
                "RGE": ("OK" if result.get("rge_ok") else "Absent") if result.get("rge_ok") is not None else None,
                "Signature": ("Presente" if result.get("signature_benef") else "Absente") if result.get("signature_benef") is not None else None,
            }
            infos_clean = {k: v for k, v in infos.items() if v}
            if infos_clean:
                with st.expander("Informations extraites du document"):
                    for k, v in infos_clean.items():
                        st.write(f"**{k}** : {v}")

            if result.get("resume_global"):
                st.info(result["resume_global"])

            # Mentions
            st.markdown('<div class="eco-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="eco-card-title">Verification des mentions CEE — {fiche["code"]}</div>',
                        unsafe_allow_html=True)
            for m in mentions:
                present  = m.get("present", False)
                conforme = m.get("conforme")
                icon = "✅" if (present and conforme is not False) else ("⚠️" if present else "❌")
                val  = f" <span style='color:#126332;font-weight:600'>→ {m['valeur']}</span>" if m.get("valeur") else ""
                comm = f"<div class='mention-detail'>{m['commentaire']}</div>" if m.get("commentaire") else ""
                st.markdown(
                    f'<div class="mention-row">'
                    f'<span style="font-size:1rem;flex-shrink:0">{icon}</span>'
                    f'<div><span>{m.get("mention","")}</span>{val}{comm}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

            # Blocages
            for b in result.get("blocages_cee", []):
                st.error(f"🔴 {b}")
            for a in result.get("points_attention", []):
                st.warning(f"🟠 {a}")

        elif not result and prime_result.get("prime", 0) > 0:
            st.success("Prime calculee. Deposez un document a l'etape 2 pour verifier sa conformite.")

        # Message recap
        if result or prime_result.get("prime", 0) > 0:
            st.divider()
            st.markdown('<div class="eco-card-title" style="margin-bottom:0.75rem">Message a envoyer</div>',
                        unsafe_allow_html=True)
            parts = []
            if prime_result.get("prime", 0) > 0:
                parts.append(f"Estimation prime CEE ({fiche['code']}) : {prime_result['prime']:,.0f} EUR")
                parts.append(f"Gisement : {prime_result['gisement_mwh']} MWhc cumac\n")
            if result:
                score = result.get("score_cee", 0)
                parts.append(f"Score de conformite document : {score}/100")
                for b in result.get("blocages_cee", []):
                    parts.append(f"  - BLOQUANT : {b}")
                for a in result.get("points_attention", []):
                    parts.append(f"  - A corriger : {a}")
                parts.append("")
            parts.append("Merci de corriger les points signales avant depot du dossier complet.")
            parts.append("— Econov'")
            st.text_area("", "\n".join(parts), height=180, key="msg_out")
            st.caption("Copiez ce message et transmettez-le a votre installateur.")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Modifier les parametres", use_container_width=True, type="secondary"):
                st.session_state.step = 2
                st.session_state.result = None
                st.rerun()
        with col2:
            if st.button("Nouvelle simulation", use_container_width=True, type="primary"):
                for k in list(defaults.keys()):
                    st.session_state[k] = defaults[k]
                st.rerun()

    # Footer
    st.markdown("""
<div class="eco-footer">
    Simulateur CEE &bull; <strong>Econov'</strong> &bull; Resultats indicatifs, non contractuels
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
