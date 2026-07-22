## Why

The current student-management application already supports basic CRUD, but it
is still difficult to use as a real management interface once the dataset grows.
The app needs a true Dashboard at `/`, shared navigation, and list-management
enhancements so users can browse, sort, select, and delete student records
efficiently without leaving the approved Flask architecture.

## What Changes

- Add a server-rendered Dashboard at `/` instead of returning a JSON 404 or only
  redirecting to `/students`
- Extend the shared template layout so the Dashboard and student page use the
  same navigation, spacing, visual language, and active-page state
- Add repository, service, and API support for `count_students` and
  `GET /api/students/stats`
- Extend `GET /api/students` with keyword-aware pagination and safe whitelist
  sorting
- Add current-page row selection, select-all behavior, and batch deletion
  through one API request
- Update the student-management page to show pagination controls, sortable
  headers, matching-record totals, and batch-delete controls while preserving
  the existing create/edit modal workflow
- Update README guidance for the new manual verification flow

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `student-data-management`: extend student list, stats, sorting, pagination,
  and batch-delete behavior across repository, service, and REST API layers
- `student-management-ui`: add the Dashboard, shared navigation, consistent
  styling, pagination controls, sortable headers, current-page selection, and
  batch-delete UI behavior

## Impact

- Affected code: `app/routes/pages.py`, `app/routes/students.py`,
  `app/repositories/student_repository.py`, `app/services/student_service.py`,
  `app/templates/base.html`, `app/templates/dashboard.html`,
  `app/templates/students.html`, `app/static/css/style.css`,
  `app/static/js/dashboard.js`, `app/static/js/students.js`, `README.md`
- Affected routes: `GET /`, `GET /students`, `GET /api/students`,
  `GET /api/students/stats`, `POST /api/students/batch-delete`
- Dependencies: no new third-party dependency is expected
- Systems: browser UI, Flask REST API, StudentService, StudentRepository, SQLite
