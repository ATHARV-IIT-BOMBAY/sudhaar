"""Download each sampled file (by blob sha) into eco/repos/<owner_repo>/<path>."""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

eco = Path(sys.argv[1])
rows = [l.split("\t") for l in (eco / "uniq.tsv").read_text().splitlines() if l.count("\t") >= 3]


def get(row):
    repo, path, _, sha = row[:4]
    out = eco / "repos" / repo.replace("/", "__") / path.replace("/", "__")
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/git/blobs/{sha}"],
                       capture_output=True)
    if r.returncode == 0:
        out.write_bytes(r.stdout)
    return r.returncode == 0


with ThreadPoolExecutor(10) as ex:
    ok = sum(ex.map(get, rows))
print(f"{ok}/{len(rows)} files")
