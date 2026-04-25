Feature: Validate forbidden field enforcement

  Scenario: PASS event contains defectCode
    Given MES sends a PASS event with defectCode
    When the system processes the event
    Then validation should fail
    And event should not be sent to FLAGS

  Scenario: PASS event contains override fields
    Given MES sends a PASS event with overrideReasonCode
    When the system processes the event
    Then validation should fail
