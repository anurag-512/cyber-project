from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import os
import pytz
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import csv
import io

app = Flask(__name__)

# DATABASE_URL environment variable se le (Render pe automatically set hoga)
DATABASE_URL = os.getenv("DATABASE_URL")

# Local development ke liye - Agar DATABASE_URL nahi hai toh SQLite use karo
if not DATABASE_URL:
    print("⚠️ DATABASE_URL not found! Using SQLite for local development...")
    DATABASE_URL = "sqlite:///locations.db"
else:
    # PostgreSQL ke liye SSL fix (Render ke liye)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print(f"✅ Using PostgreSQL database")

print(f"📊 Database: {DATABASE_URL[:50]}...")  # Show first 50 chars only

# Database Setup
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

# Table Schema
class Location(Base):
    __tablename__ = 'locations'
    
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }

# Create table
Base.metadata.create_all(engine)
print("✅ Database tables ready")

# Session factory
Session = sessionmaker(bind=engine)

# IST Timezone
IST = pytz.timezone('Asia/Kolkata')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/save-location', methods=['POST'])
def save_location():
    try:
        data = request.get_json()
        
        # Get current time in IST
        ist_now = datetime.now(IST)
        
        # Create new record
        new_location = Location(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy=data.get("accuracy"),
            timestamp=ist_now
        )
        
        # Save to database
        session = Session()
        session.add(new_location)
        session.commit()
        
        record_count = session.query(Location).count()
        session.close()
        
        print(f"✅ Location saved: {data.get('latitude')}, {data.get('longitude')} at {ist_now}")
        
        return jsonify({
            "status": "success",
            "message": "Location saved successfully",
            "total_records": record_count
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/view')
def view_locations():
    return render_template('dashboard.html')

@app.route('/api/locations')
def api_locations():
    """API endpoint for fetching locations with search"""
    try:
        search = request.args.get('search', '').strip()
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        session = Session()
        query = session.query(Location)
        
        # Search functionality
        if search:
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
    """Export all locations to CSV"""
    try:
        search = request.args.get('search', '').strip()
        
        session = Session()
        query = session.query(Location)
        
        if search:
            locations = query.filter(
                Location.timestamp.cast(Text).contains(search)
            ).order_by(Location.timestamp.desc()).all()
        else:
            locations = query.order_by(Location.timestamp.desc()).all()
        
        session.close()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['ID', 'Latitude', 'Longitude', 'Accuracy (m)', 'Timestamp (IST)', 'Google Maps Link'])
        
        # Write data
        for loc in locations:
            maps_link = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
            writer.writerow([
                loc.id,
                loc.latitude,
                loc.longitude,
                loc.accuracy if loc.accuracy else 'N/A',
                loc.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
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

@app.route('/api/stats')
def api_stats():
    """Get statistics about records"""
    try:
        session = Session()
        total = session.query(Location).count()
        session.close()
        
        return jsonify({
            'total_records': total
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)