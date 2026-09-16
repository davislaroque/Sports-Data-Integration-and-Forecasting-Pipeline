# Pipeline design and scope

## Main workflow

1. Ingestion retrieves standard markets in bulk, or player props for one event. HTTP GET requests use connection/read timeouts and two retries for transient statuses. Errors omit credential-bearing URLs.
2. Processing retains `game_id`, bookmaker, market, player, outcome, raw line, and normalized `contract_line`. Spread contract lines use the home-team perspective.
3. Each complete two-outcome contract is normalized within its bookmaker. `implied_prob = 1 / decimal_odds`; `devig_prob` divides by the sum for that bookmaker and contract. Incomplete/invalid groups keep `NaN`.
4. Analysis compares the best decimal odds for identical event/market/player/line combinations. The reported percentage is equal-payout ROI, rather than the probability shortfall below one.
5. The CLI writes normalized data, comparisons, and deduplicated quote history. The Streamlit app supports explicit sample/live selection and a five-minute live-data cache.

## Persistence

History deduplicates event, bookmaker, market, player, outcome, line, price, update time, and odds format when present. Re-ingesting an identical quote does not add another row. A changed price or provider update timestamp creates a new row. The CSV is replaced atomically, but concurrent writers are not supported; use a transactional database before scheduling overlapping jobs.

The bundled fixture is synthetic and covers h2h only. Live player props require an event ID and the relevant API access. A successful offline demo is not evidence that a particular key or subscription can access live props.

## Modeling boundaries

`features.build_features` represents a row observed after a game and sets the following game's points/date as the target. When splitting, ensure all training target dates precede the first evaluation prediction time. `evaluation.backtest` requires aligned binary outcomes and actual offered prices. It does not model pushes or simultaneous bankroll exposure.

The V2 UI uses `true_prob` as a legacy column name for the core `devig_prob` estimate. It is not an independent learned probability. These calculations do not demonstrate profitability. The separate Sports_Prediction_Model repository contains the reproducible regression workflow.

## Next steps

- Validate quote timestamps and market freshness before comparing prices.
- Replace single-writer CSV history with a database if ingestion becomes concurrent.
- Connect documented historical outcomes for model calibration and walk-forward evaluation.
