Feature: Schema Version Detection and Validation

  Scenario: Process active schema version
    Given MES sends an event with an active schema version
    When the system processes the event
    Then the schema should be detected
    And the payload should be normalized
    And validation should run on canonical model
    And FLAGS should receive the expected payload

  Scenario: Process deprecated schema version
    Given MES sends an event using a deprecated schema version
    When the system processes the event
    Then the event should still be accepted
    And a deprecation warning should be logged

  Scenario: Reject retired schema version
    Given MES sends an event using a retired schema version
    When the system processes the event
    Then the event should be rejected
    And moved to exception queue
