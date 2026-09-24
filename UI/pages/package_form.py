from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

from nicegui import ui

import api
from common import (
    page_layout,
    section_card,
)
from .package_form_spec import (
    build_spec,
    init_state,
)


# =====================================================================
# Routes
# =====================================================================


@ui.page("/packages/new")
async def new_package_page():

    with page_layout(
        "Build package",
        "Create and publish a new Debian package.",
        back_to="/",
    ):
        render_package_form(
            mode="create",
            package=None,
        )


@ui.page("/packages/{name}/edit")
async def update_package_page(
    name: str,
):

    try:
        package = await api.get_package(name)

    except httpx.HTTPError as exc:
        with page_layout(
            f"Update {name}",
            back_to="/",
        ):
            ui.label("Could not load package").classes(
                "text-xl font-semibold text-red-400"
            )

            ui.label(str(exc)).classes("text-slate-500")

        return

    with page_layout(
        f"Update {name}",
        "Existing files are preserved unless you explicitly replace or remove them.",
        back_to="/",
    ):
        render_package_form(
            mode="update",
            package=package,
        )


# =====================================================================
# Helpers
# =====================================================================


def store_upload(
    target: dict,
    key: str,
    event,
):
    data = event.content.read()

    target[key] = (
        event.name,
        data,
    )

    ui.notify(
        f"Loaded {event.name} ({len(data):,} bytes)",
        type="positive",
    )


@dataclass
class ResponsePanel:
    status: ui.label
    time: ui.label
    size: ui.label
    body: ui.code
    headers: ui.code

    def set(
        self,
        response,
        elapsed_ms: float,
    ):

        try:
            body = response.json()

            body_text = json.dumps(
                body,
                indent=2,
                ensure_ascii=False,
            )

        except Exception:
            body_text = response.text

        self.status.set_text(f"{response.status_code} {response.reason_phrase}")

        self.status.classes(
            remove=("text-green-400 text-yellow-400 text-red-400 text-slate-500")
        )

        if response.status_code < 300:
            self.status.classes(add="text-green-400")

        elif response.status_code < 400:
            self.status.classes(add="text-yellow-400")

        else:
            self.status.classes(add="text-red-400")

        self.time.set_text(f"{elapsed_ms:.0f} ms")

        size = len(response.content)

        if size < 1024:
            size_text = f"{size} B"

        elif size < 1024 * 1024:
            size_text = f"{size / 1024:.1f} KB"

        else:
            size_text = f"{size / 1024 / 1024:.1f} MB"

        self.size.set_text(size_text)

        self.body.set_content(body_text)

        self.headers.set_content(
            json.dumps(
                dict(response.headers),
                indent=2,
            )
        )

    def mark_network_error(
        self,
        exc: Exception,
    ):

        self.status.set_text("Network Error")

        self.status.classes(
            remove=("text-green-400 text-yellow-400 text-slate-500"),
            add="text-red-400",
        )

        self.body.set_content(str(exc))


# =====================================================================
# Sections
# =====================================================================


def _render_metadata_section(
    package: dict,
    is_update: bool,
):

    with section_card(
        "Package information",
        "Metadata embedded into the Debian package.",
    ):
        with ui.grid(columns=12).classes("w-full gap-4 items-start"):
            name_input = (
                ui.input(
                    "Package name",
                    value=package.get(
                        "name",
                        "myapp",
                    ),
                    placeholder="my-agent",
                )
                .props("outlined")
                .classes("col-span-6 w-full")
            )

            if is_update:
                name_input.disable()

            version_input = (
                ui.input(
                    "Version",
                    value=package.get(
                        "version",
                        "1.0.0",
                    ),
                )
                .props("outlined")
                .classes("col-span-3 w-full")
            )

            arch_input = (
                ui.select(
                    [
                        "amd64",
                        "arm64",
                    ],
                    value=package.get(
                        "arch",
                        "amd64",
                    ),
                    label="Architecture",
                )
                .props("outlined")
                .classes("col-span-3 w-full")
            )

    return (
        name_input,
        version_input,
        arch_input,
    )


