## Purpose

Define the Flask-rendered Dashboard and student-management browser interface.
## Requirements
### Requirement: Student management page
The system SHALL provide browser-accessible student-management screens rendered
with Flask templates, including a shared layout and an enhanced `/students`
page.

#### Scenario: Student page is server-rendered
- **WHEN** a browser requests `GET /students`
- **THEN** the system SHALL return an HTML page for student management
- **AND** the page SHALL be rendered through Flask templates rather than a
  separate SPA framework

#### Scenario: Initial page render shows the complete page before any modal workflow
- **WHEN** a browser initially loads or refreshes `GET /students`
- **THEN** the system SHALL first display the complete student management page
- **AND** the visible page SHALL include shared navigation, the toolbar/search
  area, and the student list or empty state
- **AND** it SHALL NOT automatically open a modal during that initial render

#### Scenario: UI labels are Chinese while code keys remain English
- **WHEN** the student management page is rendered and used
- **THEN** visible labels, actions, and feedback messages SHALL be presented in
  Chinese
- **AND** API payload keys and JavaScript field names SHALL remain English

#### Scenario: Student table and reusable modal use the approved fields
- **WHEN** the student management page renders the table or the reusable
  create/edit modal
- **THEN** they SHALL use the fields `student_number`, `name`, `gender`, `age`,
  `major`, `year_level`, `score`, `phone`, and `email`
- **AND** the visible Chinese labels SHALL show `year_level` as `年级` and
  `score` as `成绩`

#### Scenario: Student page includes list-enhancement controls
- **WHEN** the student management page renders successfully
- **THEN** it SHALL include pagination controls, matching-record totals,
  sortable headers, row checkboxes, a current-page select-all checkbox, and a
  batch-delete action
- **AND** the default page SHALL show no more than 15 student records

#### Scenario: Modal and backdrop are hidden by default
- **WHEN** the student management page is initially rendered, refreshed,
  loading the student list, or showing the empty state
- **THEN** the reusable modal and its backdrop SHALL remain hidden by default
- **AND** the page SHALL NOT automatically enter create mode or edit mode

#### Scenario: Create workflow opens the reusable modal
- **WHEN** the user activates the `新增学生` control from the student management
  page
- **THEN** the page SHALL open the reusable modal in create mode instead of
  showing a permanently expanded inline create form

#### Scenario: Edit workflow opens the reusable modal with current values
- **WHEN** the user activates the `编辑` control for an existing student
- **THEN** the page SHALL open the reusable modal in edit mode
- **AND** the modal SHALL be prefilled with the current student data

---

### Requirement: Browser-side CRUD interactions
The system SHALL provide browser-side student-management behavior through
vanilla JavaScript ES modules that consume the REST API.

#### Scenario: Initial load shows data or empty state
- **WHEN** the student management page loads
- **THEN** the browser SHALL request the student list from the REST API using
  default page `1`, default `page_size` `15`, default `sort_by`
  `student_number`, and default `sort_order` `asc`
- **AND** it SHALL show either the student data or an explicit empty state
- **AND** it SHALL present a visible loading state while the request is in
  progress

#### Scenario: Search uses the REST API and resets to page 1
- **WHEN** the user searches for students from the page
- **THEN** the browser SHALL request filtered results from `GET /api/students`
- **AND** the list display SHALL update from the API response
- **AND** the UI SHALL reset to page 1 for the new keyword

#### Scenario: Sort uses the REST API and resets to page 1
- **WHEN** the user changes the sort field or sort direction from a sortable
  table header
- **THEN** the browser SHALL request the sorted list from `GET /api/students`
- **AND** the UI SHALL reset to page 1
- **AND** the page SHALL visibly indicate ascending or descending order

#### Scenario: Pagination controls request the corresponding page
- **WHEN** the user moves to the next page, previous page, or another available
  page
- **THEN** the browser SHALL request that page from `GET /api/students`
- **AND** it SHALL update the visible list and pagination display from the API
  response metadata

#### Scenario: Current-page select-all affects only visible rows
- **WHEN** the user toggles the header checkbox on the student table
- **THEN** the page SHALL select or clear only the student rows visible on the
  current page
- **AND** it SHALL NOT select records from other pages

