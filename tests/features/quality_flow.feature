Feature: Validate quality result processing

  Scenario Outline: Validate quality result processing
    Given MES sends a QUALITY_RESULT event
    And step is <process_step>
    And result is <quality_result>
    When the system processes the event
    Then validation should follow configured rules
    And payload should be transformed using mapping configuration
    And FLAGS should receive the correct payload
    And event should be stored with appropriate status
    
    Examples:
      | process_step | quality_result |
      | ROUTE        | PASS           |
      | ROUTE        | FAIL           |
