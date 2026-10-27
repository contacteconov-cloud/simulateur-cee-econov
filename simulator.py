"""
Simulateur CEE Econov
Calcul de prime estimee + verification document en 3 etapes.
Donnees extraites des simulateurs Excel B2C et B2B Econov.
"""

import streamlit as st
import anthropic
import base64
import json
import re
import pdfplumber
import io

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG API
# ──────────────────────────────────────────────────────────────────────────────

def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return ""

# ──────────────────────────────────────────────────────────────────────────────
# POLLUEURS
# ──────────────────────────────────────────────────────────────────────────────

POLLUEURS = {
    "PICOTY": {
        "label": "PICOTY / EVELA",
        "emoji": "🔵",
        "prix_cee_ref": {"classique": 7.5, "precarite": 12.5},
        "exigences": [
            "Application photo Rhinocertification imposee",
            "Cadre de contribution PICOTY/EVELA signe avant engagement",
            "Residence principale requise (Coup de Pouce)",
            "Mention Coup de Pouce Chauffage sur le devis",
        ],
        "app_photo": "Rhinocertification",
    },
    "ENGIE": {
        "label": "ENGIE",
        "emoji": "🟢",
        "prix_cee_ref": {"classique": 7.3, "precarite": 12.0},
        "exigences": [
            "Cadre de contribution ENGIE signe selon process interne",
            "Photos horodatees/geolocalisees exigees",
        ],
        "app_photo": None,
    },
    "TOTALENERGIES": {
        "label": "TotalEnergies",
        "emoji": "🔴",
        "prix_cee_ref": {"classique": 7.2, "precarite": 11.8},
        "exigences": [
            "Cadre de contribution TotalEnergies requis",
            "Photos AVANT / APRES obligatoires",
        ],
        "app_photo": None,
    },
    "EDF": {
        "label": "EDF",
        "emoji": "🔷",
        "prix_cee_ref": {"classique": 7.0, "precarite": 11.5},
        "exigences": [
            "Cadre de contribution EDF signe",
            "Devis avec mentions EDF Coup de Pouce",
        ],
        "app_photo": None,
    },
    "BUTAGAZ": {
        "label": "Butagaz",
        "emoji": "🟠",
        "prix_cee_ref": {"classique": 7.2, "precarite": 11.5},
        "exigences": ["Cadre de contribution Butagaz requis"],
        "app_photo": None,
    },
    "ANTARGAZ": {
        "label": "Antargaz",
        "emoji": "🟡",
        "prix_cee_ref": {"classique": 7.0, "precarite": 11.0},
        "exigences": ["Cadre de contribution Antargaz requis"],
        "app_photo": None,
    },
    "PRIMAGAZ": {
        "label": "Primagaz",
        "emoji": "🟣",
        "prix_cee_ref": {"classique": 7.0, "precarite": 11.0},
        "exigences": ["Cadre de contribution Primagaz requis"],
        "app_photo": None,
    },
    "OCTOPUS": {
        "label": "Octopus Energy",
        "emoji": "🩷",
        "prix_cee_ref": {"classique": 7.0, "precarite": 11.0},
        "exigences": ["Cadre de contribution Octopus requis"],
        "app_photo": None,
    },
    "AUTRE": {
        "label": "Autre / Je ne sais pas",
        "emoji": "⚪",
        "prix_cee_ref": {"classique": 7.0, "precarite": 11.0},
        "exigences": [],
        "app_photo": None,
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# FICHES & CALCUL CEE
# Donnees extraites des simulateurs Excel Econov (B2C v2026-11, B2B v5)
# ──────────────────────────────────────────────────────────────────────────────

FICHES = {
    # ── RESIDENTIEL INDIVIDUEL ────────────────────────────────────────────────
    "BAR-EN-101": {
        "label": "BAR-EN-101 — Isolation combles perdus / rampants",
        "secteur": "Residentiel individuel",
        "abrogation": "01/05/2027",
        "mentions_cee": [
            "Marque et reference de l'isolant",
            "Resistance thermique R >= 7 m2K/W (combles perdus) ou R >= 6 (rampants)",
            "Surface isolee en m2",
            "Type de combles : combles perdus ou rampants",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire + date",
        ],
        "calcul": {
            "type": "surface",
            "inputs": ["zone", "surface", "beneficiaire"],
            "facteurs": {"H1": 1700, "H2": 1400, "H3": 920},
            "prix_ref": {"classique": 7.3, "precarite": 12.5},
            "multiplicateur": 1,
            "rappel": "R mini : 7 m2K/W (combles perdus), 6 m2K/W (rampants)",
        },
    },
    "BAR-EN-102": {
        "label": "BAR-EN-102 — Isolation des murs (ITI/ITE)",
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
            "inputs": ["zone", "surface", "beneficiaire"],
            "facteurs": {"H1": 1600, "H2": 1300, "H3": 880},
            "prix_ref": {"classique": 7.0, "precarite": 12.0},
            "multiplicateur": 1,
            "rappel": "R mini : 3,7 m2K/W",
        },
    },
    "BAR-EN-103": {
        "label": "BAR-EN-103 — Isolation planchers bas",
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
            "inputs": ["zone", "surface", "beneficiaire"],
            "facteurs": {"H1": 1100, "H2": 890, "H3": 590},
            "prix_ref": {"classique": 7.0, "precarite": 12.5},
            "multiplicateur": 1,
            "rappel": "R mini : 3 m2K/W",
        },
    },
    "BAR-TH-171": {
        "label": "BAR-TH-171 — PAC air/eau",
        "secteur": "Residentiel individuel",
        "abrogation": None,
        "mentions_cee": [
            "Marque et reference de la PAC",
            "Etas >= 126 % (BT) ou Etas >= 111 % (MHT)",
            "Application PAC : chauffage seul ou chauffage + ECS",
            "Type d'emetteurs (planchers chauffants / radiateurs / ventilo-convecteurs)",
            "Zone climatique (H1 / H2 / H3)",
            "SIRET et numero RGE de l'entreprise",
            "Adresse complete des travaux",
            "Signature beneficiaire (bon pour accord) + date",
            "Mention Coup de Pouce Chauffage (si applicable)",
        ],
        "calcul": {
            "type": "pac_residentiel",
            "inputs": ["zone", "type_logement", "usage_pac", "etas", "surface", "beneficiaire", "remplacement_chaudiere"],
            # Montants base kWhc (type_logement|usage -> [bande1_111-140, bande2_>=140])
            "montants_base": {
                "Maison individuelle|Chauffage": [90900, 109200],
                "Maison individuelle|Chauffage + ECS": [90900, 109200],
                "Appartement|Chauffage": [48700, 58900],
                "Appartement|Chauffage + ECS": [48700, 58900],
            },
            # Coefficient zone
            "coeff_zone": {"H1": 1.2, "H2": 1.0, "H3": 0.7},
            # Coefficient surface maison (seuils/coeffs depuis Excel)
            "coeff_surface_maison": [(0, 0.5), (70, 0.7), (90, 1.0), (1e9, 1.0)],
            "coeff_surface_appart": [(0, 0.5), (35, 0.7), (60, 1.0), (1e9, 1.0)],
            # Facteur Coup de Pouce (x5 si remplacement chaudiere gaz/charbon/fioul)
            "facteur_cdp": 5,
            "prix_ref": {"classique": 7.4, "precarite": 11.7},
            "rappel": "Etas >= 126% (BT) ou >= 111% (MHT). Coup de Pouce x5 si remplacement chaudiere.",
        },
    },
    # ── RESIDENTIEL COLLECTIF ─────────────────────────────────────────────────
    "BAR-TH-179": {
        "label": "BAR-TH-179 — PAC collective residentiel <=400kW",
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
        "calcul": {
            "type": "nc",
            "inputs": [],
            "rappel": "Calcul BAR-TH-179 selon fiche specifique Econov — contacter Econov pour simulation.",
        },
    },
    # ── TERTIAIRE ─────────────────────────────────────────────────────────────
    "BAT-TH-163": {
        "label": "BAT-TH-163 — PAC air/eau tertiaire",
        "secteur": "Tertiaire",
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
            "inputs": ["zone", "secteur_activite", "puissance_pac", "etas_ou_cop", "surface", "facteur_r", "remplacement_chaudiere"],
            # Barème <=400kW kWhc/m² par classe Etas et zone
            "bareme_lte400": {
                "111%-126%": {"H1": 1100, "H2": 900, "H3": 600},
                "126%-175%": {"H1": 1200, "H2": 1000, "H3": 700},
                "175%+":     {"H1": 1300, "H2": 1000, "H3": 700},
            },
            # Barème >400kW kWhc/m² par classe COP et zone
            "bareme_gt400": {
                "4-5":  {"H1": 1200, "H2": 1000, "H3": 700},
                "5+":   {"H1": 1300, "H2": 1000, "H3": 700},
            },
            # Facteurs secteur d'activite
            "facteur_secteur": {
                "Bureaux": 1.2, "Enseignement": 0.8, "Hotellerie / Restauration": 0.7,
                "Sante": 1.1, "Commerces": 0.9, "Autres": 0.7,
            },
            "facteur_cdp": 1.3,
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "Etas >= 111% (<=400kW) ou COP >= 3,4 (>400kW). Facteur R = part PAC dans chaufferie.",
        },
    },
    "BAT-TH-134": {
        "label": "BAT-TH-134 — Regulation HP flottante sur froid",
        "secteur": "Tertiaire",
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
            "inputs": ["zone", "application", "type_condensation", "puissance_kw"],
            # Facteurs kWhc/kW (zone x application x type condensation) — table Excel B2B
            "facteurs": {
                "Autres applications|Par rapport a l'atmosphere": {"H1": 19100, "H2": 15700, "H3": 10400},
                "Autres applications|Par rapport a l'eau": {"H1": 9000, "H2": 7400, "H3": 4900},
                "Froid commercial": {"H1": 35100, "H2": 28800, "H3": 19100},
            },
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "La puissance nominale doit etre prouvee par la plaque signaletique.",
        },
    },
    "BAT-TH-139": {
        "label": "BAT-TH-139 — Recuperation chaleur sur groupe froid",
        "secteur": "Tertiaire",
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
            "inputs": ["zone", "secteur_activite", "p_compresseur", "p_ecs", "p_chauffage"],
            # Facteur kWhc/kWth par secteur
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
            # Coeff valorisation chauffage selon zone
            "coeff_chauffage": {"H1": 0.63, "H2": 0.59, "H3": 0.50},
            "prix_ref": {"classique": 7.0, "precarite": 7.0},
            "rappel": "Precup max = 2,9 x Pcomp. Concomitance des besoins obligatoire.",
        },
    },
}

