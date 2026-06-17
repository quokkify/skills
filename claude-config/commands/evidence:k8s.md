Extends `/evidence` with K8s-specific investigation steps for cube review/staging environments.

You **MUST** follow `~/.claude/rules/common/investigation-discipline.md` strictly.
All base rules from `/evidence` apply. This command adds the K8s layer on top.

**Failure context:**
$ARGUMENTS

---

## Pre-flight — get the test actually running in K8s

Clear infrastructure blockers before investigating the real failure:

```bash
# 1. Identify the namespace (review env name)
kubectl get namespaces | grep <env-name>

# 2. Fetch DB credentials from K8s secret
kubectl get secret <secret-name> -n <ns> -o jsonpath='{.data.DB_URL}' | base64 -d

# 3. Start port-forward for PostgreSQL (if needed by test)
kubectl port-forward -n <ns> <postgres-pod> 5432:5432 &

# 4. Verify the right pods are running
kubectl get pods -n <ns>
```

Only move to Step 1 once the test runs end-to-end and produces a **real** failure, not an infra error.
Common infra errors to clear first:
- `java.sql.SQLException: No suitable driver` → DB env vars not set
- `java.net.ConnectException: Connection refused` → port-forward not running
- `LoadError: cannot load such file` → wrong working directory in exec

---

## Step 1 — Fetch the actual logs (K8s)

```bash
# Service pod logs (tail + follow)
kubectl logs -n <ns> <pod-name> --tail=200

# All pods of a deployment
kubectl logs -n <ns> -l app=<label> --tail=100

# Previous crashed container
kubectl logs -n <ns> <pod> --previous

# Exec into pod for interactive inspection
kubectl exec -n <ns> <pod> -- bash
```

For Sidekiq/worker services: check worker pod logs, not API pod logs.

---

## Step 2.5 — Map the full data path

Before reading any code, draw the chain. Example for segmentor:
```
Java test
  → Casino API (/api/v1/admin/filters.json)
    → Kafka (filters topic) → FiltersConsumer → StringifyFilter → Segment.filters in MongoDB
  → Kafka (events.user.limits) → UserLimitsConsumer → User.acl in MongoDB
  → RecalculateSegmentWorker → MongoQuery → MongoDB $elemMatch query
    → result: user_ids → GroupAssignment
```

**Before querying MongoDB:** verify field names from the Mongoid model definition:
```bash
kubectl exec -n <ns> <pod> -- grep -n "field :" /segmentor/app/models/model_fields/user_fields.rb
# e.g.: field :acl, as: :account_limits   ← correct
#        field :al,  as: :access_limits    ← completely different!
```

---

## Step 3 — Reproduce directly in the pod

For data-layer bugs, run a minimal reproduction inside the service pod:

```bash
kubectl exec -n <ns> <pod> -- ruby -e "
  require '/segmentor/config/environment'

  client = Mongoid.client(:default)
  col = client[:repro_test]
  col.drop

  col.insert_one({ 'threshold' => 100 })

  # Test the actual query used by the broken code:
  puts col.find({ 'threshold' => { '\$gte' => '0' } }).count   # string → expect 0 (bug)
  puts col.find({ 'threshold' => { '\$gte' => 0   } }).count   # integer → expect 1 (correct)

  col.drop
"
```

**Shell escaping rule:** `$` in MongoDB operators MUST be escaped as `\$` inside double-quoted
shell strings, or use a heredoc with `'EOF'` (single-quoted, no interpolation):

```bash
# Safe pattern — single-quoted heredoc, no $ escaping needed
kubectl exec -n <ns> <pod> -- ruby -e "$(cat <<'RUBY'
  require '/segmentor/config/environment'
  col = Mongoid.client(:default)[:test]
  puts col.find({ 'x' => { '$gte' => 0 } }).count
RUBY
)"
```

---

## Step 4 — Standard VERIFIED / HYPOTHESIZED format

(Same as base `/evidence` — see that command.)

---

## K8s-specific regression check

When checking what changed between "was working" and "now" in a K8s service:

```bash
# Check if a new image was deployed (look at deployment history)
kubectl rollout history deployment/<name> -n <ns>

# Check which git commit is running
kubectl exec -n <ns> <pod> -- cat /segmentor/REVISION 2>/dev/null || \
  kubectl exec -n <ns> <pod> -- env | grep VERSION

# Then check that commit's Gemfile.lock for dependency changes
git show <commit>:Gemfile.lock | grep "mongoid\|rails\|mongo "
```

---

## Past K8s incidents

- **PAQA-4942667 (account_limit filter):** `StringifyFilter` + Mongoid 8→9 upgrade.
  Reproduced with `ruby -e` directly in segmentor pod. MongoDB 6.0.6: `{$gte: "0"}` (String)
  never matches integer threshold. Fix: `to_numeric(val)` in `MongoQuery#build_threshold_condition`.
  Breaking commit: `bc392ba37` [CASINO-46727], 2026-03-12.
