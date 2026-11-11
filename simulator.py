"""
Simulateur CEE — ECONOV'
Version 3 — Design page unique style simulateur-prime-evolution.fr
Fond menthe + card blanc + sections inline + export PDF
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
        "secteur": "Residentiel individuel",
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
        "secteur": "Residentiel individuel",
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
        "secteur": "Residentiel individuel",
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
        "secteur": "Residentiel individuel",
        "abrogation": None,
        "mentions_cee": [
            "Marque et reference de la PAC",
            "Etas >= 126% (BT) ou Etas >= 111% (MHT)",
            "Application : chauffage seul ou chauffage + ECS",
            "Type d'emetteurs (planchers / radiateurs / ventilo-convecteurs)",
            "Zone climatique (H1 / H2 / H3)",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire + date",
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
            "rappel": "Etas >= 126% (BT) ou >= 111% (MHT). CdP x5 si remplacement chaudiere fioul/gaz/charbon.",
        },
    },
    "BAR-TH-179": {
        "label": "PAC collective <= 400 kW",
        "secteur": "Residentiel collectif",
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
        "calcul": {"type": "nc", "rappel": "Contactez Econov' pour le calcul BAR-TH-179."},
    },
    "BAT-TH-163": {
        "label": "PAC air/eau — Tertiaire",
        "secteur": "Tertiaire",
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
        "secteur": "Tertiaire",
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
            "rappel": "Puissance nominale prouvee par la plaque signaletique.",
        },
    },
    "BAT-TH-139": {
        "label": "Recuperation chaleur sur groupe froid",
        "secteur": "Tertiaire",
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
        return {"prime": round(g / 1000 * prix_cee, 2), "gisement_mwh": round(g / 1000, 2),
                "detail": f"{s} m2 x {f} kWhc/m2 (zone {zone})"}

    elif ctype == "pac_residentiel":
        tl  = params.get("type_logement", "Maison individuelle")
        us  = params.get("usage_pac", "Chauffage")
        eta = params.get("etas", 130)
        s   = params.get("surface", 100)
        cdp = params.get("cdp", False)
        mb  = calcul["montants_base"].get(f"{tl}|{us}", [90900, 109200])
        base = mb[1 if eta >= 140 else 0]
        cz   = calcul["coeff_zone"].get(zone, 1.0)
        seuils = calcul["coeff_surface_maison"] if "Maison" in tl else calcul["coeff_surface_appart"]
        cs = seuils[0][1]
        for seuil, c in seuils:
            if s >= seuil: cs = c
        fc = calcul["facteur_cdp"] if cdp else 1
        g  = base * cz * fc
        return {"prime": round(g / 1000 * prix_cee, 2), "gisement_mwh": round(g / 1000, 2),
                "detail": f"Base {base} kWhc x zone {cz} x CdP x{fc}", "cdp": cdp}

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
        return {"prime": round(g / 1000 * prix_cee, 2), "gisement_mwh": round(g / 1000, 2),
                "detail": f"{kwh} kWhc/m2 x {fs} x R{fr} x {s} m2"}

    elif ctype == "puissance_froid":
        app = params.get("application", list(calcul["facteurs"].keys())[0])
        p   = params.get("puissance_kw", 0)
        f   = calcul["facteurs"].get(app, {}).get(zone, 0)
        g   = p * f
        return {"prime": round(g / 1000 * prix_cee, 2), "gisement_mwh": round(g / 1000, 2),
                "detail": f"{p} kW x {f} kWhc/kW (zone {zone})"}

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
        return {"prime": round(g / 1000 * prix_cee, 2), "gisement_mwh": round(g / 1000, 2),
                "detail": f"ECS {round(er * f)} + Ch. {round(cr * f * cc)} kWhc", "p_cap": round(cap, 1)}

    return {"prime": 0, "gisement_mwh": 0, "detail": "Calcul non disponible"}


# ─────────────────────────────────────────────────────────────────────────────
# GENERATION PDF
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf(fiche_id, params, prix_cee, prime_result, result=None, client_name=""):
    try:
        from fpdf import FPDF

        f = FICHES[fiche_id]

        def clean(s):
            """Remplace les caracteres non-latin1."""
            return str(s).encode("latin-1", errors="replace").decode("latin-1")

        class PDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 9)
                self.set_text_color(18, 99, 50)
                self.cell(0, 8, "ECONOV'", align="L")
                self.set_font("Helvetica", "", 7)
                self.set_text_color(150, 150, 150)
                self.set_xy(10, self.get_y())
                self.cell(0, 8, clean(f"Simulateur CEE -- {fiche_id}"), align="R")
                self.ln(3)
                self.set_draw_color(97, 214, 144)
                self.set_line_width(0.8)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(5)

            def footer(self):
                self.set_y(-13)
                self.set_font("Helvetica", "I", 7)
                self.set_text_color(180, 180, 180)
                self.cell(0, 8, "Resultats indicatifs, non contractuels -- Simulateur CEE Econov'", align="C")

        pdf = PDF()
        pdf.set_doc_option("core_fonts_encoding", "windows-1252")
        pdf.set_margins(14, 14, 14)
        pdf.add_page()

        # Titre
        if client_name:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 6, clean(f"Client : {client_name}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 12, clean(f"Simulation {fiche_id}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, clean(f['label']), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # Prime principale
        if prime_result.get("prime", 0) > 0:
            pdf.set_fill_color(240, 250, 244)
            pdf.rect(14, pdf.get_y(), 182, 32, style="F")
            pdf.set_font("Helvetica", "B", 28)
            pdf.set_text_color(18, 99, 50)
            pdf.cell(0, 20, clean(f"{prime_result['prime']:,.2f} EUR"), align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 7, "PRIME CEE ESTIMEE", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(100, 100, 100)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 5, clean(f"Gisement : {prime_result['gisement_mwh']} MWhc cumac -- {prime_result.get('detail', '')}"), align="C", new_x="LMARGIN", new_y="NEXT")
            if prime_result.get("cdp"):
                pdf.set_text_color(18, 99, 50)
                pdf.cell(0, 5, "Coup de Pouce Chauffage x5 inclus", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(6)

        # Parametres
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, "PARAMETRES", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(220, 235, 220)
        pdf.set_line_width(0.3)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(3)

        param_labels = {
            "zone": "Zone climatique",
            "surface": "Surface (m2)",
            "type_logement": "Type de logement",
            "usage_pac": "Usage PAC",
            "etas": "Etas (%)",
            "cdp": "Coup de Pouce",
            "puissance_pac": "Puissance PAC (kW)",
            "etas_ou_cop": "Etas (%) ou COP",
            "facteur_r": "Facteur R",
            "secteur_activite": "Secteur d'activite",
            "application": "Application",
            "puissance_kw": "Puissance (kW)",
            "p_compresseur": "P compresseur (kW)",
            "p_ecs": "P recup ECS (kW)",
            "p_chauffage": "P recup chauffage (kW)",
        }

        pdf.set_font("Helvetica", "", 8)
        rows = []
        for k, v in params.items():
            lbl = param_labels.get(k, k)
            if k == "cdp":
                v = "Oui" if v else "Non"
            rows.append((lbl, str(v)))
        rows.append(("Prix CEE", f"{prix_cee} EUR/MWhc"))

        col_w = 90
        for i in range(0, len(rows), 2):
            r1 = rows[i]
            r2 = rows[i + 1] if i + 1 < len(rows) else None
            pdf.set_text_color(130, 130, 130)
            pdf.cell(col_w, 5, clean(r1[0]))
            if r2:
                pdf.cell(col_w, 5, clean(r2[0]), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(5)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(col_w, 5, clean(r1[1]))
            if r2:
                pdf.cell(col_w, 5, clean(r2[1]), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(5)
            pdf.set_font("Helvetica", "", 8)
            pdf.ln(2)

        pdf.ln(4)

        # Analyse document
        if result:
            score = result.get("score_cee", 0)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 5, "VERIFICATION DOCUMENT", new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(220, 235, 220)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())
            pdf.ln(3)

            if score >= 80:
                sc = (18, 99, 50)
                sv = "Document conforme"
            elif score >= 50:
                sc = (217, 119, 6)
                sv = "Points a corriger"
            else:
                sc = (220, 38, 38)
                sv = "Document non conforme"

            pdf.set_font("Helvetica", "B", 20)
            pdf.set_text_color(*sc)
            pdf.cell(30, 12, clean(f"{score}/100"))
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.set_xy(44, pdf.get_y() + 3)
            pdf.cell(0, 6, clean(sv), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

            for b in result.get("blocages_cee", []):
                pdf.set_text_color(220, 38, 38)
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 5, clean(f"BLOQUANT : {b}"), new_x="LMARGIN", new_y="NEXT")
            for a in result.get("points_attention", []):
                pdf.set_text_color(217, 119, 6)
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 5, clean(f"A corriger : {a}"), new_x="LMARGIN", new_y="NEXT")

            # Mentions
            mentions = result.get("mentions_cee", [])
            if mentions:
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(0, 5, "DETAIL DES MENTIONS CEE", new_x="LMARGIN", new_y="NEXT")
                pdf.set_draw_color(220, 235, 220)
                pdf.line(14, pdf.get_y(), 196, pdf.get_y())
                pdf.ln(3)

                for m in mentions:
                    present  = m.get("present", False)
                    conforme = m.get("conforme")
                    if present and conforme is not False:
                        icon, color = "OK ", (18, 99, 50)
                    elif present:
                        icon, color = "!! ", (217, 119, 6)
                    else:
                        icon, color = "X  ", (220, 38, 38)
                    pdf.set_font("Helvetica", "B", 7)
                    pdf.set_text_color(*color)
                    pdf.cell(8, 5, icon)
                    pdf.set_font("Helvetica", "", 7)
                    pdf.set_text_color(50, 50, 50)
                    val = f" -> {m['valeur']}" if m.get("valeur") else ""
                    pdf.multi_cell(0, 5, clean(f"{m.get('mention', '')}{val}"), new_x="LMARGIN", new_y="NEXT")
        else:
            # Juste les mentions attendues
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 5, "MENTIONS CEE REQUISES SUR LE DOCUMENT", new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(220, 235, 220)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())
            pdf.ln(3)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(70, 70, 70)
            for mention in f["mentions_cee"]:
                pdf.cell(5, 5, "-")
                pdf.multi_cell(0, 5, clean(mention), new_x="LMARGIN", new_y="NEXT")

        return bytes(pdf.output())

    except ImportError:
        return None
    except Exception as e:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE DOCUMENT
# ─────────────────────────────────────────────────────────────────────────────

def encode_file(fb, fn):
    ext = fn.lower().split(".")[-1]
    b64 = base64.standard_b64encode(fb).decode()
    m   = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
           "png": "image/png", "webp": "image/webp"}
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
            content = [{"type": "document", "source": {"type": "base64", "media_type": mt, "data": b64}},
                       {"type": "text", "text": "Analyse."}]
        elif mt:
            content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                       {"type": "text", "text": "Analyse."}]
        else:
            try:
                with pdfplumber.open(io.BytesIO(fb)) as pdf:
                    txt = "\n".join(p.extract_text() or "" for p in pdf.pages)[:8000]
            except Exception:
                txt = ""
            content = [{"type": "text", "text": f"Texte :\n{txt}\nAnalyse."}]

        resp = client.messages.create(model="claude-opus-4-5", max_tokens=2000, system=system,
                                      messages=[{"role": "user", "content": content}])
        raw = re.sub(r"^```json\s*|\s*```$", "", resp.content[0].text.strip())
        return json.loads(raw)
    except Exception as e:
        return {"type_document": "inconnu", "resume_global": f"Erreur : {e}",
                "mentions_cee": [], "score_cee": 0, "blocages_cee": [str(e)], "points_attention": []}


# ─────────────────────────────────────────────────────────────────────────────
# CSS — STYLE PAGE UNIQUE
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
#MainMenu, footer, header, .stDeployButton { visibility: hidden !important; display: none !important; }

/* Fond menthe Econov */
.stApp { background: #daeee4 !important; }

/* Card blanc principal */
.main .block-container {
    background: #ffffff !important;
    border-radius: 28px !important;
    box-shadow: 0 12px 60px rgba(8,50,25,0.12) !important;
    max-width: 1040px !important;
    padding: 0 3rem 4rem !important;
    margin: 1.5rem auto 2rem !important;
    overflow: hidden !important;
}

/* ━━━━━━━━ PAGE HEADER ━━━━━━━━ */
.pg-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2rem 0 1.75rem;
    border-bottom: 1.5px solid #edf2ed;
    margin-bottom: 2rem;
}
.pg-logo {
    font-size: 1.1rem;
    font-weight: 900;
    letter-spacing: 5px;
    color: #111;
    text-transform: uppercase;
}
.pg-logo span { color: #126332; }

/* ━━━━━━━━ PAGE INTRO ━━━━━━━━ */
.pg-eyebrow {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #126332;
    margin-bottom: 0.6rem;
}
.pg-title {
    font-size: 2.8rem;
    font-weight: 900;
    color: #0a0a0a;
    margin: 0 0 0.5rem;
    line-height: 1.1;
    letter-spacing: -1px;
}
.pg-desc {
    font-size: 0.95rem;
    color: #888;
    margin: 0 0 2.5rem;
    font-weight: 500;
}

/* ━━━━━━━━ SECTION SEPARATEURS ━━━━━━━━ */
.section-sep {
    border: none;
    border-top: 1.5px solid #edf2ed;
    margin: 2.25rem 0 1.75rem;
}
.section-title {
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    color: #bbb;
    margin-bottom: 1.5rem;
}

/* ━━━━━━━━ FICHE CARDS (selection) ━━━━━━━━ */
.fiche-sel-active {
    border: 2px solid #126332 !important;
    background: #f1fbf5 !important;
    color: #0a0a0a !important;
}

/* ━━━━━━━━ PARAMETRES ━━━━━━━━ */
.params-grid {
    background: #f9fbf9;
    border: 1.5px solid #e5ede5;
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 0.5rem;
}

/* ━━━━━━━━ RESULTATS ━━━━━━━━ */
.results-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0;
    border: 1.5px solid #e5ede5;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 1.5rem;
}
.result-cell {
    padding: 1.1rem 1.5rem;
    border-right: 1px solid #edf2ed;
}
.result-cell:last-child { border-right: none; }
.result-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #bbb;
    margin-bottom: 0.4rem;
}
.result-value {
    font-size: 1.1rem;
    font-weight: 800;
    color: #111;
}

/* Prime principale */
.prime-main {
    background: #f1fbf5;
    border: 1.5px solid #c8e8d4;
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.prime-main::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(97,214,144,0.2) 0%, transparent 65%);
}
.prime-main-label {
    font-size: 0.65rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #126332;
    margin-bottom: 0.6rem;
    position: relative;
    z-index: 1;
}
.prime-main-amount {
    font-size: 4rem;
    font-weight: 900;
    color: #126332;
    line-height: 1;
    letter-spacing: -2px;
    position: relative;
    z-index: 1;
}
.prime-main-currency {
    font-size: 2rem;
    color: #61d690;
    vertical-align: super;
    margin-right: 4px;
    font-weight: 900;
}
.prime-main-cents {
    font-size: 2rem;
    color: rgba(18,99,50,0.4);
}
.prime-main-sub {
    font-size: 0.8rem;
    color: #888;
    margin-top: 0.6rem;
    position: relative;
    z-index: 1;
}
.prime-main-formula {
    font-size: 0.72rem;
    color: #bbb;
    margin-top: 0.3rem;
    position: relative;
    z-index: 1;
}
.cdp-pill {
    display: inline-block;
    background: #126332;
    color: #fff;
    font-size: 0.7rem;
    font-weight: 800;
    padding: 5px 14px;
    border-radius: 30px;
    margin-top: 0.9rem;
    position: relative;
    z-index: 1;
    letter-spacing: 0.3px;
}

/* Resultat vide */
.prime-empty {
    background: #f9fbf9;
    border: 1.5px dashed #d0ddd0;
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    color: #ccc;
    font-size: 0.88rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
}

/* ━━━━━━━━ ANALYSE DOCUMENT ━━━━━━━━ */
.score-band {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    padding: 1.25rem 1.75rem;
    border-radius: 14px;
    margin-bottom: 1.25rem;
}
.score-band.pass { background: #ecfdf5; border: 1.5px solid #a7f3d0; }
.score-band.warn { background: #fffbeb; border: 1.5px solid #fde68a; }
.score-band.fail { background: #fef2f2; border: 1.5px solid #fecaca; }
.score-num {
    font-size: 2.4rem;
    font-weight: 900;
    line-height: 1;
    white-space: nowrap;
}
.score-band.pass .score-num { color: #126332; }
.score-band.warn .score-num { color: #d97706; }
.score-band.fail .score-num { color: #dc2626; }
.score-verdict { font-size: 0.9rem; font-weight: 700; color: #374151; }
.score-sub { font-size: 0.78rem; color: #888; margin-top: 2px; }

.check-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 7px 0;
    border-bottom: 1px solid #f3f4f3;
    font-size: 0.84rem;
}
.check-row:last-child { border-bottom: none; }
.check-icon { flex-shrink: 0; margin-top: 1px; }
.check-label { color: #111; line-height: 1.4; }
.check-val { color: #126332; font-weight: 700; margin-left: 5px; }
.check-comment { font-size: 0.73rem; color: #aaa; margin-top: 2px; }
.checks-wrap {
    background: #fff;
    border: 1.5px solid #e5ede5;
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    margin-top: 1.25rem;
}

.upload-zone {
    background: #f9fbf9;
    border: 2px dashed #c8e8d4;
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
}
.upload-zone-label {
    font-size: 0.84rem;
    font-weight: 700;
    color: #111;
    margin-bottom: 0.3rem;
}
.upload-zone-hint {
    font-size: 0.77rem;
    color: #aaa;
    margin-bottom: 0.75rem;
}
.opt-pill {
    font-size: 0.6rem;
    font-weight: 800;
    background: #e8f5ed;
    color: #126332;
    padding: 2px 7px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-left: 7px;
    vertical-align: middle;
}

/* ━━━━━━━━ INFOS EXTRAITES ━━━━━━━━ */
.infos-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid #f0f4f0;
    font-size: 0.82rem;
}
.infos-row:last-child { border-bottom: none; }
.infos-k { color: #aaa; font-weight: 600; }
.infos-v { color: #111; font-weight: 700; text-align: right; }

/* ━━━━━━━━ FOOTER ━━━━━━━━ */
.pg-footer {
    text-align: center;
    padding: 2rem 0 0.5rem;
    font-size: 0.72rem;
    color: #ccc;
    font-weight: 500;
}
.pg-footer strong { color: #126332; }

/* ━━━━━━━━ BUTTONS ━━━━━━━━ */
.stButton > button {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    font-size: 0.86rem !important;
    transition: all 0.18s ease !important;
    white-space: pre-wrap !important;
    letter-spacing: 0.1px !important;
    min-height: 44px !important;
    line-height: 1.4 !important;
}
.stButton > button[kind="secondary"] {
    background: #fff !important;
    border: 1.5px solid #d8e8d8 !important;
    color: #374151 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #61d690 !important;
    background: #f4fbf6 !important;
    box-shadow: 0 3px 12px rgba(97,214,144,0.2) !important;
    transform: translateY(-1px) !important;
    color: #111 !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #126332 0%, #0c4b26 100%) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(18,99,50,0.28) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 24px rgba(18,99,50,0.4) !important;
}

/* Download button = style primary */
.stDownloadButton > button {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    font-size: 0.84rem !important;
    background: linear-gradient(135deg, #126332 0%, #0c4b26 100%) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(18,99,50,0.28) !important;
    min-height: 44px !important;
    padding: 0 1.5rem !important;
    transition: all 0.18s !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 24px rgba(18,99,50,0.4) !important;
}

/* ━━━━━━━━ TABS ━━━━━━━━ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    background: transparent !important;
    border-bottom: 2px solid #e5ede5 !important;
    margin-bottom: 1.5rem !important;
}
.stTabs [data-baseweb="tab"] {
    padding: 0.7rem 1.4rem !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
    color: #aaa !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
    transition: all 0.2s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #126332 !important; background: #f4fbf6 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #126332 !important;
    border-bottom-color: #61d690 !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }
.stTabs [data-baseweb="tab-panel"]     { padding: 0 !important; }

/* ━━━━━━━━ INPUTS ━━━━━━━━ */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="number-input"] {
    border-radius: 9px !important;
    border-color: #d5e3d5 !important;
    background: #fff !important;
    font-family: 'Montserrat', sans-serif !important;
}
div[data-baseweb="input"] > div > input,
div[data-baseweb="number-input"] input {
    font-family: 'Montserrat', sans-serif !important;
    font-size: 0.9rem !important;
}
label[data-testid="stWidgetLabel"] p {
    font-family: 'Montserrat', sans-serif !important;
    font-size: 0.7rem !important;
    font-weight: 800 !important;
    color: #666 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
}
.stCheckbox label p {
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    color: #374151 !important;
}
.stAlert { border-radius: 11px !important; }
details > summary {
    font-family: 'Montserrat', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    color: #126332 !important;
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# WIDGETS PARAMETRES (sans form, live)
# ─────────────────────────────────────────────────────────────────────────────

def render_params_widgets(fiche_id):
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
        prix_cee = st.number_input("Prix CEE (EUR/MWhc)", value=prix_ref,
                                    step=0.1, min_value=1.0, max_value=30.0, key="p_prix")

    params = {"zone": zone}

    if ctype == "surface":
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        params["surface"] = st.number_input("Surface isolee (m2)",
                                             value=100.0, min_value=1.0, step=5.0, key="p_surf")

    elif ctype == "pac_residentiel":
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["type_logement"] = st.selectbox("Type de logement",
                                                    ["Maison individuelle", "Appartement"], key="p_tl")
            params["surface"] = st.number_input("Surface (m2)", value=100.0,
                                                 min_value=10.0, step=5.0, key="p_surf")
        with cb:
            params["usage_pac"] = st.selectbox("Usage PAC",
                                                ["Chauffage", "Chauffage + ECS"], key="p_usage")
            params["etas"] = st.number_input("Etas (%)", value=130,
                                              min_value=100, max_value=250, key="p_etas")
        params["cdp"] = st.checkbox(
            "Remplacement chaudiere fioul / gaz / charbon — Coup de Pouce x5", key="p_cdp")

    elif ctype == "pac_tertiaire":
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["puissance_pac"] = st.number_input("Puissance PAC (kW)",
                                                       value=200.0, min_value=1.0, key="p_ppac")
            params["etas_ou_cop"] = st.number_input("Etas (%) ou COP",
                                                     value=130.0, min_value=0.0, key="p_ec")
        with cb:
            params["surface"] = st.number_input("Surface chauffee (m2)",
                                                 value=500.0, step=10.0, key="p_surf")
            params["facteur_r"] = st.slider("Facteur R (part PAC)",
                                            0.0, 1.0, 1.0, 0.05, key="p_fr")
        params["secteur_activite"] = st.selectbox("Secteur d'activite",
                                                   list(calcul["facteur_secteur"].keys()),
                                                   key="p_sa_tert")

    elif ctype == "puissance_froid":
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["application"] = st.selectbox("Application",
                                                  list(calcul["facteurs"].keys()), key="p_app")
        with cb:
            params["puissance_kw"] = st.number_input("Puissance electrique nominale (kW)",
                                                      value=10.0, step=0.5, key="p_pkw")

    elif ctype == "recuperation_froid":
        params["secteur_activite"] = st.selectbox("Secteur",
                                                   list(calcul["facteurs_secteur"].keys()),
                                                   key="p_sa_recup")
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        ca, cb, cc = st.columns(3)
        with ca:
            params["p_compresseur"] = st.number_input("P comp. (kW)",
                                                       value=15.0, step=1.0, key="p_pc")
        with cb:
            params["p_ecs"] = st.number_input("P recup ECS (kW)",
                                               value=0.0, step=0.5, key="p_pe")
        with cc:
            params["p_chauffage"] = st.number_input("P recup Ch. (kW)",
                                                     value=0.0, step=0.5, key="p_pch")

    return params, prix_cee


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    "fiche_id":       None,
    "result":         None,
    "uploaded_bytes": None,
    "uploaded_name":  None,
    "analysis_done":  False,
}


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

    api_key = get_api_key()

    # ─── HEADER ───────────────────────────────────────────
    fiche_id = st.session_state.fiche_id
    prime_result = {}
    params = {}
    prix_cee = 7.0

    # Calcul live si fiche selectionnee
    if fiche_id and FICHES[fiche_id]["calcul"].get("type") != "nc":
        # On a besoin des valeurs de widgets — elles seront lues plus bas
        pass

    col_logo, col_pdf = st.columns([7, 3], gap="medium")
    with col_logo:
        st.markdown(
            '<div class="pg-logo"><span>ECO</span>NOV\'</div>',
            unsafe_allow_html=True,
        )

    # ─── INTRO ────────────────────────────────────────────
    st.markdown("""
