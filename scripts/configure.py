"""Create secrets for a new personal install. Existing configuration is preserved."""

import argparse
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
target = root / ".env"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--show-password", action="store_true", help="在自己的终端显示当前工作台密码"
)
args = parser.parse_args()
if not target.exists():
    template = (root / ".env.example").read_text()
    template = template.replace(
        "RADAR_PASSWORD=\n", "RADAR_PASSWORD=" + secrets.token_urlsafe(24) + "\n"
    )
    template = template.replace(
        "POSTGRES_PASSWORD=\n", "POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n"
    )
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(template)
    print("已生成私有配置 .env")
if args.show_password:
    for line in target.read_text().splitlines():
        if line.startswith("RADAR_PASSWORD="):
            print(line.partition("=")[2])
            break
else:
    print("在自己的终端运行 python3 scripts/configure.py --show-password 查看登录密码")
