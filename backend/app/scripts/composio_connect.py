"""Connect a user's Gmail + Google Calendar to Composio.

Usage:
    uv run python -m app.scripts.composio_connect you@example.com

The email is the Composio external user_id the app uses (the signed-in user's email). Prints the
current connection status and, for any toolkit not yet connected, an OAuth URL to open in a
browser. After authorizing, run again to confirm both are ACTIVE.
"""

import sys

from app.agents.tools import composio_tools

TOOLKITS = ["gmail", "googlecalendar"]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: uv run python -m app.scripts.composio_connect <user-email>")
        raise SystemExit(2)
    user_id = sys.argv[1]

    if not composio_tools.composio_enabled():
        print("COMPOSIO_API_KEY is not set — nothing to connect.")
        raise SystemExit(1)

    status = composio_tools.connection_status(user_id)
    print(f"Connection status for user_id={user_id}:")
    for tk in TOOLKITS:
        print(f"  {tk:14} {'CONNECTED' if status.get(tk) else 'not connected'}")

    pending = [tk for tk in TOOLKITS if not status.get(tk)]
    if not pending:
        print("\nAll set — Gmail and Google Calendar are connected.")
        return

    print("\nOpen these URLs in a browser and authorize, then re-run this script:")
    for tk in pending:
        try:
            url = composio_tools.authorize_url(user_id, tk)
            print(f"\n  {tk}:\n  {url}")
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {tk}: could not start auth — {exc}")


if __name__ == "__main__":
    main()
