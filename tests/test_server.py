import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import (
    check_tir_carnet_requirements,
    generate_tir_carnet_paperwork,
    validate_iru_associate_member,
    check_aeo_status,
    check_cmr_consignment_note,
    check_dangerous_goods_adr_international,
    prepare_border_crossing_pack,
    TIR_CONTRACTING_PARTIES,
    IRU_GUARANTEEING_ASSOCIATIONS,
    CMR_REQUIRED_FIELDS,
    ADR_CLASSES,
    ADR_TUNNEL_CODES,
    AEO_TYPES,
    ETIR_DATA_ELEMENTS,
)


def _call(t, **kw):
    fn = t.fn if hasattr(t, "fn") else t
    return fn(**kw)


# ────────────────────────────────────────────────────────────
# check_tir_carnet_requirements
# ────────────────────────────────────────────────────────────

def test_tir_required_gb_to_tr():
    r = _call(check_tir_carnet_requirements,
              origin_country="GB", destination_country="TR",
              transit_countries=["FR", "DE", "AT", "HU", "RO", "BG"],
              sealable=True, goods_under_customs_control=True)
    assert r["decision"] == "TIR_REQUIRED"
    assert r["all_tir_contracting_parties"] is True
    assert r["border_crossings"] == 7


def test_tir_not_needed_intra_eu():
    r = _call(check_tir_carnet_requirements,
              origin_country="DE", destination_country="FR",
              transit_countries=["BE"],
              sealable=True, goods_under_customs_control=True)
    assert r["decision"] == "NOT_NEEDED"
    assert "NCTS" in r["reason"]


def test_tir_not_usable_non_party_route():
    # Vietnam (VN) is not a TIR party
    r = _call(check_tir_carnet_requirements,
              origin_country="CN", destination_country="VN",
              transit_countries=[],
              sealable=True, goods_under_customs_control=True)
    assert r["decision"] == "NOT_USABLE"
    assert "VN" in r["non_party_countries"]
    assert r["alternative_if_not_usable"]


def test_tir_not_usable_when_not_sealable():
    r = _call(check_tir_carnet_requirements,
              origin_country="DE", destination_country="TR",
              transit_countries=["AT", "HU", "RO", "BG"],
              sealable=False, goods_under_customs_control=True)
    assert r["decision"] == "NOT_USABLE"
    assert "sealable" in r["reason"]


def test_tir_no_border_crossing():
    r = _call(check_tir_carnet_requirements,
              origin_country="FR", destination_country="FR",
              transit_countries=[],
              sealable=True, goods_under_customs_control=True)
    assert r["decision"] == "NOT_NEEDED"


# ────────────────────────────────────────────────────────────
# generate_tir_carnet_paperwork
# ────────────────────────────────────────────────────────────

def test_carnet_valid_full_payload():
    r = _call(generate_tir_carnet_paperwork,
              holder_id="GB/021/0000123",
              guaranteeing_association="GB",
              consignor={"name": "Acme Ltd", "country": "GB"},
              consignee={"name": "Anadolu Lojistik", "country": "TR"},
              approved_vehicle={"reg": "AB12CDE", "vin": "WDB",
                                "type_approval_cert": "TIR-GB-2026-99",
                                "expiry": "2027-12-31"},
              goods_manifest=[{"hs": "8418.10", "kg": 12000, "value": 35000}],
              route=[
                  {"office_code": "GBDOV1", "country": "GB", "type": "departure"},
                  {"office_code": "FRCQF1", "country": "FR", "type": "transit_entry"},
                  {"office_code": "TRKAP1", "country": "TR", "type": "destination"},
              ],
              carnet_number="XB.123.456.789")
    assert r["ready_to_submit"] is True
    assert r["voucher_count_required"] == 3
    assert r["carnet_number_format_valid"] is True
    assert r["errors"] == []


