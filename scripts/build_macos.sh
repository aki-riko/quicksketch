#!/usr/bin/env bash
# Codex 配置助手 —— macOS Nuitka 打包脚本
# 产出 build/CodexConfig.app,再用 hdiutil 打成 dist/CodexConfig_<ver>_<arch>.dmg
# 需先在同一 venv 里 pip install -r requirements.txt nuitka,并已生成 resources/app_icon.icns
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
APP_NAME="CodexConfig"
APP_VER="${APP_VER:-1.0.0}"
ARCH="$(uname -m)"   # arm64 或 x86_64

# 动态定位 site-packages 里的 prismqml 包目录(各机路径不同,禁止硬编码)
FQ="$("$PY" -c 'import os, prismqml; print(os.path.dirname(prismqml.__file__))')"
echo "[INFO] prismqml 路径: $FQ"

# 换参数前先删 build,避免残留产物干扰
rm -rf build

ICON_ARGS=()
if [ -f "resources/app_icon.icns" ]; then
  ICON_ARGS+=(--macos-app-icon=resources/app_icon.icns)
else
  echo "[WARN] 缺少 resources/app_icon.icns,将使用默认图标"
fi

"$PY" -m nuitka \
  --standalone \
  --assume-yes-for-downloads \
  --enable-plugin=pyside6 \
  --include-qt-plugins=qml \
  --include-data-dir=qml=qml \
  --include-data-dir=resources=resources \
  --include-data-dir="$FQ=prismqml" \
  --include-data-files=providers.json=providers.json \
  --include-package=prismqml \
  --include-package=backend \
  --macos-create-app-bundle \
  --macos-app-name="$APP_NAME" \
  "${ICON_ARGS[@]}" \
  --company-name=9li \
  --product-name="$APP_NAME" \
  --product-version="$APP_VER" \
  --output-dir=build \
  --output-filename="$APP_NAME" \
  main.py

APP_BUNDLE="build/main.app"
if [ ! -d "$APP_BUNDLE" ]; then
  # Nuitka 不同版本可能用 output-filename 命名 bundle
  APP_BUNDLE="build/${APP_NAME}.app"
fi
if [ ! -d "$APP_BUNDLE" ]; then
  echo "[ERROR] 未找到 .app 产物,build 目录内容:"
  ls -la build
  exit 1
fi
echo "[OK] app bundle: $APP_BUNDLE"

# 打 DMG
mkdir -p dist
DMG_PATH="dist/${APP_NAME}_${APP_VER}_${ARCH}.dmg"
rm -f "$DMG_PATH"

STAGING="build/dmg_staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP_BUNDLE" "$STAGING/${APP_NAME}.app"
ln -s /Applications "$STAGING/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGING" \
  -ov -format UDZO \
  "$DMG_PATH"

echo "[OK] DMG 产物: $DMG_PATH"
