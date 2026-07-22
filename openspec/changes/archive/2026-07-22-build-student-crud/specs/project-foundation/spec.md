## MODIFIED Requirements

### Requirement: Configuration boundaries
The system SHALL define `DevelopmentConfig`, `TestingConfig`, and `ProductionConfig`, all inheriting from a base `Config` class, and SHALL expose centralized configuration values needed by approved database-backed capabilities, including `DATABASE_PATH`.

#### Scenario: Development configuration
- **WHEN** DevelopmentConfig is used
- **THEN** `DEBUG` SHALL be `True`

#### Scenario: Testing configuration
- **WHEN** TestingConfig is used
- **THEN** `TESTING` SHALL be `True`

#### Scenario: Production SECRET_KEY validation
- **WHEN** ProductionConfig is used
- **THEN** the system SHALL raise a `RuntimeError` on startup if `SECRET_KEY` is missing or still set to a development default

#### Scenario: CRUD database path is centralized
- **WHEN** the application is created for the student CRUD capability
- **THEN** `DATABASE_PATH` SHALL be available through centralized application configuration
- **AND** Development configuration SHALL default `DATABASE_PATH` to `<Flask instance path>/students_v2.db`
- **AND** a relative configured `DATABASE_PATH` SHALL resolve consistently against the project root

#### Scenario: Production requires explicit database path
- **WHEN** ProductionConfig is used for the student CRUD capability
- **THEN** the system SHALL require an explicitly configured `DATABASE_PATH`
- **AND** it SHALL NOT create database files or parent directories during module import or application creation

### Requirement: CLI registration
The system SHALL provide centralized CLI registration so explicit maintenance commands can be attached to the Flask application.

#### Scenario: Database initialization command is registered
- **WHEN** the application starts for the student CRUD capability
- **THEN** it SHALL register a Flask CLI command named `init-db`
- **AND** the command SHALL be invokable through `flask --app run.py init-db`

#### Scenario: init-db is non-destructive
- **WHEN** `flask --app run.py init-db` is executed
- **THEN** the command MAY create the configured database parent directory and missing tables
- **AND** it SHALL NOT delete existing tables
- **AND** it SHALL NOT erase existing records

### Requirement: Blueprint registration
The system SHALL provide a `register_blueprints(app)` function that registers application Blueprints through a centralized integration point.

#### Scenario: Health blueprint registered
- **WHEN** the application starts
- **THEN** the health check Blueprint SHALL be registered through `register_blueprints()`

#### Scenario: Student blueprints registered
- **WHEN** the student CRUD capability is enabled
- **THEN** the student API Blueprint and the student page Blueprint SHALL be registered through `register_blueprints()`

#### Scenario: Blueprint registration avoids circular imports
- **WHEN** route modules are imported for registration
- **THEN** the registration structure SHALL avoid circular import failures

### Requirement: Foundation documentation
The system SHALL update `README.md` and `.env.example` to document manual setup and manual verification for approved runtime capabilities.

#### Scenario: README contains manual install instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL include user-facing dependency installation commands

#### Scenario: README contains startup instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL include instructions for starting the application with `python run.py`

#### Scenario: README contains database initialization instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL describe the manual `flask --app run.py init-db` command required to initialize the SQLite database for student CRUD

#### Scenario: README contains CRUD verification instructions
- **WHEN** `README.md` is read
- **THEN** it SHALL describe how to verify student list, search, create, edit, and delete behavior manually

#### Scenario: Documentation states no extra installation is required
- **WHEN** `README.md` is read for this change
- **THEN** it SHALL state that SQLite is part of Python
- **AND** it SHALL state that no additional package installation is required for this change
- **AND** it SHALL state that if an unexpected dependency is discovered, implementation must stop and report it

#### Scenario: .env.example contains placeholder values
- **WHEN** `.env.example` is read
- **THEN** it SHALL document recognized environment variables using placeholder values only