SECTEUR_ICONS = {
    "Residentiel individuel": "🏠",
    "Residentiel collectif": "🏢",
    "Tertiaire": "🏗️",
}

# ──────────────────────────────────────────────────────────────────────────────
# CALCUL DE PRIME
# ──────────────────────────────────────────────────────────────────────────────

def calculer_prime(fiche_id, params, prix_cee):
    """Calcule le gisement et la prime estimee selon les parametres saisis."""
    calcul = FICHES[fiche_id]["calcul"]
    ctype = calcul["type"]
    zone = params.get("zone", "H1")

    if ctype == "surface":
        surface = params.get("surface", 0)
        facteur = calcul["facteurs"].get(zone, 0)
        gisement_kwh = surface * facteur
        prime = (gisement_kwh / 1000) * prix_cee
        return {
            "gisement_kwh": round(gisement_kwh),
            "gisement_mwh": round(gisement_kwh / 1000, 1),
            "prime": round(prime, 2),
            "detail": f"{surface} m² x {facteur} kWhc/m² (zone {zone})",
        }

    elif ctype == "pac_residentiel":
        type_log = params.get("type_logement", "Maison individuelle")
        usage = params.get("usage_pac", "Chauffage")
        etas = params.get("etas", 130)
        surface = params.get("surface", 100)
        remplace = params.get("remplacement_chaudiere", False)

        cle = f"{type_log}|{usage}"
        montants = calcul["montants_base"].get(cle, [90900, 109200])
        bande = 1 if etas >= 140 else 0
        montant_base = montants[bande]

        # Coefficient zone
        coeff_z = calcul["coeff_zone"].get(zone, 1.0)

        # Coefficient surface
        if "Maison" in type_log:
            seuils = calcul["coeff_surface_maison"]
        else:
            seuils = calcul["coeff_surface_appart"]
        coeff_s = 1.0
        for seuil, coeff in seuils:
            if surface >= seuil:
                coeff_s = coeff
        # Trouver le bon coeff (seuils croissants)
        coeff_s = seuils[0][1]
        for seuil, coeff in seuils:
            if surface >= seuil:
                coeff_s = coeff

        # Facteur CdP
        facteur_cdp = calcul["facteur_cdp"] if remplace else 1

        gisement = montant_base * coeff_z * facteur_cdp
        prime = (gisement / 1000) * prix_cee
        bande_str = ">=140%" if bande == 1 else "111-140%"
        detail = f"Base {montant_base} kWhc x zone {coeff_z} x CdP {facteur_cdp} (Etas bande {bande_str})"
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 1),
            "prime": round(prime, 2),
            "detail": detail,
            "cdp_actif": remplace,
        }

    elif ctype == "pac_tertiaire":
        puissance = params.get("puissance_pac", 200)
        etas_cop = params.get("etas_ou_cop", 130)
        surface = params.get("surface", 1000)
        secteur_act = params.get("secteur_activite", "Bureaux")
        facteur_r = params.get("facteur_r", 1.0)
        remplace = params.get("remplacement_chaudiere", False)

        if puissance <= 400:
            if etas_cop >= 175:
                bande = "175%+"
            elif etas_cop >= 126:
                bande = "126%-175%"
            else:
                bande = "111%-126%"
            kwh_m2 = calcul["bareme_lte400"][bande].get(zone, 0)
        else:
            if etas_cop >= 5:
                bande = "5+"
            else:
                bande = "4-5"
            kwh_m2 = calcul["bareme_gt400"][bande].get(zone, 0)

        fact_secteur = calcul["facteur_secteur"].get(secteur_act, 0.7)
        kwh_m2_corrige = kwh_m2 * fact_secteur * facteur_r
        if remplace:
            kwh_m2_corrige *= calcul.get("facteur_cdp", 1)

        gisement = kwh_m2_corrige * surface
        prime = (gisement / 1000) * prix_cee
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 1),
            "prime": round(prime, 2),
            "detail": f"{kwh_m2} kWhc/m² x facteur secteur {fact_secteur} x R={facteur_r} x {surface} m²",
        }

    elif ctype == "puissance_froid":
        application = params.get("application", "Autres applications|Par rapport a l'atmosphere")
        puissance = params.get("puissance_kw", 0)
        facteur = calcul["facteurs"].get(application, {}).get(zone, 0)
        gisement = puissance * facteur
        prime = (gisement / 1000) * prix_cee
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 1),
            "prime": round(prime, 2),
            "detail": f"{puissance} kW x {facteur} kWhc/kW (zone {zone}, {application})",
        }

    elif ctype == "recuperation_froid":
        secteur_act = params.get("secteur_activite", "Autres")
        p_comp = params.get("p_compresseur", 0)
        p_ecs = params.get("p_ecs", 0)
        p_chaud = params.get("p_chauffage", 0)
        coeff_ch = calcul["coeff_chauffage"].get(zone, 0.5)

        facteur = calcul["facteurs_secteur"].get(secteur_act, 13800)
        # Cap reglementaire
        p_cap = max(0, 2.9 * p_comp)
        p_total = min(p_ecs + p_chaud, p_cap)
        p_ecs_ret = min(p_ecs, p_cap)
        p_ch_ret = min(p_chaud, max(0, p_cap - p_ecs_ret))

        gis_ecs = p_ecs_ret * facteur
        gis_ch = p_ch_ret * facteur * coeff_ch
        gisement = gis_ecs + gis_ch
        prime = (gisement / 1000) * prix_cee
        return {
            "gisement_kwh": round(gisement),
            "gisement_mwh": round(gisement / 1000, 1),
            "prime": round(prime, 2),
            "detail": f"ECS {round(gis_ecs)} kWhc + Chauffage {round(gis_ch)} kWhc (coeff zone {coeff_ch})",
            "p_cap": round(p_cap, 1),
        }

    return {"gisement_kwh": 0, "gisement_mwh": 0, "prime": 0, "detail": "Calcul non disponible."}


