# Thailand boundary / provenance / trust anchors

## Boundary (offline asset)
- Source: **Natural Earth**, Admin 0 countries **1:50m**, `ADM0_A3=THA`.
- Repository revision: `ca96624a56bd078437bca8184e78163e5039ad19`.
- Exact URL and SHA-256 of original worldwide GeoJSON: [`source.json`](source.json).
- License: **public domain**, [Natural Earth terms](https://www.naturalearthdata.com/about/terms-of-use/) (reviewed 2026-10-25). Made with Natural Earth.
- `thailand.geojson` is the original Thailand Feature extracted without coordinate changes (MultiPolygon, all rings/islands retained). It is not a manually drawn outline.
- `tools/generate_thailand.py` rasterizes polygon rings/holes using pixel-centre even/odd tests to `src/thailand_mask.h`: 112×174, 2,436 bytes in flash, WGS84 longitude 97..106, latitude 5.5..20.7. This rasterization is the offline display simplification; no arbitrary fabricated vertices. Islands narrower than a pixel may disappear. Not for navigation or legal boundary use.
- 25 model sampling locations: interior 1.5-degree grid, plus interior southern-peninsula points. Generator checks containment in original polygons. These are not measurement stations.

Regenerate without network: `python tools/generate_thailand.py`.
Download pinned upstream and regenerate: `python tools/generate_thailand.py --download` (stdlib only). Keep `source.json` and extracted GeoJSON with the generated header.

## TLS
`src/api_roots.h` embeds public ISRG Root X1 and X2 PEM trust anchors, retrieved from:
- https://letsencrypt.org/certs/isrgrootx1.pem
- https://letsencrypt.org/certs/isrg-root-x2.pem
- https://letsencrypt.org/certificates/ ([ISRG repository/license](https://github.com/letsencrypt/website/tree/main/static/certs))

Both Open-Meteo hosts were checked against their Let's Encrypt chains on 2026-10-25. Firmware validates hostname/chain/dates, waits for NTP, and fails closed; no `setInsecure`. Roots/issuer policy may change: update trust anchors deliberately if HTTPS begins failing, never disable validation. These certificates are public, not secrets. SNTP itself is not authenticated; clock bootstrap inherits that limitation.

## Data attribution / usage
- [Open-Meteo weather documentation](https://open-meteo.com/en/docs): current `temperature_2m`, Celsius, model air temperature at 2m (not land surface temperature).
- [Open-Meteo air quality documentation](https://open-meteo.com/en/docs/air-quality-api): current `pm2_5`, µg/m³, `domains=cams_global`. Thailand uses **CAMS Global atmospheric composition forecasts**, approximately 0.4°/45km, 3-hourly native output, updated every 12h. API current output can have an hourly/interpolated timestamp; it is not a live station observation.
- Credit: **Open-Meteo; Copernicus Atmosphere Monitoring Service (CAMS), CAMS ENSEMBLE data providers**. The API documentation requests Open-Meteo and CAMS ENSEMBLE attribution; Thailand data specifically come from the global domain. UI includes a short attribution; documentation supplies the links and details.
- API data: **CC BY 4.0**, https://creativecommons.org/licenses/by/4.0/ . This project transforms sampled data with inverse-distance-weighted interpolation and a fixed color scale, clipped to the rasterized Thailand boundary. Interpolation adds visual smoothness, not scientific resolution; no health/safety or emergency decisions.
- [Free API terms](https://open-meteo.com/en/terms), reviewed 2026-10-25: **non-commercial only**, no API key; <10,000 calls/day, 5,000/hour, 600/minute, table also lists 300,000/month. Multi-location queries can count as multiple calls: conservatively 25 points × 2 datasets × 24 refreshes = **1,200 location-calls/day/device** before retries. Shared public IP / multiple boards share limits. Commercial use requires a suitable paid plan and endpoint change.
- Only fixed public sample coordinates are sent; no WiFi SSID/password or device GPS. Provider sees source public IP and requested coordinates; terms describe log retention up to 90 days. Internet/WiFi data charges may apply. Availability and accuracy are not guaranteed.
