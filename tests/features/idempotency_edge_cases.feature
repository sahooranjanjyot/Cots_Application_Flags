Feature: Validate idempotency edge cases

  Scenario: Same event with different payload content
    Given MES sends an event with same eventId but modified data
    When the system processes the event
    Then duplicate should be detected
    And event should not be reprocessed

  Scenario: Replay does not duplicate
    Given an event has already been processed
    When replay is triggered
    Then FLAGS should not receive duplicate record