def formulaire_calcul(fiche_id, pollueur_key):
    """Affiche le formulaire de calcul selon la fiche et retourne (params, prix_cee)."""
    calcul = FICHES[fiche_id]["calcul"]
    ctype = calcul["type"]
    pollueur = POLLUEURS[pollueur_key]
    beneficiaire_type = st.session_state.get("beneficiaire_type", "classique")

    # Prix CEE suggere par le pollueur
    prix_ref = pollueur["prix_cee_ref"][beneficiaire_type]
    inputs_needed = calcul.get("inputs", [])
    params = {}

    if ctype == "nc":
        st.info(f"Le calcul pour {fiche_id} necessite une simulation specifique. Contactez Econov.")
        return {}, prix_ref

    col1, col2, col3 = st.columns(3)

    if "zone" in inputs_needed:
        with col1:
            params["zone"] = st.selectbox("Zone climatique", ["H1", "H2", "H3"], key="calc_zone")

    if "beneficiaire" in inputs_needed:
        with col2:
            benef = st.selectbox("Type de beneficiaire", ["Classique", "Precarite"], key="calc_benef")
            beneficiaire_type = "precarite" if benef == "Precarite" else "classique"
            st.session_state.beneficiaire_type = beneficiaire_type
            prix_ref = pollueur["prix_cee_ref"][beneficiaire_type]
        with col3:
            prix_cee = st.number_input("Prix CEE (EUR/MWhc)", value=float(prix_ref), step=0.1,
                                       min_value=1.0, max_value=30.0, key="calc_prix")
    else:
        with col3:
            prix_cee = st.number_input("Prix CEE (EUR/MWhc)", value=float(prix_ref), step=0.1,
                                       min_value=1.0, max_value=30.0, key="calc_prix")

    if "surface" in inputs_needed:
        params["surface"] = st.number_input("Surface (m²)", value=100.0, min_value=1.0, step=1.0,
                                             key="calc_surface")

    if "type_logement" in inputs_needed:
        col_a, col_b = st.columns(2)
        with col_a:
            params["type_logement"] = st.selectbox("Type de logement",
                                                    ["Maison individuelle", "Appartement"], key="calc_type_log")
        with col_b:
            params["usage_pac"] = st.selectbox("Usage PAC", ["Chauffage", "Chauffage + ECS"], key="calc_usage")

    if "etas" in inputs_needed:
        col_a, col_b = st.columns(2)
        with col_a:
            params["etas"] = st.number_input("Etas (%)", value=130, min_value=100, max_value=250,
                                              key="calc_etas")
        with col_b:
            params["remplacement_chaudiere"] = st.checkbox(
                "Remplacement chaudiere gaz/charbon/fioul (Coup de Pouce x5)?",
                key="calc_cdp"
            )

    if "secteur_activite" in inputs_needed:
        secteurs_act = list(FICHES[fiche_id]["calcul"].get("facteur_secteur",
                       FICHES[fiche_id]["calcul"].get("facteurs_secteur", {"Autres": 1})).keys())
        params["secteur_activite"] = st.selectbox("Secteur d'activite", secteurs_act, key="calc_sect_act")

    if "puissance_pac" in inputs_needed:
        col_a, col_b = st.columns(2)
        with col_a:
            params["puissance_pac"] = st.number_input("Puissance thermique PAC (kW)", value=200.0,
                                                       min_value=1.0, key="calc_pui_pac")
        with col_b:
            params["etas_ou_cop"] = st.number_input("Etas (%) si <=400kW ou COP si >400kW",
                                                     value=130.0, min_value=0.0, step=1.0, key="calc_etas_cop")

    if "facteur_r" in inputs_needed:
        col_a, col_b = st.columns(2)
        with col_a:
            params["facteur_r"] = st.slider("Facteur R (part PAC dans la puissance chaufferie)",
                                             0.0, 1.0, 1.0, 0.05, key="calc_fr")
        with col_b:
            params["remplacement_chaudiere"] = st.checkbox(
                "Remplacement chaudiere (Coup de Pouce)?", key="calc_cdp_bat"
            )

    if "application" in inputs_needed:
        app_choices = list(FICHES[fiche_id]["calcul"]["facteurs"].keys())
        params["application"] = st.selectbox("Application / Type condensation", app_choices, key="calc_app")

    if "puissance_kw" in inputs_needed:
        params["puissance_kw"] = st.number_input("Puissance electrique nominale (kW)",
                                                  value=10.0, min_value=0.1, step=0.1, key="calc_pui")

    if "p_compresseur" in inputs_needed:
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            params["p_compresseur"] = st.number_input("Puissance compresseur (kW)",
                                                       value=15.0, min_value=0.0, step=0.5, key="calc_pcomp")
        with col_b:
            params["p_ecs"] = st.number_input("Puissance recup ECS (kW)",
                                               value=0.0, min_value=0.0, step=0.5, key="calc_pecs")
        with col_c:
            params["p_chauffage"] = st.number_input("Puissance recup Chauffage (kW)",
                                                     value=0.0, min_value=0.0, step=0.5, key="calc_pch")

    return params, prix_cee


