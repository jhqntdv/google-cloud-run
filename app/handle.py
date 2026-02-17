import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import io

from helper import run_cca

app = Flask(__name__)
app.json.sort_keys = False
CORS(app)

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_DF_COLUMNS = 15
MAX_DF_ROWS = 50
NUM_OF_SIMULATIONS = 2 * 10**4
SEED = 42


def _to_jsonable(value):
    if isinstance(value, dict):
        return {key: _to_jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.tolist()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _parse_inputs(form):
    input_method = form.get('input_method')
    stock_price_str = form.get('stock_price')
    total_equity_value_str = form.get('total_equity_value')
    stock_volatility_str = form.get('stock_volatility')
    time_to_exit_str = form.get('time_to_exit')
    risk_free_rate_str = form.get('risk_free_rate')

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
        return None, "Invalid numeric input for one or more parameters. Please ensure all financial parameters are valid numbers."

    return {
        "input_method": input_method,
        "stock_price": stock_price,
        "tev0_target": tev0_target,
        "stock_volatility": stock_volatility,
        "time_to_exit": time_to_exit,
        "risk_free_rate": risk_free_rate,
    }, None


def _run_cca_from_upload(form, file_storage):
    inputs, error = _parse_inputs(form)
    if error:
        return None, error, 400

    if not file_storage:
        return None, "No file part in the request", 400

    if file_storage.filename == '':
        return None, "No file selected", 400

    try:
        file_content = file_storage.read()
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            return None, f"File size exceeds the limit of {MAX_FILE_SIZE_MB} MB.", 400

        filename = file_storage.filename.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content))
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            return None, "Unsupported file type", 400

        if df.empty or df.shape[1] == 0:
            return None, "The uploaded file does not contain valid 2D tabular data.", 400

        if df.shape[1] > MAX_DF_COLUMNS:
            return None, f"The uploaded file exceeds the maximum allowed columns of {MAX_DF_COLUMNS}.", 400
        if df.shape[0] > MAX_DF_ROWS:
            return None, f"The uploaded file exceeds the maximum allowed rows of {MAX_DF_ROWS}.", 400

        df_display = df.copy().round(2)
        df_display = df_display.loc[:, ['class', 'shares', 'strike', 'Note']]  # manual
        class_names = df.loc[:, 'class']

        metric = df.loc[:, 'shares':'is_cliff'].values  # manual
        nsim = NUM_OF_SIMULATIONS if inputs["time_to_exit"] > 0.01 else 1
        seed = SEED

        result = run_cca(
            metric,
            inputs["stock_price"],
            inputs["stock_volatility"],
            inputs["tev0_target"],
            inputs["risk_free_rate"],
            inputs["time_to_exit"],
            nsim,
            seed,
        )

        payload = {
            "status": "success",
            "inputs": inputs,
            "cap_table": _to_jsonable(df_display),
            "result": _to_jsonable(result),
        }
        return payload, None, 200
    except Exception as e:
        return None, f"Error processing file: {str(e)}", 500


def _api_spec():
    return {
        "endpoint": "/api",
        "methods": ["GET", "POST"],
        "content_type": "multipart/form-data",
        "file_field": "file",
        "inputs": [
            {
                "id": "input_method",
                "type": "string",
                "required": True,
                "allowed": ["stock_price", "equity_value"],
                "description": "Selects whether to use stock price or total equity value."
            },
            {
                "id": "stock_price",
                "type": "number",
                "required_if": {"input_method": "stock_price"},
                "description": "Stock price in dollars."
            },
            {
                "id": "total_equity_value",
                "type": "number",
                "required_if": {"input_method": "equity_value"},
                "description": "Total equity value in thousands (e.g., 1200 for $1.2M)."
            },
            {
                "id": "stock_volatility",
                "type": "number",
                "required": True,
                "description": "Equity volatility as a decimal (e.g., 0.45)."
            },
            {
                "id": "time_to_exit",
                "type": "number",
                "required": True,
                "description": "Time to exit in years (e.g., 5.0)."
            },
            {
                "id": "risk_free_rate",
                "type": "number",
                "required": True,
                "description": "Risk-free rate as a decimal (e.g., 0.05)."
            }
        ],
        "response": {
            "status": "success or failed",
            "inputs": "echo of parsed inputs",
            "cap_table": "array of rows with class, shares, strike, Note",
            "result": "raw run_cca result (jsonified)"
        }
    }


@app.route("/api", methods=["GET", "POST"])
def handle_api():
    if request.method == "GET":
        return jsonify(_api_spec()), 200

    has_form = bool(request.form)
    has_files = bool(request.files)
    if not has_form and not has_files:
        return jsonify(_api_spec()), 200

    payload, error, status = _run_cca_from_upload(request.form, request.files.get('file'))
    if error:
        return jsonify({"error": error}), status
    return jsonify(payload), 200

@app.route("/", methods=["GET"])
def handle_root():
    return f"API running with {NUM_OF_SIMULATIONS} Nsim", 200

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port) # flask --app app/handle.py run