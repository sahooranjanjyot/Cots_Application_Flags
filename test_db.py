from database import SessionLocal, MESQualityEvent
db = SessionLocal()
events = db.query(MESQualityEvent).all()
for e in events:
    print(f"Event: {e.event_id}, Status: {e.validation_status}, Transmission: {e.transmission_status}")
db.close()
