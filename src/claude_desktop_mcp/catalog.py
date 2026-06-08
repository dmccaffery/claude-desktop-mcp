# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""The fake tool catalog.

A pure-data module (no FastMCP imports) describing 100+ realistic, themed "fake"
tools spread across common SaaS-style domains. Each :class:`ToolSpec` carries
enough metadata to (a) build a real MCP input schema, (b) be ranked by the cheap
search index, and (c) drive a generic canned-response handler.

Keeping this module dependency-free makes it trivially unit-testable and lets the
search index operate on plain Python objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# Spec primitives
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToolParam:
    """A single input parameter of a tool."""

    name: str
    type: str  # JSON Schema primitive: string | integer | number | boolean | array
    description: str
    required: bool = True
    default: Any = None
    enum: tuple[Any, ...] | None = None
    items_type: str | None = None  # element type when ``type == "array"``

    def to_schema(self) -> dict[str, Any]:
        prop: dict[str, Any] = {"type": self.type, "description": self.description}
        if self.enum is not None:
            prop["enum"] = list(self.enum)
        if self.type == "array":
            prop["items"] = {"type": self.items_type or "string"}
        if self.default is not None:
            prop["default"] = self.default
        return prop


@dataclass(frozen=True)
class ToolSpec:
    """A fake tool: name, description, schema, and search metadata."""

    name: str
    description: str
    domain: str
    params: tuple[ToolParam, ...] = ()
    tags: frozenset[str] = field(default_factory=frozenset)

    def input_schema(self) -> dict[str, Any]:
        """Build the MCP ``inputSchema`` (a JSON Schema object)."""
        properties = {p.name: p.to_schema() for p in self.params}
        required = [p.name for p in self.params if p.required]
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def searchable_text(self) -> str:
        """Concatenated, lowercased text the search index ranks against."""
        parts: list[str] = [
            self.name.replace("_", " "),
            self.description,
            " ".join(sorted(self.tags)),
        ]
        for p in self.params:
            parts.append(p.name.replace("_", " "))
            parts.append(p.description)
        return " ".join(parts).lower()


# --------------------------------------------------------------------------- #
# Terse parameter builders (keep the catalog table readable)
# --------------------------------------------------------------------------- #


def s(name: str, desc: str, required: bool = True, **kw: Any) -> ToolParam:
    return ToolParam(name, "string", desc, required, **kw)


def i(name: str, desc: str, required: bool = True, **kw: Any) -> ToolParam:
    return ToolParam(name, "integer", desc, required, **kw)


def b(name: str, desc: str, required: bool = True, **kw: Any) -> ToolParam:
    return ToolParam(name, "boolean", desc, required, **kw)


def num(name: str, desc: str, required: bool = True, **kw: Any) -> ToolParam:
    return ToolParam(name, "number", desc, required, **kw)


def arr(
    name: str, desc: str, items: str = "string", required: bool = True, **kw: Any
) -> ToolParam:
    return ToolParam(name, "array", desc, required, items_type=items, **kw)


# Reusable pagination params shared by many "list" tools.
LIMIT = i(
    "limit",
    "Maximum number of items to return (page size).",
    required=False,
    default=20,
)
CURSOR = s(
    "cursor", "Opaque pagination cursor returned by a previous call.", required=False
)


# --------------------------------------------------------------------------- #
# Tag vocabulary used to boost search recall
# --------------------------------------------------------------------------- #

DOMAIN_SYNONYMS: dict[str, tuple[str, ...]] = {
    "orders": (
        "order",
        "purchase",
        "sale",
        "ecommerce",
        "shop",
        "checkout",
        "cart",
        "fulfillment",
        "invoice",
    ),
    "users": ("user", "account", "member", "people", "profile", "identity", "customer"),
    "files": ("file", "document", "folder", "drive", "attachment", "storage"),
    "github": (
        "github",
        "git",
        "repository",
        "repo",
        "code",
        "pull",
        "request",
        "commit",
        "issue",
        "source",
        "branch",
    ),
    "slack": ("slack", "chat", "message", "messaging", "channel", "conversation", "dm"),
    "weather": (
        "weather",
        "forecast",
        "temperature",
        "climate",
        "conditions",
        "meteorology",
    ),
    "calendar": (
        "calendar",
        "event",
        "meeting",
        "schedule",
        "appointment",
        "availability",
    ),
    "database": ("database", "sql", "table", "query", "row", "schema", "postgres"),
    "email": ("email", "mail", "inbox", "smtp", "mailbox", "message"),
    "payments": (
        "payment",
        "charge",
        "billing",
        "invoice",
        "refund",
        "money",
        "stripe",
        "transaction",
        "subscription",
    ),
    "jira": ("jira", "ticket", "issue", "task", "bug", "project", "backlog", "sprint"),
    "analytics": (
        "analytics",
        "metric",
        "report",
        "event",
        "dashboard",
        "funnel",
        "retention",
        "telemetry",
    ),
    "notifications": ("notification", "push", "sms", "alert", "reminder", "message"),
    "storage": ("storage", "bucket", "object", "blob", "s3", "file"),
}

