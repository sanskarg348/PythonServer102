from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/process", methods=["POST","GET"])
def process():
    payload = request.get_json()

    # Example: CPI sends one split entry
    entry_id = payload.get("id")

    response = {
        "id": entry_id,
        "processed": True
    }

    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)
