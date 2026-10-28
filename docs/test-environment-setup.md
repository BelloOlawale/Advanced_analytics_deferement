# Test environment setup (new tenant)

This guide explains the **multi-environment configuration** in plain language and
walks through standing up a test build in a **separate Fabric tenant** with
generated data, before touching the customer's environment.

---

## 1. What "multi-environment configuration" means

Think of it like separate browser profiles. Each environment gets its own small
settings file, and the tool loads **exactly one** of them per run:

| File | Environment | Used for |
|---|---|---|
| `.env` | `local` | The existing NewCross prototype / local work |
| `.env.sandbox` | `sandbox` | The new test tenant |
| `.env.customer` | `customer` | The customer build (when we get there) |

You never edit one file to switch environments. You **choose a profile**:

```bash
python tools/fabric_query.py --env sandbox --test
```

or:

```bash
FABRIC_ENV=sandbox python tools/fabric_query.py --test
```

Why this matters:

- **No accidental cross-wiring.** A sandbox run cannot inherit the customer's
  server, because profiles do not layer on top of each other.
- **Separate sign-in caches.** Each profile gets its own Azure CLI cache, so a
  sandbox login cannot be silently reused for the customer tenant.
- **Secrets stay local.** All `.env*` files are git-ignored (except
  `.env.example`).

The old behaviour still works: if you pass no `--env` and set no `FABRIC_ENV`,
the tool loads `.env` exactly as before.

---

## 2. Create the sandbox profile

Copy the example and fill in the new tenant's values:

```bash
cp .env.example .env.sandbox
```

`.env.sandbox`:

```dotenv
FABRIC_SQL_SERVER=<warehouse>@<workspace>.datawarehouse.fabric.microsoft.com
FABRIC_SQL_DATABASE=<warehouse-name>
FABRIC_SQL_AUTH=default
FABRIC_SQL_TENANT=<new-tenant-id>

# Optional: leave unset to use ~/.azure-fabric/sandbox
# AZURE_CONFIG_DIR=
```

The SQL server/database can stay blank until a Warehouse exists in the new
workspace. Uploading CSVs to `lh_bronze/Files` does **not** need the SQL settings.

Then sign in to the **new tenant** once:

```bash
az login --tenant <new-tenant-id-or-domain>
```

Check what the tool will use (secrets are redacted):

```bash
python tools/fabric_query.py --env sandbox --show-env
```

Expected output:

```text
profile : sandbox
file    : .../.env.sandbox  (found)

FABRIC_ENV          : sandbox
FABRIC_SQL_SERVER   : <warehouse>@<workspace>...
FABRIC_SQL_DATABASE : <warehouse-name>
FABRIC_SQL_AUTH     : default
FABRIC_SQL_TENANT   : <new-tenant-id>
AZURE_CONFIG_DIR    : .../.azure-fabric/sandbox
```

If the file says `NOT FOUND`, the profile name and filename do not match. The
name after `--env` is the suffix after `.env.`: `--env sandbox` reads
`.env.sandbox`.

### 2.1 Find the tenant ID (the GUID)

"Wragby Business Solutions & Technology" is the **tenant name/domain**, not the
tenant ID. The ID is a GUID and is what `.env.sandbox` needs.

| Method | Steps |
|---|---|
| Entra admin center | **Microsoft Entra ID → Overview → Tenant ID** |
| Azure CLI | `az login --tenant <tenant-domain-or-id>` then `az account show --query tenantId -o tsv` |
| OpenID config | `curl -s https://login.microsoftonline.com/<tenant-domain>/v2.0/.well-known/openid-configuration` — the `issuer` contains the tenant ID |
| Fabric / Power BI | Ask a tenant admin; the ID is not shown in the workspace UI |
| Decode your own token | The Fabric access token contains the tenant ID in its `tid` claim (no domain needed) |

```bash
# after az login to the Wragby tenant
az account show --query "{tenantId:tenantId, user:user.name, tenant:tenantDefaultDomain}" -o json

# no domain? decode the tenant ID from a Fabric token
az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv \
  | python -c "import sys,base64,json; t=sys.stdin.read().strip().split('.')[1]; print(json.loads(base64.urlsafe_b64decode(t+'='*(-len(t)%4)))['tid'])"

# or via Microsoft Graph
az rest --method get --resource https://graph.microsoft.com \
  --url 'https://graph.microsoft.com/v1.0/organization?$select=id,displayName' \
  --query "value[0]" -o json
```

### 2.2 Find the workspace ID, capacity SKU and region

