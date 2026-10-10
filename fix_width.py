from pathlib import Path
p = Path("dashboard/app.py")
c = p.read_text(encoding="utf-8")
before = c.count("use_container_width=True")
c = c.replace('use_container_width=True', 'width="stretch"')
c = c.replace('use_container_width=False', 'width="content"')
p.write_text(c, encoding="utf-8")
print(f"Sostituite {before} occorrenze di use_container_width=True")