#### Scenario: Partial selection uses an indeterminate header state
- **WHEN** the user selects some but not all visible student rows
- **THEN** the header checkbox SHALL display the partial or indeterminate state

#### Scenario: Selection resets when the list basis changes
- **WHEN** the current page, keyword, or sort changes
- **THEN** the current selection SHALL be cleared

#### Scenario: Batch delete uses one API request
- **WHEN** the user confirms batch deletion for one or more selected students
- **THEN** the browser SHALL send one `POST /api/students/batch-delete`
  request
- **AND** after success it SHALL refresh the visible list and the visible
  matching-record totals on the student page
- **AND** if the current page becomes empty it SHALL move to the previous valid
  page

#### Scenario: List loading and empty-state rendering do not open the modal automatically
- **WHEN** the browser loads the list, refreshes the list, or renders the empty
  state after a search result
- **THEN** the reusable create/edit modal SHALL remain closed unless the user
  explicitly opened it through a supported action

#### Scenario: Add, edit, and single delete continue to use the REST API
- **WHEN** the user adds, edits, or deletes a single student from the page
- **THEN** the browser SHALL call the corresponding REST API endpoint
- **AND** it SHALL update the visible list from the resulting response flow

#### Scenario: Modal submission closes and refreshes
- **WHEN** a create or edit request succeeds from a modal workflow
- **THEN** the page SHALL close the modal
- **AND** it SHALL refresh the visible student list

#### Scenario: Modal can be cancelled or closed
- **WHEN** the user cancels or closes the create or edit modal
- **THEN** the modal SHALL close without submitting a mutation request
- **AND** the user SHALL return to the visible student management page

---

### Requirement: Shared administration layout
The system SHALL provide one shared administration layout for the Dashboard and
student management page.

#### Scenario: Dashboard uses the shared administration layout
- **WHEN** a browser requests `GET /`
- **THEN** the rendered page SHALL use the shared administration layout
- **AND** the page SHALL display a top bar, a left-side navigation region, and
  a right-side content region

#### Scenario: Student page uses the same shared administration layout
- **WHEN** a browser requests `GET /students`
- **THEN** the rendered page SHALL use the same shared administration layout as
  the Dashboard
- **AND** the page shell SHALL NOT diverge into a conflicting page-specific
  outer layout

---

### Requirement: Primary navigation
The system SHALL expose one clear primary navigation model for page switching.

#### Scenario: Dashboard navigation active state is visible
- **WHEN** the user is on the Dashboard
- **THEN** the `首页` navigation item SHALL display an active state

#### Scenario: Student page navigation active state is visible
- **WHEN** the user is on the student management page
- **THEN** the `学生管理` navigation item SHALL display an active state

#### Scenario: Shared navigation routes to the Dashboard
- **WHEN** the user activates the `首页` navigation item
- **THEN** the browser SHALL navigate to `/`

#### Scenario: Shared navigation routes to student management
- **WHEN** the user activates the `学生管理` navigation item
- **THEN** the browser SHALL navigate to `/students`

---

### Requirement: No duplicate header actions
The system SHALL avoid repeating equivalent student-management entry actions in
the Dashboard header area.

#### Scenario: Dashboard does not render duplicate student-management buttons
- **WHEN** the Dashboard finishes rendering
- **THEN** the top-right header area SHALL NOT display two duplicate
  `学生管理系统` or `学生管理` actions
- **AND** the primary navigation entry points SHALL remain clear and
  non-duplicative

---

### Requirement: Consistent visual styling
The system SHALL present the Dashboard and student management page with one
coherent visual language.

#### Scenario: Shared shell uses consistent visual treatment
- **WHEN** the user switches between `/` and `/students`
- **THEN** both pages SHALL use consistent navigation, typography, spacing,
  cards, buttons, form controls, table styling, status messages, and content
  containers

---

### Requirement: Responsive layout
The system SHALL remain usable across common desktop and narrower browser
widths.

#### Scenario: Navigation does not obscure content on narrower screens
- **WHEN** the browser width shrinks
- **THEN** the main content SHALL remain accessible
- **AND** the navigation SHALL NOT obscure the main content
- **AND** the page SHALL NOT introduce unnecessary large horizontal overflow

---

### Requirement: Modal visual isolation
The system SHALL keep the reusable student modal visually independent from the
shared shell.

