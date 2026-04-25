Feature: Validate override flow

  Scenario: Validate override flow
    Given MES sends a QUALITY_RESULT override event
    And original result is FAIL
    And override result is PASS
    And approval is required
    When the system processes the event
    Then the event should be stored with PENDING status
    When approval is completed
    Then the event should be sent to FLAGS
    And audit trail should be maintained
