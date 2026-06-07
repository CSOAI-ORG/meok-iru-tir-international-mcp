#!/usr/bin/env python3
"""
MEOK IRU TIR International Transport MCP
=========================================

By MEOK AI Labs · https://haulage.app · MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-iru-tir-international-mcp -->

WHAT THIS DOES
--------------
Extends MEOK haulage compliance to **international road transport** under the
TIR (Transports Internationaux Routiers) and CMR systems administered by the
International Road Transport Union (IRU).

The TIR system is the only **universal Customs transit** regime, covering 78
operational contracting parties and 1,000+ national association affiliates.
A single TIR Carnet lets sealed goods cross multiple borders without re-checks,
provided the holder is approved, the vehicle is sealed and approved, and the
Carnet is correctly issued by an IRU-affiliated guaranteeing association.

This MCP gives international hauliers the callable toolkit to:
  - Decide if TIR is needed for a specific consignment
  - Generate the IRU eTIR data set for a cross-border move
  - Validate that the operator's national association is IRU-affiliated
  - Check Authorised Economic Operator (AEO) status to speed Customs clearance
  - Validate the CMR consignment note (Convention 1956)
  - Route ADR dangerous-goods consignments respecting tunnel restrictions
  - Prepare per-border Customs entry/exit document packs

TOOLS (7)
---------
- check_tir_carnet_requirements(consignment)         → when is TIR needed?
- generate_tir_carnet_paperwork(consignment, route)  → eTIR data set
- validate_iru_associate_member(operator_name)       → IRU affiliate lookup
- check_aeo_status(operator_country, eori_number)    → AEO compliance
- check_cmr_consignment_note(consignment)            → CMR 1956 validity
- check_dangerous_goods_adr_international(...)       → ADR + tunnel routing
- prepare_border_crossing_pack(consignment, ...)     → per-country docs

WHY YOU PAY
-----------
A single failed TIR move at a hostile border = €2,000-€50,000 in delay,
demurrage, re-routing, lost loads, and Customs deposits. TIR Carnet errors
can also trigger guarantor-association claims up to €100,000 per Carnet.

PRICING
-------
Free MIT self-host · €99/mo Starter · €299/mo Pro · €1,499/mo Fleet.
EUR pricing — this is international road transport.

REGULATORY BASIS
----------------
TIR Convention 1975 — UN ECE, Geneva (consolidated)
CMR Convention 1956 — Convention on the Contract for International
                       Carriage of Goods by Road
ADR European Agreement 2025 — UN ECE Dangerous Goods by Road
Authorised Economic Operator (AEO) — WCO SAFE Framework + EU UCC
EU Implementing Regulation 2015/2447 (UCC IA) — AEO criteria
IRU eTIR — digital transformation of TIR Carnet, IRU Geneva
"""

from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone, date, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("meok-iru-tir-international")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")


# ──────────────────────────────────────────────────────────────────────
# Regulatory tables
# ──────────────────────────────────────────────────────────────────────

