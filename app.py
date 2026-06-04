from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/save-location', methods=['POST'])
def save_location():

    data = request.get_json()

    record = {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    filename = "locations.json"

    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                records = json.load(f)
        except:
            records = []
    else:
        records = []

    records.append(record)

    with open(filename, "w") as f:
        json.dump(records, f, indent=4)

    print(record)

    return jsonify({
        "status": "success"
    })


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)