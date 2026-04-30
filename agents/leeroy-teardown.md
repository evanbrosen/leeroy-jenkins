---
name: leeroy-teardown
description: Teardown skill for leeroy-jenkins demo data. Deletes all Salesforce records for a given customer slug from the target org, in reverse dependency order. Use this to clean up after a demo or before re-running leeroy-jenkins for the same customer.
---

# Skill: /leeroy-teardown

You are cleaning up a Salesforce demo org by deleting records that were created by `/leeroy-jenkins` for a specific customer. Work carefully — deletions are permanent.

---

## Step 1 — Identify What to Delete

Ask the user:

1. **Customer slug**: "Which customer slug do you want to tear down? (e.g. `xometry`, `acme-corp`)"
2. **Target org**: Run `sf org list --json` and show authenticated orgs. Ask which one to target.

Then locate the ID file:
```bash
ls /tmp/ids_<slug>.json
```

If the file exists, read it. If it doesn't exist, ask the user:
> "I can't find `/tmp/ids_<slug>.json`. Do you have an alternate path to the IDs file, or would you like me to query the org directly for Accounts matching this customer's names?"

If querying directly, ask the user to provide the 5 account names and search:
```bash
sf data query \
  --query "SELECT Id, Name FROM Account WHERE Name IN ('Name1','Name2',...)" \
  --target-org <alias> --json
```

---

## Step 2 — Show What Will Be Deleted

Before deleting anything, show the SE a summary table of what will be removed:

| Object | Count | IDs |
|---|---|---|
| Tasks | N | (list) |
| Cases | N | (list) |
| Orders | N | (list) |
| OpportunityLineItems | N | (list) |
| Opportunities | N | (list) |
| Contracts | N | (list) |
| Contacts | N | (list) |
| Accounts | N | (list) |

Ask: "This will permanently delete these records from `<org alias>`. Proceed? (y/n)"

If the user says no, stop.

---

## Step 3 — Delete Records (Reverse Dependency Order)

Delete in this exact order — children before parents:

### 1. Tasks
```bash
sf data delete record --sobject Task --record-id <id> --target-org <alias> --json
```

### 2. Cases
```bash
sf data delete record --sobject Case --record-id <id> --target-org <alias> --json
```

### 3. Orders
```bash
# First deactivate (set Status back to Draft), then delete
sf data update record --sobject Order --record-id <id> \
  --values "Status='Draft'" --target-org <alias> --json
sf data delete record --sobject Order --record-id <id> --target-org <alias> --json
```

### 4. OpportunityLineItems
```bash
sf data delete record --sobject OpportunityLineItem --record-id <id> --target-org <alias> --json
```

### 5. Opportunities
```bash
sf data delete record --sobject Opportunity --record-id <id> --target-org <alias> --json
```

### 6. Contracts
```bash
# Contracts must be deactivated before deletion
sf data update record --sobject Contract --record-id <id> \
  --values "Status='Draft'" --target-org <alias> --json
sf data delete record --sobject Contract --record-id <id> --target-org <alias> --json
```

### 7. Contacts
```bash
sf data delete record --sobject Contact --record-id <id> --target-org <alias> --json
```

### 8. Accounts
```bash
sf data delete record --sobject Account --record-id <id> --target-org <alias> --json
```

For each deletion, log success or failure. If a record fails to delete (e.g. it was already deleted, or there's a dependency you didn't account for), log the error and continue — do not abort.

---

## Step 4 — Clean Up Local Files (Optional)

After deletions are complete, ask:
> "Do you also want to delete the local output files at `~/claude-projects/leeroy-jenkins/customers/<slug>/`? (y/n)"

If yes:
```bash
rm -rf ~/claude-projects/leeroy-jenkins/customers/<slug>
rm -f /tmp/ids_<slug>.json
rm -f /tmp/dataplan_<slug>.json
```

---

## Step 5 — Confirm

Report:
1. Total records deleted (by object type)
2. Any records that failed to delete (with error messages)
3. Whether local files were removed
4. The org is now clean for a fresh `/leeroy-jenkins` run for this customer