#### Scenario: Closed modal remains hidden
- **WHEN** the student modal is closed
- **THEN** the modal and its backdrop SHALL remain hidden

#### Scenario: Open modal appears above the shared layout
- **WHEN** the student modal is opened
- **THEN** it SHALL render above the shared layout
- **AND** it SHALL NOT be obscured by the top bar, sidebar, or content
  container

---

### Requirement: Readable Chinese text
The system SHALL present readable Chinese text in all user-visible copy.

#### Scenario: User-visible text does not contain mojibake
- **WHEN** any user-visible page text is rendered
- **THEN** it SHALL use normal readable Chinese where Chinese copy is intended
- **AND** it SHALL NOT show mojibake, replacement glyphs, broken punctuation,
  or corrupted placeholder text

---

### Requirement: UI feedback states
The system SHALL provide clear loading, empty, disabled, and error states for
the Dashboard and student-management page.

#### Scenario: Loading state is visible during requests
- **WHEN** the browser is waiting for Dashboard data, a student list response,
  or a mutation response
- **THEN** the page SHALL present a visible loading state

#### Scenario: Batch delete action is disabled with no selection
- **WHEN** no student rows are selected on the current page
- **THEN** the batch-delete action SHALL be visibly disabled

#### Scenario: Error message is shown on failed request
- **WHEN** an API request fails
- **THEN** the page SHALL present an error message to the user
- **AND** it SHALL NOT silently pretend the operation succeeded

#### Scenario: Dashboard cards fail independently
- **WHEN** one Dashboard data request fails while another succeeds
- **THEN** the failed card SHALL show its own fallback or error state
- **AND** the other card SHALL remain independently renderable

---

### Requirement: Dashboard page
The system SHALL provide a server-rendered Dashboard at the root route `/`.

#### Scenario: Root route returns HTML Dashboard
- **WHEN** a browser requests `GET /`
- **THEN** the system SHALL return an HTML Dashboard page
- **AND** it SHALL NOT return a JSON 404 response
- **AND** it SHALL NOT only redirect to `/students`

#### Scenario: Dashboard shows shared navigation and quick access
- **WHEN** the Dashboard is rendered
- **THEN** it SHALL show the shared application shell with the top bar and
  left-side primary navigation
- **AND** the `首页` navigation item SHALL be active
- **AND** it SHALL provide a clear quick link to `/students`

#### Scenario: Dashboard shows student total and system status
- **WHEN** the Dashboard loads
- **THEN** it SHALL display a student total-count card using
  `GET /api/students/stats`
- **AND** it SHALL display a health or status card using the approved
  application health information

#### Scenario: Dashboard stats refresh on page load or refresh
- **WHEN** the user opens or refreshes the Dashboard
- **THEN** the page SHALL request the latest count from
  `GET /api/students/stats`
- **AND** it SHALL NOT rely on cross-page browser state from `/students`

#### Scenario: Dashboard and student page share visual style
- **WHEN** the user navigates between `/` and `/students`
- **THEN** both pages SHALL use consistent spacing, typography, colors,
  buttons, cards, and message styles

---

### Requirement: Shared layout and navigation
The system SHALL provide shared navigation between the Dashboard and student
management page.

#### Scenario: Navigation works in both directions
- **WHEN** the user uses the page navigation
- **THEN** `首页` SHALL navigate to `/`
- **AND** `学生管理` SHALL navigate to `/students`

#### Scenario: Active navigation state reflects the current page
- **WHEN** either the Dashboard or the student page is rendered
- **THEN** the current page's navigation item SHALL display an active state

#### Scenario: Student page provides a clear return path
- **WHEN** the user is on `/students`
- **THEN** the page SHALL provide a clear and visible way to return to the
  Dashboard

---

### Requirement: Preserve existing student interactions
The system SHALL preserve the approved student-management interaction contract
while applying layout and styling changes.

#### Scenario: Visual refresh does not change the interaction contract
- **WHEN** the layout, styling, or visible copy is updated
- **THEN** create, edit, single delete, pagination, sorting, current-page
  selection, batch delete, `year_level`, `score`, and leading-zero student
  numbers SHALL continue to use the approved API and browser interaction
  contract

### Requirement: AI Chat preserves student UI contracts
The system SHALL add AI Chat through the shared layout without changing the
student page's server-rendering or modal-state contracts.

