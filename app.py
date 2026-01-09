from flask import Flask, request, jsonify
from utils import *
import pandas as pd

app = Flask(__name__)


@app.route("/analyze", methods=["POST"])
def analyze():
    payload = request.get_json()
    df = pd.DataFrame(payload["orders"])

    df = run_numeric_analysis(df)
    df = run_frequency_analysis(df)
    df = run_text_analysis(df)

    recommendations = generate_recommendations(df)

    return jsonify({
        "task_list_id": payload["task_list_id"],
        "recommendations": recommendations
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)