**Portal (simplest):**

1. Open Fabric → workspace **Maf**.
2. **Workspace settings** (gear) → **License info**. This shows whether the
   workspace is on a Fabric capacity, a trial capacity, or Pro, and the
   capacity name.
3. If you have permission, click the capacity name → capacity settings shows
   the **SKU** (e.g. F2, F16) and **region**.
4. Definitive view: **Fabric admin portal → Capacities** (requires Fabric admin).
   It lists capacity name, SKU, region, state and admins.
5. Azure portal → search **Microsoft Fabric capacities** (if you can read the
   Azure subscription that owns the capacity).

**CLI:**

```bash
# tenant + signed-in account
az login --tenant <tenant-domain-or-id>
az account show --query "{tenantId:tenantId, user:user.name}" -o json

# capacities in the current Azure subscription (name, region, SKU, state)
az resource list --resource-type Microsoft.Fabric/capacities \
  --query "[].{name:name, region:location, sku:sku.name, state:properties.state}" -o table

# workspace ID and capacity ID (Fabric REST)
TOKEN=$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)
curl -s -H "Authorization: Bearer $TOKEN" https://api.fabric.microsoft.com/v1/workspaces \
  | python -c "import sys,json; [print(w['displayName'], w['id'], w.get('capacityId')) for w in json.load(sys.stdin)['value']]"
```

`az resource list` only covers the **current subscription**. If it returns
nothing, the capacity is in another subscription or you do not have Azure read
access — ask the Fabric/capacity admin for the SKU and region.

Power BI REST alternative for the workspace → capacity mapping:

```bash
az rest --method get --resource https://analysis.windows.net/powerbi/api \
  --url "https://api.powerbi.com/v1.0/myorg/groups?\$filter=name%20eq%20'Maf'"
```

The workspace ID is also the GUID in the workspace URL:
`https://app.fabric.microsoft.com/groups/<workspace-id>/...`.

### 2.3 What the workspace Member role allows

| Fabric role | Create lakehouses / notebooks / pipelines? | Also allows |
|---|---|---|
| **Admin** | Yes | Workspace settings, members, Git integration, delete workspace |
| **Member** | **Yes** | Create/edit/delete items, share, add lower roles |
| **Contributor** | Yes | Create/edit/delete items, but cannot manage access |
| **Viewer** | No | View only |

So **Member is enough to create the build items**. Three other gates still apply:

1. **A Fabric capacity** must be assigned to the workspace. A Pro-only workspace
   cannot host lakehouses/notebooks/pipelines.
2. The tenant setting **"Users can create Fabric items"** must allow your account
   or security group (a Fabric admin can restrict this).
3. Your **license** must permit it. A Fabric (free) license is normally enough
   when the workspace is on Fabric capacity; some Power BI items may still
   require Pro.

Git integration and workspace settings may require **Admin**, even though
creating items only needs Member.

> I do not have my own Fabric identity. Commands run on your machine and use
> **your** `az login` / portal session, so your Member role is what we rely on.

---

## 3. Generate the raw test data

The new tenant has no source warehouse yet, so we seed from the extracts already
in `data/` (they are git-ignored and stay local).

```bash
# Last 180 days from the real extracts, station/well names anonymised
python tools/generate_test_data.py --env sandbox --days 180 --anonymise
```

Output:

```text
test_data/sandbox/
├── raw/
│   ├── production_fact.csv
│   ├── deferment_fact.csv
│   ├── flowstations_dim.csv
│   ├── deferment_category_dim.csv
│   └── deferment_subcategory_dim.csv
├── ref/
│   ├── dim_date.csv
│   ├── dim_asset.csv
│   ├── dim_station.csv
│   ├── dim_well.csv
│   ├── oil_prices.csv
│   └── owner_map.csv
├── _manifest.json
└── README.md
```

Useful options:

| Option | Meaning |
|---|---|
| `--days N` | How many trailing days to include (default 180) |
| `--source seed` | Slice the existing extracts |
| `--source synthetic` | Generate from scratch (no extracts needed) |
| `--source auto` | Seed if all extracts exist, otherwise synthetic (default) |
| `--anonymise` | Rename stations/wells/assets to `Test Station A`, `TST...` |
| `--seed N` | Reproducible randomness for synthetic mode |
| `--end YYYY-MM-DD` | Last date in the set |
| `--force` | Overwrite the output folder |

If the extracts are missing, the tool falls back to **synthetic** data with the
same schema, realistic ranges, and injected precursor declines before coded
failures — so the early-warning logic still has something to detect.

