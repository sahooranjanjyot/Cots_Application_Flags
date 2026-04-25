Feature: Validate mandatory field edge cases

  Scenario: Mandatory field is null
    Given MES sends an event with null serialNumber
    When the system processes the event
    Then validation should fail

  Scenario: Mandatory field is empty string
    Given MES sends an event with empty productId
    When the system processes the event
    Then validation should fail

  Scenario: Incorrect field data type
    Given MES sends an event with numeric serialNumber
    When the system processes the event
    Then validation should fail
