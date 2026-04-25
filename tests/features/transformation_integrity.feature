Feature: Validate transformation integrity

  Scenario: Mapping produces correct FLAGS payload
    Given MES sends a valid QUALITY_RESULT event
    When the system processes the event
    Then payload should be transformed correctly
    And FLAGS should receive mapped fields

  Scenario: Extra fields are ignored
    Given MES sends an event with extra fields
    When the system processes the event
    Then extra fields should not impact transformation
