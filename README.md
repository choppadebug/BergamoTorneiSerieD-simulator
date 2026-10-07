# Bergamo Tornei Serie D

A dependency-free Python Monte Carlo simulator for end-of-season points by finishing position. Requires Python 3.10 or later.

## Web app: run locally

From the repository root:

```powershell
python serve.py --port 8000
```

Open **http://127.0.0.1:8000** in a modern browser. Stop the server with `Ctrl+C`. This server serves the static app and a restricted `/api/live` proxy for public Bergamo standings. Use HTTP instead of double-clicking `index.html`: browser workers and source loading require a served site. `python -m http.server 8000 --bind 127.0.0.1` still serves the baseline, but does not provide the live import endpoint.

No npm install or frontend build step is required. The site runs the actual Python simulation modules in a [Pyodide](https://pyodide.org/en/stable/usage/webworker.html) module worker, keeping the page responsive. [Chart.js](https://www.chartjs.org/docs/latest/charts/line.html) renders the charts. Dependencies are pinned to Pyodide 314.0.7 and Chart.js 4.5.1 on jsDelivr. The first run downloads the Python runtime and needs internet access; subsequent runs reuse it. Fonts load from Google Fonts with local fallbacks. This is not an offline app. Live remote imports need the local server or the optional hosted proxy; a published snapshot works entirely on static hosting.

### Controls and results

| CLI option | Web control |
| --- | --- |
| `--simulations` | Simulated seasons slider, 1,000–50,000 |
| `--teams` | Teams slider, 4–24 |
| `--legs` | Legs slider, 1–4 |
| `--draw-probability` | Baseline draw probability slider, 0–100% |
| `--confidence` | Central prediction range slider, 50–99% |
| `--historical-calibration` | Enable checkbox plus influence slider, 0–100% |
| `--historical-dir` | Bundled file checkboxes plus local CSV file selection |
| `--seed` | Integer seed field, 0–2,147,483,647 |
| `--csv` | Download CSV button after a completed run |

The sliders use practical browser limits; the CLI still supports its original wider ranges. A seed is an exact integer field rather than a slider so it can be reproduced reliably. Select CSV files to substitute for a local directory, which a hosted page cannot read by path. Added CSVs replace bundled files with matching names. Source contents are processed in browser memory, not sent to an application backend. Bundled CSVs are publicly downloadable when you publish the site.

Click **Simulate season** to run. Settings are locked while working. Cancel terminates the worker, including calibration, and the next run reloads the runtime. Identical source sets reuse the latest historical fit within a worker. Changing settings afterward labels existing results as stale until you rerun. Download always exports the displayed run, including its effective settings.

- **Projected table chart:** finishing position on the horizontal axis and points on the vertical axis. The solid line is the median. The shaded region runs between the lower and upper prediction bounds. Hover for exact values; optional checkboxes add the mean and top-k benchmark. Bounds are also available in the table.
- **Position distribution chart:** choose a finishing position with the slider. Each bar is the percentage of simulated seasons where that position earned a particular number of points. Teal bars lie within the reported central range; pale bars are outside. The expandable data table gives exact counts. This describes points conditional on a rank, not the probability of a rank conditional on points.
- **Assumptions and historical sources:** effective draw probability, strength spread, calibration input/exclusions, and any fit-boundary warning accompany the results.

## Publish with GitHub Pages

The repository root is already a static site with `index.html` and `.nojekyll`. Follow [GitHub's Pages setup instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site):

1. Commit and push these files to your GitHub repository. Keep the Python modules and `input/` alongside the web files.
2. In **Settings → Pages → Build and deployment**, select **GitHub Actions** to use the included daily refresh/deployment workflow.
3. Push to `main`, or run **Refresh standings and deploy Pages** from the Actions tab. If your default branch has another name, update `.github/workflows/pages.yml`.
4. Once deployment completes, visit the URL shown in Pages settings, usually `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/`.

All local asset paths are relative, so a repository subpath works. The workflow fetches the default tournament's standings/calendars each day at 05:23 UTC, runs tests, and deploys only the static app and its snapshot. It does not commit generated snapshots back to Git. Scheduled workflows run on the default branch and can be delayed; always check the displayed fetch time. If fetching or tests fail, the previous deployment remains. See [GitHub scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). No publishing action has been executed in this workspace.

Branch-based Pages hosting also works, but snapshots then require manual refresh and commit. Do not enable both deployment methods. On static hosting without a proxy, the default URL loads the published snapshot; custom URLs require the proxy below or a JSON snapshot upload.

If Git is already configured for the repository, review changes and publish with:

```powershell
git status
git add index.html styles.css app.js live.js worker.js web_runner.py league_simulator.py historical_calibration.py live_standings.py live_projection.py live_fetch.py serve.py live-config.json input/ data/ proxy/ .github/workflows/pages.yml .nojekyll update_manifest.py test_web_runner.py test_live.py README.md
git commit -m "Add browser season simulator for GitHub Pages"
git push origin main
```

Replace `main` with your publishing branch. For a new checkout without Git, first create an empty repository on GitHub, then run the following before the add/commit commands above (skip these if Git is already configured):

```powershell
git init -b main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
```

Use `git push -u origin main` for the first push. Substitute your actual repository URL. If the remote already contains commits, clone it first and copy the project into that clone instead of initializing unrelated history.

After adding/removing bundled CSVs, refresh their list and commit both the CSVs and manifest:

```powershell
python update_manifest.py
```

Changes to existing CSV contents need no manifest update. New or corrected sources are validated again on the next fit. Uploads selected in the browser are temporary and are not added to the repository.

## Verification

```powershell
python -m unittest -v
node --check app.js
node --check worker.js
node --check live.js
node --check proxy/worker.mjs
```

Node is optional and used here only for JavaScript syntax checks. The Python tests check that web results match native results and that each rank's histogram accounts for every simulated season.

For a browser smoke test, run the local server, simulate the default 10,000 seasons (champion median 37), enable full historical influence with all bundled files (current champion median 53), inspect exclusions, change the selected position, and download the CSV. Change settings and verify the stale-result notice. Start a longer run, cancel, then rerun. Check narrow/mobile layout and keyboard control access. To exercise repository-subpath hosting locally, serve the parent directory and navigate to this repository's folder URL.

If dependencies fail to load, check access to jsDelivr and reload. Browser errors appear next to the run button. A calibration run with no eligible selected tables reports an error rather than silently falling back to the baseline.

## Current-season projections

After completing a baseline simulation, the **Project the rest of your season** section becomes available:

1. Keep the default [2026/27 tournament URL](https://www.bergamotornei.com/it/t-teamtable/154/campionato-nazionale-asi-bergamo-tornei-calcio-a-7/) or enter another Bergamo Tornei standings URL.
2. Click **Load / refresh standings**. The source and fetch time are always shown. On local `serve.py` or with a configured hosted proxy, this fetches the source now. On GitHub Pages without a proxy, the default URL uses `data/live.json`, explicitly labeled as a snapshot. Snapshots older than 36 hours are flagged.
3. Choose a league, then a team in that league. All imported columns are available in the expandable standings table.
4. Check the number of legs and choose the prior-strength slider. Click **Project remaining season**. The completed baseline supplies simulation count, confidence, seed and the effective draw prior; the selected league supplies the actual team count.
5. Inspect final-position probabilities, updated rank points ranges, and projected accumulated points by scheduled date. Change teams or the comparison rank without rerunning. Download a team forecast CSV with source and run metadata.

Refresh the source after new results to get a new conditional forecast. The future trajectory is a forecast from one snapshot, not observed future data or a forecast of how final-position probabilities will change after unknown outcomes. Scheduled dates are not guaranteed match dates.

### What is imported and how it is linked

The source page is an AJAX shell. Its public `system/include/ajax/public/league.php` endpoint uses `op=20&tid=...&round=all` for standings and `op=22&tid=...&round=LEAGUE_ID` for the full calendar. The standings markup has `.standing-table-title` followed by `.tables-container`. Team names/positions are in its `.left-table`; stat rows are in the matching `.right-table`. The parser pairs these rows only inside the same container and reads stat columns by their headers. It matches the league title to the page's `select[name=round]` options to obtain the calendar ID.

The calendar includes completed scores, unplayed matches and explicit `Turno di riposo` byes. Byes are skipped. A numeric 0–0 is a completed draw; an empty score pane is unplayed. Unsupported statuses are rejected. Dates are interpreted within the source's July–June season (e.g. October 2026 and January 2027 for 2026/27). Dates without enough information remain undated and are grouped last.

Custom links currently mean other `/it/t-teamtable/ID/name/` pages on `bergamotornei.com`, not arbitrary websites with unrelated schemas. Fetchers restrict requests to this public host and known standings/calendar operations and reject redirects.

### Forecast model and data checks

- **Pt:** official points are the starting totals. Any difference from `3V + N` is preserved and reported as a points adjustment.
- **G/V/N/P:** validate games/results against completed calendar fixtures and estimate strength from a shrunk win/loss ratio. The prior contributes half a win and half a loss per equivalent game, tempering early extremes.
- **F/S:** a shrunk scoring/conceding ratio contributes 35% of the strength estimate; the result ratio contributes 65%. This is a transparent heuristic, not a trained weight. The scoring prior is pooled from current goals, with a starting assumption of 2.5 goals per team-game.
- **+/−:** checked against F minus S; it is not counted again as independent evidence.
- **FP:** imported as fair play and displayed. It does not affect strength or tie-breaks because those rules have not been confirmed.

Live team strengths replace the baseline's anonymous randomly drawn strengths and stay fixed during simulation. Historical calibration informs the baseline draw prior; its anonymous strength-spread parameter is not reused as a named-team rating. The live draw rate pools observed draws with 20 prior matches at the baseline effective draw rate. Conditional decisive-match probabilities use the logistic difference between the two shrunk team strengths. No home advantage or opponent adjustment is fitted. These choices need backtesting before claiming an accuracy improvement.

Only actual remaining fixtures are simulated, starting from the official points totals. Every pairing must occur the selected number of times in the complete calendar; completed games, wins/draws/losses and goals must reconcile with the table. No synthetic fixtures are added to fix missing data. Inconsistencies block that league's forecast with a specific error. In the initial 7 October 2026 snapshot, seven leagues reconcile, including all four Serie D groups; Serie B is blocked because Prezzatese's calendar wins disagree with its table. A later refreshed source may resolve this.

Future equal-points ties use random ordering. A fully completed, reconciled season retains the official imported order. Official future goal-difference/head-to-head/fair-play tie-breaks and uncertainty in estimated strengths are not modeled. Prediction ranges reflect match-result variability conditional on the estimates.

The selected team's final-position bars sum to 100% before rounding. The table also reports its points range **conditional on finishing at each rank**, along with the number of supporting simulations. Rare ranks can have unstable ranges or no samples. The day-by-day chart compares the selected team's accumulated points with points held by a chosen rank at each scheduled date; it is not a final-rank cutoff at that date.

### Refresh or export a snapshot

```powershell
python live_fetch.py --output data/live.json
python live_fetch.py --url "https://www.bergamotornei.com/it/t-teamtable/154/campionato-nazionale-asi-bergamo-tornei-calcio-a-7/" --output output/my-tournament.json
```

The JSON contains all leagues and calendars and can be selected under **Import and connection options**. The default export is used by Pages without a proxy. With branch-based deployment, commit/push the updated file; with the included Actions workflow, it is generated during each deployment. The public source is fetched directly by the local exporter; no third-party scraping service is used.

### Optional live proxy for GitHub Pages and custom URLs

The source does not return `Access-Control-Allow-Origin`, so a GitHub Pages browser cannot directly read its responses. The supplied [Cloudflare Worker proxy](https://developers.cloudflare.com/workers/examples/cors-header-proxy/) is a small, restricted bridge; simulation still happens in the browser.

1. Set `ALLOWED_ORIGIN` in `proxy/wrangler.jsonc` to your Pages origin, e.g. `https://YOUR-USERNAME.github.io` (no repository path).
2. With a Cloudflare account and Node.js available, deploy from the project root:

```powershell
npx wrangler login
npx wrangler deploy --config proxy/wrangler.jsonc
```

3. Put the returned HTTPS Worker URL in `live-config.json` as `proxy_url`, then redeploy the static app. Alternatively enter it in the page's **Live proxy endpoint** field for that session.

```json
{"proxy_url": "https://bergamo-standings-proxy.YOUR-SUBDOMAIN.workers.dev/"}
```

The proxy has not been deployed automatically. Local development with `python serve.py` needs no Cloudflare setup. If a user opens the page with the old plain `http.server`, stop it and use `serve.py` to enable live imports.

## Run

```powershell
python league_simulator.py
python league_simulator.py --simulations 10000 --confidence 0.90 --draw-probability 0.25 --seed 42 --csv output/projections.csv
python -m unittest -v
```

Defaults: 11 teams, two legs, 20 matches per team, 110 matches per season, and 3/1/0 points for win/draw/loss. You can also change `--teams` and `--legs`. A fixed seed makes runs reproducible.

## Initial model

The following equal-strength assumptions apply when historical calibration is disabled (the default).

All teams are equally strong. Each match is independent, with a 25% draw probability and a 37.5% probability of either team winning. The draw rate is a configurable starting assumption, not an estimate from your league. There is no home advantage. The simulator plays every pairing once per leg, so the opponents' points are coupled through actual match outcomes. It does not generate team totals independently.

Teams tied on points receive a random tie-break. This does not change the points reported for each position. Goals, goal difference, head-to-head results, and named-team forecasts are not yet modeled. Scheduling dates and byes are unnecessary for this initial full-season model.

## Reading the output

For each finishing position, the simulator reports:

- **Mean and median:** typical end-of-season points for that position across simulations.
- **Range:** the central prediction interval selected with `--confidence`. At 0.90 this runs from the empirical 5th to 95th percentile. Integer/discrete scores can make coverage exceed 90%. These are individual position ranges, not a simultaneous 90% band for the whole table.
- **Top-k benchmark:** one point above the empirical 90th percentile of position k's points (or your selected confidence percentile). This strictly beats that position's points in at least the selected fraction of simulated tables. It is a conservative planning reference for finishing at least that high. Last place has a benchmark of zero because every team finishes in the top 11.

For example, the default run gives third place a median of 32, a central 90% range of 29–35, and a top-three benchmark of 35. The range uses the 5th and 95th percentiles, while the benchmark uses the 90th percentile plus one; they answer different questions.

**The benchmark is not a claim that a team earning 35 points has a 90% probability of finishing in the top three.** That would require estimating finishing position conditional on that team's points and assumptions about its strength. Changing a team's results also changes opponents' points. Similarly, a points range for third place does not mean every team within that range finishes third. Position ranges overlap.

These ranges describe season-to-season variability under the model, not confidence intervals for an estimated mean. Increasing simulation count stabilizes the estimates; it does not remove real season variability or uncertainty about model assumptions. Extremely small simulation counts or extreme confidence levels give unreliable tail estimates. In extreme settings a strict benchmark can even exceed the attainable points maximum; it is then unattainable, not a recommended target.

## Useful next parameters

1. **Opponent-adjusted team strength:** improve the current aggregate-results heuristic with match-level ratings and backtesting.
2. **Draw frequency by matchup:** extend the historical/current pooled draw rate to reflect differences between opponents.
3. **Forecast evaluation over time:** retain dated snapshots and compare predictions against later results to measure accuracy and interval coverage.
4. **Home advantage:** if venue or home status matters in this league.
5. **Goals and official tie-break rules:** simulate scorelines and resolve equal points according to league rules.
6. **Form and availability:** injuries, absences, roster changes, or changing strength over the season.

Current-season mode now reports named teams' finishing probabilities. Estimating a top-k finish conditional on a specific points total, and validating its reliability, remain possible extensions.

## Historical standings: proposed calibration

### Optional historical influence

```powershell
python league_simulator.py --historical-calibration 0.5 --simulations 10000
python league_simulator.py --historical-calibration 1 --historical-dir input --csv output/calibrated.csv
```

`--historical-calibration` accepts 0 through 1, default 0. Zero preserves the baseline and does not read historical files. One uses the full fitted model. Intermediate values blend parameters, not final points or entire tables:

- Effective draw probability = `(1 - magnitude) * baseline_draw_probability + magnitude * historical_draw_probability`.
- Effective strength standard deviation = `magnitude * fitted_strength_standard_deviation`.

`--draw-probability` sets the baseline end of the blend; at magnitude 1 it has no effect. Magnitude is an influence control, not a confidence level or a fitted probability that history is relevant. Its effect on points need not be linear. `--confidence` independently controls prediction ranges.

The first implementation accepts only arithmetically consistent, complete double-round-robin tables, of any team count, and prints included files and exclusions. It does not infer missing columns, penalties, or completion status. The seven-game 2021/22 edition is excluded until its format is confirmed. Positive calibration with no eligible data fails explicitly.

Each simulated season draws anonymous team strengths from a normal distribution; those strengths stay fixed throughout that season. Conditional on a decisive match, the home win probability is `1 / (1 + exp(away_strength - home_strength))`. Draw probability is constant across pairings. There is no home advantage.

The fit matches the average within-table population variance of points per game. For each candidate strength spread (0 to 4 in steps of 0.2), it simulates 500 seasons at each historical team count, using the pooled historical draw rate. Each eligible table has equal weight in the variance target; matches have equal weight in the draw estimate. A fixed calibration seed makes the fit reproducible independently of the forecast seed and simulation count. A boundary fit prints a warning. This is a coarse method-of-moments fit, not a fit of the entire rank distribution.

The current fit is a single parameter estimate. Prediction intervals include random team strengths and match outcomes, but do not yet include uncertainty in the fitted parameters. Season-level validation, resampling, division weighting, and single-leg/partial-season support remain future work. No calibrated magnitude is claimed to be optimal.

The files in `input/` are used when historical calibration is enabled (see below). Keep original files unchanged. Each row is expected to contain position, points, wins, draws, losses; trailing empty CSV fields can be ignored.

The current inputs contain eight tables from five season labels, with 8 to 12 teams:

| File | Teams | Games per team from W+D+L | Observation |
| --- | ---: | --- | --- |
| 202122_SerieC.csv | 8 | 7 | Consistent with a single round robin; confirm format/completion |
| 202223_SerieC.csv | 11 | 20 | Arithmetic checks pass |
| 202324_SerieC.csv | 11 | 20 | Position 4 has 32 points but 13 wins and 3 draws imply 42 |
| 202425_SerieC_A.csv | 10 | 18 | Arithmetic checks pass |
| 202425_SerieC_B.csv | 10 | 18 | Corrected five-column data; arithmetic checks pass; included in calibration |
| 202425_SerieC_C.csv | 10 | 18 | Arithmetic checks pass |
| 202526_SerieD_A.csv | 12 | 20 to 22 | Positions 5 and 7 have 21 games, position 11 has 20; others have 22 |
| 202526_SerieD_B.csv | 11 | 20 | Arithmetic checks pass |

Validation should check consecutive unique positions, nonnegative integer results, points = 3*wins + draws (unless documented adjustments apply), total wins = total losses, even total draws, and match counts against the confirmed format. Matching aggregate totals alone does not prove the underlying fixtures are valid.

For descriptive comparisons, use points per game and a 20-game equivalent (`20 * points / games`). Compare table shapes using relative rank `(position - 1) / (team_count - 1)`, with interpolation if needed. These are comparison tools, not a substitute for simulating the target format: shorter seasons have more sampling variability, and multiplying points does not preserve that uncertainty. Unequal schedules also affect opponent difficulty.

Estimate match draw probability as `sum(draws) / sum(wins + draws + losses)` across team rows. Both numerator and denominator count each match twice, so the factors cancel. The five eligible tables from 2022/23, 2024/25 A, B and C, and 2025/26 B contain 44 drawn matches out of 490 (8.98%). Corrected 2024/25 group B contributes 7 draws in 90 matches (7.78%). This pooled rate is used at full historical influence; the uncalibrated default remains 25%. Serie D B alone has 6 draws in 110 matches (5.45%).

With these inputs, the fitted strength spread remains 1.80. At 50% historical influence the effective draw rate is 16.99% and strength spread is 0.90; at 100% they are 8.98% and 1.80. The 10,000-season forecast with seed 42 still has a champion median of 53 points at full calibration. Three tables remain excluded for the reasons listed above. The loader discovers corrected contents automatically, and the existing web manifest already includes group B, so no calibration-code or manifest change is needed. Rerun the browser simulation to fetch the corrected file and recompute its cached fit.

The optional calibration model now fits both draw frequency and variation in team strength; the broader validation steps below remain future work. Assign anonymous teams latent strengths drawn from a common distribution, and make win probabilities depend on strength differences. Fit the spread of strengths by comparing simulated and historical table dispersion, top/bottom points, and rank profiles. Simulate each historical competition using its own team count and confirmed number of legs during fitting, then forecast the target with 11 teams and two legs. Do not treat final ranks as known preseason strength rankings or all observed points variation as strength variation.

Retain season, division and group as metadata. Treat earlier lowest-division Serie C as potentially relevant evidence, with a sensitivity comparison against Serie D-only data. Any recency or division weights must be explicit; no arbitrary weights have been applied. Multiple groups in the same year share context, so validation and resampling should keep each season's groups together. Leave one season out when checking predictive performance.

There are only five season labels. Running 10,000 simulations reduces Monte Carlo noise but does not create additional historical evidence. Ultimately sample plausible fitted parameters as well as match results to incorporate calibration uncertainty into prediction ranges. Standings alone cannot identify home advantage, score distributions, or individual future team strengths without additional data.
