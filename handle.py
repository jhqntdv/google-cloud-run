import os
from flask import Flask, request
import pandas as pd
import io

from helper import run_cca

app = Flask(__name__)

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_DF_COLUMNS = 10
MAX_DF_ROWS = 50

@app.route("/", methods=["GET", "POST"])
def handle_upload():
    html_form = '''
    <!doctype html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CCA</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container py-5">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card shadow">
                        <div class="card-body p-4">
                            <h1 class="text-center mb-4">CCA</h1>
                            <form method="POST" enctype="multipart/form-data">
                                <div class="mb-4 p-3 border rounded bg-light text-center">
                                    <label class="form-label fw-bold">Upload Spec</label>
                                    <input type="file" name="file" class="form-control" accept=".csv,.xlsx" required>
                                </div>
                                
                                <!-- Input Method Selection -->
                                <div class="mb-3 p-3 border rounded bg-light">
                                    <label class="form-label fw-bold">Choose Input Method</label>
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="input_method" id="stock_price_method" value="stock_price" checked>
                                        <label class="form-check-label" for="stock_price_method">
                                            Stock Price ($)
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="radio" name="input_method" id="equity_value_method" value="equity_value">
                                        <label class="form-check-label" for="equity_value_method">
                                            Total Equity Value (in thousands)
                                        </label>
                                    </div>
                                </div>

                                <div class="row g-3 mb-3">
                                    <div class="col-6">
                                        <label class="form-label">Stock Price ($)</label>
                                        <input type="number" name="stock_price" id="stock_price_input" class="form-control" value="100.0" step="0.01">
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label">Total Equity Value (thousands)</label>
                                        <input type="number" name="total_equity_value" id="equity_value_input" class="form-control" value="1200.0" step="0.1" disabled>
                                        <div class="form-text">e.g., 1200 for $1.2M</div>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label">Equity Volatility</label>
                                        <input type="number" name="stock_volatility" class="form-control" value="0.45" step="0.01" required>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label">Time to Exit (Years)</label>
                                        <input type="number" name="time_to_exit" id="time_to_exit_input" class="form-control" value="5.0" step="0.01" min="0.01" max="10" required>
                                        <div class="form-text" id="time_range_hint">Range: 0.01 - 10 years</div>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label">Risk Free Rate</label>
                                        <input type="number" name="risk_free_rate" class="form-control" value="0.05" step="0.0001" required>
                                    </div>
                                </div>
                                
                                <button type="submit" class="btn btn-primary w-100 py-2">Run Analysis</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            // Handle input method switching
            document.addEventListener('DOMContentLoaded', function() {
                const stockPriceRadio = document.getElementById('stock_price_method');
                const equityValueRadio = document.getElementById('equity_value_method');
                const stockPriceInput = document.getElementById('stock_price_input');
                const equityValueInput = document.getElementById('equity_value_input');
                const timeToExitInput = document.getElementById('time_to_exit_input');
                const timeRangeHint = document.getElementById('time_range_hint');
                
                function updateInputs() {
                    if (stockPriceRadio.checked) {
                        stockPriceInput.disabled = false;
                        stockPriceInput.required = true;
                        equityValueInput.disabled = true;
                        equityValueInput.required = false;
                        equityValueInput.value = '0';
                        
                        // Time range for stock price method: 0 < t <= 10
                        timeToExitInput.min = '0.01';
                        timeToExitInput.max = '10';
                        timeRangeHint.textContent = 'Range: 0.01 - 10 years';
                    } else {
                        stockPriceInput.disabled = true;
                        stockPriceInput.required = false;
                        stockPriceInput.value = '0';
                        equityValueInput.disabled = false;
                        equityValueInput.required = true;
                        
                        // Time range for equity value method: 0 < t <= 10
                        timeToExitInput.min = '0.01';
                        timeToExitInput.max = '10';
                        timeRangeHint.textContent = 'Range: 0.01 - 10 years';
                    }
                }
                
                stockPriceRadio.addEventListener('change', updateInputs);
                equityValueRadio.addEventListener('change', updateInputs);
                updateInputs(); // Initialize
            });
        </script>
    </body>
    </html>
    '''

    if request.method == 'POST':
        input_method = request.form.get('input_method')
        stock_price_str = request.form.get('stock_price')
        total_equity_value_str = request.form.get('total_equity_value')
        stock_volatility_str = request.form.get('stock_volatility')
        time_to_exit_str = request.form.get('time_to_exit')
        risk_free_rate_str = request.form.get('risk_free_rate')

        try:
            stock_volatility = float(stock_volatility_str)
            time_to_exit = float(time_to_exit_str)
            risk_free_rate = float(risk_free_rate_str)

            if input_method == 'stock_price':
                stock_price = float(stock_price_str)
                tev0_target = 0.0
            else:
                total_equity_value = float(total_equity_value_str)
                tev0_target = total_equity_value * 1000.0
                stock_price = 0.0
                
        except (ValueError, TypeError):
            return "Invalid numeric input for one or more parameters. Please ensure all financial parameters are valid numbers.", 400

        if 'file' not in request.files:
            return "No file part in the request", 400
        
        file = request.files['file']
        if file.filename == '':
            return "No file selected", 400

        try:
            # Sanity Check 1: File Size
            file_content = file.read() 
            if len(file_content) > MAX_FILE_SIZE_BYTES:
                return f"File size exceeds the limit of {MAX_FILE_SIZE_MB} MB.", 400

            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_content))
            elif file.filename.endswith('.xlsx'):
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return "Unsupported file type", 400
            
            if df.empty or df.shape[1] == 0:
                return "The uploaded file does not contain valid 2D tabular data.", 400

            if df.shape[1] > MAX_DF_COLUMNS:
                return f"The uploaded file exceeds the maximum allowed columns of {MAX_DF_COLUMNS}.", 400
            if df.shape[0] > MAX_DF_ROWS:
                return f"The uploaded file exceeds the maximum allowed rows of {MAX_DF_ROWS}.", 400
            
            df_display = df.copy().round(2)
            class_names = df.loc[:, 'class']
            
            # df has index and headers, read df values as metric
            metric = df.loc[:, 'shares':].values
            nsim = 2*10**4 if time_to_exit > 0.01 else 1
            seed = 42

            result = run_cca(metric, stock_price, stock_volatility, tev0_target, risk_free_rate, time_to_exit, nsim, seed)

            table_html = df_display.to_html(
                classes='table table-striped table-bordered table-hover',
                table_id='results-table',
                border=0,
                escape=False,
                index=False
            )
            
            if result['status']:  # Check if the calculation was successful
                dilution_pct = result['dilution'] * 100
                equity_vol_pct = result['voleq'] * 100
                common_vol_pct = result['volcm'] * 100
                
                # Create table rows for strikes, time/perf, and fair values
                table_rows = ""
                for i in range(len(result['fair_value_per_share'])):
                    class_name = class_names.iloc[i] if i < len(class_names) else f'Class {i+1}'
                    strike_val = result['strikes'][i] if i < len(result['strikes']) else 'N/A'
                    time_perf = 'Time-based' if (i < len(result['is_time']) and result['is_time'][i] == 1) else 'Perf-based'
                    fair_val = result['fair_value_per_share'][i]
                    
                    # Format strike_val outside the f-string
                    formatted_strike = f"{strike_val:.2f}" if isinstance(strike_val, (int, float)) else strike_val
                    
                    table_rows += f'''
                    <tr>
                        <td class="text-center">{class_name}</td>
                        <td class="text-center">${formatted_strike}</td>
                        <td class="text-center">{time_perf}</td>
                        <td class="text-center">${fair_val:.2f}</td>
                    </tr>
                    '''

                result_summary = f'''
                <div class="mt-4">
                    <h5 class="mb-3">Analysis Summary</h5>
                    <p class="mb-4" style="text-align: justify; line-height: 1.6;">
                        Based on the analysis, there are <strong>{result['num_of_class']} classes</strong> of equity instruments. 
                        The total equity value is <strong>${result['tev0']/1000:,.0f} thousand(s)</strong> with an option dilution impact of <strong>{dilution_pct:.2f}%</strong>. 
                        {f"Furthermore, we estimated the equity volatility to be <strong>{equity_vol_pct:.2f}%</strong> and the common stock volatility to be <strong>{common_vol_pct:.2f}%</strong>. " if time_to_exit > 0.01 else "Based on the immediate exit scenario, we performed a liquidation analysis instead. "}
                        The fair value per share of each class are detailed in the table below
                    </p>
                    
                    <h6 class="mb-3">Fair Value Summary by Class</h6>
                    <div class="table-responsive" style="max-height: 400px; overflow-x: auto;">
                        <table class="table table-striped table-bordered table-hover table-sm">
                            <thead class="table-dark sticky-top">
                                <tr>
                                    <th class="text-center" style="min-width: 100px;">Class</th>
                                    <th class="text-center" style="min-width: 120px;">Strike Price ($)</th>
                                    <th class="text-center" style="min-width: 140px;">Vesting Type</th>
                                    <th class="text-center" style="min-width: 140px;">Fair Value per Share ($)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                        </table>
                    </div>
                    <p class="mb-2" style="text-align: justify; line-height: 1.6;">
                        <em>Note: The analysis has verified the discount factor (Dt) of <strong>{result['check'][0]:.2%}</strong> and convergence after <strong>{result['iterations']} iterations</strong></em>
                    </p>
                    <p class="mb-4" style="text-align: justify; line-height: 1.6;">
                        <em>Note: For cliff vesting, the fair value calculation assumes a three-tier vesting schedule: one-third vests at the start date, another third at the midpoint between the start and end dates, and the final third at the end date.</em>
                    </p>
                </div>
                '''
            else:
                result_summary = f'''
                <div class="mt-4">
                    <div class="alert alert-danger">
                        <h6 class="alert-heading">Calculation Error</h6>
                        <strong>{result['message']}</strong>
                    </div>
                </div>
                '''

            response_message = f'''
            <!doctype html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Analysis Results</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body class="bg-light">
                <div class="container py-4">
                    <div class="card shadow">
                        <div class="card-body">
                            <h2 class="text-center mb-4">Analysis Results</h2>
                            
                            <div class="mb-4">
                                <h5 class="mb-3">Input Overview</h5>
                                <p class="mb-4" style="text-align: justify; line-height: 1.6;">
                                    The analysis was conducted using the following parameters: {f"<strong>Stock Price of ${stock_price:.2f}</strong>" if input_method == 'stock_price' else f"<strong>Total Equity Value of ${tev0_target/1000:,.0f} thousand(s)</strong>"},
                                    <strong>Volatility of {stock_volatility:.1%}</strong>, 
                                    <strong>Time to Exit of {time_to_exit:.1f} years</strong>, and 
                                    <strong>Risk-Free Rate of {risk_free_rate:.2%}</strong>.
                                </p>
                            </div>
                            
                            <h5 class="mb-3">Cap Table</h5>
                            <div class="table-responsive" style="max-height: 400px; overflow-x: auto; max-width: 100%;">
                                {table_html}
                            </div>
                            
                            {result_summary}
                            
                            <a href="/" class="btn btn-primary">Run Another Analysis</a>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            '''
            return response_message
        
        except Exception as e:
            return f"Error processing file: {str(e)}", 500
    
    # If GET request, just show the form
    return html_form

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)