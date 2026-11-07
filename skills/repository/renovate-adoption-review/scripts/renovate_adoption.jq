# Reusable jq defs for the renovate-adoption-review helper.

def normalize_url:
  sub("^https://redirect\\.github\\.com/"; "https://github.com/");

def trim: sub("^\\s+"; "") | sub("\\s+$"; "");

# Leading numeric components of a version string, stopping at the first
# non-numeric one ("21-jdk-alpine" -> [21], "4.7.0" -> [4,7,0]).
def numprefix:
  [splits("[.-]")] as $p
  | (first(range(0; $p | length) | select($p[.] | test("^[0-9]+$") | not))
     // ($p | length)) as $n
  | $p[:$n] | map(tonumber);

def classify($from; $to):
  ($from // "" | sub("^v"; "")) as $f
  | ($to // "" | sub("^v"; "")) as $t
  | if ($f | test("^(?=.*[a-f])[0-9a-f]{7,40}$")) and ($t | test("^(?=.*[a-f])[0-9a-f]{7,40}$")) then "digest"
    else
      ($f | numprefix) as $a
      | ($t | numprefix) as $b
      | if ($a | length) == 0 or ($b | length) == 0 then "unknown"
        elif ($a | length) < ($b | length) and $b[:($a | length)] == $a then "pin"
        else
          (first(range(0; [($a | length), ($b | length)] | min)
                 | select($a[.] != $b[.])) // null) as $i
          | if $i == null then "unknown"
            elif $i == 0 then "major"
            elif $i == 1 then (if $a[0] == 0 then "major" else "minor" end)
            else "patch"
            end
        end
    end;

def split_row:
  split("|") | .[1:] | if length > 0 and (.[-1] | trim) == "" then .[:-1] else . end
  | map(trim);

# Renovate's own Update column value -> updateType, or null when unknown.
def renovate_type:
  if . == "pinDigest" then "pin"
  elif . == "major" or . == "minor" or . == "patch" or . == "digest" or . == "pin"
       or . == "lockFileMaintenance" or . == "rollback" or . == "replacement" or . == "bump"
  then .
  else null end;

# Markdown body string -> [{package, sourceUrl, from, to, updateType, renovateType}]
# renovateType is internal (null without a usable Update column); parse_updates strips it.
def parse_updates_raw:
  split("\n") as $lines
  | (first(range(0; $lines | length) | select($lines[.] | startswith("| Package |"))) // null) as $h
  | if $h == null then []
    else
      ($lines[$h] | split_row) as $head
      | (first(range(0; $head | length) | select($head[.] == "Change")) // 1) as $ci
      | (first(range(0; $head | length) | select($head[.] == "Update")) // null) as $ui
      | $lines[($h + 2):] as $rows
      | (first(range(0; $rows | length) | select($rows[.] | startswith("|") | not))
         // ($rows | length)) as $n
      | $rows[:$n]
      | map(split_row
            | (.[0] | capture("\\[(?<name>[^\\]]+)\\]\\((?<url>[^)]+)\\)")? ) as $link
            | (if $ui == null then null else .[$ui] | renovate_type end) as $rt
            | (.[$ci] | split("→")) as $sides
            | ([$sides[] | [scan("`([^`]+)`") | .[0]] | .[0]]) as $ver
            | { package: ($link.name // .[0]),
                sourceUrl: ($link.url // null | if . == null then null else normalize_url end),
                from: $ver[0],
                to: $ver[1],
                renovateType: $rt }
            | .updateType = (.renovateType // classify(.from; .to)))
    end;

def parse_updates: parse_updates_raw | map(del(.renovateType));

# Keep the release-note URLs under this update's own repository; all of them
# when the update has no sourceUrl or none matches.
def urls_for($urls):
  if .sourceUrl == null then $urls
  else
    (.sourceUrl | rtrimstr("/") | ascii_downcase) as $base
    | [$urls[] | select(ascii_downcase | startswith($base + "/"))] as $own
    | if ($own | length) > 0 then $own else $urls end
  end;

def release_notes_urls:
  [ match("https://(?:redirect\\.)?github\\.com/[^/\\s)>\\]]+/[^/\\s)>\\]]+/(?:releases/tag|compare)/[^\\s)>\\]]+"; "g").string
    | normalize_url ]
  | unique;

def repo_key: ascii_downcase | sub("/+$"; "") | sub("\\.git$"; "") | sub("/+$"; "");

# True when the update's source is the consumer repository itself.
def is_self($self):
  .sourceUrl != null and ($self | repo_key) != "" and (.sourceUrl | repo_key) == ($self | repo_key);

# One update -> {verdict, reason}
def triage($mode; $allow; $self):
  if is_self($self) then
    {verdict: "skip", reason: "self dependency"}
  elif (.package as $p | $allow | index($p)) != null then
    {verdict: "candidate", reason: "allowlisted"}
  elif $mode == "retro" and (.updateType == "major" or .updateType == "minor") then
    {verdict: "candidate", reason: "\(.updateType) update"}
  elif $mode == "open" and .updateType == "major" then
    {verdict: "candidate", reason: "major update"}
  else
    {verdict: "skip", reason: "\(.updateType) not reviewed in \($mode) mode"}
  end;

# gh pr view JSON -> inspect item
def inspect_item($mode; $allow; $self):
  . as $pr
  | ($pr.body // "") as $body
  | ( if ($pr.title // "") | test("lock file maintenance"; "i") then
        [{package: "lock file maintenance", sourceUrl: null, from: null, to: null,
          updateType: "lockFileMaintenance"}]
      else ($body | parse_updates) end
    ) as $updates
  | ($updates | map(. + triage($mode; $allow; $self))) as $t
  | ($t | map(select(.verdict == "candidate"))) as $cand
  | ($body | release_notes_urls) as $urls
  | { pr: $pr.number, branch: $pr.headRefName, headSha: $pr.headRefOid,
      updates: ($updates | map(. + {releaseNotesUrls: urls_for($urls)})),
      verdict: (if ($cand | length) > 0 then "candidate" else "skip" end),
      reason: (if ($t | length) == 0 then "no updates table"
               elif ($cand | length) > 0 then ($cand | map(.reason) | unique | join("; "))
               else ($t | map(.reason) | unique | join("; ")) end) };

# gh pr list JSON (merged) -> [{pr, mergedAt, updates}]
def pr_updates:
  map(. as $p
      | ($p.body // "") as $b
      | ($b | release_notes_urls) as $urls
      | { pr: $p.number, mergedAt: $p.mergedAt,
          updates: ($b | parse_updates_raw | map(. + {releaseNotesUrls: urls_for($urls)})) });

# [{pr, mergedAt, updates}] -> [retro item] without verdict
def aggregate:
  sort_by(.mergedAt)
  | map(. as $p | .updates[] | . + {pr: $p.pr})
  | group_by([.package, .sourceUrl])
  | map(. as $g
        | ([$g[] | select(.updateType != "digest" and .updateType != "pin")]) as $v
        | { package: $g[0].package,
            sourceUrl: ($g | map(.sourceUrl) | map(select(. != null)) | first // null),
            from: (if ($v | length) > 0 then $v[0].from else $g[0].from end),
            to: (if ($v | length) > 0 then $v[-1].to else $g[-1].to end),
            prs: ($g | map(.pr) | unique),
            releaseNotesUrls: ($g | map(.releaseNotesUrls) | add | unique) }
        | .updateType = (($g | map(.renovateType) | unique) as $rt
                         | if ($rt | length) == 1 and $rt[0] != null then $rt[0]
                           else classify(.from; .to) end))
  | map({package, sourceUrl, from, to, updateType, prs, releaseNotesUrls});

def retro_items($allow; $self):
  pr_updates | aggregate | map(. + triage("retro"; $allow; $self));

# Top-level scalar value of a YAML key in a copier file/answers text, or null.
def yaml_scalar($key):
  split("\n") | map(select(startswith($key + ":"))) | first // null
  | if . == null then null
    else sub("^[^:]+:\\s*"; "") | sub("\\s+#.*$"; "") | sub("^[\"']"; "") | sub("[\"']\\s*$"; "")
    end;

# Render the subset of Jinja used by copier _subdirectory: `{{ var }}` and a
# single `{% if var == 'x' %}A{% else %}B{% endif %}`. Anything left over is
# unresolvable and yields null.
def render_subdir($vars):
  gsub("\\{%\\s*if\\s+(?<a>\\w+)\\s*==\\s*'(?<b>[^']*)'\\s*%\\}(?<t>.*?)\\{%\\s*else\\s*%\\}(?<e>.*?)\\{%\\s*endif\\s*%\\}";
       . as $c | if ($vars | has($c.a)) then (if $vars[$c.a] == $c.b then $c.t else $c.e end) else "{%?" end)
  | gsub("\\{\\{\\s*(?<n>\\w+)\\s*\\}\\}"; . as $c | if ($vars | has($c.n)) then $vars[$c.n] else "{{?" end)
  | if test("\\{[{%]") then null else . end;

def strip_suffix($suffix):
  if $suffix != "" and endswith($suffix) then .[: (length - ($suffix | length))] else . end;

# Input: git tree response. Args: copier.yml text, answers-file text.
# Output: {paths, warn}; paths are consumer-relative.
def owned_for($copier; $answers):
  ($copier | yaml_scalar("_templates_suffix") // ".jinja") as $suffix
  | ($copier | yaml_scalar("_subdirectory")) as $raw
  | ([$answers | split("\n")[] | capture("^(?<k>[A-Za-z_][A-Za-z0-9_]*):[ \\t]+(?<v>.*)$")?
      | {(.k): (.v | sub("\\s+#.*$"; "") | sub("^[\"']"; "") | sub("[\"']\\s*$"; ""))}] | add // {}) as $vars
  | [.tree[]? | select(.type == "blob") | .path] as $blobs
  | [$blobs[] | select(. != "copier.yml") | strip_suffix($suffix)] as $whole
  | if $raw == null then {paths: $whole, warn: null}
    else
      (if $raw | test("^[>|][-+0-9]*$") then null else $raw | render_subdir($vars) end
       | if . == null then null
         else sub("^(\\./)+"; "") | sub("/+$"; "") | if . == "." then "" else . end end) as $dir
      | if $dir == null then {paths: $whole, warn: "unresolvable _subdirectory: \($raw)"}
        elif $dir == "" then {paths: $whole, warn: null}
        else
          [$blobs[] | select(startswith($dir + "/")) | .[($dir | length) + 1:] | strip_suffix($suffix)] as $own
          | if ($own | length) == 0 then {paths: $whole, warn: "_subdirectory \($raw) matches no files"}
            else {paths: $own, warn: null}
            end
        end
    end;