def _render_binary_section(
    state: dict,
    package: dict,
    is_update: bool,
    current_binary: dict,
):

    with section_card(
        "Application binary",
        (
            "Replace the current binary or keep it unchanged."
            if is_update
            else "The executable installed into the package."
        ),
    ):
        if is_update and current_binary:
            with ui.card().classes(
                "w-full bg-[#0d0d12] border border-slate-800 shadow-none p-4"
            ):
                ui.label("Current binary").classes("text-sm text-slate-500")

                ui.label(
                    current_binary.get(
                        "filename",
                        package.get(
                            "name",
                            "binary",
                        ),
                    )
                ).classes("font-semibold")

        ui.upload(
            label=("Replace binary" if is_update else "Drop binary here or browse"),
            multiple=False,
            auto_upload=True,
            on_upload=lambda e: store_upload(
                state,
                "binary",
                e,
            ),
        ).props("flat bordered").classes("w-full")

        binary_destination_input = (
            ui.input(
                "Install destination",
                value=current_binary.get(
                    "destination",
                    f"/usr/bin/{package.get('name', 'myapp')}",
                ),
                placeholder="/usr/bin/myapp",
            )
            .props("outlined")
            .classes("w-full")
        )

        if is_update:
            ui.label("Leave binary upload empty to keep the current binary.").classes(
                "text-xs text-slate-500"
            )

    return binary_destination_input


def _render_extra_files_section(
    state: dict,
    is_update: bool,
):

    with section_card(
        "Additional files",
        (
            "Existing files are kept unless you replace or remove them."
            if is_update
            else "Optional config, assets, certificates or other files."
        ),
    ):

        @ui.refreshable
        def render_extra_files():

            if not state["extra"]:
                with ui.column().classes("w-full items-center py-5 gap-1"):
                    ui.icon("note_add").classes("text-3xl text-slate-600")

                    ui.label("No additional files").classes("text-sm text-slate-400")

                return

            for index, row in enumerate(state["extra"]):
                with ui.card().classes(
                    "w-full bg-[#0d0d12] border border-slate-800 shadow-none p-4"
                ):
                    # -----------------------------------------
                    # Existing file
                    # -----------------------------------------

                    if row["existing"]:
                        # Removed → struck-through + undo
                        if row["action"] == "remove":
                            with ui.row().classes("w-full items-center gap-3"):
                                ui.icon("delete_outline").classes("text-slate-600")
                                ui.label(row["filename"]).classes(
                                    "text-slate-500 line-through"
                                )
                                ui.label("will be removed").classes(
                                    "text-sm text-slate-500"
                                )
                                ui.space()

                                def undo_remove(r=row):
                                    r["action"] = "keep"
                                    render_extra_files.refresh()

                                ui.button(
                                    icon="undo",
                                    on_click=undo_remove,
                                ).props("flat round color=grey-5")

                        else:
                            with ui.row().classes("w-full items-center gap-4"):
                                with ui.column().classes("gap-0 flex-1"):
                                    ui.label(row["filename"]).classes(
                                        "font-semibold"
                                    )
                                    ui.label(row["dest"]).classes(
                                        "text-sm text-slate-500"
                                    )
                                    if row["action"] == "replace" and row["file"]:
                                        ui.label(
                                            f"replace → {row['file'][0]}"
                                        ).classes("text-xs text-indigo-400")

                                def mark_remove(r=row):
                                    r["action"] = "remove"
                                    render_extra_files.refresh()

                                ui.button(
                                    icon="delete",
                                    on_click=mark_remove,
                                ).props("flat round color=negative")

                            def on_replace_upload(e, r=row):
                                r["file"] = (e.name, e.content.read())
                                r["action"] = "replace"
                                render_extra_files.refresh()

                            ui.upload(
                                label="Drop replacement here or browse",
                                multiple=False,
                                auto_upload=True,
                                on_upload=on_replace_upload,
                            ).props("flat bordered").classes("w-full")

                    # -----------------------------------------
                    # New file
                    # -----------------------------------------

                    else:
                        with ui.row().classes("w-full gap-3 items-center flex-wrap"):
                            ui.upload(
                                label="File",
                                multiple=False,
                                auto_upload=True,
                                on_upload=(
                                    lambda e, r=row: r.__setitem__(
                                        "file",
                                        (
                                            e.name,
                                            e.content.read(),
                                        ),
                                    )
                                ),
                            ).props("flat bordered").classes("w-52")

                            ui.input(
                                "Destination",
                                value=row["dest"],
                                placeholder=("/etc/myapp/config.yaml"),
                            ).on(
                                "update:model-value",
                                lambda e, r=row: r.__setitem__(
                                    "dest",
                                    e.args or "",
                                ),
                            ).props("outlined dense").classes("flex-1 min-w-[280px]")

                            ui.checkbox(
                                "Config",
                                value=row["config"],
                            ).on(
                                "change",
                                lambda e, r=row: r.__setitem__(
                                    "config",
                                    bool(e.args),
                                ),
                            )

                            ui.input(
                                "Mode",
                                value=row["mode"],
                                placeholder="0644",
                            ).on(
                                "update:model-value",
                                lambda e, r=row: r.__setitem__(
                                    "mode",
                                    e.args or "",
                                ),
                            ).props("outlined dense").classes("w-24")

                            def delete_new_row(
                                i=index,
                            ):
                                state["extra"].pop(i)
                                render_extra_files.refresh()

                            ui.button(
                                icon="delete",
                                on_click=delete_new_row,
                            ).props("flat round color=negative")

        render_extra_files()

        def add_extra_file():

            state["extra"].append(
                {
                    "existing": False,
                    "filename": "",
                    "dest": "",
                    "config": False,
                    "mode": "0644",
                    "action": "add",
                    "file": None,
                }
            )

            render_extra_files.refresh()

        ui.button(
            "Add file",
            icon="add",
            on_click=add_extra_file,
        ).props("flat no-caps color=primary")


