#!/usr/bin/env python3
"""
クライアント管理ユーティリティ
他のスクリプトから import して使う共通モジュール
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# スクリプト自身の場所からリポジトリルートを算出（インストールパス非依存）
_SNS_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = _SNS_ROOT / "clients"


def list_clients() -> list[str]:
    """登録済みクライアント一覧を返す"""
    if not CLIENTS_DIR.exists():
        return []
    return [d.name for d in sorted(CLIENTS_DIR.iterdir()) if d.is_dir()]


def get_client_dir(client_name: str) -> Path:
    """クライアントのディレクトリパスを返す"""
    return CLIENTS_DIR / client_name


def load_profile(client_name: str) -> dict:
    """クライアントのprofile.jsonを読み込む"""
    profile_path = get_client_dir(client_name) / "profile.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"プロフィールが見つかりません: {client_name}")
    with open(profile_path, encoding="utf-8") as f:
        return json.load(f)


def load_credentials(client_name: str) -> dict:
    """クライアントの.envを読み込んで認証情報を返す"""
    env_path = get_client_dir(client_name) / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f".envが見つかりません: {client_name}")
    load_dotenv(env_path, override=True)
    return {
        "x": {
            "username": os.getenv("X_USERNAME", ""),
            "password": os.getenv("X_PASSWORD", ""),
        },
        "instagram": {
            "username": os.getenv("INSTAGRAM_USERNAME", ""),
            "password": os.getenv("INSTAGRAM_PASSWORD", ""),
        },
        "threads": {
            "username": os.getenv("THREADS_USERNAME", ""),
            "password": os.getenv("THREADS_PASSWORD", ""),
        },
        "tiktok": {
            "username": os.getenv("TIKTOK_USERNAME", ""),
            "password": os.getenv("TIKTOK_PASSWORD", ""),
        },
        "youtube": {
            "email":    os.getenv("YOUTUBE_EMAIL", ""),
            "password": os.getenv("YOUTUBE_PASSWORD", ""),
        },
        "facebook": {
            "email":    os.getenv("FACEBOOK_EMAIL", ""),
            "password": os.getenv("FACEBOOK_PASSWORD", ""),
        },
    }


def get_enabled_sns(client_name: str) -> list[str]:
    """有効なSNS一覧を返す"""
    profile = load_profile(client_name)
    return [sns for sns, cfg in profile.get("sns", {}).items() if cfg.get("enabled")]


def load_templates(client_name: str, sns: str) -> list[str]:
    """テンプレートファイルを読み込んで---区切りでリストとして返す"""
    tmpl_path = get_client_dir(client_name) / "templates" / f"{sns}.txt"
    if not tmpl_path.exists():
        return []
    content = tmpl_path.read_text(encoding="utf-8")
    templates = [t.strip() for t in content.split("---") if t.strip() and not t.strip().startswith("#")]
    return templates


def get_next_template(client_name: str, sns: str) -> str | None:
    """テンプレートを順番に返す（ローテーション）"""
    templates = load_templates(client_name, sns)
    if not templates:
        return None

    # ローテーション状態ファイル
    state_path = get_client_dir(client_name) / f".template_index_{sns}"
    idx = 0
    if state_path.exists():
        try:
            idx = int(state_path.read_text().strip())
        except ValueError:
            idx = 0

    template = templates[idx % len(templates)]
    state_path.write_text(str((idx + 1) % len(templates)))
    return template


if __name__ == "__main__":
    print("登録済みクライアント:")
    for c in list_clients():
        profile = load_profile(c)
        enabled = get_enabled_sns(c)
        print(f"  {c}  ({', '.join(enabled) if enabled else 'SNS未設定'})")
