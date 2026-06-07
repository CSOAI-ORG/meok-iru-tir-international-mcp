<!-- mcp-name: io.github.CSOAI-ORG/meok-iru-tir-international-mcp -->
[![MCP Scorecard: 84/100](https://img.shields.io/badge/proofof.ai-84%2F100-5b21b6)](https://proofof.ai/scorecard/meok-iru-tir-international-mcp.html)

# meok-iru-tir-international-mcp

> International road transport compliance: TIR Carnet, CMR consignment note, ADR dangerous goods, AEO status, IRU eTIR, per-border Customs packs. Covers the **78 TIR contracting parties** and IRU's **1,000+ national associations**. By **MEOK AI Labs**.

## Why this exists

A single failed international road move = €2,000-€50,000 in delays, demurrage, re-routing, lost loads, and Customs deposits. TIR Carnet errors can trigger guarantor-association claims up to €100,000 per Carnet.

This MCP gives international hauliers, freight forwarders, and customs brokers the callable toolkit to:
- Decide if TIR is needed
- Generate IRU eTIR data envelopes
- Validate IRU national-association membership
- Check Authorised Economic Operator (AEO) status
- Validate CMR consignment notes
- Route ADR dangerous-goods consignments through tunnel-restricted routes
- Prepare per-border Customs document packs

## Install

```bash
pip install meok-iru-tir-international-mcp
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "iru-tir": {
      "command": "meok-iru-tir-international-mcp"
    }
  }
}
```

## Tools (7)

| Tool | Use case |
|------|----------|
| `check_tir_carnet_requirements` | When is TIR needed? Cross-border sealed-goods transit across 78 countries |
| `generate_tir_carnet_paperwork` | IRU eTIR data envelope — consignment + vehicle approval + Customs sealing |
| `validate_iru_associate_member` | IRU national association lookup (RHA UK, FNTR France, BGL Germany, ASMAP, ZMPD…) |
| `check_aeo_status` | Authorised Economic Operator — speeds Customs clearance, EORI validation |
| `check_cmr_consignment_note` | Convention Marchandises Routières — CMR 1956 note validity |
| `check_dangerous_goods_adr_international` | ADR class checks, tunnel-restriction routing |
| `prepare_border_crossing_pack` | Per-country Customs entry/exit document packs |

## Pricing (EUR — international)

- **Free** — MIT self-host
- **Starter** — €99/mo
- **Pro** — €299/mo (multi-route)
- **Fleet** — €1,499/mo (multi-Carnet + eTIR API integration)

## Regulatory basis

- **TIR Convention 1975** — UN ECE, Geneva (consolidated)
- **CMR Convention 1956** — Convention on the Contract for International Carriage of Goods by Road
- **ADR European Agreement 2025** — UN ECE Dangerous Goods by Road
- **WCO SAFE Framework** — Authorised Economic Operator
- **EU UCC Art. 38 + Implementing Reg. 2015/2447** — AEO criteria
- **IRU eTIR** — digital TIR Carnet, IRU Geneva

## Sign your responses

```bash
export MEOK_HMAC_SECRET="your-secret"
meok-iru-tir-international-mcp
```

## License

MIT © 2026 Nicholas Templeman / MEOK AI Labs · [haulage.app](https://haulage.app)


<!-- GEO-FOOTER:v1 -->

---

### Part of the MEOK constellation

This MCP is one node in a connected ecosystem built by **MEOK AI LABS** around a single
sovereign AI core — governed agents with a hash-chained audit trail, mapped to the CSOAI
compliance charter.

- 🌐 The whole map: **<https://meok.ai/constellation>**
- 🛡️ AI governance & certification: **<https://councilof.ai>** · **<https://csoai.org>**
- ✅ Verify any signed report: **<https://meok.ai/verify>**