#### Scenario: Student page remains server-rendered with AI Chat
- **WHEN** a browser requests `GET /students`
- **THEN** the system SHALL return the Flask-rendered student-management page
- **AND** the AI Chat panel SHALL be included through the shared `base.html`
  layout without changing the student page template structure

#### Scenario: Dashboard shared layout includes AI Chat
- **WHEN** a browser requests `GET /`
- **THEN** the Dashboard SHALL use the shared administration layout
- **AND** the AI Chat icon SHALL be rendered as part of that shared layout

#### Scenario: AI Chat does not alter student modal state
- **WHEN** the student modal is closed
- **THEN** it SHALL remain hidden regardless of AI Chat panel state
- **WHEN** the student modal opens
- **THEN** the AI Chat panel SHALL close automatically
- **AND** the modal SHALL remain open regardless of any prior Chat Panel state

### Requirement: Login-protected server-rendered pages
The Dashboard and student-management pages SHALL require login while preserving the existing Flask-rendered page model.

#### Scenario: Dashboard redirects unauthenticated user
- **WHEN** an unauthenticated browser requests `GET /`
- **THEN** the system SHALL redirect to `/login` with a safe site-local `next` value

#### Scenario: Student page redirects unauthenticated user
- **WHEN** an unauthenticated browser requests `GET /students`
- **THEN** the system SHALL redirect to `/login` with a safe site-local `next` value

#### Scenario: Authenticated user can render pages
- **WHEN** an authenticated Viewer, Staff, or Admin requests `GET /` or `GET /students`
- **THEN** the system SHALL render the existing server-side template flow
- **AND** it SHALL include the current username, current role, and CSRF token for browser interactions

### Requirement: Login page UI
The system SHALL provide a server-rendered login page that fits the existing visual language while using a simple centered card layout.

#### Scenario: Login form contains required controls
- **WHEN** `GET /login` renders for an unauthenticated user
- **THEN** the page SHALL show the system name, username field, password field, login button, generic error area, CSRF hidden field, and accessible labels

#### Scenario: Login copy is safe and readable
- **WHEN** the login page displays an error
- **THEN** the message SHALL be generic
- **AND** it SHALL NOT reveal whether a username exists
- **AND** user-visible Chinese text SHALL be readable and not mojibake

### Requirement: Role-aware browser controls
The browser UI SHALL hide unavailable student-management controls based on the current role while relying on backend authorization as the enforcement boundary.

#### Scenario: Viewer controls are read-only
- **WHEN** a Viewer renders the student-management page
- **THEN** create, edit, single-delete, and batch-delete entry points SHALL be hidden or disabled
- **AND** read-only list, search, sort, pagination, stats, and AI Chat entry points SHALL remain usable

#### Scenario: Staff controls exclude delete
- **WHEN** a Staff user renders the student-management page
- **THEN** create and edit entry points SHALL be available
- **AND** single-delete and batch-delete entry points SHALL be hidden or disabled

#### Scenario: Admin controls include all student actions
- **WHEN** an Admin renders the student-management page
- **THEN** create, edit, single-delete, and batch-delete entry points SHALL be available

### Requirement: Logout UI
The shared authenticated layout SHALL display the current username and role and provide a POST-only logout control.

#### Scenario: Authenticated layout shows identity
- **WHEN** an authenticated page renders
- **THEN** the top area SHALL show the current username and role

#### Scenario: Logout uses POST with CSRF
- **WHEN** a user activates logout
- **THEN** the browser SHALL submit `POST /logout` with a CSRF token
- **AND** logout SHALL NOT be implemented as a GET navigation

### Requirement: Browser unsafe requests include CSRF
Existing vanilla JavaScript browser requests that mutate student data or confirm AI actions SHALL include the CSRF token using `X-CSRF-Token`.

#### Scenario: Student mutations include CSRF header
- **WHEN** `students.js` sends create, update, single-delete, or batch-delete requests
- **THEN** it SHALL include `X-CSRF-Token`

#### Scenario: AI Chat unsafe requests include CSRF header
- **WHEN** `ai_chat.js` sends `POST /api/chat` or `POST /api/chat/actions/confirm`
- **THEN** it SHALL include `X-CSRF-Token`

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