VERB_SYNONYMS: dict[str, tuple[str, ...]] = {
    "get": ("retrieve", "fetch", "read", "view", "show", "details", "lookup"),
    "list": ("enumerate", "browse", "all", "index"),
    "create": ("add", "new", "make", "open", "start"),
    "update": ("edit", "modify", "change", "patch", "set"),
    "delete": ("remove", "destroy", "drop"),
    "cancel": ("void", "abort", "stop"),
    "search": ("find", "query", "lookup", "discover"),
    "send": ("post", "dispatch", "deliver", "publish"),
    "track": ("status", "trace", "follow"),
    "refund": ("reimburse", "return", "chargeback"),
    "merge": ("combine", "integrate"),
    "share": ("grant", "permission", "access"),
    "transition": ("move", "workflow", "status"),
    "assign": ("owner", "assignee"),
    "schedule": ("plan", "future", "later"),
}


def _build_tags(domain: str, name: str) -> frozenset[str]:
    tags: set[str] = set(DOMAIN_SYNONYMS.get(domain, ()))
    tokens = name.split("_")
    tags.update(tokens)
    for tok in tokens:
        tags.update(VERB_SYNONYMS.get(tok, ()))
    return frozenset(tags)


# --------------------------------------------------------------------------- #
# The catalog table: domain -> list of (name, description, params)
# --------------------------------------------------------------------------- #

