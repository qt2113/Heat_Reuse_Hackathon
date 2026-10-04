# Bundled fallback data (used only when live downloads fail)

* `ll84_sample.csv` – snapshot of NYC LL84 dataset 5zyy-y8am (report years 2022-2024), rows within
  1,100 m of 111 8th Ave, downloaded 2026-10-03. Real data, but frozen.
* `pluto_sample.csv` – snapshot of PLUTO (64uk-42ks) lots within 1,100 m, downloaded 2026-10-03.
* Weather fallback is **synthetic** (NOAA Central Park normals as a sinusoid), generated in code.
* Street fallback is a **synthetic** Manhattan grid, generated in code.

The app labels every dataset as LIVE / CACHE / SAMPLE.
