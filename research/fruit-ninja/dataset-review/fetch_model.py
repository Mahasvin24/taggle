#!/usr/bin/env python3
"""Download the exact public SlimSAM checkpoint used for this experiment."""

import concurrent.futures
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
REVISION="d67c795ed0caaec7423d799da25cdeded48aac40"


def main():
    folder=ROOT/".models/slimsam"
    folder.mkdir(parents=True,exist_ok=True)
    def fetch(name):
        target=folder/name
        if not target.exists():
            temporary=target.with_suffix(target.suffix+".download")
            subprocess.run(["curl","-sS","-L","--fail","--retry","2","--max-time","180",
                f"https://huggingface.co/Zigeng/SlimSAM-uniform-50/resolve/{REVISION}/{name}","-o",str(temporary)],check=True)
            temporary.replace(target)
        print(name,target.stat().st_size,"bytes",flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch,["config.json","preprocessor_config.json","model.safetensors"]))


if __name__=="__main__":
    main()