_OPS: dict[str, list[tuple[str, str, list[ToolParam]]]] = {
    "orders": [
        (
            "orders_list_orders",
            "List customer orders, optionally filtered by customer or status, with pagination.",
            [
                s(
                    "customer_id",
                    "Filter to orders placed by this customer.",
                    required=False,
                ),
                s(
                    "status",
                    "Filter by order status.",
                    required=False,
                    enum=(
                        "pending",
                        "paid",
                        "shipped",
                        "delivered",
                        "cancelled",
                        "refunded",
                    ),
                ),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "orders_get_order",
            "Retrieve full details of a single customer order by its order ID, including line items, totals, status, and shipping.",
            [s("order_id", "Unique identifier of the order to retrieve.")],
        ),
        (
            "orders_create_order",
            "Create a new customer order from a list of product line items.",
            [
                s("customer_id", "Customer placing the order."),
                arr(
                    "items",
                    "Line items, each a product id and quantity.",
                    items="object",
                ),
            ],
        ),
        (
            "orders_update_order",
            "Update mutable fields on an existing order such as shipping address or internal notes.",
            [
                s("order_id", "Order to update."),
                s("shipping_address", "New shipping address.", required=False),
                s("notes", "Internal notes.", required=False),
            ],
        ),
        (
            "orders_cancel_order",
            "Cancel an order that has not yet shipped.",
            [
                s("order_id", "Order to cancel."),
                s("reason", "Reason for cancellation.", required=False),
            ],
        ),
        (
            "orders_refund_order",
            "Issue a full or partial refund against a paid order.",
            [
                s("order_id", "Order to refund."),
                num(
                    "amount",
                    "Amount to refund; omit for a full refund.",
                    required=False,
                ),
            ],
        ),
        (
            "orders_track_order",
            "Get the current shipment tracking status and carrier events for an order.",
            [s("order_id", "Order to track.")],
        ),
        (
            "orders_search_orders",
            "Search orders by free-text query across customer name, email, product, or order number.",
            [s("query", "Free-text search query."), LIMIT],
        ),
        (
            "orders_get_order_invoice",
            "Fetch the invoice document and billing breakdown for an order.",
            [s("order_id", "Order whose invoice to fetch.")],
        ),
    ],
    "users": [
        (
            "users_list_users",
            "List user accounts, optionally filtered by role or status.",
            [
                s("role", "Filter by role.", required=False),
                s(
                    "status",
                    "Filter by account status.",
                    required=False,
                    enum=("active", "suspended", "invited", "deactivated"),
                ),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "users_get_user",
            "Retrieve a single user account by user ID.",
            [s("user_id", "Unique identifier of the user.")],
        ),
        (
            "users_create_user",
            "Create a new user account.",
            [
                s("email", "Email address for the new user."),
                s("name", "Full name of the user.", required=False),
                s("role", "Initial role.", required=False),
            ],
        ),
        (
            "users_update_user",
            "Update profile fields on an existing user account.",
            [
                s("user_id", "User to update."),
                s("name", "New full name.", required=False),
                s("email", "New email address.", required=False),
            ],
        ),
        (
            "users_delete_user",
            "Permanently delete a user account.",
            [s("user_id", "User to delete.")],
        ),
        (
            "users_search_users",
            "Search user accounts by name, email, or username.",
            [s("query", "Free-text search query."), LIMIT],
        ),
        (
            "users_get_user_profile",
            "Get the extended public profile for a user, including avatar and bio.",
            [s("user_id", "User whose profile to fetch.")],
        ),
        (
            "users_reset_user_password",
            "Trigger a password reset email for a user account.",
            [s("user_id", "User to reset.")],
        ),
        (
            "users_set_user_role",
            "Change the access role assigned to a user.",
            [s("user_id", "User to modify."), s("role", "New role to assign.")],
        ),
    ],
    "files": [
        (
            "files_list_files",
            "List files in a folder, optionally filtered by MIME type.",
            [
                s(
                    "folder_id",
                    "Folder to list; omit for the root folder.",
                    required=False,
                ),
                s("mime_type", "Filter by MIME type.", required=False),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "files_get_file_metadata",
            "Retrieve metadata for a file such as name, size, owner, and timestamps.",
            [s("file_id", "File whose metadata to fetch.")],
        ),
        (
            "files_upload_file",
            "Upload a new file from base64 content or a source URL.",
            [
                s("name", "File name."),
                s("content", "Base64-encoded file content.", required=False),
                s("source_url", "URL to fetch content from.", required=False),
            ],
        ),
        (
            "files_download_file",
            "Download the binary content of a file.",
            [s("file_id", "File to download.")],
        ),
        (
            "files_delete_file",
            "Move a file to trash, or delete it permanently.",
            [
                s("file_id", "File to delete."),
                b(
                    "permanent",
                    "Delete permanently instead of trashing.",
                    required=False,
                    default=False,
                ),
            ],
        ),
        (
            "files_move_file",
            "Move a file to a different folder.",
            [s("file_id", "File to move."), s("folder_id", "Destination folder.")],
        ),
        (
            "files_copy_file",
            "Create a copy of a file.",
            [
                s("file_id", "File to copy."),
                s("name", "Name for the copy.", required=False),
            ],
        ),
        (
            "files_search_files",
            "Search files by name or full-text content.",
            [s("query", "Free-text search query."), LIMIT],
        ),
        (
            "files_share_file",
            "Create a shareable link or grant a user access to a file.",
            [
                s("file_id", "File to share."),
                s("email", "User to share with.", required=False),
                s(
                    "role",
                    "Permission to grant.",
                    required=False,
                    enum=("viewer", "commenter", "editor"),
                ),
            ],
        ),
    ],
    "github": [
        (
            "github_list_repositories",
            "List Git repositories for a user or organization.",
            [s("owner", "User or organization login.", required=False), LIMIT, CURSOR],
        ),
        (
            "github_get_repository",
            "Get details about a single Git repository.",
            [s("owner", "Repository owner."), s("repo", "Repository name.")],
        ),
        (
            "github_create_issue",
            "Open a new issue on a repository.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                s("title", "Issue title."),
                s("body", "Issue body in Markdown.", required=False),
            ],
        ),
        (
            "github_list_issues",
            "List issues on a repository, filtered by state.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                s(
                    "state",
                    "Issue state.",
                    required=False,
                    enum=("open", "closed", "all"),
                ),
                LIMIT,
            ],
        ),
        (
            "github_get_issue",
            "Get a single issue by number.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                i("number", "Issue number."),
            ],
        ),
        (
            "github_create_pull_request",
            "Open a pull request from a head branch into a base branch.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                s("title", "Pull request title."),
                s("head", "Head branch."),
                s("base", "Base branch."),
            ],
        ),
        (
            "github_list_pull_requests",
            "List pull requests on a repository.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                s(
                    "state",
                    "Pull request state.",
                    required=False,
                    enum=("open", "closed", "all"),
                ),
                LIMIT,
            ],
        ),
        (
            "github_merge_pull_request",
            "Merge an open pull request.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                i("number", "Pull request number."),
                s(
                    "method",
                    "Merge method.",
                    required=False,
                    enum=("merge", "squash", "rebase"),
                ),
            ],
        ),
        (
            "github_list_commits",
            "List commits on a branch.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                s("branch", "Branch name.", required=False),
                LIMIT,
            ],
        ),
        (
            "github_get_commit",
            "Get details and diff stats for a single commit.",
            [
                s("owner", "Repository owner."),
                s("repo", "Repository name."),
                s("sha", "Commit SHA."),
            ],
        ),
    ],
    "slack": [
        (
            "slack_send_message",
            "Send a message to a Slack channel or user.",
            [s("channel", "Channel ID or name."), s("text", "Message text.")],
        ),
        (
            "slack_list_channels",
            "List Slack channels in the workspace.",
            [
                s(
                    "type",
                    "Channel type filter.",
                    required=False,
                    enum=("public", "private", "im", "mpim"),
                ),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "slack_get_channel",
            "Get metadata for a single Slack channel.",
            [s("channel", "Channel ID.")],
        ),
        (
            "slack_create_channel",
            "Create a new Slack channel.",
            [
                s("name", "Channel name."),
                b(
                    "private",
                    "Create as a private channel.",
                    required=False,
                    default=False,
                ),
            ],
        ),
        (
            "slack_list_messages",
            "List recent messages in a channel.",
            [s("channel", "Channel ID."), LIMIT, CURSOR],
        ),
        (
            "slack_set_status",
            "Set the authenticated user's status text and emoji.",
            [
                s("text", "Status text."),
                s("emoji", "Status emoji shortcode.", required=False),
            ],
        ),
        (
            "slack_upload_snippet",
            "Upload a text snippet or file to a channel.",
            [
                s("channel", "Channel ID."),
                s("content", "Snippet content."),
                s("filename", "File name.", required=False),
            ],
        ),
        (
            "slack_invite_user",
            "Invite a user to a channel.",
            [s("channel", "Channel ID."), s("user_id", "User to invite.")],
        ),
    ],
    "weather": [
        (
            "weather_get_current_weather",
            "Get current weather conditions for a location.",
            [
                s("location", "City name, postal code, or 'lat,long'."),
                s("units", "Unit system.", required=False, enum=("metric", "imperial")),
            ],
        ),
        (
            "weather_get_forecast",
            "Get a multi-day weather forecast for a location.",
            [
                s("location", "City name, postal code, or 'lat,long'."),
                i("days", "Number of days to forecast.", required=False, default=5),
                s("units", "Unit system.", required=False, enum=("metric", "imperial")),
            ],
        ),
        (
            "weather_get_alerts",
            "Get active severe-weather alerts and warnings for a location.",
            [s("location", "City name, postal code, or 'lat,long'.")],
        ),
        (
            "weather_get_historical_weather",
            "Get historical weather observations for a location on a past date.",
            [
                s("location", "City name, postal code, or 'lat,long'."),
                s("date", "Date in YYYY-MM-DD format."),
            ],
        ),
        (
            "weather_get_air_quality",
            "Get the current air quality index and pollutant breakdown for a location.",
            [s("location", "City name, postal code, or 'lat,long'.")],
        ),
    ],
    "calendar": [
        (
            "calendar_list_events",
            "List calendar events within a date range.",
            [
                s(
                    "calendar_id",
                    "Calendar to query.",
                    required=False,
                    default="primary",
                ),
                s("start", "Range start (ISO 8601).", required=False),
                s("end", "Range end (ISO 8601).", required=False),
                LIMIT,
            ],
        ),
        (
            "calendar_get_event",
            "Get a single calendar event by ID.",
            [
                s("event_id", "Event to retrieve."),
                s(
                    "calendar_id",
                    "Calendar containing the event.",
                    required=False,
                    default="primary",
                ),
            ],
        ),
        (
            "calendar_create_event",
            "Create a new calendar event.",
            [
                s("title", "Event title."),
                s("start", "Start time (ISO 8601)."),
                s("end", "End time (ISO 8601)."),
                arr("attendees", "Attendee email addresses.", required=False),
            ],
        ),
        (
            "calendar_update_event",
            "Update fields on an existing calendar event.",
            [
                s("event_id", "Event to update."),
                s("title", "New title.", required=False),
                s("start", "New start time.", required=False),
                s("end", "New end time.", required=False),
            ],
        ),
        (
            "calendar_delete_event",
            "Delete a calendar event.",
            [
                s("event_id", "Event to delete."),
                s(
                    "calendar_id",
                    "Calendar containing the event.",
                    required=False,
                    default="primary",
                ),
            ],
        ),
        (
            "calendar_find_free_slots",
            "Find open time slots across one or more calendars for scheduling a meeting.",
            [
                arr("calendar_ids", "Calendars to check for availability."),
                i("duration_minutes", "Desired meeting length in minutes."),
                s("start", "Search window start (ISO 8601).", required=False),
                s("end", "Search window end (ISO 8601).", required=False),
            ],
        ),
        (
            "calendar_list_calendars",
            "List the calendars the user has access to.",
            [LIMIT],
        ),
        (
            "calendar_respond_to_invite",
            "Respond to a meeting invitation.",
            [
                s("event_id", "Event to respond to."),
                s(
                    "response",
                    "Response to the invite.",
                    enum=("accepted", "declined", "tentative"),
                ),
            ],
        ),
    ],
    "database": [
        (
            "database_run_query",
            "Run a read-only SQL query and return the resulting rows.",
            [
                s("sql", "SQL query to execute."),
                i("limit", "Maximum rows to return.", required=False, default=100),
            ],
        ),
        (
            "database_list_tables",
            "List tables in a database schema.",
            [s("schema", "Schema name.", required=False, default="public")],
        ),
        (
            "database_describe_table",
            "Describe a table's columns, types, and indexes.",
            [
                s("table", "Table name."),
                s("schema", "Schema name.", required=False, default="public"),
            ],
        ),
        (
            "database_insert_row",
            "Insert a row into a table.",
            [
                s("table", "Table name."),
                arr("columns", "Column names."),
                arr("values", "Values matching the columns."),
            ],
        ),
        (
            "database_update_row",
            "Update rows in a table that match a condition.",
            [
                s("table", "Table name."),
                s("set", "SET clause assignments, e.g. status='active'."),
                s("where", "WHERE condition."),
            ],
        ),
        (
            "database_delete_row",
            "Delete rows from a table that match a condition.",
            [s("table", "Table name."), s("where", "WHERE condition.")],
        ),
        (
            "database_create_index",
            "Create an index on one or more table columns.",
            [
                s("table", "Table name."),
                arr("columns", "Columns to index."),
                b("unique", "Create a unique index.", required=False, default=False),
            ],
        ),
        (
            "database_get_table_stats",
            "Get row counts and size statistics for a table.",
            [
                s("table", "Table name."),
                s("schema", "Schema name.", required=False, default="public"),
            ],
        ),
    ],
    "email": [
        (
            "email_send_email",
            "Send an email message.",
            [
                arr("to", "Recipient email addresses."),
                s("subject", "Subject line."),
                s("body", "Email body."),
                arr("cc", "CC recipients.", required=False),
            ],
        ),
        (
            "email_list_emails",
            "List emails in a mailbox folder.",
            [
                s("folder", "Mailbox folder.", required=False, default="inbox"),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "email_get_email",
            "Retrieve a single email message by ID.",
            [s("message_id", "Email message to fetch.")],
        ),
        (
            "email_search_emails",
            "Search emails by sender, subject, or body text.",
            [s("query", "Free-text search query."), LIMIT],
        ),
        (
            "email_delete_email",
            "Delete an email message.",
            [s("message_id", "Email to delete.")],
        ),
        (
            "email_mark_as_read",
            "Mark an email as read or unread.",
            [
                s("message_id", "Email to update."),
                b(
                    "read",
                    "Mark as read; set false to mark unread.",
                    required=False,
                    default=True,
                ),
            ],
        ),
        (
            "email_create_draft",
            "Create a draft email without sending it.",
            [
                arr("to", "Recipient email addresses.", required=False),
                s("subject", "Subject line.", required=False),
                s("body", "Draft body.", required=False),
            ],
        ),
        (
            "email_add_label",
            "Apply a label to an email message.",
            [s("message_id", "Email to label."), s("label", "Label to apply.")],
        ),
    ],
    "payments": [
        (
            "payments_create_charge",
            "Create a payment charge against a customer or card.",
            [
                i("amount", "Amount in the smallest currency unit (e.g. cents)."),
                s("currency", "ISO 4217 currency code.", required=False, default="usd"),
                s("customer_id", "Customer to charge.", required=False),
            ],
        ),
        (
            "payments_refund_charge",
            "Refund a previously created charge, fully or partially.",
            [
                s("charge_id", "Charge to refund."),
                i(
                    "amount",
                    "Amount to refund; omit for a full refund.",
                    required=False,
                ),
            ],
        ),
        (
            "payments_get_charge",
            "Retrieve a charge by ID.",
            [s("charge_id", "Charge to retrieve.")],
        ),
        (
            "payments_list_charges",
            "List charges, optionally for a single customer.",
            [
                s("customer_id", "Filter to one customer.", required=False),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "payments_create_customer",
            "Create a new billing customer.",
            [
                s("email", "Customer email."),
                s("name", "Customer name.", required=False),
            ],
        ),
        (
            "payments_get_balance",
            "Get the current account balance, available and pending.",
            [],
        ),
        (
            "payments_list_payouts",
            "List payouts sent to your bank account.",
            [LIMIT, CURSOR],
        ),
        (
            "payments_create_subscription",
            "Start a recurring subscription for a customer on a price plan.",
            [
                s("customer_id", "Customer to subscribe."),
                s("price_id", "Price or plan to subscribe to."),
            ],
        ),
    ],
    "jira": [
        (
            "jira_create_ticket",
            "Create a new issue or ticket in a project.",
            [
                s("project", "Project key."),
                s("summary", "Ticket summary."),
                s(
                    "type",
                    "Issue type.",
                    required=False,
                    enum=("bug", "task", "story", "epic"),
                ),
                s("description", "Ticket description.", required=False),
            ],
        ),
        (
            "jira_get_ticket",
            "Get a ticket by its key.",
            [s("ticket_key", "Ticket key, e.g. ENG-123.")],
        ),
        (
            "jira_update_ticket",
            "Update fields on a ticket.",
            [
                s("ticket_key", "Ticket to update."),
                s("summary", "New summary.", required=False),
                s("priority", "New priority.", required=False),
            ],
        ),
        (
            "jira_list_tickets",
            "List tickets in a project, optionally filtered by status.",
            [
                s("project", "Project key."),
                s("status", "Filter by status.", required=False),
                LIMIT,
            ],
        ),
        (
            "jira_transition_ticket",
            "Move a ticket to a new workflow status.",
            [
                s("ticket_key", "Ticket to transition."),
                s("status", "Target status, e.g. 'In Progress' or 'Done'."),
            ],
        ),
        (
            "jira_add_comment",
            "Add a comment to a ticket.",
            [s("ticket_key", "Ticket to comment on."), s("body", "Comment text.")],
        ),
        (
            "jira_assign_ticket",
            "Assign a ticket to a user.",
            [
                s("ticket_key", "Ticket to assign."),
                s("assignee", "Username or account ID of the assignee."),
            ],
        ),
        (
            "jira_search_tickets",
            "Search tickets using a text query or JQL.",
            [s("query", "Text query or JQL expression."), LIMIT],
        ),
    ],
    "analytics": [
        (
            "analytics_track_event",
            "Record a product analytics event for a user.",
            [
                s("event", "Event name."),
                s("user_id", "User who triggered the event.", required=False),
                s("properties", "JSON-encoded event properties.", required=False),
            ],
        ),
        (
            "analytics_get_metric",
            "Get the value of a single metric over a time range.",
            [
                s("metric", "Metric name."),
                s("start", "Range start (ISO 8601).", required=False),
                s("end", "Range end (ISO 8601).", required=False),
            ],
        ),
        (
            "analytics_run_report",
            "Run an analytics report grouped by a dimension.",
            [
                s("report", "Report name or ID."),
                s("dimension", "Dimension to group by.", required=False),
                s("start", "Range start.", required=False),
                s("end", "Range end.", required=False),
            ],
        ),
        ("analytics_list_dashboards", "List available analytics dashboards.", [LIMIT]),
        (
            "analytics_get_funnel",
            "Compute conversion through an ordered funnel of events.",
            [
                arr("steps", "Ordered event names forming the funnel."),
                s("start", "Range start.", required=False),
                s("end", "Range end.", required=False),
            ],
        ),
        (
            "analytics_get_retention",
            "Compute user retention cohorts over time.",
            [
                s("cohort_event", "Event defining the cohort.", required=False),
                s("return_event", "Event defining a return.", required=False),
                s(
                    "period",
                    "Cohort period.",
                    required=False,
                    enum=("day", "week", "month"),
                ),
            ],
        ),
        (
            "analytics_export_report",
            "Export a report's raw rows to CSV or JSON.",
            [
                s("report", "Report to export."),
                s("format", "Export format.", required=False, enum=("csv", "json")),
            ],
        ),
    ],
    "notifications": [
        (
            "notifications_send_push",
            "Send a push notification to a device or user.",
            [
                s("user_id", "User to notify."),
                s("title", "Notification title."),
                s("body", "Notification body."),
            ],
        ),
        (
            "notifications_send_sms",
            "Send an SMS text message to a phone number.",
            [
                s("phone", "Destination phone number in E.164 format."),
                s("message", "Text message body."),
            ],
        ),
        (
            "notifications_schedule_notification",
            "Schedule a notification to be delivered at a future time.",
            [
                s("user_id", "User to notify."),
                s("body", "Notification body."),
                s("send_at", "Delivery time (ISO 8601)."),
            ],
        ),
        (
            "notifications_cancel_notification",
            "Cancel a previously scheduled notification.",
            [s("notification_id", "Scheduled notification to cancel.")],
        ),
        (
            "notifications_list_notifications",
            "List sent and scheduled notifications.",
            [
                s(
                    "status",
                    "Filter by status.",
                    required=False,
                    enum=("scheduled", "sent", "failed", "cancelled"),
                ),
                LIMIT,
            ],
        ),
    ],
    "storage": [
        (
            "storage_create_bucket",
            "Create a new object-storage bucket.",
            [
                s("name", "Globally unique bucket name."),
                s("region", "Region to create the bucket in.", required=False),
            ],
        ),
        ("storage_list_buckets", "List object-storage buckets.", [LIMIT]),
        (
            "storage_delete_bucket",
            "Delete an empty object-storage bucket.",
            [s("name", "Bucket to delete.")],
        ),
        (
            "storage_set_bucket_policy",
            "Set the access policy on a bucket.",
            [
                s("name", "Bucket to configure."),
                s("policy", "JSON-encoded access policy."),
            ],
        ),
        (
            "storage_list_objects",
            "List objects in a bucket under an optional key prefix.",
            [
                s("bucket", "Bucket to list."),
                s("prefix", "Key prefix filter.", required=False),
                LIMIT,
                CURSOR,
            ],
        ),
        (
            "storage_get_object_url",
            "Generate a pre-signed URL to download an object.",
            [
                s("bucket", "Bucket containing the object."),
                s("key", "Object key."),
                i(
                    "expires_in",
                    "URL lifetime in seconds.",
                    required=False,
                    default=3600,
                ),
            ],
        ),
    ],
}


def _build_catalog() -> tuple[ToolSpec, ...]:
    specs: list[ToolSpec] = []
    for domain, ops in _OPS.items():
        for name, description, params in ops:
            specs.append(
                ToolSpec(
                    name=name,
                    description=description,
                    domain=domain,
                    params=tuple(params),
                    tags=_build_tags(domain, name),
                )
            )
    return tuple(specs)


CATALOG: tuple[ToolSpec, ...] = _build_catalog()

# The whole point of this server is to exceed Claude Desktop's comfortable tool count.
assert len({spec.name for spec in CATALOG}) == len(CATALOG), (
    "duplicate tool names in catalog"
)
assert len(CATALOG) >= 101, f"catalog must contain >=101 tools, got {len(CATALOG)}"
