Feature: Validate FLAGS response handling

  Scenario: FLAGS returns 4xx error
    Given FLAGS API returns client error
    When the system processes the event
    Then retry should not be triggered
    And event should move to exception queue

  Scenario: FLAGS returns 5xx error
    Given FLAGS API returns server error
    When the system processes the event
    Then retry should be triggered
