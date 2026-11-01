"""Run sudhaar over every downloaded repo and summarise ecosystem health."""
import collections, json, re, sys
from pathlib import Path

sys.path.insert(0, sys.argv[2])
import sudhaar as sd

eco = Path(sys.argv[1]) / "repos"
repos = sorted(p for p in eco.iterdir() if p.is_dir())
checked, broken, rule_repos, examples = 0, 0, collections.Counter(), collections.defaultdict(list)


def rule(i):
    if i["key"] == "model":
        return f"dead model {i['value']}"
    if i["key"] == "speaker":
        return f"invalid speaker for {i['model']}"
    if i["key"].endswith("language_code"):
        return "wrong Odia / language code"
    return f"bad {i['key']} for {i['model']}"


for r in repos:
    files = [f for f in r.iterdir() if f.is_file()]
    # only repos where we can see at least one literal Sarvam model id count as "checkable"
    hits = [h for f in files for h in sd.hits_in(f.read_text(errors="ignore")) if h["key"] == "model" and sd.family(h["value"])]
    if not hits:
        continue
    checked += 1
    errs = [i for f in files for i in sd.check_file(f) if i["severity"] == "error"]
    if errs:
        broken += 1
        for name in {rule(i) for i in errs}:
            rule_repos[name] += 1
            if len(examples[name]) < 3:
                examples[name].append(r.name.replace("__", "/", 1))

print(f"repos sampled: {len(repos)}  with literal Sarvam model ids: {checked}  broken today: {broken} ({broken / max(checked, 1):.0%})")
for name, n in rule_repos.most_common(15):
    print(f"  {n:4d}  {name}   e.g. {', '.join(examples[name])}")
json.dump({"sampled": len(repos), "checked": checked, "broken": broken, "rules": rule_repos.most_common(),
           "examples": examples}, open(Path(sys.argv[1]) / "summary.json", "w"), indent=1)