# ──────────────────────────────────────────────────────────────────────────────
# ANALYSE DOCUMENT (Claude API)
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes):
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)[:8000]
    except Exception:
        return ""


def encode_file(file_bytes, filename):
    ext = filename.lower().split(".")[-1]
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
    if ext == "pdf":
        return "application/pdf", b64
    elif ext in ["jpg", "jpeg"]:
        return "image/jpeg", b64
    elif ext == "png":
        return "image/png", b64
    elif ext == "webp":
        return "image/webp", b64
    return None, None


def analyze_document(api_key, file_bytes, filename, fiche_id, pollueur_key):
    client = anthropic.Anthropic(api_key=api_key)
    fiche = FICHES[fiche_id]
    pollueur = POLLUEURS[pollueur_key]
    mentions_str = "\n".join(f"- {m}" for m in fiche["mentions_cee"])
    exigences_str = "\n".join(f"- {e}" for e in pollueur["exigences"]) or "- Aucune specifique"
    app_photo = pollueur.get("app_photo") or "non imposee"

    system = f"""Expert CEE France. Analyse un document pour fiche {fiche_id} ({fiche['label']}).
Valorisateur : {pollueur['label']}.

MENTIONS CEE OBLIGATOIRES :
{mentions_str}

EXIGENCES {pollueur['label']} :
{exigences_str}
Application photo imposee : {app_photo}

Pour chaque mention : present (true/false), valeur si presente, conforme (true/false/null), commentaire si anomalie.
Extrais : type_document, nom_beneficiaire, adresse_travaux, siret_entreprise, rge_ok, signature_benef, date_document, resume_global.
Score_cee (0-100), score_pollueur (0-100), blocages_cee (liste), points_attention (liste).

JSON uniquement :
{{
  "type_document": "devis|facture|ah|photos|autre",
  "nom_beneficiaire": null, "adresse_travaux": null, "siret_entreprise": null,
  "rge_ok": null, "signature_benef": null, "date_document": null,
  "resume_global": "...",
  "mentions_cee": [{{"mention":"...","present":true,"valeur":null,"conforme":null,"commentaire":""}}],
  "exigences_pollueur": [{{"exigence":"...","present":false,"commentaire":""}}],
  "score_cee": 75, "score_pollueur": 60,
  "blocages_cee": [], "points_attention": []
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
            txt = extract_text_from_pdf(file_bytes)
            content = [{"type": "text", "text": f"Texte :\n{txt}\n\nAnalyse."}]

        resp = client.messages.create(
            model="claude-opus-4-5", max_tokens=2000, system=system,
            messages=[{"role": "user", "content": content}]
        )
        raw = re.sub(r"^```json\s*", "", resp.content[0].text.strip())
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        return {"type_document": "inconnu", "resume_global": f"Erreur : {e}",
                "mentions_cee": [], "exigences_pollueur": [], "score_cee": 0,
                "score_pollueur": 0, "blocages_cee": [str(e)], "points_attention": []}


def generate_message(fiche_id, pollueur_key, result, prime_result=None):
    fiche = FICHES[fiche_id]
    pollueur = POLLUEURS[pollueur_key]
    score = result.get("score_cee", 0)
    blocages = result.get("blocages_cee", [])
    attention = result.get("points_attention", [])

    parts = []
    if prime_result and prime_result.get("prime", 0) > 0:
        parts.append(f"Prime CEE estimee pour votre operation {fiche_id} : {prime_result['prime']:.0f} EUR")
        parts.append(f"Gisement : {prime_result['gisement_mwh']} MWhc\n")

    if score >= 80 and not blocages:
        parts.append(f"Votre document {fiche_id} semble conforme sur les points CEE principaux.")
    elif blocages:
        parts.append(f"Document {fiche_id} analyse — points bloquants identifies :")
        for b in blocages:
            parts.append(f"  - {b}")
        parts.append("")
    else:
        parts.append(f"Document {fiche_id} analyse — points a corriger avant depot :")

    if attention:
        parts.append("Points d'attention :")
        for a in attention:
            parts.append(f"  - {a}")
        parts.append("")

    manquantes = [e["exigence"] for e in result.get("exigences_pollueur", []) if not e.get("present")]
    if manquantes:
        parts.append(f"Exigences {pollueur['label']} manquantes :")
        for m in manquantes:
            parts.append(f"  - {m}")
        parts.append("")

    parts.append("Merci de corriger ces points avant transmission du dossier complet.")
    parts.append("— Econov")
    return "\n".join(parts)


def score_color(score):
    if score >= 80:
        return "pass", "✅"
    elif score >= 50:
        return "warn", "⚠️"
    return "fail", "❌"


# ──────────────────────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.stApp { background: linear-gradient(135deg, #f0f4ff 0%, #ffffff 100%); }
.main .block-container { max-width: 880px; padding-top: 1.5rem; padding-bottom: 4rem; }

.sim-header {
    text-align: center; padding: 2rem 1rem 1.25rem;
    background: white; border-radius: 16px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.06); margin-bottom: 1.5rem;
}
.sim-header h1 { font-size: 1.9rem; font-weight: 700; color: #1a1a2e; margin: 0 0 0.4rem; }
.sim-header p { color: #6b7280; font-size: 1rem; margin: 0; }
.sim-badge {
    display: inline-block; background: #ecfdf5; color: #059669;
    font-size: 0.78rem; font-weight: 600; padding: 3px 12px;
    border-radius: 20px; margin-top: 0.6rem;
}

.steps-bar { display: flex; justify-content: center; align-items: center; margin-bottom: 1.5rem; }
.step-item { display: flex; align-items: center; gap: 6px; }
.step-num {
    width: 30px; height: 30px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 600; font-size: 0.82rem;
}
.step-num.active { background: #4f46e5; color: white; }
.step-num.done { background: #059669; color: white; }
.step-num.pending { background: #e5e7eb; color: #9ca3af; }
.step-label { font-size: 0.82rem; font-weight: 500; }
.step-label.active { color: #4f46e5; }
.step-label.done { color: #059669; }
.step-label.pending { color: #9ca3af; }
.step-sep { width: 44px; height: 2px; background: #e5e7eb; margin: 0 6px; }
.step-sep.done { background: #059669; }

.prime-card {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    border-radius: 16px; padding: 1.5rem 2rem; color: white;
    text-align: center; margin: 1rem 0;
    box-shadow: 0 8px 24px rgba(79,70,229,0.3);
}
.prime-card .montant { font-size: 3rem; font-weight: 700; line-height: 1; }
.prime-card .label { font-size: 1rem; opacity: 0.85; margin-top: 0.3rem; }
.prime-card .detail { font-size: 0.8rem; opacity: 0.7; margin-top: 0.5rem; }
.prime-card .gisement { font-size: 0.9rem; opacity: 0.8; margin-top: 0.2rem; }

.section-card {
    background: white; border-radius: 14px; padding: 1.5rem 1.75rem;
    box-shadow: 0 2px 16px rgba(0,0,0,0.05); margin-bottom: 1.25rem;
}
.section-title { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.75rem; }

.result-header { text-align: center; padding: 1.75rem; border-radius: 14px; margin-bottom: 1.25rem; }
.result-header.pass { background: linear-gradient(135deg, #ecfdf5, #d1fae5); }
.result-header.warn { background: linear-gradient(135deg, #fffbeb, #fef3c7); }
.result-header.fail { background: linear-gradient(135deg, #fef2f2, #fee2e2); }
.result-score { font-size: 3rem; font-weight: 700; line-height: 1; }
.result-score.pass { color: #059669; }
.result-score.warn { color: #d97706; }
.result-score.fail { color: #dc2626; }
.result-label { font-size: 1rem; font-weight: 600; color: #374151; margin-top: 0.4rem; }

.mention-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 9px 0; border-bottom: 1px solid #f3f4f6; font-size: 0.9rem;
}
.mention-item:last-child { border-bottom: none; }
.mention-detail { font-size: 0.8rem; color: #6b7280; margin-top: 2px; }

.pollueur-exigence {
    display: flex; align-items: flex-start; gap: 8px;
    padding: 8px 0; font-size: 0.88rem; color: #374151;
    border-bottom: 1px solid #f3f4f6;
}
.pollueur-exigence:last-child { border-bottom: none; }

.upload-hint {
    background: #f9fafb; border: 2px dashed #d1d5db;
    border-radius: 10px; padding: 1.25rem; text-align: center;
    color: #6b7280; font-size: 0.9rem; margin: 0.5rem 0 0.75rem;
}

.abrogation-badge {
    display: inline-block; background: #fef3c7; color: #d97706;
    font-size: 0.78rem; font-weight: 600; padding: 3px 10px;
    border-radius: 20px; margin-left: 8px;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(79,70,229,0.3) !important;
}
.econov-footer {
    text-align: center; padding: 1.25rem; color: #9ca3af;
    font-size: 0.8rem; margin-top: 1.5rem;
}
</style>
"""


