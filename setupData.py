import pandas as pd

from utils import *
from constants import FIELDS_TO_COMPARE


# ------------------------------------------------------------------
# Build data model
# ------------------------------------------------------------------
def build_data_model(payload):
    task_df = pd.DataFrame(payload['results'][1]['value'])
    mo_df = pd.DataFrame(payload['results'][0]['d']['results'])

    task_df["TaskListOperationInternalId"] = task_df["TaskListOperationInternalId"].astype(int)
    mo_df["TaskListOperationInternalId"] = mo_df["TaskListOperationInternalId"].astype(int)

    task_df = task_df[
        ['WorkCenter', 'Plant', 'OpPlannedWorkQuantity',
         'OpWorkQuantityUnit', 'TaskListOperationInternalId','OperationText']
    ]

    mo_df = mo_df[
        ['MaintenanceOrder', 'MaintenanceOrderOperation',
         'WorkCenter', 'Plant',
         'MaintOrderOperationQuantity',
         'MaintOrdOperationQuantityUnit',
         'TaskListOperationInternalId',
         'OperationDescription']
    ]

    task_df.rename(columns={
        'OpPlannedWorkQuantity': 'Quantity',
        'OpWorkQuantityUnit': 'Unit',
        'OperationText': 'OperationDescription'
    }, inplace=True)

    mo_df.rename(columns={
        'MaintOrderOperationQuantity': 'Quantity',
        'MaintOrdOperationQuantityUnit': 'Unit'
    }, inplace=True)

    # Normalize to hours
    task_df["Quantity_H"] = task_df.apply(
        lambda r: normalize_to_hours(r["Quantity"], r["Unit"]),
        axis=1
    )

    mo_df["Quantity_H"] = mo_df.apply(
        lambda r: normalize_to_hours(r["Quantity"], r["Unit"]),
        axis=1
    )

    task_df["NormDescription"] = task_df["OperationDescription"].apply(normalize_description)
    mo_df["NormDescription"] = mo_df["OperationDescription"].apply(normalize_description)

    return task_df, mo_df


# ------------------------------------------------------------------
# Group by maintenance order
# ------------------------------------------------------------------
def group_by_order(mo_df):
    return {
        order_id: df
        for order_id, df in mo_df.groupby("MaintenanceOrder")
    }


# ------------------------------------------------------------------
# Analyze a single order
# ------------------------------------------------------------------
def analyze_single_order(order_df, task_df):
    result = {
        "new_operations": [],
        "missing_operations": [],
        "quantity_deltas": [],
        "field_deltas": []
    }

    task_ops = set(task_df["TaskListOperationInternalId"])
    order_ops = set(order_df["TaskListOperationInternalId"])

    # New operations (InternalId = 0)
    new_ops = order_df[order_df["TaskListOperationInternalId"] == 0]
    if not new_ops.empty:
        result["new_operations"] = new_ops.to_dict("records")

    # Missing operations
    result["missing_operations"] = list(task_ops - order_ops)

    merged = order_df.merge(
        task_df,
        on="TaskListOperationInternalId",
        how="inner",
        suffixes=("_actual", "_planned")
    )

    for _, row in merged.iterrows():
        for field in FIELDS_TO_COMPARE:
            actual = row[f"{field}_actual"]
            planned = row[f"{field}_planned"]

            if field == "Quantity":
                delta = row["Quantity_H_actual"] - row["Quantity_H_planned"]
                result["quantity_deltas"].append({
                    "TaskListOperationInternalId": row["TaskListOperationInternalId"],
                    "delta": delta
                })
            elif actual != planned:
                result["field_deltas"].append({
                    "TaskListOperationInternalId": row["TaskListOperationInternalId"],
                    "field": field,
                    "actual": actual
                })
    return result


