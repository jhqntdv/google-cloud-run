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

    | class | shares | strike | vstart | vend | is_time | v_cnt | groups | is_cliff |
    |-------|--------|--------|--------|------|---------|-------|---------|----------|
    | Common | 10,000 | 0.00 | 0.00 | 0.00 | 1 | 0 | 1 | 0 |
    | B1-Time | 100 | 10.00 | 0.00 | 0.00 | 1 | 0 | 2 | 0 |
    | B1-Perf-Cliff | 100 | 10.00 | 20.00 | 30.00 | 0 | 2 | 2 | 1 |
    | B1-Perf-Linear | 100 | 10.00 | 20.00 | 30.00 | 0 | 2 | 2 | 0 |
    | B3-Time | 100 | 25.00 | 0.00 | 0.00 | 1 | 0 | 3 | 0 |
    | B3-Perf-Cliff-3x-5x | 100 | 25.00 | 30.00 | 50.00 | 0 | 2 | 3 | 1 |
    | B3-Perf-Linear-3x-5x | 100 | 25.00 | 30.00 | 50.00 | 0 | 2 | 3 | 0 |
    | B3-Perf-Vest-Upon-3x | 100 | 25.00 | 30.00 | 0.00 | 0 | 1 | 3 | 1 |
    | B3-Perf-Vest-Upon-4x | 100 | 25.00 | 40.00 | 0.00 | 0 | 1 | 3 | 1 |
    | PSU-Vest-Upon-3x | 100 | 0.00 | 30.00 | 0.00 | 0 | 1 | 4 | 1 |
    | PSU-Vest-Upon-4x | 100 | 0.00 | 40.00 | 0.00 | 0 | 1 | 4 | 1 |
    | PSU-Cliff-3x-4x | 100 | 0.00 | 30.00 | 40.00 | 0 | 2 | 4 | 1 |
    | PSU-Linear-3x-4x | 100 | 0.00 | 30.00 | 40.00 | 0 | 2 | 4 | 0 |
    | PSU-Linear-0x-4x | 100 | 0.00 | 0.00 | 40.00 | 1 | 0 | 4 | 0 |

**Column Definitions:**
  - **class** - The name of the security class or instrument type
  - **shares** - Number of shares or units outstanding for this security
  - **strike** - Exercise price, strike price or distribution threshold with respect to the underlying security (for options/warrants)
  - **vstart** - Performance vesting threshold start value quoted in actual per share of underlying (equity multiple e.g., ROI, MOIC, MoM)
  - **vend** - Performance vesting threshold end value in actual per share of underlying (equity multiple)
  - **is_time** - Flag indicating if this is time-based vesting (1) or performance-based (0)
  - **v_cnt** - Vesting condition count (0=no vesting condition, 1=single vesting threshold, 2=range of vesting thresholds)
  - **groups** - Security group identifier typically by similar moneyness range, issue date, strike price, etc.
  - **is_cliff** - Flag indicating cliff vesting (1) vs. linear vesting (0). By default the cliff vesting schedule uses 33%/33%/34% vesting schedule on vstart, vmid (midpoint of vstart and vend), vend respectively

Download the [sample_cap_table.xlsx](https://github.com/jhqntdv/google-cloud-run/raw/main/data/sample_cap_table.xlsx) or [sample_cap_table.csv](https://github.com/jhqntdv/google-cloud-run/blob/main/data/sample_cap_table.csv) to get started.

##