# Contratos de dados

## ERA5 processado por ponto/célula

Chaves mínimas:
- `time`: timestamp UTC monotônico;
- `latitude`, `longitude`;
- `cell_id`: identificador estável da unidade espacial.

Variáveis mínimas candidatas:
- `t2m_c`;
- `d2m_c`;
- `vpd_kpa`;
- `surface_pressure_hpa`;
- `wind_speed_10m`;
- `precip_mm_hour_ending`.

## Perturbação agregada por célula

Chaves:
- `cell_id`;
- `reference_year` ou janela temporal.

Features planejadas:
- `forest_fraction`;
- `forest_loss_fraction`;
- `deforested_area_km2`;
- `fire_pressure`;
- `recent_deter_area_km2`;
- `disturbance_class` (somente depois de congelar definição).

## Série pronta para dinâmica não linear

Metadados obrigatórios:
- `series_id`;
- `cell_id`;
- variável;
- preprocessing (`raw`, `diurnal_anomaly`, `seasonal_anomaly`...);
- período;
- frequência;
- número de amostras;
- percentual ausente;
- configuração/commit/manifests de origem.
