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
  | if ($f | test("^[0-9a-f]{7,40}$")) and ($t | test("^[0-9a-f]{7,40}$")) then "digest"
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

# Markdown body string -> [{package, sourceUrl, from, to, updateType}]
def parse_updates:
  split("\n") as $lines
  | (first(range(0; $lines | length) | select($lines[.] | startswith("| Package |"))) // null) as $h
  | if $h == null then []
    else
      ($lines[$h] | split_row) as $head
      | (first(range(0; $head | length) | select($head[.] == "Change")) // 1) as $ci
      | $lines[($h + 2):] as $rows
      | (first(range(0; $rows | length) | select($rows[.] | startswith("|") | not))
         // ($rows | length)) as $n
      | $rows[:$n]
      | map(split_row
            | (.[0] | capture("\\[(?<name>[^\\]]+)\\]\\((?<url>[^)]+)\\)")? ) as $link
            | ([.[$ci] | scan("`([^`]+)`") | .[0]]) as $ver
            | { package: ($link.name // .[0]),
                sourceUrl: ($link.url // null | if . == null then null else normalize_url end),
                from: ($ver[0] // null),
                to: ($ver[1] // null) }
            | .updateType = classify(.from; .to))
    end;

def release_notes_urls:
  [ match("https://(?:redirect\\.)?github\\.com/[^/\\s)>\\]]+/[^/\\s)>\\]]+/(?:releases/tag|compare)/[^\\s)>\\]]+"; "g").string
    | normalize_url ]
  | unique;

# One update -> {verdict, reason}
def triage($mode; $allow):
  if (.package as $p | $allow | index($p)) != null then
    {verdict: "candidate", reason: "allowlisted"}
  elif $mode == "retro" and (.updateType == "major" or .updateType == "minor") then
    {verdict: "candidate", reason: "\(.updateType) update"}
  elif $mode == "open" and .updateType == "major" then
    {verdict: "candidate", reason: "major update"}
  else
    {verdict: "skip", reason: "\(.updateType) not reviewed in \($mode) mode"}
  end;

# gh pr view JSON -> inspect item
def inspect_item($mode; $allow):
  . as $pr
  | ($pr.body // "") as $body
  | ( if ($pr.title // "") | test("lock file maintenance"; "i") then
        [{package: "lock file maintenance", sourceUrl: null, from: null, to: null,
          updateType: "lockFileMaintenance"}]
      else ($body | parse_updates) end
    ) as $updates
  | ($updates | map(. + triage($mode; $allow))) as $t
  | ($t | map(select(.verdict == "candidate"))) as $cand
  | ($body | release_notes_urls) as $urls
  | { pr: $pr.number, branch: $pr.headRefName, headSha: $pr.headRefOid,
      updates: ($updates | map(. + {releaseNotesUrls: $urls})),
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
          updates: ($b | parse_updates | map(. + {releaseNotesUrls: $urls})) });

# [{pr, mergedAt, updates}] -> [retro item] without verdict
def aggregate:
  sort_by(.mergedAt)
  | map(. as $p | .updates[] | . + {pr: $p.pr})
  | group_by(.package)
  | map(. as $g
        | { package: $g[0].package,
            sourceUrl: ($g | map(.sourceUrl) | map(select(. != null)) | first // null),
            from: $g[0].from,
            to: $g[-1].to,
            prs: ($g | map(.pr) | unique),
            releaseNotesUrls: ($g | map(.releaseNotesUrls) | add | unique) }
        | .updateType = classify(.from; .to))
  | map({package, sourceUrl, from, to, updateType, prs, releaseNotesUrls});

def retro_items($allow):
  pr_updates | aggregate | map(. + triage("retro"; $allow));
