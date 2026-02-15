# OPM (CCA) deployed on Google Cloud Run

An online cap table analysis calculator built on Google Cloud Run with Docker containerization. Simply upload your cap table to understand the value of each security.

### Local Development with Docker

1. **Build the Docker image:**
   ```bash
   docker build -t my-cloud-run-app .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8080:8080 -e PORT=8080 my-cloud-run-app
   docker run -p 8080:8080 my-cloud-run-app
   ```

3. **Access the application:**
   Open your browser and navigate to: `http://localhost:8080`

### Steps for Deployment to Google Cloud Run

1. **Create GitHub Repository**
   - Push your code to a GitHub repository
   - Ensure your `Dockerfile` is in the root directory

2. **Connect to Google Cloud Run**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to **Cloud Run** service
   - Click **Create Service**
   - Choose **"Continuously deploy new revisions from a source repository"**
   - Connect your GitHub repository
   - Select **Docker** build option (not Cloud Buildpacks)

3. **Configure Build Settings**
   - Set build type: **Dockerfile**
   - Dockerfile location: `/Dockerfile`
   - Set service name and region

4. **Deploy & Access**
   - Push changes to your main branch
   - Google Cloud automatically triggers deployment
   - Access your live application at:
   ```
   https://<your-service-name>-<hash>-<region>.run.app
   ```

### OPM (CCA) Implmentation

The analysis uses a standard Monte Carlo approach to value each security as a call-option-like security, which is widely adopted by Big 4 accounting firms despite their varying names (OPM, CCA, Waterfall Analysis, etc.). The implementation is capable of valuing complex instruments while considering the potential dilution from options.

The analysis uses standard monte carlo approach to value each security as call-option-like security which are widely adopted by Big 4 despite their variation names (OPM, CCA, Waterfall Analysis..etc). The implementation is capable of valuing complex instruments as well as considering the potential dilution from the options.

## User guide
To use this app, you'll need:
- **Market inputs**:
  - Stock price/equity value based on market observation for public companies or latest transaction/409A valuation for private companies
  - Equity volatility (typically 30-60% depending on sector)
  - Risk-free rate (the treasury rate as of your valuation date)
  - Expected time to exit