# ------------------------------------------------------------------
# Aggregate learning across all orders
# ------------------------------------------------------------------
def aggregate_learning(order_results):
    agg = {
        "quantity_deltas": {},
        "field_stats": {},
        "new_ops_count": {},
        "missing_ops_count": {}
    }

    for res in order_results.values():

        for q in res["quantity_deltas"]:
            op = q["TaskListOperationInternalId"]
            agg["quantity_deltas"].setdefault(op, []).append(q["delta"])

        for f in res["field_deltas"]:
            key = (f["TaskListOperationInternalId"], f["field"], f["actual"])
            agg["field_stats"][key] = agg["field_stats"].get(key, 0) + 1

        for op in res["missing_operations"]:
            agg["missing_ops_count"][op] = agg["missing_ops_count"].get(op, 0) + 1

        if res["new_operations"]:
            agg.setdefault("new_ops", []).extend(res["new_operations"])
            agg["new_ops_count"]["NEW_OP"] = agg["new_ops_count"].get("NEW_OP", 0) + 1

    return agg


# ------------------------------------------------------------------
# Quantity proposal logic (STATISTICAL + UNIT COUPLED)
# ------------------------------------------------------------------
def propose_quantity_changes(task_df, agg):
    proposals = []

    for op_id, deltas in agg.get("quantity_deltas", {}).items():
        deltas = np.array(deltas)

        z = np.abs(stats.zscore(deltas))
        filtered = deltas[z < 2.5]

        if len(filtered) < 3:
            continue

        mean_delta = stats.trim_mean(filtered, 0.1)
        std_dev = np.std(filtered)
        cv = std_dev / abs(mean_delta) if mean_delta != 0 else np.inf

        if abs(mean_delta) < 0.25:
            continue

        row = task_df.loc[
            task_df.TaskListOperationInternalId == op_id
        ].iloc[0]

        current_qty = float(row["Quantity"])
        current_unit = row["Unit"]
        current_hours = float(row["Quantity_H"])

        suggested_hours = current_hours + mean_delta

        suggested_qty, suggested_unit = suggest_quantity_and_unit(
            suggested_hours,
            preferred_unit=current_unit
        )

        confidence = (
            "HIGH" if cv < 0.3 else
            "MEDIUM" if cv < 0.5 else
            "LOW"
        )

        proposal_type = (
            "UPDATE_QUANTITY_AND_UNIT"
            if suggested_unit != current_unit
            else "UPDATE_QUANTITY"
        )

        proposals.append({
            "TaskListOperationInternalId": int(op_id),
            "type": proposal_type,
            "current": {
                "quantity": current_qty,
                "unit": current_unit
            },
            "suggested": {
                "quantity": suggested_qty,
                "unit": suggested_unit
            },
            "normalized_hours": round(suggested_hours, 2),
            "stats": {
                "mean_delta_hours": round(mean_delta, 2),
                "std_dev": round(std_dev, 2),
                "cv": round(cv, 2),
                "sample_size": int(len(filtered))
            },
            "confidence": confidence,
            "rule": "UNIT_COUPLED_WITH_QUANTITY"
        })

    return proposals


def propose_description_changes_semantic(task_df, agg, total_orders):
    """
    Detects semantic description drift and proposes a merged master description.
    Uses NLP embeddings + clustering.
    """

    proposals = []

    # Collect description variants per operation
    desc_map = {}
    for (op_id, field, actual_desc), count in agg.get("field_stats", {}).items():
        if field != "OperationDescription":
            continue

        desc_map.setdefault(op_id, []).extend([actual_desc] * count)

    for op_id, desc_list in desc_map.items():
        if len(desc_list) < 3:
            continue

        # Normalize + keep raw text aligned
        norm_descs = []
        raw_descs = []
        for d in desc_list:
            nd = normalize_description(d)
            if nd:
                norm_descs.append(nd)
                raw_descs.append(d)

        if not norm_descs:
            continue

        # Semantic clustering
        clusters = cluster_by_similarity(norm_descs, threshold=0.8)

        # Find dominant cluster
        dominant = max(clusters, key=len)
        ratio = len(dominant) / total_orders
        print(ratio)
        if ratio < 0.6:
            continue

        # Representative phrase (most frequent raw text in cluster)
        cluster_raw = [raw_descs[i] for i in dominant]
        suggested_desc = Counter(cluster_raw).most_common(1)[0][0]

        current_desc = task_df.loc[
            task_df.TaskListOperationInternalId == op_id,
            "OperationDescription"
        ].iloc[0]

        if normalize_description(current_desc) == normalize_description(suggested_desc):
            continue

        proposals.append({
            "TaskListOperationInternalId": int(op_id),
            "type": "UPDATE_DESCRIPTION",
            "current_description": current_desc,
            "suggested_description": suggested_desc,
            "confidence": "HIGH" if ratio > 0.8 else "MEDIUM",
            "evidence": {
                "variants": list(set(cluster_raw)),
                "occurrences": len(cluster_raw),
                "orders_affected_ratio": round(ratio, 2),
                "semantic_threshold": 0.8
            },
            "method": "SEMANTIC_CLUSTERING"
        })

    return proposals


