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

    print("LOCATION RECEIVED:", record)

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

    return jsonify({
        "status": "success"
    })


@app.route('/view')
def view_locations():

    filename = "locations.json"

    try:
        with open(filename, "r") as f:
            data = json.load(f)
    except:
        data = []

    html = """
    <html>
    <head>
        <title>Location Records</title>

        <style>

        body{
            font-family:Arial;
            padding:20px;
            background:#f5f5f5;
        }

        h2{
            text-align:center;
        }

        table{
            border-collapse:collapse;
            width:100%;
            background:white;
        }

        th,td{
            border:1px solid #ddd;
            padding:12px;
            text-align:center;
        }

        th{
            background:#007bff;
            color:white;
        }

        a{
            text-decoration:none;
        }

        </style>

    </head>
    <body>

    <h2>Location Records</h2>

    <table>

    <tr>
        <th>Latitude</th>
        <th>Longitude</th>
        <th>Timestamp</th>
        <th>Google Maps</th>
    </tr>
    """

    for row in data:

        lat = row.get("latitude")
        lon = row.get("longitude")
        time = row.get("timestamp")

        html += f"""
        <tr>
            <td>{lat}</td>
            <td>{lon}</td>
            <td>{time}</td>
            <td>
                <a href="https://maps.google.com/?q={lat},{lon}"
                   target="_blank">
                   Open Map
                </a>
            </td>
        </tr>
        """

    html += """
    </table>

    </body>
    </html>
    """

    return html


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )