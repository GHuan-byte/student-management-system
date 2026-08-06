## ADDED Requirements

### Requirement: Student page exposes stable data-ai-target identifiers
The system SHALL expose stable `data-ai-target` attributes on the student page for
the elements the AI-guided animation needs, so animation targeting does not depend on
fragile selectors such as `nth-child` or AI-supplied selector strings.

#### Scenario: Create and search controls are marked
- **WHEN** the student management page renders
- **THEN** the `新增学生` button SHALL carry `data-ai-target="student-add-button"`
- **AND** the search input SHALL carry `data-ai-target="student-search-input"`
- **AND** the search submit button SHALL carry `data-ai-target="student-search-button"`

#### Scenario: Modal and form controls are marked
- **WHEN** the student create/edit modal renders
- **THEN** the modal container SHALL carry `data-ai-target="student-form-modal"`
- **AND** the form fields SHALL carry `data-ai-target` values for
  `student-number-input`, `student-name-input`, `student-gender-input`,
  `student-age-input`, `student-major-input`, `student-year-level-select`,
  `student-score-input`, `student-phone-input`, and `student-email-input`
- **AND** the submit button SHALL carry `data-ai-target="student-submit-button"`
- **AND** the cancel button SHALL carry `data-ai-target="student-cancel-button"`

#### Scenario: Missing identifiers are detectable
- **WHEN** a required `data-ai-target` element is missing after a template change
- **THEN** a test or startup check SHALL fail with a clear message identifying the
  missing identifier
- **AND** the animation runner SHALL report "目标元素不存在" instead of proceeding

### Requirement: AI-driven list refresh and highlight
The system SHALL let the AI-guided flow refresh and highlight the student list after
a confirmed write succeeds, using the same single-source-of-truth list state as the
manual UI, without duplicating list state or write logic.

#### Scenario: AI success refreshes the list once
- **WHEN** the backend reports that a guided write action succeeded
- **THEN** the student page SHALL reload the list from `GET /api/students`
- **AND** SHALL show the updated data

#### Scenario: New record is highlighted
- **WHEN** a guided create succeeds
- **THEN** the affected row SHALL receive a brief visual highlight
- **AND** the highlight SHALL clear automatically

#### Scenario: Failure does not highlight or refresh as success
- **WHEN** the backend reports that a guided write action failed
- **THEN** the page SHALL NOT highlight the record or refresh as if it succeeded
- **AND** the failure SHALL be reported

### Requirement: Manual CRUD interaction contract is preserved
The system SHALL keep the existing manual student CRUD, search, pagination, sorting,
current-page select-all, and batch-delete interactions fully functional and
unchanged while the AI-guided animation is active.

#### Scenario: Manual workflows remain identical
- **WHEN** a user manually opens the create/edit modal, searches, sorts, pages, or
  deletes
- **THEN** the behavior SHALL match the existing manual interaction contract
- **AND** the AI-guided animation SHALL NOT alter manual button, form, or modal
  behavior

#### Scenario: Animation overlay does not block normal use
- **WHEN** the AI-guided animation is not active
- **THEN** no animation mask, simulated mouse, or step prompt SHALL be visible
- **AND** the page SHALL remain fully interactive for the user