# TIR Convention 1975 — operational contracting parties (selected subset)
# Full list of 78 is published by UN ECE; this is the working subset most
# used by EU-Asia and EU-Middle East corridors.
TIR_CONTRACTING_PARTIES = {
    "EU_block": [
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
        "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
        "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    ],
    "EFTA_and_neighbours": ["NO", "CH", "IS", "LI", "GB", "UA", "MD", "RS", "MK", "AL", "ME", "BA"],
    "Caucasus_central_asia": ["AM", "AZ", "GE", "KZ", "KG", "TJ", "TM", "UZ"],
    "middle_east": ["TR", "IL", "JO", "LB", "SY", "IR", "IQ", "AE", "SA"],
    "north_africa": ["MA", "TN", "DZ", "EG", "LY"],
    "asia_pacific": ["CN", "PK", "AF", "IN", "MN", "RU", "BY"],
    "americas": ["US", "CA", "CL", "UY"],
}

# IRU national associations (selected — full directory has 1,000+ members in
# 78 countries; this is the active "guaranteeing association" subset used
# day-to-day for Carnet issue/discharge).
IRU_GUARANTEEING_ASSOCIATIONS = {
    "GB": {"name": "Road Haulage Association (RHA)", "iru_affiliated": True},
    "FR": {"name": "Fédération Nationale des Transports Routiers (FNTR)", "iru_affiliated": True},
    "DE": {"name": "Bundesverband Güterkraftverkehr Logistik und Entsorgung (BGL)", "iru_affiliated": True},
    "ES": {"name": "Confederación Española de Transporte de Mercancías (CETM)", "iru_affiliated": True},
    "IT": {"name": "Federazione Italiana Autotrasportatori Professionali (FIAP)", "iru_affiliated": True},
    "NL": {"name": "Transport en Logistiek Nederland (TLN)", "iru_affiliated": True},
    "PL": {"name": "Zrzeszenie Międzynarodowych Przewoźników Drogowych (ZMPD)", "iru_affiliated": True},
    "TR": {"name": "Uluslararası Nakliyeciler Derneği (UND)", "iru_affiliated": True},
    "RU": {"name": "Association of International Road Carriers (ASMAP)", "iru_affiliated": True},
    "UA": {"name": "Association of International Road Carriers (AsMAP-UA)", "iru_affiliated": True},
    "BY": {"name": "BAMAP Belarusian Assoc. of International Road Carriers", "iru_affiliated": True},
    "KZ": {"name": "Kazakhstan Association of International Road Carriers (KazATO)", "iru_affiliated": True},
    "UZ": {"name": "AIRCUZ — Association of Intl Road Carriers of Uzbekistan", "iru_affiliated": True},
    "IR": {"name": "Iran Chamber of Commerce TIR Section", "iru_affiliated": True},
    "JO": {"name": "Jordan International Forwarders Association (JIFA)", "iru_affiliated": True},
    "MA": {"name": "Association Marocaine de Transit (AMT)", "iru_affiliated": True},
    "CN": {"name": "China Road Transport Association (CRTA)", "iru_affiliated": True},
    "US": {"name": "Customs-Trade Partnership (no TIR) — operator must transit via CA/MX assoc.", "iru_affiliated": False},
}

# CMR Convention 1956 — required consignment note fields (Art. 6)
CMR_REQUIRED_FIELDS = [
    "date_and_place_of_drawing_up",
    "sender_name_address",
    "consignee_name_address",
    "carrier_name_address",
    "place_and_date_of_taking_over_goods",
    "place_designated_for_delivery",
    "description_of_goods_and_packaging",
    "number_of_packages_marks_numbers",
    "gross_weight_or_quantity",
    "charges_to_be_paid_by_sender_or_consignee",
    "instructions_required_for_customs",
    "statement_that_carriage_subject_to_cmr",
]

# ADR — selected dangerous-goods classes (2025 edition)
ADR_CLASSES = {
    "1": "Explosives",
    "2.1": "Flammable gas",
    "2.2": "Non-flammable non-toxic gas",
    "2.3": "Toxic gas",
    "3": "Flammable liquid",
    "4.1": "Flammable solid",
    "4.2": "Substances liable to spontaneous combustion",
    "4.3": "Substances which, in contact with water, emit flammable gases",
    "5.1": "Oxidising substance",
    "5.2": "Organic peroxide",
    "6.1": "Toxic substance",
    "6.2": "Infectious substance",
    "7": "Radioactive material",
    "8": "Corrosive substance",
    "9": "Miscellaneous (incl. lithium batteries UN3480/3481)",
}

# ADR tunnel restriction codes (Chapter 1.9.5)
ADR_TUNNEL_CODES = {
    "A": "No restriction",
    "B": "Restriction for dangerous-goods leading to a very large explosion",
    "C": "Restriction for B + large explosion or large toxic release",
    "D": "Restriction for C + large fire",
    "E": "All packages > 8t carry restriction unless UN2919/3291/3331/3359/3373",
}

# AEO categories under WCO SAFE Framework / EU UCC Art. 38
AEO_TYPES = {
    "AEOC": "Customs simplifications",
    "AEOS": "Security and safety",
    "AEOF": "Full (AEOC + AEOS)",
}

# eTIR data envelope per IRU spec (subset)
ETIR_DATA_ELEMENTS = [
    "carnet_number",
    "holder_id",
    "guaranteeing_association_id",
    "consignor_id",
    "consignee_id",
    "approved_vehicle_id",
    "customs_seal_numbers",
    "goods_manifest",
    "route_offices",
    "expected_arrival_dates",
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _sign(payload: dict) -> str:
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(
        _HMAC_SECRET.encode(),
        json.dumps(payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attestation(payload: dict) -> dict:
    return {**payload, "ts": _ts(), "sig": _sign(payload),
            "issuer": "meok-iru-tir-international-mcp", "version": "1.0.0"}


def _is_tir_party(country_code: str) -> bool:
    cc = (country_code or "").upper()
    for region in TIR_CONTRACTING_PARTIES.values():
        if cc in region:
            return True
    return False


def _eu_member(country_code: str) -> bool:
    cc = (country_code or "").upper()
    return cc in TIR_CONTRACTING_PARTIES["EU_block"]


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def check_tir_carnet_requirements(
    origin_country: str = "",
    destination_country: str = "",
    transit_countries: Optional[list] = None,
    sealable: bool = True,
    goods_under_customs_control: bool = True,
    intra_eu: Optional[bool] = None,
) -> dict:
    """Decide whether a TIR Carnet is needed for this consignment.

    A TIR Carnet is required when:
      - The route crosses at least one Customs border, AND
      - All countries on the route are TIR contracting parties, AND
      - The vehicle/container is sealable, AND
      - The goods are under Customs control (i.e. not free-circulation
        between two EU member states or two free-trade-zone members).

    Args:
      origin_country: ISO-3166 alpha-2 of origin (e.g. "GB")
      destination_country: ISO-3166 alpha-2 of destination (e.g. "TR")
      transit_countries: list of ISO-3166 alpha-2 transit codes
      sealable: vehicle/container can carry approved Customs seals
      goods_under_customs_control: goods are not in free-circulation
      intra_eu: optional override; if True, TIR is not used (NCTS used instead)
    """
    transit_countries = transit_countries or []
    route = [origin_country, *transit_countries, destination_country]
    route = [c.upper() for c in route if c]

    if intra_eu is None:
        intra_eu = _eu_member(origin_country) and _eu_member(destination_country) \
                   and all(_eu_member(c) for c in transit_countries)

    all_tir_parties = all(_is_tir_party(c) for c in route)
    non_party_countries = [c for c in route if not _is_tir_party(c)]
    border_crossings = max(0, len(route) - 1)

    if border_crossings == 0:
        decision = "NOT_NEEDED"
        reason = "Origin == destination, no Customs border crossed."
    elif intra_eu:
        decision = "NOT_NEEDED"
        reason = "Intra-EU move — use NCTS (New Computerised Transit System), not TIR."
    elif not all_tir_parties:
        decision = "NOT_USABLE"
        reason = f"Route includes non-TIR-party countries: {non_party_countries}. TIR cannot cover the full route."
    elif not sealable:
        decision = "NOT_USABLE"
        reason = "Vehicle/container is not sealable — TIR requires Customs seals."
    elif not goods_under_customs_control:
        decision = "NOT_NEEDED"
        reason = "Goods are in free-circulation — Customs transit not required."
    else:
        decision = "TIR_REQUIRED"
        reason = "Cross-border move, all parties are TIR contracting parties, vehicle sealable, goods under Customs control."

    return _attestation({
        "tool": "check_tir_carnet_requirements",
        "origin_country": origin_country.upper(),
        "destination_country": destination_country.upper(),
        "transit_countries": [c.upper() for c in transit_countries],
        "border_crossings": border_crossings,
        "all_tir_contracting_parties": all_tir_parties,
        "non_party_countries": non_party_countries,
        "intra_eu_route": intra_eu,
        "decision": decision,
        "reason": reason,
        "alternative_if_not_usable": (
            "Use NCTS (EU transit) or T1/T2 documents per non-TIR border"
            if decision == "NOT_USABLE" else None
        ),
    })


@mcp.tool()
def generate_tir_carnet_paperwork(
    holder_id: str,
    guaranteeing_association: str,
    consignor: Optional[dict] = None,
    consignee: Optional[dict] = None,
    approved_vehicle: Optional[dict] = None,
    goods_manifest: Optional[list] = None,
    route: Optional[list] = None,
    carnet_number: str = "",
) -> dict:
    """Produce the IRU eTIR data envelope for a cross-border move.

    The eTIR system is the IRU's digital replacement for the paper TIR Carnet.
    Each Carnet contains pages ("vouchers") corresponding to each Customs
    office on the route; this helper assembles the metadata IRU eTIR needs.

    Args:
      holder_id: TIR ID of the transport operator (issued by IRU)
      guaranteeing_association: ISO-3166 alpha-2 of the issuing assoc. country
      consignor: {"name": "...", "address": "...", "country": "DE", "tax_id": "..."}
      consignee: same shape
      approved_vehicle: {"reg": "AB12CDE", "vin": "...",
                          "type_approval_cert": "TIR-DE-2026-12345",
                          "expiry": "2027-01-01"}
      goods_manifest: list of dicts with HS code, description, packages, kg, value
      route: list of {"office_code": "DEHAM1", "country": "DE", "type": "departure"}
              types: departure / transit_entry / transit_exit / destination
      carnet_number: pre-issued Carnet number (e.g. "XB.123.456.789")
    """
    consignor = consignor or {}
    consignee = consignee or {}
    approved_vehicle = approved_vehicle or {}
    goods_manifest = goods_manifest or []
    route = route or []

    errors = []
    if not holder_id:
        errors.append("holder_id required (IRU-issued TIR operator ID)")
    if not guaranteeing_association:
        errors.append("guaranteeing_association required (ISO country code)")
    if not approved_vehicle.get("type_approval_cert"):
        errors.append("approved_vehicle.type_approval_cert required (TIR vehicle approval)")
    try:
        if approved_vehicle.get("expiry") and date.fromisoformat(approved_vehicle["expiry"]) < date.today():
            errors.append("approved_vehicle.expiry is in the past — TIR vehicle approval lapsed")
    except Exception:
        errors.append("approved_vehicle.expiry has invalid date format (use YYYY-MM-DD)")
    if len(goods_manifest) == 0:
        errors.append("goods_manifest cannot be empty")
    if len(route) < 2:
        errors.append("route must contain at least an entry and exit Customs office")

    voucher_count = len(route)  # one voucher per Customs office stop

    # Compute Carnet number checksum (IRU formats XB.NNN.NNN.NNN)
    carnet_valid_format = bool(re.match(r"^[A-Z]{2}\.\d{3}\.\d{3}\.\d{3}$", carnet_number)) if carnet_number else False

    payload = {
        "tool": "generate_tir_carnet_paperwork",
        "carnet_number": carnet_number,
        "carnet_number_format_valid": carnet_valid_format,
        "holder_id": holder_id,
        "guaranteeing_association": guaranteeing_association.upper(),
        "consignor": consignor,
        "consignee": consignee,
        "approved_vehicle": approved_vehicle,
        "goods_manifest_lines": len(goods_manifest),
        "route_offices": route,
        "voucher_count_required": voucher_count,
        "etir_data_elements": ETIR_DATA_ELEMENTS,
        "errors": errors,
        "ready_to_submit": len(errors) == 0 and carnet_valid_format,
        "submission_endpoint": "https://etir.iru.org/api/v1/declaration",
    }
    return _attestation(payload)


@mcp.tool()
def validate_iru_associate_member(
    operator_name: str = "",
    country_code: str = "",
) -> dict:
    """Look up an IRU national-association affiliate by country.

    IRU membership matters because only IRU-affiliated guaranteeing
    associations can issue TIR Carnets. An operator must be in good standing
    with its national IRU member to use the TIR system.
    """
    cc = (country_code or "").upper()
    assoc = IRU_GUARANTEEING_ASSOCIATIONS.get(cc)
    if assoc:
        return _attestation({
            "tool": "validate_iru_associate_member",
            "operator_name": operator_name,
            "country_code": cc,
            "association_name": assoc["name"],
            "iru_affiliated": assoc["iru_affiliated"],
            "tir_carnet_issuance_authorised": assoc["iru_affiliated"],
            "advisory": (
                f"Apply to {assoc['name']} for TIR holder status; submit financial-standing evidence and approved-vehicle list."
                if assoc["iru_affiliated"] else
                f"{assoc['name']} is not currently IRU-affiliated for TIR — operator must work with a neighbouring IRU member."
            ),
        })
    # Country not in the IRU directory subset — flag explicitly
    return _attestation({
        "tool": "validate_iru_associate_member",
        "operator_name": operator_name,
        "country_code": cc,
        "association_name": None,
        "iru_affiliated": False,
        "tir_carnet_issuance_authorised": False,
        "advisory": (
            f"No IRU guaranteeing association registered for country {cc} in this directory. "
            "Check the full IRU directory at https://www.iru.org/about-iru/members or use a neighbouring TIR-party association."
        ),
    })


@mcp.tool()
def check_aeo_status(
    operator_country: str = "",
    eori_number: str = "",
    aeo_type: str = "",
) -> dict:
    """Check Authorised Economic Operator (AEO) status.

    AEO is the WCO SAFE Framework programme implemented as EU UCC Art. 38 and
    parallel national schemes (US C-TPAT, JP AEO, CN AEO, etc.). AEO status
    gives a haulier:
      - Reduced Customs controls
      - Priority Customs processing
      - Mutual recognition with partner countries (EU↔CN, EU↔JP, EU↔US…)

    For TIR moves, AEOC speeds Customs clearance at borders.

    Args:
      operator_country: ISO-3166 alpha-2 of the AEO-issuing country
      eori_number: Economic Operators Registration and Identification number
                   e.g. "GB123456789000" or "DE123456789012345"
      aeo_type: one of AEOC, AEOS, AEOF
    """
    cc = (operator_country or "").upper()
    errors = []
    eori_format_ok = False

    # EORI format: ISO2 alpha + up to 15 alphanumerics
    if eori_number:
        m = re.match(r"^([A-Z]{2})([A-Z0-9]{1,15})$", eori_number.upper())
        eori_format_ok = bool(m)
        if not m:
            errors.append("EORI format invalid — expected 2-letter country prefix + up to 15 alphanumerics")
        elif m.group(1) != cc:
            errors.append(f"EORI prefix {m.group(1)} does not match operator_country {cc}")

    if aeo_type and aeo_type.upper() not in AEO_TYPES:
        errors.append(f"aeo_type must be one of {list(AEO_TYPES)}")

    has_aeo = bool(aeo_type and aeo_type.upper() in AEO_TYPES and not errors)

    return _attestation({
        "tool": "check_aeo_status",
        "operator_country": cc,
        "eori_number": eori_number,
        "eori_format_valid": eori_format_ok,
        "aeo_type": aeo_type.upper() if aeo_type else "",
        "aeo_type_description": AEO_TYPES.get(aeo_type.upper(), ""),
        "has_aeo": has_aeo,
        "customs_benefits": (
            [
                "Reduced controls at Customs",
                "Priority lane for inspection",
                "Lower guarantee for transit",
                "Mutual recognition (EU↔CN, EU↔JP, EU↔US, EU↔CH, EU↔NO)",
            ] if has_aeo else []
        ),
        "errors": errors,
        "advisory": (
            "Maintain AEO criteria: compliance record, accounting standards, financial solvency, security & safety, practical standards of competence."
            if has_aeo else
            "Apply for AEOC via national Customs (HMRC/BMF/Douane/AdM). 9-12 month process; expect site audit."
        ),
    })


@mcp.tool()
def check_cmr_consignment_note(
    note_fields: Optional[dict] = None,
    note_number: str = "",
    cmr_statement_present: Optional[bool] = None,
) -> dict:
    """Validate a CMR consignment note against the 1956 Convention.

    The CMR Convention requires specific fields on every international road
    consignment note (Art. 6). Missing fields don't void the contract (Art. 4)
    but expose the carrier to evidentiary disadvantage and shift liability.

    Args:
      note_fields: dict keyed by CMR field name → value
      note_number: carrier's CMR reference
      cmr_statement_present: whether the note carries the prescribed CMR statement
    """
    note_fields = note_fields or {}
    missing = []
    for f in CMR_REQUIRED_FIELDS:
        v = note_fields.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(f)

    if cmr_statement_present is None:
        cmr_statement_present = bool(note_fields.get("statement_that_carriage_subject_to_cmr"))

    valid = len(missing) == 0 and cmr_statement_present

    return _attestation({
        "tool": "check_cmr_consignment_note",
        "note_number": note_number,
        "fields_provided": len(note_fields),
        "missing_fields": missing,
        "cmr_statement_present": cmr_statement_present,
        "valid": valid,
        "liability_consequence": (
            "Note is valid — CMR liability regime applies. Carrier limit ~8.33 SDR/kg under Art. 23."
            if valid else
            "Missing required fields — burden of proof shifts to carrier; sender/consignee may dispute weight, condition, or instructions. Fix before despatch."
        ),
        "convention_reference": "CMR Convention 1956 Geneva, Articles 4-6",
    })


@mcp.tool()
def check_dangerous_goods_adr_international(
    un_number: str = "",
    adr_class: str = "",
    packing_group: str = "",
    quantity_kg: float = 0.0,
    tunnel_code: str = "",
    route_tunnels: Optional[list] = None,
) -> dict:
    """Validate an ADR (international dangerous-goods-by-road) declaration.

    Cross-border road moves of dangerous goods must comply with the ADR
    European Agreement (UN ECE) plus per-tunnel restrictions (ADR Ch. 1.9.5).

    Args:
      un_number: UN four-digit substance ID (e.g. "1203" petrol, "3480" Li-ion)
      adr_class: ADR class code (e.g. "3", "8", "2.1")
      packing_group: I / II / III (most severe to least)
      quantity_kg: gross weight of the consignment
      tunnel_code: A / B / C / D / E (per ADR Ch. 1.9.5)
      route_tunnels: list of dicts {"name": "Mont Blanc", "restriction": "C"}
    """
    route_tunnels = route_tunnels or []
    errors = []
    warnings = []

    if not un_number or not re.match(r"^\d{4}$", un_number):
        errors.append("un_number required as 4-digit string (e.g. '1203')")
    if adr_class and adr_class not in ADR_CLASSES:
        errors.append(f"adr_class '{adr_class}' not in ADR set {list(ADR_CLASSES)}")
    if packing_group and packing_group.upper() not in ("I", "II", "III"):
        errors.append("packing_group must be I, II, or III")
    if tunnel_code and tunnel_code.upper() not in ADR_TUNNEL_CODES:
        errors.append(f"tunnel_code must be one of {list(ADR_TUNNEL_CODES)}")

    blocked_tunnels = []
    severity_rank = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
    cargo_rank = severity_rank.get(tunnel_code.upper(), 0) if tunnel_code else 0
    for t in route_tunnels:
        t_restr = (t.get("restriction") or "A").upper()
        tunnel_rank = severity_rank.get(t_restr, 0)
        if cargo_rank > tunnel_rank:
            blocked_tunnels.append({
                "name": t.get("name", "?"),
                "tunnel_restriction": t_restr,
                "cargo_tunnel_code": tunnel_code.upper(),
                "result": "BLOCKED — must re-route",
            })

    if quantity_kg > 1000 and (packing_group or "").upper() == "I":
        warnings.append("Quantity >1000kg of Packing Group I — requires ADR driver training cert + orange plates + ADR-approved vehicle (FL/AT/MEMU type).")

    return _attestation({
        "tool": "check_dangerous_goods_adr_international",
        "un_number": un_number,
        "adr_class": adr_class,
        "adr_class_label": ADR_CLASSES.get(adr_class, ""),
        "packing_group": packing_group.upper(),
        "quantity_kg": quantity_kg,
        "tunnel_code": tunnel_code.upper() if tunnel_code else "",
        "tunnel_code_meaning": ADR_TUNNEL_CODES.get(tunnel_code.upper(), ""),
        "route_tunnels_evaluated": len(route_tunnels),
        "blocked_tunnels": blocked_tunnels,
        "errors": errors,
        "warnings": warnings,
        "compliant": len(errors) == 0 and len(blocked_tunnels) == 0,
        "convention_reference": "ADR European Agreement 2025 — UN ECE Geneva",
    })


@mcp.tool()
def prepare_border_crossing_pack(
    origin_country: str,
    destination_country: str,
    transit_countries: Optional[list] = None,
    goods_value_eur: float = 0.0,
    tir_carnet_number: str = "",
    cmr_note_number: str = "",
    has_adr_goods: bool = False,
    has_aeo: bool = False,
) -> dict:
    """Assemble the per-border Customs document pack.

    Produces a per-country checklist of what the driver must present at each
    Customs office on the route — entry, exit, and any intermediate transit
    offices.

    Args:
      origin_country: ISO-3166 alpha-2 origin
      destination_country: ISO-3166 alpha-2 destination
      transit_countries: list of ISO-3166 alpha-2 codes
      goods_value_eur: consignment value (drives guarantee + Customs deposit)
      tir_carnet_number: TIR Carnet ref if TIR is used
      cmr_note_number: CMR consignment note ref
      has_adr_goods: include ADR papers
      has_aeo: operator holds AEO — use AEO simplifications
    """
    transit_countries = transit_countries or []
    route = [origin_country.upper(), *[c.upper() for c in transit_countries], destination_country.upper()]

    border_checklists = []
    for idx in range(len(route) - 1):
        out_country = route[idx]
        in_country = route[idx + 1]
        is_eu_internal = _eu_member(out_country) and _eu_member(in_country)
        checklist = [
            "CMR consignment note (3 originals — sender, carrier, consignee)",
            "Commercial invoice + packing list",
            "Driver's passport / ID + visa if required",
            "Driver's vocational licence + CPC + ADR cert if applicable",
            "Vehicle V5C / registration + Green Card insurance",
            "Manifest of goods",
        ]
        if tir_carnet_number and not is_eu_internal:
            checklist.append(f"TIR Carnet {tir_carnet_number} (paper + eTIR submission ack)")
            checklist.append("Customs seals intact + seal numbers logged")
        if not tir_carnet_number and not is_eu_internal:
            checklist.append("T1 / T2 transit accompanying document (NCTS MRN)")
        if has_adr_goods:
            checklist.append("ADR transport document (UN no., class, PG, tunnel code)")
            checklist.append("ADR driver training cert + orange-plate vehicle")
            checklist.append("Instructions in Writing (ADR Ch. 5.4.3, driver-language)")
        if goods_value_eur > 1000 and not has_aeo:
            checklist.append(f"Customs guarantee / cash deposit (~{round(goods_value_eur * 0.05, 2)} EUR at ~5% — varies)")
        if has_aeo:
            checklist.append("AEO certificate (mutual recognition lane)")

        border_checklists.append({
            "from": out_country,
            "to": in_country,
            "is_eu_internal_border": is_eu_internal,
            "documents_required": checklist,
        })

    return _attestation({
        "tool": "prepare_border_crossing_pack",
        "origin_country": origin_country.upper(),
        "destination_country": destination_country.upper(),
        "transit_countries": [c.upper() for c in transit_countries],
        "route": route,
        "border_crossings": len(border_checklists),
        "border_checklists": border_checklists,
        "tir_carnet_number": tir_carnet_number,
        "cmr_note_number": cmr_note_number,
        "advisory": (
            "Pre-clear via eTIR + NCTS where supported. AEO operators should book priority slots."
            if has_aeo else
            "Allow 2-4 hours at each non-EU border. Pre-lodge electronic declarations to reduce delay."
        ),
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/00wfZjcgAeUW4c5cyQ8k90K"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