def test_carnet_expired_vehicle_approval():
    r = _call(generate_tir_carnet_paperwork,
              holder_id="GB/021/0000123",
              guaranteeing_association="GB",
              approved_vehicle={"type_approval_cert": "TIR-GB-2010-1",
                                "expiry": "2020-01-01"},
              goods_manifest=[{"hs": "8418.10"}],
              route=[{"office_code": "GBDOV1"}, {"office_code": "TRKAP1"}],
              carnet_number="XB.123.456.789")
    assert any("lapsed" in e for e in r["errors"])
    assert r["ready_to_submit"] is False


def test_carnet_invalid_number_format():
    r = _call(generate_tir_carnet_paperwork,
              holder_id="GB/021/123",
              guaranteeing_association="GB",
              approved_vehicle={"type_approval_cert": "TIR-GB-2026-99",
                                "expiry": "2027-12-31"},
              goods_manifest=[{"hs": "8418.10"}],
              route=[{"office_code": "X"}, {"office_code": "Y"}],
              carnet_number="not-valid")
    assert r["carnet_number_format_valid"] is False
    assert r["ready_to_submit"] is False


# ────────────────────────────────────────────────────────────
# validate_iru_associate_member
# ────────────────────────────────────────────────────────────

def test_iru_rha_uk_affiliated():
    r = _call(validate_iru_associate_member, operator_name="Acme Haulage Ltd", country_code="GB")
    assert r["iru_affiliated"] is True
    assert "Road Haulage Association" in r["association_name"]


def test_iru_fntr_france_affiliated():
    r = _call(validate_iru_associate_member, operator_name="Transports XYZ", country_code="FR")
    assert r["iru_affiliated"] is True
    assert "FNTR" in r["association_name"]


def test_iru_unknown_country():
    r = _call(validate_iru_associate_member, operator_name="X", country_code="ZZ")
    assert r["iru_affiliated"] is False
    assert r["tir_carnet_issuance_authorised"] is False


def test_iru_us_no_tir_issuance():
    r = _call(validate_iru_associate_member, operator_name="Acme Inc", country_code="US")
    assert r["iru_affiliated"] is False


# ────────────────────────────────────────────────────────────
# check_aeo_status
# ────────────────────────────────────────────────────────────

def test_aeo_full_gb():
    r = _call(check_aeo_status, operator_country="GB",
              eori_number="GB123456789000", aeo_type="AEOF")
    assert r["has_aeo"] is True
    assert r["eori_format_valid"] is True
    assert "Mutual recognition" in " ".join(r["customs_benefits"])


def test_aeo_eori_mismatch_country():
    r = _call(check_aeo_status, operator_country="DE",
              eori_number="GB123456789000", aeo_type="AEOC")
    assert any("prefix" in e for e in r["errors"])
    assert r["has_aeo"] is False


def test_aeo_invalid_eori_format():
    r = _call(check_aeo_status, operator_country="DE",
              eori_number="!!!", aeo_type="AEOC")
    assert r["eori_format_valid"] is False
    assert any("invalid" in e.lower() for e in r["errors"])


def test_aeo_bad_type():
    r = _call(check_aeo_status, operator_country="DE",
              eori_number="DE12345", aeo_type="GOLD")
    assert r["has_aeo"] is False
    assert any("aeo_type" in e for e in r["errors"])


# ────────────────────────────────────────────────────────────
# check_cmr_consignment_note
# ────────────────────────────────────────────────────────────

def test_cmr_valid_note():
    fields = {f: "filled" for f in CMR_REQUIRED_FIELDS}
    r = _call(check_cmr_consignment_note,
              note_fields=fields, note_number="CMR-2026-001",
              cmr_statement_present=True)
    assert r["valid"] is True
    assert r["missing_fields"] == []


def test_cmr_missing_fields():
    fields = {"sender_name_address": "Acme GmbH"}
    r = _call(check_cmr_consignment_note,
              note_fields=fields, note_number="CMR-2026-002")
    assert r["valid"] is False
    assert len(r["missing_fields"]) >= 5
    assert "carrier_name_address" in r["missing_fields"]


# ────────────────────────────────────────────────────────────
# check_dangerous_goods_adr_international
# ────────────────────────────────────────────────────────────

