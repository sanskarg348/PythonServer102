from flask import Flask, request, jsonify
from dataCreation import *
import json
from setupData import *
import os

app = Flask(__name__)


@app.route("/analyze", methods=["POST"])
def analyze():
    payload = json.loads(request.data.decode("utf-8"))
    # print(payload)
    # return jsonify({"Good": [1,2,3,4]})
    task_df, mo_df = build_data_model(payload)

    if task_df is None or mo_df is None:
        print("No Data Case")
        return jsonify({"Message": "No Data sent to python server"})

    grouped_orders = group_by_order(mo_df)

    order_results = {
        order_id: analyze_single_order(df, task_df)
        for order_id, df in grouped_orders.items()
    }

    agg = aggregate_learning(order_results)

    proposals = propose_master_changes(
        task_df,
        agg,
        total_orders=len(grouped_orders)
    )

    print("RESULTS: ", proposals)

    return jsonify({
        "order_level_analysis": order_results,
        "master_change_proposals": proposals
    })


@app.route("/get_data", methods=["GET"])
def get_data():
    payloadGenerated = generate_large_payload(int(json.loads(request.data.decode("utf-8"))['num']))
    return payloadGenerated


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.environ.get('PORT', 3000))