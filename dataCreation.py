
import json
import random

TASK_LIST_DESCRIPTIONS = {
    10: "Inspect motor",
    20: "Replace seal",
    30: "Lubricate bearing",
    40: "Calibrate sensor",
    50: "Clean filter",
    60: "Check alignment",
    70: "Tighten bolts",
    80: "Functional test"
}

NEW_OPERATION_DESCRIPTIONS = [
    "Seal replacement",
    "Emergency cleaning",
    "Cable re-routing"
]

MASTER_TASK_LIST = [
    {
        "TaskListOperationInternalId": op_id,
        "WorkCenter": f"WC0{op_id//10}",
        "Plant": "1000",
        "OpPlannedWorkQuantity": qty,
        "OpWorkQuantityUnit": unit,
        "OperationText": TASK_LIST_DESCRIPTIONS[op_id]
    }
    for op_id, qty, unit in [
        (10, 4.0, "H"),
        (20, 3.0, "H"),
        (30, 2.0, "H"),
        (40, 1.0, "D"),
        (50, 120, "MIN"),
        (60, 2.0, "H"),
        (70, 2.5, "H"),
        (80, 1.5, "H")
    ]
]


def generate_large_payload(num_orders=100):
    mo_results = []

    for i in range(1, num_orders + 1):
        order_id = f"MO{7000 + i}"

        for op in MASTER_TASK_LIST:
            op_id = op["TaskListOperationInternalId"]

            # -------------------------------
            # Operation lifecycle rules
            # -------------------------------
            include = False

            if op_id == 10:
                include = True  # always
            elif op_id == 20:
                include = i <= int(0.7 * num_orders)  # fades out
            elif op_id == 30:
                include = random.random() < 0.5
            elif op_id == 40:
                include = i <= int(0.3 * num_orders)  # early-only
            elif op_id == 50:
                include = i >= int(0.5 * num_orders)  # late-only
            elif op_id == 60:
                include = random.random() < 0.3
            elif op_id == 70:
                include = False  # never appears
            elif op_id == 80:
                include = True  # always

            if not include:
                continue

            # -------------------------------
            # Quantity + Unit behavior
            # -------------------------------
            if op_id == 20:
                qty = random.uniform(180, 210)
                unit = "MIN"
            elif op_id == 40:
                qty = random.uniform(0.9, 1.1)
                unit = "D"
            else:
                qty = random.uniform(
                    op["OpPlannedWorkQuantity"] * 0.9,
                    op["OpPlannedWorkQuantity"] * 1.1
                )
                unit = op["OpWorkQuantityUnit"]

            # -------------------------------
            # WorkCenter / Plant drift
            # -------------------------------
            wc = op["WorkCenter"]
            plant = op["Plant"]

            if op_id == 30 and random.random() < 0.7:
                wc = "WC99"

            if op_id == 40:
                plant = "2000"

            mo_results.append({
                "MaintenanceOrder": order_id,
                "MaintenanceOrderOperation": str(op_id).zfill(4),
                "WorkCenter": wc,
                "Plant": plant,
                "MaintOrderOperationQuantity": round(qty, 2),
                "MaintOrdOperationQuantityUnit": unit,
                "TaskListOperationInternalId": op_id,
                "OperationDescription": TASK_LIST_DESCRIPTIONS.get(op_id)
            })

        # -------------------------------
        # Repeated NEW operation (for ADD_NEW_OPERATION)
        # -------------------------------
        if i % 2 == 0:
            desc = random.choice(NEW_OPERATION_DESCRIPTIONS)

            mo_results.append({
                "MaintenanceOrder": order_id,
                "MaintenanceOrderOperation": "0090",
                "WorkCenter": "WCX",
                "Plant": "3000",
                "MaintOrderOperationQuantity": round(random.uniform(1.2, 1.6), 2),
                "MaintOrdOperationQuantityUnit": "H",
                "TaskListOperationInternalId": 0,
                "OperationDescription": desc
            })

    return {
        "results": [
            {"d": {"results": mo_results}},
            {"value": MASTER_TASK_LIST}
        ]
    }
