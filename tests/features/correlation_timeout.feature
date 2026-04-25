Feature: Validate correlation timeout handling

  Scenario: Missing sub-assembly after timeout
    Given a parent assembly exists without required sub-assemblies
    When timeout threshold is reached
    Then correlation group should be marked FAILED

  Scenario: Late arriving sub-assembly
    Given a correlation group is marked IN_PROGRESS
    And a delayed sub-assembly event arrives
    When the system processes the event
    Then the group should be re-evaluated
