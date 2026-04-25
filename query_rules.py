from database import SessionLocal, ValidationRule, MESQualityEvent
db = SessionLocal()
print("Total paths seeded: ", db.query(ValidationRule).count())
db.close()