def steps_html(current_step):
    steps = [("1", "Operation"), ("2", "Calcul + Doc"), ("3", "Resultat")]
    items = []
    for i, (num, label) in enumerate(steps, 1):
        if i < current_step:
            cn, cl, nd = "done", "done", "✓"
        elif i == current_step:
            cn, cl, nd = "active", "active", num
        else:
            cn, cl, nd = "pending", "pending", num
        items.append(
            f'<div class="step-item">'
            f'<div class="step-num {cn}">{nd}</div>'
            f'<span class="step-label {cl}">{label}</span>'
            f'</div>'
        )
        if i < len(steps):
            sep = "done" if i < current_step else ""
            items.append(f'<div class="step-sep {sep}"></div>')
    return f'<div class="steps-bar">{"".join(items)}</div>'


# ──────────────────────────────────────────────────────────────────────────────
# APP
# ──────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Simulateur CEE — Econov", page_icon="🏠",
                       layout="centered", initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)

    for k, v in [("step", 1), ("pollueur_key", None), ("fiche_id", None),
                 ("result", None), ("prime_result", None), ("beneficiaire_type", "classique")]:
        if k not in st.session_state:
            st.session_state[k] = v

    st.markdown("""
<div class="sim-header">
    <h1>🏠 Simulateur CEE</h1>
    <p>Estimez votre prime et verifiez votre document en quelques secondes</p>
    <span class="sim-badge">Acces libre &mdash; Econov</span>
</div>
""", unsafe_allow_html=True)

    st.markdown(steps_html(st.session_state.step), unsafe_allow_html=True)
    api_key = get_api_key()

    # ═══════════════════════════════════════════════
    # ETAPE 1 — Pollueur + Fiche
    # ═══════════════════════════════════════════════
    if st.session_state.step == 1:

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">1. Choisissez votre valorisateur (pollueur)</div>',
                    unsafe_allow_html=True)
        st.caption("L'entreprise qui finance la prime CEE de votre client.")

        cols = st.columns(3)
        for i, (key, p) in enumerate(POLLUEURS.items()):
            with cols[i % 3]:
                selected = st.session_state.pollueur_key == key
                if st.button(f"{p['emoji']} {p['label']}", key=f"pol_{key}",
                             use_container_width=True, type="primary" if selected else "secondary"):
                    st.session_state.pollueur_key = key
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.pollueur_key:
            p = POLLUEURS[st.session_state.pollueur_key]
            st.success(f"Valorisateur : **{p['emoji']} {p['label']}**")
            if p["exigences"]:
                with st.expander(f"Exigences specifiques {p['label']}"):
                    for e in p["exigences"]:
                        st.write(f"• {e}")
                    if p.get("app_photo"):
                        st.info(f"Application photo imposee : **{p['app_photo']}**")

        st.divider()

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">2. Choisissez la fiche CEE</div>', unsafe_allow_html=True)

        secteurs: dict = {}
        for fid, f in FICHES.items():
            secteurs.setdefault(f["secteur"], []).append(fid)

        for secteur, fids in secteurs.items():
            icon = SECTEUR_ICONS.get(secteur, "📁")
            st.markdown(f"**{icon} {secteur}**")
            for fid in fids:
                fiche = FICHES[fid]
                selected = st.session_state.fiche_id == fid
                ab = fiche.get("abrogation")
                ab_tag = f" ⚠️ Abrogee {ab}" if ab else ""
                label = f"{'✓  ' if selected else ''}{fiche['label']}{ab_tag}"
                if st.button(label, key=f"fiche_{fid}", use_container_width=True,
                             type="primary" if selected else "secondary"):
                    st.session_state.fiche_id = fid
                    st.rerun()
            st.write("")

        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.pollueur_key and st.session_state.fiche_id:
            if st.button("Continuer — Calculer ma prime  ➡", type="primary", use_container_width=True):
                st.session_state.step = 2
                st.rerun()
        else:
            st.info("Selectionnez un valorisateur ET une fiche CEE pour continuer.")

    # ═══════════════════════════════════════════════
    # ETAPE 2 — Calcul prime + Upload doc
    # ═══════════════════════════════════════════════
    elif st.session_state.step == 2:

        fiche = FICHES[st.session_state.fiche_id]
        pollueur = POLLUEURS[st.session_state.pollueur_key]
        ab = fiche.get("abrogation")

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Fiche** : {st.session_state.fiche_id} — {fiche['label']}")
        with col2:
            st.info(f"**Valorisateur** : {pollueur['emoji']} {pollueur['label']}")

        if ab:
            st.warning(f"⚠️ Cette fiche est annoncee comme abrogee au **{ab}**.")

        # ── Formulaire calcul prime
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Parametres de l\'operation — Estimation de prime</div>',
                    unsafe_allow_html=True)

        with st.form("form_calcul_et_doc"):
            params, prix_cee = formulaire_calcul(st.session_state.fiche_id, st.session_state.pollueur_key)

            st.markdown("---")
            st.markdown("**Document a verifier (optionnel)**")
            st.caption("Deposez un devis, facture ou autre piece CEE pour en verifier la conformite.")
            st.markdown("""
<div class="upload-hint">
    Glissez-deposez votre fichier (PDF, JPG, PNG) ou cliquez<br>
    <small>1 seul fichier &bull; 20 Mo max</small>
</div>
""", unsafe_allow_html=True)

            uploaded = st.file_uploader("Document", type=["pdf", "jpg", "jpeg", "png", "webp"],
                                        label_visibility="collapsed")

            with st.expander("Mentions CEE attendues sur le document"):
                for m in fiche["mentions_cee"]:
                    st.write(f"• {m}")

            submit = st.form_submit_button("🔍 Calculer la prime + Analyser le document",
                                           type="primary", use_container_width=True)

        if submit:
            prime_result = calculer_prime(st.session_state.fiche_id, params, prix_cee)
            st.session_state.prime_result = prime_result
            st.session_state.params_calcul = params

            if uploaded and api_key:
                with st.spinner("Analyse du document en cours... (10-30 secondes)"):
                    fb = uploaded.read()
                    result = analyze_document(api_key, fb, uploaded.name,
                                              st.session_state.fiche_id, st.session_state.pollueur_key)
                    st.session_state.result = result
            elif uploaded and not api_key:
                st.error("API non configuree. Contactez Econov pour activer l'analyse de documents.")
                st.session_state.result = None
            else:
                st.session_state.result = None

            st.session_state.step = 3
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("← Retour", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

    # ═══════════════════════════════════════════════
    # ETAPE 3 — Resultats
    # ═══════════════════════════════════════════════
    elif st.session_state.step == 3:

        fiche = FICHES[st.session_state.fiche_id]
        pollueur = POLLUEURS[st.session_state.pollueur_key]
        prime_result = st.session_state.prime_result or {}
        result = st.session_state.result

        # ── Prime card
        prime = prime_result.get("prime", 0)
        gisement_mwh = prime_result.get("gisement_mwh", 0)
        detail = prime_result.get("detail", "")
        cdp = prime_result.get("cdp_actif", False)

        if prime > 0:
            cdp_note = " (Coup de Pouce x5 inclus)" if cdp else ""
            st.markdown(f"""
<div class="prime-card">
    <div class="montant">{prime:,.0f} EUR</div>
    <div class="label">Prime CEE estimee{cdp_note}</div>
    <div class="gisement">Gisement : {gisement_mwh} MWhc cumac</div>
    <div class="detail">{detail}</div>
</div>
""", unsafe_allow_html=True)

            rappel = FICHES[st.session_state.fiche_id]["calcul"].get("rappel", "")
            if rappel:
                st.caption(f"ℹ️ {rappel}")
        else:
            st.info("Prime non calculee (parametres manquants ou fiche sans barème integre).")

        # ── Rappel cap BAT-TH-139
        if prime_result.get("p_cap"):
            st.caption(f"Cap reglementaire Precup max : {prime_result['p_cap']} kW")

        st.divider()

        # ── Resultats analyse document
        if result:
            score_cee = result.get("score_cee", 0)
            cls_cee, icon_cee = score_color(score_cee)

            st.markdown(f"""
<div class="result-header {cls_cee}">
    <div class="result-score {cls_cee}">{score_cee}%</div>
    <div class="result-label">{icon_cee} Score de conformite CEE — {st.session_state.fiche_id}</div>
</div>
""", unsafe_allow_html=True)

            mentions = result.get("mentions_cee", [])
            n_ok = sum(1 for m in mentions if m.get("present"))
            n_blk = len(result.get("blocages_cee", []))
            score_pol = result.get("score_pollueur", 0)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Type document", result.get("type_document", "?").capitalize())
            col2.metric("Mentions presentes", f"{n_ok}/{len(mentions)}")
            col3.metric("Blocages CEE", n_blk)
            col4.metric(f"Score {pollueur['label']}", f"{score_pol}%")

            infos = {}
            for key, label in [("nom_beneficiaire", "Beneficiaire"), ("adresse_travaux", "Adresse"),
                                ("siret_entreprise", "SIRET"), ("date_document", "Date")]:
                if result.get(key):
                    infos[label] = result[key]
            if result.get("rge_ok") is not None:
                infos["RGE"] = "OK" if result["rge_ok"] else "Non trouve"
            if result.get("signature_benef") is not None:
                infos["Signature"] = "Presente" if result["signature_benef"] else "Absente"
            if infos:
                with st.expander("Informations extraites"):
                    for k, v in infos.items():
                        st.write(f"**{k}** : {v}")
            if result.get("resume_global"):
                st.info(result["resume_global"])

            # Mentions CEE
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Mentions CEE</div>', unsafe_allow_html=True)
            for m in mentions:
                present = m.get("present", False)
                conforme = m.get("conforme")
                icon = "✅" if (present and conforme is not False) else ("⚠️" if present else "❌")
                valeur = f" → **{m['valeur']}**" if m.get("valeur") else ""
                comm = f"<div class='mention-detail'>⚠ {m['commentaire']}</div>" if m.get("commentaire") else ""
                st.markdown(f"""
<div class="mention-item">
    <span style="flex-shrink:0;font-size:1.05rem">{icon}</span>
    <div><div>{m.get('mention','')}{valeur}</div>{comm}</div>
</div>
""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Blocages
            for b in result.get("blocages_cee", []):
                st.error(f"🔴 {b}")
            for a in result.get("points_attention", []):
                st.warning(f"🟠 {a}")

            # Exigences pollueur
            exigences_pol = result.get("exigences_pollueur", [])
            if exigences_pol:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="section-title">{pollueur["emoji"]} Exigences {pollueur["label"]}</div>',
                            unsafe_allow_html=True)
                st.caption("Ces points ne bloquent pas l'eligibilite CEE reglementaire.")
                for e in exigences_pol:
                    icon = "✅" if e.get("present") else "❌"
                    comm = f"<div style='font-size:0.8rem;color:#6b7280'>{e['commentaire']}</div>" if e.get("commentaire") else ""
                    st.markdown(f'<div class="pollueur-exigence"><span>{icon}</span><div>{e.get("exigence","")}{comm}</div></div>',
                                unsafe_allow_html=True)
                if pollueur.get("app_photo"):
                    st.info(f"App photo imposee : **{pollueur['app_photo']}**")
                st.markdown('</div>', unsafe_allow_html=True)

        elif not result:
            if prime > 0:
                st.success("Prime calculee. Deposez un document a l'etape 2 pour verifier sa conformite.")
            else:
                st.info("Aucun document analyse.")

        # ── Message recap
        if result or prime > 0:
            st.divider()
            st.markdown('<div class="section-title">Message recapitulatif</div>', unsafe_allow_html=True)
            message = generate_message(st.session_state.fiche_id, st.session_state.pollueur_key,
                                       result or {}, prime_result)
            st.text_area("", message, height=200, key="msg_box")

        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("← Modifier les parametres", use_container_width=True):
                st.session_state.step = 2
                st.session_state.result = None
                st.rerun()
        with col2:
            if st.button("Nouvelle simulation", use_container_width=True):
                for k in ["step", "pollueur_key", "fiche_id", "result", "prime_result"]:
                    st.session_state[k] = None
                st.session_state.step = 1
                st.rerun()
        with col3:
            st.button("Deposer le dossier complet →", type="primary", use_container_width=True,
                      help="Acces au Checker Econov complet.")

    st.markdown("""
<div class="econov-footer">
    Simulateur CEE &mdash; <strong>Econov</strong> &bull; Analyse IA par Claude (Anthropic)<br>
    Resultats indicatifs — non contractuels
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
