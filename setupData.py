import pandas as pd
import numpy as np


def build_data_model(payload):
    task_df = pd.DataFrame(payload["TaskListOperations"])
    mo_df = pd.DataFrame(payload["MaintenanceOrderOperations"])

    # Ensure correct dtypes
    task_df["OperationKey"] = task_df["OperationKey"].astype(int)
    mo_df["OperationKey"] = mo_df["OperationKey"].astype(int)

    return task_df, mo_df


def group_by_order(mo_df):
    return {
        order_id: df
        for order_id, df in mo_df.groupby("MaintenanceOrder")
    }


def analyze_single_order(order_df, task_df):
    result = {
        "new_operations": [],
        "missing_operations": [],
        "quantity_deltas": []
    }

    task_ops = set(task_df["OperationKey"])
    order_ops = set(order_df["OperationKey"])

    # New operations (OperationKey = 0)
    new_ops = order_df[order_df["OperationKey"] == 0]
    if not new_ops.empty:
        result["new_operations"] = new_ops.to_dict("records")

    # Missing operations (exist in master but not executed)
    missing_ops = task_ops - order_ops
    result["missing_operations"] = list(missing_ops)

    # Quantity deviations
    merged = order_df.merge(
        task_df,
        on=["OperationKey", "unit"],
        how="inner",
        suffixes=("_actual", "_planned")
    )

    merged["delta"] = merged["quantity_actual"] - merged["quantity_planned"]

    result["quantity_deltas"] = merged[[
        "OperationKey", "quantity_planned", "quantity_actual", "delta"
    ]].to_dict("records")

    return result


def aggregate_learning(order_results):
    agg = {
        "qty_stats": {},
        "new_ops_count": {},
        "missing_ops_count": {}
    }

    for order_id, res in order_results.items():
        for q in res["quantity_deltas"]:
            op = q["OperationKey"]
            agg["qty_stats"].setdefault(op, []).append(q["delta"])

        for op in res["missing_operations"]:
            agg["missing_ops_count"][op] = agg["missing_ops_count"].get(op, 0) + 1

        for op in res["new_operations"]:
            key = "NEW_OP"
            agg["new_ops_count"][key] = agg["new_ops_count"].get(key, 0) + 1

    return agg


def propose_master_changes(task_df, agg, total_orders):
    proposals = []

    for op_key, deltas in agg["qty_stats"].items():
        mean_delta = np.mean(deltas)

        if abs(mean_delta) > 1:  # business threshold
            proposals.append({
                "OperationKey": op_key,
                "type": "UPDATE_QUANTITY",
                "current_quantity": float(
                    task_df.loc[task_df.OperationKey == op_key, "quantity"].iloc[0]
                ),
                "suggested_quantity": float(
                    task_df.loc[task_df.OperationKey == op_key, "quantity"].iloc[0]
                    + mean_delta
                ),
                "confidence": "HIGH"
            })

    for op_key, count in agg["missing_ops_count"].items():
        if count / total_orders > 0.6:
            proposals.append({
                "OperationKey": op_key,
                "type": "DELETE_OPERATION",
                "confidence": "MEDIUM"
            })

    if agg["new_ops_count"].get("NEW_OP", 0) / total_orders > 0.4:
        proposals.append({
            "OperationKey": 0,
            "type": "ADD_NEW_OPERATION",
            "confidence": "LOW"
        })

    return proposals
