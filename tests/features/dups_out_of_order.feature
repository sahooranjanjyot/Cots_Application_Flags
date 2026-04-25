Feature: Handle Duplicate and Out-of-Order MES Events

  Scenario: Duplicate event is ignored
    Given MES sends a quality event
    And the same event is received again with the same idempotency key
    When the engine processes the duplicate event
    Then no duplicate FLAGS record should be created
    And the duplicate should be logged

  Scenario: Out-of-order event is held
    Given a sub-assembly event arrives before the parent assembly event
    When the engine processes the event
    Then the event should be stored in HOLDING_FOR_DEPENDENCY status
    And it should not be sent to FLAGS

  Scenario: Held event is released
    Given a held event exists
    And its missing dependency later arrives
    When the engine re-evaluates dependencies
    Then the event should be validated
    And sent to FLAGS if all rules pass
