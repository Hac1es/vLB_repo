# vLB repo

Build & publish `.deb` packages qua web UI. Backend FastAPI đóng gói bằng `dpkg-deb`, lưu trong `/etc/repo/<name>/`.

## Structure

```
FastAPI/   # backend (port 8000) — build/list/update/delete/pull .deb
UI/        # frontend NiceGUI (port 8081) — quản lý package
```

## Yêu cầu hệ thống

- Python 3.12+
- `dpkg-deb` (gói `dpkg-dev` trên Debian/Ubuntu)
- Quyền ghi `/etc/repo/` (chạy backend với sudo, hoặc chmod thư mục)

## Setup (sau git clone)

```bash
git clone <repo-url> vLB_repo
cd vLB_repo

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Chạy

**Backend** (terminal 1):
```bash
cd FastAPI
sudo ../venv/bin/python main.py          # sudo để ghi /etc/repo
# hoặc: sudo mkdir -p /etc/repo && sudo chown $USER /etc/repo && ../venv/bin/python main.py
```
Backend chạy ở `http://localhost:8000`. Tạo `/etc/repo/` tự động nếu thiếu.

**UI** (terminal 2):
```bash
cd UI
../venv/bin/python main.py
```
Mở `http://localhost:8081`.

## Trên VM — pull & install package

VM chỉ cần `curl` + `dpkg`. Script `vm-pull.sh`:

```bash
#!/bin/bash
# Usage: ./vm-pull.sh <package-name> [backend-host]
NAME="$1"
HOST="${2:-http://<backend-ip>:8000}"
curl -fsSL "$HOST/pull/$NAME" -o "/tmp/$NAME.deb" || { echo "pull failed"; exit 1; }
sudo dpkg -i "/tmp/$NAME.deb"
echo "installed $NAME"
```

```bash
chmod +x vm-pull.sh
./vm-pull.sh vlb-agent http://192.168.x.x:8000
```

Service (nếu package có systemd unit) tự enable khi `dpkg -i` nếu unit có `[Install]`. Hoặc:
```bash
sudo systemctl enable --now vlb-agent
```

## Endpoints

| Route | Method | Mô tả |
|-------|--------|-------|
| `/list` | GET | list package |
| `/package/{name}` | GET | spec để prefill edit |
| `/publish` | POST | tạo package mới |
| `/update/{name}` | POST | update (ghi đè) |
| `/delete/{name}` | DELETE | xóa package |
| `/pull/{name}` | GET | tải .deb (cho VM) |
