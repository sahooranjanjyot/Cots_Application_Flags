Feature: Validate Override Workflow generic scenarios

  Scenario Outline: Validate workflow intercepts
    Given an OVERRIDE quality result event
    And the approval requirement is <approval_req>
    And the approval status is <status>
    When the system processes the event
    Then the engine should react with <expected_behavior>
    
    Examples:
      | approval_req | status   | expected_behavior |
      | true         | PENDING  | workflow_pending  |
      | true         | REJECTED | workflow_rejected |
      | true         | APPROVED | success           |
      | false        | NONE     | success           |