def test_adr_petrol_compliant_no_tunnel_block():
    r = _call(check_dangerous_goods_adr_international,
              un_number="1203", adr_class="3", packing_group="II",
              quantity_kg=22000, tunnel_code="D",
              route_tunnels=[{"name": "Karawanken", "restriction": "D"}])
    assert r["compliant"] is True
    assert r["blocked_tunnels"] == []
    assert r["adr_class_label"] == "Flammable liquid"


def test_adr_blocked_by_tunnel():
    # Cargo needs tunnel D but route includes a B tunnel
    r = _call(check_dangerous_goods_adr_international,
              un_number="1203", adr_class="3", packing_group="II",
              quantity_kg=22000, tunnel_code="D",
              route_tunnels=[{"name": "Mont Blanc", "restriction": "B"}])
    assert r["compliant"] is False
    assert len(r["blocked_tunnels"]) == 1
    assert r["blocked_tunnels"][0]["name"] == "Mont Blanc"


def test_adr_invalid_un_number():
    r = _call(check_dangerous_goods_adr_international,
              un_number="ABC", adr_class="3", packing_group="II",
              quantity_kg=100)
    assert r["compliant"] is False
    assert any("un_number" in e for e in r["errors"])


def test_adr_packing_group_i_large_qty_warning():
    r = _call(check_dangerous_goods_adr_international,
              un_number="1203", adr_class="3", packing_group="I",
              quantity_kg=2000, tunnel_code="A")
    assert any("ADR driver training" in w for w in r["warnings"])


# ────────────────────────────────────────────────────────────
# prepare_border_crossing_pack
# ────────────────────────────────────────────────────────────

def test_border_pack_gb_to_tr_with_tir():
    r = _call(prepare_border_crossing_pack,
              origin_country="GB", destination_country="TR",
              transit_countries=["FR", "DE", "AT", "HU", "RO", "BG"],
              goods_value_eur=50000, tir_carnet_number="XB.123.456.789",
              cmr_note_number="CMR-001", has_adr_goods=False, has_aeo=False)
    assert r["border_crossings"] == 7
    # Find a non-EU-internal border (GB->FR is post-Brexit non-internal)
    gb_to_fr = r["border_checklists"][0]
    assert any("TIR Carnet" in d for d in gb_to_fr["documents_required"])


def test_border_pack_intra_eu_no_tir():
    r = _call(prepare_border_crossing_pack,
              origin_country="DE", destination_country="ES",
              transit_countries=["FR"],
              goods_value_eur=10000)
    assert r["border_crossings"] == 2
    de_to_fr = r["border_checklists"][0]
    assert de_to_fr["is_eu_internal_border"] is True
    # Intra-EU border: NO TIR/T1 required
    assert not any("TIR Carnet" in d for d in de_to_fr["documents_required"])
    assert not any(d.startswith("T1") for d in de_to_fr["documents_required"])


def test_border_pack_adr_includes_orange_plates():
    r = _call(prepare_border_crossing_pack,
              origin_country="DE", destination_country="TR",
              transit_countries=["AT", "HU", "RO", "BG"],
              goods_value_eur=80000, tir_carnet_number="XB.999.999.999",
              has_adr_goods=True, has_aeo=True)
    docs = r["border_checklists"][-1]["documents_required"]
    assert any("orange-plate" in d for d in docs)
    assert any("AEO certificate" in d for d in docs)


# ────────────────────────────────────────────────────────────
# attestation chain
# ────────────────────────────────────────────────────────────

def test_attestation_chain_present():
    r = _call(check_aeo_status, operator_country="DE",
              eori_number="DE12345", aeo_type="AEOC")
    assert "sig" in r
    assert "ts" in r
    assert r["issuer"] == "meok-iru-tir-international-mcp"
    assert r["version"] == "1.0.0"


def test_attestation_signed_when_secret_set(monkeypatch):
    import server
    monkeypatch.setattr(server, "_HMAC_SECRET", "test-secret-key")
    r = _call(check_tir_carnet_requirements,
              origin_country="GB", destination_country="FR")
    assert r["sig"] != "unsigned-no-key-configured"
    assert len(r["sig"]) == 64  # sha256 hex


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