<div class="pg-eyebrow">CEE &bull; RENOVATION ENERGETIQUE</div>
<div class="pg-title">Simulateur de prime CEE</div>
<p class="pg-desc">Resultats en temps reel &mdash; Calcul officiel &mdash; Verification IA de documents</p>
""", unsafe_allow_html=True)

    # ─── SECTION : OPERATION ──────────────────────────────
    st.markdown('<hr class="section-sep"><div class="section-title">OPERATION</div>', unsafe_allow_html=True)

    from collections import defaultdict
    secteurs = defaultdict(list)
    for fid, f in FICHES.items():
        secteurs[f["secteur"]].append(fid)

    tabs = st.tabs(list(secteurs.keys()))
    for tab, secteur in zip(tabs, list(secteurs.keys())):
        with tab:
            fids = secteurs[secteur]
            cols = st.columns(2, gap="medium")
            for i, fid in enumerate(fids):
                f  = FICHES[fid]
                ab = f.get("abrogation")
                selected = st.session_state.fiche_id == fid
                icon  = "✓  " if selected else ""
                ab_lbl = f"\n⚠ Abroge le {ab[:7]}" if ab else ""
                btn_lbl = f"{icon}{fid}\n{f['label']}{ab_lbl}"
                with cols[i % 2]:
                    if st.button(btn_lbl, key=f"btn_{fid}", use_container_width=True,
                                 type="primary" if selected else "secondary"):
                        for k in list(st.session_state.keys()):
                            if k.startswith("p_"):
                                del st.session_state[k]
                        st.session_state.fiche_id    = fid
                        st.session_state.result      = None
                        st.session_state.analysis_done = False
                        st.session_state.uploaded_bytes = None
                        st.rerun()

    # ─── SECTION : PARAMETRES ─────────────────────────────
    if st.session_state.fiche_id:
        fiche_id = st.session_state.fiche_id
        f = FICHES[fiche_id]
        ab = f.get("abrogation")

        st.markdown('<hr class="section-sep">', unsafe_allow_html=True)

        col_sec, col_fiche = st.columns([6, 4])
        with col_sec:
            st.markdown('<div class="section-title">PARAMETRES</div>', unsafe_allow_html=True)
        with col_fiche:
            st.markdown(
                f'<div style="text-align:right;font-size:.75rem;font-weight:700;color:#aaa;'
                f'padding-top:.1rem">{fiche_id} &mdash; {f["label"]}</div>',
                unsafe_allow_html=True,
            )

        if ab:
            st.warning(f"⚠️ Cette fiche sera abrogee le **{ab}** — verifiez la date d'engagement.")

        st.markdown('<div class="params-grid">', unsafe_allow_html=True)
        params, prix_cee = render_params_widgets(fiche_id)
        st.markdown('</div>', unsafe_allow_html=True)

        # ─── SECTION : RESULTATS ──────────────────────────
        st.markdown('<hr class="section-sep">', unsafe_allow_html=True)

        prime_result = calculer_prime(fiche_id, params, prix_cee) if params else {}
        prime_val    = prime_result.get("prime", 0)
        gis          = prime_result.get("gisement_mwh", 0)
        detail       = prime_result.get("detail", "")
        cdp          = prime_result.get("cdp", False)

        # En-tete section + bouton PDF
        col_sec2, col_pdf2 = st.columns([5, 5], gap="medium")
        with col_sec2:
            st.markdown('<div class="section-title">RESULTATS</div>', unsafe_allow_html=True)
        with col_pdf2:
            if prime_val > 0:
                result = st.session_state.result
                client_name = ""
                pdf_bytes = generate_pdf(fiche_id, params, prix_cee, prime_result, result, client_name)
                if pdf_bytes:
                    st.download_button(
                        label="📄 Generer PDF",
                        data=pdf_bytes,
                        file_name=f"prime-cee-{fiche_id}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

        # Metriques en grille (style reference)
        if prime_val > 0:
            zone_lbl   = params.get("zone", "—")
            profil_lbl = "Precarite" if st.session_state.get("p_profil") == "Precarite" else "Classique"
            st.markdown(
                f'<div class="results-grid">'
                f'<div class="result-cell"><div class="result-label">ZONE</div>'
                f'<div class="result-value">{zone_lbl}</div></div>'
                f'<div class="result-cell"><div class="result-label">PROFIL</div>'
                f'<div class="result-value">{profil_lbl}</div></div>'
                f'<div class="result-cell"><div class="result-label">GISEMENT</div>'
                f'<div class="result-value">{gis} MWhc</div></div>'
                f'<div class="result-cell"><div class="result-label">PRIX CEE</div>'
                f'<div class="result-value">{prix_cee} EUR/MWh</div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Prime principale
            int_part = f"{int(prime_val):,}".replace(",", "\u202f")
            dec_part = f"{prime_val:.2f}".split(".")[1]
            cdp_html = '<div class="cdp-pill">⚡ Coup de Pouce x5 inclus</div>' if cdp else ""
            rappel   = f["calcul"].get("rappel", "")
            st.markdown(
                f'<div class="prime-main">'
                f'<div class="prime-main-label">Prime CEE estimee</div>'
                f'<div class="prime-main-amount">'
                f'<sup class="prime-main-currency">&#8364;</sup>'
                f'{int_part}<span class="prime-main-cents">,{dec_part}</span>'
                f'</div>'
                f'<div class="prime-main-sub">{gis} MWhc cumac</div>'
                f'<div class="prime-main-formula">{detail}</div>'
                f'{cdp_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if rappel:
                st.caption(f"ℹ️ {rappel}")
            if prime_result.get("p_cap"):
                st.caption(f"Cap Precup max : {prime_result['p_cap']} kW")
        else:
            st.markdown(
                '<div class="prime-empty">Renseignez les parametres ci-dessus pour voir la prime estimee</div>',
                unsafe_allow_html=True,
            )

        # ─── SECTION : DOCUMENT ───────────────────────────
        st.markdown('<hr class="section-sep">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">VERIFICATION DOCUMENT'
            '<span class="opt-pill">Optionnel</span></div>',
            unsafe_allow_html=True,
        )

        # Analyse IA (une seule fois)
        if (st.session_state.uploaded_bytes
                and not st.session_state.analysis_done and api_key):
            with st.spinner("Analyse IA en cours (10-30 s)…"):
                result_ai = analyze_document(api_key, st.session_state.uploaded_bytes,
                                             st.session_state.uploaded_name, fiche_id)
            st.session_state.result        = result_ai
            st.session_state.analysis_done = True
            st.rerun()
        elif st.session_state.uploaded_bytes and not api_key:
            st.error("Cle API non configuree — analyse impossible.")
            st.session_state.uploaded_bytes = None

        result = st.session_state.result

        if result:
            # Afficher resultats analyse
            score     = result.get("score_cee", 0)
            mentions  = result.get("mentions_cee", [])
            blocages  = result.get("blocages_cee", [])
            attentions = result.get("points_attention", [])
            n_ok      = sum(1 for m in mentions if m.get("present"))

            if score >= 80:   cls, verdict = "pass", "✅ Document conforme"
            elif score >= 50: cls, verdict = "warn", "⚠️ Points a corriger"
            else:             cls, verdict = "fail", "❌ Document non conforme"

            st.markdown(
                f'<div class="score-band {cls}">'
                f'<div class="score-num">{score}<span style="font-size:1.1rem;font-weight:700;color:#aaa">/100</span></div>'
                f'<div><div class="score-verdict">{verdict}</div>'
                f'<div class="score-sub">{n_ok}/{len(mentions)} mentions presentes &bull; '
                f'{len(blocages)} point(s) bloquant(s)</div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if result.get("resume_global"):
                st.info(result["resume_global"])

            # Infos extraites
            infos = {k: v for k, v in {
                "Beneficiaire": result.get("nom_beneficiaire"),
                "Adresse":      result.get("adresse_travaux"),
                "SIRET":        result.get("siret_entreprise"),
                "Date":         result.get("date_document"),
                "RGE":    "OK" if result.get("rge_ok") else ("Absent" if result.get("rge_ok") is not None else None),
                "Signature": "Presente" if result.get("signature_benef") else ("Absente" if result.get("signature_benef") is not None else None),
            }.items() if v}

            if infos or mentions:
                col_info, col_checks = st.columns([4, 6])
                with col_info:
                    if infos:
                        rows = "".join(
                            f'<div class="infos-row">'
                            f'<span class="infos-k">{k}</span>'
                            f'<span class="infos-v">{v}</span></div>'
                            for k, v in infos.items()
                        )
                        st.markdown(
                            f'<div style="border:1.5px solid #e5ede5;border-radius:12px;'
                            f'padding:1rem 1.25rem">{rows}</div>',
                            unsafe_allow_html=True,
                        )
                with col_checks:
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
                                f'<div><div class="check-label">{m.get("mention","")}{val_html}</div>{comm_html}</div>'
                                f'</div>'
                            )
                        st.markdown(f'<div class="checks-wrap">{rows_html}</div>', unsafe_allow_html=True)

            for b in blocages:
                st.error(f"🔴 {b}")
            for a in attentions:
                st.warning(f"🟠 {a}")

            # Bouton reset analyse
            st.markdown('<div style="height:.75rem"></div>', unsafe_allow_html=True)
            col_reset, _ = st.columns([3, 7])
            with col_reset:
                if st.button("Analyser un autre document", use_container_width=True):
                    st.session_state.result        = None
                    st.session_state.analysis_done = False
                    st.session_state.uploaded_bytes = None
                    st.rerun()
        else:
            # Upload zone
            st.markdown("""