def _render_service_section(
    state: dict,
    is_update: bool,
    current_service: dict,
):

    with section_card(
        "Systemd service",
        (
            "Keep or replace the existing systemd unit."
            if is_update
            else "Optionally install and manage a systemd unit."
        ),
    ):
        service_switch = ui.switch(
            "Include systemd service",
            value=state["service_enabled"],
        ).props("color=primary")

        service_container = ui.column().classes("w-full gap-5 mt-3")

        with service_container:
            if is_update and current_service:
                with ui.card().classes(
                    "w-full bg-[#0d0d12] border border-slate-800 shadow-none p-4"
                ):
                    ui.label("Current service").classes("text-sm text-slate-500")

                    ui.label(
                        current_service.get(
                            "unit",
                            "systemd unit",
                        )
                    ).classes("font-semibold")

            ui.upload(
                label=("Replace service unit" if is_update else "Upload .service"),
                multiple=False,
                auto_upload=True,
                on_upload=lambda e: store_upload(
                    state,
                    "service_unit",
                    e,
                ),
            ).props('accept=".service" flat bordered').classes("w-full")

            with ui.expansion(
                "Advanced lifecycle scripts",
                icon="tune",
            ).classes("w-full"):
                with ui.row().classes("gap-3 flex-wrap"):
                    for hook in (
                        "preinstall",
                        "postinstall",
                        "preremove",
                        "postremove",
                    ):
                        ui.upload(
                            label=hook,
                            multiple=False,
                            auto_upload=True,
                            on_upload=(
                                lambda e, h=hook: store_upload(
                                    state["service_scripts"],
                                    h,
                                    e,
                                )
                            ),
                        ).props("flat bordered").classes("w-44")

        service_container.set_visibility(state["service_enabled"])

        def toggle_service(event):

            state["service_enabled"] = bool(event.value)

            service_container.set_visibility(bool(event.value))

        service_switch.on_value_change(toggle_service)


