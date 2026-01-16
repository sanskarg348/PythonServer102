UNIT_CONVERSION_TO_HOURS = {
    "H": 1.0,
    "MIN": 1 / 60,
    "D": 8.0      # business assumption: 1 day = 8 working hours
}

FIELDS_TO_COMPARE = [
    "Quantity",
    "Unit",
    "WorkCenter",
    "Plant",
    "OperationDescription"
    # "OperationNumber"
]
UNIT_PREFERENCE_RULES = {
    "H": {
        "min": 0.25,
        "max": 16
    },
    "MIN": {
        "min": 1,
        "max": 600
    },
    "D": {
        "min": 0.25,
        "max": 5
    }
}
ENABLE_SEMANTIC_DESC = True
MIN_PRESENCE_RATIO = 0.2
MIN_ORDERED_NEEDED_FOR_DELETE = 10