from __future__ import annotations

import httpx

from nicegui import ui

import api
from common import page_layout


@ui.page("/")
async def packages_page():

    with page_layout(
        "Packages",
        "Packages currently available in the repository.",
    ):
        # -----------------------------------------------------
        # Toolbar
        # -----------------------------------------------------

        with ui.row().classes("w-full items-center"):
            ui.label("Package repository").classes("text-xl font-semibold")

            ui.space()

            ui.button(
                "New package",
                icon="add",
                on_click=lambda: ui.navigate.to("/packages/new"),
            ).props("unelevated no-caps color=primary")

        # -----------------------------------------------------
        # Load packages
        # -----------------------------------------------------

        try:
            data = await api.list_packages()

        except httpx.HTTPError as exc:
            with ui.card().classes(
                "w-full bg-[#111116] border border-red-900 shadow-none p-6"
            ):
                ui.label("Could not load packages").classes(
                    "text-lg font-semibold text-red-400"
                )

                ui.label(str(exc)).classes("text-sm text-slate-500")

            return

        # Support either:
        #
        # [ {...}, {...} ]
        #
        # or
        #
        # { "packages": [...] }

        if isinstance(data, dict):
            packages = data.get("packages", [])
        else:
            packages = data

        # -----------------------------------------------------
        # Empty state
        # -----------------------------------------------------

        if not packages:
            with ui.card().classes(
                "w-full bg-[#111116] border border-slate-800 shadow-none p-10"
            ):
                with ui.column().classes("w-full items-center gap-3"):
                    ui.icon("inventory_2").classes("text-5xl text-slate-600")

                    ui.label("No packages yet").classes("text-xl font-semibold")

                    ui.label("Publish your first package to get started.").classes(
                        "text-sm text-slate-500"
                    )

                    ui.button(
                        "New package",
                        icon="add",
                        on_click=lambda: ui.navigate.to("/packages/new"),
                    ).props("unelevated no-caps color=primary")

            return

        # -----------------------------------------------------
        # Package list
        # -----------------------------------------------------

        with ui.card().classes(
            "w-full "
            "bg-[#111116] "
            "border border-slate-800 "
            "shadow-none p-0 overflow-hidden"
        ):
            # Header

            with ui.row().classes(
                "w-full px-6 py-4 border-b border-slate-800 items-center"
            ):
                ui.label("Package").classes("w-[35%] text-sm text-slate-500")

                ui.label("Version").classes("w-[20%] text-sm text-slate-500")

                ui.label("Architecture").classes("w-[20%] text-sm text-slate-500")

                ui.label("Actions").classes("flex-1 text-right text-sm text-slate-500")

            # Rows

            for package in packages:
                name = package.get(
                    "name",
                    "unknown",
                )

                version = package.get(
                    "version",
                    package.get(
                        "latest_version",
                        "—",
                    ),
                )

                arch = package.get(
                    "arch",
                    "—",
                )

                with ui.row().classes(
                    "w-full "
                    "px-6 py-4 "
                    "items-center "
                    "border-b border-slate-800 "
                    "last:border-b-0"
                ):
                    # Package
                    with ui.row().classes("w-[35%] items-center gap-3"):
                        ui.icon("inventory_2").classes("text-indigo-400")

                        ui.label(name).classes("font-semibold")

                    # Version
                    ui.label(version).classes("w-[20%]")

                    # Arch
                    ui.label(arch).classes("w-[20%] text-slate-400")

                    # Actions
                    with ui.row().classes("flex-1 justify-end gap-1"):
                        ui.button(
                            "Update",
                            icon="upgrade",
                            on_click=(
                                lambda n=name: ui.navigate.to(f"/packages/{n}/edit")
                            ),
                        ).props("flat no-caps color=grey-4")

                        ui.button(
                            icon="delete",
                            on_click=(lambda n=name: open_delete(n)),
                        ).props("flat round color=negative")


def open_delete(
    name: str,
):

    with ui.dialog() as dialog:
        with ui.card().classes("w-[460px] bg-[#111116] border border-slate-800 p-6"):
            ui.label(f"Delete {name}?").classes("text-xl font-semibold")

            ui.label("This removes the package from the repository.").classes(
                "text-sm text-slate-500"
            )

            async def confirm():
                response = await api.delete_package(name)

                if response.is_success:
                    ui.notify(
                        f"{name} deleted",
                        type="positive",
                    )
                    dialog.close()
                    ui.navigate.reload()

                else:
                    ui.notify(
                        f"Delete failed: {response.status_code}",
                        type="negative",
                    )

            with ui.row().classes("w-full justify-end mt-4"):
                ui.button(
                    "Cancel",
                    on_click=dialog.close,
                ).props("flat no-caps")

                ui.button(
                    "Delete",
                    icon="delete",
                    on_click=confirm,
                ).props("unelevated no-caps color=negative")

    dialog.open()