def _render_response_section() -> ResponsePanel:

    with ui.card().classes(
        "w-full bg-[#0d0d12] border border-slate-800 shadow-none p-0 overflow-hidden"
    ):
        with ui.row().classes(
            "w-full items-center px-5 py-3 border-b border-slate-800"
        ):
            ui.label("Response").classes("text-xl font-semibold")

            ui.space()

            status = ui.label("—").classes("text-sm font-medium text-slate-500")

            time_label = ui.label("— ms").classes("text-sm text-slate-500")

            size = ui.label("— B").classes("text-sm text-slate-500")

        with ui.tabs().classes("w-full border-b border-slate-800") as response_tabs:
            body_tab = ui.tab("Body")
            headers_tab = ui.tab("Headers")

        with ui.tab_panels(
            response_tabs,
            value=body_tab,
        ).classes("w-full bg-transparent"):
            with ui.tab_panel(body_tab).classes("p-0"):
                body = ui.code(
                    json.dumps(
                        {"status": "waiting"},
                        indent=2,
                    ),
                    language="json",
                ).classes(
                    "w-full "
                    "bg-transparent "
                    "text-sm "
                    "p-5 "
                    "min-h-[180px] "
                    "max-h-[500px] "
                    "overflow-auto"
                )

            with ui.tab_panel(headers_tab).classes("p-0"):
                headers = ui.code(
                    "{}",
                    language="json",
                ).classes(
                    "w-full "
                    "bg-transparent "
                    "text-sm "
                    "p-5 "
                    "min-h-[180px] "
                    "max-h-[500px] "
                    "overflow-auto"
                )

    return ResponsePanel(
        status=status,
        time=time_label,
        size=size,
        body=body,
        headers=headers,
    )


def _render_submit_section(
    is_update: bool,
):

    with ui.card().classes(
        "w-full bg-[#111116] border border-slate-800 shadow-none p-5"
    ):
        with ui.row().classes("w-full items-center"):
            with ui.column().classes("gap-0"):
                ui.label(
                    ("Ready to update?" if is_update else "Ready to build?")
                ).classes("font-semibold text-xl")

                if is_update:
                    ui.label("Unchanged files will remain untouched.").classes(
                        "text-sm text-slate-500"
                    )

            ui.space()

            submit_button = (
                ui.button(
                    ("Publish update" if is_update else "Build & Publish"),
                    icon=("upgrade" if is_update else "rocket_launch"),
                )
                .props("unelevated no-caps color=primary")
                .classes("px-5")
            )

    return submit_button


# =====================================================================
# Orchestrator
# =====================================================================


def render_package_form(
    mode: str,
    package: dict | None,
):

    is_update = mode == "update"

    package = package or {}

    current_binary = package.get("binary") or {}

    current_service = package.get("service") or {}

    state = init_state(package)

    # --- Sections ---

    (
        name_input,
        version_input,
        arch_input,
    ) = _render_metadata_section(
        package,
        is_update,
    )

    binary_destination_input = _render_binary_section(
        state,
        package,
        is_update,
        current_binary,
    )

    _render_extra_files_section(
        state,
        is_update,
    )

    _render_service_section(
        state,
        is_update,
        current_service,
    )

    panel = _render_response_section()

    submit_button = _render_submit_section(is_update)

    # --- Submit ---

    async def submit():

        try:
            fields = {
                "name": name_input.value,
                "version": version_input.value,
                "arch": arch_input.value,
                "binary_destination": (binary_destination_input.value),
            }

            spec, files = build_spec(
                mode,
                state,
                fields,
                current_service,
            )

        except ValueError as exc:
            ui.notify(
                str(exc),
                type="negative",
            )

            return

        submit_button.disable()

        panel.status.set_text("Sending...")

        panel.time.set_text("— ms")

        panel.size.set_text("— B")

        try:
            started = time.perf_counter()

            if is_update:
                response = await api.update_package(
                    spec["name"],
                    spec,
                    files,
                )

            else:
                response = await api.publish(
                    spec,
                    files,
                )

            elapsed = (time.perf_counter() - started) * 1000

            panel.set(response, elapsed)

            if response.is_success:
                ui.notify(
                    ("Package updated" if is_update else "Package published"),
                    type="positive",
                )

            else:
                ui.notify(
                    f"Request failed: {response.status_code}",
                    type="negative",
                )

        except httpx.HTTPError as exc:
            panel.mark_network_error(exc)

        finally:
            submit_button.enable()

    submit_button.on_click(submit)
