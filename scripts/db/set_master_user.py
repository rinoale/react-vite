#!/usr/bin/env python3
"""Bootstrap roles, feature flags, and assign 'master' role to a user by game_id.

Idempotent — creates roles/flags/assignments only if they don't already exist.
"""

import argparse

from sqlalchemy import create_engine, text
from uuid_utils import uuid7


ROLES = ["master", "admin"]

FEATURE_FLAGS = ["manage_tags", "manage_corrections"]

# role -> list of feature flags
ROLE_FLAGS = {
    "admin": ["manage_tags"],
}


def _ensure_roles(conn):
    for name in ROLES:
        result = conn.execute(
            text("INSERT INTO roles (id, name) VALUES (:id, :name) ON CONFLICT (name) DO NOTHING"),
            {"id": str(uuid7()), "name": name},
        )
        if result.rowcount > 0:
            print(f"  + role: {name}")
        else:
            print(f"  . role: {name} (exists)")


def _ensure_feature_flags(conn):
    for name in FEATURE_FLAGS:
        result = conn.execute(
            text("INSERT INTO feature_flags (id, name) VALUES (:id, :name) ON CONFLICT (name) DO NOTHING"),
            {"id": str(uuid7()), "name": name},
        )
        if result.rowcount > 0:
            print(f"  + flag: {name}")
        else:
            print(f"  . flag: {name} (exists)")


def _ensure_role_flags(conn):
    for role_name, flags in ROLE_FLAGS.items():
        role_row = conn.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}
        ).fetchone()
        if not role_row:
            print(f"  ! role '{role_name}' not found, skipping flag assignments")
            continue
        for flag_name in flags:
            flag_row = conn.execute(
                text("SELECT id FROM feature_flags WHERE name = :name"), {"name": flag_name}
            ).fetchone()
            if not flag_row:
                print(f"  ! flag '{flag_name}' not found, skipping")
                continue
            result = conn.execute(
                text(
                    "INSERT INTO role_feature_flags (id, role_id, feature_flag_id) "
                    "VALUES (:id, :role_id, :flag_id) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"id": str(uuid7()), "role_id": role_row.id, "flag_id": flag_row.id},
            )
            if result.rowcount > 0:
                print(f"  + {role_name} -> {flag_name}")
            else:
                print(f"  . {role_name} -> {flag_name} (exists)")


def _assign_master(conn, game_id):
    row = conn.execute(
        text(
            "SELECT u.id AS user_id, r.id AS role_id "
            "FROM users u, roles r "
            "WHERE u.game_id = :game_id AND r.name = 'master'"
        ),
        {"game_id": game_id},
    ).fetchone()

    if not row:
        print(f"\n  User with game_id='{game_id}' not found. Skipping role assignment.")
        return

    result = conn.execute(
        text(
            "INSERT INTO user_roles (id, user_id, role_id) "
            "VALUES (:id, :user_id, :role_id) "
            "ON CONFLICT DO NOTHING"
        ),
        {"id": str(uuid7()), "user_id": row.user_id, "role_id": row.role_id},
    )
    if result.rowcount > 0:
        print(f"\n  Assigned 'master' role to game_id='{game_id}'")
    else:
        print(f"\n  . game_id='{game_id}' already has 'master' role")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap roles, feature flags, and assign master user.")
    parser.add_argument("--game-id", default="아자린")
    parser.add_argument("--database-url", default="postgresql+psycopg2://mabinogi:mabinogi@localhost:5432/mabinogi")
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    with engine.begin() as conn:
        print("Roles:")
        _ensure_roles(conn)
        print("\nFeature flags:")
        _ensure_feature_flags(conn)
        print("\nRole -> flag assignments:")
        _ensure_role_flags(conn)
        _assign_master(conn, args.game_id)


if __name__ == "__main__":
    main()