`test_data/` is git-ignored. Do not commit it.

---

## 4. Load the data into the new tenant

These steps happen in the Fabric portal (or with the Fabric REST API if the
identity has rights):

1. Create or confirm the workspace (e.g. `deferment-ew-sandbox`) and assign it
   to a capacity.
2. Create the lakehouses: `lh_bronze`, `lh_silver`, `lh_gold`.
3. Open `lh_bronze` → **Files** → create `raw/` and `ref/`.
4. Upload:
   - everything in `test_data/sandbox/raw/` → `Files/raw/`
   - everything in `test_data/sandbox/ref/` → `Files/ref/`

The bronze notebook then reads:

```text
Files/raw/production_fact.csv
Files/raw/deferment_fact.csv
Files/raw/flowstations_dim.csv
Files/raw/deferment_category_dim.csv
Files/raw/deferment_subcategory_dim.csv
Files/ref/dim_date.csv
Files/ref/dim_station.csv
...
```

---

## 5. Verify connectivity (once a warehouse exists)

```bash
python tools/fabric_query.py --env sandbox --test
python tools/fabric_query.py --env sandbox --info
```

`--test` runs `SELECT 1`; `--info` lists tables and columns. Both are read-only.
Every query is appended to `logs/fabric_queries.log` with a timestamp.

> **Note:** reading a **Warehouse** and reading **lakehouse Files** are two
> different access paths. Uploading CSVs to `lh_bronze/Files` needs the
> workspace/lakehouse role, not a SQL connection string. The `.env.sandbox`
> SQL settings only apply once a Warehouse exists in the new tenant.

---

## 6. Switching environments safely

```bash
# New test tenant
python tools/fabric_query.py --env sandbox --show-env
python tools/fabric_query.py --env sandbox --test

# Existing NewCross environment (unchanged)
python tools/fabric_query.py --env local --show-env
python tools/fabric_query.py --env local --test
```

Always run `--show-env` first when you are unsure which target is live. The
server and tenant are printed; passwords and connection strings are redacted.

---

## 7. What is still needed from the new tenant

The generator and profile handle the data and the local side. To create the
Fabric items in the new tenant, we still need:

1. **Tenant ID (GUID)** — not just the tenant display name.
2. **Workspace name** (confirmed: `Maf`) and its **workspace ID** (the GUID in
   the workspace URL / workspace settings).
3. **Capacity SKU and region** — confirmed: `mafcapacity`, **F2**, **North
   Europe** (capacity ID `F874D5A0-467B-493C-AA43-EF099DE4C979`).
4. **Role confirmation** — Member is sufficient for creating items, subject to
   the capacity and tenant-setting gates in §2.3. If we need Git integration or
   workspace settings, we need Admin.
5. Confirmation of the **upload path** (`lh_bronze/Files/raw` and `ref`), or
   permission for me to create it.

> **F2 note:** F2 is the smallest Fabric SKU (2 capacity units). It is fine for
> creating items and a small test build, but Spark notebooks may be slow or
> throttled. Schedule the run off-peak, keep the test window short (e.g. 60–180
> days), and ask for a temporary F4/F8 only if we hit capacity limits.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `file ... (NOT FOUND)` | Profile suffix mismatch | `--env sandbox` must match `.env.sandbox` |
| `Missing config for profile 'sandbox'` | File exists but server/database are blank | Fill both values, or use the data-only path |
| `Refused: only SELECT / WITH allowed` | The tool is read-only by design | Use a SELECT; DDL/DML is blocked |
| Login opens the wrong tenant | Stale token cache | `az login --tenant <id>` with the profile's `AZURE_CONFIG_DIR` |
| `No complete extract set found` | `data/` is missing CSVs | Use `--source synthetic`, or restore the extracts |
| CSV upload joins fail | Blank category/subcategory IDs exist in the real extract | Map blanks to an `Unknown` member in silver |
| Workspace shows no capacity | Workspace is Pro-only or trial expired | Assign a Fabric capacity; Member role alone cannot enable items |
| Cannot create a lakehouse despite Member | Tenant setting restricts Fabric item creation | Ask a Fabric admin to allow your group |

---

## 9. Guardrails

- **Read-only** on every source; the query tool refuses anything but `SELECT`/`WITH`.
- **Missing is not zero**; blanks in the seed data stay blank on purpose.
- **`test_data/` is git-ignored**; client-derived values never enter the repo.
- **One profile per run**; no cross-environment inheritance.
- **Secrets never in chat or code**; use `.env.<profile>` or Key Vault.
