Feature: Validate out-of-order processing robustness

  Scenario: Main assembly arrives before sub-assembly
    Given a main assembly event arrives first
    When the system processes the event
    Then the event should be held in correlation group
    And not sent to FLAGS

  Scenario: Dependent events complete later
    Given dependent sub-assembly events arrive later
    When the system re-evaluates the group
    Then the event should be processed and sent to FLAGS
