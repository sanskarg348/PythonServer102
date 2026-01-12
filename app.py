from flask import Flask, request, jsonify
from setupData import *
app = Flask(__name__)


@app.route("/analyze", methods=["POST"])
def analyze():
    payload = request.get_json()
    task_df, mo_df = build_data_model(payload)
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
    print(proposals)
    return jsonify({
        "order_level_analysis": order_results,
        "master_change_proposals": proposals
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)
