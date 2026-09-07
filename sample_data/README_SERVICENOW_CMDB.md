# ServiceNow + CMDB sample for Weave (5,000 rows)

File: [`servicenow_cmdb_itsm_5000.csv`](./servicenow_cmdb_itsm_5000.csv)

Regenerate:

```bash
python3 sample_data/generate_servicenow_cmdb_csv.py
```

## What is in the CSV

One denormalized ITSM + CMDB table (5,000 incident rows) with:

- **Incident** fields (`incident_number`, priority, state, category, SLA, …)
- **Caller / user** fields
- **Assignment group** fields
- **CMDB CI** fields (class, environment, owner, support group, parent/depends-on)
- **Business service** fields (tier, criticality)
- **Problem / change** links
- **`business_rule_text`** phrases (`must` / `should` / `cannot`) for Ontology rule discovery
- **`relationship_summary`** for Knowledge Graph / relational chunking

## Create a fabric in Weave

1. Open **Knowledge** → create fabric → **Database**
2. Choose **CSV upload** mode
3. Upload `servicenow_cmdb_itsm_5000.csv`
4. Profile tip: use `postgresql` or leave default DB profile (tabular)
5. Create fabric (optionally train)
6. Open **Knowledge Graph**, then run **Ontology discovery** and review **business rules**

Suggested weave domain / tags: ITSM, ServiceNow, CMDB.
