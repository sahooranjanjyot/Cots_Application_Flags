Feature: Validate exception handling

  Scenario: Validation failure goes to exception queue
    Given MES sends an invalid event missing mandatory fields
    When the system processes the event
    Then validation should fail
    And the event should be stored in exception queue

  Scenario: Rule not found
    Given MES sends an event with unknown processStep
    When the system processes the event
    Then the event should be rejected
    And stored in exception queue

  Scenario: Exception resolved
    Given an event exists in exception queue
    When support resolves the issue
    Then the event should be marked as resolved
