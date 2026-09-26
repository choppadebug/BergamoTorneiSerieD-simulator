# Bergamo Tornei Serie D

A dependency-free Python Monte Carlo simulator for end-of-season points by finishing position. Requires Python 3.10 or later.

## Web app: run locally

From the repository root:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Open **http://127.0.0.1:8000** in a modern browser. Stop the server with `Ctrl+C`. Use HTTP instead of double-clicking `index.html`: browser workers and source loading require a served site.

No npm install, build step, or application server is required. The site runs the actual `league_simulator.py` and `historical_calibration.py` in a [Pyodide](https://pyodide.org/en/stable/usage/webworker.html) module worker, keeping the page responsive. [Chart.js](https://www.chartjs.org/docs/latest/charts/line.html) renders the charts. Dependencies are pinned to Pyodide 314.0.7 and Chart.js 4.5.1 on jsDelivr. The first run downloads the Python runtime and needs internet access; subsequent runs reuse it. Fonts load from Google Fonts with local fallbacks. This is not an offline app.

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
2. In **Settings → Pages → Build and deployment**, select **Deploy from a branch**.
3. Select your publishing branch (usually `main`) and **/(root)**, then save.
4. Once deployment completes, visit the URL shown in Pages settings, usually `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/`.

All local asset paths are relative, so a repository subpath works. No API keys, backend service, or Actions workflow is needed. The repository has not been published automatically.

If Git is already configured for the repository, review changes and publish with:

```powershell
git status
git add index.html styles.css app.js worker.js web_runner.py league_simulator.py historical_calibration.py input/ .nojekyll update_manifest.py test_web_runner.py README.md
git commit -m "Add browser season simulator for GitHub Pages"
git push origin main
```

Replace `main` with your publishing branch. This workspace did not have a Git repository when the web app was added. For a new repository, first create an empty repository on GitHub, then run the following before the add/commit commands above:

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
```

Node is optional and used here only for JavaScript syntax checks. The Python tests check that web results match native results and that each rank's histogram accounts for every simulated season.

For a browser smoke test, run the local server, simulate the default 10,000 seasons (champion median 37), enable full historical influence with all bundled files (current champion median 53), inspect exclusions, change the selected position, and download the CSV. Change settings and verify the stale-result notice. Start a longer run, cancel, then rerun. Check narrow/mobile layout and keyboard control access. To exercise repository-subpath hosting locally, serve the parent directory and navigate to this repository's folder URL.

If dependencies fail to load, check access to jsDelivr and reload. Browser errors appear next to the run button. A calibration run with no eligible selected tables reports an error rather than silently falling back to the baseline.

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

1. **Team strength:** ratings or past results to give each fixture different win/draw/loss probabilities. This is the most useful next step toward representing a specific league.
2. **Actual draw frequency:** estimate from previous seasons instead of using the initial 25% assumption.
3. **Current table and remaining fixtures:** preserve completed results and simulate only the rest of the season.
4. **Home advantage:** if venue or home status matters in this league.
5. **Goals and official tie-break rules:** simulate scorelines and resolve equal points according to league rules.
6. **Form and availability:** injuries, absences, roster changes, or changing strength over the season.

Once named teams and their strengths are included, we can report each team's finish probabilities and estimate the probability of a top-k finish given a particular points total.

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

Initial inspection found eight tables from five season labels, with 8 to 12 teams:

| File | Teams | Games per team from W+D+L | Observation |
| --- | ---: | --- | --- |
| 202122_SerieC.csv | 8 | 7 | Consistent with a single round robin; confirm format/completion |
| 202223_SerieC.csv | 11 | 20 | Arithmetic checks pass |
| 202324_SerieC.csv | 11 | 20 | Position 4 has 32 points but 13 wins and 3 draws imply 42 |
| 202425_SerieC_A.csv | 10 | 18 | Arithmetic checks pass |
| 202425_SerieC_B.csv | 10 | Unknown | Four populated fields per row; column meaning needs confirmation |
| 202425_SerieC_C.csv | 10 | 18 | Arithmetic checks pass |
| 202526_SerieD_A.csv | 12 | 20 to 22 | Positions 5 and 7 have 21 games, position 11 has 20; others have 22 |
| 202526_SerieD_B.csv | 11 | 20 | Arithmetic checks pass |

Validation should check consecutive unique positions, nonnegative integer results, points = 3*wins + draws (unless documented adjustments apply), total wins = total losses, even total draws, and match counts against the confirmed format. Matching aggregate totals alone does not prove the underlying fixtures are valid.

For descriptive comparisons, use points per game and a 20-game equivalent (`20 * points / games`). Compare table shapes using relative rank `(position - 1) / (team_count - 1)`, with interpolation if needed. These are comparison tools, not a substitute for simulating the target format: shorter seasons have more sampling variability, and multiplying points does not preserve that uncertainty. Unequal schedules also affect opponent difficulty.

Estimate match draw probability as `sum(draws) / sum(wins + draws + losses)` across team rows. Both numerator and denominator count each match twice, so the factors cancel. Use documented complete, comparable tables for an initial estimate. The four arithmetically consistent tables from 2022/23, 2024/25 A and C, and 2025/26 B contain 37 drawn matches out of 400 (9.25%). This is a provisional pooled rate, not yet the simulator default. Serie D B alone has 6 draws in 110 matches (5.45%).

The optional calibration model now fits both draw frequency and variation in team strength; the broader validation steps below remain future work. Assign anonymous teams latent strengths drawn from a common distribution, and make win probabilities depend on strength differences. Fit the spread of strengths by comparing simulated and historical table dispersion, top/bottom points, and rank profiles. Simulate each historical competition using its own team count and confirmed number of legs during fitting, then forecast the target with 11 teams and two legs. Do not treat final ranks as known preseason strength rankings or all observed points variation as strength variation.

Retain season, division and group as metadata. Treat earlier lowest-division Serie C as potentially relevant evidence, with a sensitivity comparison against Serie D-only data. Any recency or division weights must be explicit; no arbitrary weights have been applied. Multiple groups in the same year share context, so validation and resampling should keep each season's groups together. Leave one season out when checking predictive performance.

There are only five season labels. Running 10,000 simulations reduces Monte Carlo noise but does not create additional historical evidence. Ultimately sample plausible fitted parameters as well as match results to incorporate calibration uncertainty into prediction ranges. Standings alone cannot identify home advantage, score distributions, or individual future team strengths without additional data.