- **Cap table** (Excel or CSV format with security details)
  - To outline how the terms of each security can be expressed quantiatively, A example of cap table is showned that includes most popular instruments issued as stock-based compensations (Warrants, Options, RSU, PSU, Incentive Units..etc)

   | class | shares | is_time | strike | v_cnt | vstart | vmid | vend | vstart_perc | vmid_perc | vend_perc | groups | is_cliff | Note |
   |---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
   | Common (Type of Time-Based) | 10,000 | 1 | 0 | 0 | -1 | -1 | -1 | -100.00% | -100.00% | -100.00% | 1 | 0 | Common (Type of Time-Based) - Time-Based Vesting |
   | Security A | 100 | 1 | 10 | 0 | -1 | -1 | -1 | -100.00% | -100.00% | -100.00% | 2 | 0 | Security A - Time-Based Vesting |
   | Security B | 100 | 0 | 10 | 2 | 20 | -1 | 30 | 50.00% | -100.00% | 100.00% | 2 | 1 | Security B - Performance-Based Vesting (Cliff), 2 Tranche(s) Vesting @ 20x / 30x, with vesting schedule of 50% / 100% |
   | Security C | 100 | 0 | 10 | 2 | 20 | -1 | 30 | 50.00% | -100.00% | 100.00% | 2 | 0 | Security C - Performance-Based Vesting (Linear), 2 Tranche(s) Vesting @ 20x / 30x, with vesting schedule of 50% / 100% |
   | Security D | 100 | 1 | 25 | 0 | -1 | -1 | -1 | -100.00% | -100.00% | -100.00% | 3 | 0 | Security D - Time-Based Vesting |
   | Security E | 100 | 0 | 25 | 3 | 30 | 40 | 50 | 50.00% | 75.00% | 100.00% | 3 | 1 | Security E - Performance-Based Vesting (Cliff), 3 Tranche(s) Vesting @ 30x / 40x / 50x, with vesting schedule of 50% / 75% / 100% |
   | Security F | 100 | 0 | 25 | 3 | 30 | 40 | 50 | 50.00% | 75.00% | 100.00% | 3 | 0 | Security F - Performance-Based Vesting (Linear), 3 Tranche(s) Vesting @ 30x / 40x / 50x, with vesting schedule of 50% / 75% / 100% |
   | Security G | 100 | 0 | 25 | 1 | 30 | -1 | -1 | 100.00% | -100.00% | -100.00% | 3 | 1 | Security G - Performance-Based Vesting (Cliff), 1 Tranche(s) Vesting @ 30x, with vesting schedule of 100% |
   | Security H | 100 | 0 | 25 | 1 | 40 | -1 | -1 | 100.00% | -100.00% | -100.00% | 3 | 1 | Security H - Performance-Based Vesting (Cliff), 1 Tranche(s) Vesting @ 40x, with vesting schedule of 100% |
   | Security I | 100 | 0 | 0 | 1 | 30 | -1 | -1 | 100.00% | -100.00% | -100.00% | 4 | 1 | Security I - Performance-Based Vesting (Cliff), 1 Tranche(s) Vesting @ 30x, with vesting schedule of 100% |
   | Security J | 100 | 0 | 0 | 1 | 40 | -1 | -1 | 100.00% | -100.00% | -100.00% | 4 | 1 | Security J - Performance-Based Vesting (Cliff), 1 Tranche(s) Vesting @ 40x, with vesting schedule of 100% |
   | Security K | 100 | 0 | 0 | 2 | 30 | -1 | 40 | 0.00% | -100.00% | 100.00% | 4 | 1 | Security K - Performance-Based Vesting (Cliff), 2 Tranche(s) Vesting @ 30x / 40x, with vesting schedule of 0% / 100% |
   | Security L | 100 | 0 | 0 | 2 | 30 | -1 | 40 | 0.00% | -100.00% | 100.00% | 4 | 0 | Security L - Performance-Based Vesting (Linear), 2 Tranche(s) Vesting @ 30x / 40x, with vesting schedule of 0% / 100% |
   | Security M | 100 | 0 | 0 | 3 | 10 | 25 | 40 | 33.33% | 66.67% | 100.00% | 5 | 1 | Security M - Performance-Based Vesting (Cliff), 3 Tranche(s) Vesting @ 10x / 25x / 40x, with vesting schedule of 33% / 67% / 100% |
   | Security N | 100 | 0 | 0 | 3 | 10 | 25 | 40 | 33.33% | 66.67% | 100.00% | 5 | 0 | Security N - Performance-Based Vesting (Linear), 3 Tranche(s) Vesting @ 10x / 25x / 40x, with vesting schedule of 33% / 67% / 100% |

**Column Definitions:**
  - **class** - The name of the security class or instrument type
  - **shares** - Number of shares or units outstanding for this security
  - **strike** - Exercise price, strike price or distribution threshold with respect to the underlying security (for options/warrants)
  - **vstart** - Performance vesting threshold start value quoted in actual per share of underlying (equity multiple e.g., ROI, MOIC, MoM)
  - **vmid** - Performance vesting threshold mid value in actual per share of underlying (equity multiple)
  - **vend** - Performance vesting threshold end value in actual per share of underlying (equity multiple)
  - **vstart_perc** - Vesting schedule at vstart
  - **vmid_perc** - Vesting schedule at vmid
  - **vend_perc** - Vesting schedule at vend
  - **is_time** - Flag indicating if this is time-based vesting (1) or performance-based (0)
  - **v_cnt** - Vesting condition count (0=no vesting condition, 1=single vesting threshold, 2=range of vesting thresholds)
  - **groups** - Security group identifier typically by similar moneyness range, issue date, strike price, etc.
  - **is_cliff** - Flag indicating cliff vesting (1) vs. linear vesting (0).

Download the [sample_cap_table.xlsx](https://github.com/jhqntdv/google-cloud-run/raw/main/data/sample_cap_table.xlsx) or [sample_cap_table.csv](https://github.com/jhqntdv/google-cloud-run/blob/main/data/sample_cap_table.csv) to get started.

##