# ------------------------------------------------------------------
# Master proposal orchestrator
# ------------------------------------------------------------------
def propose_master_changes(task_df, agg, total_orders):
    proposals = []

    # Quantity proposals (single source of truth)
    proposals.extend(propose_quantity_changes(task_df, agg))

    if ENABLE_SEMANTIC_DESC:
        proposals.extend(
            propose_description_changes_semantic(task_df, agg, total_orders)
        )

    # Non-quantity field proposals
    for (op_id, field, proposed_value), count in agg.get("field_stats", {}).items():
        if count / total_orders < 0.6:
            continue
        if field == "Unit" or field == "OperationDescription":
            continue

        current_value = task_df.loc[
            task_df.TaskListOperationInternalId == op_id, field
        ].iloc[0]

        proposals.append({
            "TaskListOperationInternalId": int(op_id),
            "type": f"UPDATE_{field.upper()}",
            "current_value": current_value,
            "suggested_value": proposed_value,
            "confidence": "HIGH" if count / total_orders > 0.8 else "MEDIUM"
        })

    if MIN_ORDERED_NEEDED_FOR_DELETE > 10:
        # Structural deletes
        for op_key, count in agg.get("missing_ops_count", {}).items():
            presence = agg.get("op_presence", {}).get(op_key, 0)
            presence_ratio = presence / total_orders

            if presence_ratio < MIN_PRESENCE_RATIO:
                continue

            if count / total_orders > 0.6:
                proposals.append({
                    "TaskListOperationInternalId": int(op_key),
                    "type": "DELETE_OPERATION",
                    "confidence": "MEDIUM"
                })

    # New operation detection
    # ------------------------------------------------------------
    # Suggest new operation (PROVISIONAL)
    # ------------------------------------------------------------
    new_ops = agg.get("new_ops", [])
    new_op_ratio = agg.get("new_ops_count", {}).get("NEW_OP", 0) / total_orders

    if new_ops and new_op_ratio > 0.4:
        total_orders = total_orders

        # Cluster by normalized description
        clusters = {}
        for op in new_ops:
            key = normalize_description(op.get("OperationDescription"))
            if key:
                clusters.setdefault(key, []).append(op)

        for desc_key, ops in clusters.items():
            affected_orders = len(set(op["MaintenanceOrder"] for op in ops))
            ratio = affected_orders / total_orders

            if ratio < 0.6:
                continue  # not strong enough

            # Aggregate attributes
            wc_values = [op["WorkCenter"] for op in ops if op.get("WorkCenter")]
            plant_values = [op["Plant"] for op in ops if op.get("Plant")]

            qty_hours = [
                normalize_to_hours(op["Quantity"], op["Unit"])
                for op in ops
                if op.get("Quantity") is not None and op.get("Unit") is not None
            ]

            if not qty_hours:
                continue

            avg_hours = stats.trim_mean(qty_hours, 0.1)
            suggested_qty, suggested_unit = suggest_quantity_and_unit(avg_hours)

            proposals.append({
                "type": "ADD_NEW_OPERATION",
                "confidence": "HIGH",
                "suggested_operation": {
                    "Description": ops[0]["OperationDescription"],
                    "WorkCenter": most_common(wc_values),
                    "Plant": most_common(plant_values),
                    "Quantity": suggested_qty,
                    "Unit": suggested_unit
                },
                "evidence": {
                    "occurrences": len(ops),
                    "orders_affected_ratio": round(ratio, 2),
                    "avg_quantity_hours": round(avg_hours, 2)
                }
            })

    return proposals
