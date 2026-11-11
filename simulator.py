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
# PARTENAIRES CEE — Cadres de contribution BAR-TH-171 (residentiel)
# ─────────────────────────────────────────────────────────────────────────────

# mode "fixe"  : le client recoit X €/MWhc (valeur fixe), le reste a l'installateur
# mode "pct"   : le client recoit X % de la prime totale

PARTENAIRES = {
    "Drapo": {
        "mode":  "fixe",
        "valeur": 3.0,
        "desc":  "Drapo — 3,00 €/MWhc au client (montant fixe)",
        "site":  "www.drapo.com",
    },
    "Picoty": {
        "mode":  "pct",
        "valeur": 50.0,
        "desc":  "Picoty — 50 % de la prime au client",
        "site":  "www.picoty.fr",
    },
    "Personnalise": {
        "mode":  "libre",
        "valeur": None,
        "desc":  "Saisie libre par le professionnel",
        "site":  "",
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
            return str(s).encode("latin-1", errors="replace").decode("latin-1")

        # ── Couleurs Econov ──────────────────────────────────────────────────
        C_VERT_FONCE  = (18, 99, 50)    # #126332
        C_VERT_CLAIR  = (97, 214, 144)  # #61d690
        C_VERT_BG     = (241, 251, 245) # fond vert tres pale
        C_GRIS_TITRE  = (160, 160, 160)
        C_GRIS_TEXTE  = (80, 80, 80)
        C_NOIR        = (20, 20, 20)
        C_ROUGE       = (220, 38, 38)
        C_ORANGE      = (217, 119, 6)
        C_SEP         = (225, 237, 225)

        MARGIN = 14
        PAGE_W = 210 - 2 * MARGIN  # 182 mm

        def section_title(pdf, label):
            """Separateur + titre de section style uppercase gris."""
            pdf.set_draw_color(*C_SEP)
            pdf.set_line_width(0.4)
            pdf.line(MARGIN, pdf.get_y(), 210 - MARGIN, pdf.get_y())
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(0, 5, clean(label), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        class PDF(FPDF):
            def footer(self):
                self.set_y(-11)
                self.set_draw_color(*C_SEP)
                self.set_line_width(0.3)
                self.line(MARGIN, self.get_y(), 210 - MARGIN, self.get_y())
                self.ln(1)
                self.set_font("Helvetica", "I", 6.5)
                self.set_text_color(190, 190, 190)
                self.cell(0, 5,
                    "Resultats indicatifs, non contractuels — Simulateur CEE Econov'  |  Page "
                    + str(self.page_no()),
                    align="C"
                )

        pdf = PDF()
        pdf.set_doc_option("core_fonts_encoding", "windows-1252")
        pdf.set_margins(MARGIN, 0, MARGIN)
        pdf.add_page()

        # ── HEADER BANDE VERTE ───────────────────────────────────────────────
        pdf.set_fill_color(*C_VERT_FONCE)
        pdf.rect(0, 0, 210, 22, style="F")
        # Logo Econov a gauche
        pdf.set_xy(MARGIN, 7)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(50, 8, "ECONOV'", align="L")
        # Simulateur CEE a droite
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(180, 230, 200)
        pdf.set_xy(MARGIN + 50, 7)
        pdf.cell(PAGE_W - 50, 8, clean(f"Simulateur CEE — {fiche_id}"), align="R")
        # Sous-titre fiche
        pdf.set_xy(MARGIN, 15)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(160, 220, 185)
        pdf.cell(PAGE_W, 5, clean(f["label"]), align="L")

        pdf.set_y(26)
        pdf.set_margins(MARGIN, MARGIN, MARGIN)

        # ── INFOS CLIENT + DATE ──────────────────────────────────────────────
        import datetime
        date_str = datetime.date.today().strftime("%d/%m/%Y")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*C_GRIS_TEXTE)
        if client_name:
            pdf.cell(PAGE_W // 2, 5, clean(f"Client : {client_name}"), align="L")
        else:
            pdf.cell(PAGE_W // 2, 5, "")
        pdf.cell(PAGE_W // 2, 5, clean(f"Date : {date_str}"), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # ── BLOC PRIME PRINCIPALE ────────────────────────────────────────────
        prime_val = prime_result.get("prime", 0)
        if prime_val > 0:
            box_h = 38 if prime_result.get("cdp") else 30
            y0 = pdf.get_y()
            # Fond vert pale
            pdf.set_fill_color(*C_VERT_BG)
            pdf.set_draw_color(*C_VERT_CLAIR)
            pdf.set_line_width(0.5)
            pdf.rect(MARGIN, y0, PAGE_W, box_h, style="FD")

            # Label
            pdf.set_xy(MARGIN, y0 + 5)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(PAGE_W, 5, "PRIME CEE ESTIMEE", align="C", new_x="LMARGIN", new_y="NEXT")

            # Montant
            pdf.set_font("Helvetica", "B", 32)
            pdf.set_text_color(*C_VERT_FONCE)
            montant_str = f"{prime_val:,.2f} EUR".replace(",", " ")
            pdf.cell(PAGE_W, 14, clean(montant_str), align="C", new_x="LMARGIN", new_y="NEXT")

            # Detail gisement
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(*C_GRIS_TEXTE)
            detail_str = clean(
                f"Gisement : {prime_result.get('gisement_mwh', 0)} MWhc cumac  |  "
                f"{prime_result.get('detail', '')}  |  Prix : {prix_cee} EUR/MWhc"
            )
            pdf.cell(PAGE_W, 5, detail_str, align="C", new_x="LMARGIN", new_y="NEXT")

            # Badge Coup de Pouce
            if prime_result.get("cdp"):
                pdf.ln(1)
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(255, 255, 255)
                pdf.set_fill_color(*C_VERT_FONCE)
                pdf.cell(PAGE_W, 7, "  COUP DE POUCE CHAUFFAGE x5 INCLUS  ",
                         align="C", fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_y(y0 + box_h + 6)

        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(0, 8, "Aucune prime calculee.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # ── REPARTITION CLIENT / INSTALLATEUR ────────────────────────────────
        part_cl = prime_result.get("part_client")
        part_in = prime_result.get("part_instal")
        partenaire_pdf = prime_result.get("partenaire", "")
        prix_cl_mwh    = prime_result.get("prix_client_mwh", 0)

        if part_cl is not None and prime_val > 0:
            section_title(pdf, "REPARTITION DE LA PRIME")
            pct_cl = round(part_cl / prime_val * 100, 1)
            pct_in = round(100 - pct_cl, 1)
            half   = PAGE_W / 2 - 2

            y_rep = pdf.get_y()

            # Bloc client (vert)
            pdf.set_fill_color(*C_VERT_BG)
            pdf.set_draw_color(*C_VERT_CLAIR)
            pdf.set_line_width(0.5)
            pdf.rect(MARGIN, y_rep, half, 24, style="FD")
            pdf.set_xy(MARGIN + 3, y_rep + 3)
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(half - 6, 4, clean(f"PART CLIENT  ({pct_cl}%)"))
            pdf.set_xy(MARGIN + 3, y_rep + 8)
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*C_VERT_FONCE)
            pdf.cell(half - 6, 10, clean(f"{part_cl:,.2f} EUR".replace(",", " ")))
            pdf.set_xy(MARGIN + 3, y_rep + 19)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(half - 6, 4, clean(f"{prix_cl_mwh} EUR/MWhc — {partenaire_pdf}"))

            # Bloc installateur (gris)
            x2 = MARGIN + half + 4
            pdf.set_fill_color(249, 251, 249)
            pdf.set_draw_color(*C_SEP)
            pdf.rect(x2, y_rep, half, 24, style="FD")
            pdf.set_xy(x2 + 3, y_rep + 3)
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(half - 6, 4, clean(f"PART INSTALLATEUR  ({pct_in}%)"))
            pdf.set_xy(x2 + 3, y_rep + 8)
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*C_NOIR)
            prix_in_mwh = round(prime_result.get("gisement_mwh", 0) and
                                (part_in / prime_result.get("gisement_mwh", 1)), 2)
            pdf.cell(half - 6, 10, clean(f"{part_in:,.2f} EUR".replace(",", " ")))
            pdf.set_xy(x2 + 3, y_rep + 19)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(half - 6, 4, clean("Marge Econov'"))

            pdf.set_y(y_rep + 28)

        # ── PARAMETRES ───────────────────────────────────────────────────────
        section_title(pdf, "PARAMETRES DE SIMULATION")

        param_labels = {
            "zone":            "Zone climatique",
            "surface":         "Surface (m2)",
            "type_logement":   "Type de logement",
            "usage_pac":       "Usage PAC",
            "etas":            "Etas (%)",
            "cdp":             "Coup de Pouce",
            "puissance_pac":   "Puissance PAC (kW)",
            "etas_ou_cop":     "Etas (%) ou COP",
            "facteur_r":       "Facteur R",
            "secteur_activite":"Secteur d'activite",
            "application":     "Application",
            "puissance_kw":    "Puissance (kW)",
            "p_compresseur":   "P compresseur (kW)",
            "p_ecs":           "P recup ECS (kW)",
            "p_chauffage":     "P recup chauffage (kW)",
        }

        # Exclure les cles de repartition (affichees dans leur propre bloc)
        EXCLUDE_PARAMS = {"prix_client_mwh", "partenaire"}
        rows = []
        for k, v in params.items():
            if k in EXCLUDE_PARAMS:
                continue
            lbl = param_labels.get(k, k)
            if k == "cdp":
                v = "Oui — x5" if v else "Non"
            rows.append((lbl, str(v)))
        rows.append(("Prix CEE", f"{prix_cee} EUR/MWhc"))

        col_w = PAGE_W / 2
        row_h_lbl = 4
        row_h_val = 5.5
        pdf.set_x(MARGIN)

        for i in range(0, len(rows), 2):
            r1 = rows[i]
            r2 = rows[i + 1] if i + 1 < len(rows) else None

            # Labels (gris, petite casse)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(col_w, row_h_lbl, clean(r1[0]))
            pdf.cell(col_w, row_h_lbl, clean(r2[0]) if r2 else "",
                     new_x="LMARGIN", new_y="NEXT")

            # Valeurs (noir, gras)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*C_NOIR)
            pdf.cell(col_w, row_h_val, clean(r1[1]))
            pdf.cell(col_w, row_h_val, clean(r2[1]) if r2 else "",
                     new_x="LMARGIN", new_y="NEXT")

            # Separateur leger
            pdf.set_draw_color(*C_SEP)
            pdf.set_line_width(0.2)
            pdf.line(MARGIN, pdf.get_y(), 210 - MARGIN, pdf.get_y())
            pdf.ln(1.5)

        pdf.ln(4)

        # ── ANALYSE DOCUMENT ─────────────────────────────────────────────────
        if result:
            score = result.get("score_cee", 0)
            section_title(pdf, "VERIFICATION DOCUMENT")

            if score >= 80:
                fill_col = (236, 253, 245)
                border_col = (167, 243, 208)
                txt_col = C_VERT_FONCE
                sv = "Document conforme"
            elif score >= 50:
                fill_col = (255, 251, 235)
                border_col = (253, 230, 138)
                txt_col = C_ORANGE
                sv = "Points a corriger"
            else:
                fill_col = (254, 242, 242)
                border_col = (254, 202, 202)
                txt_col = C_ROUGE
                sv = "Document non conforme"

            # Bande de score
            y_sc = pdf.get_y()
            pdf.set_fill_color(*fill_col)
            pdf.set_draw_color(*border_col)
            pdf.set_line_width(0.5)
            pdf.rect(MARGIN, y_sc, PAGE_W, 18, style="FD")
            pdf.set_xy(MARGIN + 4, y_sc + 2)
            pdf.set_font("Helvetica", "B", 22)
            pdf.set_text_color(*txt_col)
            pdf.cell(28, 14, clean(f"{score}"))
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*C_GRIS_TITRE)
            pdf.cell(10, 14, "/100")
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*txt_col)
            pdf.cell(0, 14, clean(sv))
            pdf.set_y(y_sc + 20)

            # Blocages
            for b in result.get("blocages_cee", []):
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*C_ROUGE)
                pdf.cell(14, 5, "BLOQUANT")
                pdf.set_font("Helvetica", "", 7.5)
                pdf.set_text_color(*C_GRIS_TEXTE)
                pdf.multi_cell(PAGE_W - 14, 5, clean(b), new_x="LMARGIN", new_y="NEXT")

            for a in result.get("points_attention", []):
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*C_ORANGE)
                pdf.cell(14, 5, "ATTENTION")
                pdf.set_font("Helvetica", "", 7.5)
                pdf.set_text_color(*C_GRIS_TEXTE)
                pdf.multi_cell(PAGE_W - 14, 5, clean(a), new_x="LMARGIN", new_y="NEXT")

            # Mentions CEE
            mentions = result.get("mentions_cee", [])
            if mentions:
                pdf.ln(4)
                section_title(pdf, "DETAIL DES MENTIONS CEE")
                for m in mentions:
                    present  = m.get("present", False)
                    conforme = m.get("conforme")
                    if present and conforme is not False:
                        icon, color = "OK", C_VERT_FONCE
                    elif present:
                        icon, color = "!!", C_ORANGE
                    else:
                        icon, color = "X", C_ROUGE
                    pdf.set_font("Helvetica", "B", 7.5)
                    pdf.set_text_color(*color)
                    pdf.cell(10, 5, icon)
                    pdf.set_font("Helvetica", "", 7.5)
                    pdf.set_text_color(*C_GRIS_TEXTE)
                    val = clean(f" → {m['valeur']}") if m.get("valeur") else ""
                    pdf.multi_cell(PAGE_W - 10, 5,
                                   clean(f"{m.get('mention', '')}{val}"),
                                   new_x="LMARGIN", new_y="NEXT")
        else:
            # Mentions requises sans analyse
            section_title(pdf, "MENTIONS CEE REQUISES SUR LE DOCUMENT")
            for mention in f["mentions_cee"]:
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(*C_GRIS_TEXTE)
                pdf.cell(6, 5, "-")
                pdf.multi_cell(PAGE_W - 6, 5, clean(mention), new_x="LMARGIN", new_y="NEXT")

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
/* Toggle Coup de Pouce */
.stToggle label p {
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    color: #374151 !important;
}
[data-testid="stToggle"] > label > div[role="checkbox"][aria-checked="true"] {
    background-color: #126332 !important;
}
[data-testid="stToggle"] > label > div[role="checkbox"] {
    border-color: #d97706 !important;
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
    # Prix auto par profil : 7.2 classique / 13.0 precarite — reset si profil change
    prix_default = 13.0 if profil == "Precarite" else 7.2
    if st.session_state.get("p_profil_prev") != profil:
        st.session_state["p_prix"] = prix_default
    st.session_state["p_profil_prev"] = profil
    with c3:
        prix_cee = st.number_input("Prix CEE (EUR/MWhc)", value=prix_default,
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
            # Selecteur tranches officielles BAR-TH-171
            etas_opts = {
                "MHT — Etas 111 a 126 % (tres haute temp.)":  115,
                "BT — Etas 126 a 140 % (basse temp.)":        130,
                "BT HP — Etas >= 140 % (haute performance)":  145,
            }
            etas_sel = st.selectbox("Performance Etas (tranche officielle)",
                                    list(etas_opts.keys()), index=1, key="p_etas_tr")
            params["etas"] = etas_opts[etas_sel]

        # CDP — toggle proement avec baniere visible
        st.markdown("""
<div style="background:#fffbeb;border:2px solid #fde68a;border-radius:14px;
padding:1rem 1.25rem;margin:1.25rem 0 0.5rem;display:flex;align-items:center;gap:1rem">
<div style="font-size:1.6rem;line-height:1">&#128293;</div>
<div style="flex:1">
<div style="font-size:0.68rem;font-weight:800;color:#d97706;text-transform:uppercase;
letter-spacing:1.5px;margin-bottom:3px">COUP DE POUCE CHAUFFAGE — Prime x5</div>
<div style="font-size:0.82rem;color:#374151;font-weight:600;line-height:1.4">
Remplacement d'une chaudiere au fioul, gaz ou charbon existante</div>
</div>
</div>
""", unsafe_allow_html=True)
        params["cdp"] = st.toggle(
            "Activer le Coup de Pouce Chauffage (x5)", key="p_cdp",
            help="La prime est multipliee par 5 en cas de remplacement d'une chaudiere fioul/gaz/charbon."
        )

        # ── REPARTITION DE LA PRIME ─────────────────────────────────────────
        st.markdown("""
<div style="margin-top:1.25rem;margin-bottom:0.25rem;">
<span style="font-size:0.68rem;font-weight:800;text-transform:uppercase;
letter-spacing:2px;color:#bbb">REPARTITION DE LA PRIME</span>
</div>""", unsafe_allow_html=True)

        cp1, cp2, cp3 = st.columns([3, 3, 4])
        with cp1:
            partenaire_sel = st.selectbox(
                "Partenaire CEE",
                list(PARTENAIRES.keys()),
                key="p_partenaire",
                help="Selectionner le pollueur obligé — pre-remplit la part client selon son cadre de contribution."
            )
        ptn = PARTENAIRES[partenaire_sel]

        # Calcul du prix client par defaut selon le mode du partenaire
        if ptn["mode"] == "fixe":
            default_prix_client = float(ptn["valeur"])
            help_txt = f"{partenaire_sel} : {ptn['valeur']} EUR/MWhc fixes au client"
        elif ptn["mode"] == "pct":
            default_prix_client = round(prix_cee * ptn["valeur"] / 100.0, 2)
            help_txt = f"{partenaire_sel} : {ptn['valeur']}% de {prix_cee} EUR/MWhc"
        else:
            default_prix_client = round(prix_cee * 0.5, 2)
            help_txt = "Saisie libre — ajustez la part client"

        # Reset si partenaire change
        if st.session_state.get("p_partenaire_prev") != partenaire_sel:
            st.session_state["p_prix_client"] = default_prix_client
        st.session_state["p_partenaire_prev"] = partenaire_sel

        with cp2:
            prix_client_mwh = st.number_input(
                "Part client (EUR/MWhc)",
                value=default_prix_client,
                min_value=0.0,
                max_value=float(prix_cee),
                step=0.1,
                key="p_prix_client",
                help=help_txt,
            )
        with cp3:
            prix_instal_mwh = round(prix_cee - prix_client_mwh, 2)
            pct_client = round(prix_client_mwh / prix_cee * 100, 1) if prix_cee > 0 else 0
            st.markdown(
                f'<div style="padding-top:1.6rem;font-size:0.82rem;color:#555;font-weight:600">'
                f'Client : <strong style="color:#126332">{pct_client}%</strong>'
                f'&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'Installateur : <strong style="color:#374151">{round(100-pct_client,1)}%</strong>'
                f'&nbsp;&nbsp;({prix_instal_mwh} EUR/MWhc)</div>',
                unsafe_allow_html=True,
            )
        params["prix_client_mwh"] = prix_client_mwh
        params["partenaire"]      = partenaire_sel

    elif ctype == "pac_tertiaire":
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            params["puissance_pac"] = st.number_input("Puissance PAC (kW)",
                                                       value=200.0, min_value=1.0, key="p_ppac")
            puissance_val = params["puissance_pac"]
            if puissance_val <= 400:
                # Tranches Etas officielles BAT-TH-163 (<=400 kW)
                etas_tert_opts = {
                    "Etas 111 % a 126 % (seuil minimum)": 115,
                    "Etas 126 % a 175 % (performance standard)": 140,
                    "Etas >= 175 % (tres haute performance)": 180,
                }
                etas_sel_t = st.selectbox("Tranche Etas (<=400 kW)",
                                          list(etas_tert_opts.keys()), key="p_ec_tr")
                params["etas_ou_cop"] = float(etas_tert_opts[etas_sel_t])
            else:
                # COP pour puissance >400 kW
                cop_opts = {
                    "COP 4 a 5 (standard)":    4.5,
                    "COP >= 5 (haute perf)":   5.5,
                }
                cop_sel = st.selectbox("Tranche COP (>400 kW)",
                                       list(cop_opts.keys()), key="p_ec_tr")
                params["etas_ou_cop"] = float(cop_opts[cop_sel])
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

        # Repartition client / installateur (uniquement si partenaire renseigne)
        part_client = None
        part_instal = None
        if "prix_client_mwh" in params and gis > 0 and prime_val > 0:
            part_client = round(gis * params["prix_client_mwh"], 2)
            part_instal = round(prime_val - part_client, 2)

        # En-tete section + bouton PDF
        col_sec2, col_pdf2 = st.columns([5, 5], gap="medium")
        with col_sec2:
            st.markdown('<div class="section-title">RESULTATS</div>', unsafe_allow_html=True)
        with col_pdf2:
            if prime_val > 0:
                result = st.session_state.result
                client_name = ""
                # Injecter la repartition dans prime_result pour le PDF
                if part_client is not None:
                    prime_result["part_client"]    = part_client
                    prime_result["part_instal"]    = part_instal
                    prime_result["partenaire"]     = params.get("partenaire", "")
                    prime_result["prix_client_mwh"]= params.get("prix_client_mwh", 0)
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

            # Repartition client / installateur
            if part_client is not None:
                partenaire_lbl = params.get("partenaire", "")
                pct_cl = round(part_client / prime_val * 100, 1) if prime_val > 0 else 0
                pct_in = round(100 - pct_cl, 1)
                col_cl, col_in = st.columns(2, gap="medium")
                with col_cl:
                    st.markdown(
                        f'<div style="background:#f1fbf5;border:1.5px solid #c8e8d4;border-radius:14px;'
                        f'padding:1.1rem 1.4rem;text-align:center">'
                        f'<div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;'
                        f'letter-spacing:1.5px;color:#126332;margin-bottom:0.4rem">'
                        f'PART CLIENT &nbsp;<span style="font-weight:500;color:#aaa">({pct_cl}%)</span></div>'
                        f'<div style="font-size:1.9rem;font-weight:900;color:#126332;letter-spacing:-1px">'
                        f'{part_client:,.2f} <span style="font-size:1rem">EUR</span></div>'
                        f'<div style="font-size:0.72rem;color:#aaa;margin-top:0.3rem">'
                        f'{params.get("prix_client_mwh",0)} EUR/MWhc — via {partenaire_lbl}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_in:
                    instal_per_mwh = round(prix_cee - params.get("prix_client_mwh", 0), 2)
                    st.markdown(
                        f'<div style="background:#f9fbf9;border:1.5px solid #e5ede5;border-radius:14px;'
                        f'padding:1.1rem 1.4rem;text-align:center">'
                        f'<div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;'
                        f'letter-spacing:1.5px;color:#374151;margin-bottom:0.4rem">'
                        f'PART INSTALLATEUR &nbsp;<span style="font-weight:500;color:#aaa">({pct_in}%)</span></div>'
                        f'<div style="font-size:1.9rem;font-weight:900;color:#374151;letter-spacing:-1px">'
                        f'{part_instal:,.2f} <span style="font-size:1rem">EUR</span></div>'
                        f'<div style="font-size:0.72rem;color:#aaa;margin-top:0.3rem">'
                        f'{instal_per_mwh} EUR/MWhc — marge Econov</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
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
