import json
from database import SessionLocal, ValidationRule

PROCESS_STEPS = [
  "ROUTE_STEP",
  "PART_VERIFICATION",
  "DC_TOOL_STEP",
  "FLUID_FILL_STEP",
  "FF_STEP",
  "DECKING_VISION",
  "FINAL_ASSEMBLY",
  "ROUTE",
  "ROUTE_NO_APPROVAL",
  "DC_TOOL",
  "FLUID_FILL"
]

ASSEMBLY_LEVELS = [
  "MAIN_ASSEMBLY",
  "SUB_ASSEMBLY",
  "ASSEMBLY" # To natively bind what test configurations used
]

RESULT_TYPES = [
  "PASS",
  "FAIL",
  "OVERRIDE_PASS",
  "OVERRIDE_FAIL"
]

BASE_FIELDS = [
  "eventId",
  "eventType",
  "sourceSystem",
  "step", # Mapped from processStep
  "entityType", # Mapped from assemblyLevel
  "result", # Mapped from resultType
  "productId",
  "serialNumber"
]

FAIL_FIELDS = [
  "defectCode",
  "defectDescription",
  "errorCode"
]

OVERRIDE_FIELDS = [
  "overrideReasonCode",
  "overrideBy",
  "overrideTimestamp"
]

def generate_rules():
    db = SessionLocal()
    try:
        # Clear existing rules if re-running
        db.query(ValidationRule).delete()
        
        count = 0
        for step in PROCESS_STEPS:
            for level in ASSEMBLY_LEVELS:
                for result in RESULT_TYPES:
                    rule_id = f"{step}_{level}_{result}"
                    
                    mandatory_fields = list(BASE_FIELDS)
                    forbidden_fields = []
                    
                    if result == "FAIL":
                        mandatory_fields.extend(FAIL_FIELDS)
                        forbidden_fields.extend(OVERRIDE_FIELDS)
                        
                    elif result == "PASS":
                        forbidden_fields.extend(FAIL_FIELDS)
                        forbidden_fields.extend(OVERRIDE_FIELDS)
                        
                    elif result == "OVERRIDE_PASS":
                        mandatory_fields.extend(OVERRIDE_FIELDS)
                        forbidden_fields.extend(FAIL_FIELDS)
                        
                    elif result == "OVERRIDE_FAIL":
                        mandatory_fields.extend(FAIL_FIELDS)
                        mandatory_fields.extend(OVERRIDE_FIELDS)
                        # No forbidden fields
                        
                    new_rule = ValidationRule(
                        rule_id=rule_id,
                        process_step=step,
                        assembly_level=level,
                        result_type=result,
                        mandatory_fields_json=json.dumps(mandatory_fields),
                        forbidden_fields_json=json.dumps(forbidden_fields),
                        enabled=True
                    )
                    db.add(new_rule)
                    count += 1
                    
        db.commit()
        print(f"Successfully generated and seeded {count} validation rules into validation_rules table.")
    except Exception as e:
        print(f"Error seeding database rules: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generate_rules()