<div class="upload-zone">
  <div class="upload-zone-label">📄 Deposez un devis, facture ou attestation</div>
  <div class="upload-zone-hint">Analyse IA de conformite CEE &mdash; PDF, JPG, PNG &mdash; 20 Mo max</div>
</div>
""", unsafe_allow_html=True)
            uploaded = st.file_uploader("", type=["pdf", "jpg", "jpeg", "png", "webp"],
                                        label_visibility="collapsed")
            if uploaded:
                st.caption(f"✓ **{uploaded.name}** · {uploaded.size // 1024} Ko")
                if st.button("Analyser ce document →", type="primary", use_container_width=True):
                    st.session_state.uploaded_bytes = uploaded.read()
                    st.session_state.uploaded_name  = uploaded.name
                    st.session_state.analysis_done  = False
                    st.session_state.result         = None
                    st.rerun()

            with st.expander(f"Voir les {len(f['mentions_cee'])} mentions CEE requises pour {fiche_id}"):
                for m in f["mentions_cee"]:
                    st.write(f"→ {m}")

    else:
        # Aucune fiche selectionnee
        st.markdown("""
<hr class="section-sep">
<div style="text-align:center;padding:3rem 2rem;color:#ccc;">
  <div style="font-size:2rem;margin-bottom:.75rem">👆</div>
  <div style="font-size:.95rem;font-weight:600">Selectionnez une operation ci-dessus pour estimer votre prime CEE</div>
</div>
""", unsafe_allow_html=True)

    # Footer
    st.markdown("""
<div class="pg-footer">
  Simulateur CEE &bull; <strong>Econov'</strong> &bull;
  Resultats indicatifs, non contractuels &bull; Analyse IA par Claude (Anthropic)
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
