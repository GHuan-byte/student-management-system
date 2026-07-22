## Context

The archived `build-student-crud` change established the current end-to-end
student flow: Flask pages, a REST API, a service layer, a repository layer, and
SQLite storage. That foundation now works, but it still behaves like an MVP:
there is no Dashboard at `/`, `base.html` does not provide shared navigation,
`GET /api/students` returns an unpaginated collection, and the browser page
lacks sorting, current-page selection, and batch deletion.

The new change enhances the existing application rather than introducing a new
stack. The approved dependency direction remains unchanged:

Browser UI -> Flask REST API -> StudentService -> StudentRepository -> SQLite

No route may access SQLite directly. No new third-party dependency is expected.
Automated tests remain out of scope for this change.

## Goals / Non-Goals

**Goals:**

- Add a real server-rendered Dashboard at `/`
- Introduce shared navigation and consistent layout styling between `/` and
  `/students`
- Add student counting, paginated list queries, whitelist sorting, current-page
  selection, and batch deletion without breaking existing CRUD behavior
- Keep browser state centralized so pagination, search, sort, selection, and
  modal flows do not drift out of sync
- Preserve the approved student data model, including `year_level` and `score`

**Non-Goals:**

- Authentication or user-specific widgets
- Excel import/export
- MCP or AI Chat
- Legacy migration
- Automated tests
- Deployment work
- Analytics charts beyond the requested summary cards

## Decisions

### D1: Serve a true Dashboard at `/` and move the shared application shell into `base.html`

`GET /` will render a dedicated `dashboard.html` template through
`app/routes/pages.py`. `base.html` will become the shared shell for both
Dashboard and student-management pages. The shared shell owns the stable
administration layout:

- a top bar
- a left-side primary navigation region
- a right-side content region for each page body
- navigation links for `首页` and `学生管理`
- an active-page state supplied by the page route
- shared spacing, card, button, form, table, modal, and message styles

Dashboard and student-management pages must not maintain separate, conflicting
page skeletons. The main page-switching affordance is the shared navigation,
not duplicate per-page header buttons.

This keeps page ownership server-rendered while giving both screens one unified
application shell.

Alternative considered:
- Redirect `/` to `/students`
  - Rejected because the approved behavior explicitly requires a real Dashboard
    page at the root path.

### D2: Keep Dashboard content focused while avoiding duplicate navigation actions

The Dashboard will render server-side HTML immediately, then use
`app/static/js/dashboard.js` to load live data for:

- student total count from `GET /api/students/stats`
- health/status from the existing `GET /api/health`

The Dashboard may keep one in-content quick link to `/students`, but it must
not also repeat equivalent student-management entry buttons in the top-right
header area. Navigation should remain clear, non-duplicative, and consistent
with the shared shell.

This keeps the page responsive on first render while ensuring the displayed
count reflects the current SQLite data through the approved route -> service ->
repository path.

Alternative considered:
- Render the count directly inside the page route
  - Rejected because it would duplicate service wiring inside the page render
    path and reduce reuse of the new stats API.

### D3: Keep list state in one browser-side source of truth

`app/static/js/students.js` will manage one state object containing:

- `students`
- `currentPage`
- `pageSize`
- `keyword`
- `sortBy`
- `sortOrder`
- `selectedIds`
- `total`
- `totalPages`
- `loading`
- modal-related state already present in the current page

This state becomes the single source of truth for rendering the table,
pagination controls, sortable headers, selection state, and batch-delete
availability. Search and sort changes will reset to page 1. Page, keyword, and
sort changes will also clear the current selection.

Alternative considered:
- Separate state per UI concern
  - Rejected because the project guardrails already call for one source of
    truth for the list view.

### D4: Perform pagination and sorting in the repository with explicit validation

`StudentRepository` will implement paginated list queries and total-count
queries using parameterized SQL. Sorting will be limited to a repository-side
whitelist:

- `student_number`
- `name`
- `gender`
- `age`
- `major`
- `year_level`
- `score`

Supported orders are `asc` and `desc`. The service layer will validate:

- `page >= 1`
- `page_size >= 1`
- `page_size <= 50`
- `sort_by` within the approved whitelist
- `sort_order` within `asc` / `desc`

