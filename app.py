from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from datetime import datetime
import os
import pytz
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, Text, String, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import csv
import io
from functools import wraps
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import base64

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here-change-this-in-production")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Anurag512@")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️ DATABASE_URL not found! Using SQLite for local development...")
    DATABASE_URL = "sqlite:///locations.db"
else:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print(f"✅ Using PostgreSQL database")

print(f"📊 Database: {DATABASE_URL[:50]}...")

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

class Location(Base):
    __tablename__ = 'locations'
    
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    photo = Column(Text, nullable=True)
    photo_filename = Column(String(255), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'has_photo': self.photo is not None
        }

# Create table
Base.metadata.create_all(engine)

# ============ AUTO MIGRATION: Add photo columns if missing ============
try:
    with engine.connect() as conn:
        if 'postgresql' in DATABASE_URL:
            # Check if photo column exists in PostgreSQL
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='locations' AND column_name='photo'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE locations ADD COLUMN photo TEXT"))
                conn.execute(text("ALTER TABLE locations ADD COLUMN photo_filename VARCHAR(255)"))
                conn.commit()
                print("✅ Added missing photo columns to existing table")
            else:
                print("✅ Photo columns already exist")
        else:
            # For SQLite
            try:
                conn.execute(text("ALTER TABLE locations ADD COLUMN photo TEXT"))
                conn.execute(text("ALTER TABLE locations ADD COLUMN photo_filename VARCHAR(255)"))
                conn.commit()
                print("✅ Added photo columns for SQLite")
            except Exception as e:
                print(f"Columns might already exist: {e}")
except Exception as e:
    print(f"⚠️ Migration check skipped: {e}")

print("✅ Database tables ready")

Session = sessionmaker(bind=engine)
IST = pytz.timezone('Asia/Kolkata')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/save-location', methods=['POST'])
def save_location():
    try:
        data = request.get_json()
        
        ist_now = datetime.now(IST)
        
        new_location = Location(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy=data.get("accuracy"),
            timestamp=ist_now,
            photo=data.get("photo"),
            photo_filename=data.get("photo_filename")
        )
        
        session = Session()
        session.add(new_location)
        session.commit()
        record_count = session.query(Location).count()
        session.close()
        
        print(f"✅ Location + Photo saved: {data.get('latitude')}, {data.get('longitude')}")
        
        return jsonify({
            "status": "success",
            "message": "Location and photo saved successfully",
            "total_records": record_count
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('view_locations'))
        else:
            return render_template('login.html', error="Invalid password!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/view')
@login_required
def view_locations():
    return render_template('dashboard.html')

@app.route('/api/photo/<int:id>')
@login_required
def get_photo(id):
    try:
        session = Session()
        location = session.query(Location).filter_by(id=id).first()
        session.close()
        
        if location and location.photo:
            return Response(base64.b64decode(location.photo), mimetype='image/jpeg')
        else:
            return jsonify({'error': 'No photo found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/locations')
def api_locations():
    try:
        search = request.args.get('search', '').strip()
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        session = Session()
        query = session.query(Location)
        
        if search:
            if search.isdigit():
                locations = query.filter(Location.id == int(search)).order_by(Location.timestamp.desc()).offset(offset).limit(limit).all()
                total = query.filter(Location.id == int(search)).count()
            else:
                locations = query.filter(
                    Location.timestamp.cast(Text).contains(search)
                ).order_by(Location.timestamp.desc()).offset(offset).limit(limit).all()
                total = query.filter(
                    Location.timestamp.cast(Text).contains(search)
                ).count()
        else:
            locations = query.order_by(Location.timestamp.desc()).offset(offset).limit(limit).all()
            total = query.count()
        
        session.close()
        
        return jsonify({
            'locations': [loc.to_dict() for loc in locations],
            'total': total,
            'offset': offset,
            'limit': limit
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-csv')
def export_csv():
    try:
        search = request.args.get('search', '').strip()
        
        session = Session()
        query = session.query(Location)
        
        if search:
            if search.isdigit():
                locations = query.filter(Location.id == int(search)).order_by(Location.timestamp.desc()).all()
            else:
                locations = query.filter(
                    Location.timestamp.cast(Text).contains(search)
                ).order_by(Location.timestamp.desc()).all()
        else:
            locations = query.order_by(Location.timestamp.desc()).all()
        
        session.close()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'Latitude', 'Longitude', 'Accuracy (m)', 'Timestamp (IST)', 'Has Photo', 'Google Maps Link'])
        
        for loc in locations:
            maps_link = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
            writer.writerow([
                loc.id,
                loc.latitude,
                loc.longitude,
                loc.accuracy if loc.accuracy else 'N/A',
                loc.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'Yes' if loc.photo else 'No',
                maps_link
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=locations_export.csv"}
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-pdf')
@login_required
def export_pdf():
    try:
        search = request.args.get('search', '').strip()
        
        session = Session()
        query = session.query(Location)
        
        if search:
            if search.isdigit():
                locations = query.filter(Location.id == int(search)).order_by(Location.timestamp.desc()).all()
            else:
                locations = query.filter(
                    Location.timestamp.cast(Text).contains(search)
                ).order_by(Location.timestamp.desc()).all()
        else:
            locations = query.order_by(Location.timestamp.desc()).all()
        
        session.close()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=50, bottomMargin=30)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16,
                                      textColor=colors.HexColor('#1e3a8a'), alignment=1, spaceAfter=20)
        
        elements = []
        elements.append(Paragraph("📍 Cyber Crime Investigation Portal", title_style))
        elements.append(Paragraph(f"Location Records Report - Total: {len(locations)} records", styles['Heading2']))
        elements.append(Spacer(1, 20))
        
        current_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"Generated on: {current_time} IST", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        data = [['S.No', 'ID', 'Latitude', 'Longitude', 'Accuracy', 'Timestamp', 'Photo', 'Google Maps']]
        
        for idx, loc in enumerate(locations, 1):
            data.append([
                str(idx), str(loc.id), str(loc.latitude), str(loc.longitude),
                str(loc.accuracy if loc.accuracy else 'N/A'),
                loc.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                'Yes' if loc.photo else 'No',
                f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
            ])
        
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f5f5f5')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#333333')),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        
        return Response(buffer.getvalue(), mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment;filename=location_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    try:
        session = Session()
        total = session.query(Location).count()
        session.close()
        return jsonify({'total_records': total})
    except Exception as e:
        return jsonify({'error': str(e), 'total_records': 0}), 500

@app.route('/api/delete-location/<int:id>', methods=['DELETE'])
@login_required
def delete_location(id):
    try:
        session = Session()
        location = session.query(Location).filter_by(id=id).first()
        if not location:
            session.close()
            return jsonify({"status": "error", "message": f"Record with ID {id} not found"}), 404
        
        session.delete(location)
        session.commit()
        total = session.query(Location).count()
        session.close()
        
        return jsonify({"status": "success", "message": f"Record {id} deleted successfully", "total_records": total})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)