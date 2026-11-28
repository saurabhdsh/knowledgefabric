-- Weave demo: Cost-of-Care Claims warehouse (Unity Catalog)
-- Catalog/schema: workspace.claims_demo
-- Run in Databricks SQL Editor with Starter Warehouse, OR via seed script.

CREATE SCHEMA IF NOT EXISTS workspace.claims_demo
COMMENT 'Weave Knowledge Fabric demo — healthcare claims with measured FK relationships';

-- --------------------------------------------------------------------------
-- Dimension tables
-- --------------------------------------------------------------------------

CREATE OR REPLACE TABLE workspace.claims_demo.members (
  member_id        STRING NOT NULL,
  member_number    STRING NOT NULL,
  first_name       STRING NOT NULL,
  last_name        STRING NOT NULL,
  date_of_birth    DATE NOT NULL,
  gender           STRING,
  email            STRING,
  phone            STRING,
  state            STRING,
  zip_code         STRING,
  plan_id          STRING NOT NULL,
  enrollment_date  DATE,
  status           STRING,
  risk_score       DOUBLE
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.plans (
  plan_id          STRING NOT NULL,
  plan_name        STRING NOT NULL,
  plan_type        STRING NOT NULL,
  carrier          STRING NOT NULL,
  network_tier     STRING,
  deductible       DECIMAL(12,2),
  oop_max          DECIMAL(12,2),
  effective_from   DATE,
  effective_to     DATE
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.providers (
  provider_id      STRING NOT NULL,
  npi              STRING NOT NULL,
  provider_name    STRING NOT NULL,
  specialty        STRING,
  provider_type    STRING,
  city             STRING,
  state            STRING,
  tin              STRING,
  network_status   STRING
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.diagnosis_codes (
  diagnosis_code   STRING NOT NULL,
  short_desc       STRING NOT NULL,
  category         STRING,
  chronic_flag     BOOLEAN
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.procedure_codes (
  procedure_code   STRING NOT NULL,
  short_desc       STRING NOT NULL,
  category         STRING,
  avg_allowed      DECIMAL(12,2)
) USING DELTA;

-- --------------------------------------------------------------------------
-- Fact tables
-- --------------------------------------------------------------------------

CREATE OR REPLACE TABLE workspace.claims_demo.claims (
  claim_id           STRING NOT NULL,
  claim_number       STRING NOT NULL,
  member_id          STRING NOT NULL,
  provider_id        STRING NOT NULL,
  plan_id            STRING NOT NULL,
  primary_diagnosis  STRING,
  service_from       DATE NOT NULL,
  service_to         DATE,
  received_date      DATE,
  claim_status       STRING NOT NULL,
  claim_type         STRING,
  place_of_service   STRING,
  billed_amount      DECIMAL(12,2),
  allowed_amount     DECIMAL(12,2),
  paid_amount        DECIMAL(12,2),
  member_responsibility DECIMAL(12,2),
  denial_reason      STRING
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.claim_lines (
  claim_line_id      STRING NOT NULL,
  claim_id           STRING NOT NULL,
  line_number        INT NOT NULL,
  procedure_code     STRING NOT NULL,
  diagnosis_code     STRING,
  service_date       DATE,
  units              INT,
  billed_amount      DECIMAL(12,2),
  allowed_amount     DECIMAL(12,2),
  paid_amount        DECIMAL(12,2),
  line_status        STRING
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.payments (
  payment_id         STRING NOT NULL,
  claim_id           STRING NOT NULL,
  payment_date       DATE NOT NULL,
  payment_method     STRING,
  check_eft_number   STRING,
  paid_amount        DECIMAL(12,2),
  payee_provider_id  STRING
) USING DELTA;

CREATE OR REPLACE TABLE workspace.claims_demo.claim_events (
  event_id           STRING NOT NULL,
  claim_id           STRING NOT NULL,
  event_ts           TIMESTAMP NOT NULL,
  event_type         STRING NOT NULL,
  actor              STRING,
  notes              STRING
) USING DELTA;
