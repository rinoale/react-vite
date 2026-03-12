#!/usr/bin/env python3
"""Assign 'master' role to a user by game_id."""

import argparse

from sqlalchemy import create_engine, text
from uuid_utils import uuid7


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", default="아자린")
    parser.add_argument("--database-url", default="postgresql+psycopg2://mabinogi:mabinogi@localhost:5432/mabinogi")
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT u.id AS user_id, r.id AS role_id "
                "FROM users u, roles r "
                "WHERE u.game_id = :game_id AND r.name = 'master'"
            ),
            {"game_id": args.game_id},
        ).fetchone()

        if not row:
            print(f"User with game_id='{args.game_id}' or role 'master' not found.")
            return

        conn.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role_id) "
                "VALUES (:id, :user_id, :role_id)"
            ),
            {"id": str(uuid7()), "user_id": row.user_id, "role_id": row.role_id},
        )
        print(f"Assigned 'master' role to game_id='{args.game_id}'")


if __name__ == "__main__":
    main()
