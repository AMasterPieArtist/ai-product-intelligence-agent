"""Run maintained offline suites in isolated subprocesses (same module names)."""
import re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
code=0;count=0;skipped=0
for folder, test_dir in [(ROOT/'evaluator','tests'),(ROOT,'tests'),(ROOT/'benchmarks','.')]:
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',test_dir],cwd=folder,capture_output=True,text=True,encoding='utf-8',errors='replace')
    output=result.stdout+result.stderr
    match=re.search(r'Ran (\d+) tests?',output);count+=int(match.group(1)) if match else 0
    skip=re.search(r'skipped=(\d+)',output);skipped+=int(skip.group(1)) if skip else 0
    print(folder.name, 'passed' if result.returncode==0 else 'failed',match.group(0) if match else '')
    if result.returncode:print(output);code=1
print('Discovered:',count,'Executed:',count-skipped,'Skipped:',skipped)
raise SystemExit(code)
