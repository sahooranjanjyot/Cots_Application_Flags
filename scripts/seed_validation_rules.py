import os
import sys
import json
import uuid

# Add parent directory to path since scripts/ needs to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, ValidationRule

PROCESS_STEPS = [
  "ROUTE_STEP",
  "PART_VERIFICATION",
  "DC_TOOL_STEP",
  "FLUID_FILL_STEP",
  "FF_STEP",
  "DECKING_VISION"
]

ASSEMBLY_LEVELS = [
  "MAIN_ASSEMBLY",
  "SUB_ASSEMBLY"
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
  "targetSystem",
  "processStep",
  "assemblyLevel",
  "resultType",
  "productId",
  "serialNumber",
  "eventTimestamp",
  "qualityResultFileId"
]

FAIL_FIELDS = [
  "defectCode",
  "defectDescription"
]

OVERRIDE_FIELDS = [
  "overrideReasonCode",
  "overrideBy",
  "overrideTimestamp"
]

def generate_rules():
    db = SessionLocal()
    try:
        rules_generated = 0
        rules_updated = 0
        rules_inserted = 0

        for step in PROCESS_STEPS:
            for assembly in ASSEMBLY_LEVELS:
                for result in RESULT_TYPES:
                    rule_id = f"{step}_{assembly}_{result}"
                    
                    mandatory_fields = list(BASE_FIELDS)
                    forbidden_fields = []
                    
                    if result == "FAIL":
                        mandatory_fields.extend(FAIL_FIELDS)
                        forbidden_fields.extend(OVERRIDE_FIELDS)
                    elif result == "OVERRIDE_PASS":
                        mandatory_fields.extend(OVERRIDE_FIELDS)
                        forbidden_fields.extend(FAIL_FIELDS)
                    elif result == "OVERRIDE_FAIL":
                        mandatory_fields.extend(FAIL_FIELDS)
                        mandatory_fields.extend(OVERRIDE_FIELDS)
                        forbidden_fields = []
                    elif result == "PASS":
                        forbidden_fields.extend(FAIL_FIELDS)
                        forbidden_fields.extend(OVERRIDE_FIELDS)
                        
                    # Check if rule exists
                    existing_rule = db.query(ValidationRule).filter_by(rule_id=rule_id).first()
                    
                    if existing_rule:
                        existing_rule.mandatory_fields_json = json.dumps(mandatory_fields)
                        existing_rule.forbidden_fields_json = json.dumps(forbidden_fields)
                        existing_rule.enabled = True
                        rules_updated += 1
                    else:
                        new_rule = ValidationRule(
                            rule_id=rule_id,
                            process_step=step,
                            assembly_level=assembly,
                            result_type=result,
                            mandatory_fields_json=json.dumps(mandatory_fields),
                            forbidden_fields_json=json.dumps(forbidden_fields),
                            enabled=True
                        )
                        db.add(new_rule)
                        rules_inserted += 1
                        
                    rules_generated += 1
                    
        db.commit()
        print(f"Generated a total of {rules_generated} rules.")
        print(f"Inserted: {rules_inserted}")
        print(f"Updated: {rules_updated}")
                    
    finally:
        db.close()

if __name__ == "__main__":
    print(f"Connecting to database and seeding rules...")
    generate_rules()
    print("Done!")