The API will return paginated list data plus `meta` fields:
`page`, `page_size`, `total`, `total_pages`, `sort_by`, and `sort_order`.

Alternative considered:
- Load all rows and paginate in JavaScript
  - Rejected because it scales poorly and violates the requirement to keep
    pagination in the backend.

### D5: Add transactional batch delete through one service call and one API request

Batch deletion will use a dedicated endpoint:

- `POST /api/students/batch-delete`

The service layer will normalize duplicate IDs, reject empty or invalid input,
and call one repository method that deletes the requested rows in a single
transaction. The success payload will report both `requested_count` and
`deleted_count`.

The student page will expose one batch-delete control for the current
selection. If deleting the selected rows empties the current page, the browser
will reload the previous valid page automatically.

Alternative considered:
- Issue one `DELETE /api/students/<id>` request per selected row
  - Rejected because the approved behavior explicitly disallows repeated browser
    delete requests for batch removal.

### D6: Preserve the reusable create/edit modal inside the new shared shell

The current student page already uses a reusable create/edit modal. This change
will preserve that workflow and add:

- sortable table headers
- row checkboxes
- a header checkbox for current-page select-all
- a disabled-when-empty batch-delete action
- pagination and total-result controls

Selection behavior must not interfere with opening the edit modal. Clicking
`编辑` continues to open the existing reusable modal. Single delete behavior
remains intact.

The modal must continue to:

- remain hidden by default
- render above the shared layout with a backdrop
- avoid being clipped or obscured by the top bar, sidebar, or content region
- remain interactive while open
- restore page scrolling after close

This change updates layout, styling, and visible copy only. It does not alter
the REST API contract, pagination rules, sorting rules, selection rules,
batch-delete rules, or the create/edit modal's business behavior.

### D7: Centralize visual language in one stylesheet and keep it resilient

`app/static/css/style.css` remains the centralized styling entry point for:

- the shared application shell
- Dashboard cards and status sections
- student-page search, toolbar, table, pagination, and status areas
- the reusable modal
- responsive layout adjustments

Templates should not introduce large inline CSS blocks, and the stylesheet
should avoid letting one page define a second conflicting style system for the
same UI primitives. The layout must remain stable at common desktop widths and
must degrade responsively on narrower screens without major horizontal overflow,
navigation overlap, or hidden elements becoming visible unexpectedly.

User-visible Chinese text must remain readable and must not contain mojibake,
replacement glyphs, or placeholder corruption.

Alternative considered:
- Replace the existing modal workflow again
  - Rejected because the approved CRUD design already converged on one reusable
    create/edit modal and this change only enhances the surrounding list page.

## Risks / Trade-offs

- More list state increases front-end complexity -> Keep one explicit state
  object and reset rules for page, keyword, sort, and selection changes
- Sorting introduces SQL-injection risk if done naively -> Enforce a strict
  repository-side whitelist and validate sort order in the service layer
- Batch delete can leave the UI on an empty page -> Recompute the current page
  after deletion and fall back to the previous valid page when needed
- Dashboard data could drift from the student page if fetched differently ->
  Use the same stats and health APIs rather than duplicating count logic
- Shared styling work could accidentally regress the existing modal workflow ->
  Keep the create/edit modal contract unchanged and verify it explicitly during
  manual acceptance
- A new shared shell can introduce layout collisions between navigation,
  content, and overlays -> keep layout ownership centralized in `base.html` and
  keep modal layering independent from the sidebar and top bar
- Text and encoding regressions can make the UI look broken even when behavior
  is correct -> keep user-visible Chinese copy readable and verify that no
  visible mojibake remains

## Migration Plan

- No database schema migration is required for this change
- Apply the repository and service enhancements before updating the REST API
- Add the Dashboard route and shared application shell before wiring the
  page-level JavaScript enhancements
- Update the student page after the API contract is in place
- Refresh README manual verification steps to match the enhanced UI

Rollback plan:

- Revert the new change as one unit if pagination, sorting, or batch deletion
  destabilize the existing CRUD workflow
- Because the schema is unchanged, rollback does not require database cleanup

## Open Questions

- No blocking product decision is currently required for implementation
- If the team later wants richer Dashboard metrics beyond total count and
  health, that should be proposed in a follow-up change rather than folded into
  this one
