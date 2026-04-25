Feature: Validate assembly correlation

  Scenario: Validate assembly correlation
    Given sub-assembly events are received
    And linked to a parent assembly
    When the assembly event is processed
    Then all sub-assemblies should be validated
    And final result should be computed
    And FLAGS should receive complete correlated payload
